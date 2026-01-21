"""
Financial Analysis Agent

A coding agent that answers financial questions about P&L data using the Claude Code SDK.
Uses SDK's built-in tools (Bash, Read) for execution.
"""

from pathlib import Path
import asyncio

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from claude_code_sdk import (
    query,
    ClaudeCodeOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from tracing import ExecutionTrace, AgentMetrics
from prompts import load_prompt


class FinancialAnalysisAgent:
    """Financial analysis agent with full logging."""

    def __init__(self, dataset_path: str = "data/FUN_company_pl_actuals_dataset.csv", log_traces: bool = True):
        """Initialize the agent."""
        self.project_root = Path(__file__).parent
        self.dataset_path = self.project_root / dataset_path
        self.traces_dir = self.project_root / "logs"
        self.log_traces = log_traces

        # Load system prompt from file
        self.system_prompt = load_prompt("financial_agent.txt")

        # Verify dataset exists
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")

        # Metrics tracking
        self.metrics = AgentMetrics()

        if self.log_traces:
            self.traces_dir.mkdir(exist_ok=True)

    def query(self, question: str) -> dict:
        """Process a user question through the agent loop."""
        return asyncio.run(self._query_async(question))

    async def _query_async(self, question: str) -> dict:
        """Async implementation of query."""
        trace = ExecutionTrace(query=question)
        current_turn = {"thinking": "", "tool_calls": []}
        final_answer = ""

        options = ClaudeCodeOptions(
            max_turns=15,
            system_prompt=self.system_prompt,
            cwd=str(self.project_root),
            allowed_tools=["Read", "Bash"],
            permission_mode="acceptEdits"
        )

        async for message in query(prompt=question, options=options):
            # Handle AssistantMessage (contains text and tool use blocks)
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        current_turn["thinking"] += block.text + "\n"
                        final_answer = block.text
                    elif isinstance(block, ToolUseBlock):
                        trace.total_tool_calls += 1
                        current_turn["tool_calls"].append({
                            "tool": block.name,
                            "input": str(block.input)[:500],  # Truncate long inputs
                        })

            # Handle ResultMessage (contains usage stats)
            elif isinstance(message, ResultMessage):
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

        trace.final_answer = final_answer

        # Save trace
        self.metrics.add_trace(trace)
        log_path = None
        if self.log_traces:
            log_path = self.metrics.save_trace(trace, self.traces_dir)

        return {
            "answer": final_answer,
            "trace": trace,
            "log_path": log_path
        }


def main():
    """Simple CLI for testing the agent."""
    import sys
    import traceback

    agent = FinancialAnalysisAgent()

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        result = agent.query(question)
        print("\n" + "="*60)
        print("ANSWER:")
        print("="*60)
        print(result["answer"])

        trace = result["trace"]
        print("\n" + "-"*40)
        print("METRICS:")
        print(f"  Tokens: {trace.total_tokens} (in: {trace.input_tokens}, out: {trace.output_tokens})")
        print(f"  Tool calls: {trace.total_tool_calls}")
        print(f"  Cost: ${trace.total_cost_usd:.4f}")
        print("-"*40)
    else:
        print("Financial Analysis Agent")
        print("="*40)
        print("Commands: 'quit', 'metrics'\n")

        while True:
            try:
                question = input("You: ").strip()
                if not question:
                    continue
                if question.lower() == "quit":
                    if agent.metrics.traces:
                        print("\n" + "="*40)
                        print("SESSION METRICS:")
                        for k, v in agent.metrics.compute().items():
                            print(f"  {k}: {v}")
                    break
                if question.lower() == "metrics":
                    if agent.metrics.traces:
                        print("\nMETRICS:")
                        for k, v in agent.metrics.compute().items():
                            print(f"  {k}: {v}")
                    else:
                        print("No queries yet.")
                    continue

                print("\nThinking...")
                result = agent.query(question)
                print("\n" + "-"*40)
                print(result["answer"])

                trace = result["trace"]
                print(f"\n[Tokens: {trace.total_tokens}, Tool calls: {trace.total_tool_calls}, Cost: ${trace.total_cost_usd:.4f}]")
                print("-"*40 + "\n")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}\n")
                traceback.print_exc()


if __name__ == "__main__":
    main()
