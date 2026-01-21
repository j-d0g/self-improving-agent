"""
Agent Orchestrator

Coordinates the financial analysis agent with automatic evaluation and improvement.
Supports multiple evaluation modes: inline, batch, or background.
"""

from pathlib import Path
import asyncio
import json
from datetime import datetime
from typing import Literal, Optional
from dataclasses import dataclass, field
import threading
import queue

# Note: Claude Code SDK uses Claude CLI authentication, not ANTHROPIC_API_KEY

from agent import FinancialAnalysisAgent
from evaluator import EvaluatorAgent
from tracing import ExecutionTrace


@dataclass
class QueryResult:
    """Result from an orchestrated query."""
    query: str
    answer: str
    trace: ExecutionTrace
    evaluation: Optional[dict] = None
    improvements_applied: bool = False


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""
    # Evaluation mode: 
    # - "none": No automatic evaluation
    # - "inline": Evaluate after every query (slower, more expensive)
    # - "batch": Evaluate after N queries
    # - "background": Queue evaluations to run asynchronously
    eval_mode: Literal["none", "inline", "batch", "background"] = "batch"
    
    # For batch mode: evaluate after this many queries
    batch_size: int = 5
    
    # Auto-apply improvements from evaluator?
    auto_apply: bool = False
    
    # Use separate improver agent (vs evaluator applying directly)
    # If True: evaluator analyzes → improver applies
    # If False: evaluator analyzes and applies (when auto_apply=True)
    use_improver: bool = True
    
    # Score threshold for triggering improvements (0-100)
    improvement_threshold: float = 80.0


class AgentOrchestrator:
    """
    Orchestrates agent queries with automatic evaluation and improvement.
    
    Usage:
        orchestrator = AgentOrchestrator()
        result = orchestrator.query("What was revenue in Q1 2024?")
        
        # With inline evaluation
        orchestrator = AgentOrchestrator(config=OrchestratorConfig(eval_mode="inline"))
        
        # With auto-apply improvements
        orchestrator = AgentOrchestrator(config=OrchestratorConfig(auto_apply=True))
    """
    
    def __init__(self, config: OrchestratorConfig = None):
        self.config = config or OrchestratorConfig()
        self.project_root = Path(__file__).parent
        
        # Initialize agents
        self.agent = FinancialAnalysisAgent()
        self.evaluator = EvaluatorAgent()
        
        # Query history for batch evaluation
        self.query_history: list[QueryResult] = []
        self.pending_evaluations: queue.Queue = queue.Queue()
        
        # Background worker thread (if needed)
        self._background_worker = None
        self._stop_worker = threading.Event()
        
        if self.config.eval_mode == "background":
            self._start_background_worker()
    
    def query(self, question: str) -> QueryResult:
        """
        Process a query through the agent with optional evaluation.
        
        Returns:
            QueryResult with answer, trace, and optional evaluation
        """
        # Run the agent
        agent_result = self.agent.query(question)
        
        result = QueryResult(
            query=question,
            answer=agent_result["answer"],
            trace=agent_result["trace"]
        )
        
        self.query_history.append(result)
        
        # Handle evaluation based on mode
        if self.config.eval_mode == "inline":
            self._evaluate_inline(result)
        elif self.config.eval_mode == "batch":
            self._check_batch_evaluation()
        elif self.config.eval_mode == "background":
            self.pending_evaluations.put(result)
        
        return result
    
    def _evaluate_inline(self, result: QueryResult):
        """Run evaluation immediately after query."""
        # Save a mini eval file for this single query
        eval_data = self._create_eval_data([result])
        eval_path = self._save_temp_eval(eval_data)
        
        # Run evaluator
        eval_result = self.evaluator.evaluate(
            eval_file=eval_path,
            apply_improvements=self.config.auto_apply
        )
        
        result.evaluation = {
            "analysis": eval_result.get("analysis", ""),
            "applied": self.config.auto_apply
        }
        result.improvements_applied = self.config.auto_apply
    
    def _check_batch_evaluation(self):
        """Check if batch size reached and run evaluation."""
        unevaluated = [r for r in self.query_history if r.evaluation is None]
        
        if len(unevaluated) >= self.config.batch_size:
            self._run_batch_evaluation(unevaluated)
    
    def _run_batch_evaluation(self, results: list[QueryResult]):
        """Run evaluation on a batch of results."""
        eval_data = self._create_eval_data(results)
        eval_path = self._save_temp_eval(eval_data)
        
        print(f"\n[Orchestrator] Running batch evaluation on {len(results)} queries...")
        
        eval_result = self.evaluator.evaluate(
            eval_file=eval_path,
            apply_improvements=self.config.auto_apply
        )
        
        # Mark all as evaluated
        for r in results:
            r.evaluation = {"batch": True, "analysis": "See batch report"}
            r.improvements_applied = self.config.auto_apply
        
        print(f"[Orchestrator] Batch evaluation complete. Auto-apply: {self.config.auto_apply}")
    
    def _start_background_worker(self):
        """Start background thread for async evaluations."""
        def worker():
            while not self._stop_worker.is_set():
                try:
                    result = self.pending_evaluations.get(timeout=1.0)
                    self._evaluate_inline(result)
                    print(f"\n[Background] Evaluated: {result.query[:50]}...")
                except queue.Empty:
                    continue
        
        self._background_worker = threading.Thread(target=worker, daemon=True)
        self._background_worker.start()
    
    def _create_eval_data(self, results: list[QueryResult]) -> dict:
        """Create evaluation data structure from results."""
        return {
            "eval_file": "orchestrator_inline",
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_queries": len(results),
                "successful": len(results),
                "errors": 0
            },
            "results": [
                {
                    "query": r.query,
                    "expected_answer": "",  # No expected answer for live queries
                    "agent_answer": r.answer,
                    "metrics": {
                        "total_tokens": r.trace.total_tokens,
                        "tool_calls": r.trace.total_tool_calls
                    },
                    "status": "success"
                }
                for r in results
            ]
        }
    
    def _save_temp_eval(self, eval_data: dict) -> str:
        """Save temporary evaluation file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.project_root / "learnings" / f"orchestrator_eval_{timestamp}.json"
        path.parent.mkdir(exist_ok=True)
        
        with open(path, "w") as f:
            json.dump(eval_data, f, indent=2)
        
        return str(path)
    
    def force_evaluation(self):
        """Force evaluation of all pending queries."""
        unevaluated = [r for r in self.query_history if r.evaluation is None]
        if unevaluated:
            self._run_batch_evaluation(unevaluated)
        else:
            print("[Orchestrator] No pending queries to evaluate.")
    
    def get_stats(self) -> dict:
        """Get orchestrator statistics."""
        total = len(self.query_history)
        evaluated = sum(1 for r in self.query_history if r.evaluation is not None)
        improved = sum(1 for r in self.query_history if r.improvements_applied)
        
        return {
            "total_queries": total,
            "evaluated": evaluated,
            "pending_evaluation": total - evaluated,
            "improvements_applied": improved,
            "eval_mode": self.config.eval_mode,
            "auto_apply": self.config.auto_apply
        }
    
    def shutdown(self):
        """Shutdown orchestrator (stop background workers)."""
        if self._background_worker:
            self._stop_worker.set()
            self._background_worker.join(timeout=5.0)


def main():
    """Interactive CLI for the orchestrator."""
    import sys
    
    def print_help():
        print("""
