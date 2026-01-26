# ACE: Agentic Counterfactual Expansion

A 3-agent pipeline for self-improving question answering, inspired by Stanford's ACE framework.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  BATCH LOOP                                                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. SOLVER (Haiku) - Parallel query execution                │
│     └─ Output: answer + bullet_ids_used                      │
│                                                              │
│  2. REFLECTOR (Haiku) - Judge + tag bullets                  │
│     └─ Output: correct/incorrect, helpful/harmful tags       │
│                                                              │
│  3. CURATOR (Sonnet) - Apply delta operations                │
│     └─ Output: ADD/UPDATE/DELETE to knowledge files          │
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
python train.py --no-improve
```

> **Note**: ACE has its own `knowledge/` directory, separate from V1's `agent/knowledge/`. Training data and the dataset are shared with V1 (from `agent/evals/` and `agent/data/`).

## Key Concepts

### Bullet Format
Knowledge files use trackable bullets with counters:
```markdown
[ex-00001] helpful=5 harmful=1 :: CAGR calculation pattern
  Code: cagr = (end/start) ** (1/years) - 1
```

- **ID**: Unique identifier (e.g., `ex-00001`, `sch-00003`)
- **Counters**: `helpful` and `harmful` track effectiveness
- **Content**: The actual knowledge

### Learning Flow

1. **Solver** answers queries, citing bullets used: `"Using [sch-00016]..."`
2. **Reflector** judges correctness, tags each bullet:
   - `helpful` - contributed to correct answer
   - `harmful` - led to incorrect answer
   - `neutral` - cited but didn't affect outcome
3. **Curator** analyzes accumulated tags:
   - DELETE bullets where `harmful > helpful`
   - UPDATE bullets that need refinement
   - ADD new bullets for knowledge gaps

## File Structure

```
ace/
├── train.py              # CLI entry point
├── orchestrator.py       # Pipeline coordination
├── solver.py             # Query execution agent (single & multi-turn)
├── reflector.py          # Answer judging + bullet tagging
├── curator.py            # Knowledge file updates
├── playbook_utils.py     # Bullet parsing/updating
├── knowledge/
│   ├── schema.md         # Dataset facts [sch-*]
│   ├── examples.md       # Query patterns [ex-*]
│   └── functions.py      # Helper functions
└── logs/
    ├── tags.jsonl        # Accumulated bullet tags
    ├── training/         # Training run logs
    └── curator/          # Curator operation logs
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

```
python train.py [OPTIONS]

Options:
  --epochs N          Number of epochs (default: 3)
  --batch-size N      Queries per batch (default: 4)
  --no-improve        Disable Curator (baseline mode)
  -q, --quiet         Minimal output
  --train-file PATH   Custom training queries
  --test-file PATH    Custom validation queries
```

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

============================================================
EPOCH 1
============================================================
[Batch 1] Running 4 queries...
[Batch 1] Accuracy: 3/4 (75%)
[Curator] Applied 1 operations
...

============================================================
TRAINING SUMMARY
============================================================
Final train accuracy: 88.9%
Final validation accuracy: 75.0%
Total tokens: 45,230
Total cost: $0.1523
```
