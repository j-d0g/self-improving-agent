# CLAUDE.md

> **Audience**: Claude Code CLI - context for assisting humans with this repository.
> For human documentation, see [README.md](./README.md).
> For Agent SDK working memory, see [agent/CLAUDE.md](./agent/CLAUDE.md).

This file provides guidance to Claude Code when working with this repository.

**Important**: This project implements agents using the **Claude Agent SDK** (Python), not Claude Code CLI. The `agent/` directory contains a standalone Python application - do not confuse it with Claude Code CLI features like `.claude/agents/` or auto-discovery.

## Overview

Self-improving financial analysis agent that answers P&L questions using pandas. The core innovation is **cross-session learning**: a two-agent pipeline (Learner → Improver) that persists learnings to files so future sessions benefit from past mistakes.

## Architecture

```
┌─────────────┐                      ┌─────────────┐
│   Learner   │────session trace────▶│  Improver   │
│   (Haiku)   │                      │  (Sonnet)   │
└─────────────┘                      └─────────────┘
       │                                    │
       ▼                                    ▼
  logs/sessions/                       knowledge/
```

- **Learner**: Answers queries, logs execution trace (thinking + tool calls + reflections)
- **Improver**: Analyzes session traces, identifies patterns/errors, applies fixes to knowledge files (restricted to `knowledge/` only)

## Commands

All commands run from `agent/` directory:

```bash
# Single query
python agent.py "What was revenue for Product A in Q1 2024?"

# Run evaluations
python evaluate.py train          # Training set (9 queries)
python evaluate.py test           # Test set (8 queries)

# Benchmarking
python evals/benchmark.py run           # Full benchmark
python evals/benchmark.py dashboard     # View visualizations
python evals/benchmark.py list          # List all runs
python evals/benchmark.py compare <run1> <run2>
```

## Key Files

| File | Purpose |
|------|---------|
| `agent/agent.py` | Core LearnerAgent + background improver |
| `agent/tracing.py` | ExecutionTrace, SessionTrace, metrics |
| `agent/evaluate.py` | Runs train/test evaluation sets |
| `agent/evals/benchmark.py` | Performance tracking with visualizations |

## Knowledge System

The learner reads these before answering queries:

| File | Purpose |
|------|---------|
| `knowledge/schema.md` | Data facts, column definitions, formulas, edge cases |
| `knowledge/examples.md` | Query patterns with working code |
| `knowledge/functions.py` | Reusable helper functions |

The improver updates these based on session traces.

## Log Structure

```
logs/
├── sessions/      # Session traces (JSON) - input to improver
├── improver/      # Improver traces (JSON) - execution history
└── reflections/   # Learner self-reflections (human reference)
```

Session traces contain full execution details (thinking, tool calls, answers) and are saved after each query so the improver can analyze them in real-time. Improver traces capture the improver's own execution (reasoning, file modifications, token usage).

## Dataset

`data/FUN_company_pl_actuals_dataset.csv` - 21,600 rows of P&L data
- **Products**: A, B, C, D (no others exist)
- **Countries**: Australia, Canada, Germany, Japan, United Kingdom, United States
- **Years**: 2020-2024
- **Metrics**: Revenue, COGS, OPEX, Other Income/Expenses

## Agent SDK Implementation

The Python agents (not Claude Code CLI):
- **Learner** (Haiku) - `agent/agent.py` with `prompts/learner.txt`
- **Improver** (Sonnet) - background task in `agent/agent.py` with `prompts/improver.txt`

These read `agent/CLAUDE.md` as their working memory via explicit file reads in their system prompts.

## Development Notes

- Agent SDK uses `ANTHROPIC_API_KEY` from `.env` file
- Session traces saved after each query to `logs/sessions/` (improver reads these)
- Reflection logs written to `logs/reflections/` for human debugging
- Improver is restricted to modifying only `knowledge/` directory
- Agent version tracked via git commit in execution traces

## RULES!

- NEVER SET THIS UP WITHOUT A VIRTUAL ENVIRONMENT! ALWAYS USE A .venv.