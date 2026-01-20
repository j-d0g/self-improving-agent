---
name: run-baseline
description: Spawn data-analyst agents to answer queries about the P&L dataset.
---

# Run Baseline

Spawn a `data-analyst` agent for each query the user specifies.

```
Task tool parameters:
- subagent_type: "data-analyst"
- model: "haiku"
- prompt: |
    Answer this question about the P&L dataset.

    **Query ID:** [e.g., q01, q17, q23 - from tests/test_queries.md]
    **Question:** [query text]

    **Data file:** data/FUN_company_pl_actuals_dataset.csv

    Show your work. If you encounter errors or ambiguity, document them honestly.
```

When spawning agents, always include the Query ID from the test file (q01-q25).
