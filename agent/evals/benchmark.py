#!/usr/bin/env python3
"""
Benchmark V2 - Track learning progress with LLM-based accuracy scoring.

Usage:
    python benchmark.py run                     # 3 epochs, batch_size=2
    python benchmark.py run --epochs 5          # 5 epochs
    python benchmark.py run --batch-size 3      # 3 queries per batch
    python benchmark.py run --no-improve        # Baseline without improver
    python benchmark.py dashboard               # Regenerate dashboard
    python benchmark.py list                    # List all runs
    python benchmark.py compare <r1> <r2>       # Compare two runs
"""

import json
import sys
import asyncio
import subprocess
import webbrowser
import logging
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
import uuid
import random

PROJECT_ROOT = Path(__file__).parent.parent  # evals/ -> agent/
BENCHMARKS_DIR = Path(__file__).parent / "benchmarks"

sys.path.insert(0, str(PROJECT_ROOT))


def configure_logging(quiet: bool = False):
    """Configure logging level based on quiet mode."""
    level = logging.WARNING if quiet else logging.INFO
    logging.basicConfig(level=level, force=True)
    # Suppress SDK internal logs in quiet mode
    if quiet:
        logging.getLogger("claude_agent_sdk").setLevel(logging.WARNING)
        logging.getLogger("agent").setLevel(logging.WARNING)


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class QueryResult:
    """Result from a single query."""
    query_num: int              # Global query number (all-time)
    epoch: int                  # Which epoch
    batch: int                  # Which batch within epoch
    query: str
    expected_answer: str
    agent_answer: str
    tokens: int
    tool_calls: int
    latency_seconds: float
    judge_score: float          # 0-1 from Haiku judge
    judge_reason: str           # Brief explanation from judge
    rolling_avg_tokens: float
    rolling_avg_score: float    # Rolling judge score
    status: str


@dataclass
class ValidationCheckpoint:
    """Validation metrics after a batch of training queries."""
    epoch: int
    batch: int
    query_num_after: int        # Global query number this checkpoint follows
    avg_tokens: float
    avg_tool_calls: float
    avg_judge_score: float


@dataclass
class EpochCheckpoint:
    """Aggregate metrics for an epoch."""
    epoch: int
    train_avg_tokens: float
    train_avg_tool_calls: float
    train_avg_judge_score: float
    validation_avg_tokens: float
    validation_avg_tool_calls: float
    validation_avg_judge_score: float


@dataclass
class BenchmarkRun:
    """A complete benchmark run with all metrics."""
    run_id: str
    timestamp: str
    agent_version: str
    learner_model: str
    improver_model: str

    # Configuration
    num_epochs: int = 0
    batch_size: int = 2
    train_size: int = 9
    test_size: int = 8
    improve_enabled: bool = True

    # Per-query results (the core data)
    query_results: list[dict] = field(default_factory=list)

    # Validation checkpoints (after each batch)
    validation_checkpoints: list[dict] = field(default_factory=list)

    # Epoch checkpoints
    epoch_checkpoints: list[dict] = field(default_factory=list)

    # Final summary
    total_queries: int = 0
    successful_queries: int = 0
    avg_tokens_per_query: float = 0.0
    avg_tool_calls_per_query: float = 0.0
    avg_latency_seconds: float = 0.0
    avg_train_judge_score: float = 0.0
    avg_validation_judge_score: float = 0.0

    # Knowledge state snapshot
    knowledge_snapshot: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BenchmarkRun":
        return cls(**data)


# ============================================================
# LLM JUDGE
# ============================================================

async def judge_answer(query: str, expected: str, actual: str) -> tuple[float, str]:
    """Use Haiku to judge if agent answer matches expected answer.

    Returns: (score, reason)
        score: 0.0 (wrong) or 1.0 (correct)
        reason: Brief explanation
    """
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

    prompt = f"""Compare the expected answer to the agent's answer for this query.

Query: {query}

Expected Answer: {expected}

Agent Answer: {actual}

Judge as CORRECT (1.0) if:
- The answer conveys the same information as expected
- Numeric values match (allow formatting differences: $1.2M = $1,200,000)
- For "not available" answers, the reason is substantively correct

Judge as WRONG (0.0) if:
- The answer is factually incorrect
- Key information is missing or wrong
- The reasoning leads to a wrong conclusion

Return ONLY a JSON object:
{{"score": <0.0 or 1.0>, "reason": "<brief explanation>"}}"""

    try:
        options = ClaudeAgentOptions(
            model="claude-haiku-4-5",
            max_turns=1,
            system_prompt="You are a judge evaluating answer accuracy. Return only valid JSON.",
            cwd=str(PROJECT_ROOT),
            allowed_tools=[],
            permission_mode="acceptEdits",
            max_budget_usd=0.01,
        )

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            response_text = ""
            async for message in client.receive_response():
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            response_text += block.text

        # Parse JSON from response
        # Handle case where response might have extra text
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)
            score = float(result.get("score", 0.0))
            reason = result.get("reason", "No reason provided")
            return (score, reason)

        return (0.0, "Failed to parse judge response")

    except Exception as e:
        return (0.0, f"Judge error: {str(e)[:50]}")


