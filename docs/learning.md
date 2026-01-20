# Learning Mechanism

This document describes how the agent learns from mistakes and persists that knowledge for future sessions.

## Core Principle: Error-Driven Learning

The agent only learns when it **recovers from an error**. This is a deliberate design choice based on research and practical considerations.

### Why Error-Driven?

1. **Clear signal**: Errors provide unambiguous evidence that something was learned
2. **Avoids noise**: Prevents accumulation of trivial or redundant learnings
3. **Research-backed**: Per "When Can LLMs Actually Correct Their Own Mistakes?" (TACL 2024), self-correction is most effective with external feedback
4. **Natural filter**: Only genuinely useful patterns get persisted

### Learning Trigger Conditions

```
Learning is triggered when:
  1. An error was encountered (errors_encountered > 0)
  2. The error was recovered from (error_recovered = True)
  3. The agent edits a file in knowledge/learned/
```

**NOT triggered when**:
- Query succeeds on first try (nothing to learn)
- Error occurs but not recovered (learning would be incomplete)
- Agent decides the pattern isn't generalizable

## Learning Artifacts

### Guidelines (`knowledge/learned/guidelines.md`)

Text descriptions of lessons learned, formatted for the agent to read.

**Format**:
```markdown
### [Error Type]: [Brief Description]
**Error**: [What went wrong]
**Cause**: [Root cause]
**Fix**: [How to avoid this]
```

**Example**:
```markdown
### VALIDATION_ERROR: Non-existent Product Query
**Error**: User asked about "Product Z" which doesn't exist in the dataset
**Cause**: Dataset only contains Products A, B, C, and D
**Fix**: Always validate product existence before attempting calculations.
Check df['Product'].unique() and inform user of available products.
```

**When to use**: Error patterns that require understanding or judgment, not just code.

### Functions (`knowledge/learned/functions.py`)

Reusable Python functions that prevent classes of errors.

**Format**:
```python
def get_quarter_months(quarter: str) -> list:
    """
    Return the months that comprise a fiscal quarter.

    Learned from: Q1 only returning January instead of Jan-Mar
    """
    quarters = {
        'Q1': ['01', '02', '03'],
        'Q2': ['04', '05', '06'],
        'Q3': ['07', '08', '09'],
        'Q4': ['10', '11', '12']
    }
    return quarters.get(quarter, [])
```

**When to use**: Error patterns that can be codified into a reusable function.

### Design Decision: Two Learning Types

| Type | Storage | Best For |
|------|---------|----------|
| Guidelines | Markdown | Conceptual understanding, judgment calls |
| Functions | Python | Mechanical transformations, calculations |

**Rationale**: Some learnings are better expressed as rules (guidelines), others as code (functions). The agent chooses based on the nature of the error.

## Learning Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                     Error Recovery Flow                      │
│                                                             │
│  1. Execute code                                            │
│         │                                                   │
│         ▼                                                   │
│  2. Error detected (verification fails)                     │
│         │                                                   │
│         ▼                                                   │
│  3. Agent receives feedback with recovery hint              │
│         │                                                   │
│         ▼                                                   │
│  4. Agent fixes code and retries                            │
│         │                                                   │
│         ▼                                                   │
│  5. Success! Agent analyzes what was learned                │
│         │                                                   │
│         ▼                                                   │
│  6. Agent decides: Is this generalizable?                   │
│         │                                                   │
│    ┌────┴────┐                                              │
│    │         │                                              │
│    ▼         ▼                                              │
│  [YES]     [NO]                                             │
│    │         │                                              │
│    ▼         └──────▶ Done (no learning persisted)          │
│  7. Edit knowledge/learned/ files                           │
│         │                                                   │
│         ▼                                                   │
│  8. Reload learned functions into namespace                 │
│         │                                                   │
│         ▼                                                   │
│     Done (learning persisted)                               │
└─────────────────────────────────────────────────────────────┘
```

## System Prompt Guidance

The agent is instructed via system prompt on when and how to learn:

```
### Step 4: Error Recovery and Learning (CRITICAL)
If ANY error signal is detected:

