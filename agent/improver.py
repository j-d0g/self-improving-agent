"""
Improver Agent

Applies improvements to knowledge files based on evaluator recommendations.
Takes structured improvement specs and implements changes safely.
"""

from pathlib import Path
import asyncio
import json
import shutil
import subprocess
from datetime import datetime

# Note: Claude Agent SDK uses Claude CLI authentication, not ANTHROPIC_API_KEY

from claude_agent_sdk import (
    query as sdk_query,
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from tracing import ExecutionTrace, AgentMetrics
from prompts import load_prompt


class ImproverAgent:
    """Agent that applies improvements to knowledge files."""

    def __init__(self):
        """Initialize the improver agent."""
        self.project_root = Path(__file__).parent
        self.logs_dir = self.project_root / "logs"
        self.evaluations_dir = self.logs_dir / "evaluations"
        self.improvements_dir = self.logs_dir / "improvements"
        self.knowledge_dir = self.project_root / "knowledge"

        # Ensure directories exist
        self.evaluations_dir.mkdir(parents=True, exist_ok=True)
        self.improvements_dir.mkdir(parents=True, exist_ok=True)
        self.knowledge_dir.mkdir(exist_ok=True)

        # Load system prompt
        self.system_prompt = load_prompt("improver.txt")

        # Metrics tracking
        self.metrics = AgentMetrics()

    def improve(self, eval_file: str = None, dry_run: bool = False) -> dict:
        """
        Apply improvements from an evaluation report.

        Args:
            eval_file: Path to evaluation report. If None, uses most recent.
            dry_run: If True, only analyze and report what would be changed.

        Returns:
            dict with improvement results
        """
        return asyncio.run(self._improve_async(eval_file, dry_run))

    async def _improve_async(self, eval_file: str, dry_run: bool) -> dict:
        """Async implementation of improve."""
        # Find evaluation file
        if eval_file is None:
            eval_files = sorted(self.evaluations_dir.glob("eval_*.md"), reverse=True)
            if not eval_files:
                return {"error": "No evaluation files found in logs/evaluations/"}
            eval_file = str(eval_files[0])

        trace = ExecutionTrace(query=f"Improve from: {eval_file}")
        current_turn = {"thinking": "", "tool_calls": []}
        final_answer = ""

        # Build the improvement prompt
        prompt = self._build_improvement_prompt(eval_file, dry_run)

        # Configure tools based on dry_run mode
        if dry_run:
            allowed_tools = ["Read", "Grep", "Glob"]
        else:
            allowed_tools = ["Read", "Write", "Edit", "Grep", "Glob"]

        options = ClaudeAgentOptions(
            max_turns=20,
            system_prompt=self.system_prompt,
            cwd=str(self.project_root),
            allowed_tools=allowed_tools,
            permission_mode="acceptEdits"
        )

        async for message in sdk_query(prompt=prompt, options=options):
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

        # Save improvement report
        report_path = self._save_report(eval_file, final_answer, trace, dry_run)

        # Commit improvements to learnings branch (unless dry run)
        commit_result = None
        if not dry_run:
            commit_result = self._commit_improvements(eval_file)

        return {
            "result": final_answer,
            "trace": trace,
            "report_path": report_path,
            "dry_run": dry_run,
            "commit": commit_result
        }

    def _build_improvement_prompt(self, eval_file: str, dry_run: bool) -> str:
        """Build the prompt for applying improvements."""
        mode = "analyze (dry run - no changes)" if dry_run else "apply"
        return f"""Please {mode} improvements from the evaluation report: {eval_file}

Your task:
1. Read the evaluation report
2. Review the "Improvement Specifications" section
3. {"Report what changes would be made (do NOT modify any files)" if dry_run else "Apply each improvement in priority order (Critical → High → Medium → Low)"}
4. Write a summary report to logs/improvements/

Focus on:
- Understanding each improvement specification
- {"Verifying target files exist" if dry_run else "Carefully applying changes to the correct locations"}
- Preserving existing content when adding new material
- {"Reporting what would change" if dry_run else "Verifying changes were applied correctly"}
"""

    def _commit_improvements(self, eval_file: str) -> dict:
        """Commit knowledge changes to the learnings branch using git worktree."""
        try:
            # Check if there are changes to knowledge/
            status = subprocess.run(
                ["git", "status", "--porcelain", "knowledge/"],
                capture_output=True, text=True, cwd=self.project_root
            )
            if not status.stdout.strip():
                return {"committed": False, "reason": "No changes to knowledge/"}

            # Get repo root (may differ from project_root)
            repo_root = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, cwd=self.project_root, check=True
            ).stdout.strip()

            # Worktree path (sibling of repo)
            worktree_path = Path(repo_root).parent / ".worktree-learnings"
            branch_name = "learnings"

            # Check if learnings branch exists
            branch_exists = subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"],
                cwd=repo_root
            ).returncode == 0

            # Create worktree
            if branch_exists:
                subprocess.run(
                    ["git", "worktree", "add", str(worktree_path), branch_name],
                    capture_output=True, cwd=repo_root, check=True
                )
            else:
                subprocess.run(
                    ["git", "worktree", "add", "-b", branch_name, str(worktree_path), "HEAD"],
                    capture_output=True, cwd=repo_root, check=True
                )

            try:
                # Copy changed knowledge files to worktree
                knowledge_src = self.project_root / "knowledge"
                knowledge_dst = worktree_path / "agent" / "knowledge"

                if knowledge_dst.exists():
                    shutil.rmtree(knowledge_dst)
                shutil.copytree(knowledge_src, knowledge_dst)

                # Stage and commit in worktree
                subprocess.run(
                    ["git", "add", "agent/knowledge/"],
                    cwd=worktree_path, check=True
                )

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                eval_name = Path(eval_file).stem
                commit_msg = f"learning: {eval_name} ({timestamp})"

                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    capture_output=True, cwd=worktree_path, check=True
                )

                # Get commit hash
                commit_hash = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    capture_output=True, text=True, cwd=worktree_path
                ).stdout.strip()

                return {"committed": True, "branch": branch_name, "commit": commit_hash}

            finally:
                # Always clean up worktree
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree_path)],
                    capture_output=True, cwd=repo_root
                )
                subprocess.run(
                    ["git", "worktree", "prune"],
                    capture_output=True, cwd=repo_root
                )

        except subprocess.CalledProcessError as e:
            return {"committed": False, "error": str(e)}

    def _save_report(self, eval_file: str, result: str, trace: ExecutionTrace, dry_run: bool) -> str:
        """Save the improvement report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = "dry_run_" if dry_run else "improvement_"
        report = {
            "timestamp": datetime.now().isoformat(),
            "eval_file": eval_file,
            "dry_run": dry_run,
            "result": result,
            "metrics": {
                "tokens": trace.total_tokens,
                "tool_calls": trace.total_tool_calls,
                "cost_usd": trace.total_cost_usd
            }
        }

        report_path = self.improvements_dir / f"{prefix}{timestamp}.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        return str(report_path)


def main():
    """CLI for the improver agent."""
    import sys

    improver = ImproverAgent()

    def print_help():
        print("""
