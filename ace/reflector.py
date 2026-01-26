"""
Reflector Agent for ACE Pipeline (v2)

The Reflector performs DEEP ANALYSIS of Solver execution traces to understand
what worked, what failed, and why. This goes beyond simple correctness checking.

Key responsibilities:
- Judge answer correctness
- Analyze full execution trace (tool efficiency, reasoning, calculations)
- Perform root cause analysis for failures
- Tag bullets as helpful/harmful/neutral with rationales
- Suggest delta operations for Curator
- Persist detailed logs for debugging and Aggregator consumption
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .playbook_utils import BulletTag, Tag
from .solver import SolverResult

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

class DeltaType(Enum):
    """Types of changes the Reflector can suggest."""
    ADD = "ADD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    STRUCTURAL = "STRUCTURAL"  # New category, merge, restructure


@dataclass
class ToolAnalysis:
    """Analysis of tool usage efficiency."""
    total_calls: int = 0
    redundant_calls: int = 0
    failed_calls: int = 0
    wrong_tool_choices: list[str] = field(default_factory=list)
    assessment: str = ""


@dataclass
class ReasoningAnalysis:
    """Analysis of reasoning/planning quality."""
    flawed_assumptions: list[str] = field(default_factory=list)
    logic_errors: list[str] = field(default_factory=list)
    missed_considerations: list[str] = field(default_factory=list)
    assessment: str = ""


@dataclass
class CalculationAnalysis:
    """Analysis of calculation correctness."""
    errors_found: list[str] = field(default_factory=list)
    assessment: str = ""


@dataclass
class SelfConsistency:
    """Analysis of answer vs actual computation results."""
    is_consistent: bool = True
    inconsistencies: list[str] = field(default_factory=list)


@dataclass
class IssueFound:
    """An issue identified in the execution."""
    category: str  # e.g., "inefficiency", "wrong_approach", "calculation_error"
    description: str
    knowledge_gap: str | None = None  # What knowledge would have helped?


@dataclass
class Analysis:
    """Complete analysis of solver execution."""
    # Component analyses
    tool_analysis: ToolAnalysis = field(default_factory=ToolAnalysis)
    reasoning_analysis: ReasoningAnalysis = field(default_factory=ReasoningAnalysis)
    calculation_analysis: CalculationAnalysis = field(default_factory=CalculationAnalysis)
    self_consistency: SelfConsistency = field(default_factory=SelfConsistency)

    # Issues found
    issues_found: list[IssueFound] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tool_analysis": {
                "total_calls": self.tool_analysis.total_calls,
                "redundant_calls": self.tool_analysis.redundant_calls,
                "failed_calls": self.tool_analysis.failed_calls,
                "wrong_tool_choices": self.tool_analysis.wrong_tool_choices,
                "assessment": self.tool_analysis.assessment,
            },
            "reasoning_analysis": {
                "flawed_assumptions": self.reasoning_analysis.flawed_assumptions,
                "logic_errors": self.reasoning_analysis.logic_errors,
                "missed_considerations": self.reasoning_analysis.missed_considerations,
                "assessment": self.reasoning_analysis.assessment,
            },
            "calculation_analysis": {
                "errors_found": self.calculation_analysis.errors_found,
                "assessment": self.calculation_analysis.assessment,
            },
            "self_consistency": {
                "is_consistent": self.self_consistency.is_consistent,
                "inconsistencies": self.self_consistency.inconsistencies,
            },
            "issues_found": [
                {
                    "category": issue.category,
                    "description": issue.description,
                    "knowledge_gap": issue.knowledge_gap,
                }
                for issue in self.issues_found
            ],
        }


@dataclass
class EnhancedBulletTag:
    """Bullet tag with rationale."""
    bullet_id: str
    tag: Tag
    rationale: str  # Why this tag?
    query: str = ""
    run_id: str = ""


@dataclass
class SuggestedDelta:
    """A suggested change for Curator to consider."""
    delta_type: DeltaType
    confidence: float  # 0.0 - 1.0
    content: str | None = None  # For ADD
    bullet_id: str | None = None  # For UPDATE/DELETE
    section: str | None = None  # For ADD
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.delta_type.value,
            "confidence": self.confidence,
            "content": self.content,
            "bullet_id": self.bullet_id,
            "section": self.section,
            "rationale": self.rationale,
        }


@dataclass
class ReflectorResult:
    """Result from Reflector deep analysis of a Solver result."""
    run_id: str
    query: str

    # Judgment
    is_correct: bool
    score: float  # 0.0 - 1.0
    judge_reason: str

    # Deep Analysis
    analysis: Analysis = field(default_factory=Analysis)

    # Bullet Tags (with rationales)
    bullet_tags: list[EnhancedBulletTag] = field(default_factory=list)

    # Legacy bullet tags (for backwards compat with tags.jsonl)
    legacy_bullet_tags: list[BulletTag] = field(default_factory=list)

    # Suggested Changes
    suggested_deltas: list[SuggestedDelta] = field(default_factory=list)

    # Metrics
    latency_seconds: float = 0.0
    total_tokens: int = 0
    total_cost_usd: float = 0.0

    # For backwards compatibility
    @property
    def insight(self) -> str | None:
        """Return first issue description as insight."""
        if self.analysis.issues_found:
            return self.analysis.issues_found[0].description
        return None

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "query": self.query,
            "is_correct": self.is_correct,
            "score": self.score,
            "judge_reason": self.judge_reason,
            "analysis": self.analysis.to_dict(),
            "bullet_tags": [
                {
                    "bullet_id": t.bullet_id,
                    "tag": t.tag.value,
                    "rationale": t.rationale,
                }
                for t in self.bullet_tags
            ],
            "suggested_deltas": [d.to_dict() for d in self.suggested_deltas],
            "latency_seconds": self.latency_seconds,
            "total_tokens": self.total_tokens,
            "total_cost_usd": self.total_cost_usd,
        }


# =============================================================================
# LLM Calls
# =============================================================================

async def judge_answer(query: str, expected: str, actual: str) -> tuple[float, str]:
    """Use LLM to judge if agent answer matches expected answer.

    Returns: (score, reason)
        score: 0.0 (wrong) to 1.0 (correct)
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

