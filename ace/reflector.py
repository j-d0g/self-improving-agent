"""
Reflector Agent for ACE Pipeline

The Reflector evaluates Solver results and tags bullets as helpful/harmful.
Runs on EVERY query (success and failure) to build signal over time.

Key responsibilities:
- Judge answer correctness using LLM
- Tag each bullet_id_used as helpful/harmful/neutral
- Generate insights for failures
- Append tags to logs/tags.jsonl
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .playbook_utils import BulletTag, Tag
from .solver import SolverResult

logger = logging.getLogger(__name__)


@dataclass
class ReflectorResult:
    """Result from Reflector analysis of a Solver result."""
    run_id: str
    query: str
    is_correct: bool
    score: float  # 0.0 or 1.0
    judge_reason: str

    # Bullet tagging
    bullet_tags: list[BulletTag] = field(default_factory=list)

    # Insight for failures
    insight: str | None = None

    # Metrics
    latency_seconds: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "query": self.query,
            "is_correct": self.is_correct,
            "score": self.score,
            "judge_reason": self.judge_reason,
            "bullet_tags": [
                {
                    "bullet_id": t.bullet_id,
                    "tag": t.tag.value,
                    "insight": t.insight,
                }
                for t in self.bullet_tags
            ],
            "insight": self.insight,
            "latency_seconds": self.latency_seconds,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
        }


async def judge_answer(query: str, expected: str, actual: str) -> tuple[float, str]:
    """Use Haiku to judge if agent answer matches expected answer.

    Returns: (score, reason)
        score: 0.0 (wrong) or 1.0 (correct)
        reason: Brief explanation
    """
    prompt = f"""Compare the expected answer to the agent's answer for this query.

Query: {query}

Expected Answer: {expected}

Agent Answer: {actual}

Judge as CORRECT (1.0) if:
- The answer conveys the same information as expected
- Numeric values match (allow formatting differences: $1.2M = $1,200,000)
- For "not available" answers, the reason is substantively correct

Judge as WRONG (0.0) if:
- The answer is factually incorrect
- Key information is missing or wrong
- The reasoning leads to a wrong conclusion

Return ONLY a JSON object:
{{"score": <0.0 or 1.0>, "reason": "<brief explanation>"}}"""

    try:
        options = ClaudeAgentOptions(
            model="claude-haiku-4-5",
            max_turns=1,
            system_prompt="You are a judge evaluating answer accuracy. Return only valid JSON.",
            cwd=str(Path(__file__).parent),
            allowed_tools=[],
            permission_mode="acceptEdits",
            max_budget_usd=0.01,
        )

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            response_text = ""
            async for message in client.receive_response():
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            response_text += block.text

        # Parse JSON from response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)
            score = float(result.get("score", 0.0))
            reason = result.get("reason", "No reason provided")
            return (score, reason)

        return (0.0, "Failed to parse judge response")

    except Exception as e:
        return (0.0, f"Judge error: {str(e)[:50]}")


async def tag_bullets(
    query: str,
    answer: str,
    expected: str,
    bullet_ids: list[str],
    is_correct: bool,
) -> tuple[list[BulletTag], str | None]:
    """Use Haiku to tag bullets and generate insight.

    Args:
        query: The original query
        answer: The agent's answer
        expected: The expected answer
        bullet_ids: List of bullet IDs used by the solver
        is_correct: Whether the answer was judged correct

    Returns:
        (list of BulletTags, insight for failures)
    """
    if not bullet_ids:
        return [], None

    outcome = "CORRECT" if is_correct else "INCORRECT"
    insight_instruction = (
        "Generate a brief insight about what went wrong and what knowledge would help."
        if not is_correct else ""
    )
    insight_field = (
        '"insight": "<brief explanation of what went wrong>"'
        if not is_correct else '"insight": null'
    )

    prompt = f"""Analyze which knowledge bullets helped or harmed the agent's answer.

Query: {query}
Expected Answer: {expected}
Agent Answer: {answer}
Outcome: {outcome}

The agent cited these knowledge bullets: {bullet_ids}

For EACH bullet ID, determine its contribution:
- HELPFUL: The bullet provided correct information that led toward the right answer
- HARMFUL: The bullet provided incorrect or misleading information
- NEUTRAL: The bullet was cited but didn't significantly affect the answer

{insight_instruction}

