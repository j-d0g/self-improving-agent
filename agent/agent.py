"""
Financial Analysis Agent

A coding agent that answers financial questions about P&L data using pandas.
Tracks token usage and tool calls for metrics.
"""

from pathlib import Path

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import anthropic
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
import traceback
import json
import subprocess


def get_agent_version() -> dict:
    """Get version info from git commit and working tree status."""
    try:
        # Get current commit hash
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=Path(__file__).parent
        ).stdout.strip()[:8]  # Short hash

        # Check if working tree is dirty
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=Path(__file__).parent
        ).stdout.strip() != ""

        return {
            "commit": commit,
            "dirty": dirty,
            "version": f"{commit}{'-dirty' if dirty else ''}"
        }
    except Exception:
        return {"commit": "unknown", "dirty": False, "version": "unknown"}



@dataclass
class ExecutionTrace:
    """Tracks a single query execution for metrics."""
    query: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_version: dict = field(default_factory=get_agent_version)

    # Token metrics
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tool_calls: int = 0

    # Full execution history - each turn contains thinking + tool calls + results
    turns: list = field(default_factory=list)
    final_answer: str = ""

    def to_dict(self) -> dict:
        return {
            "agent_version": self.agent_version,
            "query": self.query,
            "timestamp": self.timestamp,
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tool_calls": self.total_tool_calls,
            "turns": self.turns,
            "final_answer": self.final_answer,
        }


@dataclass
class AgentMetrics:
    """Aggregated metrics across multiple queries."""
    traces: list[ExecutionTrace] = field(default_factory=list)

    def add_trace(self, trace: ExecutionTrace):
        self.traces.append(trace)

    def compute(self) -> dict:
        if not self.traces:
            return {"error": "No traces recorded"}

        total = len(self.traces)
        total_tokens = sum(t.total_tokens for t in self.traces)
        total_input_tokens = sum(t.input_tokens for t in self.traces)
        total_output_tokens = sum(t.output_tokens for t in self.traces)
        total_tool_calls = sum(t.total_tool_calls for t in self.traces)

        return {
            "total_queries": total,
            "total_tokens": total_tokens,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_tool_calls": total_tool_calls,
            "avg_tokens_per_query": round(total_tokens / total, 2),
            "avg_tool_calls_per_query": round(total_tool_calls / total, 2),
        }

    def save(self, path: str = "metrics.json"):
        data = {
            "computed_at": datetime.now().isoformat(),
            "summary": self.compute(),
            "traces": [t.to_dict() for t in self.traces]
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        return path

    def save_trace(self, trace: ExecutionTrace, logs_dir: Path) -> str:
        """Save a single trace to the learnings directory."""
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"trace_{timestamp}.json"
        filepath = logs_dir / filename
        with open(filepath, "w") as f:
            json.dump(trace.to_dict(), f, indent=2)
        return str(filepath)


# Tool definitions
TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the knowledge directory or codebase. Use this to read schema.md, learned functions, and guidelines before answering queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root (e.g., 'knowledge/schema.md')"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "execute_pandas",
        "description": "Execute pandas code against the financial dataset. The DataFrame is available as 'df'. Returns the result or error message.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python pandas code to execute. The DataFrame is available as 'df'. Assign your final result to 'result' variable."
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory to see what's available.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to project root"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "edit_file",
        "description": "Append content to a knowledge file to persist learnings for future sessions. Use this after recovering from errors to save patterns that help avoid similar mistakes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relative to project root (must be in knowledge/ directory)"
                },
                "content": {
                    "type": "string",
                    "description": "Content to append to the file"
                }
            },
            "required": ["path", "content"]
        }
    }
]


