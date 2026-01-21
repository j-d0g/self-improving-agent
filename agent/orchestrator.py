"""
Self-Improving Agent Orchestrator

Uses Claude Agent SDK with programmatic subagents (AgentDefinition) to coordinate:
- learner: Answers financial queries, writes session logs
- evaluator: Analyzes session logs, suggests improvements
- improver: Applies improvements to knowledge base

Architecture based on: https://platform.claude.com/docs/en/agent-sdk/overview
"""

import asyncio
import json
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
    ToolUseBlock,
    ToolResultBlock,
)

from prompts import load_prompt
from tracing import ExecutionTrace, AgentMetrics

PROJECT_ROOT = Path(__file__).parent

# Model configuration - single source of truth
AGENT_MODEL = "claude-sonnet-4-20250514"


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


ORCHESTRATOR_PROMPT = """You are a self-improving financial analysis system that learns from every query.

## Available Agents

You have three specialized agents (use via Task tool):

1. **learner** - Answers financial queries using pandas
   - Writes session logs with self-reflection to logs/sessions/

2. **evaluator** - Critiques session logs for correctness and efficiency
   - Writes evaluation reports to logs/evaluations/

3. **improver** - Applies improvements to knowledge base
   - Updates files in knowledge/

## Automatic Improvement Loop

For EVERY user query, run this pipeline automatically:

1. **Learner phase**: Delegate the question to the learner agent
2. **Evaluation phase**: Once learner completes, use evaluator to critique the session log
3. **Improvement phase**: If evaluator finds actionable improvements, use improver to apply them
4. **Response**: Return the learner's answer to the user

This loop runs on every query - no user action required.

## Special Commands

- **"evaluate only"** - Run evaluator on recent sessions without applying changes
- **"improve only"** - Run evaluator + improver without answering a query
- **"skip improvement"** - Answer query with learner only, skip evaluation/improvement

## Output Format

After the full loop completes, respond with:
1. The answer to the user's question (from learner)
2. Brief note if any improvements were applied (optional)

Be concise. The user cares about the answer, not the improvement process details.
"""


# ============================================================
# ORCHESTRATOR
# ============================================================

# Global metrics tracker for the session
_session_metrics = AgentMetrics()


def get_session_metrics() -> AgentMetrics:
    """Get the current session metrics."""
    return _session_metrics


async def run_query(question: str, log_traces: bool = True) -> dict:
    """
    Run a query through the self-improving orchestrator.

    The orchestrator automatically runs: learner → evaluator → improver
    for every query (unless special commands like "skip improvement" are used).

    Args:
        question: The query to run
        log_traces: If True, save execution traces to logs/traces/

    Returns:
        dict with answer, trace, and optional log_path
    """
    agents = get_agents()

    options = ClaudeAgentOptions(
        model=AGENT_MODEL,
        system_prompt=ORCHESTRATOR_PROMPT,
        cwd=str(PROJECT_ROOT),
        agents=agents,
        allowed_tools=["Task", "Read", "Grep", "Glob"],  # Task for spawning subagents
        max_turns=50,  # Increased for full improvement loop
    )

    prompt = question

    # Initialize tracing
    trace = ExecutionTrace(query=question)
    current_turn = {"thinking": "", "tool_calls": []}
    result = ""

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        current_turn["thinking"] += block.text + "\n"
                        result = block.text
                        print(block.text)
                    elif isinstance(block, ToolUseBlock):
                        # Track tool usage
                        trace.total_tool_calls += 1
                        current_turn["tool_calls"].append({
                            "tool": block.name,
                            "input": str(block.input)[:500],  # Truncate long inputs
                        })
            elif isinstance(message, ResultMessage):
                # Capture metrics from result
                if hasattr(message, 'usage') and message.usage:
                    trace.input_tokens = message.usage.get('input_tokens', 0)
                    trace.output_tokens = message.usage.get('output_tokens', 0)
                    trace.total_tokens = trace.input_tokens + trace.output_tokens
                if hasattr(message, 'total_cost_usd') and message.total_cost_usd:
                    trace.total_cost_usd = message.total_cost_usd

    # Finalize turn
    current_turn["thinking"] = current_turn["thinking"].strip()
    if current_turn["thinking"] or current_turn["tool_calls"]:
        trace.turns.append(current_turn)

    trace.final_answer = result

    # Add to session metrics
    _session_metrics.add_trace(trace)

    # Save trace if logging enabled
    log_path = None
    if log_traces:
        traces_dir = PROJECT_ROOT / "logs" / "traces"
        traces_dir.mkdir(parents=True, exist_ok=True)
        log_path = _session_metrics.save_trace(trace, traces_dir)

    return {
        "answer": result,
        "trace": trace,
        "log_path": log_path
    }


async def interactive_mode():
    """Interactive REPL mode."""
    print("\n" + "="*60)
    print("Self-Improving Financial Analysis Agent")
    print("="*60)
    print("Every query runs: learner → evaluator → improver")
    print()
    print("Commands:")
    print("  quit            - Exit (shows session metrics)")
    print("  metrics         - Show session metrics")
    print("  evaluate only   - Run evaluator on recent sessions (no changes)")
    print("  improve only    - Run evaluator + improver (no query)")
    print("  skip improvement <query> - Answer without improvement loop")
    print()

    while True:
        try:
            question = input("You: ").strip()

            if not question:
                continue
            if question.lower() == 'quit':
                # Show session metrics on exit
                metrics = get_session_metrics()
                if metrics.traces:
                    print("\n" + "="*40)
                    print("SESSION METRICS:")
                    for k, v in metrics.compute().items():
                        print(f"  {k}: {v}")
                break
            if question.lower() == 'metrics':
                metrics = get_session_metrics()
                if metrics.traces:
                    print("\nMETRICS:")
                    for k, v in metrics.compute().items():
                        print(f"  {k}: {v}")
                else:
                    print("No queries yet.")
                continue

            print("\nRunning improvement loop...\n")
            result = await run_query(question)

            # Show metrics for this query
            trace = result["trace"]
            print(f"\n[Tokens: {trace.total_tokens}, Tool calls: {trace.total_tool_calls}, Cost: ${trace.total_cost_usd:.4f}]")
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
        print(f"\nQuery: {question}")
        print("Running improvement loop: learner → evaluator → improver\n")
        result = asyncio.run(run_query(question))

        # Show summary
        trace = result["trace"]
        print("\n" + "-"*40)
        print("METRICS:")
        print(f"  Tokens: {trace.total_tokens} (in: {trace.input_tokens}, out: {trace.output_tokens})")
        print(f"  Tool calls: {trace.total_tool_calls}")
        print(f"  Cost: ${trace.total_cost_usd:.4f}")
        if result.get("log_path"):
            print(f"  Trace: {result['log_path']}")
        print("-"*40)
    else:
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