Return ONLY a JSON object:
{{
    "tags": {{
        "<bullet_id>": "helpful" | "harmful" | "neutral",
        ...
    }},
    {insight_field}
}}"""

    try:
        options = ClaudeAgentOptions(
            model="claude-haiku-4-5",
            max_turns=1,
            system_prompt="You analyze knowledge bullet effectiveness. Return only valid JSON.",
            cwd=str(Path(__file__).parent),
            allowed_tools=[],
            permission_mode="acceptEdits",
            max_budget_usd=0.02,
        )

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            response_text = ""
            async for message in client.receive_response():
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            response_text += block.text

        # Parse JSON
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)

            tags_dict = result.get("tags", {})
            insight = result.get("insight")

            bullet_tags = []
            for bullet_id in bullet_ids:
                tag_str = tags_dict.get(bullet_id, "neutral").lower()
                if tag_str == "helpful":
                    tag = Tag.HELPFUL
                elif tag_str == "harmful":
                    tag = Tag.HARMFUL
                else:
                    tag = Tag.NEUTRAL

                bullet_tags.append(BulletTag(
                    bullet_id=bullet_id,
                    tag=tag,
                    insight=insight if tag == Tag.HARMFUL else None,
                    query=query,
                ))

            return bullet_tags, insight

        # Default: mark all as neutral if parsing fails
        return [
            BulletTag(bullet_id=bid, tag=Tag.NEUTRAL, query=query)
            for bid in bullet_ids
        ], None

    except Exception as e:
        logger.error(f"Tag bullets error: {e}")
        return [
            BulletTag(bullet_id=bid, tag=Tag.NEUTRAL, query=query)
            for bid in bullet_ids
        ], None


class Reflector:
    """Evaluates Solver results and tags bullets for learning."""

    def __init__(
        self,
        tags_log_path: Path | None = None,
    ):
        """Initialize the Reflector.

        Args:
            tags_log_path: Path to tags.jsonl (append-only log)
        """
        self.ace_root = Path(__file__).parent
        self.tags_log_path = tags_log_path or self.ace_root / "logs" / "tags.jsonl"

        # Ensure logs directory exists
        self.tags_log_path.parent.mkdir(parents=True, exist_ok=True)

    async def reflect(self, solver_result: SolverResult) -> ReflectorResult:
        """Reflect on a single Solver result.

        Args:
            solver_result: Result from SolverAgent.solve()

        Returns:
            ReflectorResult with correctness judgment and bullet tags
        """
        import time
        start_time = time.time()

        result = ReflectorResult(
            run_id=solver_result.run_id,
            query=solver_result.query,
            is_correct=False,
            score=0.0,
            judge_reason="",
        )

        # Step 1: Judge correctness
        if solver_result.expected_answer:
            score, reason = await judge_answer(
                solver_result.query,
                solver_result.expected_answer,
                solver_result.answer,
            )
            result.score = score
            result.is_correct = score >= 0.5
            result.judge_reason = reason
        else:
            # No expected answer - can't judge
            result.score = 0.0
            result.is_correct = False
            result.judge_reason = "No expected answer provided"

        # Step 2: Tag bullets (runs on both correct and incorrect)
        if solver_result.bullet_ids_used:
            tags, insight = await tag_bullets(
                query=solver_result.query,
                answer=solver_result.answer,
                expected=solver_result.expected_answer or "",
                bullet_ids=solver_result.bullet_ids_used,
                is_correct=result.is_correct,
            )
            result.bullet_tags = tags
            result.insight = insight

            # Add run_id to each tag
            for tag in result.bullet_tags:
                tag.run_id = solver_result.run_id

        result.latency_seconds = time.time() - start_time

        # Step 3: Append to tags log
        self._append_tags(result)

        return result

    async def reflect_batch(
        self,
        solver_results: list[SolverResult],
        concurrency: int | None = None,
    ) -> list[ReflectorResult]:
        """Reflect on a batch of Solver results in parallel.

        Args:
            solver_results: List of SolverResults to reflect on
            concurrency: Max concurrent reflections (default: all at once)

        Returns:
            List of ReflectorResults in same order
        """
        if concurrency is None:
            tasks = [self.reflect(r) for r in solver_results]
            return await asyncio.gather(*tasks)

        semaphore = asyncio.Semaphore(concurrency)

        async def limited_reflect(r: SolverResult) -> ReflectorResult:
            async with semaphore:
                return await self.reflect(r)

        tasks = [limited_reflect(r) for r in solver_results]
        return await asyncio.gather(*tasks)

    def _append_tags(self, result: ReflectorResult) -> None:
        """Append tags to the persistent log."""
        timestamp = datetime.now().isoformat()

        with open(self.tags_log_path, "a") as f:
            for tag in result.bullet_tags:
                entry = {
                    "timestamp": timestamp,
                    "run_id": result.run_id,
                    "bullet_id": tag.bullet_id,
                    "tag": tag.tag.value,
                    "is_correct": result.is_correct,
                    "query": tag.query,
                    "insight": tag.insight,
                }
                f.write(json.dumps(entry) + "\n")

    def read_pending_tags(self) -> list[dict]:
        """Read all tags from the log file.

        Returns:
            List of tag entries (dicts)
        """
        if not self.tags_log_path.exists():
            return []

        tags = []
        with open(self.tags_log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        tags.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return tags

    def clear_tags(self) -> int:
        """Clear the tags log file.

        Returns:
            Number of tags that were cleared
        """
        count = len(self.read_pending_tags())
        if self.tags_log_path.exists():
            self.tags_log_path.unlink()
        return count


async def test_reflector():
    """Test the Reflector with a mock Solver result."""
    from .solver import SolverResult

    # Create mock solver result
    solver_result = SolverResult(
        query="What was the total Net Revenue for Product A in 2023?",
        answer="The total Net Revenue for Product A in 2023 was $12,345,678.90",
        bullet_ids_used=["sch-00016", "ex-00002"],
        run_id="test123",
        expected_answer="$12,345,678.90",
    )

    reflector = Reflector()

    print("Testing Reflector...")
    result = await reflector.reflect(solver_result)

    print(f"\nReflector Result:")
    print(f"  Run ID: {result.run_id}")
    print(f"  Is Correct: {result.is_correct}")
    print(f"  Score: {result.score}")
    print(f"  Judge Reason: {result.judge_reason}")
    print(f"  Bullet Tags:")
    for tag in result.bullet_tags:
        print(f"    - {tag.bullet_id}: {tag.tag.value}")
    print(f"  Insight: {result.insight}")
    print(f"  Latency: {result.latency_seconds:.1f}s")

    # Check tags log
    tags = reflector.read_pending_tags()
    print(f"\nTags log has {len(tags)} entries")


if __name__ == "__main__":
    asyncio.run(test_reflector())
