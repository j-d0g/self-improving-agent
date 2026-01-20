"""
Self-Improving Financial Analysis Agent

A coding agent that uses file editing tools to modify its own knowledge base.
The learning mechanism IS the agent editing its own files.
"""

import os
from pathlib import Path

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import anthropic
import pandas as pd
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import traceback
import json

# Import verification module
from verification import (
    VerificationPipeline,
    ExceptionClassifier,
    ErrorCategory,
    ErrorType,
    Severity,
    VerificationReport
)


@dataclass
class ExecutionTrace:
    """Tracks a single query execution for metrics."""
    query: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    # Execution tracking
    code_attempts: list[dict] = field(default_factory=list)  # {code, result, error, verification}
    total_attempts: int = 0
    successful: bool = False

    # Error tracking (now with verification-based classification)
    errors_encountered: list[dict] = field(default_factory=list)  # {type, category, message, attempt, recovery_hint}
    error_recovered: bool = False

    # Learning tracking
    learning_triggered: bool = False
    learning_type: str = None  # "guideline", "function", or "both"
    learning_description: str = None

    # Verification tracking
    verification_failures: list[dict] = field(default_factory=list)  # Detailed verification results
    programmatic_errors: int = 0  # Errors caught by programmatic verification (not LLM)

    # Timing
    total_tool_calls: int = 0

    def add_code_attempt(
        self,
        code: str,
        result: str,
        verification_report: VerificationReport = None
    ):
        """Add a code execution attempt with optional verification results."""
        self.total_attempts += 1

        # Determine if this is an error based on verification
        is_error = False
        error_type = None
        error_category = None
        recovery_hint = None

        if verification_report and not verification_report.passed:
            is_error = True
            self.programmatic_errors += 1
            first_error = verification_report.first_error
            if first_error:
                error_type = first_error.error_type.value if first_error.error_type else "unknown"
                error_category = first_error.category.value if first_error.category else "unknown"
                recovery_hint = first_error.recovery_hint
                self.verification_failures.append({
                    "attempt": self.total_attempts,
                    "layer": first_error.layer,
                    "error_type": error_type,
                    "category": error_category,
                    "message": first_error.error_message,
                    "recovery_hint": recovery_hint
                })

        # Store the attempt
        self.code_attempts.append({
            "attempt": self.total_attempts,
            "code": code,
            "result": result[:500] if result else None,  # Truncate for storage
            "is_error": is_error,
            "error_type": error_type,
            "error_category": error_category
        })

        if is_error:
            self.errors_encountered.append({
                "attempt": self.total_attempts,
                "type": error_type,
                "category": error_category,
                "message": result[:200] if result else "Unknown error",
                "recovery_hint": recovery_hint
            })
        else:
            self.successful = True
            if self.total_attempts > 1:
                self.error_recovered = True

    def to_dict(self) -> dict:
        return {
            "query": self.query,
            "timestamp": self.timestamp,
            "total_attempts": self.total_attempts,
            "successful": self.successful,
            "errors_encountered": len(self.errors_encountered),
            "error_categories": list(set(e.get("category") for e in self.errors_encountered if e.get("category"))),
            "error_recovered": self.error_recovered,
            "learning_triggered": self.learning_triggered,
            "learning_type": self.learning_type,
            "total_tool_calls": self.total_tool_calls,
            "programmatic_errors": self.programmatic_errors
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
        successful = sum(1 for t in self.traces if t.successful)
        with_errors = sum(1 for t in self.traces if t.errors_encountered)
        recovered = sum(1 for t in self.traces if t.error_recovered)
        learned = sum(1 for t in self.traces if t.learning_triggered)

        total_attempts = sum(t.total_attempts for t in self.traces)
        total_tool_calls = sum(t.total_tool_calls for t in self.traces)
        programmatic_errors = sum(t.programmatic_errors for t in self.traces)

        # Aggregate error categories
        error_categories = {}
        for t in self.traces:
            for e in t.errors_encountered:
                cat = e.get("category", "unknown")
                if cat:
                    error_categories[cat] = error_categories.get(cat, 0) + 1

        return {
            "total_queries": total,
            "successful_queries": successful,
            "success_rate": round(successful / total * 100, 1),

            "queries_with_errors": with_errors,
            "error_rate": round(with_errors / total * 100, 1),

            "errors_recovered": recovered,
            "recovery_rate": round(recovered / with_errors * 100, 1) if with_errors > 0 else 0,

            "learnings_created": learned,
            "learning_rate": round(learned / total * 100, 1),

            "avg_attempts_per_query": round(total_attempts / total, 2),
            "avg_tool_calls_per_query": round(total_tool_calls / total, 2),

            # First-try success (no errors at all)
            "first_try_success": sum(1 for t in self.traces if t.successful and not t.errors_encountered),
            "first_try_success_rate": round(
                sum(1 for t in self.traces if t.successful and not t.errors_encountered) / total * 100, 1
            ),

            # Verification-specific metrics
            "programmatic_errors_caught": programmatic_errors,
            "error_categories": error_categories
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


# Tool definitions
TOOLS = [
    {
        "name": "read_file",
        "description": "Read a file from the knowledge directory or codebase. Use this to read dataset_schema.md, learned functions, and guidelines before answering queries.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root (e.g., 'knowledge/dataset_schema.md')"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "edit_file",
        "description": "Edit a file by replacing old_string with new_string. Use this to add learned functions or guidelines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root"
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact string to find and replace"
                },
                "new_string": {
                    "type": "string",
                    "description": "The string to replace it with"
                }
            },
            "required": ["path", "old_string", "new_string"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file (creates or overwrites). Use sparingly - prefer edit_file for modifications.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to project root"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write"
                }
            },
            "required": ["path", "content"]
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
    }
]


