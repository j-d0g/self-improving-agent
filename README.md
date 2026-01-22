# Self-Improving Financial Analysis Agent

> **Audience**: Humans - project overview, setup, and usage instructions.
> For Claude Code context, see [CLAUDE.md](./CLAUDE.md).
> For Agent SDK working memory, see [agent/CLAUDE.md](./agent/CLAUDE.md).

An AI agent that answers financial questions about P&L data and **learns from its mistakes**. The agent generates pandas code, logs detailed reflections, and improves its knowledge base so future queries benefit from past errors.

## Key Feature: Cross-Session Learning

```
┌─────────────┐                      ┌─────────────┐
│   Learner   │─────reflection──────▶│  Improver   │
│   (Haiku)   │                      │  (Sonnet)   │
└─────────────┘                      └─────────────┘
       │                                    │
       ▼                                    ▼
  logs/reflections/                   knowledge/
  (errors, root causes,               (schema, examples,
   suggested fixes)                    helper functions)
```

1. **Learner** (Haiku) answers queries and self-reflects on errors, dead ends, and root causes
2. **Improver** (Sonnet) judges reflections, consolidates feedback, and propagates fixes to knowledge files

New learner sessions read the updated knowledge base before answering.

## Setup

```bash
cd agent
pip install -r requirements.txt

# Create .env with your API key
echo "ANTHROPIC_API_KEY=your-key" > .env
```

## Usage

### Interactive Mode
```bash
cd agent
python agent.py
```

### Single Query
```bash
cd agent
python agent.py "What was revenue for Product A in Q1 2024?"
```

## Evaluation Sets

| Set | Purpose | Queries |
|-----|---------|---------|
| `train.json` | **Populate knowledge** - mistakes trigger learning | 9 queries |
| `test.json` | **Benchmark efficiency** - measure improvement | 8 queries |

```bash
# Run training set (generates reflection logs)
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
├── agent.py                 # Learner agent implementation (Agent SDK)
├── improver.py              # Updates knowledge files from reflections
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
    ├── reflections/         # Learner reflection logs
    ├── improvements/        # Improver reports
    └── traces/              # Raw JSON execution traces
```

## How Learning Works

### Reflection Logs

Every query produces a structured reflection log in `logs/reflections/`:

```markdown
<query>What was revenue for Product E?</query>

<interpretation>...</interpretation>

<process>Step-by-step execution...</process>

<answer>Product E does not exist...</answer>

<errors>KeyError when filtering...</errors>

<root_cause_analysis>
Missing validation for product names...
</root_cause_analysis>

<suggested_improvements>
Add product validation to schema.md...
</suggested_improvements>
```

### Knowledge Base

The learner reads these files before answering:

| File | Purpose |
|------|---------|
| `knowledge/schema.md` | Column definitions, valid values, rules |
| `knowledge/examples.md` | Query patterns with working code |
| `knowledge/functions.py` | Reusable helper functions |

The improver updates these based on learner reflection logs.

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

## Trace Logging

Every session logs a JSON trace to `logs/traces/` with:
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