Improver Agent - Apply improvements to knowledge files

Usage:
  python improver.py                     Apply improvements from most recent evaluation
  python improver.py <eval_file>         Apply improvements from specific evaluation
  python improver.py --dry-run           Analyze without making changes
  python improver.py --dry-run <file>    Analyze specific file without changes

Examples:
  python improver.py logs/evaluations/eval_q01_revenue.md
  python improver.py --dry-run
  python improver.py --dry-run logs/evaluations/eval_q01_revenue.md
""")

    if len(sys.argv) > 1:
        arg = sys.argv[1]

        if arg in ["--help", "-h"]:
            print_help()
            return

        if arg == "--dry-run":
            eval_file = sys.argv[2] if len(sys.argv) > 2 else None
            print("Analyzing improvements (dry run)...")
            result = improver.improve(eval_file=eval_file, dry_run=True)
        else:
            print(f"Applying improvements from: {arg}")
            result = improver.improve(eval_file=arg)
    else:
        print("Applying improvements from most recent evaluation...")
        result = improver.improve()

    if "error" in result:
        print(f"Error: {result['error']}")
        return

    print("\n" + "=" * 60)
    print("IMPROVEMENT RESULT" + (" (DRY RUN)" if result.get("dry_run") else ""))
    print("=" * 60)
    print(result["result"])

    if "trace" in result:
        trace = result["trace"]
        print("\n" + "-" * 40)
        print(f"[Tokens: {trace.total_tokens}, Tool calls: {trace.total_tool_calls}, Cost: ${trace.total_cost_usd:.4f}]")

    if "report_path" in result:
        print(f"\nReport saved to: {result['report_path']}")

    if result.get("commit"):
        commit = result["commit"]
        if commit.get("committed"):
            print(f"Committed to branch '{commit['branch']}': {commit['commit']}")
        elif commit.get("reason"):
            print(f"No commit: {commit['reason']}")
        elif commit.get("error"):
            print(f"Commit failed: {commit['error']}")


if __name__ == "__main__":
    main()