SYSTEM_PROMPT = """You are a self-improving financial data analysis agent.

## Your Mission
Answer financial questions about a company's P&L dataset by generating and executing pandas code.
You improve by learning from your MISTAKES - when code fails or produces wrong results, you persist that learning to prevent the same error in future sessions.

## Workflow for Every Query

### Step 1: Gather Context
ALWAYS start by reading these files (use read_file tool):
1. knowledge/dataset_schema.md - Column definitions, valid values, important calculations
2. knowledge/learned/functions.py - Helper functions created from past mistakes
3. knowledge/learned/guidelines.md - Lessons learned from past errors

### Step 2: Generate and Execute Code
- Use execute_pandas tool to run your analysis
- The DataFrame 'df' is pre-loaded with the financial data
- Assign your final result to a 'result' variable
- USE any helper functions from knowledge/learned/functions.py - they exist because past errors taught us we need them

### Step 3: Validate Results (ERROR DETECTION)
After execution, CHECK FOR THESE ERROR SIGNALS:
- **Execution error**: Code threw an exception
- **Empty result**: DataFrame/Series has 0 rows (likely wrong filter)
- **Unexpected None**: Result is None when a value was expected
- **Nonsensical values**: Negative revenue (unless returns), impossibly large numbers
- **Missing data**: NaN values where numbers expected
- **Wrong magnitude**: Result seems off by orders of magnitude

### Step 4: Error Recovery and Learning (CRITICAL)
If ANY error signal is detected:

1. **STOP and analyze**: What went wrong? Classify the error:
   - DATA_FILTER_ERROR: Wrong column name, value, or filter logic
   - CALCULATION_ERROR: Wrong formula or aggregation
   - EDGE_CASE_ERROR: Didn't handle quarter boundaries, negative values, etc.
   - VALIDATION_ERROR: Asked about non-existent product/country/etc.

2. **Fix and retry**: Correct the code and execute again

3. **PERSIST THE LEARNING** (only after successful recovery):
   - Edit knowledge/learned/guidelines.md: Add a guideline describing the error and how to avoid it
   - Edit knowledge/learned/functions.py: If you wrote a reusable fix, add it as a helper function

   Format for guidelines:
   ```
   ### [Error Type]: [Brief Description]
   **Error**: [What went wrong]
   **Cause**: [Root cause]
   **Fix**: [How to avoid this]
   ```

## When NOT to Learn
- Do NOT persist learnings if the query succeeded on first try
- Do NOT add helper functions for one-off calculations
- Only persist learnings that would prevent a CLASS of errors, not just one instance

## Important Rules
- ALWAYS read knowledge files first - they contain lessons from past mistakes
- Use "Amount in USD" for all monetary calculations unless specifically asked about local currency
- Quarters span 3 months: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec
- "Revenue" typically means Net Revenue (sum of all FSLine Statement L1 = "Net Revenue" items)
- Only Products A, B, C, D exist. Flag if user asks about non-existent products.
- Be precise with column names - they have spaces and specific capitalization

## Response Format
After completing your analysis, provide:
1. The answer to the user's question (clear and concise)
2. Brief explanation of how you calculated it
3. If you encountered and recovered from an error, explain what you learned"""


