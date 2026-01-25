"""
Learner Agent

A coding agent that answers financial questions about P&L data using the Claude Code SDK.
Uses SDK's built-in tools (Bash, Read) for execution.

Workflow (deterministic, no orchestrator):
  User → Learner Agent → Answer + Session Log
                              ↓ (automatic)
                         Improver (background)
"""

from pathlib import Path
import asyncio
import logging
import time

# Note: Claude Code SDK uses Claude CLI authentication, not ANTHROPIC_API_KEY
# Don't load .env as it may conflict with CLI auth

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    ThinkingBlock,
    HookMatcher,
)
from claude_agent_sdk.types import StreamEvent, HookContext

from tracing import ExecutionTrace, SessionTrace, AgentMetrics
from prompts import load_prompt
from tools import pl_tools_server, PL_TOOL_NAMES

# Configure logging for background tasks
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track background tasks for graceful shutdown
_background_tasks: set[asyncio.Task] = set()


async def validate_improver_writes(
    input_data: dict,
    tool_use_id: str | None,
    context: HookContext,
) -> dict:
    """Hook to ensure improver only writes to knowledge/ directory.

    This enforces the security rule that the improver agent can only modify
    files in the knowledge/ directory, preventing accidental changes to
    agent code, prompts, or other system files.
    """
    tool_name = input_data.get("tool_name", "")
    if tool_name not in ["Write", "Edit"]:
        return {}

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    # Normalize path and check if it's in knowledge/
    # Handle both absolute and relative paths
    path = Path(file_path)
    path_str = str(path)

    # Allow if path contains knowledge/ directory
    if "knowledge/" in path_str or path_str.startswith("knowledge"):
        return {}

    # Also allow logs/reflections for improver trace writing
    if "logs/" in path_str:
        return {}

    # Block all other writes
    logger.warning(f"Improver blocked from writing to: {file_path}")
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Improver restricted to knowledge/ directory. Attempted: {file_path}"
        }
    }


def _format_tool_input_summary(tool_input: dict) -> str:
    """Format tool input for display during streaming."""
    if "file_path" in tool_input:
        return f" → {tool_input['file_path']}"
    if "command" in tool_input:
        cmd = tool_input["command"]
        return f" → {cmd[:57]}..." if len(cmd) > 60 else f" → {cmd}"
    if "pattern" in tool_input:
        return f" → pattern: {tool_input['pattern']}"
    return ""


def _extract_tool_output(content) -> str | None:
    """Extract text output from tool result content."""
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


