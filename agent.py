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
from typing import Any
import traceback


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
When you learn something new that would help future queries, persist that knowledge by editing files.

## Workflow for Every Query

### Step 1: Gather Context
ALWAYS start by reading these files (use read_file tool):
1. knowledge/dataset_schema.md - Column definitions, valid values, important calculations
2. knowledge/learned/functions.py - Helper functions you've created in past sessions
3. knowledge/learned/guidelines.md - Best practices you've learned

### Step 2: Generate and Execute Code
- Use execute_pandas tool to run your analysis
- The DataFrame 'df' is pre-loaded with the financial data
- Assign your final result to a 'result' variable
- You can import pandas as pd and use any functions from knowledge/learned/functions.py

### Step 3: Validate Results
After getting results, verify:
- Does the result make sense? (e.g., revenue shouldn't be negative unless it's a return)
- Did you filter correctly? (check row counts)
- Did you handle all edge cases mentioned in the schema?

### Step 4: Learn and Persist (CRITICAL)
If you discover something useful during this query:

**Add a helper function** - Edit knowledge/learned/functions.py:
- If you wrote code that would be reusable (e.g., quarter filtering, margin calculation)
- Find the "# ---LEARNING_MARKER---" line and add your function after it

**Add a guideline** - Edit knowledge/learned/guidelines.md:
- If you made a mistake and learned from it
- If you discovered a data quirk
- Find the "<!-- ---LEARNING_MARKER--- -->" line and add your guideline after it

**Log the example** - Edit knowledge/examples.md:
- Log successful query patterns for reference
- Find the "<!-- ---EXAMPLES_MARKER--- -->" line and add your example

## Error Handling
If your code fails or returns unexpected results:
1. Analyze what went wrong
2. Fix the immediate issue
3. If the error reveals a pattern others might hit, ADD A GUIDELINE
4. If you wrote a fix that would help future queries, ADD A HELPER FUNCTION

## Important Rules
- ALWAYS read knowledge files first before answering
- Use "Amount in USD" for all monetary calculations unless specifically asked about local currency
- Quarters span 3 months: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec
- "Revenue" typically means Net Revenue (sum of all FSLine Statement L1 = "Net Revenue" items)
- Only Products A, B, C, D exist. Flag if user asks about non-existent products.
- Be precise with column names - they have spaces and specific capitalization

## Response Format
After completing your analysis, provide:
1. The answer to the user's question (clear and concise)
2. Brief explanation of how you calculated it
3. If you learned something, mention that you've persisted it for future sessions"""


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
        """
        messages = [{"role": "user", "content": question}]
        code_executed = []
        learned_something = False

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

                return {
                    "answer": answer,
                    "code_executed": code_executed,
                    "learned": learned_something
                }

            # Handle tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input

                    # Track if we're editing knowledge files
                    if tool_name in ("edit_file", "write_file"):
                        path = tool_input.get("path", "")
                        if "knowledge/learned" in path or "knowledge/examples" in path:
                            learned_something = True

                    # Track code execution
                    if tool_name == "execute_pandas":
                        code_executed.append(tool_input.get("code", ""))

                    # Execute the tool
                    result = self._execute_tool(tool_name, tool_input)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})

    def _execute_tool(self, name: str, input_data: dict) -> str:
        """Execute a tool and return the result as a string."""
        try:
            if name == "read_file":
                return self._tool_read_file(input_data["path"])
            elif name == "write_file":
                return self._tool_write_file(input_data["path"], input_data["content"])
            elif name == "edit_file":
                return self._tool_edit_file(
                    input_data["path"],
                    input_data["old_string"],
                    input_data["new_string"]
                )
            elif name == "execute_pandas":
                return self._tool_execute_pandas(input_data["code"])
            elif name == "list_files":
                return self._tool_list_files(input_data["path"])
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

    def _tool_execute_pandas(self, code: str) -> str:
        """Safely execute pandas code against the dataset."""
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

        try:
            exec(code, namespace)
            result = namespace.get("result")

            if result is None:
                return "Code executed but 'result' variable was not set. Please assign your final answer to 'result'."

            # Format the result nicely
            if isinstance(result, pd.DataFrame):
                if len(result) > 20:
                    return f"DataFrame with {len(result)} rows:\n{result.head(20).to_string()}\n... (truncated)"
                return f"DataFrame:\n{result.to_string()}"
            elif isinstance(result, pd.Series):
                if len(result) > 20:
                    return f"Series with {len(result)} items:\n{result.head(20).to_string()}\n... (truncated)"
                return f"Series:\n{result.to_string()}"
            else:
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
        if result["learned"]:
            print("\n[Agent persisted learnings for future sessions]")
    else:
        # Interactive mode
        print("Self-Improving Financial Analysis Agent")
        print("="*40)
        print("Ask questions about the financial dataset.")
        print("Type 'quit' to exit, 'reset' to clear learnings.\n")

        while True:
            try:
                question = input("You: ").strip()
                if not question:
                    continue
                if question.lower() == "quit":
                    break
                if question.lower() == "reset":
                    agent.reset_learnings()
                    continue

                print("\nThinking...")
                result = agent.query(question)
                print("\n" + "-"*40)
                print(result["answer"])
                if result["learned"]:
                    print("\n[Persisted learnings for future sessions]")
                print("-"*40 + "\n")

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
