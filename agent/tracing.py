"""
Tracing and Metrics Module

Shared dataclasses and utilities for tracking agent execution metrics.
Used by both agent.py and agent_sdk.py.
"""

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

__all__ = ["get_agent_version", "ExecutionTrace", "AgentMetrics"]


def get_agent_version() -> dict:
    """Get version info from git commit and working tree status."""
    try:
        # Get current commit hash
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=Path(__file__).parent
        ).stdout.strip()[:8]  # Short hash

        # Check if working tree is dirty
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=Path(__file__).parent
        ).stdout.strip() != ""

        return {
            "commit": commit,
            "dirty": dirty,
            "version": f"{commit}{'-dirty' if dirty else ''}"
        }
    except Exception:
        return {"commit": "unknown", "dirty": False, "version": "unknown"}


@dataclass
class ExecutionTrace:
    """Tracks a single query execution for metrics."""
    query: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_version: dict = field(default_factory=get_agent_version)

    # Token metrics
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tool_calls: int = 0

    # Cost tracking
    total_cost_usd: float = 0.0

    # Error tracking
    errors_encountered: list = field(default_factory=list)
    error_recovered: bool = False
    learning_triggered: bool = False
    total_attempts: int = 0

    # Full execution history - each turn contains thinking + tool calls + results
    turns: list = field(default_factory=list)
    final_answer: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_version": self.agent_version,
            "query": self.query,
            "timestamp": self.timestamp,
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_cost_usd": self.total_cost_usd,
            "total_tool_calls": self.total_tool_calls,
            "errors_encountered": self.errors_encountered,
            "error_recovered": self.error_recovered,
            "learning_triggered": self.learning_triggered,
            "total_attempts": self.total_attempts,
            "turns": self.turns,
            "final_answer": self.final_answer,
        }


@dataclass
class AgentMetrics:
    """Aggregated metrics across multiple queries."""
    traces: list[ExecutionTrace] = field(default_factory=list)

    def add_trace(self, trace: ExecutionTrace):
        self.traces.append(trace)

    def compute(self) -> dict:
        if not self.traces:
            return {"error": "No traces recorded"}

        total = len(self.traces)
        total_tokens = sum(t.total_tokens for t in self.traces)
        total_input_tokens = sum(t.input_tokens for t in self.traces)
        total_output_tokens = sum(t.output_tokens for t in self.traces)
        total_tool_calls = sum(t.total_tool_calls for t in self.traces)
        total_cost = sum(t.total_cost_usd for t in self.traces)

        return {
            "total_queries": total,
            "total_tokens": total_tokens,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tool_calls": total_tool_calls,
            "total_cost_usd": round(total_cost, 4),
            "avg_tokens_per_query": round(total_tokens / total, 2),
            "avg_tool_calls_per_query": round(total_tool_calls / total, 2),
        }

    def save(self, path: str = "metrics.json"):
        data = {
            "computed_at": datetime.now().isoformat(),
            "summary": self.compute(),
            "traces": [t.to_dict() for t in self.traces]
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def save_trace(self, trace: ExecutionTrace, traces_dir: Path) -> str:
        """Save a single trace to the traces directory."""
        traces_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trace_{timestamp}.json"
        filepath = traces_dir / filename
        with open(filepath, "w") as f:
            json.dump(trace.to_dict(), f, indent=2)
        return str(filepath)