class SelfImprovingAgent:
    """A financial analysis agent that learns by editing its own knowledge files."""

    def __init__(self, dataset_path: str = "FUN_company_pl_actuals_dataset.csv"):
        """Initialize the agent with the dataset."""
        self.client = anthropic.Anthropic()
        self.project_root = Path(__file__).parent
        self.dataset_path = self.project_root / dataset_path

        # Load the dataset
        self.df = pd.read_csv(self.dataset_path)

        # Load any learned functions into namespace
        self.learned_namespace = self._load_learned_functions()

        # Metrics tracking
        self.metrics = AgentMetrics()

        # Verification pipeline for programmatic error detection
        self.verifier = VerificationPipeline()

    def _load_learned_functions(self) -> dict:
        """Load learned functions from the knowledge directory."""
        namespace = {"pd": pd}
        functions_path = self.project_root / "knowledge" / "learned" / "functions.py"

        if functions_path.exists():
            try:
                code = functions_path.read_text()
                exec(code, namespace)
            except Exception as e:
                print(f"Warning: Could not load learned functions: {e}")

        return namespace

    def query(self, question: str) -> dict:
        """
        Process a user question through the agentic loop.

        Returns a dict with:
        - answer: The final answer
        - code_executed: The pandas code that was run
        - learned: Whether the agent persisted any learnings
        - trace: ExecutionTrace with detailed metrics
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

                # Save trace to metrics
                self.metrics.add_trace(trace)

                return {
                    "answer": answer,
                    "code_executed": [a["code"] for a in trace.code_attempts],
                    "learned": trace.learning_triggered,
                    "trace": trace
                }

            # Handle tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    trace.total_tool_calls += 1

                    # Track if we're editing knowledge files (learning)
                    if tool_name in ("edit_file", "write_file"):
                        path = tool_input.get("path", "")
                        if "knowledge/learned" in path:
                            trace.learning_triggered = True
                            if "functions.py" in path:
                                trace.learning_type = "function" if not trace.learning_type else "both"
                            elif "guidelines.md" in path:
                                trace.learning_type = "guideline" if not trace.learning_type else "both"

                    # Execute the tool
                    result, verification_report = self._execute_tool_with_verification(
                        tool_name, tool_input
                    )

                    # Track code execution results with verification
                    if tool_name == "execute_pandas":
                        trace.add_code_attempt(
                            code=tool_input.get("code", ""),
                            result=result,
                            verification_report=verification_report
                        )

                        # If verification failed, append feedback to help agent self-correct
                        if verification_report and not verification_report.passed:
                            feedback = verification_report.to_feedback()
                            result = f"{result}\n\n[VERIFICATION FAILED]\n{feedback}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})

    def _execute_tool_with_verification(
        self, name: str, input_data: dict
    ) -> tuple[str, Optional[VerificationReport]]:
        """
        Execute a tool and return (result, verification_report).

        Verification is only performed for execute_pandas tool.
        """
        try:
            if name == "read_file":
                return self._tool_read_file(input_data["path"]), None
            elif name == "write_file":
                return self._tool_write_file(input_data["path"], input_data["content"]), None
            elif name == "edit_file":
                return self._tool_edit_file(
                    input_data["path"],
                    input_data["old_string"],
                    input_data["new_string"]
                ), None
            elif name == "execute_pandas":
                return self._tool_execute_pandas_with_verification(input_data["code"])
            elif name == "list_files":
                return self._tool_list_files(input_data["path"]), None
            else:
                return f"Unknown tool: {name}", None
        except Exception as e:
            return f"Error: {type(e).__name__}: {str(e)}", None

    def _execute_tool(self, name: str, input_data: dict) -> str:
        """Execute a tool and return the result as a string (legacy method)."""
        result, _ = self._execute_tool_with_verification(name, input_data)
        return result

    def _tool_read_file(self, path: str) -> str:
        """Read a file from the project."""
        file_path = self.project_root / path
        if not file_path.exists():
            return f"File not found: {path}"
        if not file_path.is_file():
            return f"Path is not a file: {path}"
        return file_path.read_text()

    def _tool_write_file(self, path: str, content: str) -> str:
        """Write content to a file."""
        file_path = self.project_root / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)
        return f"Successfully wrote {len(content)} bytes to {path}"

    def _tool_edit_file(self, path: str, old_string: str, new_string: str) -> str:
        """Edit a file by replacing old_string with new_string."""
        file_path = self.project_root / path
        if not file_path.exists():
            return f"File not found: {path}"

        content = file_path.read_text()
        if old_string not in content:
            return f"String not found in file. Available content snippet: {content[:500]}..."

        new_content = content.replace(old_string, new_string, 1)
        file_path.write_text(new_content)

        # Reload learned functions if we edited them
        if "functions.py" in path:
            self.learned_namespace = self._load_learned_functions()

        return f"Successfully edited {path}"

    def _tool_execute_pandas_with_verification(
        self, code: str
    ) -> tuple[str, VerificationReport]:
        """
        Safely execute pandas code and run programmatic verification.

        Returns (result_string, verification_report).
        The verification report contains all checks that were run.
        """
        # Create a restricted namespace
        namespace = {
            "df": self.df.copy(),  # Use a copy to prevent mutations
            "pd": pd,
            "result": None,
            **self.learned_namespace  # Include learned functions
        }

        # Remove potentially dangerous builtins
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

        report = VerificationReport()

        try:
            exec(code, namespace)
            result = namespace.get("result")

            # Layer 1: Check if result exists
            if result is None:
                result_str = "Code executed but 'result' variable was not set. Please assign your final answer to 'result'."
                report.add(self.verifier.verify_execution_result(result_str))
                return result_str, report

            # Layer 2: Data shape verification for DataFrames
            if isinstance(result, pd.DataFrame):
                shape_report = self.verifier.verify_dataframe(result)
                for r in shape_report.results:
                    report.add(r)

                # Format the result
                if len(result) > 20:
                    result_str = f"DataFrame with {len(result)} rows:\n{result.head(20).to_string()}\n... (truncated)"
                else:
                    result_str = f"DataFrame:\n{result.to_string()}"

            elif isinstance(result, pd.Series):
                # Check if series is empty
                if result.empty:
                    report.add(self.verifier.data_shape.check_not_empty(
                        pd.DataFrame(result)
                    ))

                if len(result) > 20:
                    result_str = f"Series with {len(result)} items:\n{result.head(20).to_string()}\n... (truncated)"
                else:
                    result_str = f"Series:\n{result.to_string()}"

            elif isinstance(result, (int, float)):
                # Layer 3: Basic financial value checks for numeric results
                # Check for obviously wrong values
                if isinstance(result, float) and (result != result):  # NaN check
                    from verification import ErrorType as VErrorType, ErrorCategory as VErrorCategory, Severity as VSeverity, VerificationResult as VResult
                    report.add(VResult.failure(
                        VErrorType.VALUE_ERROR,
                        "Result is NaN - calculation may have divided by zero or used invalid data",
                        layer="domain",
                        severity=VSeverity.ERROR,
                        category=VErrorCategory.LOGIC_ERROR,
                        recovery_hint="Check for division by zero or missing data in calculation"
                    ))
                result_str = str(result)
            else:
                result_str = str(result)

            return result_str, report

        except Exception as e:
            # Use exception classifier for semantic error analysis
            error_str = f"Execution error: {type(e).__name__}: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            classification = ExceptionClassifier.classify(error_str)
            report.add(classification)
            return error_str, report

    def _tool_execute_pandas(self, code: str) -> str:
        """Safely execute pandas code against the dataset (legacy method)."""
        result, _ = self._tool_execute_pandas_with_verification(code)
        return result

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

    def reset_learnings(self):
        """Reset all learned knowledge (for testing purposes)."""
        # Reset functions.py
        functions_path = self.project_root / "knowledge" / "learned" / "functions.py"
        functions_path.write_text('''"""
