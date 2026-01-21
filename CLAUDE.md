# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Self-improving financial analysis agent that answers P&L questions using pandas. The core innovation is **cross-session learning**: a three-agent pipeline (Learner → Evaluator → Improver) that persists learnings to files so future sessions benefit from past mistakes.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Learner   │────▶│  Evaluator  │────▶│  Improver   │
│   (Haiku)   │     │   (Opus)    │     │  (Sonnet)   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
  logs/sessions/     logs/evaluations/    knowledge/
```

- **Learner**: Answers queries, logs process + self-reflection
- **Evaluator**: Critiques logs for correctness/efficiency, generates improvement specs
- **Improver**: Applies specs to knowledge files (restricted to `knowledge/` only)

## Commands

All commands run from `agent/` directory:

```bash
# Single query
python agent.py "What was revenue for Product A in Q1 2024?"

# Run evaluations
python evaluate.py train          # Training set (9 queries)
python evaluate.py test           # Test set (9 queries)

# Benchmarking
python benchmark.py run           # Full benchmark
python benchmark.py dashboard     # View visualizations
python benchmark.py list          # List all runs
python benchmark.py compare <run1> <run2>
```

## Key Files

| File | Purpose |
|------|---------|
| `agent/agent.py` | Core LearnerAgent using Claude SDK |
| `agent/improver.py` | ImproverAgent that updates knowledge files |
| `agent/tracing.py` | ExecutionTrace, SessionTrace, metrics |
| `agent/evaluate.py` | Runs train/test evaluation sets |
| `agent/benchmark.py` | Performance tracking with visualizations |

## Knowledge System

The learner reads these before answering queries:

| File | Purpose |
|------|---------|
| `knowledge/schema.md` | Dataset column definitions, valid values |
| `knowledge/examples.md` | Query patterns with working code |
| `knowledge/functions.py` | Reusable helper functions |

The improver updates these based on evaluator feedback.

## Log Structure

```
logs/
├── sessions/      # Learner output (markdown with XML tags)
├── evaluations/   # Evaluator judgments
├── improvements/  # Improver reports
└── traces/        # Raw JSON execution traces
```

## Dataset

`data/FUN_company_pl_actuals_dataset.csv` - 21,600 rows of P&L data
- **Products**: A, B, C, D (no others exist)
- **Countries**: Australia, Canada, Germany, Japan, United Kingdom, United States
- **Years**: 2020-2024
- **Metrics**: Revenue, COGS, OPEX, Other Income/Expenses

## Claude Code Agents

Defined in `agent/.claude/agents/`:
- `learner.md` - Haiku model, answers financial queries, writes session logs
- `evaluator.md` - Opus model, critiques session logs
- `improver.md` - Sonnet model, applies knowledge updates

## Development Notes

- Agent uses Claude CLI authentication (not .env ANTHROPIC_API_KEY)
- Session logs are mandatory - every query must produce a file in `logs/sessions/`
- Improver is restricted to modifying only `knowledge/` directory
- Agent version tracked via git commit in execution traces