SYSTEM_PROMPT = """You are a financial data analysis agent.

## Your Mission
Answer financial questions about a company's P&L dataset by generating and executing pandas code.

## Workflow for Every Query

### Step 1: Gather Context
Start by reading the schema file (use read_file tool):
- knowledge/schema.md - Column definitions, valid values, important calculations

### Step 2: Generate and Execute Code
- Use execute_pandas tool to run your analysis
- The DataFrame 'df' is pre-loaded with the financial data
- Assign your final result to a 'result' variable

### Step 3: Validate Results
After execution, check for error signals:
- **Execution error**: Code threw an exception
- **Empty result**: DataFrame/Series has 0 rows (likely wrong filter)
- **Unexpected None**: Result is None when a value was expected
- **Nonsensical values**: Negative revenue (unless returns), impossibly large numbers
- **Missing data**: NaN values where numbers expected

### Step 4: Error Recovery
If an error is detected:
1. Analyze what went wrong
2. Fix and retry the code

### Step 5: Learn from Mistakes (Cross-Session Improvement)
If you encountered an error and successfully recovered:
1. **Analyze**: What went wrong? What fixed it?
2. **Generalize**: Would this help future similar queries?
3. **Persist**: Use edit_file to add to the appropriate knowledge file:
   - knowledge/examples.md - Query patterns with working code
   - knowledge/functions.py - Reusable helper functions
   - knowledge/improvements.md - Tips and common pitfalls

Format for examples.md:
```
## [Pattern Description]
**Query:** [The question]
**Mistake:** [What went wrong]
**Fix:** [How to avoid it]
**Working Code:**
```python
# code that works
```
```

## Important Rules
- Use "Amount in USD" for all monetary calculations unless specifically asked about local currency
- Quarters span 3 months: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec
- "Revenue" typically means Net Revenue (sum of all FSLine Statement L1 = "Net Revenue" items)
- Only Products A, B, C, D exist. Flag if user asks about non-existent products.
- Be precise with column names - they have spaces and specific capitalization

## Response Format
After completing your analysis, provide:
1. The answer to the user's question (clear and concise)
2. Brief explanation of how you calculated it"""


