# Verification System Design

This document describes the programmatic verification pipeline used for error detection and agent self-correction.

## Design Philosophy

### Gather-Act-Verify Pattern

The verification system implements the **gather-act-verify** pattern recommended by the Claude Agent SDK:

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent Loop                              │
│                                                             │
│   GATHER          ACT              VERIFY                   │
│   ┌─────┐       ┌─────┐          ┌─────────────────────┐   │
│   │Read │──────▶│Exec │─────────▶│ Programmatic Checks │   │
│   │Files│       │Code │          │                     │   │
│   └─────┘       └─────┘          │ Layer 1: Execution  │   │
│                                  │ Layer 2: Data Shape │   │
│                                  │ Layer 3: Domain     │   │
│                                  │ Layer 4: LLM Judge  │   │
│                                  └──────────┬──────────┘   │
│                                             │              │
│                    ┌────────────────────────┴───────┐      │
│                    │                                │      │
│                    ▼                                ▼      │
│               [PASS]                           [FAIL]      │
│            Return result                  Return feedback  │
│                                          for self-correct  │
└─────────────────────────────────────────────────────────────┘
```

### Why Programmatic First?

Research from "When Can LLMs Actually Correct Their Own Mistakes?" (TACL 2024) shows:

1. **LLM self-correction with only prompted feedback rarely works** - The model often "corrects" correct answers or fails to identify real errors
2. **External/programmatic feedback enables reliable self-correction** - Deterministic signals provide reliable correction triggers
3. **The bottleneck is feedback quality** - Better verification = better self-correction

## Layered Architecture

### Layer 1: Execution Verification

Catches code execution failures immediately.

| Check | Error Type | When Triggered |
|-------|------------|----------------|
| Exception detection | `SYNTAX_ERROR`, `NAME_ERROR`, `TYPE_ERROR`, etc. | Traceback in output |
| Result exists | `NO_RESULT` | `result` variable not set |
| Type check | `WRONG_TYPE` | Result type doesn't match expected |
| Timeout | `TIMEOUT` | Execution exceeded time limit |

**Exception Classification**:

```python
EXCEPTION_MAPPING = {
    "SyntaxError": (ErrorType.SYNTAX_ERROR, ErrorCategory.CODE_GENERATION,
                    "Code has invalid Python syntax"),
    "NameError": (ErrorType.NAME_ERROR, ErrorCategory.CODE_GENERATION,
                  "Variable or function not defined"),
    "TypeError": (ErrorType.TYPE_ERROR, ErrorCategory.TYPE_MISMATCH,
                  "Type mismatch - check data types"),
    "KeyError": (ErrorType.KEY_ERROR, ErrorCategory.DATA_ACCESS,
                 "Column or key not found"),
    ...
}
```

**Design Decision**: Map exceptions to semantic categories because different error types require different correction strategies. A `KeyError` suggests checking column names, while a `SyntaxError` suggests code generation issues.

### Layer 2: Data Shape Verification

Validates DataFrame structure without examining values.

| Check | Error Type | When Triggered |
|-------|------------|----------------|
| Not empty | `EMPTY_RESULT` | DataFrame has 0 rows |
| Row count | `TOO_FEW_ROWS`, `TOO_MANY_ROWS` | Outside expected range |
| Columns exist | `MISSING_COLUMNS` | Required columns not present |
| No nulls | `UNEXPECTED_NULLS` | Critical columns have NaN |
| No duplicates | `DUPLICATE_ROWS` | Unexpected duplicate rows |

**Design Decision**: Check shape before values because:
- Empty results are a common filter error
- Shape issues are fast to detect (O(1))
- Shape errors often indicate filter logic problems

### Layer 3: Domain Verification

Financial domain-specific rules that must hold.

| Check | Error Type | Rule |
|-------|------------|------|
| Revenue positive | `NEGATIVE_WHEN_POSITIVE_EXPECTED` | Revenue >= 0 |
| Cost positive | `NEGATIVE_WHEN_POSITIVE_EXPECTED` | COGS, OPEX >= 0 |
| Margin cap | `MARGIN_EXCEEDS_100` | Gross margin <= 100% |
| Margin hierarchy | `MARGIN_HIERARCHY_VIOLATED` | Gross >= Operating >= Net |
| Quarters sum | `TEMPORAL_INCONSISTENCY` | Q1+Q2+Q3+Q4 = Annual |
| Accounting identity | `FAILED_IDENTITY_CHECK` | Revenue - COGS = Gross Profit |
| Growth rate | `GROWTH_RATE_ANOMALY` | Growth within -99% to +500% |

**Design Decision**: Include financial domain rules because:
- Catches logical errors that pass execution
- Based on accounting standards (GAAP)
- Provides specific recovery hints

### Layer 4: LLM Judge (Optional)

For semantic validation that can't be done programmatically.

**When to use**:
- Validating natural language answers
- Checking reasoning quality
- Complex multi-step verification

**Current status**: Not implemented. Programmatic checks handle most cases.

## Error Categories

High-level categories guide the agent's correction strategy:

| Category | Meaning | Typical Fix |
|----------|---------|-------------|
| `CODE_GENERATION` | Invalid Python code | Fix syntax, imports, variable names |
| `TYPE_MISMATCH` | Wrong data types | Cast types, check operations |
| `VALUE_ERROR` | Wrong values | Check constraints, ranges |
| `DATA_ACCESS` | Column/key not found | Verify schema, column names |
| `LOGIC_ERROR` | Wrong results | Fix calculation logic |
| `TIMEOUT` | Took too long | Simplify query, add limits |

## Recovery Hints

Each error includes a recovery hint to guide self-correction:

```python
VerificationResult.failure(
    ErrorType.KEY_ERROR,
    "Column 'Revnue' not found",
    layer="execution",
    category=ErrorCategory.DATA_ACCESS,
    recovery_hint="Column or key not found - verify column names in schema"
)
```

**Design Decision**: Include recovery hints because:
- Provides actionable guidance
- Reduces trial-and-error iterations
- Leverages domain knowledge about common fixes

## Verification Report

Results are aggregated into a `VerificationReport`:

```python
@dataclass
class VerificationReport:
    results: List[VerificationResult]

    @property
    def passed(self) -> bool:
        """True if no ERROR-severity failures."""

    @property
    def first_error(self) -> Optional[VerificationResult]:
        """Most likely cause of failure."""

    def to_feedback(self) -> str:
        """Generate feedback string for agent."""
