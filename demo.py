#!/usr/bin/env python3
"""
Demo Script for Self-Improving Financial Analysis Agent

This script demonstrates the cross-session learning capabilities of the agent.
Run it multiple times to see how the agent improves over sessions.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agent import SelfImprovingAgent


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


def show_learned_files(project_root: Path):
    """Display the contents of learned knowledge files."""
    print_subheader("Current Learned Knowledge")

    functions_path = project_root / "knowledge" / "learned" / "functions.py"
    guidelines_path = project_root / "knowledge" / "learned" / "guidelines.md"

    print("\n📁 knowledge/learned/functions.py:")
    print("-" * 30)
    content = functions_path.read_text()
    # Show only the learned part (after the marker)
    if "# ---LEARNING_MARKER---" in content:
        learned_part = content.split("# ---LEARNING_MARKER---")[1].strip()
        if learned_part:
            print(learned_part)
        else:
            print("(No functions learned yet)")
    print()

    print("📁 knowledge/learned/guidelines.md:")
    print("-" * 30)
    content = guidelines_path.read_text()
    if "<!-- ---LEARNING_MARKER--- -->" in content:
        learned_part = content.split("<!-- ---LEARNING_MARKER--- -->")[1].strip()
        if learned_part:
            print(learned_part)
        else:
            print("(No guidelines learned yet)")
    print()


def demo_session(agent: SelfImprovingAgent, session_num: int, questions: list[str]):
    """Run a demo session with given questions."""
    print_header(f"SESSION {session_num}")

    for i, question in enumerate(questions, 1):
        print(f"\n🔹 Question {i}: {question}")
        print("Thinking...", end=" ", flush=True)

        result = agent.query(question)

        print("Done!\n")
        print("📊 Answer:")
        print(result["answer"])

        if result["code_executed"]:
            print("\n💻 Code executed:")
            for code in result["code_executed"]:
                print(f"```python\n{code}\n```")

        if result["learned"]:
            print("\n✨ Agent learned something and persisted it!")


def interactive_mode(agent: SelfImprovingAgent):
    """Run in interactive mode."""
    print_header("Interactive Mode")
    print("""
Commands:
  - Type your question to ask the agent
  - 'show' - Show current learned knowledge
  - 'reset' - Reset all learned knowledge
  - 'quit' - Exit the demo
""")

    project_root = Path(__file__).parent

    while True:
        try:
            user_input = input("\n🔹 Your question: ").strip()

            if not user_input:
                continue
            elif user_input.lower() == "quit":
                print("Goodbye!")
                break
            elif user_input.lower() == "show":
                show_learned_files(project_root)
            elif user_input.lower() == "reset":
                agent.reset_learnings()
                print("✨ All learnings have been reset.")
            else:
                print("Thinking...", end=" ", flush=True)
                result = agent.query(user_input)
                print("Done!\n")
                print("📊 Answer:")
                print(result["answer"])

                if result["learned"]:
                    print("\n✨ Agent learned something and persisted it!")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


def scripted_demo():
    """Run a scripted demo showing cross-session learning."""
    project_root = Path(__file__).parent

    print_header("SELF-IMPROVING FINANCIAL ANALYSIS AGENT DEMO")
    print("""
This demo shows how the agent learns across sessions.

We'll demonstrate:
1. Agent making a mistake and learning from it
2. Agent persisting that learning to files
3. A "new session" (fresh agent) using the learned knowledge
""")

    # Session 1: Make a mistake and learn
    print_header("SIMULATING SESSION 1 - Agent Learns From Mistake")
    agent1 = SelfImprovingAgent()
    agent1.reset_learnings()  # Start fresh

    print("\nStarting with clean slate (no learned knowledge)...")
    show_learned_files(project_root)

    # Ask a question that might trip up the agent
    question1 = "What was the total Gross Revenue for Product A in Q1 2024?"

    print(f"\n🔹 Question: {question1}")
    print("Thinking...", end=" ", flush=True)
    result1 = agent1.query(question1)
    print("Done!\n")
    print("📊 Answer:")
    print(result1["answer"])

    if result1["learned"]:
        print("\n✨ Agent learned something!")
        show_learned_files(project_root)

    # Session 2: Fresh agent uses learned knowledge
    print_header("SIMULATING SESSION 2 - Fresh Agent Uses Learned Knowledge")
    print("\nCreating a NEW agent instance (simulating a new session)...")

    agent2 = SelfImprovingAgent()  # Fresh instance

    # Ask a similar question
    question2 = "What was the total Gross Revenue for Product B in Q2 2023?"

    print(f"\n🔹 Question: {question2}")
    print("Thinking...", end=" ", flush=True)
    result2 = agent2.query(question2)
    print("Done!\n")
    print("📊 Answer:")
    print(result2["answer"])

    print_header("DEMO COMPLETE")
    print("""
Key Observations:
- The agent can read and use knowledge from previous sessions
- Helper functions in knowledge/learned/functions.py are available to the agent
- Guidelines in knowledge/learned/guidelines.md inform the agent's approach
- This creates genuine cross-session improvement!

To explore further, run: python demo.py --interactive
""")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--interactive" or sys.argv[1] == "-i":
            agent = SelfImprovingAgent()
            interactive_mode(agent)
        elif sys.argv[1] == "--reset":
            agent = SelfImprovingAgent()
            agent.reset_learnings()
            print("All learnings have been reset.")
        elif sys.argv[1] == "--show":
            show_learned_files(Path(__file__).parent)
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("""
Self-Improving Financial Analysis Agent Demo

Usage:
  python demo.py              Run the scripted demo
  python demo.py -i           Interactive mode
  python demo.py --reset      Reset all learned knowledge
  python demo.py --show       Show current learned knowledge
  python demo.py --help       Show this help message
""")
        else:
            # Treat as a question
            agent = SelfImprovingAgent()
            question = " ".join(sys.argv[1:])
            result = agent.query(question)
            print(result["answer"])
    else:
        scripted_demo()


if __name__ == "__main__":
    main()
