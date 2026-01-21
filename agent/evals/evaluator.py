"""
Evaluator Agent

Analyzes execution logs and evaluation results to suggest improvements
to the knowledge base, prompts, and agent behavior.
"""

from pathlib import Path
import asyncio
import json
from datetime import datetime

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


class EvaluatorAgent:
    """Agent that analyzes logs and suggests improvements."""

    def __init__(self):
        """Initialize the evaluator agent."""
        self.project_root = Path(__file__).parent
        self.logs_dir = self.project_root / "logs"
        self.learnings_dir = self.project_root / "learnings"
        self.knowledge_dir = self.project_root / "knowledge"

        # Load system prompt
        self.system_prompt = load_prompt("evaluator.txt")

        # Metrics tracking
        self.metrics = AgentMetrics()

    def evaluate(self, eval_file: str = None, apply_improvements: bool = False) -> dict:
        """
        Analyze evaluation results and suggest improvements.

        Args:
            eval_file: Path to evaluation results JSON. If None, uses most recent.
            apply_improvements: If True, automatically apply suggested improvements.

        Returns:
            dict with analysis results and suggestions
        """
        return asyncio.run(self._evaluate_async(eval_file, apply_improvements))

    async def _evaluate_async(self, eval_file: str, apply_improvements: bool) -> dict:
        """Async implementation of evaluate."""
        # Find evaluation file
        if eval_file is None:
            eval_files = sorted(self.learnings_dir.glob("eval_*.json"), reverse=True)
            if not eval_files:
                return {"error": "No evaluation files found in learnings/"}
            eval_file = str(eval_files[0])

        trace = ExecutionTrace(query=f"Evaluate: {eval_file}")
        current_turn = {"thinking": "", "tool_calls": []}
        final_answer = ""

        # Build the evaluation prompt
        prompt = self._build_evaluation_prompt(eval_file, apply_improvements)

        options = ClaudeCodeOptions(
            max_turns=20,
            system_prompt=self.system_prompt,
            cwd=str(self.project_root),
            allowed_tools=["Read", "Bash", "Write", "Edit"] if apply_improvements else ["Read", "Bash"],
            permission_mode="acceptEdits" if apply_improvements else "bypassPermissions"
        )

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        current_turn["thinking"] += block.text + "\n"
                        final_answer = block.text
                    elif isinstance(block, ToolUseBlock):
                        trace.total_tool_calls += 1
                        current_turn["tool_calls"].append({
                            "tool": block.name,
                            "input": str(block.input)[:500],
                        })

            elif isinstance(message, ResultMessage):
                if hasattr(message, 'usage') and message.usage:
                    trace.input_tokens = message.usage.get('input_tokens', 0)
                    trace.output_tokens = message.usage.get('output_tokens', 0)
                    trace.total_tokens = trace.input_tokens + trace.output_tokens
                if hasattr(message, 'total_cost_usd') and message.total_cost_usd:
                    trace.total_cost_usd = message.total_cost_usd

        # Finalize
        current_turn["thinking"] = current_turn["thinking"].strip()
        if current_turn["thinking"] or current_turn["tool_calls"]:
            trace.turns.append(current_turn)

        trace.final_answer = final_answer
        self.metrics.add_trace(trace)

        # Save evaluation report
        report_path = self._save_report(eval_file, final_answer, trace)

        return {
            "analysis": final_answer,
            "trace": trace,
            "report_path": report_path
        }

    def _build_evaluation_prompt(self, eval_file: str, apply_improvements: bool) -> str:
        """Build the prompt for evaluation analysis."""
        action = "analyze and apply improvements to" if apply_improvements else "analyze"
        return f"""Please {action} the evaluation results in: {eval_file}

Your task:
1. Read the evaluation results file
2. Identify any failures or suboptimal responses (compare agent_answer vs expected_answer)
3. Look for patterns in errors or inefficiencies
4. Review the current knowledge files (knowledge/schema.md, knowledge/examples.md)
5. {"Suggest AND apply improvements to knowledge files" if apply_improvements else "Suggest specific improvements"} to prevent similar issues

Focus on:
- Incorrect answers (agent got wrong result)
- Missing edge case handling
- Unclear or verbose responses
- Repeated patterns that could be documented
- Opportunities to add examples to knowledge/examples.md
"""

    def _save_report(self, eval_file: str, analysis: str, trace: ExecutionTrace) -> str:
        """Save the evaluation report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report = {
            "timestamp": datetime.now().isoformat(),
            "eval_file": eval_file,
            "analysis": analysis,
            "metrics": {
                "tokens": trace.total_tokens,
                "tool_calls": trace.total_tool_calls,
                "cost_usd": trace.total_cost_usd
            }
        }

        report_path = self.learnings_dir / f"evaluation_report_{timestamp}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        return str(report_path)

    def analyze_traces(self, limit: int = 10) -> dict:
        """
        Analyze recent execution traces for patterns.

        Args:
            limit: Number of recent traces to analyze

        Returns:
            dict with pattern analysis
        """
        return asyncio.run(self._analyze_traces_async(limit))

    async def _analyze_traces_async(self, limit: int) -> dict:
        """Async implementation of trace analysis."""
        trace_files = sorted(self.logs_dir.glob("trace_*.json"), reverse=True)[:limit]

        if not trace_files:
            return {"error": "No trace files found"}

        trace = ExecutionTrace(query=f"Analyze {len(trace_files)} recent traces")
        current_turn = {"thinking": "", "tool_calls": []}
        final_answer = ""

        trace_paths = "\n".join(f"- {f}" for f in trace_files)
        prompt = f"""Analyze these recent execution traces for patterns and improvement opportunities:

