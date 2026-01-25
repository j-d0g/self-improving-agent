#!/usr/bin/env python3
"""
Benchmark Suite for Self-Improving Agent

Tracks performance across runs to measure improvement over time.
Generates visualizations showing growth of the system.

Usage:
    # Run a full benchmark (train → improve → test → compare)
    python benchmark.py run

    # Compare two specific runs
    python benchmark.py compare run_20260121_010000 run_20260121_020000

    # View dashboard of all runs
    python benchmark.py dashboard

    # List all benchmark runs
    python benchmark.py list
"""

import json
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
import statistics
import uuid

PROJECT_ROOT = Path(__file__).parent.parent  # evals/ -> agent/
BENCHMARKS_DIR = Path(__file__).parent / "benchmarks"  # evals/benchmarks/

# Add project root to path for imports
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class QueryResult:
    """Result of a single query evaluation."""
    query: str
    expected_answer: str
    agent_answer: Optional[str]
    tokens: int
    tool_calls: int
    status: str  # "success" | "error"
    error: Optional[str] = None
    
    # Accuracy metrics (set by evaluator)
    accuracy_score: Optional[float] = None  # 0-1 scale
    key_facts_matched: Optional[int] = None
    key_facts_total: Optional[int] = None


@dataclass 
class BenchmarkRun:
    """A complete benchmark run with all metrics."""
    run_id: str
    timestamp: str
    agent_version: str
    model: str = "claude-sonnet-4-20250514"
    
    # Configuration
    train_file: str = ""
    test_file: str = ""
    improvement_applied: bool = False
    
    # Aggregate metrics
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    
    # Efficiency metrics
    total_tokens: int = 0
    total_tool_calls: int = 0
    avg_tokens_per_query: float = 0.0
    avg_tool_calls_per_query: float = 0.0
    
    # Latency metrics
    total_latency_seconds: float = 0.0
    avg_latency_seconds: float = 0.0
    
    # Accuracy metrics (if evaluator ran)
    avg_accuracy: Optional[float] = None
    
    # Individual results
    results: list[dict] = field(default_factory=list)
    
    # Knowledge state snapshot
    knowledge_snapshot: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "BenchmarkRun":
        return cls(**data)


@dataclass
class Comparison:
    """Comparison between two benchmark runs."""
    baseline_id: str
    current_id: str
    timestamp: str
    
    # Efficiency changes (negative = improvement)
    token_change_pct: float = 0.0
    tool_call_change_pct: float = 0.0
    
    # Accuracy changes (positive = improvement)
    accuracy_change: Optional[float] = None
    
    # Success rate change
    success_rate_change: float = 0.0
    
    # Per-query comparisons
    query_comparisons: list[dict] = field(default_factory=list)
    
    # Summary
    improved_queries: int = 0
    regressed_queries: int = 0
    unchanged_queries: int = 0


# ============================================================
# BENCHMARK RUNNER
# ============================================================

