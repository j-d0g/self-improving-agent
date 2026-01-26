"""
ACE: Agentic Counterfactual Expansion (v2)

A 4-component pipeline for self-improving question answering:
- Solver: Executes queries, tracks bullet IDs used
- Reflector: Deep analysis of execution traces, tags bullets, suggests deltas
- Curator: Applies immediate changes (counters, simple ADDs), defers structural changes
- Aggregator: Batch-level pattern analysis and strategic knowledge updates
"""

from .playbook_utils import (
    Bullet,
    BulletTag,
    DeltaOp,
    OpType,
    Playbook,
    Tag,
    apply_operation,
    apply_operations,
    get_playbook_stats,
    load_playbook,
    parse_bullet,
    parse_playbook,
    save_playbook,
    update_counters,
)
from .solver import SolverAgent, SolverResult, extract_bullet_ids
from .reflector import (
    Reflector,
    ReflectorResult,
    judge_answer,
    Analysis,
    EnhancedBulletTag,
    SuggestedDelta,
    DeltaType,
    IssueFound,
    SelfConsistency,
)
from .curator import Curator, CuratorResult, aggregate_tags, compute_counter_updates
from .aggregator import Aggregator, AggregatorResult, FailurePattern, AggregatorDecision
from .orchestrator import BatchOrchestrator, BatchResult, EpochResult, TrainingRun, load_queries

__all__ = [
    # Playbook utilities
    "Bullet",
    "BulletTag",
    "DeltaOp",
    "OpType",
    "Playbook",
    "Tag",
    "apply_operation",
    "apply_operations",
    "get_playbook_stats",
    "load_playbook",
    "parse_bullet",
    "parse_playbook",
    "save_playbook",
    "update_counters",
    # Solver
    "SolverAgent",
    "SolverResult",
    "extract_bullet_ids",
    # Reflector
    "Reflector",
    "ReflectorResult",
    "judge_answer",
    "Analysis",
    "EnhancedBulletTag",
    "SuggestedDelta",
    "DeltaType",
    # Curator
    "Curator",
    "CuratorResult",
    "aggregate_tags",
    "compute_counter_updates",
    # Aggregator
    "Aggregator",
    "AggregatorResult",
    "FailurePattern",
    "AggregatorDecision",
    # Orchestrator
    "BatchOrchestrator",
    "BatchResult",
    "EpochResult",
    "TrainingRun",
    "load_queries",
]