Judge as PARTIALLY CORRECT (0.5) if:
- The answer is directionally correct but has minor errors
- Most key information is present

Judge as WRONG (0.0) if:
- The answer is factually incorrect
- Key information is missing or wrong
- The reasoning leads to a wrong conclusion

Return ONLY a JSON object:
{{"score": <0.0, 0.5, or 1.0>, "reason": "<brief explanation>"}}"""

    return await _call_llm_json(prompt, "claude-haiku-4-5", max_budget=0.02)


async def judge_soundness(query: str, actual: str, criteria: str) -> tuple[float, str]:
    """Use LLM to judge answer soundness based on criteria (no ground truth)."""
    prompt = f"""Evaluate the agent's answer for logical soundness based on the given criteria.

Query: {query}

Agent Answer: {actual}

Scoring Criteria:
{criteria}

Based on the criteria above, assign a score from 0.0 to 1.0 and explain your reasoning.

Return ONLY a JSON object:
{{"score": <0.0 to 1.0>, "reason": "<brief explanation>"}}"""

    return await _call_llm_json(prompt, "claude-haiku-4-5", max_budget=0.02)


async def deep_analyze(
    query: str,
    answer: str,
    turns: list[dict],
    bullet_ids: list[str],
) -> dict[str, Any]:
    """Perform deep analysis of solver execution from trace alone.

    Analyzes: tool efficiency, reasoning soundness, calculation correctness,
    self-consistency (does answer match what code produced?), and knowledge usage.

    Args:
        query: The original query
        answer: Solver's final answer
        turns: Full execution trace (thinking + tool calls)
        bullet_ids: Bullet IDs cited

    Returns:
        Dict with analysis, bullet_tags, and suggested_deltas
    """
    # Format the execution trace for the LLM
    trace_summary = _format_trace_for_analysis(turns)

    # Note: We explicitly do NOT use expected answer for quality assessment
    # Ground truth comparison is a separate eval concern
    prompt = f"""Perform deep analysis of this agent execution trace.

Your job is to assess EXECUTION QUALITY from the trace alone - not correctness vs ground truth.

## Query
{query}

## Agent's Final Answer
{answer}

## Execution Trace
{trace_summary}

## Bullets Cited
{bullet_ids if bullet_ids else "(none)"}

---