async def process_agent_stream(
    message_stream,
    trace: ExecutionTrace,
    tool_prefix: str = "Tool",
    stream_output: bool = True,
) -> str:
    """Process agent message stream, populate trace, return final answer.

    Handles SDK message types:
    - StreamEvent: Real-time streaming output (text deltas, tool calls)
    - AssistantMessage: Turn tracking (thinking, text, tool calls)
    - ResultMessage: Usage stats (tokens, cost) - canonical source for metrics

    Args:
        message_stream: Async iterator of SDK messages
        trace: ExecutionTrace to populate (mutated in place)
        tool_prefix: Prefix for tool output display (e.g., "Tool", "Improver Tool")
        stream_output: Whether to print streaming output

    Returns:
        Final answer text
    """
    import json as json_module

    # State for turn tracking
    current_turn: dict | None = None
    final_answer = ""

    # State for tool result matching (tool_id -> tool_call dict)
    pending_tool_calls: dict[str, dict] = {}

    # State for streaming tool input display
    streaming_tool_name: str | None = None
    streaming_tool_json = ""

    async for message in message_stream:
        try:
            # StreamEvent: Real-time output for interactive display
            if isinstance(message, StreamEvent):
                event = message.event
                event_type = event.get("type")

                if event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    delta_type = delta.get("type")

                    if delta_type == "text_delta" and stream_output:
                        print(delta.get("text", ""), end="", flush=True)
                    elif delta_type == "input_json_delta":
                        streaming_tool_json += delta.get("partial_json", "")

                elif event_type == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        streaming_tool_name = block.get("name")
                        streaming_tool_json = ""
                        if stream_output:
                            print(f"\n[{tool_prefix}] {streaming_tool_name}", end="", flush=True)

                elif event_type == "content_block_stop":
                    if streaming_tool_name and streaming_tool_json and stream_output:
                        try:
                            tool_input = json_module.loads(streaming_tool_json)
                            print(_format_tool_input_summary(tool_input), flush=True)
                        except json_module.JSONDecodeError:
                            print(flush=True)
                        streaming_tool_name = None
                        streaming_tool_json = ""

                continue  # Don't process StreamEvents further

            # AssistantMessage: Each one represents a turn in the conversation
            if isinstance(message, AssistantMessage):
                # Save previous turn if it has content
                if current_turn and (current_turn["thinking"] or current_turn["tool_calls"]):
                    current_turn["thinking"] = current_turn["thinking"].strip()
                    trace.turns.append(current_turn)

                # Start new turn
                current_turn = {"thinking": "", "tool_calls": []}

                for block in message.content:
                    if isinstance(block, ThinkingBlock):
                        # ThinkingBlock uses .thinking attribute per SDK docs
                        thinking_text = getattr(block, 'thinking', None) or getattr(block, 'text', '')
                        current_turn["thinking"] += thinking_text + "\n"

                    elif isinstance(block, TextBlock):
                        current_turn["thinking"] += block.text + "\n"
                        final_answer = block.text

                    elif isinstance(block, ToolUseBlock):
                        trace.total_tool_calls += 1
                        tool_call = {
                            "tool": block.name,
                            "input": block.input,
                            "output": None,
                        }
                        current_turn["tool_calls"].append(tool_call)
                        # Track for result matching
                        if block.id:
                            pending_tool_calls[block.id] = tool_call

                    elif isinstance(block, ToolResultBlock):
                        # Tool result within AssistantMessage
                        tool_id = block.tool_use_id
                        output = _extract_tool_output(block.content)
                        if tool_id and tool_id in pending_tool_calls:
                            pending_tool_calls[tool_id]["output"] = output

                continue

            # ResultMessage: Canonical source for usage and cost metrics
            if isinstance(message, ResultMessage):
                if message.usage:
                    trace.input_tokens = message.usage.get('input_tokens', 0)
                    trace.output_tokens = message.usage.get('output_tokens', 0)
                    trace.total_tokens = trace.input_tokens + trace.output_tokens
                if message.total_cost_usd:
                    trace.total_cost_usd = message.total_cost_usd
                continue

            # Standalone ToolResultBlock (may come outside AssistantMessage)
            if isinstance(message, ToolResultBlock):
                tool_id = message.tool_use_id
                output = _extract_tool_output(message.content)
                if tool_id and tool_id in pending_tool_calls:
                    pending_tool_calls[tool_id]["output"] = output
                continue

            # Handle any other message types with nested tool results
            if hasattr(message, 'content') and message.content:
                blocks = message.content if isinstance(message.content, list) else [message.content]
                for block in blocks:
                    if isinstance(block, ToolResultBlock):
                        tool_id = block.tool_use_id
                        output = _extract_tool_output(block.content)
                        if tool_id and tool_id in pending_tool_calls:
                            pending_tool_calls[tool_id]["output"] = output

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    # Finalize last turn
    if current_turn and (current_turn["thinking"] or current_turn["tool_calls"]):
        current_turn["thinking"] = current_turn["thinking"].strip()
        trace.turns.append(current_turn)

    trace.final_answer = final_answer
    return final_answer


