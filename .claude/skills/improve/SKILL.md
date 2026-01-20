---
name: improve
description: Run the improvement loop - analyze failures and generate persistent learnings.
---

# Run Improvement Loop

Analyze failed queries from an evaluation run and generate improvements.

## Usage

```
/improve [run_id]
```

## Process

1. **Load Failures**: Read failed evaluations from `evals/results/<run_id>/`
2. **For Each Failure**:
   - Spawn `improver` agent with failure context
   - Agent diagnoses root cause
   - Agent generates appropriate improvement
   - Agent writes to `knowledge/`
3. **Verify**: Check that improvements were written correctly
4. **Report**: Summarize what was learned

## Workflow

```
/improve run_001
  │
  ├─> Load failures from evals/results/run_001/
  │
  ├─> For each failure:
  │     ├─> Analyze: What went wrong?
  │     ├─> Categorize: Example? Function? Doc?
  │     └─> Write: Update knowledge/
  │
  └─> Report: "Added 3 examples, 1 function, 2 doc entries"
```

## Output

```markdown
# Improvement Report: [run_id]

## Summary
- Failures analyzed: N
- Improvements generated: M
  - Examples: X
  - Functions: Y
  - Documentation: Z

## Changes Made

### knowledge/examples.md
- Added: [pattern name] for query [q_id]

### knowledge/functions.py
- Added: `function_name()` - [description]

### knowledge/learnings.md
- Added: [topic] - [summary]

## Next Steps
- Re-run evaluation to verify improvements
- Command: `/run-baseline test`
```

## Files Read

- `evals/results/<run_id>/*.json` - Failed evaluation results
- `knowledge/*` - Existing knowledge (to avoid duplicates)

## Files Written

- `knowledge/examples.md` - Worked examples
- `knowledge/functions.py` - Helper functions
- `knowledge/learnings.md` - Schema/data discoveries