class BenchmarkSuite:
    """Orchestrates benchmark runs and comparisons."""
    
    def __init__(self):
        BENCHMARKS_DIR.mkdir(exist_ok=True)
        (BENCHMARKS_DIR / "runs").mkdir(exist_ok=True)
        (BENCHMARKS_DIR / "comparisons").mkdir(exist_ok=True)
    
    def _get_agent_version(self) -> str:
        """Get current agent version from git."""
        import subprocess
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
    
    def _get_model(self) -> str:
        """Get the model being used by the agent."""
        # Default model used by LearnerAgent
        return "claude-haiku-3-5-20241022"
    
    def _snapshot_knowledge(self) -> dict:
        """Capture current state of knowledge files."""
        knowledge_dir = PROJECT_ROOT / "knowledge"
        snapshot = {}
        for f in knowledge_dir.glob("*"):
            if f.is_file() and f.suffix in [".md", ".py", ".txt"]:
                snapshot[f.name] = {
                    "size": f.stat().st_size,
                    "lines": len(f.read_text().splitlines()),
                    "hash": hash(f.read_text()) % (10**8)  # Simple hash for change detection
                }
        return snapshot
    
    def _load_eval_file(self, path: str) -> list[dict]:
        """Load queries from eval file."""
        eval_path = Path(__file__).parent / path  # evals/ directory
        with open(eval_path) as f:
            return json.load(f)
    
    async def run_queries(self, queries: list[dict], run_id: str, enable_improve: bool = False) -> list[dict]:
        """Run queries through the agent and collect results."""
        from agent import LearnerAgent

        agent = LearnerAgent(
            log_traces=True,
            enable_background_improve=enable_improve
        )

        results = []
        for i, q in enumerate(queries, 1):
            query_text = q["query"]
            expected = q.get("answer", "")
            query_run_id = uuid.uuid4().hex[:12]

            print(f"  [{i}/{len(queries)}] {query_text[:50]}...")

            try:
                result = await agent._query_async(query_text, run_id=query_run_id)
                trace = result["trace"]

                results.append({
                    "query": query_text,
                    "expected_answer": expected,
                    "agent_answer": result["answer"],
                    "tokens": trace.total_tokens,
                    "tool_calls": trace.total_tool_calls,
                    "latency_seconds": getattr(trace, 'latency_seconds', 0.0),
                    "status": "success",
                    "error": None
                })
                print(f"      ✓ {trace.total_tokens} tokens, {trace.total_tool_calls} tools, {getattr(trace, 'latency_seconds', 0):.1f}s")

            except Exception as e:
                results.append({
                    "query": query_text,
                    "expected_answer": expected,
                    "agent_answer": None,
                    "tokens": 0,
                    "tool_calls": 0,
                    "latency_seconds": 0.0,
                    "status": "error",
                    "error": str(e)
                })
                print(f"      ✗ Error: {e}")

        return results
    
    async def run_benchmark(
        self,
        train_file: str = "train.json",
        test_file: str = "test.json",
        apply_improvements: bool = True,
        run_id: Optional[str] = None
    ) -> BenchmarkRun:
        """
        Run a complete benchmark cycle:
        1. Run training queries (optional improvement)
        2. Run test queries
        3. Compute metrics
        4. Save results
        """
        if run_id is None:
            run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"\n{'='*60}")
        print(f"BENCHMARK RUN: {run_id}")
        print(f"{'='*60}")
        
        # Initialize run
        run = BenchmarkRun(
            run_id=run_id,
            timestamp=datetime.now().isoformat(),
            agent_version=self._get_agent_version(),
            model=self._get_model(),
            train_file=train_file,
            test_file=test_file,
            improvement_applied=apply_improvements,
            knowledge_snapshot=self._snapshot_knowledge()
        )
        
        # Phase 1: Training (with optional improvement)
        if apply_improvements:
            print(f"\n[Phase 1] Training with improvements...")
            train_queries = self._load_eval_file(train_file)
            print(f"  Running {len(train_queries)} training queries...")

            # Run training queries with background improvement enabled
            await self.run_queries(train_queries, run_id, enable_improve=True)

            # Wait for background improvement tasks to complete
            print(f"\n  Waiting for background improvements...")
            from agent import wait_for_background_tasks
            await wait_for_background_tasks(timeout=60.0)

            # Update knowledge snapshot after improvements
            run.knowledge_snapshot = self._snapshot_knowledge()

        # Phase 2: Test evaluation
        print(f"\n[Phase 2] Test evaluation...")
        test_queries = self._load_eval_file(test_file)
        print(f"  Running {len(test_queries)} test queries...")

        # Run test queries without improvement (clean evaluation)
        results = await self.run_queries(test_queries, run_id, enable_improve=False)
        run.results = results
        
        # Compute aggregate metrics
        successful = [r for r in results if r["status"] == "success"]
        run.total_queries = len(results)
        run.successful_queries = len(successful)
        run.failed_queries = len(results) - len(successful)
        
        if successful:
            run.total_tokens = sum(r["tokens"] for r in successful)
            run.total_tool_calls = sum(r["tool_calls"] for r in successful)
            run.total_latency_seconds = sum(r.get("latency_seconds", 0) for r in successful)
            run.avg_tokens_per_query = run.total_tokens / len(successful)
            run.avg_tool_calls_per_query = run.total_tool_calls / len(successful)
            run.avg_latency_seconds = run.total_latency_seconds / len(successful)
        
        # Save run
        run_path = BENCHMARKS_DIR / "runs" / f"{run_id}.json"
        with open(run_path, "w") as f:
            json.dump(run.to_dict(), f, indent=2)
        
        # Print summary
        print(f"\n{'='*60}")
        print("BENCHMARK SUMMARY")
        print(f"{'='*60}")
        print(f"  Run ID: {run.run_id}")
        print(f"  Agent Version: {run.agent_version}")
        print(f"  Queries: {run.successful_queries}/{run.total_queries} successful")
        print(f"  Total Tokens: {run.total_tokens:,}")
        print(f"  Avg Tokens/Query: {run.avg_tokens_per_query:,.1f}")
        print(f"  Avg Tool Calls/Query: {run.avg_tool_calls_per_query:.1f}")
        print(f"  Avg Latency: {run.avg_latency_seconds:.1f}s")
        print(f"\n  Saved to: {run_path}")
        
        return run
    
    def compare_runs(self, baseline_id: str, current_id: str) -> Comparison:
        """Compare two benchmark runs and compute improvement metrics."""
        # Load runs
        baseline_path = BENCHMARKS_DIR / "runs" / f"{baseline_id}.json"
        current_path = BENCHMARKS_DIR / "runs" / f"{current_id}.json"
        
        with open(baseline_path) as f:
            baseline = BenchmarkRun.from_dict(json.load(f))
        with open(current_path) as f:
            current = BenchmarkRun.from_dict(json.load(f))
        
        comparison = Comparison(
            baseline_id=baseline_id,
            current_id=current_id,
            timestamp=datetime.now().isoformat()
        )
        
        # Efficiency changes (negative = better)
        if baseline.avg_tokens_per_query > 0:
            comparison.token_change_pct = (
                (current.avg_tokens_per_query - baseline.avg_tokens_per_query) 
                / baseline.avg_tokens_per_query * 100
            )
        
        if baseline.avg_tool_calls_per_query > 0:
            comparison.tool_call_change_pct = (
                (current.avg_tool_calls_per_query - baseline.avg_tool_calls_per_query)
                / baseline.avg_tool_calls_per_query * 100
            )
        
        # Success rate change
        baseline_rate = baseline.successful_queries / baseline.total_queries if baseline.total_queries else 0
        current_rate = current.successful_queries / current.total_queries if current.total_queries else 0
        comparison.success_rate_change = (current_rate - baseline_rate) * 100
        
        # Per-query comparison
        baseline_by_query = {r["query"]: r for r in baseline.results}
        current_by_query = {r["query"]: r for r in current.results}
        
        for query, curr_result in current_by_query.items():
            if query in baseline_by_query:
                base_result = baseline_by_query[query]
                
                # Compare tokens
                token_diff = curr_result["tokens"] - base_result["tokens"]
                token_pct = (token_diff / base_result["tokens"] * 100) if base_result["tokens"] else 0
                
                # Compare tool calls
                tool_diff = curr_result["tool_calls"] - base_result["tool_calls"]
                
                # Classify change
                if token_pct < -10:  # >10% fewer tokens = improved
                    comparison.improved_queries += 1
                    status = "improved"
                elif token_pct > 10:  # >10% more tokens = regressed
                    comparison.regressed_queries += 1
                    status = "regressed"
                else:
                    comparison.unchanged_queries += 1
                    status = "unchanged"
                
                comparison.query_comparisons.append({
                    "query": query[:60] + "..." if len(query) > 60 else query,
                    "baseline_tokens": base_result["tokens"],
                    "current_tokens": curr_result["tokens"],
                    "token_change_pct": round(token_pct, 1),
                    "baseline_tools": base_result["tool_calls"],
                    "current_tools": curr_result["tool_calls"],
                    "status": status
                })
        
        # Save comparison
        comp_path = BENCHMARKS_DIR / "comparisons" / f"{baseline_id}_vs_{current_id}.json"
        with open(comp_path, "w") as f:
            json.dump(asdict(comparison), f, indent=2)
        
        return comparison
    
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
                        "model": data.get("model", "sonnet-4"),
                        "agent_version": data["agent_version"],
                        "queries": data["total_queries"],
                        "success_rate": f"{data['successful_queries']}/{data['total_queries']}",
                        "avg_tokens": round(data["avg_tokens_per_query"], 1),
                        "avg_tools": round(data["avg_tool_calls_per_query"], 1),
                        "avg_latency": round(data.get("avg_latency_seconds", 0), 1)
                    })
        return runs
    
    def generate_dashboard(self, output_path: Optional[str] = None) -> str:
        """Generate an HTML dashboard showing performance over time."""
        runs = []
        runs_dir = BENCHMARKS_DIR / "runs"
        
        if runs_dir.exists():
            for f in sorted(runs_dir.glob("*.json")):
                with open(f) as fp:
                    runs.append(json.load(fp))
        
        if not runs:
            return "No benchmark runs found."
        
        # Sort by timestamp
        runs.sort(key=lambda x: x["timestamp"])
        
        # Prepare data for charts
        timestamps = [r["timestamp"][:16].replace("T", " ") for r in runs]
        tokens = [r["avg_tokens_per_query"] for r in runs]
        tools = [r["avg_tool_calls_per_query"] for r in runs]
        latencies = [r.get("avg_latency_seconds", 0) for r in runs]
        success_rates = [r["successful_queries"] / r["total_queries"] * 100 if r["total_queries"] else 0 for r in runs]
        
        # Calculate improvements from first to last
        if len(runs) >= 2:
            first, last = runs[0], runs[-1]
            token_improvement = ((first["avg_tokens_per_query"] - last["avg_tokens_per_query"]) 
                                / first["avg_tokens_per_query"] * 100) if first["avg_tokens_per_query"] else 0
            tool_improvement = ((first["avg_tool_calls_per_query"] - last["avg_tool_calls_per_query"])
                               / first["avg_tool_calls_per_query"] * 100) if first["avg_tool_calls_per_query"] else 0
            latency_improvement = ((first.get("avg_latency_seconds", 0) - last.get("avg_latency_seconds", 0))
                                  / first.get("avg_latency_seconds", 1) * 100) if first.get("avg_latency_seconds", 0) else 0
        else:
            token_improvement = tool_improvement = latency_improvement = 0
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Benchmark Results</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f8f9fa;
            color: #212529;
            line-height: 1.5;
            padding: 2rem;
        }}
        
        .dashboard {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #dee2e6;
        }}
        
        h1 {{
            font-size: 1.5rem;
            font-weight: 600;
            color: #212529;
            margin-bottom: 0.25rem;
        }}
        
        .subtitle {{
            color: #6c757d;
            font-size: 0.875rem;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        @media (max-width: 900px) {{
            .metrics-grid {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}
        
        @media (max-width: 600px) {{
            .metrics-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
        
        .metric-card {{
            background: #fff;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 1.25rem;
        }}
        
        .metric-label {{
            font-size: 0.75rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #6c757d;
            margin-bottom: 0.5rem;
        }}
        
        .metric-value {{
            font-size: 1.75rem;
            font-weight: 600;
            color: #212529;
        }}
        
        .metric-change {{
            font-size: 0.8125rem;
            margin-top: 0.25rem;
        }}
        
        .metric-change.positive {{
            color: #198754;
        }}
        
        .metric-change.negative {{
            color: #dc3545;
        }}
        
        .metric-change.neutral {{
            color: #6c757d;
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        
        @media (max-width: 900px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .chart-card {{
            background: #fff;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 1.25rem;
        }}
        
        .chart-title {{
            font-size: 0.875rem;
            font-weight: 600;
            margin-bottom: 1rem;
            color: #212529;
        }}
        
        .chart-container {{
            position: relative;
            height: 220px;
        }}
        
        .runs-table {{
            background: #fff;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            overflow: hidden;
        }}
        
        .table-header {{
            padding: 1rem 1.25rem;
            border-bottom: 1px solid #dee2e6;
            font-weight: 600;
            font-size: 0.875rem;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}
        
        th {{
            padding: 0.75rem 1rem;
            text-align: left;
            font-weight: 500;
            color: #6c757d;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid #dee2e6;
            background: #f8f9fa;
        }}
        
        td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #f1f3f4;
            color: #212529;
        }}
        
        tr:last-child td {{
            border-bottom: none;
        }}
        
        tr:hover {{
            background: #f8f9fa;
        }}
        
        .version-tag {{
            display: inline-block;
            padding: 0.125rem 0.5rem;
            background: #e9ecef;
            border-radius: 3px;
            font-size: 0.75rem;
            font-family: 'SF Mono', Monaco, monospace;
            color: #495057;
        }}
        
        .trend {{
            font-weight: 500;
        }}
        
        .trend.improved {{
            color: #198754;
        }}
        
        .trend.regressed {{
            color: #dc3545;
        }}
        
        .trend.baseline {{
            color: #6c757d;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #dee2e6;
            color: #6c757d;
            font-size: 0.75rem;
        }}
    </style>
</head>
<body>
    <div class="dashboard">
        <header>
            <h1>Benchmark Results</h1>
            <p class="subtitle">{len(runs)} runs &middot; {runs[-1].get("model", "claude-sonnet-4-20250514")}</p>
        </header>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">Avg Tokens / Query</div>
                <div class="metric-value">{tokens[-1]:,.0f}</div>
                <div class="metric-change {'positive' if token_improvement > 0 else 'negative' if token_improvement < 0 else 'neutral'}">
                    {f"{token_improvement:+.1f}% vs baseline" if len(runs) > 1 else "Baseline"}
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Avg Tool Calls / Query</div>
                <div class="metric-value">{tools[-1]:.1f}</div>
                <div class="metric-change {'positive' if tool_improvement > 0 else 'negative' if tool_improvement < 0 else 'neutral'}">
                    {f"{tool_improvement:+.1f}% vs baseline" if len(runs) > 1 else "Baseline"}
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Avg Latency</div>
                <div class="metric-value">{latencies[-1]:.1f}s</div>
                <div class="metric-change {'positive' if latency_improvement > 0 else 'negative' if latency_improvement < 0 else 'neutral'}">
                    {f"{latency_improvement:+.1f}% vs baseline" if len(runs) > 1 and latencies[0] > 0 else "Baseline"}
                </div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Success Rate</div>
                <div class="metric-value">{success_rates[-1]:.0f}%</div>
                <div class="metric-change neutral">Latest run</div>
            </div>
            
            <div class="metric-card">
                <div class="metric-label">Total Runs</div>
                <div class="metric-value">{len(runs)}</div>
                <div class="metric-change neutral">Since {timestamps[0][:10]}</div>
            </div>
        </div>
        
        <div class="charts-grid">
            <div class="chart-card">
                <div class="chart-title">Tokens per Query</div>
                <div class="chart-container">
                    <canvas id="tokensChart"></canvas>
                </div>
            </div>
            
            <div class="chart-card">
                <div class="chart-title">Tool Calls per Query</div>
                <div class="chart-container">
                    <canvas id="toolsChart"></canvas>
                </div>
            </div>
            
            <div class="chart-card">
                <div class="chart-title">Latency (seconds)</div>
                <div class="chart-container">
                    <canvas id="latencyChart"></canvas>
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
                        <th>Success</th>
                        <th>Tokens</th>
                        <th>Tools</th>
                        <th>Latency</th>
                        <th>Change</th>
                    </tr>
                </thead>
                <tbody>
                    {"".join(f'''
                    <tr>
                        <td>{r["run_id"].replace("run_", "")[:20]}</td>
                        <td>{r["timestamp"][5:16].replace("T", " ")}</td>
                        <td><span class="version-tag">{r.get("model", "sonnet-4").replace("claude-", "").replace("-20250514", "")}</span></td>
                        <td><span class="version-tag">{r["agent_version"][:8]}</span></td>
                        <td>{r["successful_queries"]}/{r["total_queries"]}</td>
                        <td>{r["avg_tokens_per_query"]:,.0f}</td>
                        <td>{r["avg_tool_calls_per_query"]:.1f}</td>
                        <td>{r.get("avg_latency_seconds", 0):.1f}s</td>
                        <td class="trend {"improved" if i > 0 and r["avg_tokens_per_query"] < runs[i-1]["avg_tokens_per_query"] else "regressed" if i > 0 and r["avg_tokens_per_query"] > runs[i-1]["avg_tokens_per_query"] else "baseline"}">
                            {f'{((r["avg_tokens_per_query"] - runs[i-1]["avg_tokens_per_query"]) / runs[i-1]["avg_tokens_per_query"] * 100):+.1f}%' if i > 0 else "—"}
                        </td>
                    </tr>
                    ''' for i, r in enumerate(reversed(runs)))}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
    
    <script>
        const chartOptions = {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{
                legend: {{ display: false }},
            }},
            scales: {{
                x: {{
                    grid: {{ color: '#f1f3f4' }},
                    ticks: {{ color: '#6c757d', font: {{ size: 11 }} }}
                }},
                y: {{
                    grid: {{ color: '#f1f3f4' }},
                    ticks: {{ color: '#6c757d', font: {{ size: 11 }} }},
                    beginAtZero: false
                }}
            }}
        }};
        
        new Chart(document.getElementById('tokensChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps([t[5:16].replace("T", " ") for t in timestamps])},
                datasets: [{{
                    data: {json.dumps(tokens)},
                    borderColor: '#0d6efd',
                    backgroundColor: 'rgba(13, 110, 253, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#0d6efd',
                    pointRadius: 3,
                    borderWidth: 2
                }}]
            }},
            options: chartOptions
        }});
        
        new Chart(document.getElementById('toolsChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps([t[5:16].replace("T", " ") for t in timestamps])},
                datasets: [{{
                    data: {json.dumps(tools)},
                    borderColor: '#6c757d',
                    backgroundColor: 'rgba(108, 117, 125, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#6c757d',
                    pointRadius: 3,
                    borderWidth: 2
                }}]
            }},
            options: chartOptions
        }});
        
        new Chart(document.getElementById('latencyChart'), {{
            type: 'line',
            data: {{
                labels: {json.dumps([t[5:16].replace("T", " ") for t in timestamps])},
                datasets: [{{
                    data: {json.dumps(latencies)},
                    borderColor: '#198754',
                    backgroundColor: 'rgba(25, 135, 84, 0.05)',
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#198754',
                    pointRadius: 3,
                    borderWidth: 2
                }}]
            }},
            options: chartOptions
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

def print_comparison(comp: Comparison):
    """Pretty print a comparison."""
    print(f"\n{'='*60}")
    print("COMPARISON RESULTS")
    print(f"{'='*60}")
    print(f"  Baseline: {comp.baseline_id}")
    print(f"  Current:  {comp.current_id}")
    print()
    
    # Efficiency
    token_emoji = "✓" if comp.token_change_pct < 0 else "✗" if comp.token_change_pct > 0 else "—"
    tool_emoji = "✓" if comp.tool_call_change_pct < 0 else "✗" if comp.tool_call_change_pct > 0 else "—"
    
    print("  EFFICIENCY:")
    print(f"    {token_emoji} Tokens: {comp.token_change_pct:+.1f}%")
    print(f"    {tool_emoji} Tool Calls: {comp.tool_call_change_pct:+.1f}%")
    print()
    
    print("  QUERY BREAKDOWN:")
    print(f"    ↑ Improved: {comp.improved_queries}")
    print(f"    ↓ Regressed: {comp.regressed_queries}")
    print(f"    — Unchanged: {comp.unchanged_queries}")
    print()
    
    # Per-query details
    if comp.query_comparisons:
        print("  PER-QUERY CHANGES:")
        for q in sorted(comp.query_comparisons, key=lambda x: x["token_change_pct"]):
            emoji = "↑" if q["status"] == "improved" else "↓" if q["status"] == "regressed" else "—"
            print(f"    {emoji} {q['token_change_pct']:+6.1f}% | {q['query']}")


async def main():
    """CLI entry point."""
    suite = BenchmarkSuite()
    
    if len(sys.argv) < 2:
        print("""
Benchmark Suite for Self-Improving Agent

Usage:
    python benchmark.py run [--no-improve]     Run full benchmark cycle
    python benchmark.py compare <id1> <id2>    Compare two runs
    python benchmark.py dashboard              Generate HTML dashboard
    python benchmark.py list                   List all runs
    python benchmark.py quick                  Quick test run (no improvements)

Examples:
    python benchmark.py run
    python benchmark.py compare run_20260121_010000 run_20260121_020000
    python benchmark.py dashboard
""")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "run":
        apply_improvements = "--no-improve" not in sys.argv
        run = await suite.run_benchmark(apply_improvements=apply_improvements)
        
        # Auto-generate dashboard after run
        dashboard_path = suite.generate_dashboard()
        print(f"\n  Dashboard: {dashboard_path}")
        
    elif command == "quick":
        # Quick test run without improvements
        run = await suite.run_benchmark(
            train_file="train.json",
            test_file="test.json",
            apply_improvements=False
        )
        dashboard_path = suite.generate_dashboard()
        print(f"\n  Dashboard: {dashboard_path}")
        
    elif command == "compare":
        if len(sys.argv) < 4:
            print("Usage: python benchmark.py compare <baseline_id> <current_id>")
            sys.exit(1)
        comp = suite.compare_runs(sys.argv[2], sys.argv[3])
        print_comparison(comp)
        
    elif command == "dashboard":
        path = suite.generate_dashboard()
        print(f"Dashboard generated: {path}")
        
        # Try to open in browser
        import webbrowser
        webbrowser.open(f"file://{path}")
        
    elif command == "list":
        runs = suite.list_runs()
        if not runs:
            print("No benchmark runs found.")
        else:
            print(f"\n{'Run ID':<30} {'Timestamp':<17} {'Model':<12} {'Version':<10} {'Queries':<8} {'Tokens':<10} {'Tools':<8} {'Latency'}")
            print("-" * 110)
            for r in runs:
                model_short = r['model'].replace('claude-', '').replace('-20250514', '')[:10]
                print(f"{r['run_id']:<30} {r['timestamp'][:16]:<17} {model_short:<12} {r['agent_version']:<10} {r['success_rate']:<8} {r['avg_tokens']:<10} {r['avg_tools']:<8} {r['avg_latency']:.1f}s")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
