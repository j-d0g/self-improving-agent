# CLAUDE.md

> **Audience**: Claude Code CLI - context for assisting humans with this repository.
> For human documentation, see [README.md](./README.md).
> For Agent SDK working memory, see [agent/CLAUDE.md](./agent/CLAUDE.md).

This file provides guidance to Claude Code when working with this repository.

**Important**: This project implements agents using the **Claude Agent SDK** (Python), not Claude Code CLI. The `agent/` and `ace/` directories contain standalone Python applications - do not confuse them with Claude Code CLI features like `.claude/agents/` or auto-discovery.

## Implementations

| Directory | Architecture | Description |
|-----------|--------------|-------------|
| `agent/` | Learner + Improver | V1: Per-query improvement cycle |
| `ace/` | Solver → Reflector → Curator → Aggregator | V2: ACE pipeline with batch-based learning and delta operations |

## V1 Architecture (agent/)

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

## V2 Architecture (ace/)

```
Per Query:   SOLVER (Haiku) → REFLECTOR (Haiku)
Per Batch:   CURATOR (programmatic)
Per Epoch:   AGGREGATOR (Opus)
```

See `ace/README.md` for details.

## Commands

### V1 (agent/)

```bash
cd agent

# Single query
python agent.py "What was revenue for Product A in Q1 2024?"

# Benchmarking (with LLM judge scoring)
python evals/benchmark.py run                # 3 epochs, batch_size=2
python evals/benchmark.py run --epochs 1 -q  # Quick test, quiet mode
python evals/benchmark.py run --no-improve   # Baseline without improver
python evals/benchmark.py dashboard          # View visualizations
```

### V2 (ace/)

```bash
cd ace
source ../agent/.venv/bin/activate  # Use shared venv

# Run training
python train.py                      # 3 epochs, batch_size=4
python train.py --epochs 1 -q        # Quick test
python train.py --no-improve         # Baseline without Curator
```

## Key Files

### V1 (agent/)
| File | Purpose |
|------|---------|
| `agent/agent.py` | Core LearnerAgent + background improver |
| `agent/tracing.py` | ExecutionTrace, SessionTrace, metrics |
| `agent/evals/benchmark.py` | Benchmarking with LLM judge + dashboard |

### V2 (ace/)
| File | Purpose |
|------|---------|
| `ace/solver.py` | SolverAgent (single/multi-turn query execution) |
| `ace/reflector.py` | Answer judging + bullet tagging |
| `ace/curator.py` | Knowledge file delta operations |
| `ace/orchestrator.py` | Pipeline coordination |
| `ace/train.py` | CLI entry point |

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

- Agent SDK uses **Claude CLI authentication** (run `claude auth` to set up)
- Session traces saved after each query to `logs/sessions/` (improver reads these)
- Reflection logs written to `logs/reflections/` for human debugging
- Improver is restricted to `knowledge/` directory (enforced via SDK hooks)
- Budget limits: $0.50/query (learner), $0.25/run (improver) - configurable
- `permission_mode='acceptEdits'` enables deterministic execution without prompts
- `setting_sources=['project']` loads CLAUDE.md automatically via SDK
- Agent version tracked via git commit in execution traces

## RULES!

- NEVER SET THIS UP WITHOUT A VIRTUAL ENVIRONMENT! ALWAYS USE A .venv.