"""
Aggregator Agent for ACE Pipeline (v2)

The Aggregator is the strategic architect. It runs per-batch (not per-query)
and makes structural decisions based on trends and patterns across multiple queries.

Responsibilities:
- Analyze patterns across all queries in the batch
- Process deferred proposals from Curator
- Create new categories when needed
- Merge/dedupe similar bullets
- Prune low-value bullets
- Restructure sections for better organization

Uses Opus model for deep strategic reasoning (expensive, but justified per-batch).
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .playbook_utils import (
    Bullet,
    DeltaOp,
    OpType,
    Playbook,
    apply_operation,
    apply_operations,
    get_playbook_stats,
    load_playbook,
    save_playbook,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FailurePattern:
    """A pattern of failures detected across queries."""
    category: str
    frequency: int
    description: str
    affected_run_ids: list[str]
    suggested_action: str


@dataclass
class AggregatorDecision:
    """A decision made by the Aggregator."""
    action: str  # "APPLY", "MERGE", "PRUNE", "NEW_CATEGORY", "RESTRUCTURE", "REJECT"
    rationale: str
    proposals_addressed: list[str]  # run_ids of proposals this handles
    changes_applied: list[dict]


@dataclass
class AggregatorResult:
    """Result from Aggregator batch processing."""
    batch_id: str

    # Input summary
    curator_logs_processed: int
    proposals_received: int
    proposals_by_type: dict[str, int]

    # Pattern analysis
    failure_patterns: list[FailurePattern] = field(default_factory=list)

    # Decisions made
    decisions: list[AggregatorDecision] = field(default_factory=list)

    # Changes applied
    bullets_added: int = 0
    bullets_updated: int = 0
    bullets_deleted: int = 0
    bullets_merged: int = 0
    categories_created: int = 0

    # Proposals handled
    proposals_applied: int = 0
    proposals_rejected: int = 0
    rejected_proposals: list[dict] = field(default_factory=list)

    # Stats
    stats_before: dict = field(default_factory=dict)
    stats_after: dict = field(default_factory=dict)

    # Metrics
    latency_seconds: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "curator_logs_processed": self.curator_logs_processed,
            "proposals_received": self.proposals_received,
            "proposals_by_type": self.proposals_by_type,
            "failure_patterns": [
                {
                    "category": fp.category,
                    "frequency": fp.frequency,
                    "description": fp.description,
                    "affected_run_ids": fp.affected_run_ids,
                    "suggested_action": fp.suggested_action,
                }
                for fp in self.failure_patterns
            ],
            "decisions": [
                {
                    "action": d.action,
                    "rationale": d.rationale,
                    "proposals_addressed": d.proposals_addressed,
                    "changes_applied": d.changes_applied,
                }
                for d in self.decisions
            ],
            "bullets_added": self.bullets_added,
            "bullets_updated": self.bullets_updated,
            "bullets_deleted": self.bullets_deleted,
            "bullets_merged": self.bullets_merged,
            "categories_created": self.categories_created,
            "proposals_applied": self.proposals_applied,
            "proposals_rejected": self.proposals_rejected,
            "rejected_proposals": self.rejected_proposals,
            "stats_before": self.stats_before,
            "stats_after": self.stats_after,
            "latency_seconds": self.latency_seconds,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
        }


# =============================================================================
# Aggregator Class
# =============================================================================

class Aggregator:
    """Strategic architect for batch-level knowledge evolution.

    The Aggregator analyzes patterns across a batch of queries and makes
    structural decisions about the knowledge base:

    - Which deferred proposals to apply?
    - Should we create new categories?
    - Should we merge similar bullets?
    - Should we prune low-value bullets?
    - How should sections be reorganized?

    Uses Opus model for deep strategic reasoning.
    """

    # Model configuration
    MODEL = "claude-opus-4-5"
    MAX_TOKENS = 8192

    # Thresholds
    MIN_HARMFUL_TO_PRUNE = 3  # Minimum harmful count to consider pruning
    MIN_PROPOSALS_TO_MERGE = 2  # Minimum similar proposals to consider merging

    def __init__(
        self,
        knowledge_dir: Path | None = None,
        curator_log_dir: Path | None = None,
        reflector_log_dir: Path | None = None,
        aggregator_log_dir: Path | None = None,
    ):
        """Initialize the Aggregator.

        Args:
            knowledge_dir: Path to knowledge files
            curator_log_dir: Path to curator logs (for deferred proposals)
            reflector_log_dir: Path to reflector logs (for failure analysis)
            aggregator_log_dir: Path to aggregator logs
        """
        self.ace_root = Path(__file__).parent
        self.knowledge_dir = knowledge_dir or self.ace_root / "knowledge"
        self.curator_log_dir = curator_log_dir or self.ace_root / "logs" / "curator"
        self.reflector_log_dir = reflector_log_dir or self.ace_root / "logs" / "reflector"
        self.aggregator_log_dir = aggregator_log_dir or self.ace_root / "logs" / "aggregator"

        # Ensure directories exist
        self.aggregator_log_dir.mkdir(parents=True, exist_ok=True)

    def read_curator_logs(self) -> list[dict]:
        """Read all curator logs from the directory."""
        logs = []
        if not self.curator_log_dir.exists():
            return logs

        for log_file in sorted(self.curator_log_dir.glob("curator_*.json")):
            try:
                with open(log_file) as f:
                    logs.append(json.load(f))
            except (json.JSONDecodeError, IOError):
                continue
        return logs

    def read_reflector_logs(self) -> list[dict]:
        """Read all reflector logs from the directory."""
        logs = []
        if not self.reflector_log_dir.exists():
            return logs

        for log_file in sorted(self.reflector_log_dir.glob("*.json")):
            try:
                with open(log_file) as f:
                    logs.append(json.load(f))
            except (json.JSONDecodeError, IOError):
                continue
        return logs

    def clear_curator_logs(self) -> int:
        """Clear processed curator logs."""
        count = 0
        if self.curator_log_dir.exists():
            for log_file in self.curator_log_dir.glob("curator_*.json"):
                try:
                    log_file.unlink()
                    count += 1
                except IOError:
                    continue
        return count

    def _load_all_playbooks(self) -> dict[str, Playbook]:
        """Load all knowledge playbooks."""
        playbooks = {}
        for name in ["schema.md", "examples.md"]:
            path = self.knowledge_dir / name
            if path.exists():
                playbooks[name] = load_playbook(path)
        return playbooks

    def _get_combined_stats(self, playbooks: dict[str, Playbook]) -> dict:
        """Get combined stats across all playbooks."""
        total_bullets = 0
        total_helpful = 0
        total_harmful = 0
        sections = {}

        for name, pb in playbooks.items():
            stats = get_playbook_stats(pb)
            total_bullets += stats["total_bullets"]
            total_helpful += stats["total_helpful"]
            total_harmful += stats["total_harmful"]
            for sec_name, sec_stats in stats["sections"].items():
                sections[f"{name}:{sec_name}"] = sec_stats

        return {
            "total_bullets": total_bullets,
            "total_helpful": total_helpful,
            "total_harmful": total_harmful,
            "avg_net_score": (total_helpful - total_harmful) / total_bullets if total_bullets > 0 else 0,
            "sections": sections,
        }

    def _collect_deferred_proposals(self, curator_logs: list[dict]) -> list[dict]:
        """Collect all deferred proposals from curator logs."""
        proposals = []
        for log in curator_logs:
            for proposal in log.get("deferred_proposals", []):
                proposals.append(proposal)
        return proposals

    def _analyze_failure_patterns(self, reflector_logs: list[dict]) -> list[FailurePattern]:
        """Analyze failure patterns from reflector logs."""
        # Group by issue categories
        categories: dict[str, list[dict]] = {}

        for log in reflector_logs:
            issues = log.get("analysis", {}).get("issues_found", [])
            for issue in issues:
                category = issue.get("category", "unknown")
                if category not in categories:
                    categories[category] = []
                categories[category].append({
                    "run_id": log.get("run_id", "unknown"),
                    "description": issue.get("description", ""),
                    "severity": issue.get("severity", "medium"),
                })

        # Convert to FailurePattern objects
        patterns = []
        for category, issues in categories.items():
            if len(issues) >= 2:  # Only report if pattern repeats
                patterns.append(FailurePattern(
                    category=category,
                    frequency=len(issues),
                    description=f"{len(issues)} queries failed due to {category}",
                    affected_run_ids=[i["run_id"] for i in issues],
                    suggested_action=self._suggest_action_for_pattern(category, issues),
                ))

        return sorted(patterns, key=lambda p: p.frequency, reverse=True)

    def _suggest_action_for_pattern(self, category: str, issues: list[dict]) -> str:
        """Suggest action for a failure pattern."""
        category_lower = category.lower()

        if "temporal" in category_lower or "date" in category_lower:
            return "Add bullet clarifying date handling and temporal granularity"
        elif "metric" in category_lower or "calculation" in category_lower:
            return "Add bullet with correct formula or metric definition"
        elif "schema" in category_lower or "column" in category_lower:
            return "Add bullet documenting schema or column definitions"
        elif "tool" in category_lower:
            return "Add example demonstrating correct tool usage"
        else:
            return "Review and add clarifying bullet"

    def _identify_harmful_bullets(self, playbooks: dict[str, Playbook]) -> list[tuple[str, Bullet, str]]:
        """Identify bullets with high harmful counts that might need pruning."""
        harmful = []

        for name, pb in playbooks.items():
            for section in pb.sections:
                for bullet in section.bullets:
                    net_score = bullet.helpful_count - bullet.harmful_count
                    if bullet.harmful_count >= self.MIN_HARMFUL_TO_PRUNE and net_score < 0:
                        harmful.append((name, bullet, section.name))

        return sorted(harmful, key=lambda x: x[1].harmful_count, reverse=True)

    async def aggregate(self) -> AggregatorResult:
        """Run batch-level aggregation.

        Process:
        1. Read all curator logs and collect deferred proposals
        2. Read reflector logs for failure pattern analysis
        3. Analyze patterns and cluster proposals
        4. Use LLM to make strategic decisions
        5. Apply decisions to knowledge base
        6. Log results

        Returns:
            AggregatorResult with decisions and applied changes
        """
        start_time = time.time()
        batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Read inputs
        curator_logs = self.read_curator_logs()
        reflector_logs = self.read_reflector_logs()

        if not curator_logs and not reflector_logs:
            return AggregatorResult(
                batch_id=batch_id,
                curator_logs_processed=0,
                proposals_received=0,
                proposals_by_type={},
            )

        # Collect deferred proposals
        proposals = self._collect_deferred_proposals(curator_logs)

        # Count proposals by type
        proposals_by_type: dict[str, int] = {}
        for p in proposals:
            ptype = p.get("type", "UNKNOWN")
            proposals_by_type[ptype] = proposals_by_type.get(ptype, 0) + 1

        # Load playbooks and get stats
        playbooks = self._load_all_playbooks()
        stats_before = self._get_combined_stats(playbooks)

        # Analyze failure patterns
        failure_patterns = self._analyze_failure_patterns(reflector_logs)

        # Identify harmful bullets for potential pruning
        harmful_bullets = self._identify_harmful_bullets(playbooks)

        # Use LLM to make strategic decisions
        decisions, tokens_used = await self._make_strategic_decisions(
            proposals=proposals,
            failure_patterns=failure_patterns,
            harmful_bullets=harmful_bullets,
            playbooks=playbooks,
        )

        # Apply decisions
        applied, rejected = self._apply_decisions(decisions, playbooks)

        # Save playbooks
        for pb in playbooks.values():
            save_playbook(pb)

        # Get stats after
        playbooks_after = self._load_all_playbooks()
        stats_after = self._get_combined_stats(playbooks_after)

        # Count changes
        bullets_added = sum(1 for d in applied if d.action == "APPLY" and "ADD" in str(d.changes_applied))
        bullets_updated = sum(1 for d in applied if d.action == "APPLY" and "UPDATE" in str(d.changes_applied))
        bullets_deleted = sum(1 for d in applied if d.action in ["PRUNE", "DELETE"])
        bullets_merged = sum(1 for d in applied if d.action == "MERGE")
        categories_created = sum(1 for d in applied if d.action == "NEW_CATEGORY")

        # Clear processed logs
        self.clear_curator_logs()

        # Calculate cost (Opus pricing)
        # Input: $15/M tokens, Output: $75/M tokens
        # Rough estimate: 70% input, 30% output
        cost = (tokens_used * 0.7 * 15 + tokens_used * 0.3 * 75) / 1_000_000

        result = AggregatorResult(
            batch_id=batch_id,
            curator_logs_processed=len(curator_logs),
            proposals_received=len(proposals),
            proposals_by_type=proposals_by_type,
            failure_patterns=failure_patterns,
            decisions=applied + rejected,
            bullets_added=bullets_added,
            bullets_updated=bullets_updated,
            bullets_deleted=bullets_deleted,
            bullets_merged=bullets_merged,
            categories_created=categories_created,
            proposals_applied=len(applied),
            proposals_rejected=len(rejected),
            rejected_proposals=[{"action": d.action, "rationale": d.rationale} for d in rejected],
            stats_before=stats_before,
            stats_after=stats_after,
            latency_seconds=time.time() - start_time,
            total_tokens=tokens_used,
            total_cost_usd=cost,
        )

        # Save aggregator log
        self._save_aggregator_log(result)

        return result

    async def _make_strategic_decisions(
        self,
        proposals: list[dict],
        failure_patterns: list[FailurePattern],
        harmful_bullets: list[tuple[str, Bullet, str]],
        playbooks: dict[str, Playbook],
    ) -> tuple[list[AggregatorDecision], int]:
        """Use LLM to make strategic decisions about knowledge evolution.

        Returns:
            (decisions, tokens_used)
        """
        if not proposals and not failure_patterns and not harmful_bullets:
            return [], 0

        # Build context about current knowledge base
        kb_summary = self._summarize_knowledge_base(playbooks)

        # Build the prompt
        prompt = self._build_aggregator_prompt(
            proposals=proposals,
            failure_patterns=failure_patterns,
            harmful_bullets=harmful_bullets,
            kb_summary=kb_summary,
        )

        try:
            options = ClaudeAgentOptions(
                model=self.MODEL,
                max_turns=1,
                system_prompt="You are a strategic architect for a self-improving knowledge base. Return only valid JSON.",
                cwd=str(Path(__file__).parent),
                allowed_tools=[],
                permission_mode="acceptEdits",
                max_budget_usd=0.50,  # Opus is expensive
            )

            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)
                response_text = ""
                tokens_used = 0

                for msg in client.get_conversation():
                    if msg.get("role") == "assistant":
                        for block in msg.get("content", []):
                            if block.get("type") == "text":
                                response_text = block.get("text", "")
                    if "usage" in msg:
                        tokens_used += msg["usage"].get("input_tokens", 0)
                        tokens_used += msg["usage"].get("output_tokens", 0)

            # Parse the response
            decisions = self._parse_aggregator_response(response_text, proposals)

            return decisions, tokens_used

        except Exception as e:
            logger.error(f"Aggregator LLM call failed: {e}")
            # Fall back to simple rule-based decisions
            return self._fallback_decisions(proposals, harmful_bullets), 0

    def _summarize_knowledge_base(self, playbooks: dict[str, Playbook]) -> str:
        """Create a summary of the current knowledge base."""
        lines = ["## Current Knowledge Base\n"]

        for name, pb in playbooks.items():
            stats = get_playbook_stats(pb)
            lines.append(f"### {name}")
            lines.append(f"- Total bullets: {stats['total_bullets']}")
            lines.append(f"- Total helpful: {stats['total_helpful']}")
            lines.append(f"- Total harmful: {stats['total_harmful']}")
            lines.append(f"- Sections: {len(pb.sections)}")
            lines.append("")

            for section in pb.sections:
                lines.append(f"  - {section.name}: {len(section.bullets)} bullets")

        return "\n".join(lines)

    def _build_aggregator_prompt(
        self,
        proposals: list[dict],
        failure_patterns: list[FailurePattern],
        harmful_bullets: list[tuple[str, Bullet, str]],
        kb_summary: str,
    ) -> str:
        """Build the prompt for the Aggregator LLM call."""
        prompt_parts = [
            "You are the Aggregator for the ACE (Agentic Counterfactual Expansion) pipeline.",
            "Your role is to make strategic decisions about evolving the knowledge base based on batch-level patterns.",
            "",
            "IMPORTANT PRINCIPLES:",
            "1. Be conservative - only make changes with strong evidence",
            "2. Cluster similar proposals - don't add duplicates",
            "3. Consider long-term impact - avoid knowledge churn",
            "4. Prefer updates over deletions - preserve working knowledge",
            "5. Only create new categories when clearly justified",
            "",
            kb_summary,
            "",
        ]

        # Add proposals
        if proposals:
            prompt_parts.append("## Deferred Proposals from Curator\n")
            for i, p in enumerate(proposals, 1):
                prompt_parts.append(f"{i}. Type: {p.get('type', 'UNKNOWN')}")
                prompt_parts.append(f"   Priority: {p.get('priority', 'low')}")
                prompt_parts.append(f"   Confidence: {p.get('confidence', 0.5):.2f}")
                prompt_parts.append(f"   Content: {(p.get('content') or 'N/A')[:200]}")
                prompt_parts.append(f"   Rationale: {(p.get('rationale') or 'N/A')[:200]}")
                prompt_parts.append(f"   Reason deferred: {p.get('reason_deferred', 'N/A')}")
                prompt_parts.append("")

        # Add failure patterns
        if failure_patterns:
            prompt_parts.append("## Failure Patterns Detected\n")
            for fp in failure_patterns[:5]:  # Top 5
                prompt_parts.append(f"- {fp.category}: {fp.frequency} occurrences")
                prompt_parts.append(f"  Description: {fp.description}")
                prompt_parts.append(f"  Suggested action: {fp.suggested_action}")
                prompt_parts.append("")

        # Add harmful bullets
        if harmful_bullets:
            prompt_parts.append("## Potentially Harmful Bullets (consider pruning)\n")
            for name, bullet, section in harmful_bullets[:5]:  # Top 5
                net = bullet.helpful_count - bullet.harmful_count
                prompt_parts.append(f"- [{bullet.bullet_id}] in {name}:{section}")
                prompt_parts.append(f"  Content: {bullet.text[:100]}...")
                prompt_parts.append(f"  Stats: helpful={bullet.helpful_count}, harmful={bullet.harmful_count}, net={net}")
                prompt_parts.append("")

        # Request format
        prompt_parts.append("""