Analyze the execution and return a JSON object with these sections:

1. **tool_analysis**: Evaluate tool usage efficiency
   - total_calls: int
   - redundant_calls: int (calls that didn't add value)
   - failed_calls: int (calls that errored or returned no useful data)
   - wrong_tool_choices: list of descriptions of suboptimal tool choices
   - assessment: brief overall assessment

2. **reasoning_analysis**: Evaluate reasoning quality
   - flawed_assumptions: list of incorrect assumptions made
   - logic_errors: list of logical mistakes
   - missed_considerations: list of things that should have been considered
   - assessment: brief overall assessment

3. **calculation_analysis**: Evaluate calculation correctness (check math in tool outputs)
   - errors_found: list of specific calculation errors
   - assessment: brief overall assessment

4. **self_consistency**: Does the answer match the actual computation results?
   - is_consistent: bool
   - inconsistencies: list of discrepancies between answer and tool outputs

5. **issues_found**: List any issues that could be improved (even if answer seems fine)
   - category: one of ["inefficiency", "wrong_approach", "calculation_error", "missing_validation", "unclear_reasoning", "knowledge_gap", "tool_misuse", "none"]
   - description: detailed explanation
   - knowledge_gap: what knowledge would have helped? (null if N/A)

6. **bullet_tags**: For each cited bullet, evaluate its contribution to execution quality
   {{
     "<bullet_id>": {{
       "tag": "helpful" | "harmful" | "neutral",
       "rationale": "why this tag? (based on how it influenced the execution)"
     }}
   }}

7. **suggested_deltas**: Proposed changes to improve future executions (0-3 suggestions)
   [
     {{
       "type": "ADD" | "UPDATE" | "DELETE" | "STRUCTURAL",
       "confidence": 0.0-1.0,
       "content": "new bullet content (for ADD)",
       "bullet_id": "existing bullet id (for UPDATE/DELETE)",
       "section": "target section (for ADD)",
       "rationale": "why this change would help?"
     }}
   ]

Return ONLY valid JSON matching this structure."""

    try:
        options = ClaudeAgentOptions(
            model="claude-haiku-4-5",
            max_turns=1,
            system_prompt="You are an expert code reviewer analyzing agent execution traces. Return only valid JSON.",
            cwd=str(Path(__file__).parent),
            allowed_tools=[],
            permission_mode="acceptEdits",
            max_budget_usd=0.05,
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
            return json.loads(json_str)

        logger.warning("Failed to parse deep analysis response")
        return {}

    except Exception as e:
        logger.error(f"Deep analysis error: {e}")
        return {}


def _format_trace_for_analysis(turns: list[dict], max_length: int = 8000) -> str:
    """Format execution trace for LLM analysis."""
    lines = []

    for i, turn in enumerate(turns, 1):
        lines.append(f"### Turn {i}")

        thinking = turn.get("thinking", "")
        if thinking:
            # Truncate long thinking
            if len(thinking) > 500:
                thinking = thinking[:500] + "..."
            lines.append(f"**Thinking:** {thinking}")

        tool_calls = turn.get("tool_calls", [])
        for tc in tool_calls:
            tool = tc.get("tool", "unknown")
            tool_input = tc.get("input", {})
            output = tc.get("output", "")

            # Format input
            if isinstance(tool_input, dict):
                if "command" in tool_input:
                    input_str = tool_input["command"][:200]
                elif "file_path" in tool_input:
                    input_str = tool_input["file_path"]
                else:
                    input_str = json.dumps(tool_input)[:200]
            else:
                input_str = str(tool_input)[:200]

            # Truncate output
            if output and len(output) > 300:
                output = output[:300] + "..."

            lines.append(f"**Tool:** {tool}")
            lines.append(f"  Input: {input_str}")
            if output:
                lines.append(f"  Output: {output}")

        lines.append("")

    result = "\n".join(lines)

    # Final truncation if too long
    if len(result) > max_length:
        result = result[:max_length] + "\n\n[TRACE TRUNCATED]"

    return result


async def _call_llm_json(prompt: str, model: str, max_budget: float = 0.02) -> tuple[float, str]:
    """Call LLM and parse JSON response for score/reason."""
    try:
        options = ClaudeAgentOptions(
            model=model,
            max_turns=1,
            system_prompt="Return only valid JSON.",
            cwd=str(Path(__file__).parent),
            allowed_tools=[],
            permission_mode="acceptEdits",
            max_budget_usd=max_budget,
        )

        async with ClaudeSDKClient(options=options) as client:
            await client.query(prompt)
            response_text = ""
            async for message in client.receive_response():
                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            response_text += block.text

        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response_text[json_start:json_end]
            result = json.loads(json_str)
            score = float(result.get("score", 0.0))
            reason = result.get("reason", "No reason provided")
            return (score, reason)

        return (0.0, "Failed to parse response")

    except Exception as e:
        return (0.0, f"Error: {str(e)[:50]}")


# =============================================================================
# Reflector Class
# =============================================================================

class Reflector:
    """Performs deep analysis of Solver results and tags bullets for learning."""

    def __init__(
        self,
        tags_log_path: Path | None = None,
        reflector_log_dir: Path | None = None,
    ):
        """Initialize the Reflector.

        Args:
            tags_log_path: Path to tags.jsonl (legacy, for Curator compatibility)
            reflector_log_dir: Directory for detailed reflector logs
        """
        self.ace_root = Path(__file__).parent
        self.tags_log_path = tags_log_path or self.ace_root / "logs" / "tags.jsonl"
        self.reflector_log_dir = reflector_log_dir or self.ace_root / "logs" / "reflector"

        # Ensure directories exist
        self.tags_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.reflector_log_dir.mkdir(parents=True, exist_ok=True)

    async def reflect(self, solver_result: SolverResult) -> ReflectorResult:
        """Perform deep analysis of a Solver result.

        Analysis is based on EXECUTION QUALITY from the trace, not ground truth.
        Ground truth comparison (if expected_answer provided) is separate and
        used only for evaluation metrics.

        Args:
            solver_result: Result from SolverAgent.solve() with full trace

        Returns:
            ReflectorResult with deep analysis, tags, and suggested deltas
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

        # Step 1: Deep analysis from trace (ALWAYS runs for learning)
        analysis_result = await deep_analyze(
            query=solver_result.query,
            answer=solver_result.answer,
            turns=solver_result.turns,
            bullet_ids=solver_result.bullet_ids_used,
        )

        # Step 2: Judge correctness (requires GT or soundness criteria)
        scoring = getattr(solver_result, 'scoring', None)
        if scoring and scoring.get("type") == "soundness":
            criteria = scoring.get("criteria", "Evaluate logical soundness 0-1.")
            score, reason = await judge_soundness(
                solver_result.query,
                solver_result.answer,
                criteria,
            )
            result.score = score
            result.is_correct = score >= 0.5
            result.judge_reason = reason
        elif solver_result.expected_answer:
            score, reason = await judge_answer(
                solver_result.query,
                solver_result.expected_answer,
                solver_result.answer,
            )
            result.score = score
            result.is_correct = score >= 0.5
            result.judge_reason = reason
        else:
            # No GT - can't judge correctness, but analysis still runs for learning
            result.score = 0.0
            result.is_correct = False
            result.judge_reason = "No ground truth provided"

        # Parse analysis result
        result.analysis = self._parse_analysis(analysis_result)
        result.bullet_tags = self._parse_bullet_tags(
            analysis_result.get("bullet_tags", {}),
            solver_result.bullet_ids_used,
            solver_result.query,
            solver_result.run_id,
        )
        result.suggested_deltas = self._parse_suggested_deltas(
            analysis_result.get("suggested_deltas", [])
        )

        # Create legacy bullet tags for backwards compat
        result.legacy_bullet_tags = [
            BulletTag(
                bullet_id=t.bullet_id,
                tag=t.tag,
                insight=result.insight if t.tag == Tag.HARMFUL else None,
                query=t.query,
                run_id=t.run_id,
            )
            for t in result.bullet_tags
        ]

        result.latency_seconds = time.time() - start_time

        # Step 3: Persist logs
        self._save_reflector_log(result, solver_result)
        self._append_tags(result)

        return result

    def _parse_analysis(self, data: dict) -> Analysis:
        """Parse analysis dict into Analysis dataclass."""
        analysis = Analysis()

        # Tool analysis
        ta = data.get("tool_analysis", {})
        analysis.tool_analysis = ToolAnalysis(
            total_calls=ta.get("total_calls", 0),
            redundant_calls=ta.get("redundant_calls", 0),
            failed_calls=ta.get("failed_calls", 0),
            wrong_tool_choices=ta.get("wrong_tool_choices", []),
            assessment=ta.get("assessment", ""),
        )

        # Reasoning analysis
        ra = data.get("reasoning_analysis", {})
        analysis.reasoning_analysis = ReasoningAnalysis(
            flawed_assumptions=ra.get("flawed_assumptions", []),
            logic_errors=ra.get("logic_errors", []),
            missed_considerations=ra.get("missed_considerations", []),
            assessment=ra.get("assessment", ""),
        )

        # Calculation analysis
        ca = data.get("calculation_analysis", {})
        analysis.calculation_analysis = CalculationAnalysis(
            errors_found=ca.get("errors_found", []),
            assessment=ca.get("assessment", ""),
        )

        # Self-consistency
        sc = data.get("self_consistency", {})
        analysis.self_consistency = SelfConsistency(
            is_consistent=sc.get("is_consistent", True),
            inconsistencies=sc.get("inconsistencies", []),
        )

        # Issues found (replaces root_cause)
        issues_data = data.get("issues_found")
        if issues_data and isinstance(issues_data, dict):
            # Single issue as dict
            if issues_data.get("category") != "none":
                analysis.issues_found = [IssueFound(
                    category=issues_data.get("category", "other"),
                    description=issues_data.get("description", ""),
                    knowledge_gap=issues_data.get("knowledge_gap"),
                )]
        elif issues_data and isinstance(issues_data, list):
            # List of issues
            for issue in issues_data:
                if isinstance(issue, dict) and issue.get("category") != "none":
                    analysis.issues_found.append(IssueFound(
                        category=issue.get("category", "other"),
                        description=issue.get("description", ""),
                        knowledge_gap=issue.get("knowledge_gap"),
                    ))

        return analysis

    def _parse_bullet_tags(
        self,
        tags_data: dict,
        bullet_ids: list[str],
        query: str,
        run_id: str,
    ) -> list[EnhancedBulletTag]:
        """Parse bullet tags from analysis result."""
        tags = []

        for bullet_id in bullet_ids:
            tag_info = tags_data.get(bullet_id, {})
            if isinstance(tag_info, dict):
                tag_str = tag_info.get("tag", "neutral").lower()
                rationale = tag_info.get("rationale", "")
            else:
                tag_str = str(tag_info).lower() if tag_info else "neutral"
                rationale = ""

            if tag_str == "helpful":
                tag = Tag.HELPFUL
            elif tag_str == "harmful":
                tag = Tag.HARMFUL
            else:
                tag = Tag.NEUTRAL

            tags.append(EnhancedBulletTag(
                bullet_id=bullet_id,
                tag=tag,
                rationale=rationale,
                query=query,
                run_id=run_id,
            ))

        return tags

    def _parse_suggested_deltas(self, deltas_data: list) -> list[SuggestedDelta]:
        """Parse suggested deltas from analysis result."""
        deltas = []

        for d in deltas_data:
            if not isinstance(d, dict):
                continue

            try:
                delta_type = DeltaType[d.get("type", "ADD").upper()]
            except KeyError:
                delta_type = DeltaType.ADD

            deltas.append(SuggestedDelta(
                delta_type=delta_type,
                confidence=float(d.get("confidence", 0.5)),
                content=d.get("content"),
                bullet_id=d.get("bullet_id"),
                section=d.get("section"),
                rationale=d.get("rationale", ""),
            ))

        return deltas

    def _save_reflector_log(self, result: ReflectorResult, solver_result: SolverResult) -> None:
        """Save detailed reflector log to file."""
        log_path = self.reflector_log_dir / f"{result.run_id}.json"

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "run_id": result.run_id,
            "query": result.query,
            "expected_answer": solver_result.expected_answer,
            "solver_answer": solver_result.answer,
            "is_correct": result.is_correct,
            "score": result.score,
            "judge_reason": result.judge_reason,
            "analysis": result.analysis.to_dict(),
            "bullet_tags": [
                {
                    "bullet_id": t.bullet_id,
                    "tag": t.tag.value,
                    "rationale": t.rationale,
                }
                for t in result.bullet_tags
            ],
            "suggested_deltas": [d.to_dict() for d in result.suggested_deltas],
            "solver_trace": solver_result.turns,
            "latency_seconds": result.latency_seconds,
        }

        with open(log_path, "w") as f:
            json.dump(log_data, f, indent=2)

    def _append_tags(self, result: ReflectorResult) -> None:
        """Append tags to legacy tags.jsonl for Curator compatibility."""
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
                    "insight": result.insight,  # Root cause description
                    "rationale": tag.rationale,
                }
                f.write(json.dumps(entry) + "\n")

    async def reflect_batch(
        self,
        solver_results: list[SolverResult],
        concurrency: int | None = None,
    ) -> list[ReflectorResult]:
        """Reflect on a batch of Solver results in parallel."""
        if concurrency is None:
            tasks = [self.reflect(r) for r in solver_results]
            return await asyncio.gather(*tasks)

        semaphore = asyncio.Semaphore(concurrency)

        async def limited_reflect(r: SolverResult) -> ReflectorResult:
            async with semaphore:
                return await self.reflect(r)

        tasks = [limited_reflect(r) for r in solver_results]
        return await asyncio.gather(*tasks)

    def read_pending_tags(self) -> list[dict]:
        """Read all tags from the legacy log file."""
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
        """Clear the legacy tags log file."""
        count = len(self.read_pending_tags())
        if self.tags_log_path.exists():
            self.tags_log_path.unlink()
        return count

    def read_reflector_logs(self, run_ids: list[str] | None = None) -> list[dict]:
        """Read reflector logs from the log directory.

        Args:
            run_ids: Optional list of run IDs to filter by

        Returns:
            List of reflector log dicts
        """
        logs = []
        for log_file in self.reflector_log_dir.glob("*.json"):
            if run_ids and log_file.stem not in run_ids:
                continue
            try:
                with open(log_file) as f:
                    logs.append(json.load(f))
            except (json.JSONDecodeError, IOError):
                continue
        return logs


