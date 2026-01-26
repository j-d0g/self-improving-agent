#!/usr/bin/env python3
"""
ACE Interactive Agent

Interactive mode for the ACE pipeline with background learning.

Usage:
    python agent.py                          # Interactive mode
    python agent.py "What was Q1 revenue?"   # Single query
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ace.solver import SolverAgent, SolverResult
from ace.reflector import Reflector
from ace.curator import Curator

# Track background tasks for graceful shutdown
_background_tasks: set[asyncio.Task] = set()


async def wait_for_background_tasks(timeout: float = 60.0) -> None:
    """Wait for all background tasks to complete."""
    if not _background_tasks:
        return
    print(f"\nWaiting for {len(_background_tasks)} background task(s)...")
    try:
        await asyncio.wait_for(
            asyncio.gather(*_background_tasks, return_exceptions=True),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        print(f"Background tasks did not complete within {timeout}s")


class ACEAgent:
    """Interactive ACE agent with background learning."""

    # Curator runs after this many queries
    CURATOR_THRESHOLD = 5

    def __init__(
        self,
        enable_learning: bool = True,
        stream_output: bool = True,
    ):
        """Initialize the ACE agent.

        Args:
            enable_learning: Whether to run Reflector/Curator in background
            stream_output: Whether to print streaming output
        """
        self.solver = SolverAgent(stream_output=stream_output)
        self.reflector = Reflector()
        self.curator = Curator()
        self.enable_learning = enable_learning
        self.stream_output = stream_output

        # Track queries for curator threshold
        self.query_count = 0

    async def query(self, question: str, expected_answer: str | None = None) -> SolverResult:
        """Process a query with optional background learning.

        Args:
            question: The question to answer
            expected_answer: Optional ground truth for learning

        Returns:
            SolverResult with answer and metrics
        """
        # Run solver
        result = await self.solver.solve(
            query=question,
            expected_answer=expected_answer,
        )

        self.query_count += 1

        # Trigger background learning
        if self.enable_learning and expected_answer:
            task = asyncio.create_task(self._background_learn(result))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)

        return result

    async def _background_learn(self, solver_result: SolverResult) -> None:
        """Run Reflector in background, Curator after threshold."""
        try:
            # Run reflector
            reflector_result = await self.reflector.reflect(solver_result)

            if self.stream_output:
                status = "✓" if reflector_result.is_correct else "✗"
                print(f"\n[Learning] {status} {reflector_result.judge_reason[:50]}")

            # Run curator after threshold
            if self.query_count % self.CURATOR_THRESHOLD == 0:
                curator_result = await self.curator.curate()
                if self.stream_output and curator_result.operations:
                    print(f"[Curator] Applied {curator_result.operations_applied} operations")

        except Exception as e:
            if self.stream_output:
                print(f"\n[Learning] Error: {e}")


async def interactive_mode():
    """Run interactive REPL."""
    agent = ACEAgent(enable_learning=True, stream_output=True)

    print("ACE Interactive Agent")
    print("="*50)
    print("Pipeline: Solver → Reflector → Curator (background)")
    print()
    print("Commands:")
    print("  quit              - Exit (waits for background tasks)")
    print("  no-learn <query>  - Answer without learning")
    print()

    while True:
        try:
            question = (await asyncio.to_thread(input, "You: ")).strip()

            if not question:
                continue

            if question.lower() == "quit":
                await wait_for_background_tasks(timeout=30.0)
                print("Goodbye!")
                break

            # Check for no-learn prefix
            if question.lower().startswith("no-learn "):
                agent.enable_learning = False
                question = question[9:].strip()
            else:
                agent.enable_learning = True

            print()  # Newline before streaming
            result = await agent.query(question)
            print()  # Newline after streaming

            # Print metrics
            print(f"[Latency: {result.latency_seconds:.1f}s, "
                  f"Tokens: {result.total_tokens}, "
                  f"Cost: ${result.total_cost_usd:.4f}]")

            if result.bullet_ids_used:
                print(f"[Bullets used: {', '.join(result.bullet_ids_used)}]")

            if agent.enable_learning and _background_tasks:
                print("[Learning in background...]")

            print("-"*40 + "\n")

        except KeyboardInterrupt:
            print("\nExiting...")
            await wait_for_background_tasks(timeout=10.0)
            break
        except Exception as e:
            print(f"\nError: {e}\n")


async def single_query_mode(question: str):
    """Run a single query and exit."""
    agent = ACEAgent(enable_learning=False, stream_output=True)

    result = await agent.query(question)

    print("\n" + "="*60)
    print("ANSWER:")
    print("="*60)
    print(result.answer)

    print("\n" + "-"*40)
    print("METRICS:")
    print(f"  Latency: {result.latency_seconds:.1f}s")
    print(f"  Tokens: {result.total_tokens}")
    print(f"  Cost: ${result.total_cost_usd:.4f}")
    if result.bullet_ids_used:
        print(f"  Bullets used: {', '.join(result.bullet_ids_used)}")
    print("-"*40)


async def main_async():
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        await single_query_mode(question)
    else:
        await interactive_mode()


def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
