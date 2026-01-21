# Knowledge Base

This directory contains the **curated knowledge** that the learner agent uses to answer queries. It is updated by the improver agent based on evaluator recommendations.

## Files

| File | Purpose | Updated By |
|------|---------|------------|
| `schema.md` | Dataset documentation: columns, valid values, formulas, edge cases | Improver |
| `examples.md` | Query patterns with working code examples | Improver |
| `functions.py` | Reusable helper functions for common operations | Improver |

## How Knowledge Evolves

```
1. Learner encounters an error or inefficiency
           │
           ▼
2. Learner logs session to logs/sessions/
           │
           ▼
3. Evaluator analyzes, identifies root cause
           │
           ▼
4. Evaluator recommends knowledge update
           │
           ▼
5. Improver applies update to knowledge/
           │
           ▼
6. Future learner sessions benefit from new knowledge
```

## Guidelines

### schema.md
- Document ALL columns with exact names and data types
- List ALL valid values for categorical columns
- Include calculation formulas (Gross Profit, Operating Income, etc.)
- Document edge cases and boundaries (what doesn't exist in the data)
- Document gotchas (e.g., "Headcount Expenses" is $ amount, not employee count)

### examples.md
- One template per query pattern
- Include: Query, Interpretation, Working Code, Key Pattern
- Prioritize patterns that caused errors or inefficiency

### functions.py
- Add functions when the same code pattern appears 3+ times
- Include docstrings with usage examples

## Do NOT Put Here

- Raw session logs → `logs/sessions/`
- Evaluation reports → `logs/evaluations/`
- Improvement reports → `logs/improvements/`
- Execution traces → `logs/traces/`