```

**Design Decision**: Aggregate results because:
- Multiple checks may fail simultaneously
- First error is usually the root cause
- `to_feedback()` formats for agent consumption

## Integration with Agent

The verification pipeline integrates at the tool execution level:

```python
def _tool_execute_pandas_with_verification(self, code: str):
    report = VerificationReport()

    try:
        exec(code, namespace)
        result = namespace.get("result")

        # Layer 2: Data shape
        if isinstance(result, pd.DataFrame):
            shape_report = self.verifier.verify_dataframe(result)
            report.extend(shape_report)

        # Layer 3: Domain (for numeric results)
        if isinstance(result, float):
            # Check for NaN, range, etc.
            ...

    except Exception as e:
        # Layer 1: Exception classification
        classification = ExceptionClassifier.classify(error_str)
        report.add(classification)

    return result_str, report
```

**Design Decision**: Verify at tool level because:
- All code execution goes through `execute_pandas`
- Verification happens before result reaches agent
- Feedback can be appended to tool result

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| `ERROR` | Must fix | Blocks success, requires correction |
| `WARNING` | Should investigate | May be legitimate edge case |
| `INFO` | Informational | No action required |

**Design Decision**: Distinguish severity because:
- Not all issues are blockers
- Warnings allow investigation without failure
- Matches standard logging conventions

## Future Enhancements

1. **Confidence scoring**: Add uncertainty to verification results
2. **Custom rules**: Allow users to define domain-specific checks
3. **Learning from verification**: Track which checks commonly fail
4. **LLM judge integration**: Add optional semantic validation layer