1. **STOP and analyze**: What went wrong? Classify the error:
   - DATA_FILTER_ERROR: Wrong column name, value, or filter logic
   - CALCULATION_ERROR: Wrong formula or aggregation
   - EDGE_CASE_ERROR: Didn't handle quarter boundaries, negative values, etc.
   - VALIDATION_ERROR: Asked about non-existent product/country/etc.

2. **Fix and retry**: Correct the code and execute again

3. **PERSIST THE LEARNING** (only after successful recovery):
   - Edit knowledge/learned/guidelines.md: Add a guideline
   - Edit knowledge/learned/functions.py: Add helper function if reusable

## When NOT to Learn
- Do NOT persist learnings if the query succeeded on first try
- Do NOT add helper functions for one-off calculations
- Only persist learnings that would prevent a CLASS of errors
```

## Learning Quality Control

### Avoid Learning Noise

The agent is instructed to only persist learnings that:
1. **Prevent a class of errors** - Not just one specific instance
2. **Are generalizable** - Apply to future queries, not just this one
3. **Add new knowledge** - Don't duplicate existing guidelines

### Marker-Based Editing

Learning files use markers to ensure consistent editing:

```markdown
<!-- Agent-learned guidelines will be added below this line -->
<!-- ---LEARNING_MARKER--- -->
```

```python
# Agent-learned functions will be added below this line
# ---LEARNING_MARKER---
```

The agent edits by replacing the marker with new content plus the marker.

## Cross-Session Persistence

### How Learnings Survive Sessions

1. Agent edits files in `knowledge/learned/`
2. Files are committed to git (version controlled)
3. New agent instance loads files at startup
4. Learned functions are `exec()`ed into namespace
5. Agent reads guidelines at query start

### Loading Learned Functions

```python
def _load_learned_functions(self) -> dict:
    """Load learned functions from the knowledge directory."""
    namespace = {"pd": pd}
    functions_path = self.project_root / "knowledge" / "learned" / "functions.py"

    if functions_path.exists():
        code = functions_path.read_text()
        exec(code, namespace)

    return namespace
```

**Design Decision**: Use `exec()` because:
- Functions can use pandas operations
- Dynamic loading without imports
- Functions immediately available in code execution namespace

## Tracking Learning

The `ExecutionTrace` tracks learning activity:

```python
# In tool execution loop
if tool_name in ("edit_file", "write_file"):
    path = tool_input.get("path", "")
    if "knowledge/learned" in path:
        trace.learning_triggered = True
        if "functions.py" in path:
            trace.learning_type = "function"
        elif "guidelines.md" in path:
            trace.learning_type = "guideline"
```

This enables metrics like:
- `learning_rate`: How often does learning occur?
- `learning_type`: Guidelines vs functions vs both

## Example Learning Cycle

### Query 1: "What was revenue for Product Z in 2024?"

1. Agent filters for Product Z
2. Result is empty (Product Z doesn't exist)
3. Verification catches `EMPTY_RESULT` error
4. Agent checks valid products: A, B, C, D
5. Agent informs user and **persists guideline**:

```markdown
### VALIDATION_ERROR: Non-existent Product Query
**Error**: User asked about "Product Z" which doesn't exist
**Cause**: Dataset only contains Products A, B, C, and D
**Fix**: Always validate product existence before calculations
```

### Query 2 (new session): "What was revenue for Product X?"

1. Agent reads guidelines at start
2. Sees validation guideline
3. Checks valid products first
4. Immediately informs user: "Product X doesn't exist"
5. **No error occurs** - learning prevented the mistake

## Design Decisions Summary

| Decision | Rationale |
|----------|-----------|
| Error-driven only | Clear signal, avoids noise |
| Two artifact types | Guidelines for concepts, functions for code |
| Marker-based editing | Consistent file modification |
| Reload after edit | Immediate availability |
| Track in metrics | Validate learning effectiveness |
| Git version control | History, rollback, review |

## Future Enhancements

1. **Batch learning**: Periodically analyze accumulated examples for deeper patterns
2. **Learning review**: Human approval before persisting
3. **Learning decay**: Remove unused learnings over time
4. **Confidence scores**: Weight learnings by validation frequency
5. **Cross-query learning**: Identify patterns across multiple errors
