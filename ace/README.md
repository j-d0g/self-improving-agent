# ACE: Agentic Counterfactual Expansion

A 4-component pipeline for self-improving question answering, inspired by Stanford's ACE framework.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  PER QUERY                                                   │
├─────────────────────────────────────────────────────────────┤
│  1. SOLVER (Haiku) - Query execution                         │
│     └─ Output: answer + bullet_ids_used + execution trace    │
│                                                              │
│  2. REFLECTOR (Haiku) - Deep trace analysis                  │
│     └─ Output: issues_found, bullet_tags, suggested_deltas   │
├─────────────────────────────────────────────────────────────┤
│  PER BATCH                                                   │
├─────────────────────────────────────────────────────────────┤
│  3. CURATOR (Sonnet) - Immediate, safe changes               │
│     └─ Counter updates (deterministic)                       │
│     └─ High-confidence ADDs (>= 0.8)                         │
│     └─ Deferred proposals → Aggregator                       │
├─────────────────────────────────────────────────────────────┤
│  PER EPOCH                                                   │
├─────────────────────────────────────────────────────────────┤
│  4. AGGREGATOR (Opus) - Strategic, structural changes        │
│     └─ Pattern analysis across batch                         │
│     └─ Apply deferred proposals                              │
│     └─ Prune harmful bullets, merge duplicates               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# From project root
cd ace
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run training (3 epochs, batch_size=4)
python train.py

# Quick test (1 epoch, quiet mode)
python train.py --epochs 1 -q

# Baseline without learning
python train.py --baseline
```

> **Note**: ACE has its own `knowledge/` directory, separate from V1's `agent/knowledge/`. Training data and the dataset are shared with V1 (from `agent/evals/` and `agent/data/`).

## Key Concepts

### Bullet Format
The playbook uses trackable bullets with counters:
```markdown
[sch-00001] helpful=5 harmful=1 :: Column `Fiscal Year` (int64) - Year of the fiscal period
[str-00002] helpful=3 harmful=0 :: Always validate product names before querying
[calc-00001] helpful=2 harmful=0 :: CAGR = (End/Start)^(1/Years) - 1
```

- **ID Prefixes**: Section-specific identifiers:
  - `sch-` Schema (column definitions)
  - `str-` Strategies & Insights
  - `calc-` Formulas & Calculations
  - `code-` Code Templates
  - `edge-` Edge Cases & Pitfalls
  - `err-` Common Mistakes
  - `interp-` Query Interpretation
- **Counters**: `helpful` and `harmful` track effectiveness
- **Content**: The actual knowledge (can include multi-line code blocks)

### Learning Flow

1. **Solver** answers queries, citing bullets used: `"Using [sch-00016]..."`
2. **Reflector** performs deep trace analysis:
   - Tool efficiency (redundant calls, wrong tools)
   - Reasoning soundness (flawed assumptions, logic errors)
   - Self-consistency (answer matches computation)
   - Issues found (knowledge gaps, errors)
   - Bullet tags (helpful/harmful/neutral)
   - Suggested deltas (ADD/UPDATE/DELETE with confidence)
3. **Curator** applies immediate, safe changes:
   - Counter updates (deterministic from tags)
   - High-confidence ADDs (confidence >= 0.8)
   - Defers structural changes to Aggregator
4. **Aggregator** makes strategic decisions per epoch:
   - Analyzes failure patterns across batch
   - Applies deferred proposals with batch-level context
   - Prunes harmful bullets, merges duplicates
   - Creates new categories when justified

## File Structure

```
ace/
├── train.py              # Training CLI entry point
├── agent.py              # Interactive agent with background learning
├── chat.py               # Chat utilities
├── orchestrator.py       # Pipeline coordination
├── solver.py             # Query execution agent (single & multi-turn)
├── reflector.py          # Deep trace analysis + suggested deltas
├── curator.py            # Immediate changes + deferred proposals
├── aggregator.py         # Batch-level strategic decisions (Opus)
├── playbook_utils.py     # Bullet parsing/updating
├── DESIGN.md             # Architecture design document
├── knowledge/
│   └── playbook.md       # Unified playbook with all sections
├── evals/
│   ├── benchmark.py      # Benchmark CLI (run/list/compare/dashboard)
│   ├── dashboard.py      # HTML dashboard generation
│   └── dashboards/       # Generated HTML dashboards
└── logs/
    ├── solver/           # Per-query execution traces (JSON)
    ├── reflector/        # Reflector analysis logs (JSON)
    ├── curator/          # Curator operation logs (JSON)
    ├── aggregator/       # Aggregator decision logs (JSON)
    ├── tags.jsonl        # Accumulated bullet tags
    └── training/         # Training run logs (JSON)
