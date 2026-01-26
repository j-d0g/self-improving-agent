#!/usr/bin/env python3
"""
ACE Benchmark CLI

Run benchmarks, compare runs, and generate dashboards.

Usage:
    python benchmark.py run                    # Default benchmark
    python benchmark.py run --epochs 1 -q     # Quick test
    python benchmark.py run --no-improve      # Baseline
    python benchmark.py list                  # List all runs
    python benchmark.py compare <run1> <run2> # Compare two runs
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ace.orchestrator import BatchOrchestrator, load_queries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ACE benchmark suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run benchmark")
    run_parser.add_argument("--epochs", type=int, default=3, help="Number of epochs")
    run_parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    run_parser.add_argument("--no-improve", action="store_true", help="Disable learning")
    run_parser.add_argument("-q", "--quiet", action="store_true", help="Minimal output")

    # List command
    subparsers.add_parser("list", help="List all runs")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two runs")
    compare_parser.add_argument("run1", help="First run ID")
    compare_parser.add_argument("run2", help="Second run ID")

    return parser.parse_args()


def get_runs_dir() -> Path:
    return Path(__file__).parent.parent / "logs" / "training"


def list_runs() -> list[dict]:
    """List all benchmark runs."""
    runs_dir = get_runs_dir()
    if not runs_dir.exists():
        return []

    runs = []
    for run_file in sorted(runs_dir.glob("run_*.json")):
        try:
            with open(run_file) as f:
                data = json.load(f)
                runs.append({
                    "run_id": data.get("run_id", run_file.stem),
                    "start_time": data.get("start_time", ""),
                    "epochs": data.get("num_epochs", 0),
                    "train_acc": data.get("final_train_accuracy", 0),
                    "val_acc": data.get("final_validation_accuracy", 0),
                    "tokens": data.get("total_tokens", 0),
                    "cost": data.get("total_cost_usd", 0),
                })
        except Exception:
            continue

    return runs


def cmd_list():
    """List all runs."""
    runs = list_runs()

    if not runs:
        print("No runs found.")
        return

    print(f"\n{'Run ID':<25} {'Date':<12} {'Epochs':<8} {'Train':<8} {'Val':<8} {'Tokens':<10} {'Cost':<8}")
    print("-"*90)

    for r in runs:
        date = r["start_time"][:10] if r["start_time"] else "N/A"
        print(f"{r['run_id']:<25} {date:<12} {r['epochs']:<8} "
              f"{r['train_acc']:.1%}   {r['val_acc']:.1%}   "
              f"{r['tokens']:<10,} ${r['cost']:.4f}")

    print()


def cmd_compare(run1_id: str, run2_id: str):
    """Compare two runs."""
    runs_dir = get_runs_dir()

    # Find run files
    run1_file = runs_dir / f"{run1_id}.json"
    run2_file = runs_dir / f"{run2_id}.json"

    # Try with run_ prefix if not found
    if not run1_file.exists():
        run1_file = runs_dir / f"run_{run1_id}.json"
    if not run2_file.exists():
        run2_file = runs_dir / f"run_{run2_id}.json"

    if not run1_file.exists():
        print(f"Run not found: {run1_id}")
        return
    if not run2_file.exists():
        print(f"Run not found: {run2_id}")
        return

    with open(run1_file) as f:
        r1 = json.load(f)
    with open(run2_file) as f:
        r2 = json.load(f)

    print(f"\nComparing {run1_id} vs {run2_id}")
    print("="*60)

    metrics = [
        ("Train Accuracy", "final_train_accuracy", ".1%"),
        ("Validation Accuracy", "final_validation_accuracy", ".1%"),
        ("Total Tokens", "total_tokens", ",d"),
        ("Total Cost", "total_cost_usd", ".4f"),
    ]

    for label, key, fmt in metrics:
        v1 = r1.get(key, 0)
        v2 = r2.get(key, 0)
        diff = v2 - v1

        if fmt == ".1%":
            print(f"{label:<25} {v1:{fmt}} → {v2:{fmt}} ({diff:+.1%})")
        elif fmt == ".4f":
            print(f"{label:<25} ${v1:{fmt}} → ${v2:{fmt}} (${diff:+.4f})")
        else:
            print(f"{label:<25} {v1:{fmt}} → {v2:{fmt}} ({diff:+,d})")

    print()


async def cmd_run(args):
    """Run benchmark."""
    ace_root = Path(__file__).parent.parent
    agent_root = ace_root.parent / "agent"

    # Load queries
    train_path = agent_root / "evals" / "train.json"
    test_path = agent_root / "evals" / "test.json"

    if not train_path.exists() or not test_path.exists():
        print("Error: Query files not found in agent/evals/")
        return

    train_queries = load_queries(train_path)
    validation_queries = load_queries(test_path)

    # Create orchestrator
    orchestrator = BatchOrchestrator(
        run_curator=not args.no_improve,
        stream_output=not args.quiet,
    )

    # Run training
    run = await orchestrator.train(
        train_queries=train_queries,
        validation_queries=validation_queries,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
    )

    # Print summary
    print()
    print("="*60)
    print("BENCHMARK COMPLETE")
    print("="*60)
    print(f"Run ID: {run.run_id}")
    print(f"Final train accuracy: {run.final_train_accuracy:.1%}")
    print(f"Final validation accuracy: {run.final_validation_accuracy:.1%}")
    print(f"Total tokens: {run.total_tokens:,}")
    print(f"Total cost: ${run.total_cost_usd:.4f}")
    print()

    # Show learning curve if multiple epochs
    if len(run.epochs) > 1:
        print("Learning Curve:")
        for epoch in run.epochs:
            bar_train = "█" * int(epoch.train_accuracy * 20)
            bar_val = "█" * int(epoch.validation_accuracy * 20)
            print(f"  Epoch {epoch.epoch}: train {bar_train:<20} {epoch.train_accuracy:.0%}")
            print(f"          val   {bar_val:<20} {epoch.validation_accuracy:.0%}")


def main():
    args = parse_args()

    if args.command == "list":
        cmd_list()
    elif args.command == "compare":
        cmd_compare(args.run1, args.run2)
    elif args.command == "run":
        asyncio.run(cmd_run(args))
    else:
        print("Usage: python benchmark.py {run|list|compare} [options]")
        print("Use --help for more information.")


if __name__ == "__main__":
    main()