Learned Helper Functions

This file is automatically edited by the agent when it discovers reusable patterns.
Functions added here will be available in future sessions.

DO NOT EDIT MANUALLY - This file is managed by the self-improving agent.
"""

import pandas as pd
from typing import List, Optional, Union

# Agent-learned functions will be added below this line
# ---LEARNING_MARKER---
''')

        # Reset guidelines.md
        guidelines_path = self.project_root / "knowledge" / "learned" / "guidelines.md"
        guidelines_path.write_text('''# Learned Guidelines

This file is automatically edited by the agent when it discovers best practices.
Guidelines added here will inform future query handling.

DO NOT EDIT MANUALLY - This file is managed by the self-improving agent.

## Guidelines

<!-- Agent-learned guidelines will be added below this line -->
<!-- ---LEARNING_MARKER--- -->
''')

        # Reset examples.md
        examples_path = self.project_root / "knowledge" / "examples.md"
        examples_path.write_text('''# Query Examples Log

This file logs successful queries and their solutions for reference.

DO NOT EDIT MANUALLY - This file is managed by the self-improving agent.

## Examples

<!-- Agent will log successful queries below -->
<!-- ---EXAMPLES_MARKER--- -->
''')

        # Reload the learned namespace
        self.learned_namespace = self._load_learned_functions()
        print("All learnings have been reset.")


def main():
    """Simple CLI for testing the agent."""
    import sys

    agent = SelfImprovingAgent()

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
        print("EXECUTION TRACE:")
        print(f"  Code attempts: {trace.total_attempts}")
        print(f"  Errors encountered: {len(trace.errors_encountered)}")
        if trace.errors_encountered:
            categories = set(e.get("category") for e in trace.errors_encountered if e.get("category"))
            print(f"  Error categories: {list(categories)}")
        print(f"  Programmatic errors caught: {trace.programmatic_errors}")
        print(f"  Error recovered: {trace.error_recovered}")
        print(f"  Learning triggered: {trace.learning_triggered}")
        if trace.learning_type:
            print(f"  Learning type: {trace.learning_type}")
        print("-"*40)
    else:
        # Interactive mode
        print("Self-Improving Financial Analysis Agent")
        print("="*40)
        print("Commands: 'quit', 'reset', 'metrics'\n")

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
                if question.lower() == "reset":
                    agent.reset_learnings()
                    continue
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
                if trace.errors_encountered:
                    print(f"\n[Errors: {len(trace.errors_encountered)}, Recovered: {trace.error_recovered}]")
                if trace.learning_triggered:
                    print(f"[Learning: {trace.learning_type}]")
                print("-"*40 + "\n")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