```

## Solver Usage

The SolverAgent supports two modes:

### Single-turn (default)
```python
solver = SolverAgent()
result = await solver.solve("What was revenue in 2023?")
# Fresh session each call - no context preserved
```

### Multi-turn (context manager)
```python
async with SolverAgent() as solver:
    result1 = await solver.solve("What was revenue for Product A in 2023?")
    result2 = await solver.solve("How does that compare to 2022?")  # Remembers!
```

Multi-turn mode maintains conversation context via `ClaudeSDKClient`, enabling follow-up questions that reference prior exchanges.

> **Note**: The training pipeline (`train.py`) uses single-turn mode intentionally for deterministic, reproducible learning. Multi-turn mode is available for interactive use, debugging, or custom workflows.

## CLI Reference

### Training

```bash
python train.py [OPTIONS]

Options:
  --epochs N          Number of epochs (default: 3)
  --batch-size N      Queries per batch (default: 4)
  --baseline          Disable learning (no Curator/Aggregator)
  --no-aggregator     Disable Aggregator only (keep Curator)
  -q, --quiet         Minimal output
  --train-file PATH   Custom training queries
  --test-file PATH    Custom validation queries
```

### Benchmarking

```bash
python -m ace.evals.benchmark run                 # Run benchmark (3 epochs)
python -m ace.evals.benchmark run --epochs 1 -q   # Quick test
python -m ace.evals.benchmark run --baseline    # Baseline without learning
python -m ace.evals.benchmark list                # List all runs
python -m ace.evals.benchmark compare <r1> <r2>   # Compare two runs
```

### Dashboard

```bash
python -m ace.evals.dashboard                     # Latest run
python -m ace.evals.dashboard <run_id>            # Specific run
python -m ace.evals.dashboard --all               # Compare all runs
```

Dashboard features:
- Per-query rolling train accuracy
- Per-epoch validation accuracy
- Tokens, latency, tool calls per query
- Run comparison tables
- HTML output: `ace/evals/dashboards/`

### Interactive Mode

```bash
python agent.py                          # REPL mode
python agent.py "What was Q1 revenue?"   # Single query
```

Interactive mode runs the Solver with background Reflector tagging. Curator runs on session end.

## Comparison to V1

| Aspect | V1 (agent/) | V2 (ace/) |
|--------|-------------|-----------|
| Architecture | Learner + Improver | Solver + Reflector + Curator |
| Learning unit | Full knowledge rewrite | Delta operations on bullets |
| Execution | Sequential queries | Parallel batches |
| Feedback | Per-query improvement | Counter accumulation |
| Signal | Noisy (single query) | Aggregated (batch patterns) |
| Knowledge | `agent/knowledge/` | `ace/knowledge/` (independent) |
| Dataset | `agent/data/` | `agent/data/` (shared) |

## Dependencies

Uses the existing `agent/.venv` virtual environment:
- `claude-agent-sdk>=0.1.20` - Claude Code SDK for agent execution
- `pandas>=2.0.0` - Data analysis

## Authentication

ACE uses Claude CLI authentication (not API keys):
```bash
claude auth  # One-time setup
```

## Example Training Output

```
============================================================
ACE Training
============================================================
Training queries: 9 from train.json
Validation queries: 8 from test.json
Epochs: 3
Batch size: 4
Curator: enabled
Aggregator: enabled

============================================================
EPOCH 1
============================================================
[Batch 1] Running 4 queries...
[Reflector] 3/4 correct, 4 bullet tags
[Curator] Applied 1 operations

[Batch 2] Running 4 queries...
[Reflector] 4/4 correct, 3 bullet tags

[Aggregator] Running batch-level analysis...
[Aggregator] Made 2 decisions:
  - Applied: 1
  - Rejected: 1
  - Failure patterns detected: 1

[Validation] Running 8 queries...
[Validation] Accuracy: 6/8 (75%)

[Epoch 1 Summary]
  Train accuracy: 88%
  Validation accuracy: 75%
  Aggregator: 1 applied, 1 rejected, $0.0523
...

============================================================
TRAINING SUMMARY
============================================================
Final train accuracy: 88.9%
Final validation accuracy: 87.5%
Total tokens: 52,230
Total cost: $0.2134
```
