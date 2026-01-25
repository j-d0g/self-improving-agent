# Benchmark V2: Evaluation Framework

> Measure learning progress with LLM-based accuracy scoring and train/validation separation.

---

## Quick Start

```bash
cd agent

# Default: 3 epochs, batch_size=2, with LLM judge scoring
python evals/benchmark.py run

# Quick test (1 epoch)
python evals/benchmark.py run --epochs 1

# Quiet mode (suppress agent output)
python evals/benchmark.py run -q

# Baseline without improver
python evals/benchmark.py run --no-improve

# View dashboard
python evals/benchmark.py dashboard

# List all runs
python evals/benchmark.py list

# Compare two runs
python evals/benchmark.py compare run_20260125_101416 run_20260125_142030
```

---

## How It Works

### Execution Flow

```
For each epoch (1..num_epochs):
    Shuffle train_set (9 queries)

    For each batch (batch_size queries):
        For each query:
            1. Run query with improver ON
            2. Wait for improvement to complete
            3. Judge answer with Haiku LLM
            4. Record: tokens, tool_calls, latency, judge_score
            5. Update rolling averages

        After batch: Run validation
            1. Run all test queries with improver OFF
            2. Judge each answer
            3. Record validation checkpoint

    Record epoch checkpoint (train + validation averages)
```

### LLM Judge

Uses Haiku for binary correctness scoring:

| Score | Meaning |
|-------|---------|
| 1.0 | Correct - answer conveys the same information as expected |
| 0.0 | Wrong - factually incorrect, missing key info, or wrong conclusion |

The judge handles numeric equivalence ($1.2M = $1,200,000), semantic equivalence, and validates "not available" answers. Process quality (efficiency, reasoning steps) is tracked separately via `tokens` and `tool_calls` metrics.

---

## CLI Options

```
python evals/benchmark.py run [OPTIONS]

Options:
    --epochs N          Number of full passes through train set (default: 3)
    --batch-size N      Queries per batch before validation (default: 2)
    --window N          Rolling average window size (default: 5)
    --no-improve        Disable improver (for baseline comparison)
    --quiet, -q         Suppress agent streaming output
```

---

## Output

### Terminal

```
======================================================================
  BENCHMARK: run_20260125_142030
======================================================================
  Epochs: 3 (9 queries/epoch = 27 total)
  Batch size: 2
  Models: learner=haiku, improver=sonnet
  Improver: enabled
======================================================================

EPOCH 1
  [  1/27] ✓ tokens: 2341  tools: 5  score: 1.0  │  rolling: 2341 tok, 1.00 score
  [  2/27] ✓ tokens: 1892  tools: 4  score: 1.0  │  rolling: 2117 tok, 1.00 score
  ── VALIDATION (batch 1) ── test: 2456 tok, 0.88 score ──
  [  3/27] ✓ tokens: 1654  tools: 3  score: 1.0  │  rolling: 1962 tok, 1.00 score
  ...
──────────────────────────────────────────────────────────────────────
  EPOCH 1 COMPLETE
  Train:      1892 tokens, 0.89 score
  Validation: 2345 tokens, 0.88 score
──────────────────────────────────────────────────────────────────────
```

### JSON Run File

`evals/benchmarks/runs/run_{timestamp}.json`

```json
{
  "run_id": "run_20260125_142030",
  "num_epochs": 3,
  "batch_size": 2,
  "improve_enabled": true,
  "query_results": [
    {
      "query_num": 1,
      "epoch": 1,
      "batch": 1,
      "query": "What was Gross Revenue for Product A in Q1 2020?",
      "expected_answer": "$1,344,323.16",
      "agent_answer": "The Gross Revenue was $1,344,323.16",
      "tokens": 2341,
      "tool_calls": 5,
      "judge_score": 1.0,
      "judge_reason": "Exact numeric match",
      "rolling_avg_tokens": 2341,
      "rolling_avg_score": 1.0,
      "status": "success"
    }
  ],
  "validation_checkpoints": [
    {
      "epoch": 1,
      "batch": 1,
      "query_num_after": 2,
      "avg_tokens": 2456,
      "avg_tool_calls": 5.5,
      "avg_judge_score": 0.88
    }
  ],
  "epoch_checkpoints": [
    {
      "epoch": 1,
      "train_avg_tokens": 1892,
      "train_avg_judge_score": 0.89,
      "validation_avg_tokens": 2345,
      "validation_avg_judge_score": 0.88
    }
  ],
  "avg_train_judge_score": 0.89,
  "avg_validation_judge_score": 0.88
}
```

### Dashboard

`evals/benchmarks/dashboard.html` - Auto-opens after each run

**Charts:**
- **Performance x Epoch** - Train vs validation judge scores by epoch (learning curve)
- **Tokens x Epoch** - Token usage by epoch
- **Rolling Training vs Validation** - Fine-grained view with validation checkpoints
- **Avg Score Across Runs** - Historical train/val scores
- **Avg Tokens Across Runs** - Historical efficiency

**Metric Cards:**
- Avg Judge Score (latest validation)
- Avg Tokens/Query (with % change)
- Total Epochs Run (across all runs)
- Train vs Val Gap (overfitting indicator)

---

## Interpretation Guide

### Good Learning Signal

- Train score increases over epochs
- Validation score also increases (generalization)
- Train-Val gap stays small (<0.1)
- Token usage decreases over time

### Overfitting Signal

- Train score increases but validation flat/decreasing
- Train-Val gap grows (>0.1)
- Knowledge files contain query-specific hacks

### No Learning Signal

- Both train and validation scores flat
- Token usage unchanged
- Knowledge files unchanged or trivial additions

---

## Data Sets

| File | Purpose | Queries |
|------|---------|---------|
| `train.json` | Learning - mistakes trigger improvement | 9 |
| `test.json` | Validation - measure generalization | 8 |

Train queries are shuffled each epoch. Validation runs after every batch with improver disabled.

---

## Comparing Runs

```bash
python evals/benchmark.py compare run_20260125_090340 run_20260125_142030
```

Output:
```
Metric                    run_20260125_09 run_20260125_14 Change
----------------------------------------------------------------------
Epochs                    3               3               +0
Total Queries             27              27              +0
Avg Tokens/Query          3481.62         2349.33         -1132.29
Train Judge Score         0.78            0.89            +0.11
Val Judge Score           0.75            0.88            +0.13
```

---

## Architecture

```
benchmark.py
├── judge_answer()           # Haiku LLM judge for accuracy scoring
├── BenchmarkSuite
│   ├── run_benchmark()      # Main execution loop
│   ├── generate_dashboard() # HTML visualization
│   └── list_runs()          # List historical runs
└── Data Structures
    ├── QueryResult          # Per-query metrics + judge score
    ├── ValidationCheckpoint # Post-batch validation metrics
    ├── EpochCheckpoint      # Epoch-level aggregates
    └── BenchmarkRun         # Complete run with all data
```
