#!/usr/bin/env python3
"""
Cross-Session Learning Demo

Demonstrates the agent's ability to learn from mistakes and apply
learnings across sessions.

Flow:
1. Session 1: Query with error-prone pattern → agent fails, learns, recovers
2. Session 2: Reset agent → similar query succeeds without error
3. Show diff of knowledge files
"""

import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent import FinancialAnalysisAgent


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f" {text}")
    print("=" * 60)


def print_subheader(text: str):
    """Print a formatted subheader."""
    print("\n" + "-" * 40)
    print(f" {text}")
    print("-" * 40)


def read_knowledge_file(path: str) -> str:
    """Read a knowledge file and return its contents."""
    file_path = Path(__file__).parent / path
    if file_path.exists():
        return file_path.read_text()
    return ""


def show_knowledge_diff(before: dict, after: dict):
    """Show what changed in knowledge files."""
    print_subheader("Knowledge Files Changes")

    for name, old_content in before.items():
        new_content = after.get(name, "")
        if new_content != old_content:
            print(f"\n{name}:")
            # Show new lines added
            old_lines = set(old_content.split("\n"))
            new_lines = new_content.split("\n")
            added = [line for line in new_lines if line and line not in old_lines]
            if added:
                print("  + " + "\n  + ".join(added[:10]))  # Limit output
                if len(added) > 10:
                    print(f"  ... and {len(added) - 10} more lines")
        else:
            print(f"\n{name}: (no changes)")


def run_learning_demo():
    """Run the cross-session learning demonstration."""
    print_header("CROSS-SESSION LEARNING DEMO")
    print("""
This demo shows the agent learning from mistakes and applying
that knowledge in future sessions.
""")

    # Capture initial state of knowledge files
    knowledge_files = [
        "knowledge/examples.md",
        "knowledge/improvements.md",
        "knowledge/functions.py"
    ]
    before_knowledge = {f: read_knowledge_file(f) for f in knowledge_files}

    # Session 1: Trigger a learning opportunity
    print_subheader("Session 1: Error-Prone Query")
    print("Query: 'What was the total revenue for Product E in Q1 2024?'")
    print("\nThis query references Product E, which doesn't exist.")
    print("The agent should detect this, handle it gracefully, and learn.\n")

    agent1 = FinancialAnalysisAgent()
    print("Running query...")
    result1 = agent1.query("What was the total revenue for Product E in Q1 2024?")

    print("\nAnswer:")
    print(result1["answer"][:500] + "..." if len(result1["answer"]) > 500 else result1["answer"])

    trace1 = result1["trace"]
    print(f"\nMetrics:")
    print(f"  Tool calls: {trace1.total_tool_calls}")
    print(f"  Errors encountered: {len(trace1.errors_encountered)}")
    print(f"  Error recovered: {trace1.error_recovered}")
    print(f"  Learning triggered: {trace1.learning_triggered}")

    # Check for changes in knowledge files
    after_knowledge_s1 = {f: read_knowledge_file(f) for f in knowledge_files}

    # Session 2: Similar query with new agent instance
    print_subheader("Session 2: New Agent, Similar Query")
    print("Query: 'What was the revenue for Product Z in 2023?'")
    print("\nThis is a fresh agent instance (simulating a new session).")
    print("If learning was persisted, the agent should immediately recognize")
    print("the invalid product without needing error recovery.\n")

    agent2 = FinancialAnalysisAgent()
    print("Running query...")
    result2 = agent2.query("What was the revenue for Product Z in 2023?")

    print("\nAnswer:")
    print(result2["answer"][:500] + "..." if len(result2["answer"]) > 500 else result2["answer"])

    trace2 = result2["trace"]
    print(f"\nMetrics:")
    print(f"  Tool calls: {trace2.total_tool_calls}")
    print(f"  Errors encountered: {len(trace2.errors_encountered)}")
    print(f"  Error recovered: {trace2.error_recovered}")

    # Show knowledge file changes
    after_knowledge_s2 = {f: read_knowledge_file(f) for f in knowledge_files}
    show_knowledge_diff(before_knowledge, after_knowledge_s2)

    # Summary
    print_header("DEMO SUMMARY")
    print("""
What happened:
1. Session 1: Agent received a query about non-existent Product E
   - It read the dataset schema which lists valid products
   - It detected the issue and informed the user
   - (If learning triggered) It persisted this pattern to knowledge files

2. Session 2: Fresh agent instance received similar invalid query
   - It loaded the knowledge files at startup (via system prompt)
   - It recognized the pattern and handled it efficiently

Key insight: Learning happens through file persistence, not in-memory state.
New agent instances can benefit from previous sessions' learnings.
""")

    # Compare efficiency
    if trace1.total_tool_calls > trace2.total_tool_calls:
        print(f"Session 2 used {trace1.total_tool_calls - trace2.total_tool_calls} fewer tool calls!")
    print(f"\nSession 1 tokens: {trace1.total_tokens}")
    print(f"Session 2 tokens: {trace2.total_tokens}")


def main():
    """CLI entry point."""
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help"]:
        print("""
Cross-Session Learning Demo

Usage:
  python learning_demo.py

This demo:
1. Runs a query that triggers an error (non-existent product)
2. Shows how the agent handles and learns from the error
3. Creates a new agent instance (new session)
4. Runs a similar query to show learning applied
5. Shows changes to knowledge files
""")
        sys.exit(0)

    run_learning_demo()


if __name__ == "__main__":
    main()
