"""
Self-Improving Agent Orchestrator

Uses Claude Agent SDK with programmatic subagents (AgentDefinition) to coordinate:
- learner: Answers financial queries, writes session logs
- evaluator: Analyzes session logs, suggests improvements
- improver: Applies improvements to knowledge base

Architecture based on: https://platform.claude.com/docs/en/agent-sdk/overview
"""

import asyncio
from pathlib import Path
from datetime import datetime

from claude_agent_sdk import (
    query,
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AgentDefinition,
    AssistantMessage,
    ResultMessage,
    TextBlock,
)

from prompts import load_prompt

PROJECT_ROOT = Path(__file__).parent


# ============================================================
# AGENT DEFINITIONS
# ============================================================

def get_agents() -> dict[str, AgentDefinition]:
    """Define programmatic subagents."""
    return {
        "learner": AgentDefinition(
            description="Data analysis agent for P&L financial queries. Answers questions about revenue, costs, margins using pandas. Writes detailed session logs with self-reflection to logs/sessions/.",
            prompt=load_prompt("financial_agent.txt"),
            tools=["Read", "Write", "Bash", "Grep", "Glob"]
        ),
        "evaluator": AgentDefinition(
            description="Expert analyst that reviews session logs for patterns, inefficiencies, and errors. Identifies root causes and suggests concrete improvements to knowledge/. Writes evaluations to logs/evaluations/.",
            prompt=load_prompt("evaluator.txt"),
            tools=["Read", "Write", "Grep", "Glob"]
        ),
        "improver": AgentDefinition(
            description="Applies approved improvements from evaluator to knowledge files (schema.md, examples.md, functions.py). Writes improvement reports to logs/improvements/.",
            prompt=load_prompt("improver.txt"),
            tools=["Read", "Write", "Edit", "Grep", "Glob"]
        ),
    }


ORCHESTRATOR_PROMPT = """You are an orchestrator for a self-improving financial analysis system.

## Available Agents

You can delegate to these specialized agents using the Task tool:

1. **learner** - Answers financial queries
   - Use for: Any data analysis question about P&L data
   - Writes session logs with self-reflection to logs/sessions/

2. **evaluator** - Analyzes session logs
   - Use for: Reviewing recent query sessions for patterns and issues
   - Writes evaluation reports to logs/evaluations/

3. **improver** - Updates knowledge base
   - Use for: Applying recommended improvements from evaluator
   - Modifies files in knowledge/

## Your Process

**For regular queries:**
1. Delegate to learner agent with the user's question
2. Return the answer to the user

**For "improve" or "self-improve" commands:**
1. Call evaluator to analyze recent sessions in logs/sessions/
2. Call improver to apply the recommended changes
3. Report what was improved

**For "evaluate" command:**
1. Just call evaluator to analyze recent sessions
2. Report findings without applying changes

Be concise. Pass through the learner's answer directly to the user.
"""


# ============================================================
# ORCHESTRATOR
# ============================================================

async def run_query(question: str, auto_improve: bool = False) -> str:
    """Run a query through the orchestrator."""
    
    agents = get_agents()
    
    options = ClaudeAgentOptions(
        system_prompt=ORCHESTRATOR_PROMPT,
        cwd=str(PROJECT_ROOT),
        agents=agents,
        allowed_tools=["Task", "Read", "Grep", "Glob"],  # Task for spawning subagents
        max_turns=30,
    )
    
    prompt = question
    if auto_improve:
        prompt += "\n\nAfter answering, also run the evaluator on recent sessions and apply any improvements."
    
    result = ""
    cost = 0.0
    
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        result = block.text
                        print(block.text)
            elif isinstance(message, ResultMessage):
                cost = getattr(message, 'total_cost_usd', 0) or 0
    
    return result


async def interactive_mode():
    """Interactive REPL mode."""
    print("\n" + "="*60)
    print("Self-Improving Agent Orchestrator")
    print("="*60)
    print("Using Claude Agent SDK with AgentDefinition")
    print()
    print("Commands:")
    print("  quit      - Exit")
    print("  auto      - Toggle auto-improve mode")
    print("  improve   - Run evaluator + improver on recent sessions")
    print("  evaluate  - Run evaluator only (no changes)")
    print()
    
    auto_improve = False
    
    while True:
        try:
            mode_indicator = " [auto-improve]" if auto_improve else ""
            question = input(f"You{mode_indicator}: ").strip()
            
            if not question:
                continue
            if question.lower() == 'quit':
                break
            if question.lower() == 'auto':
                auto_improve = not auto_improve
                print(f"Auto-improve: {'ON' if auto_improve else 'OFF'}")
                continue
            
            print("\nThinking...\n")
            await run_query(question, auto_improve)
            print()
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


def main():
    import sys
    
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"\nQuery: {question}\n")
        asyncio.run(run_query(question))
    else:
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