# ============================================================
# BENCHMARK RUNNER
# ============================================================

class BenchmarkSuite:
    """Run benchmarks and generate analytics."""

    def __init__(self):
        BENCHMARKS_DIR.mkdir(exist_ok=True)
        (BENCHMARKS_DIR / "runs").mkdir(exist_ok=True)

    def _get_agent_version(self) -> str:
        """Get current agent version from git."""
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True, text=True, cwd=PROJECT_ROOT
            ).stdout.strip()
            dirty = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True, text=True, cwd=PROJECT_ROOT
            ).stdout.strip()
            return f"{commit}{'-dirty' if dirty else ''}"
        except Exception:
            return "unknown"

    def _get_models(self) -> tuple[str, str]:
        """Get the models being used by the agent."""
        from agent import LearnerAgent
        return LearnerAgent.DEFAULT_LEARNER_MODEL, LearnerAgent.DEFAULT_IMPROVER_MODEL

    def _snapshot_knowledge(self) -> dict:
        """Capture current state of knowledge files."""
        knowledge_dir = PROJECT_ROOT / "knowledge"
        snapshot = {}
        for f in knowledge_dir.glob("*"):
            if f.is_file() and f.suffix in [".md", ".py", ".txt"]:
                content = f.read_text()
                snapshot[f.name] = {
                    "size": f.stat().st_size,
                    "lines": len(content.splitlines()),
                    "hash": hash(content) % (10**8)
                }
        return snapshot

    def _load_queries(self, filename: str) -> list[dict]:
        """Load queries from eval file."""
        eval_path = Path(__file__).parent / filename
        with open(eval_path) as f:
            return json.load(f)

    def _print_query_progress(
        self,
        query_num: int,
        total: int,
        metrics: dict,
        rolling_tokens: float,
        rolling_score: float
    ):
        """Print training-style progress line."""
        status = "✓" if metrics["status"] == "success" else "✗"
        tokens = metrics.get("tokens", 0)
        tools = metrics.get("tool_calls", 0)
        score = metrics.get("judge_score", 0.0)

        print(f"  [{query_num:3d}/{total}] {status} tokens: {tokens:5d}  tools: {tools:2d}  score: {score:.1f}  │  rolling: {rolling_tokens:6.0f} tok, {rolling_score:.2f} score")

    def _print_validation(self, epoch: int, batch: int, avg_tokens: float, avg_score: float):
        """Print validation checkpoint line."""
        print(f"  ── VALIDATION (batch {batch}) ── test: {avg_tokens:.0f} tok, {avg_score:.2f} score ──")

    def _print_epoch_summary(self, epoch: int, train_stats: dict, val_stats: dict):
        """Print epoch summary."""
        print(f"\n{'─'*70}")
        print(f"  EPOCH {epoch} COMPLETE")
        print(f"  Train:      {train_stats['avg_tokens']:.0f} tokens, {train_stats['avg_score']:.2f} score")
        print(f"  Validation: {val_stats['avg_tokens']:.0f} tokens, {val_stats['avg_score']:.2f} score")
        print(f"{'─'*70}\n")

    async def run_benchmark(
        self,
        num_epochs: int = 3,
        batch_size: int = 2,
        window_size: int = 5,
        improve_enabled: bool = True,
        quiet: bool = False,
    ) -> BenchmarkRun:
        """
        Run a complete benchmark with learning curves.

        For each epoch:
            Shuffle train_set
            For each batch:
                Run queries with improver ON (if enabled)
                Judge answers
                Run validation on test_set (improver OFF)
                Record checkpoint

        Args:
            num_epochs: Number of full passes through train set
            batch_size: Queries per batch before validation
            window_size: Rolling average window
            improve_enabled: Whether to enable the improver
            quiet: Suppress agent output (tool calls, streaming)
        """
        from agent import LearnerAgent, wait_for_background_tasks

        run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        learner_model, improver_model = self._get_models()

        # Load queries
        train_queries = self._load_queries("train.json")
        test_queries = self._load_queries("test.json")
        train_size = len(train_queries)
        test_size = len(test_queries)
        total_queries = num_epochs * train_size

        print(f"\n{'='*70}")
        print(f"  BENCHMARK: {run_id}")
        print(f"{'='*70}")
        print(f"  Epochs: {num_epochs} ({train_size} queries/epoch = {total_queries} total)")
        print(f"  Batch size: {batch_size}")
        print(f"  Models: learner={learner_model.split('-')[1]}, improver={improver_model.split('-')[1]}")
        print(f"  Improver: {'enabled' if improve_enabled else 'disabled'}")
        print(f"{'='*70}\n")

        # Initialize run
        run = BenchmarkRun(
            run_id=run_id,
            timestamp=datetime.now().isoformat(),
            agent_version=self._get_agent_version(),
            learner_model=learner_model,
            improver_model=improver_model,
            num_epochs=num_epochs,
            batch_size=batch_size,
            train_size=train_size,
            test_size=test_size,
            improve_enabled=improve_enabled,
            knowledge_snapshot=self._snapshot_knowledge(),
        )

        # Create agents
        train_agent = LearnerAgent(enable_background_improve=improve_enabled, stream_output=not quiet)
        test_agent = LearnerAgent(enable_background_improve=False, stream_output=not quiet)

        # Tracking
        rolling_tokens = []
        rolling_scores = []
        global_query_num = 0

        for epoch in range(1, num_epochs + 1):
            print(f"EPOCH {epoch}")

            # Shuffle training queries each epoch
            epoch_queries = train_queries.copy()
            random.shuffle(epoch_queries)

            # Track epoch stats
            epoch_train_results = []
            batch_num = 0

            for batch_start in range(0, len(epoch_queries), batch_size):
                batch_num += 1
                batch_queries = epoch_queries[batch_start:batch_start + batch_size]

                # Process each query in the batch
                for query_data in batch_queries:
                    global_query_num += 1
                    query = query_data["query"]
                    expected = query_data["answer"]
                    query_run_id = uuid.uuid4().hex[:12]

                    # Run query
                    try:
                        result = await train_agent._query_async(query, run_id=query_run_id)
                        trace = result["trace"]
                        agent_answer = result["answer"]

                        # Judge the answer
                        judge_score, judge_reason = await judge_answer(query, expected, agent_answer)

                        metrics = {
                            "query_num": global_query_num,
                            "epoch": epoch,
                            "batch": batch_num,
                            "query": query,
                            "expected_answer": expected,
                            "agent_answer": agent_answer,
                            "tokens": trace.total_tokens,
                            "tool_calls": trace.total_tool_calls,
                            "latency_seconds": getattr(trace, 'latency_seconds', 0),
                            "judge_score": judge_score,
                            "judge_reason": judge_reason,
                            "status": "success",
                        }
                    except Exception as e:
                        metrics = {
                            "query_num": global_query_num,
                            "epoch": epoch,
                            "batch": batch_num,
                            "query": query,
                            "expected_answer": expected,
                            "agent_answer": str(e),
                            "tokens": 0,
                            "tool_calls": 0,
                            "latency_seconds": 0,
                            "judge_score": 0.0,
                            "judge_reason": f"Error: {str(e)[:30]}",
                            "status": "error",
                        }

                    # Update rolling averages
                    if metrics["status"] == "success":
                        rolling_tokens.append(metrics["tokens"])
                        rolling_scores.append(metrics["judge_score"])

                    window_tokens = rolling_tokens[-window_size:] if rolling_tokens else [0]
                    window_scores = rolling_scores[-window_size:] if rolling_scores else [0]

                    metrics["rolling_avg_tokens"] = sum(window_tokens) / len(window_tokens)
                    metrics["rolling_avg_score"] = sum(window_scores) / len(window_scores)

                    run.query_results.append(metrics)
                    epoch_train_results.append(metrics)

                    # Print progress
                    self._print_query_progress(
                        global_query_num, total_queries, metrics,
                        metrics["rolling_avg_tokens"], metrics["rolling_avg_score"]
                    )

                    # Wait for improvement if enabled
                    if improve_enabled:
                        await wait_for_background_tasks(timeout=120.0)

                # After batch: run validation on test set (parallel)
                async def run_validation_query(test_data):
                    """Run a single validation query and judge it."""
                    try:
                        result = await test_agent._query_async(
                            test_data["query"],
                            run_id=uuid.uuid4().hex[:12]
                        )
                        trace = result["trace"]
                        agent_answer = result["answer"]

                        # Judge the answer
                        score, _ = await judge_answer(
                            test_data["query"],
                            test_data["answer"],
                            agent_answer
                        )

                        return {
                            "tokens": trace.total_tokens,
                            "tool_calls": trace.total_tool_calls,
                            "judge_score": score,
                            "status": "success",
                        }
                    except Exception:
                        return {
                            "tokens": 0,
                            "tool_calls": 0,
                            "judge_score": 0.0,
                            "status": "error",
                        }

                # Run all validation queries in parallel
                val_results = await asyncio.gather(
                    *[run_validation_query(tq) for tq in test_queries]
                )

                # Compute validation stats
                val_ok = [v for v in val_results if v["status"] == "success"]
                val_avg_tokens = sum(v["tokens"] for v in val_ok) / len(val_ok) if val_ok else 0
                val_avg_tools = sum(v["tool_calls"] for v in val_ok) / len(val_ok) if val_ok else 0
                val_avg_score = sum(v["judge_score"] for v in val_ok) / len(val_ok) if val_ok else 0

                # Record validation checkpoint
                checkpoint = {
                    "epoch": epoch,
                    "batch": batch_num,
                    "query_num_after": global_query_num,
                    "avg_tokens": val_avg_tokens,
                    "avg_tool_calls": val_avg_tools,
                    "avg_judge_score": val_avg_score,
                }
                run.validation_checkpoints.append(checkpoint)

                self._print_validation(epoch, batch_num, val_avg_tokens, val_avg_score)

            # End of epoch: compute and record epoch checkpoint
            train_ok = [q for q in epoch_train_results if q["status"] == "success"]
            train_stats = {
                "avg_tokens": sum(q["tokens"] for q in train_ok) / len(train_ok) if train_ok else 0,
                "avg_tool_calls": sum(q["tool_calls"] for q in train_ok) / len(train_ok) if train_ok else 0,
                "avg_score": sum(q["judge_score"] for q in train_ok) / len(train_ok) if train_ok else 0,
            }

            # Get last validation checkpoint for this epoch
            epoch_val_checkpoints = [v for v in run.validation_checkpoints if v["epoch"] == epoch]
            if epoch_val_checkpoints:
                last_val = epoch_val_checkpoints[-1]
                val_stats = {
                    "avg_tokens": last_val["avg_tokens"],
                    "avg_tool_calls": last_val["avg_tool_calls"],
                    "avg_score": last_val["avg_judge_score"],
                }
            else:
                val_stats = {"avg_tokens": 0, "avg_tool_calls": 0, "avg_score": 0}

            epoch_checkpoint = {
                "epoch": epoch,
                "train_avg_tokens": train_stats["avg_tokens"],
                "train_avg_tool_calls": train_stats["avg_tool_calls"],
                "train_avg_judge_score": train_stats["avg_score"],
                "validation_avg_tokens": val_stats["avg_tokens"],
                "validation_avg_tool_calls": val_stats["avg_tool_calls"],
                "validation_avg_judge_score": val_stats["avg_score"],
            }
            run.epoch_checkpoints.append(epoch_checkpoint)

            self._print_epoch_summary(epoch, train_stats, val_stats)

        # Final stats
        successful = [q for q in run.query_results if q["status"] == "success"]
        run.total_queries = len(run.query_results)
        run.successful_queries = len(successful)
        run.avg_tokens_per_query = sum(q["tokens"] for q in successful) / len(successful) if successful else 0
        run.avg_tool_calls_per_query = sum(q["tool_calls"] for q in successful) / len(successful) if successful else 0
        run.avg_latency_seconds = sum(q["latency_seconds"] for q in successful) / len(successful) if successful else 0
        run.avg_train_judge_score = sum(q["judge_score"] for q in successful) / len(successful) if successful else 0

        # Validation score from last checkpoint
        if run.validation_checkpoints:
            run.avg_validation_judge_score = run.validation_checkpoints[-1]["avg_judge_score"]

        # Update knowledge snapshot
        run.knowledge_snapshot = self._snapshot_knowledge()

        # Save run
        run_path = BENCHMARKS_DIR / "runs" / f"{run_id}.json"
        with open(run_path, "w") as f:
            json.dump(run.to_dict(), f, indent=2)

        # Print final summary
        print(f"\n{'='*70}")
        print(f"  BENCHMARK COMPLETE: {run_id}")
        print(f"{'='*70}")
        print(f"  Queries: {run.successful_queries}/{run.total_queries} successful")
        print(f"  Final avg: {run.avg_tokens_per_query:.0f} tokens, {run.avg_tool_calls_per_query:.1f} tools")
        print(f"  Train score: {run.avg_train_judge_score:.2f}")
        print(f"  Validation score: {run.avg_validation_judge_score:.2f}")

        if run.epoch_checkpoints:
            first, last = run.epoch_checkpoints[0], run.epoch_checkpoints[-1]
            train_change = last["train_avg_judge_score"] - first["train_avg_judge_score"]
            val_change = last["validation_avg_judge_score"] - first["validation_avg_judge_score"]
            print(f"  Learning (score): epoch 1 → {num_epochs}: train {first['train_avg_judge_score']:.2f} → {last['train_avg_judge_score']:.2f} ({train_change:+.2f})")
            print(f"                    validation {first['validation_avg_judge_score']:.2f} → {last['validation_avg_judge_score']:.2f} ({val_change:+.2f})")

        print(f"\n  Saved: {run_path}")

        # Generate dashboard
        dashboard_path = self.generate_dashboard()
        print(f"  Dashboard: {dashboard_path}")

        return run

    def _build_runs_table(self, runs: list[dict]) -> str:
        """Build HTML table rows for runs."""
        rows = []
        for r in reversed(runs):
            run_id = r['run_id'].replace('run_', '')[:16]
            timestamp = r['timestamp'][5:16].replace('T', ' ')
            model = r.get('learner_model', r.get('model', 'unknown'))
            model = model.replace('claude-', '').replace('-20241022', '').replace('-20250514', '')[:12]
            version = r['agent_version'][:8]
            epochs = r.get('num_epochs', len(r.get('epoch_checkpoints', [])))
            queries = r.get('total_queries', r.get('num_queries', 0))
            avg_tokens = r.get('avg_tokens_per_query', 0)
            train_score = r.get('avg_train_judge_score', 0)
            val_score = r.get('avg_validation_judge_score', 0)

            rows.append(f"""
                <tr>
                    <td>{run_id}</td>
                    <td>{timestamp}</td>
                    <td><span class="tag">{model}</span></td>
                    <td><span class="tag">{version}</span></td>
                    <td>{epochs}</td>
                    <td>{queries}</td>
                    <td>{avg_tokens:,.0f}</td>
                    <td>{train_score:.2f}</td>
                    <td>{val_score:.2f}</td>
                </tr>""")
        return ''.join(rows)

    def list_runs(self) -> list[dict]:
        """List all benchmark runs."""
        runs = []
        runs_dir = BENCHMARKS_DIR / "runs"
        if runs_dir.exists():
            for f in sorted(runs_dir.glob("*.json"), reverse=True):
                with open(f) as fp:
                    data = json.load(fp)
                    runs.append({
                        "run_id": data["run_id"],
                        "timestamp": data["timestamp"],
                        "learner_model": data.get("learner_model", data.get("model", "unknown")),
                        "agent_version": data["agent_version"],
                        "epochs": data.get("num_epochs", len(data.get("epoch_checkpoints", []))),
                        "queries": data.get("total_queries", data.get("num_queries", 0)),
                        "avg_tokens": round(data.get("avg_tokens_per_query", 0), 1),
                        "train_score": round(data.get("avg_train_judge_score", 0), 2),
                        "val_score": round(data.get("avg_validation_judge_score", 0), 2),
                    })
        return runs

    def generate_dashboard(self, output_path: Optional[str] = None) -> str:
        """Generate HTML dashboard with learning curves and accuracy charts."""
        runs_dir = BENCHMARKS_DIR / "runs"
        runs = []

        if runs_dir.exists():
            for f in sorted(runs_dir.glob("*.json")):
                with open(f) as fp:
                    runs.append(json.load(fp))

        if not runs:
            return "No benchmark runs found."

        # Sort by timestamp
        runs.sort(key=lambda x: x["timestamp"])

        # Prepare data for charts
        run_labels = [r["run_id"].replace("run_", "")[:12] for r in runs]
        run_tokens = [r.get("avg_tokens_per_query", 0) for r in runs]
        run_train_scores = [r.get("avg_train_judge_score", 0) for r in runs]
        run_val_scores = [r.get("avg_validation_judge_score", 0) for r in runs]

        # Find latest run with query_results for learning curves
        latest_with_curves = None
        for r in reversed(runs):
            if r.get("query_results"):
                latest_with_curves = r
                break

        # Learning curve data (rolling averages per query)
        learning_curve_data = {"labels": [], "tokens": [], "scores": []}
        epoch_markers = []

        if latest_with_curves and latest_with_curves.get("query_results"):
            for q in latest_with_curves["query_results"]:
                learning_curve_data["labels"].append(q["query_num"])
                learning_curve_data["tokens"].append(q.get("rolling_avg_tokens", q.get("tokens", 0)))
                learning_curve_data["scores"].append(q.get("rolling_avg_score", q.get("judge_score", 0)))

            # Epoch boundaries
            train_size = latest_with_curves.get("train_size", 9)
            for i in range(train_size, len(latest_with_curves["query_results"]) + 1, train_size):
                epoch_markers.append(i)

        # Validation checkpoints for sparse line
        val_checkpoint_data = {"labels": [], "scores": [], "tokens": []}
        if latest_with_curves and latest_with_curves.get("validation_checkpoints"):
            for vc in latest_with_curves["validation_checkpoints"]:
                val_checkpoint_data["labels"].append(vc["query_num_after"])
                val_checkpoint_data["scores"].append(vc["avg_judge_score"])
                val_checkpoint_data["tokens"].append(vc["avg_tokens"])

        # Epoch progression data (train vs validation by epoch)
        epoch_data = {"labels": [], "train_score": [], "val_score": [], "train_tokens": [], "val_tokens": []}
        if latest_with_curves and latest_with_curves.get("epoch_checkpoints"):
            for ep in latest_with_curves["epoch_checkpoints"]:
                epoch_data["labels"].append(f"Epoch {ep['epoch']}")
                epoch_data["train_score"].append(ep.get("train_avg_judge_score", 0))
                epoch_data["val_score"].append(ep.get("validation_avg_judge_score", 0))
                epoch_data["train_tokens"].append(ep.get("train_avg_tokens", 0))
                epoch_data["val_tokens"].append(ep.get("validation_avg_tokens", 0))

        # Calculate metrics for cards
        latest = runs[-1]
        latest_val_score = latest.get("avg_validation_judge_score", 0)
        latest_train_score = latest.get("avg_train_judge_score", 0)
        latest_tokens = latest.get("avg_tokens_per_query", 0)
        train_val_gap = latest_train_score - latest_val_score

        if len(runs) >= 2:
            first = runs[0]
            token_change = ((latest_tokens - first.get("avg_tokens_per_query", 0))
                           / first.get("avg_tokens_per_query", 1) * 100) if first.get("avg_tokens_per_query") else 0
        else:
            token_change = 0

        total_epochs = sum(r.get("num_epochs", len(r.get("epoch_checkpoints", []))) for r in runs)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Benchmark Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117; color: #c9d1d9; line-height: 1.5; padding: 2rem;
        }}
        .dashboard {{ max-width: 1400px; margin: 0 auto; }}
        header {{ margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid #30363d; }}
        h1 {{ font-size: 1.5rem; font-weight: 600; color: #f0f6fc; }}
        .subtitle {{ color: #8b949e; font-size: 0.875rem; }}

        .metrics-grid {{
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem;
        }}
        .metric-card {{
            background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1.25rem;
        }}
        .metric-label {{ font-size: 0.75rem; font-weight: 500; text-transform: uppercase; color: #8b949e; margin-bottom: 0.5rem; }}
        .metric-value {{ font-size: 1.75rem; font-weight: 600; color: #f0f6fc; }}
        .metric-change {{ font-size: 0.8125rem; margin-top: 0.25rem; }}
        .metric-change.positive {{ color: #3fb950; }}
        .metric-change.negative {{ color: #f85149; }}
        .metric-change.neutral {{ color: #8b949e; }}

        .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 2rem; }}
        .chart-card {{
            background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 1.25rem;
        }}
        .chart-card.full {{ grid-column: 1 / -1; }}
        .chart-title {{ font-size: 0.875rem; font-weight: 600; margin-bottom: 1rem; color: #f0f6fc; }}
        .chart-container {{ position: relative; height: 280px; }}

        .runs-table {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; overflow: hidden; }}
        .table-header {{ padding: 1rem 1.25rem; border-bottom: 1px solid #30363d; font-weight: 600; font-size: 0.875rem; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
        th {{ padding: 0.75rem 1rem; text-align: left; font-weight: 500; color: #8b949e; font-size: 0.75rem; text-transform: uppercase; border-bottom: 1px solid #30363d; background: #0d1117; }}
        td {{ padding: 0.75rem 1rem; border-bottom: 1px solid #21262d; color: #c9d1d9; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover {{ background: #1f2428; }}
        .tag {{ display: inline-block; padding: 0.125rem 0.5rem; background: #21262d; border-radius: 3px; font-size: 0.75rem; font-family: monospace; }}

        .footer {{ text-align: center; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #30363d; color: #8b949e; font-size: 0.75rem; }}
    </style>
</head>
<body>
    <div class="dashboard">
        <header>
            <h1>Benchmark Dashboard</h1>
            <p class="subtitle">{len(runs)} runs · Latest: {runs[-1]['run_id'].replace('run_', '')}</p>
        </header>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Avg Judge Score</div>
                <div class="metric-value">{latest_val_score:.2f}</div>
                <div class="metric-change neutral">Latest validation</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Tokens / Query</div>
                <div class="metric-value">{latest_tokens:,.0f}</div>
                <div class="metric-change {'positive' if token_change < 0 else 'negative' if token_change > 0 else 'neutral'}">
                    {f'{token_change:+.1f}% vs first run' if len(runs) > 1 else 'Baseline'}
                </div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Total Epochs Run</div>
                <div class="metric-value">{total_epochs}</div>
                <div class="metric-change neutral">Across {len(runs)} runs</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Train vs Val Gap</div>
                <div class="metric-value">{train_val_gap:+.2f}</div>
                <div class="metric-change {'negative' if train_val_gap > 0.1 else 'positive' if train_val_gap < 0.05 else 'neutral'}">
                    {'Slight overfit' if train_val_gap > 0.1 else 'Good generalization' if train_val_gap < 0.05 else 'Normal gap'}
                </div>
            </div>
        </div>

        <div class="charts-grid">
            <div class="chart-card">
                <div class="chart-title">Performance × Epoch (Learning Curve)</div>
                <div class="chart-container">
                    <canvas id="epochScoreChart"></canvas>
                </div>
            </div>

            <div class="chart-card">
                <div class="chart-title">Tokens × Epoch</div>
                <div class="chart-container">
                    <canvas id="epochTokensChart"></canvas>
                </div>
            </div>

            <div class="chart-card full">
                <div class="chart-title">Rolling Training vs Validation (Latest Run)</div>
                <div class="chart-container">
                    <canvas id="rollingChart"></canvas>
                </div>
            </div>

            <div class="chart-card">
                <div class="chart-title">Avg Score Across Runs</div>
                <div class="chart-container">
                    <canvas id="runsScoreChart"></canvas>
                </div>
            </div>

            <div class="chart-card">
                <div class="chart-title">Avg Tokens Across Runs</div>
                <div class="chart-container">
                    <canvas id="runsTokensChart"></canvas>
                </div>
            </div>
        </div>

        <div class="runs-table">
            <div class="table-header">Run History</div>
            <table>
                <thead>
                    <tr>
                        <th>Run</th>
                        <th>Time</th>
                        <th>Model</th>
                        <th>Version</th>
                        <th>Epochs</th>
                        <th>Queries</th>
                        <th>Avg Tokens</th>
                        <th>Train Score</th>
                        <th>Val Score</th>
                    </tr>
                </thead>
                <tbody>
                    {self._build_runs_table(runs)}
                </tbody>
            </table>
        </div>

        <div class="footer">Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>

    <script>
        const chartColors = {{
            blue: '#58a6ff',
            green: '#3fb950',
            orange: '#d29922',
            purple: '#a371f7',
            gray: '#8b949e',
            gridColor: '#30363d',
        }};

        const defaultOptions = {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }} }},
            scales: {{
                x: {{ grid: {{ color: chartColors.gridColor }}, ticks: {{ color: chartColors.gray, font: {{ size: 11 }} }} }},
                y: {{ grid: {{ color: chartColors.gridColor }}, ticks: {{ color: chartColors.gray, font: {{ size: 11 }} }} }}
            }}
        }};

        // Epoch Score Chart (Train vs Validation scores by epoch)
        new Chart(document.getElementById('epochScoreChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(epoch_data['labels'])},
                datasets: [
                    {{
                        label: 'Train',
                        data: {json.dumps(epoch_data['train_score'])},
                        borderColor: chartColors.blue,
                        backgroundColor: 'rgba(88, 166, 255, 0.1)',
                        fill: false,
                        tension: 0.3,
                        pointRadius: 4,
                        borderWidth: 2
                    }},
                    {{
                        label: 'Validation',
                        data: {json.dumps(epoch_data['val_score'])},
                        borderColor: chartColors.green,
                        backgroundColor: 'rgba(63, 185, 80, 0.1)',
                        fill: false,
                        tension: 0.3,
                        pointRadius: 4,
                        borderWidth: 2
                    }}
                ]
            }},
            options: {{
                ...defaultOptions,
                plugins: {{ legend: {{ display: true, labels: {{ color: chartColors.gray }} }} }},
                scales: {{
                    ...defaultOptions.scales,
                    y: {{ ...defaultOptions.scales.y, min: 0, max: 1 }}
                }}
            }}
        }});

        // Epoch Tokens Chart
        new Chart(document.getElementById('epochTokensChart'), {{
            type: 'bar',
            data: {{
                labels: {json.dumps(epoch_data['labels'])},
                datasets: [
                    {{
                        label: 'Train',
                        data: {json.dumps(epoch_data['train_tokens'])},
                        backgroundColor: chartColors.blue,
                    }},
                    {{
                        label: 'Validation',
                        data: {json.dumps(epoch_data['val_tokens'])},
                        backgroundColor: chartColors.green,
                    }}
                ]
            }},
            options: {{
                ...defaultOptions,
                plugins: {{ legend: {{ display: true, labels: {{ color: chartColors.gray }} }} }}
            }}
        }});

        // Rolling chart with validation checkpoints
        const epochMarkers = {json.dumps(epoch_markers)};
        const annotations = epochMarkers.map(m => ({{
            type: 'line',
            xMin: m,
            xMax: m,
            borderColor: 'rgba(255,255,255,0.2)',
            borderWidth: 1,
            borderDash: [5, 5]
        }}));

        new Chart(document.getElementById('rollingChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(learning_curve_data['labels'])},
                datasets: [
                    {{
                        label: 'Train (rolling score)',
                        data: {json.dumps(learning_curve_data['scores'])},
                        borderColor: chartColors.blue,
                        backgroundColor: 'rgba(88, 166, 255, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 2,
                        borderWidth: 2
                    }},
                    {{
                        label: 'Validation',
                        data: {json.dumps([{'x': x, 'y': y} for x, y in zip(val_checkpoint_data['labels'], val_checkpoint_data['scores'])])},
                        borderColor: chartColors.green,
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0,
                        pointRadius: 6,
                        pointStyle: 'circle',
                        borderWidth: 2,
                        showLine: true
                    }}
                ]
            }},
            options: {{
                ...defaultOptions,
                plugins: {{
                    legend: {{ display: true, labels: {{ color: chartColors.gray }} }},
                }},
                scales: {{
                    ...defaultOptions.scales,
                    y: {{ ...defaultOptions.scales.y, min: 0, max: 1 }}
                }}
            }}
        }});

        // Runs score chart (historical)
        new Chart(document.getElementById('runsScoreChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(run_labels)},
                datasets: [
                    {{
                        label: 'Train',
                        data: {json.dumps(run_train_scores)},
                        borderColor: chartColors.blue,
                        tension: 0.3,
                        pointRadius: 4,
                        borderWidth: 2
                    }},
                    {{
                        label: 'Validation',
                        data: {json.dumps(run_val_scores)},
                        borderColor: chartColors.green,
                        tension: 0.3,
                        pointRadius: 4,
                        borderWidth: 2
                    }}
                ]
            }},
            options: {{
                ...defaultOptions,
                plugins: {{ legend: {{ display: true, labels: {{ color: chartColors.gray }} }} }},
                scales: {{
                    ...defaultOptions.scales,
                    y: {{ ...defaultOptions.scales.y, min: 0, max: 1 }}
                }}
            }}
        }});

        // Runs tokens chart (historical)
        new Chart(document.getElementById('runsTokensChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps(run_labels)},
                datasets: [{{
                    data: {json.dumps(run_tokens)},
                    borderColor: chartColors.orange,
                    backgroundColor: 'rgba(210, 153, 34, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    borderWidth: 2
                }}]
            }},
            options: defaultOptions
        }});
    </script>
</body>
</html>"""

        if output_path is None:
            output_path = BENCHMARKS_DIR / "dashboard.html"
        else:
            output_path = Path(output_path)

        with open(output_path, "w") as f:
            f.write(html)

        return str(output_path)


# ============================================================
# CLI
# ============================================================

async def main():
    suite = BenchmarkSuite()

    if len(sys.argv) < 2:
        print("""
Benchmark V2 - Track learning progress with LLM-based accuracy scoring.

Usage:
    python benchmark.py run                     Run benchmark (3 epochs, batch_size=2)
    python benchmark.py run --epochs 5          Run 5 epochs
    python benchmark.py run --batch-size 3      Run with batch size 3
    python benchmark.py run --no-improve        Baseline run (improver disabled)
    python benchmark.py dashboard               Regenerate dashboard
    python benchmark.py list                    List all runs

Options:
    --epochs N          Number of epochs (default: 3)
    --batch-size N      Queries per batch before validation (default: 2)
    --window N          Rolling average window (default: 5)
    --no-improve        Disable improver (for baseline comparison)
    --quiet, -q         Suppress agent output (tool calls, streaming)
""")
        sys.exit(1)

    command = sys.argv[1]

    if command == "run":
        # Parse arguments
        num_epochs = 3
        batch_size = 2
        window_size = 5
        improve_enabled = True
        quiet = False

        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--epochs":
                num_epochs = int(args[i + 1])
                i += 2
            elif args[i] == "--batch-size":
                batch_size = int(args[i + 1])
                i += 2
            elif args[i] == "--window":
                window_size = int(args[i + 1])
                i += 2
            elif args[i] == "--no-improve":
                improve_enabled = False
                i += 1
            elif args[i] in ["--quiet", "-q"]:
                quiet = True
                i += 1
            else:
                i += 1

        # Configure logging before importing agent (which sets up its own logging)
        configure_logging(quiet)

        await suite.run_benchmark(
            num_epochs=num_epochs,
            batch_size=batch_size,
            window_size=window_size,
            improve_enabled=improve_enabled,
            quiet=quiet,
        )

        # Open dashboard
        dashboard_path = BENCHMARKS_DIR / "dashboard.html"
        if dashboard_path.exists():
            webbrowser.open(f"file://{dashboard_path}")

    elif command == "dashboard":
        path = suite.generate_dashboard()
        print(f"Dashboard generated: {path}")
        webbrowser.open(f"file://{path}")

    elif command == "list":
        runs = suite.list_runs()
        if not runs:
            print("No benchmark runs found.")
        else:
            print(f"\n{'Run ID':<20} {'Time':<14} {'Model':<12} {'Epochs':<7} {'Queries':<8} {'Tokens':<10} {'Train':<7} {'Val'}")
            print("-" * 95)
            for r in runs:
                model = r['learner_model'].replace('claude-', '').replace('-20241022', '').replace('-20250514', '')[:10]
                print(f"{r['run_id']:<20} {r['timestamp'][5:16]:<14} {model:<12} {r['epochs']:<7} {r['queries']:<8} {r['avg_tokens']:<10} {r['train_score']:<7.2f} {r['val_score']:.2f}")

    elif command == "compare":
        if len(sys.argv) < 4:
            print("Usage: python benchmark.py compare <run1> <run2>")
            sys.exit(1)
        run1_id = sys.argv[2]
        run2_id = sys.argv[3]

        # Load runs
        runs_dir = BENCHMARKS_DIR / "runs"
        run1_path = runs_dir / f"{run1_id}.json"
        run2_path = runs_dir / f"{run2_id}.json"

        if not run1_path.exists():
            print(f"Run not found: {run1_id}")
            sys.exit(1)
        if not run2_path.exists():
            print(f"Run not found: {run2_id}")
            sys.exit(1)

        with open(run1_path) as f:
            run1 = json.load(f)
        with open(run2_path) as f:
            run2 = json.load(f)

        print(f"\n{'Metric':<25} {run1_id[:15]:<15} {run2_id[:15]:<15} {'Change':<15}")
        print("-" * 70)

        metrics = [
            ("Epochs", "num_epochs", ""),
            ("Total Queries", "total_queries", ""),
            ("Avg Tokens/Query", "avg_tokens_per_query", ""),
            ("Avg Tool Calls", "avg_tool_calls_per_query", ""),
            ("Train Judge Score", "avg_train_judge_score", ""),
            ("Val Judge Score", "avg_validation_judge_score", ""),
        ]

        for label, key, fmt in metrics:
            v1 = run1.get(key, 0)
            v2 = run2.get(key, 0)
            if isinstance(v1, float):
                change = v2 - v1
                print(f"{label:<25} {v1:<15.2f} {v2:<15.2f} {change:+.2f}")
            else:
                change = v2 - v1
                print(f"{label:<25} {v1:<15} {v2:<15} {change:+d}")

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
