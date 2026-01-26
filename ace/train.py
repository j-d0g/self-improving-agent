#!/usr/bin/env python3
"""
ACE Training CLI

Train the ACE pipeline on P&L queries with self-improvement.

Usage:
    python train.py                     # Default: 3 epochs, batch_size=4
    python train.py --epochs 1 -q       # Quick test
    python train.py --no-improve        # Baseline (no Curator)
"""

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ace.orchestrator import BatchOrchestrator, load_queries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train the ACE pipeline on P&L queries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python train.py                     # 3 epochs with learning
  python train.py --epochs 1 -q       # Quick test, quiet mode
  python train.py --no-improve        # Baseline without Curator
  python train.py --batch-size 2      # Smaller batches
        """,
    )

    parser.add_argument(
        "--epochs",
        type=int,
        default=3,
        help="Number of training epochs (default: 3)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Queries per batch (default: 4)",
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help="Disable Curator and Aggregator (no learning)",
    )
    parser.add_argument(
        "--no-aggregator",
        action="store_true",
        help="Disable Aggregator only (keep Curator)",
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Minimal output (disable streaming)",
    )
    parser.add_argument(
        "--train-file",
        type=Path,
        default=None,
        help="Custom training queries JSON file",
    )
    parser.add_argument(
        "--test-file",
        type=Path,
        default=None,
        help="Custom validation queries JSON file",
    )
    parser.add_argument(
        "--train-size",
        type=int,
        default=None,
        help="Cap training set to N randomly sampled queries",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )

    return parser.parse_args()


async def main_async():
    args = parse_args()

    ace_root = Path(__file__).parent
    agent_root = ace_root.parent / "agent"

    # Load queries
    train_path = args.train_file or agent_root / "evals" / "train.json"
    test_path = args.test_file or agent_root / "evals" / "test.json"

    if not train_path.exists():
        print(f"Error: Training file not found: {train_path}")
        sys.exit(1)
    if not test_path.exists():
        print(f"Error: Test file not found: {test_path}")
        sys.exit(1)

    train_queries = load_queries(train_path)
    validation_queries = load_queries(test_path)
    original_train_size = len(train_queries)

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)

    # Subsample training set if requested
    if args.train_size and args.train_size < len(train_queries):
        train_queries = random.sample(train_queries, args.train_size)

    if not args.quiet:
        print("="*60)
        print("ACE Training")
        print("="*60)
        train_info = f"{len(train_queries)} from {train_path.name}"
        if args.train_size and args.train_size < original_train_size:
            train_info += f" (sampled from {original_train_size})"
        print(f"Training queries: {train_info}")
        print(f"Validation queries: {len(validation_queries)} from {test_path.name}")
        if args.seed is not None:
            print(f"Random seed: {args.seed}")
        print(f"Epochs: {args.epochs}")
        print(f"Batch size: {args.batch_size}")
        print(f"Curator: {'disabled' if args.baseline else 'enabled'}")
        print(f"Aggregator: {'disabled' if args.baseline or args.no_aggregator else 'enabled'}")
        print()

    # Create orchestrator
    orchestrator = BatchOrchestrator(
        run_curator=not args.baseline,
        run_aggregator=not args.baseline and not args.no_aggregator,
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
    print("TRAINING SUMMARY")
    print("="*60)
    print(f"Run ID: {run.run_id}")
    print(f"Final train accuracy: {run.final_train_accuracy:.1%}")
    print(f"Final validation accuracy: {run.final_validation_accuracy:.1%}")
    print(f"Total tokens: {run.total_tokens:,}")
    print(f"Total cost: ${run.total_cost_usd:.4f}")
    print()

    # Show epoch progression
    if len(run.epochs) > 1:
        print("Epoch progression:")
        for epoch in run.epochs:
            print(f"  Epoch {epoch.epoch}: train={epoch.train_accuracy:.1%} val={epoch.validation_accuracy:.1%}")

    return 0


def main():
    try:
        sys.exit(asyncio.run(main_async()))
    except KeyboardInterrupt:
        print("\nTraining interrupted.")
        sys.exit(1)


if __name__ == "__main__":
    main()