Agent Orchestrator - Automated evaluation and improvement loop

Usage:
  python orchestrator.py                    Interactive mode (batch eval, no auto-apply)
  python orchestrator.py --inline           Evaluate after every query
  python orchestrator.py --auto             Auto-apply improvements
  python orchestrator.py --background       Background async evaluation

Options:
  --inline          Evaluate immediately after each query
  --batch N         Evaluate after N queries (default: 5)
  --background      Queue evaluations for background processing
  --auto            Automatically apply suggested improvements
  --threshold N     Score threshold for improvements (0-100, default: 80)

Examples:
  python orchestrator.py --inline --auto    Full automation: eval + apply after each query
  python orchestrator.py --batch 3          Evaluate every 3 queries
  python orchestrator.py "question"         Single query with default config
""")
    
    # Parse args
    config = OrchestratorConfig()
    query_arg = None
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ["--help", "-h"]:
            print_help()
            return
        elif arg == "--inline":
            config.eval_mode = "inline"
        elif arg == "--background":
            config.eval_mode = "background"
        elif arg == "--batch":
            config.eval_mode = "batch"
            if i + 1 < len(args) and args[i + 1].isdigit():
                i += 1
                config.batch_size = int(args[i])
        elif arg == "--auto":
            config.auto_apply = True
        elif arg == "--threshold":
            if i + 1 < len(args):
                i += 1
                config.improvement_threshold = float(args[i])
        elif not arg.startswith("--"):
            query_arg = arg
        i += 1
    
    orchestrator = AgentOrchestrator(config=config)
    
    print(f"""
Agent Orchestrator
==================
Eval mode: {config.eval_mode}
Auto-apply: {config.auto_apply}
Batch size: {config.batch_size if config.eval_mode == "batch" else "N/A"}
""")
    
    if query_arg:
        # Single query mode
        print(f"Query: {query_arg}\n")
        result = orchestrator.query(query_arg)
        print("\n" + "=" * 60)
        print("ANSWER:")
        print("=" * 60)
        print(result.answer)
        print(f"\n[Tokens: {result.trace.total_tokens}, Tools: {result.trace.total_tool_calls}]")
        if result.evaluation:
            print(f"[Evaluated: Yes, Improvements applied: {result.improvements_applied}]")
    else:
        # Interactive mode
        print("Commands: 'quit', 'stats', 'eval' (force evaluation)\n")
        
        try:
            while True:
                question = input("You: ").strip()
                if not question:
                    continue
                if question.lower() == "quit":
                    orchestrator.force_evaluation()
                    print("\nFinal Stats:", orchestrator.get_stats())
                    break
                if question.lower() == "stats":
                    print("\nStats:", orchestrator.get_stats())
                    continue
                if question.lower() == "eval":
                    orchestrator.force_evaluation()
                    continue
                
                print("\nThinking...")
                result = orchestrator.query(question)
                
                print("\n" + "-" * 40)
                print(result.answer)
                print(f"\n[Tokens: {result.trace.total_tokens}, Tools: {result.trace.total_tool_calls}]")
                
                stats = orchestrator.get_stats()
                if config.eval_mode == "batch":
                    pending = stats["pending_evaluation"]
                    print(f"[Pending evaluation: {pending}/{config.batch_size}]")
                
                print("-" * 40 + "\n")
                
        except KeyboardInterrupt:
            print("\n\nShutting down...")
        finally:
            orchestrator.shutdown()


if __name__ == "__main__":
    main()
