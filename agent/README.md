# Financial Analysis Agent

A coding agent that answers financial questions about P&L data using pandas. Features a complete self-improvement loop with evaluation and automated learning.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env  # or create .env file
# Edit .env and add your ANTHROPIC_API_KEY
```

## Architecture

```
agent/
├── agent.py              # Core financial analysis agent (Claude Code SDK)
├── evaluator.py          # Evaluator agent (Python wrapper)
├── orchestrator.py       # Automated evaluation orchestration
├── eval_runner.py        # Runs evaluation queries
├── demo.py               # Demo script
├── tracing.py            # Shared tracing/metrics
│
├── .claude/agents/       # Subagent definitions (Claude Code SDK)
│   ├── learner.md        # Query answering agent (haiku)
│   ├── evaluator.md      # Session analysis agent (opus)
│   └── improver.md       # Knowledge updater agent (sonnet)
│
├── knowledge/            # Curated knowledge base (updated by improver)
│   ├── schema.md         # Dataset documentation
│   ├── examples.md       # Query patterns
│   └── functions.py      # Helper functions
│
├── logs/                 # All execution logs
│   ├── sessions/         # Learner session logs (markdown)
│   ├── evaluations/      # Evaluator judgments (markdown)
│   ├── improvements/     # Improver reports (markdown)
│   └── traces/           # Raw execution traces (JSON)
│
├── evals/                # Test sets
│   ├── train.json
│   └── test.json
│
├── prompts/              # System prompts (Python agent)
│   ├── learner.txt
│   └── evaluator.txt
│
└── data/
    └── FUN_company_pl_actuals_dataset.csv
```

## Self-Improvement Loop

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Agent     │────▶│ Eval Runner │────▶│  Evaluator  │
│  (agent.py) │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                                       │
       │                                       │
       └───────── knowledge/ updates ◀─────────┘
```

**Manual workflow:**
1. **Agent** answers financial questions, logs traces
2. **Eval Runner** runs test queries, compares against expected answers
3. **Evaluator** analyzes results, identifies patterns, suggests/applies improvements
4. **Knowledge files** get updated, improving future agent performance

**Automated workflow (Orchestrator):**
```
┌──────────────────────────────────────────────────────────┐
│                    Orchestrator                          │
│  ┌─────────┐    ┌───────────┐    ┌────────────────────┐ │
│  │  Agent  │───▶│ Evaluator │───▶│ Knowledge Updates  │ │
│  └─────────┘    └───────────┘    └────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

The orchestrator automates evaluation with multiple modes:
- **inline**: Evaluate after every query (thorough but slow)
- **batch**: Evaluate after N queries (balanced)
- **background**: Queue evaluations asynchronously (fast responses)

## Usage

### Interactive Mode
```bash
python agent.py
```

### Single Query
```bash
python agent.py "What was the total revenue for Product A in Q1 2024?"
```

### Demo
```bash
python demo.py
```

### Run Evaluations (Manual)
```bash
# Run evaluation queries
python eval_runner.py evals/train.json

# Analyze results and get improvement suggestions
python evaluator.py

# Analyze and auto-apply improvements
python evaluator.py --apply

# Analyze recent execution traces
python evaluator.py --traces 20
```

### Automated Self-Improvement (Orchestrator)
```bash
# Interactive with batch evaluation (every 5 queries)
python orchestrator.py

# Evaluate after every query
python orchestrator.py --inline

# Auto-apply improvements after evaluation
python orchestrator.py --inline --auto

# Background async evaluation (fast responses)
python orchestrator.py --background

# Custom batch size
python orchestrator.py --batch 3

# Single query with full automation
python orchestrator.py --inline --auto "What was revenue in Q1 2024?"
```

## Components

### Financial Analysis Agent (`agent.py`)
- Uses Claude Code SDK with Read and Bash tools
- Executes pandas code via shell commands
- Reads knowledge files for context before answering
- Logs execution traces for analysis

### Evaluator Agent (`evaluator.py`)
- Analyzes evaluation results (expected vs actual answers)
- Identifies error patterns and inefficiencies
- Suggests improvements to knowledge files
- Can auto-apply improvements with `--apply` flag

### Evaluation Runner (`eval_runner.py`)
- Runs queries from evaluation files
- Captures results with metrics (tokens, tool calls, cost)
- Compares agent answers against expected answers

### Orchestrator (`orchestrator.py`)
- Wraps agent + evaluator for automated self-improvement
- Multiple evaluation modes:
  - `inline`: Evaluate every query immediately
  - `batch`: Evaluate after N queries (default: 5)
  - `background`: Async evaluation in separate thread
- Optional auto-apply of improvements to knowledge files

## Dataset

The agent analyzes `FUN_company_pl_actuals_dataset.csv`:
- **Products:** A, B, C, D
- **Countries:** Australia, Canada, Germany, Japan, UK, US
- **Years:** 2020-2024
- **Metrics:** Revenue, COGS, OPEX, Other Income/Expenses

See `knowledge/schema.md` for full schema.

## Knowledge System

The agent improves through accumulated knowledge:

| File | Purpose |
|------|---------|
| `knowledge/schema.md` | Dataset column definitions, valid values |
| `knowledge/examples.md` | Query patterns with working code |
| `knowledge/learnings/` | Captured insights from tricky queries |

The evaluator agent identifies gaps and can update these files to prevent repeated mistakes.
