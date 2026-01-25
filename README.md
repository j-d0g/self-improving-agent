# Self-Improving Financial Analysis Agent

> **Audience**: Humans - project overview, setup, and usage instructions.
> For Claude Code context, see [CLAUDE.md](./CLAUDE.md).
> For Agent SDK working memory, see [agent/CLAUDE.md](./agent/CLAUDE.md).

An AI agent that answers financial questions about P&L data and **learns from its mistakes**. The agent generates pandas code, logs detailed reflections, and improves its knowledge base so future queries benefit from past errors.

## Key Feature: Cross-Session Learning

```
┌─────────────┐                      ┌─────────────┐
│   Learner   │────session trace────▶│  Improver   │
│   (Haiku)   │                      │  (Sonnet)   │
└─────────────┘                      └─────────────┘
       │                                    │
       ▼                                    ▼
  logs/sessions/                      knowledge/
  (execution traces with              (schema, examples,
   thinking + reflections)             helper functions)
```

1. **Learner** (Haiku) answers queries, logging execution traces with thinking, tool calls, and self-reflections
2. **Improver** (Sonnet) analyzes session traces, identifies patterns/errors, and propagates fixes to knowledge files

New learner sessions read the updated knowledge base before answering.

## Setup

```bash
cd agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Authenticate with Claude CLI (SDK uses CLI auth, not API key)
claude auth
```

## Usage

### Interactive Mode (Multi-turn)
```bash
cd agent
python agent.py
```
Conversation history is preserved across queries - the agent remembers previous questions and answers within the session.

### Single Query
```bash
cd agent
python agent.py "What was revenue for Product A in Q1 2024?"
```
One-shot mode with no conversation history.

## Evaluation Sets

| Set | Purpose | Queries |
|-----|---------|---------|
| `train.json` | **Populate knowledge** - mistakes trigger learning | 9 queries |
| `test.json` | **Benchmark efficiency** - measure improvement | 8 queries |

```bash
# Run training set (generates session traces, triggers improvement)
python evaluate.py train

# Run test set (measure accuracy & efficiency)
python evaluate.py test
```

## Benchmarking

```bash
python evals/benchmark.py run           # Full benchmark
python evals/benchmark.py dashboard     # View visualizations
python evals/benchmark.py list          # List all runs
python evals/benchmark.py compare <run1> <run2>
```

## Project Structure

```
agent/
├── CLAUDE.md                # Agent working memory (read via system prompt)
├── agent.py                 # Learner agent + background improver (Agent SDK)
├── evaluate.py              # Runs train/test evaluations
├── tracing.py               # Execution traces and metrics
├── prompts/
│   ├── learner.txt          # Learner system prompt
│   └── improver.txt         # Improver system prompt
├── data/
│   └── FUN_company_pl_actuals_dataset.csv
├── evals/
│   ├── benchmark.py         # Performance tracking
│   ├── train.json           # Training queries
│   └── test.json            # Test queries
├── knowledge/               # Learning artifacts (updated by improver)
│   ├── schema.md            # Dataset documentation
│   ├── examples.md          # Query patterns
│   └── functions.py         # Reusable helpers
└── logs/
    ├── sessions/            # Session traces (JSON) - input to improver
    └── reflections/         # Learner self-reflections (human reference)
```

## How Learning Works

### Session Traces

Every query is logged to `logs/sessions/` with full execution details. The improver reads these traces to identify patterns and errors. Session traces include:
- The original query and interpretation
- Turn-by-turn thinking and tool calls
- Final answer and any errors encountered
- Self-reflection on what went wrong

### Reflection Logs (Human Reference)

The learner also writes structured reflection logs to `logs/reflections/` for human debugging. These contain the same self-reflection content in a more readable markdown format.

### Knowledge Base

The learner reads these files before answering:

| File | Purpose |
|------|---------|
| `knowledge/schema.md` | Column definitions, valid values, rules |
| `knowledge/examples.md` | Query patterns with working code |
| `knowledge/functions.py` | Reusable helper functions |

The improver updates these based on session traces.

## Dataset

`FUN_company_pl_actuals_dataset.csv`:
- **21,600 rows** of P&L data
- **Years**: 2020-2024
- **Products**: A, B, C, D (no others exist)
- **Countries**: Australia, Canada, Germany, Japan, UK, US
- **Metrics**: Revenue, COGS, OPEX, Other Income/Expenses

## Example Queries

- "What was Gross Revenue for Product A in Q1 2024?"
- "Which product had the highest operating margin in 2023?"
- "Calculate year-over-year OPEX growth between 2022 and 2023"
- "What was revenue for Product E?" *(trick question - doesn't exist)*

## Session Logging

Every session logs a JSON trace to `logs/sessions/` with:
- Session metadata (timestamps, totals)
- Agent version (git commit)
- Per-query details with turn history (thinking + tool calls)
- Token usage and costs
- Final answers

```json
{
  "session_id": "20260121_081523",
  "agent_version": {"commit": "abc123", "dirty": false, "version": "abc123"},
  "start_time": "2026-01-21T08:15:23.799069",
  "end_time": "2026-01-21T08:53:02.719906",
  "total_queries": 2,
  "total_latency_seconds": 68.49,
  "total_tokens": 2851,
  "total_cost_usd": 0.236,
  "total_tool_calls": 10,
  "queries": [
    {
      "query": "...",
      "turns": [{"thinking": "...", "tool_calls": [...]}],
      "final_answer": "..."
    }
  ]
}
```
