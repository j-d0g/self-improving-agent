#!/usr/bin/env python3
"""
Demo Script for Financial Analysis Agent

This script demonstrates the agent's ability to answer financial questions.
"""

import os
import sys
from pathlib import Path

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


def interactive_mode(agent: FinancialAnalysisAgent):
    """Run in interactive mode."""
    print_header("Interactive Mode")
    print("""
Commands:
  - Type your question to ask the agent
  - 'metrics' - Show session metrics
  - 'quit' - Exit the demo
""")

    while True:
        try:
            user_input = input("\nYour question: ").strip()

            if not user_input:
                continue
            elif user_input.lower() == "quit":
                if agent.metrics.traces:
                    print_subheader("Session Metrics")
                    for k, v in agent.metrics.compute().items():
                        print(f"  {k}: {v}")
                print("Goodbye!")
                break
            elif user_input.lower() == "metrics":
                if agent.metrics.traces:
                    print_subheader("Session Metrics")
                    for k, v in agent.metrics.compute().items():
                        print(f"  {k}: {v}")
                else:
                    print("No queries yet.")
            else:
                print("Thinking...", end=" ", flush=True)
                result = agent.query(user_input)
                print("Done!\n")
                print("Answer:")
                print(result["answer"])

                # Show trace info
                trace = result["trace"]
                print(f"\n[Tokens: {trace.total_tokens}, Tool calls: {trace.total_tool_calls}]")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")


def scripted_demo():
    """Run a scripted demo showing agent capabilities."""
    print_header("FINANCIAL ANALYSIS AGENT DEMO")
    print("""
This demo shows the agent answering financial questions about P&L data.

The agent:
1. Reads the dataset schema to understand column definitions
2. Generates pandas code to answer your question
3. Validates results with programmatic verification
4. Recovers from errors automatically
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

    print("\nTo explore further, run: python demo.py -i")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--interactive" or sys.argv[1] == "-i":
            agent = FinancialAnalysisAgent()
            interactive_mode(agent)
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("""
Financial Analysis Agent Demo

Usage:
  python demo.py              Run the scripted demo
  python demo.py -i           Interactive mode
  python demo.py --help       Show this help message
  python demo.py <question>   Ask a single question
""")
        else:
            # Treat as a question
            agent = FinancialAnalysisAgent()
            question = " ".join(sys.argv[1:])
            result = agent.query(question)
            print(result["answer"])
    else:
        scripted_demo()


if __name__ == "__main__":
    main()