async def wait_for_background_tasks(timeout: float = 60.0) -> None:
    """Wait for all background tasks to complete."""
    if not _background_tasks:
        return
    logger.info(f"Waiting for {len(_background_tasks)} background task(s)...")
    try:
        await asyncio.wait_for(
            asyncio.gather(*_background_tasks, return_exceptions=True),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.warning(f"Background tasks did not complete within {timeout}s")


class LearnerAgent:
    """Learner agent with full logging and background improvement."""

    # Model constants
    DEFAULT_LEARNER_MODEL = "claude-haiku-4-5"
    DEFAULT_IMPROVER_MODEL = "claude-sonnet-4-5"

    def __init__(
        self,
        dataset_path: str = "data/FUN_company_pl_actuals_dataset.csv",
        log_traces: bool = True,
        enable_background_improve: bool = True,
        max_budget_usd: float = 0.50,
        improver_max_budget_usd: float = 0.25,
        learner_model: str | None = None,
        improver_model: str | None = None,
        stream_output: bool = True,
    ):
        """Initialize the agent.

        Args:
            dataset_path: Path to the P&L dataset CSV.
            log_traces: Whether to save session traces to logs/.
            enable_background_improve: Whether to run improver after each query.
            max_budget_usd: Maximum budget per learner query (default $0.50).
            improver_max_budget_usd: Maximum budget per improver run (default $0.25).
            learner_model: Model for the learner agent (default: Haiku 3.5).
            improver_model: Model for the improver agent (default: Sonnet 4).
            stream_output: Whether to stream agent output to console (default: True).
        """
        self.learner_model = learner_model or self.DEFAULT_LEARNER_MODEL
        self.improver_model = improver_model or self.DEFAULT_IMPROVER_MODEL
        self.project_root = Path(__file__).parent
        self.dataset_path = self.project_root / dataset_path
        self.sessions_dir = self.project_root / "logs" / "sessions"
        self.reflections_dir = self.project_root / "logs" / "reflections"
        self.log_traces = log_traces
        self.enable_background_improve = enable_background_improve
        self.max_budget_usd = max_budget_usd
        self.improver_max_budget_usd = improver_max_budget_usd
        self.stream_output = stream_output

        # Load system prompt from file
        self.system_prompt = load_prompt("learner.txt")
        self.improver_prompt = load_prompt("improver.txt")

        # Verify dataset exists
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")

        # Metrics tracking
        self.metrics = AgentMetrics()
        self.session = SessionTrace()  # Session-level trace for full conversation

        # Multi-turn client (initialized on first query or via start_session)
        self._client: ClaudeSDKClient | None = None
        self._client_options: ClaudeAgentOptions | None = None

        if self.log_traces:
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            self.reflections_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self) -> str | None:
        """Save the session trace (call when conversation ends)."""
        if self.log_traces and self.session.queries:
            return self.session.save(self.sessions_dir)
        return None

    async def start_session(self) -> None:
        """Start a multi-turn session (opens persistent client)."""
        if self._client is not None:
            return  # Already started

        self._client_options = ClaudeAgentOptions(
            model=self.learner_model,
            max_turns=20,
            system_prompt=self.system_prompt,
            cwd=str(self.project_root),
            allowed_tools=["Read", "Write", "Bash", "Grep", "Glob"],
            include_partial_messages=True,
            permission_mode="acceptEdits",
            setting_sources=["project"],  # Loads CLAUDE.md from project
            max_budget_usd=self.max_budget_usd,  # Cost control
        )
        self._client = ClaudeSDKClient(options=self._client_options)
        await self._client.__aenter__()

    async def end_session(self) -> None:
        """End the multi-turn session (closes client)."""
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None
            self._client_options = None

    def query(self, question: str, run_id: str = None) -> dict:
        """Process a user question through the agent loop (single-turn convenience method)."""
        return asyncio.run(self._query_async(question, run_id=run_id))

    async def _background_improve(self, session_path: Path, run_id: str) -> None:
        """Run the improver agent in the background (multi-turn)."""
        try:
            if self.stream_output:
                print(f"\n[Improver] Starting for run: {run_id}")

            prompt = f"""Read the session trace at `{session_path}`.

Find the query with run_id "{run_id}" and analyze:
1. What the learner was asked
2. How it responded (tool calls, reasoning, final answer)
3. Any errors or inefficiencies in the approach

Apply improvements to the appropriate knowledge file:
- knowledge/schema.md — for data structure, column definitions, valid values
- knowledge/examples.md — for query patterns and working code
- knowledge/functions.py — for reusable helper functions"""

            # Create trace for the improver
            trace = ExecutionTrace(
                query=prompt,
                agent_type="improver",
                source_run_id=run_id,
            )
            start_time = time.time()

            options = ClaudeAgentOptions(
                model=self.improver_model,
                max_turns=15,
                system_prompt=self.improver_prompt,
                cwd=str(self.project_root),
                allowed_tools=["Read", "Write", "Edit", "Grep", "Glob", "Bash"],
                include_partial_messages=True,
                permission_mode="acceptEdits",
                setting_sources=["project"],  # Loads CLAUDE.md from project
                max_budget_usd=self.improver_max_budget_usd,  # Cost control
                hooks={
                    "PreToolUse": [
                        HookMatcher(
                            matcher="Write|Edit",
                            hooks=[validate_improver_writes],
                        ),
                    ],
                },
            )

            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)
                await process_agent_stream(
                    client.receive_response(),
                    trace,
                    tool_prefix="Improver Tool",
                    stream_output=self.stream_output,
                )

            trace.latency_seconds = time.time() - start_time

            # Save improver trace
            improver_dir = self.project_root / "logs" / "improver"
            trace_path = trace.save(improver_dir)
            if self.stream_output:
                print(f"\n[Improver] Completed (trace: {trace_path})")

        except Exception as e:
            if self.stream_output:
                print(f"\n[Improver] Failed: {e}")

    async def _query_async(self, question: str, run_id: str = None) -> dict:
        """Async implementation of query with multi-turn support."""
        trace = ExecutionTrace(query=question, agent_type="learner")
        if run_id:
            trace.run_id = run_id
        start_time = time.time()

        # Inject run_id into the question for the LLM to use in reflection log filename
        question_with_run_id = f"[RUN_ID: {trace.run_id}]\n\n{question}"

        # Use persistent client if session is active, otherwise create temporary one
        if self._client is not None:
            # Multi-turn mode: reuse existing client (conversation history preserved)
            await self._client.query(question_with_run_id)
            final_answer = await process_agent_stream(
                self._client.receive_response(),
                trace,
                tool_prefix="Tool",
                stream_output=self.stream_output,
            )
        else:
            # Single-turn mode: create temporary client
            options = ClaudeAgentOptions(
                model=self.learner_model,
                max_turns=20,
                system_prompt=self.system_prompt,
                cwd=str(self.project_root),
                allowed_tools=["Read", "Write", "Bash", "Grep", "Glob"],
                include_partial_messages=True,
                permission_mode="acceptEdits",
                setting_sources=["project"],  # Loads CLAUDE.md from project
                max_budget_usd=self.max_budget_usd,  # Cost control
            )
            async with ClaudeSDKClient(options=options) as client:
                await client.query(question_with_run_id)
                final_answer = await process_agent_stream(
                    client.receive_response(),
                    trace,
                    tool_prefix="Tool",
                    stream_output=self.stream_output,
                )

        trace.latency_seconds = time.time() - start_time

        # Add to metrics and session
        self.metrics.add_trace(trace)
        self.session.add_query(trace)

        # Save session after each query so improver can read it
        log_path = self.save_session()

        # Trigger background improvement (deterministic: always after learner completes)
        if self.enable_background_improve and log_path:
            session_path = Path(log_path)
            task = asyncio.create_task(self._background_improve(session_path, trace.run_id))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
            logger.info(f"Background improvement task scheduled for {trace.run_id}")

        return {
            "answer": final_answer,
            "trace": trace,
            "log_path": log_path
        }


