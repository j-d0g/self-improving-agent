#!/usr/bin/env python3
"""
Evaluation Runner

Runs evaluation queries through the agent and saves results for analysis.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent import FinancialAnalysisAgent


def load_eval_file(eval_path: str) -> list[dict]:
    """Load evaluation queries from JSON file."""
    with open(eval_path) as f:
        return json.load(f)


def run_evaluation(eval_path: str, output_path: str = None) -> dict:
    """
    Run all queries from an evaluation file through the agent.

    Args:
        eval_path: Path to evaluation JSON file (e.g., evals/train.json)
        output_path: Optional path to save results. Defaults to learnings/eval_<timestamp>.json

    Returns:
        dict with evaluation results and summary statistics
    """
    print(f"Loading evaluation file: {eval_path}")
    queries = load_eval_file(eval_path)
    print(f"Found {len(queries)} queries to evaluate\n")

    agent = FinancialAnalysisAgent()
    results = []

    for i, query_data in enumerate(queries, 1):
        query = query_data["query"]
        difficulty = query_data.get("difficulty", "unknown")

        print(f"[{i}/{len(queries)}] ({difficulty}) {query[:60]}...")

        try:
            result = agent.query(query)
            trace = result["trace"]

            results.append({
                "query": query,
                "expected_answer": query_data.get("answer", ""),
                "difficulty": difficulty,
                "tests": query_data.get("tests", ""),
                "agent_answer": result["answer"],
                "metrics": {
                    "total_tokens": trace.total_tokens,
                    "input_tokens": trace.input_tokens,
                    "output_tokens": trace.output_tokens,
                    "tool_calls": trace.total_tool_calls,
                },
                "status": "success"
            })
            print(f"    -> Completed (tokens: {trace.total_tokens}, tools: {trace.total_tool_calls})")

        except Exception as e:
            results.append({
                "query": query,
                "expected_answer": query_data.get("answer", ""),
                "difficulty": difficulty,
                "tests": query_data.get("tests", ""),
                "agent_answer": None,
                "error": str(e),
                "status": "error"
            })
            print(f"    -> ERROR: {e}")

    # Compute summary
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    total_tokens = sum(r.get("metrics", {}).get("total_tokens", 0) for r in results)
    total_tool_calls = sum(r.get("metrics", {}).get("tool_calls", 0) for r in results)

    summary = {
        "total_queries": len(results),
        "successful": success_count,
        "errors": error_count,
        "success_rate": round(success_count / len(results) * 100, 1) if results else 0,
        "total_tokens": total_tokens,
        "total_tool_calls": total_tool_calls,
        "avg_tokens_per_query": round(total_tokens / success_count, 1) if success_count else 0,
        "avg_tool_calls_per_query": round(total_tool_calls / success_count, 1) if success_count else 0,
    }

    output = {
        "eval_file": eval_path,
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "results": results
    }

    # Save results
    if output_path is None:
        logs_dir = Path(__file__).parent / "learnings"
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = logs_dir / f"eval_{timestamp}.json"

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*60}")
    print("EVALUATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Total queries: {summary['total_queries']}")
    print(f"  Successful: {summary['successful']}")
    print(f"  Errors: {summary['errors']}")
    print(f"  Success rate: {summary['success_rate']}%")
    print(f"  Total tokens: {summary['total_tokens']}")
    print(f"  Avg tokens/query: {summary['avg_tokens_per_query']}")
    print(f"  Avg tool calls/query: {summary['avg_tool_calls_per_query']}")
    print(f"\nResults saved to: {output_path}")

    return output


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("""
Evaluation Runner

Usage:
  python eval_runner.py <eval_file> [output_file]

Examples:
  python eval_runner.py evals/train.json
  python eval_runner.py evals/test.json learnings/test_results.json
""")
        sys.exit(1)

    eval_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    run_evaluation(eval_path, output_path)


if __name__ == "__main__":
    main()
