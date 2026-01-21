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
)

from tracing import ExecutionTrace, SessionTrace, AgentMetrics
from prompts import load_prompt

# Configure logging for background tasks
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track background tasks for graceful shutdown
_background_tasks: set[asyncio.Task] = set()


async def wait_for_background_tasks(timeout: float = 30.0) -> None:
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

    def __init__(
        self,
        dataset_path: str = "data/FUN_company_pl_actuals_dataset.csv",
        log_traces: bool = True,
        enable_background_improve: bool = True,
    ):
        """Initialize the agent."""
        self.project_root = Path(__file__).parent
        self.dataset_path = self.project_root / dataset_path
        self.sessions_dir = self.project_root / "logs" / "sessions"
        self.reflections_dir = self.project_root / "logs" / "reflections"
        self.log_traces = log_traces
        self.enable_background_improve = enable_background_improve

        # Load system prompt from file
        self.system_prompt = load_prompt("learner.txt")
        self.improver_prompt = load_prompt("improver.txt")

        # Verify dataset exists
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")

        # Metrics tracking
        self.metrics = AgentMetrics()
        self.session = SessionTrace()  # Session-level trace for full conversation

        if self.log_traces:
            self.sessions_dir.mkdir(parents=True, exist_ok=True)
            self.reflections_dir.mkdir(parents=True, exist_ok=True)

    def save_session(self) -> str | None:
        """Save the session trace (call when conversation ends)."""
        if self.log_traces and self.session.queries:
            return self.session.save(self.sessions_dir)
        return None

    def query(self, question: str, run_id: str = None) -> dict:
        """Process a user question through the agent loop."""
        return asyncio.run(self._query_async(question, run_id=run_id))

    def find_reflection_log(self, run_id: str = None) -> Path | None:
        """Find a reflection log by run_id, or most recent if no run_id."""
        if not self.reflections_dir.exists():
            return None

        if run_id:
            # Look for specific run_id file
            log_file = self.reflections_dir / f"{run_id}.md"
            return log_file if log_file.exists() else None

        # Fallback: find most recent (for backwards compatibility)
        log_files = list(self.reflections_dir.glob("*.md"))
        if not log_files:
            return None
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        return log_files[0]

    async def _background_improve(self, session_log_path: Path) -> None:
        """Run the improver agent in the background (multi-turn)."""
        try:
            logger.info(f"Background improvement starting for: {session_log_path.name}")

            options = ClaudeAgentOptions(
                max_turns=15,
                system_prompt=self.improver_prompt,
                cwd=str(self.project_root),
                allowed_tools=["Read", "Write", "Edit", "Grep", "Glob", "Bash"],
            )

            prompt = f"""Read the session log at `{session_log_path}` and apply any improvements listed in the ## Improvements section.

Only apply improvements that are actionable. Mark completed items with [x]."""

            async with ClaudeSDKClient(options=options) as client:
                await client.query(prompt)
                async for message in client.receive_response():
                    # Silent processing - don't print to user
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                logger.debug(f"Improver: {block.text[:100]}...")

            logger.info("Background improvement completed")

        except Exception as e:
            logger.error(f"Background improvement failed: {e}")

    async def _query_async(self, question: str, run_id: str = None) -> dict:
        """Async implementation of query with multi-turn support."""
        trace = ExecutionTrace(query=question)
        # Use provided run_id or the one generated by trace
        if run_id:
            trace.run_id = run_id
        start_time = time.time()
        current_turn = None  # Created fresh for each AssistantMessage
        final_answer = ""
        pending_tool_calls = {}  # Track tool calls by id for matching with results

        # Inject run_id into the question for the LLM to use in reflection log filename
        question_with_run_id = f"[RUN_ID: {trace.run_id}]\n\n{question}"

        options = ClaudeAgentOptions(
            max_turns=20,
            system_prompt=self.system_prompt,
            cwd=str(self.project_root),
            allowed_tools=["Read", "Write", "Bash", "Grep", "Glob"],
        )

        def _extract_tool_output(content) -> str | None:
            """Extract string output from tool result content."""
            if content is None:
                return None
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                # If content is list of blocks, extract text
                parts = []
                for b in content:
                    if isinstance(b, dict):
                        parts.append(str(b.get("text", b)))
                    else:
                        parts.append(str(b))
                return "\n".join(parts)
            return str(content)

        def _process_tool_result(block, tool_id=None):
            """Process a tool result block and update pending tool calls."""
            # Try multiple ways to get the tool ID
            if tool_id is None:
                tool_id = getattr(block, 'tool_use_id', None)
            if tool_id is None:
                tool_id = getattr(block, 'id', None)
            
            output = _extract_tool_output(block.content)
            
            if tool_id and tool_id in pending_tool_calls:
                pending_tool_calls[tool_id]["output"] = output
            elif current_turn and current_turn["tool_calls"]:
                # Fallback: match to the last tool call in current turn that doesn't have output
                for tool_call in reversed(current_turn["tool_calls"]):
                    if tool_call.get("output") is None:
                        tool_call["output"] = output
                        break

        async with ClaudeSDKClient(options=options) as client:
            await client.query(question_with_run_id)
            async for message in client.receive_response():
                try:
                    # Handle AssistantMessage - each one is a new turn
                    if isinstance(message, AssistantMessage):
                        # Save previous turn if exists
                        if current_turn and (current_turn["thinking"] or current_turn["tool_calls"]):
                            current_turn["thinking"] = current_turn["thinking"].strip()
                            trace.turns.append(current_turn)

                        # Start new turn
                        current_turn = {"thinking": "", "tool_calls": []}

                        for block in message.content:
                            if isinstance(block, ThinkingBlock):
                                current_turn["thinking"] += block.text + "\n"
                            elif isinstance(block, TextBlock):
                                current_turn["thinking"] += block.text + "\n"
                                final_answer = block.text
                            elif isinstance(block, ToolUseBlock):
                                trace.total_tool_calls += 1
                                tool_call = {
                                    "tool": block.name,
                                    "input": block.input,
                                    "output": None,  # Will be filled when result arrives
                                }
                                current_turn["tool_calls"].append(tool_call)
                                # Try to get tool ID for matching with results
                                tool_id = getattr(block, 'id', None) or getattr(block, 'tool_use_id', None)
                                if tool_id:
                                    pending_tool_calls[tool_id] = tool_call
                            elif isinstance(block, ToolResultBlock):
                                _process_tool_result(block)

                    # Handle tool results that may come outside AssistantMessage
                    elif hasattr(message, 'content') and message.content:
                        for block in (message.content if isinstance(message.content, list) else [message.content]):
                            if isinstance(block, ToolResultBlock):
                                _process_tool_result(block)

                    # Handle ResultMessage (contains usage stats)
                    elif isinstance(message, ResultMessage):
                        if hasattr(message, 'usage') and message.usage:
                            trace.input_tokens = message.usage.get('input_tokens', 0)
                            trace.output_tokens = message.usage.get('output_tokens', 0)
                            trace.total_tokens = trace.input_tokens + trace.output_tokens
                        if hasattr(message, 'total_cost_usd') and message.total_cost_usd:
                            trace.total_cost_usd = message.total_cost_usd
                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    # Continue processing - don't let one error stop the trace

        # Finalize last turn
        if current_turn and (current_turn["thinking"] or current_turn["tool_calls"]):
            current_turn["thinking"] = current_turn["thinking"].strip()
            trace.turns.append(current_turn)

        trace.latency_seconds = time.time() - start_time
        trace.final_answer = final_answer

        # Add to metrics and session (session is saved on session end, not per-query)
        self.metrics.add_trace(trace)
        self.session.add_query(trace)
        log_path = None  # Session will be saved via save_session() when conversation ends

        # Trigger background improvement (deterministic: always after learner completes)
        if self.enable_background_improve:
            reflection_log = self.find_reflection_log(run_id=trace.run_id)
            if reflection_log:
                task = asyncio.create_task(self._background_improve(reflection_log))
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
            await wait_for_background_tasks(timeout=30.0)
            print("Done.")

        # Save session trace
        session_path = agent.save_session()
        if session_path:
            print(f"Session trace saved: {session_path}")
    else:
        print("Learner Agent (with background improvement)")
        print("="*50)
        print("Workflow: Query → Answer → Background Improvement")
        print()
        print("Commands:")
        print("  quit              - Exit (waits for background tasks)")
        print("  metrics           - Show session metrics")
        print("  no-improve <q>    - Answer without background improvement")
        print()

        while True:
            try:
                question = input("You: ").strip()
                if not question:
                    continue
                if question.lower() == "quit":
                    # Wait for background tasks
                    if _background_tasks:
                        print("\nWaiting for background tasks...")
                        await wait_for_background_tasks(timeout=10.0)
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

                print("\nThinking...")
                result = await agent._query_async(question)
                print("\n" + "-"*40)
                print(result["answer"])

                trace = result["trace"]
                print(f"\n[Latency: {trace.latency_seconds:.1f}s, Tokens: {trace.total_tokens}, Tool calls: {trace.total_tool_calls}, Cost: ${trace.total_cost_usd:.4f}]")
                if agent.enable_background_improve and _background_tasks:
                    print("[Background improvement running...]")
                print("-"*40 + "\n")

            except KeyboardInterrupt:
                print("\nExiting...")
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
