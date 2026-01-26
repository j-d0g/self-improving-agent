"""
Solver Agent for ACE Pipeline

The Solver executes queries and tracks which knowledge bullets were used.
Supports parallel batch execution for efficient training.

Key differences from V1 LearnerAgent:
- Tracks bullet_ids_used for Reflector feedback
- No background improvement (that's Reflector/Curator's job)
- Simpler interface focused on query execution
- Multi-turn support: maintains conversation context across queries
"""

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from claude_agent_sdk.types import StreamEvent

logger = logging.getLogger(__name__)

# Bullet ID pattern for extraction from agent responses
BULLET_ID_PATTERN = re.compile(r'\[([a-z]+-\d{5})\]')


@dataclass
class SolverResult:
    """Result from a single Solver query."""
    query: str
    answer: str
    bullet_ids_used: list[str]
    run_id: str

    # Metrics
    latency_seconds: float = 0.0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_tool_calls: int = 0
    empty_tool_calls: int = 0  # Tool calls that returned empty/no output

    # Full execution trace
    turns: list[dict] = field(default_factory=list)

    # Ground truth for Reflector (set by caller)
    expected_answer: str | None = None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "query": self.query,
            "answer": self.answer,
            "bullet_ids_used": self.bullet_ids_used,
            "expected_answer": self.expected_answer,
            "latency_seconds": self.latency_seconds,
            "total_tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_cost_usd": self.total_cost_usd,
            "total_tool_calls": self.total_tool_calls,
            "empty_tool_calls": self.empty_tool_calls,
            "turns": self.turns,
        }


def extract_bullet_ids(text: str) -> list[str]:
    """Extract all bullet IDs mentioned in text.

    Bullet IDs are in format: [prefix-NNNNN] e.g., [ex-00001], [sch-00003]
    """
    return list(set(BULLET_ID_PATTERN.findall(text)))


def _format_tool_summary(tool_input: dict) -> str:
    """Format tool input for display."""
    if "file_path" in tool_input:
        return f" → {tool_input['file_path']}"
    if "command" in tool_input:
        cmd = tool_input["command"]
        return f" → {cmd[:57]}..." if len(cmd) > 60 else f" → {cmd}"
    if "pattern" in tool_input:
        return f" → pattern: {tool_input['pattern']}"
    return ""


def _extract_tool_output(content) -> str | None:
    """Extract text from tool result content."""
    if content is None:
        return None
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(b.get("text", b)) if isinstance(b, dict) else str(b)
            for b in content
        )
    return str(content)


