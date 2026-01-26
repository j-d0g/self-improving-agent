"""
ACE: Agentic Counterfactual Expansion

A 3-agent pipeline for self-improving question answering:
- Solver: Executes queries, tracks bullet IDs used
- Reflector: Tags bullets as helpful/harmful, generates insights
- Curator: Applies delta operations (ADD/UPDATE/DELETE) to knowledge
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
from .reflector import Reflector, ReflectorResult, judge_answer, tag_bullets
from .curator import Curator, CuratorResult, aggregate_tags, compute_counter_updates
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
    "tag_bullets",
    # Curator
    "Curator",
    "CuratorResult",
    "aggregate_tags",
    "compute_counter_updates",
    # Orchestrator
    "BatchOrchestrator",
    "BatchResult",
    "EpochResult",
    "TrainingRun",
    "load_queries",
]