{trace_paths}

Look for:
1. Common errors or recovery patterns
2. Queries that required many tool calls (inefficient)
3. Similar queries that could benefit from cached examples
4. Repeated code patterns that could be documented

Provide actionable suggestions to improve the agent's knowledge base.
"""

        options = ClaudeCodeOptions(
            max_turns=15,
            system_prompt=self.system_prompt,
            cwd=str(self.project_root),
            allowed_tools=["Read", "Bash"],
            permission_mode="bypassPermissions"
        )

        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        current_turn["thinking"] += block.text + "\n"
                        final_answer = block.text
                    elif isinstance(block, ToolUseBlock):
                        trace.total_tool_calls += 1

            elif isinstance(message, ResultMessage):
                if hasattr(message, 'usage') and message.usage:
                    trace.total_tokens = message.usage.get('input_tokens', 0) + message.usage.get('output_tokens', 0)
                if hasattr(message, 'total_cost_usd') and message.total_cost_usd:
                    trace.total_cost_usd = message.total_cost_usd

        trace.final_answer = final_answer
        self.metrics.add_trace(trace)

        return {
            "analysis": final_answer,
            "traces_analyzed": len(trace_files),
            "trace": trace
        }


def main():
    """CLI for the evaluator agent."""
    import sys

    evaluator = EvaluatorAgent()

    def print_help():
        print("""
Evaluator Agent - Analyze logs and suggest improvements

Usage:
  python evaluator.py                     Analyze most recent evaluation
  python evaluator.py <eval_file>         Analyze specific evaluation file
  python evaluator.py --apply             Analyze and apply improvements
  python evaluator.py --traces [N]        Analyze N recent traces (default: 10)

Examples:
  python evaluator.py learnings/eval_20260121_005409.json
  python evaluator.py --apply
  python evaluator.py --traces 20
""")

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg in ["--help", "-h"]:
            print_help()
            return

        if arg == "--traces":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            print(f"Analyzing {limit} recent traces...")
            result = evaluator.analyze_traces(limit=limit)
        elif arg == "--apply":
            eval_file = sys.argv[2] if len(sys.argv) > 2 else None
            print("Analyzing and applying improvements...")
            result = evaluator.evaluate(eval_file=eval_file, apply_improvements=True)
        else:
            print(f"Analyzing: {arg}")
            result = evaluator.evaluate(eval_file=arg)
    else:
        print("Analyzing most recent evaluation...")
        result = evaluator.evaluate()

    if "error" in result:
        print(f"Error: {result['error']}")
        return

    print("\n" + "=" * 60)
    print("EVALUATION ANALYSIS")
    print("=" * 60)
    print(result["analysis"])

    if "trace" in result:
        trace = result["trace"]
        print("\n" + "-" * 40)
        print(f"[Tokens: {trace.total_tokens}, Tool calls: {trace.total_tool_calls}, Cost: ${trace.total_cost_usd:.4f}]")

    if "report_path" in result:
        print(f"\nReport saved to: {result['report_path']}")


if __name__ == "__main__":
    main()
