"""
Financial Analysis Agent - Web Server

A FastAPI server that exposes the financial analysis agent as a REST API.
Uses direct Anthropic API for reliability.

Usage:
    uvicorn server:app --reload
    
Endpoints:
    POST /chat     - Send a question, get an answer
    GET  /health   - Health check
    GET  /metrics  - Get session metrics
"""

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import traceback
import anthropic
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime
import json

app = FastAPI(
    title="Financial Analysis Agent",
    description="A coding agent that answers financial questions about P&L data using pandas.",
    version="1.0.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Simple Agent Implementation ============

TOOLS = [
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
        "name": "read_file",
        "description": "Read a file from the knowledge directory.",
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
    }
]

SYSTEM_PROMPT = """You are a financial data analysis agent.

## Your Mission
Answer financial questions about a company's P&L dataset by generating and executing pandas code.

## Workflow
1. First read knowledge/schema.md to understand the data structure
2. Execute pandas code to answer the question
3. Validate results and provide a clear answer

## Important Rules
- Use "Amount in USD" for all monetary calculations
- Quarters: Q1=Jan-Mar, Q2=Apr-Jun, Q3=Jul-Sep, Q4=Oct-Dec
- Valid products: Product A, Product B, Product C, Product D only
- Column names have spaces: "Amount in USD", "Fiscal Year", "FSLine Statement L1"

## Response Format
Provide the answer clearly and concisely, with brief explanation of calculation."""


@dataclass
class Trace:
    """Simple trace for metrics."""
    query: str
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    answer: str = ""


class SimpleAgent:
    """A simple financial analysis agent using direct Anthropic API."""

    def __init__(self):
        self.client = anthropic.Anthropic()
        self.project_root = Path(__file__).parent
        self.df = pd.read_csv(self.project_root / "data" / "FUN_company_pl_actuals_dataset.csv")
        self.traces: list[Trace] = []

    def query(self, question: str) -> Trace:
        """Process a question and return results."""
        messages = [{"role": "user", "content": question}]
        trace = Trace(query=question)

        while True:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )

            trace.input_tokens += response.usage.input_tokens
            trace.output_tokens += response.usage.output_tokens
            trace.total_tokens += response.usage.input_tokens + response.usage.output_tokens

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        trace.answer = block.text
                        break
                self.traces.append(trace)
                return trace

            # Process tool calls
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    trace.tool_calls += 1
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })

            messages.append({"role": "user", "content": tool_results})

    def _execute_tool(self, name: str, input_data: dict) -> str:
        """Execute a tool."""
        try:
            if name == "read_file":
                path = self.project_root / input_data["path"]
                if not path.exists():
                    return f"File not found: {input_data['path']}"
                return path.read_text()

            elif name == "execute_pandas":
                namespace = {
                    "df": self.df.copy(),
                    "pd": pd,
                    "result": None,
                }
                safe_builtins = {
                    "len": len, "range": range, "enumerate": enumerate,
                    "zip": zip, "map": map, "filter": filter, "sorted": sorted,
                    "sum": sum, "min": min, "max": max, "abs": abs, "round": round,
                    "int": int, "float": float, "str": str, "bool": bool,
                    "list": list, "dict": dict, "tuple": tuple, "set": set,
                    "print": print, "isinstance": isinstance, "type": type,
                    "None": None, "True": True, "False": False,
                }
                namespace["__builtins__"] = safe_builtins

                exec(input_data["code"], namespace)
                result = namespace.get("result")

                if result is None:
                    return "Code executed but 'result' variable was not set."

                if isinstance(result, pd.DataFrame):
                    if len(result) > 20:
                        return f"DataFrame ({len(result)} rows):\n{result.head(20).to_string()}\n..."
                    return f"DataFrame:\n{result.to_string()}"
                elif isinstance(result, pd.Series):
                    if len(result) > 20:
                        return f"Series ({len(result)} items):\n{result.head(20).to_string()}\n..."
                    return f"Series:\n{result.to_string()}"
                return str(result)

            return f"Unknown tool: {name}"
        except Exception as e:
            return f"Error: {type(e).__name__}: {str(e)}"

    def get_metrics(self) -> dict:
        """Get aggregated metrics."""
        if not self.traces:
            return {}
        return {
            "total_queries": len(self.traces),
            "total_tokens": sum(t.total_tokens for t in self.traces),
            "total_tool_calls": sum(t.tool_calls for t in self.traces),
            "avg_tokens_per_query": round(sum(t.total_tokens for t in self.traces) / len(self.traces), 2),
        }


# Initialize agent
agent = SimpleAgent()


# ============ API Models ============

class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    tokens: int
    input_tokens: int
    output_tokens: int
    tool_calls: int


# ============ Endpoints ============

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "ready"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Send a question to the financial analysis agent."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        trace = agent.query(request.question)
        return ChatResponse(
            answer=trace.answer,
            tokens=trace.total_tokens,
            input_tokens=trace.input_tokens,
            output_tokens=trace.output_tokens,
            tool_calls=trace.tool_calls,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


@app.get("/metrics")
def get_metrics():
    """Get aggregated metrics for all queries."""
    metrics = agent.get_metrics()
    if not metrics:
        raise HTTPException(status_code=404, detail="No queries recorded yet")
    return metrics


@app.post("/reset")
def reset():
    """Reset metrics."""
    agent.traces.clear()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
