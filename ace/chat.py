#!/usr/bin/env python3
"""
ACE Interactive Chat

Interactive mode for querying P&L data with the ACE Solver.
Optionally runs Reflector in background for learning.

Usage:
    python chat.py              # Interactive mode
    python chat.py "query"      # Single query mode
"""

import asyncio
import sys
from pathlib import Path

from .solver import SolverAgent
from .reflector import Reflector

# Track background tasks
_background_tasks: set[asyncio.Task] = set()


async def run_background_reflect(reflector: Reflector, result) -> None:
    """Run Reflector in background."""
    try:
        await reflector.reflect(result)
    except Exception as e:
        print(f"\n[Reflector error: {e}]")


async def interactive_loop(solver: SolverAgent, reflector: Reflector | None = None):
    """Run interactive REPL loop."""
    print("ACE Interactive Chat")
    print("=" * 40)
    print("Commands:")
    print("  quit       - Exit")
    print("  metrics    - Show session stats")
    print()

    total_tokens = 0
    total_cost = 0.0
    query_count = 0

    while True:
        try:
            user_input = await asyncio.to_thread(input, "You: ")
            user_input = user_input.strip()

            if not user_input:
                continue

            if user_input.lower() == "quit":
                if _background_tasks:
                    print("\nWaiting for background tasks...")
                    await asyncio.gather(*_background_tasks, return_exceptions=True)
                print(f"\nSession: {query_count} queries, {total_tokens:,} tokens, ${total_cost:.4f}")
                break

            if user_input.lower() == "metrics":
                print(f"\nMetrics: {query_count} queries, {total_tokens:,} tokens, ${total_cost:.4f}")
                if _background_tasks:
                    print(f"Background tasks: {len(_background_tasks)}")
                print()
                continue

            # Run query
            print()
            result = await solver.solve(query=user_input)
            print()

            # Update stats
            query_count += 1
            total_tokens += result.total_tokens
            total_cost += result.total_cost_usd

            print(f"[{result.total_tokens} tokens, ${result.total_cost_usd:.4f}, {result.latency_seconds:.1f}s]")

            if result.bullet_ids_used:
                print(f"[Bullets used: {', '.join(result.bullet_ids_used)}]")

            # Run Reflector in background if enabled
            if reflector:
                task = asyncio.create_task(run_background_reflect(reflector, result))
                _background_tasks.add(task)
                task.add_done_callback(_background_tasks.discard)

            print("-" * 40)
            print()

        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except EOFError:
            break
        except Exception as e:
            print(f"\nError: {e}\n")


async def single_query(solver: SolverAgent, query: str):
    """Run a single query and exit."""
    result = await solver.solve(query=query)

    print()
    print("=" * 60)
    print("ANSWER:")
    print("=" * 60)
    print(result.answer)
    print()
    print("-" * 40)
    print(f"Tokens: {result.total_tokens}")
    print(f"Cost: ${result.total_cost_usd:.4f}")
    print(f"Latency: {result.latency_seconds:.1f}s")
    if result.bullet_ids_used:
        print(f"Bullets: {', '.join(result.bullet_ids_used)}")
    print("-" * 40)


async def main_async():
    solver = SolverAgent(stream_output=True)
    reflector = Reflector()  # Enable background learning

    if len(sys.argv) > 1:
        # Single query mode
        query = " ".join(sys.argv[1:])
        await single_query(solver, query)
    else:
        # Interactive mode
        await interactive_loop(solver, reflector)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
