---
name: review
description: Review evaluation results and summarize performance across a test run.
---

# Review Evaluation Results

Analyze evaluation outputs and produce a summary report.

## Usage

```
/review [run_id]
```

## Process

1. **Load Results**: Read evaluation results from `evals/results/<run_id>/`
2. **Compute Metrics**:
   - Total queries: N
   - Correct: X (Y%)
   - Incorrect: Z
   - By difficulty: Easy/Medium/Hard breakdown
3. **Identify Patterns**: Group failures by error type
4. **Generate Report**: Write summary to `evals/results/<run_id>/summary.md`

## Output Format

```markdown
# Evaluation Summary: [run_id]

## Overall Performance
- **Score:** X/N (Y%)
- **Model:** [model used]
- **Timestamp:** [when run]

## Results by Difficulty
| Difficulty | Correct | Total | Rate |
|------------|---------|-------|------|
| Easy       | X       | Y     | Z%   |
| Medium     | X       | Y     | Z%   |
| Hard       | X       | Y     | Z%   |

## Failures

### [Query ID]: [Short description]
- **Expected:** [ground truth]
- **Got:** [agent answer]
- **Error type:** [classification]

## Recommendations
- [Suggested improvements based on failure patterns]
```

## Files Read

- `evals/results/<run_id>/*.json` - Individual evaluation results
- `evals/train.json` or `evals/test.json` - Query metadata

## Files Written

- `evals/results/<run_id>/summary.md` - Human-readable summary