async def main_async():
    """Async CLI for the agent."""
    import sys
    import traceback

    agent = LearnerAgent()

    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        result = await agent._query_async(question)
        print("\n" + "="*60)
        print("ANSWER:")
        print("="*60)
        print(result["answer"])

        trace = result["trace"]
        print("\n" + "-"*40)
        print("METRICS:")
        print(f"  Latency: {trace.latency_seconds:.1f}s")
        print(f"  Tokens: {trace.total_tokens} (in: {trace.input_tokens}, out: {trace.output_tokens})")
        print(f"  Tool calls: {trace.total_tool_calls}")
        print(f"  Cost: ${trace.total_cost_usd:.4f}")
        print("-"*40)

        # Wait for background improvement
        if _background_tasks:
            print("\nWaiting for background improvement...")
            await wait_for_background_tasks(timeout=60.0)
            print("Done.")

        # Save session trace
        session_path = agent.save_session()
        if session_path:
            print(f"Session trace saved: {session_path}")
    else:
        print("Learner Agent (with background improvement)")
        print("="*50)
        print("Workflow: Query → Answer → Background Improvement")
        print("Mode: Multi-turn (conversation history preserved)")
        print()
        print("Commands:")
        print("  quit              - Exit (waits for background tasks)")
        print("  metrics           - Show session metrics")
        print("  no-improve <q>    - Answer without background improvement")
        print()

        # Start multi-turn session
        await agent.start_session()

        while True:
            try:
                question = (await asyncio.to_thread(input, "You: ")).strip()
                if not question:
                    continue
                if question.lower() == "quit":
                    # End multi-turn session
                    await agent.end_session()
                    # Wait for background tasks
                    if _background_tasks:
                        print("\nWaiting for background tasks...")
                        await wait_for_background_tasks(timeout=30.0)
                    if agent.metrics.traces:
                        print("\n" + "="*40)
                        print("SESSION METRICS:")
                        for k, v in agent.metrics.compute().items():
                            print(f"  {k}: {v}")
                    # Save full session trace
                    session_path = agent.save_session()
                    if session_path:
                        print(f"\nSession trace saved: {session_path}")
                    break
                if question.lower() == "metrics":
                    if agent.metrics.traces:
                        print("\nMETRICS:")
                        for k, v in agent.metrics.compute().items():
                            print(f"  {k}: {v}")
                        print(f"  background_tasks_pending: {len(_background_tasks)}")
                    else:
                        print("No queries yet.")
                    continue

                # Check for no-improve prefix
                if question.lower().startswith("no-improve "):
                    agent.enable_background_improve = False
                    question = question[11:].strip()
                else:
                    agent.enable_background_improve = True

                print()  # Newline before streaming starts
                result = await agent._query_async(question)
                print()  # Newline after streaming ends

                trace = result["trace"]
                print(f"[Latency: {trace.latency_seconds:.1f}s, Tokens: {trace.total_tokens}, Tool calls: {trace.total_tool_calls}, Cost: ${trace.total_cost_usd:.4f}]")
                if agent.enable_background_improve and _background_tasks:
                    print("[Background improvement running...]")
                print("-"*40 + "\n")

            except KeyboardInterrupt:
                print("\nExiting...")
                # End multi-turn session
                await agent.end_session()
                # Save session trace on interrupt too
                session_path = agent.save_session()
                if session_path:
                    print(f"Session trace saved: {session_path}")
                break
            except Exception as e:
                print(f"\nError: {e}\n")
                traceback.print_exc()


def main():
    """Entry point."""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
