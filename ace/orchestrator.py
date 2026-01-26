"""
Orchestrator for ACE Pipeline

Coordinates the Solver → Reflector → Curator pipeline for batch training.
Supports both sync (train.py) and async (agent.py) modes.

Pipeline per batch:
1. SOLVER: Run batch of queries in parallel
2. REFLECTOR: Judge answers, tag bullets, log to tags.jsonl
3. CURATOR: Apply accumulated learning (once per batch)
4. VALIDATION: Run validation set (Reflector only, no Curator)
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

from .solver import SolverAgent, SolverResult
from .reflector import Reflector, ReflectorResult
from .curator import Curator, CuratorResult
from .playbook_utils import Tag

logger = logging.getLogger(__name__)


@dataclass
class BatchResult:
    """Result from processing one batch."""
    batch_num: int
    epoch: int

    # Solver results
    solver_results: list[SolverResult] = field(default_factory=list)

    # Reflector results
    reflector_results: list[ReflectorResult] = field(default_factory=list)

    # Curator result (if run)
    curator_result: CuratorResult | None = None

    # Aggregates
    num_correct: int = 0
    num_total: int = 0
    accuracy: float = 0.0
    total_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_seconds: float = 0.0
    total_tool_calls: int = 0
    empty_tool_calls: int = 0
    total_turns: int = 0
    total_bullets_cited: int = 0

    # Tool usage breakdown
    tool_usage: dict = field(default_factory=dict)

    # Bullet tag statistics (from Reflector)
    helpful_tags: int = 0
    harmful_tags: int = 0
    neutral_tags: int = 0

    def compute_aggregates(self):
        """Compute aggregate metrics from results."""
        self.num_total = len(self.reflector_results)
        self.num_correct = sum(1 for r in self.reflector_results if r.is_correct)
        self.accuracy = self.num_correct / self.num_total if self.num_total > 0 else 0

        self.total_tokens = sum(r.total_tokens for r in self.solver_results)
        self.total_output_tokens = sum(r.output_tokens for r in self.solver_results)
        self.total_latency_seconds = sum(r.latency_seconds for r in self.solver_results)
        self.total_tool_calls = sum(r.total_tool_calls for r in self.solver_results)
        self.empty_tool_calls = sum(r.empty_tool_calls for r in self.solver_results)
        self.total_turns = sum(len(r.turns) for r in self.solver_results)
        self.total_bullets_cited = sum(len(r.bullet_ids_used) for r in self.solver_results)

        # Count tool usage by type
        self.tool_usage = {}
        for sr in self.solver_results:
            for turn in sr.turns:
                for tc in turn.get("tool_calls", []):
                    tool_name = tc.get("tool", "unknown")
                    self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1

        # Count bullet tags from Reflector
        self.helpful_tags = 0
        self.harmful_tags = 0
        self.neutral_tags = 0
        for rr in self.reflector_results:
            for bt in rr.bullet_tags:
                if bt.tag == Tag.HELPFUL:
                    self.helpful_tags += 1
                elif bt.tag == Tag.HARMFUL:
                    self.harmful_tags += 1
                else:
                    self.neutral_tags += 1

        self.total_cost_usd = sum(r.total_cost_usd for r in self.solver_results)
        self.total_cost_usd += sum(r.total_cost_usd for r in self.reflector_results)
        if self.curator_result:
            self.total_cost_usd += self.curator_result.total_cost_usd


@dataclass
class EpochResult:
    """Result from one epoch of training."""
    epoch: int
    train_batches: list[BatchResult] = field(default_factory=list)
    validation_result: BatchResult | None = None

    # Aggregates
    train_accuracy: float = 0.0
    validation_accuracy: float = 0.0
    total_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_seconds: float = 0.0
    total_tool_calls: int = 0
    empty_tool_calls: int = 0
    total_turns: int = 0
    total_bullets_cited: int = 0
    tool_usage: dict = field(default_factory=dict)

    # Bullet tag statistics
    helpful_tags: int = 0
    harmful_tags: int = 0
    neutral_tags: int = 0

    def compute_aggregates(self):
        """Compute aggregate metrics."""
        train_correct = sum(b.num_correct for b in self.train_batches)
        train_total = sum(b.num_total for b in self.train_batches)
        self.train_accuracy = train_correct / train_total if train_total > 0 else 0

        if self.validation_result:
            self.validation_accuracy = self.validation_result.accuracy

        # Aggregate from all batches (train + validation)
        all_batches = list(self.train_batches)
        if self.validation_result:
            all_batches.append(self.validation_result)

        self.total_tokens = sum(b.total_tokens for b in all_batches)
        self.total_output_tokens = sum(b.total_output_tokens for b in all_batches)
        self.total_cost_usd = sum(b.total_cost_usd for b in all_batches)
        self.total_latency_seconds = sum(b.total_latency_seconds for b in all_batches)
        self.total_tool_calls = sum(b.total_tool_calls for b in all_batches)
        self.empty_tool_calls = sum(b.empty_tool_calls for b in all_batches)
        self.total_turns = sum(b.total_turns for b in all_batches)
        self.total_bullets_cited = sum(b.total_bullets_cited for b in all_batches)

        # Aggregate tool usage
        self.tool_usage = {}
        for batch in all_batches:
            for tool, count in batch.tool_usage.items():
                self.tool_usage[tool] = self.tool_usage.get(tool, 0) + count

        # Aggregate bullet tags
        self.helpful_tags = sum(b.helpful_tags for b in all_batches)
        self.harmful_tags = sum(b.harmful_tags for b in all_batches)
        self.neutral_tags = sum(b.neutral_tags for b in all_batches)


@dataclass
class TrainingRun:
    """Complete training run results."""
    run_id: str
    start_time: str
    end_time: str = ""

    epochs: list[EpochResult] = field(default_factory=list)

    # Configuration
    num_epochs: int = 3
    batch_size: int = 4
    train_size: int = 0
    validation_size: int = 0

    # Final metrics
    final_train_accuracy: float = 0.0
    final_validation_accuracy: float = 0.0
    total_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_seconds: float = 0.0
    total_tool_calls: int = 0
    empty_tool_calls: int = 0
    total_turns: int = 0
    total_bullets_cited: int = 0
    tool_usage: dict = field(default_factory=dict)

    # Bullet tag statistics
    helpful_tags: int = 0
    harmful_tags: int = 0
    neutral_tags: int = 0

    def finalize(self):
        """Compute final metrics."""
        self.end_time = datetime.now().isoformat()

        if self.epochs:
            last_epoch = self.epochs[-1]
            self.final_train_accuracy = last_epoch.train_accuracy
            self.final_validation_accuracy = last_epoch.validation_accuracy

        self.total_tokens = sum(e.total_tokens for e in self.epochs)
        self.total_output_tokens = sum(e.total_output_tokens for e in self.epochs)
        self.total_cost_usd = sum(e.total_cost_usd for e in self.epochs)
        self.total_latency_seconds = sum(e.total_latency_seconds for e in self.epochs)
        self.total_tool_calls = sum(e.total_tool_calls for e in self.epochs)
        self.empty_tool_calls = sum(e.empty_tool_calls for e in self.epochs)
        self.total_turns = sum(e.total_turns for e in self.epochs)
        self.total_bullets_cited = sum(e.total_bullets_cited for e in self.epochs)

        # Aggregate tool usage across all epochs
        self.tool_usage = {}
        for epoch in self.epochs:
            for tool, count in epoch.tool_usage.items():
                self.tool_usage[tool] = self.tool_usage.get(tool, 0) + count

        # Aggregate bullet tags across all epochs
        self.helpful_tags = sum(e.helpful_tags for e in self.epochs)
        self.harmful_tags = sum(e.harmful_tags for e in self.epochs)
        self.neutral_tags = sum(e.neutral_tags for e in self.epochs)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "num_epochs": self.num_epochs,
            "batch_size": self.batch_size,
            "train_size": self.train_size,
            "validation_size": self.validation_size,
            # Accuracy
            "final_train_accuracy": self.final_train_accuracy,
            "final_validation_accuracy": self.final_validation_accuracy,
            # Token metrics
            "total_tokens": self.total_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost_usd,
            # Performance metrics
            "total_latency_seconds": self.total_latency_seconds,
            "total_tool_calls": self.total_tool_calls,
            "empty_tool_calls": self.empty_tool_calls,
            "empty_tool_call_rate": self.empty_tool_calls / self.total_tool_calls if self.total_tool_calls > 0 else 0,
            "total_turns": self.total_turns,
            "total_bullets_cited": self.total_bullets_cited,
            # Tool usage breakdown
            "tool_usage": self.tool_usage,
            # Bullet tag statistics
            "helpful_tags": self.helpful_tags,
            "harmful_tags": self.harmful_tags,
            "neutral_tags": self.neutral_tags,
            # Per-epoch details
            "epochs": [
                {
                    "epoch": e.epoch,
                    "train_accuracy": e.train_accuracy,
                    "validation_accuracy": e.validation_accuracy,
                    "total_tokens": e.total_tokens,
                    "total_output_tokens": e.total_output_tokens,
                    "total_cost_usd": e.total_cost_usd,
                    "total_latency_seconds": e.total_latency_seconds,
                    "total_tool_calls": e.total_tool_calls,
                    "empty_tool_calls": e.empty_tool_calls,
                    "total_turns": e.total_turns,
                    "total_bullets_cited": e.total_bullets_cited,
                    "tool_usage": e.tool_usage,
                    "helpful_tags": e.helpful_tags,
                    "harmful_tags": e.harmful_tags,
                    "neutral_tags": e.neutral_tags,
                }
                for e in self.epochs
            ],
        }


class BatchOrchestrator:
    """Orchestrates the ACE pipeline for batch training."""

    def __init__(
        self,
        solver: SolverAgent | None = None,
        reflector: Reflector | None = None,
        curator: Curator | None = None,
        run_curator: bool = True,
        stream_output: bool = True,
    ):
        """Initialize the orchestrator.

        Args:
            solver: SolverAgent instance (created if not provided)
            reflector: Reflector instance (created if not provided)
            curator: Curator instance (created if not provided)
            run_curator: Whether to run the Curator (set False for baseline)
            stream_output: Whether to print streaming output
        """
        self.solver = solver or SolverAgent(stream_output=stream_output)
        self.reflector = reflector or Reflector()
        self.curator = curator or Curator()
        self.run_curator = run_curator
        self.stream_output = stream_output

        self.ace_root = Path(__file__).parent

    async def run_batch(
        self,
        queries: list[dict],
        batch_num: int = 1,
        epoch: int = 1,
        run_curator: bool | None = None,
    ) -> BatchResult:
        """Run a single batch through the pipeline.

        Args:
            queries: List of {query, expected_answer} dicts
            batch_num: Batch number for logging
            epoch: Epoch number for logging
            run_curator: Override for whether to run Curator

        Returns:
            BatchResult with all metrics
        """
        should_curate = run_curator if run_curator is not None else self.run_curator

        result = BatchResult(batch_num=batch_num, epoch=epoch)

        if self.stream_output:
            print(f"\n[Batch {batch_num}] Running {len(queries)} queries...")

        # Step 1: SOLVER - Run queries in parallel
        solver_results = await self.solver.solve_batch(queries)
        result.solver_results = solver_results

        if self.stream_output:
            correct_count = 0  # We don't know yet, need reflector

        # Step 2: REFLECTOR - Judge and tag in parallel
        reflector_results = await self.reflector.reflect_batch(solver_results)
        result.reflector_results = reflector_results

        if self.stream_output:
            correct = sum(1 for r in reflector_results if r.is_correct)
            total = len(reflector_results)
            tags_count = sum(len(r.bullet_tags) for r in reflector_results)
            print(f"[Reflector] {correct}/{total} correct, {tags_count} bullet tags")

            # Show individual query results with bullet tagging
            for sr, rr in zip(solver_results, reflector_results):
                status = "✓" if rr.is_correct else "✗"
                query_preview = sr.query[:50] + "..." if len(sr.query) > 50 else sr.query
                print(f"  {status} {query_preview}")
                if sr.bullet_ids_used:
                    tag_summary = ", ".join(
                        f"{t.bullet_id}={t.tag.value}" for t in rr.bullet_tags
                    )
                    print(f"    tags: {tag_summary}")
                if not rr.is_correct and rr.insight:
                    insight_preview = rr.insight[:60] + "..." if len(rr.insight) > 60 else rr.insight
                    print(f"    insight: {insight_preview}")

        # Step 3: CURATOR - Apply learning (if enabled)
        if should_curate:
            curator_result = await self.curator.curate()
            result.curator_result = curator_result

            if self.stream_output and curator_result.operations:
                print(f"[Curator] Applied {curator_result.operations_applied} operations")

        result.compute_aggregates()

        if self.stream_output:
            empty_pct = (result.empty_tool_calls / result.total_tool_calls * 100) if result.total_tool_calls > 0 else 0
            print(f"[Batch {batch_num}] Accuracy: {result.num_correct}/{result.num_total} ({result.accuracy:.0%}) | Tools: {result.total_tool_calls} ({result.empty_tool_calls} empty, {empty_pct:.0f}%)")

        return result

    async def run_validation(
        self,
        queries: list[dict],
        epoch: int = 1,
    ) -> BatchResult:
        """Run validation set (Reflector only, no Curator).

        Args:
            queries: Validation queries
            epoch: Current epoch

        Returns:
            BatchResult with validation metrics
        """
        if self.stream_output:
            print(f"\n[Validation] Running {len(queries)} queries...")

        result = BatchResult(batch_num=0, epoch=epoch)

        # Run solver
        solver_results = await self.solver.solve_batch(queries)
        result.solver_results = solver_results

        # Run reflector (tags accumulated but Curator not run)
        reflector_results = await self.reflector.reflect_batch(solver_results)
        result.reflector_results = reflector_results

        if self.stream_output:
            correct = sum(1 for r in reflector_results if r.is_correct)
            total = len(reflector_results)
            print(f"[Validation Reflector] {correct}/{total} correct")
            for sr, rr in zip(solver_results, reflector_results):
                status = "✓" if rr.is_correct else "✗"
                query_preview = sr.query[:50] + "..." if len(sr.query) > 50 else sr.query
                print(f"  {status} {query_preview}")

        result.compute_aggregates()

        if self.stream_output:
            print(f"[Validation] Accuracy: {result.num_correct}/{result.num_total} ({result.accuracy:.0%})")

        return result

    async def run_epoch(
        self,
        train_queries: list[dict],
        validation_queries: list[dict],
        epoch: int = 1,
        batch_size: int = 4,
    ) -> EpochResult:
        """Run one epoch of training.

        Args:
            train_queries: Training queries
            validation_queries: Validation queries
            epoch: Epoch number
            batch_size: Queries per batch

        Returns:
            EpochResult with training and validation metrics
        """
        result = EpochResult(epoch=epoch)

        if self.stream_output:
            print(f"\n{'='*60}")
            print(f"EPOCH {epoch}")
            print(f"{'='*60}")

        # Split train queries into batches
        batches = [
            train_queries[i:i + batch_size]
            for i in range(0, len(train_queries), batch_size)
        ]

        # Run each training batch
        for batch_num, batch_queries in enumerate(batches, 1):
            batch_result = await self.run_batch(
                queries=batch_queries,
                batch_num=batch_num,
                epoch=epoch,
            )
            result.train_batches.append(batch_result)

        # Run validation after epoch
        if validation_queries:
            result.validation_result = await self.run_validation(
                queries=validation_queries,
                epoch=epoch,
            )

        result.compute_aggregates()

        if self.stream_output:
            print(f"\n[Epoch {epoch} Summary]")
            print(f"  Train accuracy: {result.train_accuracy:.0%}")
            if result.validation_result:
                print(f"  Validation accuracy: {result.validation_accuracy:.0%}")
            total_tags = result.helpful_tags + result.harmful_tags + result.neutral_tags
            if total_tags > 0:
                print(f"  Bullet tags: {result.helpful_tags} helpful, {result.harmful_tags} harmful, {result.neutral_tags} neutral")

        return result

    async def train(
        self,
        train_queries: list[dict],
        validation_queries: list[dict],
        num_epochs: int = 3,
        batch_size: int = 4,
        on_epoch_complete: Callable[[EpochResult], None] | None = None,
    ) -> TrainingRun:
        """Run full training loop.

        Args:
            train_queries: Training queries
            validation_queries: Validation queries
            num_epochs: Number of epochs to run
            batch_size: Queries per batch
            on_epoch_complete: Callback after each epoch

        Returns:
            TrainingRun with all results
        """
        import uuid

        run = TrainingRun(
            run_id=f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            start_time=datetime.now().isoformat(),
            num_epochs=num_epochs,
            batch_size=batch_size,
            train_size=len(train_queries),
            validation_size=len(validation_queries),
        )

        if self.stream_output:
            print(f"\n{'='*60}")
            print("ACE TRAINING")
            print(f"{'='*60}")
            print(f"Run ID: {run.run_id}")
            print(f"Epochs: {num_epochs}")
            print(f"Batch size: {batch_size}")
            print(f"Train queries: {len(train_queries)}")
            print(f"Validation queries: {len(validation_queries)}")
            print(f"Curator: {'enabled' if self.run_curator else 'disabled'}")

        for epoch in range(1, num_epochs + 1):
            epoch_result = await self.run_epoch(
                train_queries=train_queries,
                validation_queries=validation_queries,
                epoch=epoch,
                batch_size=batch_size,
            )
            run.epochs.append(epoch_result)

            if on_epoch_complete:
                on_epoch_complete(epoch_result)

        run.finalize()

        if self.stream_output:
            print(f"\n{'='*60}")
            print("TRAINING COMPLETE")
            print(f"{'='*60}")
            print(f"Final train accuracy: {run.final_train_accuracy:.0%}")
            print(f"Final validation accuracy: {run.final_validation_accuracy:.0%}")
            print()
            print("Performance Metrics:")
            print(f"  Latency: {run.total_latency_seconds:.1f}s total")
            print(f"  Tokens: {run.total_tokens:,} ({run.total_output_tokens:,} output)")
            print(f"  Cost: ${run.total_cost_usd:.4f}")
            print()
            print("Execution Metrics:")
            print(f"  Turns: {run.total_turns}")
            print(f"  Tool calls: {run.total_tool_calls} ({run.empty_tool_calls} empty, {run.empty_tool_calls/run.total_tool_calls*100:.0f}% waste)" if run.total_tool_calls > 0 else "  Tool calls: 0")
            print(f"  Bullets cited: {run.total_bullets_cited}")
            if run.tool_usage:
                print(f"  Tool usage: {run.tool_usage}")
            print()
            print("Bullet Tag Statistics:")
            total_tags = run.helpful_tags + run.harmful_tags + run.neutral_tags
            if total_tags > 0:
                print(f"  Helpful: {run.helpful_tags} ({run.helpful_tags/total_tags*100:.0f}%)")
                print(f"  Harmful: {run.harmful_tags} ({run.harmful_tags/total_tags*100:.0f}%)")
                print(f"  Neutral: {run.neutral_tags} ({run.neutral_tags/total_tags*100:.0f}%)")
            else:
                print("  No bullet tags recorded")

        # Save run
        self._save_run(run)

        return run

    def _save_run(self, run: TrainingRun) -> Path:
        """Save training run to log file."""
        log_dir = self.ace_root / "logs" / "training"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_path = log_dir / f"{run.run_id}.json"
        with open(log_path, "w") as f:
            json.dump(run.to_dict(), f, indent=2)

        if self.stream_output:
            print(f"\nRun saved: {log_path}")

        return log_path


def load_queries(json_path: Path) -> list[dict]:
    """Load queries from a JSON file.

    Expected format: [{"query": "...", "answer": "..."}, ...]
    """
    with open(json_path) as f:
        data = json.load(f)

    return [
        {"query": q["query"], "expected_answer": q.get("answer", "")}
        for q in data
    ]


async def test_orchestrator():
    """Test the orchestrator with sample queries."""
    # Create mock queries
    train_queries = [
        {"query": "What was total revenue for 2023?", "expected_answer": "$100M"},
        {"query": "How many products exist?", "expected_answer": "4 products: A, B, C, D"},
    ]
    validation_queries = [
        {"query": "What was Q1 2024 revenue?", "expected_answer": "$25M"},
    ]

    orchestrator = BatchOrchestrator(
        run_curator=False,  # Skip curator for test
        stream_output=True,
    )

    print("Testing Orchestrator...")
    result = await orchestrator.run_batch(
        queries=train_queries,
        batch_num=1,
        epoch=1,
        run_curator=False,
    )

    print(f"\nBatch Result:")
    print(f"  Accuracy: {result.accuracy:.0%}")
    print(f"  Total tokens: {result.total_tokens}")


if __name__ == "__main__":
    asyncio.run(test_orchestrator())
