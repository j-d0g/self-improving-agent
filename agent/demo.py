#!/usr/bin/env python3
"""
Demo Script for Financial Analysis Agent

This script demonstrates the agent's ability to answer financial questions.
"""

import sys
from pathlib import Path

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


def scripted_demo():
    """Run a scripted demo showing agent capabilities."""
    print_header("FINANCIAL ANALYSIS AGENT DEMO")
    print("""
This demo shows the agent answering financial questions about P&L data.

The agent:
1. Reads knowledge files to understand the data schema
2. Generates and executes pandas code via Bash
3. Validates results and provides clear answers
""")

    agent = FinancialAnalysisAgent()

    questions = [
        "What was the total Gross Revenue for Product A in Q1 2024?",
        "Which product had the highest Net Revenue in 2023?",
        "What was the year-over-year change in OPEX between 2022 and 2023?",
    ]

    for i, question in enumerate(questions, 1):
        print_subheader(f"Question {i}")
        print(f"Q: {question}")
        print("\nThinking...", end=" ", flush=True)

        result = agent.query(question)
        print("Done!\n")

        print("Answer:")
        print(result["answer"])

        trace = result["trace"]
        print(f"\n[Tokens: {trace.total_tokens}, Tool calls: {trace.total_tool_calls}]")

    print_header("DEMO COMPLETE")
    print("\nSession Metrics:")
    for k, v in agent.metrics.compute().items():
        print(f"  {k}: {v}")

    print("\nTo explore further, run: python agent.py")


def main():
    """Main entry point."""
    if len(sys.argv) > 1 and (sys.argv[1] == "--help" or sys.argv[1] == "-h"):
        print("""
Financial Analysis Agent Demo

Usage:
  python demo.py              Run the scripted demo

For interactive mode or single questions, use:
  python agent.py             Interactive mode
  python agent.py "question"  Ask a single question
""")
    else:
        scripted_demo()


if __name__ == "__main__":
    main()