## Your Task

Analyze the proposals, patterns, and harmful bullets. Make strategic decisions.

Output your decisions in this JSON format:
```json
{
  "decisions": [
    {
      "action": "APPLY|MERGE|PRUNE|NEW_CATEGORY|RESTRUCTURE|REJECT",
      "rationale": "Why this decision",
      "proposals_addressed": [1, 2],  // indices of proposals this handles (1-indexed)
      "changes": [
        {"op": "ADD|UPDATE|DELETE", "content": "...", "section": "...", "bullet_id": "..."}
      ]
    }
  ]
}
```

Actions:
- APPLY: Apply proposal(s) as-is
- MERGE: Combine similar proposals into one bullet
- PRUNE: Delete a harmful bullet
- NEW_CATEGORY: Create a new section/category
- RESTRUCTURE: Reorganize existing bullets
- REJECT: Decline proposal(s) with reason

Be concise and strategic. Only make changes with clear benefit.
""")

        return "\n".join(prompt_parts)

    def _parse_aggregator_response(self, response_text: str, proposals: list[dict]) -> list[AggregatorDecision]:
        """Parse the LLM response into decisions."""
        decisions = []

        # Try to extract JSON from response
        try:
            # Find JSON block
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = response_text[start:end]
                data = json.loads(json_str)

                for d in data.get("decisions", []):
                    # Map proposal indices to run_ids
                    addressed_indices = d.get("proposals_addressed", [])
                    addressed_run_ids = []
                    for idx in addressed_indices:
                        if 1 <= idx <= len(proposals):
                            run_id = proposals[idx - 1].get("source_run_id", f"proposal_{idx}")
                            addressed_run_ids.append(run_id)

                    decisions.append(AggregatorDecision(
                        action=d.get("action", "REJECT"),
                        rationale=d.get("rationale", ""),
                        proposals_addressed=addressed_run_ids,
                        changes_applied=d.get("changes", []),
                    ))
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse aggregator response: {e}")

        return decisions

    def _fallback_decisions(
        self,
        proposals: list[dict],
        harmful_bullets: list[tuple[str, Bullet, str]],
    ) -> list[AggregatorDecision]:
        """Fallback rule-based decisions when LLM fails."""
        decisions = []

        # Apply high-priority ADD proposals
        for i, p in enumerate(proposals):
            if p.get("type") == "ADD" and p.get("priority") == "high" and p.get("confidence", 0) >= 0.7:
                decisions.append(AggregatorDecision(
                    action="APPLY",
                    rationale="High-priority, high-confidence ADD (fallback)",
                    proposals_addressed=[p.get("source_run_id", f"proposal_{i}")],
                    changes_applied=[{
                        "op": "ADD",
                        "content": p.get("content", ""),
                        "section": p.get("section", "General"),
                    }],
                ))

        # Prune very harmful bullets
        for name, bullet, section in harmful_bullets:
            net = bullet.helpful_count - bullet.harmful_count
            if net <= -3:  # Very harmful
                decisions.append(AggregatorDecision(
                    action="PRUNE",
                    rationale=f"Net score {net} indicates harmful bullet (fallback)",
                    proposals_addressed=[],
                    changes_applied=[{
                        "op": "DELETE",
                        "bullet_id": bullet.bullet_id,
                        "section": section,
                    }],
                ))

        return decisions

    def _apply_decisions(
        self,
        decisions: list[AggregatorDecision],
        playbooks: dict[str, Playbook],
    ) -> tuple[list[AggregatorDecision], list[AggregatorDecision]]:
        """Apply decisions to playbooks.

        Returns:
            (applied_decisions, rejected_decisions)
        """
        applied = []
        rejected = []

        for decision in decisions:
            if decision.action == "REJECT":
                rejected.append(decision)
                continue

            try:
                if decision.action in ["APPLY", "MERGE", "NEW_CATEGORY"]:
                    self._apply_change_decision(decision, playbooks)
                    applied.append(decision)
                elif decision.action == "PRUNE":
                    self._apply_prune_decision(decision, playbooks)
                    applied.append(decision)
                elif decision.action == "RESTRUCTURE":
                    # For now, log restructure but don't auto-apply
                    logger.info(f"Restructure decision logged: {decision.rationale}")
                    rejected.append(AggregatorDecision(
                        action="REJECT",
                        rationale=f"Restructure deferred for manual review: {decision.rationale}",
                        proposals_addressed=decision.proposals_addressed,
                        changes_applied=[],
                    ))
                else:
                    rejected.append(decision)
            except Exception as e:
                logger.error(f"Failed to apply decision: {e}")
                rejected.append(AggregatorDecision(
                    action="REJECT",
                    rationale=f"Failed to apply: {e}",
                    proposals_addressed=decision.proposals_addressed,
                    changes_applied=[],
                ))

        return applied, rejected

    def _apply_change_decision(
        self,
        decision: AggregatorDecision,
        playbooks: dict[str, Playbook],
    ) -> None:
        """Apply ADD/UPDATE changes from a decision."""
        for change in decision.changes_applied:
            op_str = change.get("op", "ADD")
            content = change.get("content", "")
            section = change.get("section", "General")
            bullet_id = change.get("bullet_id")

            # Determine target playbook
            target = "schema.md"
            if section and ("example" in section.lower() or "pattern" in section.lower()):
                target = "examples.md"

            pb = playbooks.get(target)
            if not pb:
                continue

            if op_str == "ADD" and content:
                op = DeltaOp(
                    op_type=OpType.ADD,
                    section=section,
                    content=content,
                    reason=decision.rationale,
                )
                apply_operation(pb, op)
            elif op_str == "UPDATE" and bullet_id and content:
                op = DeltaOp(
                    op_type=OpType.UPDATE,
                    bullet_id=bullet_id,
                    content=content,
                    reason=decision.rationale,
                )
                apply_operation(pb, op)

    def _apply_prune_decision(
        self,
        decision: AggregatorDecision,
        playbooks: dict[str, Playbook],
    ) -> None:
        """Apply DELETE/PRUNE from a decision."""
        for change in decision.changes_applied:
            bullet_id = change.get("bullet_id")
            if not bullet_id:
                continue

            # Find and remove from any playbook
            for pb in playbooks.values():
                for section in pb.sections:
                    section.bullets = [b for b in section.bullets if b.bullet_id != bullet_id]

    def _save_aggregator_log(self, result: AggregatorResult) -> Path:
        """Save aggregator result to log file."""
        log_path = self.aggregator_log_dir / f"aggregator_{result.batch_id}.json"

        with open(log_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        return log_path


# =============================================================================
# Test
# =============================================================================

async def test_aggregator():
    """Test the Aggregator."""
    print("Testing Aggregator...")

    # Create some mock curator logs with deferred proposals
    curator_log_dir = Path(__file__).parent / "logs" / "curator"
    curator_log_dir.mkdir(parents=True, exist_ok=True)

    mock_curator_log = {
        "tags_processed": 5,
        "reflector_logs_processed": 2,
        "counter_updates": [],
        "bullets_added": [],
        "deferred_proposals": [
            {
                "type": "ADD",
                "priority": "medium",
                "confidence": 0.7,
                "content": "When querying quarterly data, always filter by both year AND quarter columns",
                "section": "Key_Rules",
                "rationale": "Multiple queries failed due to missing quarter filter",
                "source_run_id": "test_001",
                "reason_deferred": "Confidence 0.70 below threshold 0.8",
            },
            {
                "type": "ADD",
                "priority": "medium",
                "confidence": 0.65,
                "content": "Similar: Always verify date range matches the query intent",
                "section": "Key_Rules",
                "rationale": "Temporal issues detected",
                "source_run_id": "test_002",
                "reason_deferred": "Confidence 0.65 below threshold 0.8",
            },
            {
                "type": "DELETE",
                "priority": "high",
                "confidence": 0.8,
                "bullet_id": "sch-00001",
                "rationale": "This bullet is harmful and misleading",
                "source_run_id": "test_003",
                "reason_deferred": "DELETE operations require Aggregator review",
            },
        ],
        "stats_before": {},
        "stats_after": {},
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(curator_log_dir / f"curator_{timestamp}.json", "w") as f:
        json.dump(mock_curator_log, f)

    # Run aggregator
    aggregator = Aggregator()
    result = await aggregator.aggregate()

    print(f"\nAggregator Result:")
    print(f"  Batch ID: {result.batch_id}")
    print(f"  Curator logs processed: {result.curator_logs_processed}")
    print(f"  Proposals received: {result.proposals_received}")
    print(f"  Proposals by type: {result.proposals_by_type}")
    print(f"  Failure patterns: {len(result.failure_patterns)}")
    print(f"  Decisions made: {len(result.decisions)}")
    for d in result.decisions:
        print(f"    - {d.action}: {d.rationale[:60]}...")
    print(f"  Proposals applied: {result.proposals_applied}")
    print(f"  Proposals rejected: {result.proposals_rejected}")
    print(f"  Latency: {result.latency_seconds:.2f}s")
    print(f"  Tokens: {result.total_tokens}")
    print(f"  Cost: ${result.total_cost_usd:.4f}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_aggregator())
