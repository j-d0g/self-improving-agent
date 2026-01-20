# Metrics and Tracking

This document describes the metrics system used to measure agent performance and track improvement over time.

## Design Goals

1. **Measure effectiveness**: Track success rate, error rate, recovery rate
2. **Enable optimization**: Identify bottlenecks and improvement opportunities
3. **Validate learning**: Confirm that learnings reduce error rates
4. **Observe programmatically**: All metrics computed from execution traces, not LLM self-assessment

## Execution Trace

Every query creates an `ExecutionTrace` that captures the full execution history:

```python
@dataclass
class ExecutionTrace:
    query: str                    # Original user question
    timestamp: str                # ISO timestamp

    # Execution tracking
    code_attempts: list[dict]     # Each attempt: {code, result, is_error, error_type}
    total_attempts: int           # Number of code executions
    successful: bool              # Did we get a valid result?

    # Error tracking
    errors_encountered: list[dict]  # Each error: {type, category, message, recovery_hint}
    error_recovered: bool           # Did we recover from errors?
    programmatic_errors: int        # Errors caught by verification (not string matching)

    # Learning tracking
    learning_triggered: bool      # Did agent persist learnings?
    learning_type: str            # "guideline", "function", or "both"

    # Resource tracking
    total_tool_calls: int         # Total tool invocations
```

### Design Decision: Trace-Based Metrics

**Why traces, not LLM self-reporting?**

- **Objectivity**: Programmatic observation can't hallucinate
- **Consistency**: Same criteria applied to every query
- **Auditability**: Full history available for debugging
- **Research-backed**: Per agent observability best practices

## Aggregated Metrics

The `AgentMetrics` class aggregates traces into summary statistics:

```python
def compute(self) -> dict:
    return {
        # Success metrics
        "total_queries": total,
        "successful_queries": successful,
        "success_rate": successful / total * 100,

        # Error metrics
        "queries_with_errors": with_errors,
        "error_rate": with_errors / total * 100,

        # Recovery metrics
        "errors_recovered": recovered,
        "recovery_rate": recovered / with_errors * 100,

        # Learning metrics
        "learnings_created": learned,
        "learning_rate": learned / total * 100,

        # Efficiency metrics
        "avg_attempts_per_query": total_attempts / total,
        "avg_tool_calls_per_query": total_tool_calls / total,

        # First-try success
        "first_try_success": first_try_count,
        "first_try_success_rate": first_try_count / total * 100,

        # Verification metrics
        "programmatic_errors_caught": programmatic_errors,
        "error_categories": category_breakdown
    }
```

## Metric Definitions

### Success Rate

```
success_rate = successful_queries / total_queries * 100
```

**What it measures**: Percentage of queries that produced a valid result.

**Target**: >90% after initial learning period.

**Design Decision**: A query is "successful" if it completes without errors OR recovers from errors. This rewards resilience.

### Error Rate

```
error_rate = queries_with_errors / total_queries * 100
```

**What it measures**: Percentage of queries that encountered at least one error.

**Target**: Decreasing over time as learnings accumulate.

**Note**: High error rate is acceptable if recovery rate is also high.

### Recovery Rate

```
recovery_rate = errors_recovered / queries_with_errors * 100
```

**What it measures**: When errors occur, how often does the agent recover?

**Target**: >80%

**Design Decision**: This is the key metric for self-correction capability. It answers: "Can the agent fix its mistakes?"

### Learning Rate

```
learning_rate = learnings_created / total_queries * 100
```

**What it measures**: How often does the agent persist new learnings?

**Target**: Decreasing over time (fewer novel errors to learn from).

**Note**: High learning rate early is good; high learning rate later suggests repeated errors.

### First-Try Success Rate

```
first_try_success_rate = (successful AND no_errors) / total_queries * 100
```

**What it measures**: Queries that succeeded without any errors.

**Target**: Increasing over time as learnings are applied.

**Design Decision**: This metric validates that learnings actually prevent errors, not just recover from them.

### Average Attempts Per Query

```
avg_attempts = total_code_attempts / total_queries
```

**What it measures**: How many code executions per query on average.

**Target**: Close to 1.0 (single attempt success).

**Note**: Higher values indicate more error-recovery cycles.

### Programmatic Errors Caught

```
programmatic_errors_caught = sum(trace.programmatic_errors for all traces)
```

**What it measures**: Errors detected by verification pipeline (not string matching).

**Why track this?**: Validates that verification is working. If all errors are caught by string matching, verification isn't adding value.

### Error Categories Breakdown

```python
error_categories = {
    "code_generation": 5,
    "data_access": 12,
    "type_mismatch": 3,
    "logic_error": 2
}
```

**What it measures**: Distribution of error types.

**Why track this?**: Identifies systematic issues. If most errors are `data_access`, the agent may need better schema understanding.

## Tracking Over Time

### Session Metrics

Each session (CLI run) accumulates metrics:

```
$ python agent.py
> What was Q1 2024 revenue?
> What was Q2 2024 revenue?
> metrics

METRICS:
  total_queries: 2
  success_rate: 100.0
  first_try_success_rate: 50.0
  ...
```

### Persistent Metrics

Save metrics to JSON for cross-session analysis:

```python
agent.metrics.save("metrics.json")
```

Output:
```json
{
  "computed_at": "2024-01-20T10:30:00",
  "summary": {
    "total_queries": 50,
    "success_rate": 94.0,
    "error_rate": 20.0,
    "recovery_rate": 85.0,
    "first_try_success_rate": 80.0
  },
  "traces": [...]
}
```

## Improvement Indicators

### Learning Effectiveness

Compare metrics before and after learnings:

| Metric | Before Learning | After Learning | Improvement |
|--------|----------------|----------------|-------------|
| First-try success | 60% | 85% | +25% |
| Avg attempts | 1.8 | 1.2 | -0.6 |
| Error rate | 40% | 15% | -25% |

### Error Pattern Evolution

Track error categories over time:

```
Session 1: data_access=8, code_generation=4, logic_error=2
Session 2: data_access=3, code_generation=1, logic_error=1
Session 3: data_access=1, code_generation=0, logic_error=2
```

This shows learnings reducing `data_access` errors (likely column name issues).

## Design Decisions Summary

| Decision | Rationale |
|----------|-----------|
| Trace every query | Complete history for debugging and analysis |
| Programmatic observation | Objective, consistent, can't hallucinate |
| Distinguish recovery vs first-try | Validates prevention, not just recovery |
| Track error categories | Identifies systematic issues |
| Persist to JSON | Enables cross-session analysis |
| Include tool call counts | Measures efficiency, not just correctness |

## Future Enhancements

1. **Cost tracking**: Token usage per query
2. **Latency tracking**: Time per query and per tool call
3. **Dashboard**: Visual metrics over time
4. **Alerts**: Notify on metric degradation
5. **A/B testing**: Compare different prompts or configurations
