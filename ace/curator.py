"""
Curator Agent for ACE Pipeline (v2)

The Curator applies IMMEDIATE, SAFE changes based on Reflector analysis.
Structural changes are deferred to the Aggregator.

Responsibilities:
- Update counters (deterministic from tags)
- Apply high-confidence ADD operations (confidence >= 0.8)
- Defer structural changes (new categories, merges, deletions) to Aggregator

Key principle: Curator makes fast, safe changes. Aggregator makes strategic ones.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .playbook_utils import (
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


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class BulletAdded:
    """Record of a bullet added by Curator."""
    bullet_id: str
    section: str
    content: str
    confidence: float
    rationale: str
    source_run_id: str  # Which Reflector run suggested this


@dataclass
class DeferredProposal:
    """A proposal deferred for the Aggregator."""
    proposal_type: str  # "ADD", "UPDATE", "DELETE", "STRUCTURAL"
    priority: str  # "low", "medium", "high"
    confidence: float
    content: str | None
    bullet_id: str | None
    section: str | None
    rationale: str
    source_run_id: str
    reason_deferred: str  # Why it wasn't applied immediately

    def to_dict(self) -> dict:
        return {
            "type": self.proposal_type,
            "priority": self.priority,
            "confidence": self.confidence,
            "content": self.content,
            "bullet_id": self.bullet_id,
            "section": self.section,
            "rationale": self.rationale,
            "source_run_id": self.source_run_id,
            "reason_deferred": self.reason_deferred,
        }


@dataclass
class CuratorResult:
    """Result from Curator curation cycle."""
    # Input stats
    tags_processed: int
    reflector_logs_processed: int

    # Applied changes
    counter_updates: list[dict]  # {bullet_id, helpful_delta, harmful_delta}
    bullets_added: list[BulletAdded] = field(default_factory=list)

    # Deferred for Aggregator
    deferred_proposals: list[DeferredProposal] = field(default_factory=list)

    # Stats before/after
    stats_before: dict = field(default_factory=dict)
    stats_after: dict = field(default_factory=dict)

    # Metrics
    latency_seconds: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "tags_processed": self.tags_processed,
            "reflector_logs_processed": self.reflector_logs_processed,
            "counter_updates": self.counter_updates,
            "bullets_added": [
                {
                    "bullet_id": b.bullet_id,
                    "section": b.section,
                    "content": b.content,
                    "confidence": b.confidence,
                    "rationale": b.rationale,
                    "source_run_id": b.source_run_id,
                }
                for b in self.bullets_added
            ],
            "deferred_proposals": [p.to_dict() for p in self.deferred_proposals],
            "stats_before": self.stats_before,
            "stats_after": self.stats_after,
            "latency_seconds": self.latency_seconds,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
        }


# =============================================================================
# Helper Functions
# =============================================================================

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


# =============================================================================
# Curator Class
# =============================================================================

class Curator:
    """Applies immediate, safe changes based on Reflector analysis.

    The Curator is fast and conservative:
    - Counter updates: always applied (deterministic)
    - High-confidence ADDs: applied if confidence >= threshold
    - Everything else: deferred to Aggregator
    """

    # Thresholds
    ADD_CONFIDENCE_THRESHOLD = 0.8  # Minimum confidence to apply ADD immediately

    def __init__(
        self,
        knowledge_dir: Path | None = None,
        tags_log_path: Path | None = None,
        reflector_log_dir: Path | None = None,
        curator_log_dir: Path | None = None,
    ):
        """Initialize the Curator.

        Args:
            knowledge_dir: Path to knowledge files
            tags_log_path: Path to tags.jsonl (legacy, for counter updates)
            reflector_log_dir: Path to reflector logs (for suggested_deltas)
            curator_log_dir: Path to curator logs
        """
        self.ace_root = Path(__file__).parent
        self.knowledge_dir = knowledge_dir or self.ace_root / "knowledge"
        self.tags_log_path = tags_log_path or self.ace_root / "logs" / "tags.jsonl"
        self.reflector_log_dir = reflector_log_dir or self.ace_root / "logs" / "reflector"
        self.curator_log_dir = curator_log_dir or self.ace_root / "logs" / "curator"

        # Ensure directories exist
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        self.tags_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.curator_log_dir.mkdir(parents=True, exist_ok=True)

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

    def clear_reflector_logs(self) -> int:
        """Clear processed reflector logs."""
        count = 0
        if self.reflector_log_dir.exists():
            for log_file in self.reflector_log_dir.glob("*.json"):
                try:
                    log_file.unlink()
                    count += 1
                except IOError:
                    continue
        return count

    def _load_playbook(self) -> Playbook | None:
        """Load the unified playbook."""
        path = self.knowledge_dir / "playbook.md"
        if path.exists():
            return load_playbook(path)
        return None

    def _get_stats(self, playbook: Playbook) -> dict:
        """Get stats for the playbook."""
        return get_playbook_stats(playbook)

    async def curate(self) -> CuratorResult:
        """Run a curation cycle.

        Process:
        1. Read tags and reflector logs
        2. Apply counter updates (deterministic)
        3. Apply high-confidence ADDs from suggested_deltas
        4. Defer everything else to Aggregator
        5. Save playbooks and log results

        Returns:
            CuratorResult with applied changes and deferred proposals
        """
        start_time = time.time()

        # Read inputs
        tags = self.read_tags()
        reflector_logs = self.read_reflector_logs()

        if not tags and not reflector_logs:
            return CuratorResult(
                tags_processed=0,
                reflector_logs_processed=0,
                counter_updates=[],
            )

        # Load playbook and get stats
        playbook = self._load_playbook()
        if not playbook:
            return CuratorResult(
                tags_processed=0,
                reflector_logs_processed=0,
                counter_updates=[],
            )
        stats_before = self._get_stats(playbook)

        # Step 1: Counter updates (always apply - deterministic)
        aggregated = aggregate_tags(tags)
        counter_updates = compute_counter_updates(aggregated)

        bullet_tags = []
        for update in counter_updates:
            bid = update["bullet_id"]
            for _ in range(update["helpful_delta"]):
                bullet_tags.append(BulletTag(bullet_id=bid, tag=Tag.HELPFUL))
            for _ in range(update["harmful_delta"]):
                bullet_tags.append(BulletTag(bullet_id=bid, tag=Tag.HARMFUL))
        update_counters(playbook, bullet_tags)

        # Step 2: Process suggested deltas from Reflector logs
        bullets_added: list[BulletAdded] = []
        deferred_proposals: list[DeferredProposal] = []

        for log in reflector_logs:
            run_id = log.get("run_id", "unknown")
            suggested_deltas = log.get("suggested_deltas", [])

            for delta in suggested_deltas:
                delta_type = delta.get("type", "ADD")
                confidence = float(delta.get("confidence", 0.5))
                content = delta.get("content")
                bullet_id = delta.get("bullet_id")
                section = delta.get("section")
                rationale = delta.get("rationale", "")

                # Decide: apply immediately or defer?
                should_apply, reason_deferred = self._should_apply_immediately(
                    delta_type, confidence, content, section
                )

                if should_apply:
                    # Apply ADD immediately
                    added = self._apply_add(
                        playbook, content, section, confidence, rationale, run_id
                    )
                    if added:
                        bullets_added.append(added)
                else:
                    # Defer to Aggregator
                    priority = self._compute_priority(delta_type, confidence)
                    deferred_proposals.append(DeferredProposal(
                        proposal_type=delta_type,
                        priority=priority,
                        confidence=confidence,
                        content=content,
                        bullet_id=bullet_id,
                        section=section,
                        rationale=rationale,
                        source_run_id=run_id,
                        reason_deferred=reason_deferred,
                    ))

        # Save playbook
        save_playbook(playbook)

        # Get stats after
        playbook_after = self._load_playbook()
        stats_after = self._get_stats(playbook_after) if playbook_after else {}

        # Clear processed inputs
        self.clear_tags()
        self.clear_reflector_logs()

        result = CuratorResult(
            tags_processed=len(tags),
            reflector_logs_processed=len(reflector_logs),
            counter_updates=counter_updates,
            bullets_added=bullets_added,
            deferred_proposals=deferred_proposals,
            stats_before=stats_before,
            stats_after=stats_after,
            latency_seconds=time.time() - start_time,
        )

        # Save curator log
        self._save_curator_log(result)

        return result

    def _should_apply_immediately(
        self,
        delta_type: str,
        confidence: float,
        content: str | None,
        section: str | None,
    ) -> tuple[bool, str]:
        """Decide if a delta should be applied immediately.

        Returns:
            (should_apply, reason_if_deferred)
        """
        # Only ADDs can be applied immediately
        if delta_type != "ADD":
            return False, f"{delta_type} operations require Aggregator review"

        # Must have content
        if not content:
            return False, "ADD has no content"

        # Must have sufficient confidence
        if confidence < self.ADD_CONFIDENCE_THRESHOLD:
            return False, f"Confidence {confidence:.2f} below threshold {self.ADD_CONFIDENCE_THRESHOLD}"

        # STRUCTURAL type is always deferred
        if delta_type == "STRUCTURAL":
            return False, "Structural changes require Aggregator review"

        # Section-based rules
        if section:
            section_lower = section.lower()
            # New categories/sections are structural
            if "new" in section_lower or "category" in section_lower:
                return False, "New category creation requires Aggregator review"

        return True, ""

    def _compute_priority(self, delta_type: str, confidence: float) -> str:
        """Compute priority for deferred proposals."""
        if delta_type in ["DELETE", "STRUCTURAL"]:
            return "high"  # Need careful review
        elif confidence >= 0.7:
            return "medium"
        else:
            return "low"

    def _apply_add(
        self,
        playbook: Playbook,
        content: str,
        section: str | None,
        confidence: float,
        rationale: str,
        source_run_id: str,
    ) -> BulletAdded | None:
        """Apply an ADD operation to the playbook.

        Returns:
            BulletAdded if successful, None otherwise
        """
        # Map section to a valid playbook section
        section_name = self._map_to_section(section)

        # Create the operation
        op = DeltaOp(
            op_type=OpType.ADD,
            section=section_name,
            content=content,
            reason=rationale,
        )

        # Apply it
        success, _ = apply_operations(playbook, [op])
        if success > 0:
            # Find the bullet that was just added (last in the section)
            bullet_id = self._find_last_bullet_id(playbook, section_name)
            return BulletAdded(
                bullet_id=bullet_id or "unknown",
                section=section_name,
                content=content,
                confidence=confidence,
                rationale=rationale,
                source_run_id=source_run_id,
            )

        return None

    def _map_to_section(self, section: str | None) -> str:
        """Map a suggested section name to a valid playbook section."""
        if not section:
            return "STRATEGIES & INSIGHTS"

        section_lower = section.lower()

        # Map common patterns to our sections
        if "schema" in section_lower or "column" in section_lower:
            return "SCHEMA"
        elif "strat" in section_lower or "insight" in section_lower:
            return "STRATEGIES & INSIGHTS"
        elif "formula" in section_lower or "calc" in section_lower:
            return "FORMULAS & CALCULATIONS"
        elif "code" in section_lower or "template" in section_lower:
            return "CODE TEMPLATES"
        elif "edge" in section_lower or "pitfall" in section_lower:
            return "EDGE CASES & PITFALLS"
        elif "mistake" in section_lower or "error" in section_lower:
            return "COMMON MISTAKES"
        elif "interp" in section_lower or "query" in section_lower:
            return "QUERY INTERPRETATION"
        else:
            return "STRATEGIES & INSIGHTS"  # Default

    def _find_last_bullet_id(self, pb: Playbook, section_name: str) -> str | None:
        """Find the ID of the last bullet in a section."""
        from .playbook_utils import Bullet

        items = pb.sections.get(section_name, [])
        # Find last bullet in the section
        for item in reversed(items):
            if isinstance(item, Bullet):
                return item.id
        return None

    def _save_curator_log(self, result: CuratorResult) -> Path:
        """Save curator result to log file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = self.curator_log_dir / f"curator_{timestamp}.json"

        with open(log_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        return log_path


# =============================================================================
# Test
# =============================================================================

async def test_curator():
    """Test the enhanced Curator."""
    import asyncio

    print("Testing Enhanced Curator...")

    # Create some mock reflector logs
    reflector_log_dir = Path(__file__).parent / "logs" / "reflector"
    reflector_log_dir.mkdir(parents=True, exist_ok=True)

    mock_log = {
        "run_id": "test_curator_001",
        "query": "Test query",
        "is_correct": False,
        "suggested_deltas": [
            {
                "type": "ADD",
                "confidence": 0.9,
                "content": "Test bullet with high confidence",
                "section": "Key_Rules",
                "rationale": "This should be applied immediately",
            },
            {
                "type": "ADD",
                "confidence": 0.5,
                "content": "Test bullet with low confidence",
                "section": "Key_Rules",
                "rationale": "This should be deferred",
            },
            {
                "type": "DELETE",
                "confidence": 0.8,
                "bullet_id": "sch-00001",
                "rationale": "This should be deferred (DELETE)",
            },
        ],
    }

    with open(reflector_log_dir / "test_curator_001.json", "w") as f:
        json.dump(mock_log, f)

    # Run curator
    curator = Curator()
    result = await curator.curate()

    print(f"\nCurator Result:")
    print(f"  Tags processed: {result.tags_processed}")
    print(f"  Reflector logs processed: {result.reflector_logs_processed}")
    print(f"  Counter updates: {len(result.counter_updates)}")
    print(f"  Bullets added: {len(result.bullets_added)}")
    for added in result.bullets_added:
        print(f"    - {added.bullet_id}: {added.content[:50]}...")
    print(f"  Deferred proposals: {len(result.deferred_proposals)}")
    for deferred in result.deferred_proposals:
        print(f"    - {deferred.proposal_type} ({deferred.confidence:.1f}): {deferred.reason_deferred}")
    print(f"  Latency: {result.latency_seconds:.2f}s")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_curator())
