"""
Curator Agent for ACE Pipeline

The Curator analyzes accumulated tags and applies delta operations to knowledge files.
Uses Sonnet for sophisticated analysis and decision-making.

Key responsibilities:
- Read accumulated tags from logs/tags.jsonl
- Update counters in knowledge files
- Generate delta operations: ADD, UPDATE, DELETE
- Apply operations atomically
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher
from claude_agent_sdk.types import HookContext

from .playbook_utils import (
    Bullet,
    BulletTag,
    DeltaOp,
    OpType,
    Playbook,
    Tag,
    apply_operations,
    get_playbook_stats,
    load_playbook,
    save_playbook,
    update_counters,
)

logger = logging.getLogger(__name__)


@dataclass
class CuratorResult:
    """Result from Curator curation cycle."""
    tags_processed: int
    counter_updates: list[dict]  # {bullet_id, helpful_delta, harmful_delta}
    operations: list[dict]  # DeltaOp as dicts
    operations_applied: int
    operations_failed: int

    # Stats before/after
    stats_before: dict
    stats_after: dict

    # Metrics
    latency_seconds: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tags_processed": self.tags_processed,
            "counter_updates": self.counter_updates,
            "operations": self.operations,
            "operations_applied": self.operations_applied,
            "operations_failed": self.operations_failed,
            "stats_before": self.stats_before,
            "stats_after": self.stats_after,
            "latency_seconds": self.latency_seconds,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
        }


def aggregate_tags(tags: list[dict]) -> dict[str, dict]:
    """Aggregate tag counts by bullet_id.

    Args:
        tags: List of tag entries from tags.jsonl

    Returns:
        Dict mapping bullet_id -> {helpful: int, harmful: int, neutral: int}
    """
    aggregated: dict[str, dict] = {}
    for t in tags:
        bid = t.get("bullet_id")
        if not bid:
            continue
        if bid not in aggregated:
            aggregated[bid] = {"helpful": 0, "harmful": 0, "neutral": 0}
        tag = t.get("tag", "neutral")
        if tag in aggregated[bid]:
            aggregated[bid][tag] += 1
    return aggregated


def compute_counter_updates(aggregated: dict[str, dict]) -> list[dict]:
    """Compute counter update deltas from aggregated tags.

    Args:
        aggregated: Dict from aggregate_tags()

    Returns:
        List of {bullet_id, helpful_delta, harmful_delta}
    """
    updates = []
    for bid, counts in aggregated.items():
        if counts["helpful"] > 0 or counts["harmful"] > 0:
            updates.append({
                "bullet_id": bid,
                "helpful_delta": counts["helpful"],
                "harmful_delta": counts["harmful"],
            })
    return updates


async def validate_curator_writes(
    input_data: dict,
    tool_use_id: str | None,
    context: HookContext,
) -> dict:
    """Hook to ensure Curator only writes to knowledge/ directory."""
    tool_name = input_data.get("tool_name", "")
    if tool_name not in ["Write", "Edit"]:
        return {}

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    path = Path(file_path)
    path_str = str(path)

    # Allow if path contains knowledge/ directory
    if "knowledge/" in path_str or path_str.startswith("knowledge"):
        return {}

    # Allow logs/ for curator trace writing
    if "logs/" in path_str:
        return {}

    # Block all other writes
    logger.warning(f"Curator blocked from writing to: {file_path}")
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Curator restricted to knowledge/ directory. Attempted: {file_path}"
        }
    }


class Curator:
    """Applies learned improvements to knowledge files."""

    DEFAULT_MODEL = "claude-sonnet-4-5"

    # Thresholds for delta operations
    HELPFUL_THRESHOLD = 5  # Minimum helpful count to consider a bullet "proven"
    HARMFUL_RATIO = 0.5  # Delete if harmful > helpful * ratio

    def __init__(
        self,
        knowledge_dir: Path | None = None,
        tags_log_path: Path | None = None,
        model: str | None = None,
        max_budget_usd: float = 0.50,
    ):
        """Initialize the Curator.

        Args:
            knowledge_dir: Path to knowledge files
            tags_log_path: Path to tags.jsonl
            model: Model to use (default: Sonnet 4.5)
            max_budget_usd: Maximum budget per curation
        """
        self.ace_root = Path(__file__).parent
        self.knowledge_dir = knowledge_dir or self.ace_root / "knowledge"
        self.tags_log_path = tags_log_path or self.ace_root / "logs" / "tags.jsonl"
        self.model = model or self.DEFAULT_MODEL
        self.max_budget_usd = max_budget_usd

        # Ensure directories exist
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.tags_log_path.parent.mkdir(parents=True, exist_ok=True)

    def read_tags(self) -> list[dict]:
        """Read all tags from the log file."""
        if not self.tags_log_path.exists():
            return []

        tags = []
        with open(self.tags_log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        tags.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return tags

    def clear_tags(self) -> int:
        """Clear the tags log file after processing."""
        count = len(self.read_tags())
        if self.tags_log_path.exists():
            self.tags_log_path.unlink()
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

    async def curate(self) -> CuratorResult:
        """Run a curation cycle.

        Reads accumulated tags, updates counters, and applies delta operations.

        Returns:
            CuratorResult with details of changes made
        """
        start_time = time.time()

        # Read tags
        tags = self.read_tags()
        if not tags:
            return CuratorResult(
                tags_processed=0,
                counter_updates=[],
                operations=[],
                operations_applied=0,
                operations_failed=0,
                stats_before={},
                stats_after={},
            )

        # Load playbooks and get stats
        playbooks = self._load_all_playbooks()
        stats_before = self._get_combined_stats(playbooks)

        # Aggregate tags and compute counter updates
        aggregated = aggregate_tags(tags)
        counter_updates = compute_counter_updates(aggregated)

        # Apply counter updates to playbooks
        for pb in playbooks.values():
            bullet_tags = []
            for update in counter_updates:
                bid = update["bullet_id"]
                # Create BulletTag for each helpful/harmful increment
                for _ in range(update["helpful_delta"]):
                    bullet_tags.append(BulletTag(bullet_id=bid, tag=Tag.HELPFUL))
                for _ in range(update["harmful_delta"]):
                    bullet_tags.append(BulletTag(bullet_id=bid, tag=Tag.HARMFUL))
            update_counters(pb, bullet_tags)

        # Analyze playbook state and generate delta operations
        operations = await self._generate_operations(playbooks, tags, aggregated)

        # Apply operations
        ops_applied = 0
        ops_failed = 0
        for op_dict in operations:
            op = DeltaOp(
                op_type=OpType[op_dict["type"]],
                section=op_dict.get("section"),
                bullet_id=op_dict.get("bullet_id"),
                content=op_dict.get("content"),
                reason=op_dict.get("reason"),
            )
            # Find the right playbook for this operation
            for name, pb in playbooks.items():
                if op.op_type == OpType.ADD:
                    # ADD goes to appropriate file based on section
                    if op.section and (
                        "example" in op.section.lower() or
                        "pattern" in op.section.lower()
                    ):
                        if name == "examples.md":
                            success, _ = apply_operations(pb, [op])
                            ops_applied += success
                            break
                    elif name == "schema.md":
                        success, _ = apply_operations(pb, [op])
                        ops_applied += success
                        break
                else:
                    # UPDATE/DELETE - find bullet in any playbook
                    if pb.get_bullet(op.bullet_id):
                        success, failed = apply_operations(pb, [op])
                        ops_applied += success
                        ops_failed += failed
                        break

        # Save all playbooks
        for pb in playbooks.values():
            save_playbook(pb)

        # Get stats after
        playbooks_after = self._load_all_playbooks()
        stats_after = self._get_combined_stats(playbooks_after)

        # Clear processed tags
        self.clear_tags()

        result = CuratorResult(
            tags_processed=len(tags),
            counter_updates=counter_updates,
            operations=operations,
            operations_applied=ops_applied,
            operations_failed=ops_failed,
            stats_before=stats_before,
            stats_after=stats_after,
            latency_seconds=time.time() - start_time,
        )

        # Save curator log
        self._save_curator_log(result)

        return result

    async def _generate_operations(
        self,
        playbooks: dict[str, Playbook],
        tags: list[dict],
        aggregated: dict[str, dict],
    ) -> list[dict]:
        """Use Sonnet to analyze and generate delta operations.

        Returns:
            List of operation dicts {type, section?, bullet_id?, content?, reason}
        """
        # Collect bullets with significant signal
        bullets_to_analyze = []
        for bid, counts in aggregated.items():
            total = counts["helpful"] + counts["harmful"]
            if total >= 2:  # At least some signal
                for pb in playbooks.values():
                    bullet = pb.get_bullet(bid)
                    if bullet:
                        bullets_to_analyze.append({
                            "id": bid,
                            "content": bullet.content[:200],
                            "helpful_total": bullet.helpful + counts["helpful"],
                            "harmful_total": bullet.harmful + counts["harmful"],
                            "helpful_new": counts["helpful"],
                            "harmful_new": counts["harmful"],
                        })
                        break

        # Collect insights from failed queries
        failure_insights = []
        for t in tags:
            if not t.get("is_correct") and t.get("insight"):
                failure_insights.append({
                    "query": t.get("query", "")[:100],
                    "insight": t.get("insight", "")[:200],
                })

        if not bullets_to_analyze and not failure_insights:
            return []

        # Build prompt for Sonnet
        prompt = f"""Analyze the knowledge base performance and recommend improvements.