class SolverAgent:
    """Query execution agent with bullet tracking and multi-turn support.

    The SolverAgent can be used in two modes:

    1. Single-turn mode (default): Each `solve()` call creates a fresh session.
       Good for independent queries where context doesn't need to be preserved.

    2. Multi-turn mode: Use as async context manager to maintain conversation
       context across multiple queries. Claude remembers previous exchanges.

       ```python
       async with SolverAgent() as solver:
           result1 = await solver.solve("What was revenue in 2023?")
           result2 = await solver.solve("How does that compare to 2022?")  # Remembers!
       ```
    """

    DEFAULT_MODEL = "claude-haiku-4-5"

    def __init__(
        self,
        knowledge_dir: Path | None = None,
        dataset_path: Path | None = None,
        model: str | None = None,
        max_budget_usd: float = 0.50,
        max_turns: int = 20,
        stream_output: bool = True,
    ):
        """Initialize the Solver.

        Args:
            knowledge_dir: Path to knowledge files (schema.md, examples.md, functions.py)
            dataset_path: Path to the P&L dataset CSV
            model: Model to use (default: Haiku 4.5)
            max_budget_usd: Maximum budget per query
            max_turns: Maximum agent turns per query
            stream_output: Whether to print streaming output
        """
        self.ace_root = Path(__file__).parent
        self.project_root = self.ace_root.parent  # agemo/
        self.knowledge_dir = knowledge_dir or self.ace_root / "knowledge"
        # Dataset lives in agent/data/
        self.dataset_path = dataset_path or (self.project_root / "agent" / "data" / "FUN_company_pl_actuals_dataset.csv")
        self.model = model or self.DEFAULT_MODEL
        self.max_budget_usd = max_budget_usd
        self.max_turns = max_turns
        self.stream_output = stream_output

        # Load system prompt
        self.system_prompt = self._build_system_prompt()

        # Multi-turn session state
        self._client: ClaudeSDKClient | None = None
        self._turn_count: int = 0

    def _get_options(self) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions for this solver."""
        return ClaudeAgentOptions(
            model=self.model,
            max_turns=self.max_turns,
            system_prompt=self.system_prompt,
            cwd=str(self.ace_root),
            allowed_tools=["Read", "Bash", "Grep", "Glob"],
            include_partial_messages=True,
            permission_mode="acceptEdits",
            max_budget_usd=self.max_budget_usd,
        )

    async def __aenter__(self) -> "SolverAgent":
        """Enter multi-turn mode. Claude will remember context across queries."""
        self._client = ClaudeSDKClient(options=self._get_options())
        await self._client.connect()
        self._turn_count = 0
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit multi-turn mode and disconnect."""
        if self._client:
            await self._client.disconnect()
            self._client = None
        self._turn_count = 0

    @property
    def is_multi_turn(self) -> bool:
        """Check if we're in multi-turn mode (using context manager)."""
        return self._client is not None

    @property
    def turn_count(self) -> int:
        """Number of turns completed in current multi-turn session."""
        return self._turn_count

    def _build_system_prompt(self) -> str:
        """Build system prompt with bullet tracking instructions."""
        return f"""You are a data analysis assistant. You answer natural language questions about tabular data by writing and executing Python code.

## CRITICAL: Bullet Tracking

The knowledge files use bullet format with IDs like [ex-00001] or [sch-00003].

**When you use information from a bullet, you MUST cite it in your response.**

Example:
- If you use the CAGR formula from [ex-00001], write: "Using the CAGR pattern from [ex-00001]..."
- If you check the valid products from [sch-00012], write: "According to [sch-00012], valid products are..."

This citation is MANDATORY for learning feedback.

## Core Behaviors

### 1. Interpret Before Executing
Before running any code, translate the query into a precise statement:

```
**Interpretation:**
Your query: "[original query]"
I understand this as: [precise restatement with explicit filters, metrics, and aggregations]
```

### 2. Gather Context
Read knowledge files before writing code:
- knowledge/schema.md - Column definitions, valid values, formulas (bullets start with [sch-])
- knowledge/examples.md - Query patterns with working code (bullets start with [ex-])
- knowledge/functions.py - Reusable helper functions

### 3. Show All Work
Always show the complete code you're executing. Both successful and failed attempts are valuable.

### 4. Be Transparent About Results
After execution, explain what happened and whether results make sense.

### 5. No Guessing
If you don't know something, say so. If data doesn't exist, report that. Never fabricate results.

## Available Tools
- Read: Read files from the filesystem
- Bash: Execute shell commands (use for running Python/pandas code)

## Dataset Location
The dataset is at: {self.dataset_path}

Example execution pattern:
```bash
python3 -c "
import pandas as pd
df = pd.read_csv('{self.dataset_path}')
# Your analysis code here
print(result)
"
```

## Response Format
After completing your analysis, provide:
1. The answer to the user's question (clear and concise)
2. Brief explanation of how you calculated it
3. List of bullet IDs used: [ex-00001], [sch-00003], etc.
"""

    async def _process_response(
        self,
        response_iter: AsyncIterator,
        result: SolverResult,
    ) -> list[str]:
        """Process response messages and update result. Returns all collected text."""
        all_text = []
        current_turn: dict | None = None
        pending_tool_calls: dict[str, dict] = {}
        streaming_tool_name: str | None = None
        streaming_tool_json = ""

        async for message in response_iter:
            # StreamEvent: Real-time output
            if isinstance(message, StreamEvent):
                event = message.event
                event_type = event.get("type")

                if event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    delta_type = delta.get("type")

                    if delta_type == "text_delta":
                        text = delta.get("text", "")
                        all_text.append(text)
                        if self.stream_output:
                            print(text, end="", flush=True)
                    elif delta_type == "input_json_delta":
                        streaming_tool_json += delta.get("partial_json", "")

                elif event_type == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        streaming_tool_name = block.get("name")
                        streaming_tool_json = ""
                        if self.stream_output:
                            print(f"\n[Tool] {streaming_tool_name}", end="", flush=True)

                elif event_type == "content_block_stop":
                    if streaming_tool_name and streaming_tool_json and self.stream_output:
                        try:
                            tool_input = json.loads(streaming_tool_json)
                            print(_format_tool_summary(tool_input), flush=True)
                        except json.JSONDecodeError:
                            print(flush=True)
                        streaming_tool_name = None
                        streaming_tool_json = ""

                continue

            # AssistantMessage: Turn tracking
            if isinstance(message, AssistantMessage):
                if current_turn and (current_turn["thinking"] or current_turn["tool_calls"]):
                    current_turn["thinking"] = current_turn["thinking"].strip()
                    result.turns.append(current_turn)

                current_turn = {"thinking": "", "tool_calls": []}

                for block in message.content:
                    if isinstance(block, ThinkingBlock):
                        thinking = getattr(block, 'thinking', None) or getattr(block, 'text', '')
                        current_turn["thinking"] += thinking + "\n"
                        all_text.append(thinking)

                    elif isinstance(block, TextBlock):
                        current_turn["thinking"] += block.text + "\n"
                        all_text.append(block.text)
                        result.answer = block.text

                    elif isinstance(block, ToolUseBlock):
                        result.total_tool_calls += 1
                        tool_call = {
                            "tool": block.name,
                            "input": block.input,
                            "output": None,
                        }
                        current_turn["tool_calls"].append(tool_call)
                        if block.id:
                            pending_tool_calls[block.id] = tool_call

                    elif isinstance(block, ToolResultBlock):
                        tool_id = block.tool_use_id
                        output = _extract_tool_output(block.content)
                        if tool_id and tool_id in pending_tool_calls:
                            pending_tool_calls[tool_id]["output"] = output

                continue

            # ResultMessage: Usage metrics
            if isinstance(message, ResultMessage):
                if message.usage:
                    result.input_tokens = message.usage.get('input_tokens', 0)
                    result.output_tokens = message.usage.get('output_tokens', 0)
                    result.total_tokens = result.input_tokens + result.output_tokens
                if message.total_cost_usd:
                    result.total_cost_usd = message.total_cost_usd
                continue

            # Standalone ToolResultBlock
            if isinstance(message, ToolResultBlock):
                tool_id = message.tool_use_id
                output = _extract_tool_output(message.content)
                if tool_id and tool_id in pending_tool_calls:
                    pending_tool_calls[tool_id]["output"] = output
                continue

        # Finalize last turn
        if current_turn and (current_turn["thinking"] or current_turn["tool_calls"]):
            current_turn["thinking"] = current_turn["thinking"].strip()
            result.turns.append(current_turn)

        return all_text

    async def solve(
        self,
        query: str,
        run_id: str | None = None,
        expected_answer: str | None = None,
    ) -> SolverResult:
        """Execute a single query.

        In multi-turn mode (when using context manager), Claude remembers
        previous exchanges. Follow-up questions can reference prior context.

        In single-turn mode, each call creates a fresh session.

        Args:
            query: The question to answer
            run_id: Optional run ID for tracking
            expected_answer: Optional ground truth for Reflector

        Returns:
            SolverResult with answer and bullet_ids_used
        """
        import uuid
        run_id = run_id or uuid.uuid4().hex[:12]

        result = SolverResult(
            query=query,
            answer="",
            bullet_ids_used=[],
            run_id=run_id,
            expected_answer=expected_answer,
        )

        start_time = time.time()

        try:
            if self._client:
                # Multi-turn mode: reuse existing client connection
                await self._client.query(query)
                all_text = await self._process_response(
                    self._client.receive_response(),
                    result,
                )
                self._turn_count += 1
            else:
                # Single-turn mode: create fresh client
                async with ClaudeSDKClient(options=self._get_options()) as client:
                    await client.query(query)
                    all_text = await self._process_response(
                        client.receive_response(),
                        result,
                    )

        except Exception as e:
            logger.error(f"Solver error for {run_id}: {e}", exc_info=True)
            result.answer = f"Error: {e}"
            all_text = []

        result.latency_seconds = time.time() - start_time

        # Extract bullet IDs from all text
        full_text = "\n".join(all_text)
        result.bullet_ids_used = extract_bullet_ids(full_text)

        # Count empty tool calls (no output or empty string)
        for turn in result.turns:
            for tool_call in turn.get("tool_calls", []):
                output = tool_call.get("output")
                if output is None or (isinstance(output, str) and not output.strip()):
                    result.empty_tool_calls += 1

        if self.stream_output:
            print()  # Newline after streaming

        return result

    async def solve_batch(
        self,
        queries: list[dict],
        concurrency: int | None = None,
    ) -> list[SolverResult]:
        """Execute a batch of queries in parallel.

        Args:
            queries: List of dicts with 'query' and optional 'expected_answer', 'run_id'
            concurrency: Max concurrent queries (default: all at once)

        Returns:
            List of SolverResults in same order as queries
        """
        if concurrency is None:
            # Run all concurrently
            tasks = [
                self.solve(
                    query=q["query"],
                    run_id=q.get("run_id"),
                    expected_answer=q.get("expected_answer"),
                )
                for q in queries
            ]
            return await asyncio.gather(*tasks)

        # Semaphore-limited concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def limited_solve(q: dict) -> SolverResult:
            async with semaphore:
                return await self.solve(
                    query=q["query"],
                    run_id=q.get("run_id"),
                    expected_answer=q.get("expected_answer"),
                )

        tasks = [limited_solve(q) for q in queries]
        return await asyncio.gather(*tasks)