class FinancialAnalysisAgent:
    """A financial analysis agent with metrics tracking."""

    def __init__(self, dataset_path: str = "data/FUN_company_pl_actuals_dataset.csv", log_traces: bool = True):
        """Initialize the agent with the dataset."""
        self.client = anthropic.Anthropic()
        self.project_root = Path(__file__).parent
        self.dataset_path = self.project_root / dataset_path
        self.logs_dir = self.project_root / "learnings"
        self.log_traces = log_traces

        # Load the dataset
        self.df = pd.read_csv(self.dataset_path)

        # Metrics tracking
        self.metrics = AgentMetrics()

        # Ensure learnings directory exists
        if self.log_traces:
            self.logs_dir.mkdir(exist_ok=True)

    def query(self, question: str) -> dict:
        """
        Process a user question through the agentic loop.

        Returns a dict with:
        - answer: The final answer
        - trace: ExecutionTrace with token/tool call metrics
        """
        messages = [{"role": "user", "content": question}]
        trace = ExecutionTrace(query=question)

        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )

            # Track token usage
            trace.input_tokens += response.usage.input_tokens
            trace.output_tokens += response.usage.output_tokens
            trace.total_tokens += response.usage.input_tokens + response.usage.output_tokens

            # Add assistant response to history
            messages.append({"role": "assistant", "content": response.content})

            # Check if we're done
            if response.stop_reason == "end_turn":
                # Extract the text response
                answer = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        answer = block.text
                        break

                # Record final answer in trace
                trace.final_answer = answer

                # Save trace to metrics and log file
                self.metrics.add_trace(trace)
                if self.log_traces:
                    log_path = self.metrics.save_trace(trace, self.logs_dir)

                return {
                    "answer": answer,
                    "trace": trace,
                    "log_path": log_path if self.log_traces else None
                }

            # Capture this turn: thinking + tool calls + results
            turn = {"thinking": "", "tool_calls": []}

            # Extract thinking (text blocks)
            for block in response.content:
                if hasattr(block, "text"):
                    turn["thinking"] += block.text + "\n"
            turn["thinking"] = turn["thinking"].strip()

            # Execute tool calls and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    trace.total_tool_calls += 1
                    result = self._execute_tool(block.name, block.input)

                    # Record in turn
                    turn["tool_calls"].append({
                        "tool": block.name,
                        "input": block.input,
                        "output": result[:2000] if len(result) > 2000 else result,
                    })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            trace.turns.append(turn)
            messages.append({"role": "user", "content": tool_results})

    def _execute_tool(self, name: str, input_data: dict) -> str:
        """Execute a tool and return the result as a string."""
        try:
            if name == "read_file":
                return self._tool_read_file(input_data["path"])
            elif name == "execute_pandas":
                return self._tool_execute_pandas(input_data["code"])
            elif name == "list_files":
                return self._tool_list_files(input_data["path"])
            elif name == "edit_file":
                return self._tool_edit_file(input_data["path"], input_data["content"])
            else:
                return f"Unknown tool: {name}"
        except Exception as e:
            return f"Error: {type(e).__name__}: {str(e)}"

    def _tool_read_file(self, path: str) -> str:
        """Read a file from the project."""
        file_path = self.project_root / path
        if not file_path.exists():
            return f"File not found: {path}"
        if not file_path.is_file():
            return f"Path is not a file: {path}"
        return file_path.read_text()

    def _tool_execute_pandas(self, code: str) -> str:
        """Safely execute pandas code against the dataset."""
        # Create a restricted namespace
        namespace = {
            "df": self.df.copy(),  # Use a copy to prevent mutations
            "pd": pd,
            "result": None,
        }

        # Safe builtins
        safe_builtins = {
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "sorted": sorted,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "print": print,
            "isinstance": isinstance,
            "type": type,
            "None": None,
            "True": True,
            "False": False,
        }
        namespace["__builtins__"] = safe_builtins

        try:
            exec(code, namespace)
            result = namespace.get("result")

            if result is None:
                return "Code executed but 'result' variable was not set. Please assign your final answer to 'result'."

            # Format result based on type
            if isinstance(result, pd.DataFrame):
                if len(result) > 20:
                    return f"DataFrame with {len(result)} rows:\n{result.head(20).to_string()}\n... (truncated)"
                return f"DataFrame:\n{result.to_string()}"

            elif isinstance(result, pd.Series):
                if len(result) > 20:
                    return f"Series with {len(result)} items:\n{result.head(20).to_string()}\n... (truncated)"
                return f"Series:\n{result.to_string()}"

            return str(result)

        except Exception as e:
            return f"Execution error: {type(e).__name__}: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"

    def _tool_list_files(self, path: str) -> str:
        """List files in a directory."""
        dir_path = self.project_root / path
        if not dir_path.exists():
            return f"Directory not found: {path}"
        if not dir_path.is_dir():
            return f"Path is not a directory: {path}"

        files = []
        for item in sorted(dir_path.iterdir()):
            if item.is_file():
                files.append(f"  {item.name}")
            else:
                files.append(f"  {item.name}/")

        return f"Contents of {path}:\n" + "\n".join(files)

    def _tool_edit_file(self, path: str, content: str) -> str:
        """Append content to a knowledge file for cross-session learning."""
        # Security: only allow editing files in knowledge/ directory
        if not path.startswith("knowledge/"):
            return "Error: Can only edit files in knowledge/ directory"

        file_path = self.project_root / path
        if not file_path.exists():
            return f"Error: File not found: {path}"

        try:
            with open(file_path, "a") as f:
                f.write("\n" + content + "\n")
            return f"Successfully appended to {path}"
        except Exception as e:
            return f"Error writing to file: {type(e).__name__}: {str(e)}"


def main():
    """Simple CLI for testing the agent."""
    import sys

    agent = FinancialAnalysisAgent()

    if len(sys.argv) > 1:
        # Query from command line
        question = " ".join(sys.argv[1:])
        result = agent.query(question)
        print("\n" + "="*60)
        print("ANSWER:")
        print("="*60)
        print(result["answer"])

        # Show trace summary
        trace = result["trace"]
        print("\n" + "-"*40)
        print("METRICS:")
        print(f"  Tokens: {trace.total_tokens} (in: {trace.input_tokens}, out: {trace.output_tokens})")
        print(f"  Tool calls: {trace.total_tool_calls}")
        print("-"*40)
    else:
        # Interactive mode
        print("Financial Analysis Agent")
        print("="*40)
        print("Commands: 'quit', 'metrics'\n")

        while True:
            try:
                question = input("You: ").strip()
                if not question:
                    continue
                if question.lower() == "quit":
                    # Show final metrics before exiting
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

                # Show brief trace
                trace = result["trace"]
                print(f"\n[Tokens: {trace.total_tokens}, Tool calls: {trace.total_tool_calls}]")
                print("-"*40 + "\n")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
