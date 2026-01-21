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

__all__ = ["get_agent_version", "ExecutionTrace", "SessionTrace", "AgentMetrics"]


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

    # Runtime metrics (not serialized to JSON)
    latency_seconds: float = 0.0
    total_cost_usd: float = 0.0

    # Full execution history - each turn contains thinking + tool calls + results
    turns: list = field(default_factory=list)
    final_answer: str = ""

    def to_dict(self) -> dict:
        """Serialize trace to dict (clean format for logs).
        
        Format matches session trace structure:
        - Each turn has 'thinking' and 'tool_calls'
        - Each tool_call has 'tool', 'input', 'output'
        - Excludes runtime metrics (latency, cost, errors, etc.)
        """
        return {
            "agent_version": self.agent_version,
            "query": self.query,
            "timestamp": self.timestamp,
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tool_calls": self.total_tool_calls,
            "turns": self.turns,
            "final_answer": self.final_answer,
        }


@dataclass
class SessionTrace:
    """Tracks an entire conversation session (multiple queries)."""
    session_id: str = field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_version: dict = field(default_factory=get_agent_version)

    # All queries in this session
    queries: list[ExecutionTrace] = field(default_factory=list)

    # Aggregated metrics
    end_time: str = ""
    total_latency_seconds: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_tool_calls: int = 0

    def add_query(self, trace: ExecutionTrace):
        """Add a query trace to the session."""
        self.queries.append(trace)
        self.total_latency_seconds += trace.latency_seconds
        self.total_tokens += trace.total_tokens
        self.total_cost_usd += trace.total_cost_usd
        self.total_tool_calls += trace.total_tool_calls

    def finalize(self):
        """Finalize session when ending."""
        self.end_time = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "agent_version": self.agent_version,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_queries": len(self.queries),
            "total_latency_seconds": round(self.total_latency_seconds, 2),
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_tool_calls": self.total_tool_calls,
            "queries": [q.to_dict() for q in self.queries],
        }

    def save(self, traces_dir: Path) -> str:
        """Save the session trace to a file."""
        self.finalize()
        traces_dir.mkdir(exist_ok=True)
        filename = f"session_{self.session_id}.json"
        filepath = traces_dir / filename
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        return str(filepath)


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
        total_latency = sum(t.latency_seconds for t in self.traces)
        latencies = [t.latency_seconds for t in self.traces if t.latency_seconds > 0]

        return {
            "total_queries": total,
            "total_tokens": total_tokens,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tool_calls": total_tool_calls,
            "total_cost_usd": round(total_cost, 4),
            "total_latency_seconds": round(total_latency, 2),
            "avg_tokens_per_query": round(total_tokens / total, 2),
            "avg_tool_calls_per_query": round(total_tool_calls / total, 2),
            "avg_latency_seconds": round(total_latency / total, 2) if total > 0 else 0,
            "min_latency_seconds": round(min(latencies), 2) if latencies else 0,
            "max_latency_seconds": round(max(latencies), 2) if latencies else 0,
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
