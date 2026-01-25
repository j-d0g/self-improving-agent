# Prototype: Self-Improving Data Analysis Agent

> **Purpose**: Early exploration of self-improving agent concepts using Claude Code CLI.
> This directory contains a minimal prototype for testing feasibility before building the full Agent SDK implementation.

## Architecture: Orchestrator Pattern

```
                    ┌─────────────────────┐
                    │   Improver/Orch.    │
                    │    (Opus 4.5)       │
                    └──────────┬──────────┘
                               │
                ┌──────────────┼─────────────┐
                │              │             │
                ▼              ▼             │
        ┌──────────────┐ ┌─────────────┐     │
        │   Learner    │ │  Evaluator  │     │
        │   (Haiku)    │ │   (Opus)    │     │
        └──────┬───────┘ └──────┬──────┘     │
               │                │            │
               ▼                ▼            │
        logs/sessions/  logs/evaluations/    │
        (session logs)  (critique reports)   │
                                │            │
                                └────────────┘
                                         │
                                         ▼
                                   knowledge/
                                   (evolvable context)
```

**Flow**: Improver (Opus 4.5) orchestrates → spawns Learner (Haiku) → spawns Evaluator (Opus) → applies improvements to knowledge files.

## Agent Definitions

| Agent | Model | Purpose | Tools |
|-------|-------|---------|-------|
| **improver** | Opus 4.5 | **Orchestrator** - Coordinates learning loop, spawns sub-agents, applies improvements | Read, Write, Edit, Task |
| **learner** | Haiku | Answers financial queries, executes pandas code, writes session logs | Read, Write, Bash, Grep, Glob |
| **evaluator** | Opus | Critiques learner logs, generates improvement specs | Read, Grep, Glob |

## Workflow

**Start with improver orchestrator**:
```
Task: Process the query "What was revenue for Product A in Q1 2024?"
Subagent: improver
```

1. **Improver spawns Learner**: Answers query, writes session log to `logs/sessions/`
2. **Improver spawns Evaluator**: Critiques session, writes evaluation to `logs/evaluations/`
3. **Improver applies changes**: Updates knowledge files based on evaluation feedback

**Next session**: Learner reads updated knowledge files → answers faster → demonstrates cross-session learning.

## Knowledge Files

Evolvable context that grows through the learning loop:

| File | Purpose |
|------|---------|
| `knowledge/schema.md` | Dataset structure, column definitions, formulas, edge cases |
| `knowledge/examples.md` | Query patterns with working pandas code |
| `knowledge/functions.py` | Reusable helper functions |

## Dataset

`data/FUN_company_pl_actuals_dataset.csv` - 21,600 rows P&L data (2020-2024)
- Products: A, B, C, D
- Key column: `Amount in USD` for aggregations
- Filter by `FSLine Statement L1` (Net Revenue, Cost of Goods Sold, OPEX, Other Income/Expenses)
