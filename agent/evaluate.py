#!/usr/bin/env python3
"""
Evaluate - Run evaluation queries through the agent

Usage:
    python evaluate.py train          Run training set
    python evaluate.py test           Run test set
    python evaluate.py train-test     Run both (train first, then test)
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent import LearnerAgent

PROJECT_ROOT = Path(__file__).parent
EVALS_DIR = PROJECT_ROOT / "evals"
RESULTS_DIR = EVALS_DIR / "results"


def load_eval_file(eval_path: Path) -> list[dict]:
    """Load evaluation queries from JSON file."""
    with open(eval_path) as f:
        return json.load(f)


def run_evaluation(eval_path: Path, label: str = None) -> dict:
    """
    Run all queries from an evaluation file through the agent.

    Args:
        eval_path: Path to evaluation JSON file
        label: Label for this run (e.g., "train", "test")

    Returns:
        dict with evaluation results and summary statistics
    """
    print(f"\n{'='*60}")
    print(f"EVALUATION: {label or eval_path.name}")
    print(f"{'='*60}")
    
    print(f"Loading: {eval_path}")
    queries = load_eval_file(eval_path)
    print(f"Found {len(queries)} queries\n")

    agent = LearnerAgent()
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
                    "latency_seconds": getattr(trace, 'latency_seconds', 0),
                },
                "status": "success"
            })
            latency = getattr(trace, 'latency_seconds', 0)
            print(f"    ✓ {trace.total_tokens} tokens, {trace.total_tool_calls} tools, {latency:.1f}s")

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
            print(f"    ✗ ERROR: {e}")

    # Compute summary
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    total_tokens = sum(r.get("metrics", {}).get("total_tokens", 0) for r in results)
    total_tool_calls = sum(r.get("metrics", {}).get("tool_calls", 0) for r in results)
    total_latency = sum(r.get("metrics", {}).get("latency_seconds", 0) for r in results)

    summary = {
        "total_queries": len(results),
        "successful": success_count,
        "errors": error_count,
        "success_rate": round(success_count / len(results) * 100, 1) if results else 0,
        "total_tokens": total_tokens,
        "total_tool_calls": total_tool_calls,
        "total_latency_seconds": round(total_latency, 1),
        "avg_tokens_per_query": round(total_tokens / success_count, 1) if success_count else 0,
        "avg_tool_calls_per_query": round(total_tool_calls / success_count, 1) if success_count else 0,
        "avg_latency_seconds": round(total_latency / success_count, 1) if success_count else 0,
    }

    output = {
        "eval_file": str(eval_path),
        "label": label,
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "results": results
    }

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = RESULTS_DIR / f"eval_{label}_{timestamp}.json"

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(f"\n{'-'*40}")
    print("SUMMARY")
    print(f"{'-'*40}")
    print(f"  Queries: {summary['successful']}/{summary['total_queries']} successful")
    print(f"  Success rate: {summary['success_rate']}%")
    print(f"  Total tokens: {summary['total_tokens']:,}")
    print(f"  Avg tokens/query: {summary['avg_tokens_per_query']:,.1f}")
    print(f"  Avg tool calls/query: {summary['avg_tool_calls_per_query']:.1f}")
    print(f"  Avg latency: {summary['avg_latency_seconds']:.1f}s")
    print(f"\n  Saved: {output_path}")

    return output


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run evaluation queries through the agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python evaluate.py train          Run training set only
  python evaluate.py test           Run test set only  
  python evaluate.py train-test     Run train then test
  python evaluate.py --file custom.json   Run custom eval file
"""
    )
    
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["train", "test", "train-test"],
        help="Which evaluation set to run"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        help="Path to custom evaluation file"
    )
    
    args = parser.parse_args()
    
    # Determine what to run
    if args.file:
        run_evaluation(Path(args.file), label="custom")
    elif args.mode == "train":
        run_evaluation(EVALS_DIR / "train.json", label="train")
    elif args.mode == "test":
        run_evaluation(EVALS_DIR / "test.json", label="test")
    elif args.mode == "train-test":
        run_evaluation(EVALS_DIR / "train.json", label="train")
        run_evaluation(EVALS_DIR / "test.json", label="test")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