# =============================================================================
# Test
# =============================================================================

async def test_reflector():
    """Test the enhanced Reflector with a mock Solver result."""
    from .solver import SolverResult

    # Create mock solver result with trace
    solver_result = SolverResult(
        query="What was the total Net Revenue for Product A in 2023?",
        answer="The total Net Revenue for Product A in 2023 was $12,345,678.90",
        bullet_ids_used=["sch-00016", "sch-00019"],
        run_id="test_enhanced_123",
        expected_answer="$12,345,678.90",
        turns=[
            {
                "thinking": "I need to filter for Product A and year 2023, then sum Net Revenue.",
                "tool_calls": [
                    {
                        "tool": "Bash",
                        "input": {"command": "python3 -c \"import pandas as pd; df = pd.read_csv('data.csv'); print(df[df['Product']=='A']['Net Revenue'].sum())\""},
                        "output": "12345678.90",
                    }
                ],
            }
        ],
    )

    reflector = Reflector()

    print("Testing Enhanced Reflector...")
    result = await reflector.reflect(solver_result)

    print(f"\nReflector Result:")
    print(f"  Run ID: {result.run_id}")
    print(f"  Is Correct: {result.is_correct}")
    print(f"  Score: {result.score}")
    print(f"  Judge Reason: {result.judge_reason}")

    print(f"\n  Analysis:")
    print(f"    Tool calls: {result.analysis.tool_analysis.total_calls}")
    print(f"    Redundant: {result.analysis.tool_analysis.redundant_calls}")
    print(f"    Assessment: {result.analysis.tool_analysis.assessment}")

    if result.analysis.issues_found:
        print(f"\n  Issues Found:")
        for issue in result.analysis.issues_found:
            print(f"    - [{issue.category}] {issue.description}")

    print(f"\n  Bullet Tags:")
    for tag in result.bullet_tags:
        print(f"    - {tag.bullet_id}: {tag.tag.value} ({tag.rationale})")

    print(f"\n  Suggested Deltas:")
    for delta in result.suggested_deltas:
        print(f"    - {delta.delta_type.value}: {delta.rationale[:50]}...")

    print(f"\n  Latency: {result.latency_seconds:.1f}s")


if __name__ == "__main__":
    asyncio.run(test_reflector())