## Bullet Performance
{json.dumps(bullets_to_analyze, indent=2)}

## Failure Insights
{json.dumps(failure_insights[:5], indent=2)}  # Limit to 5 most recent

## Guidelines
1. DELETE bullets where harmful_total > helpful_total (more harm than good)
2. UPDATE bullets that are helpful but could be clearer based on insights
3. ADD new bullets ONLY if failure insights reveal a clear knowledge gap

Be conservative: only recommend operations with clear justification.

Return a JSON array of operations:
[
    {{"type": "DELETE", "bullet_id": "xxx", "reason": "..."}},
    {{"type": "UPDATE", "bullet_id": "xxx", "content": "...", "reason": "..."}},
    {{"type": "ADD", "section": "Query_Patterns", "content": "...", "reason": "..."}}
]

Return [] if no operations are needed."""

        try:
            options = ClaudeAgentOptions(
                model=self.model,
                max_turns=1,
                system_prompt="You are a knowledge base curator. Return only valid JSON arrays.",
                cwd=str(self.ace_root),
                allowed_tools=[],
                permission_mode="acceptEdits",
                max_budget_usd=self.max_budget_usd,
            )

            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)
                response_text = ""
                async for message in client.receive_response():
                    if hasattr(message, 'content'):
                        for block in message.content:
                            if hasattr(block, 'text'):
                                response_text += block.text

            # Parse JSON array
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                operations = json.loads(json_str)
                return operations if isinstance(operations, list) else []

            return []

        except Exception as e:
            logger.error(f"Curator operation generation error: {e}")
            return []

    def _save_curator_log(self, result: CuratorResult) -> Path:
        """Save curator result to log file."""
        log_dir = self.ace_root / "logs" / "curator"
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"curator_{timestamp}.json"

        with open(log_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        return log_path


async def test_curator():
    """Test the Curator."""
    from .playbook_utils import BulletTag, Tag
    from .reflector import Reflector

    # Create some mock tags
    reflector = Reflector()

    # Manually add some test tags
    test_tags = [
        {"bullet_id": "sch-00016", "tag": "helpful", "is_correct": True, "query": "test1"},
        {"bullet_id": "sch-00016", "tag": "helpful", "is_correct": True, "query": "test2"},
        {"bullet_id": "ex-00001", "tag": "harmful", "is_correct": False, "query": "test3", "insight": "Missing edge case"},
    ]

    with open(reflector.tags_log_path, "w") as f:
        for tag in test_tags:
            f.write(json.dumps(tag) + "\n")

    print("Testing Curator...")
    curator = Curator()

    # Test tag reading
    tags = curator.read_tags()
    print(f"  Tags read: {len(tags)}")

    # Test aggregation
    aggregated = aggregate_tags(tags)
    print(f"  Aggregated: {aggregated}")

    # Test curation
    result = await curator.curate()

    print(f"\nCurator Result:")
    print(f"  Tags processed: {result.tags_processed}")
    print(f"  Counter updates: {result.counter_updates}")
    print(f"  Operations: {result.operations}")
    print(f"  Applied: {result.operations_applied}, Failed: {result.operations_failed}")
    print(f"  Latency: {result.latency_seconds:.1f}s")


if __name__ == "__main__":
    asyncio.run(test_curator())
