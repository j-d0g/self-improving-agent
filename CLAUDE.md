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
│   Learner   │─────reflection──────▶│  Improver   │
│   (Haiku)   │                      │  (Sonnet)   │
└─────────────┘                      └─────────────┘
       │                                    │
       ▼                                    ▼
  logs/reflections/                    knowledge/
```

- **Learner**: Answers queries, logs process + self-reflection
- **Improver**: Judges reflections, consolidates feedback, applies fixes to knowledge files (restricted to `knowledge/` only)

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
| `agent/agent.py` | Core LearnerAgent using Agent SDK |
| `agent/improver.py` | ImproverAgent that updates knowledge files |
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

The improver updates these based on learner reflection logs.

## Log Structure

```
logs/
├── sessions/      # Learner output (markdown with XML tags)
├── reflections/   # Self-reflection logs from sessions
├── improvements/  # Improver reports
└── traces/        # Raw JSON execution traces
```

## Dataset

`data/FUN_company_pl_actuals_dataset.csv` - 21,600 rows of P&L data
- **Products**: A, B, C, D (no others exist)
- **Countries**: Australia, Canada, Germany, Japan, United Kingdom, United States
- **Years**: 2020-2024
- **Metrics**: Revenue, COGS, OPEX, Other Income/Expenses

## Agent SDK Implementation

The Python agents (not Claude Code CLI):
- **Learner** (Haiku) - `agent/agent.py` with `prompts/learner.txt`
- **Improver** (Sonnet) - `agent/improver.py` with `prompts/improver.txt`

These read `agent/CLAUDE.md` as their working memory via explicit file reads in their system prompts.

## Development Notes

- Agent SDK uses `ANTHROPIC_API_KEY` from `.env` file
- Reflection logs are mandatory - every query must produce a file in `logs/reflections/`
- Improver is restricted to modifying only `knowledge/` directory
- Agent version tracked via git commit in execution traces

## RULES!

- NEVER SET THIS UP WITHOUT A VIRTUAL ENVIRONMENT! ALWAYS USE A .venv.