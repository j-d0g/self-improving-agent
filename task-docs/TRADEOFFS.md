# Implementation Trade-Offs

> This document captures the key design decisions and trade-offs made during implementation, with rationale for each choice.

**Navigation:** [TASK](TASK.md) | [NOTES](NOTES.md) | [DESIGN](DESIGN.md) | [TRADEOFFS](TRADEOFFS.md) | [BLOG](BLOG.md)

**Previous:** [DESIGN.md](DESIGN.md) — Detailed system design
**Next:** [BLOG.md](BLOG.md) — Write-up outline for retrospective

---

## Key Concept: "N+1" Improvement

Throughout this document, **"N+1"** refers to the core requirement: **Session N+1 should be measurably better than Session N**. This means:

- After query N, the system learns something
- Query N+1 benefits from that learning
- The improvement is persistent (survives restarts)
- The improvement is measurable (tokens, tool calls, or correctness)

This requirement shaped many trade-offs — favoring immediate, per-query updates over batched learning that would show improvement at N+50 but not N+1.

---

## Trade-Off Summary

| Decision | Chose | Over | Why |
|----------|-------|------|-----|
| Learner model | Haiku 4.5 | Opus 4.5 | Force errors to demo improvement; faster/cheaper iteration |
| Agent architecture | Learner + Improver | Orchestrator + multiple specialists | Simpler; task wasn't complex enough to need separation |
| Update frequency | Per-query | Batched (10-50) | N+1 requirement; demo visibility |
| Success metric | Efficiency (tokens, tool calls) | Correctness | Haiku aced correctness; needed a differentiating signal |
| Learner responsibilities | Answer + Reflect | Answer only | Self-reflection catches nuances, but creates cognitive overload |

---

I had to make a few design decisions sacrificing performance or best-practices for the sake of something complete and demonstrable within the time constraints.

---

## Haiku 4.5 Learner, Opus 4.5 Improver

Using 4.5 Haiku instead of Opus because both models were already acing most questions I gave to it. In order to have something to demo, we had to find test-cases where the model struggled. The data analysis task is not nearly as complex as Cody, and modern LLMs are pretty good at tool-calling and querying with code (pandas). I even had to remove any 'data analyst' system prompt, and any schemas in the file structure to make this harder and force it to solve inefficiently from first principles to get something to work with.

It was also much faster and cheaper to spawn haiku sub-agents across more queries and return feedback during prototyping, as well as passing full inference feedback loops with the SDK.

Since the task prioritised learning over performance, a few decisions were made to drop performance for the sake of showing measurable improvement. We save Opus 4.5 for the evaluator and improver agents to maximise measurable improvement from reasoning against logs.

Additionally, using a weaker learning model to answer queries meant that we could lower the baseline level of difficulty of queries we tested against, and could benchmark it against the gold-standard responses assumed to be completed by Opus 4.5 on **ultrathink** (to save me time having to solve the solutions by hand).

---

## Learner → Improver: Removed Evaluator and Orchestrator

Initially intended for separation of concerns between the querier agent, the evaluator, and the one applying code changes. These were all sub-agents being managed by an orchestrator.

However, a few things emerged which led me to remove the separate evaluator step by merging it into the improver, have a self-review step in the learner, and collapse the orchestrator altogether:

- **Feedback Quality** — Self-review feedback occasionally caught more nuanced improvements than a separate evaluator, especially in identifying friction points during its own journey and reasoning against why it made certain decisions, while an external judge provided better holistic and objective feedback: there was merit in keeping both and merging the best of both world.
- **Latency** — In order to iterate fast, a manageable feedback loop was required.
    - The orchestrator added too much time between calls for a workflow that was otherwise straight-forward for the task. We didn't need the extra complexity.
    - I also made the improvements asynchronous (background agent), because I was left waiting 50s+ before being able to make another query in an interactive shell. These are threaded with run_ids so the improver knows which logs and reflections to view.
    - I removed the evaluator node to reduce the number of chained calls and contexts that needed writing to files and passing forward, also shortening the feedback loop so I could observe improvements faster.
- **Capability** — The improver was using Opus 4.5, so it could handle a complex prompt involving multiple steps: evaluating logs, reviewing reflections, and combining feedback into interpreting improvements. While this is a lot for a single agent to do, for the sake of time constraints and the simplicity of the task at hand, it was a trade-off I was willing to accept.

In the end, I traded off clear separation of concerns that would have thrived in a production environment requiring more complex workflows and decision-making and with better improvement system that relies on batching, for something I could demo in an N+1 improvement system developed locally.

**Deterministic workflow insight:** This was a simple task requiring a deterministic workflow: query → reflect → improve → repeat. No non-deterministic flows needed managing, so an orchestrator was overkill. However, removing the orchestrator also removed enforcement mechanisms — nothing ensures reflection logs actually get written. The "mandatory" reflection step became voluntary in practice.

---

## Background Improver: Separate Client vs SDK Subagent

| Approach | Behavior |
|----------|----------|
| **Chosen:** Separate `ClaudeSDKClient` + `asyncio.create_task` | True parallel execution. User continues chatting while improver works. |
| **Alternative:** SDK Subagent (via `Task` tool) | Would block learner's turn or require explicit background spawn. Adds hooks but no benefit here. |

The SDK's subagent system (`SubagentStart`/`SubagentStop` hooks, shared session context) is designed for orchestrated workflows where a parent agent spawns children. Our use case is simpler: fire-and-forget background processing. A separate client gives real concurrency without the complexity of subagent management.

This also enables streaming output from the improver while the user is typing their next query — something that wouldn't work cleanly with SDK subagents blocking the main agent loop.

---

## Multi-Turn Conversation: Persistent Client vs Per-Query Client

| Mode | Behavior |
|------|----------|
| **Interactive** (multi-turn) | Single `ClaudeSDKClient` kept open across queries. Conversation history preserved — agent remembers previous Q&A. |
| **Single query** (`python agent.py "question"`) | Temporary client per query. No history needed for one-shot usage. |

Multi-turn enables natural follow-up questions ("What about last year?" after asking about 2024 revenue) without re-explaining context. The SDK client maintains conversation state internally.

Implementation uses `start_session()` / `end_session()` to manage the persistent client lifecycle, with `_query_async()` detecting which mode to use based on whether a client is already open.

---

## Improvement System

The current improvement system attempts to modify the repository after every example. Of course, this could lead to noisy examples being persisted.

Originally I wanted a system that propagated changes after a batch of 10-50 examples in order to identify underlying patterns and act on more averaged feedback, akin to gradient descent.

However, this would be harder to demo for the size of the project, and also not satisfy the N+1 improvement requirement, so I deprioritised. I did think about doing both frequent and cyclical changes, but ultimately I did not have time.

### Sequential Processing: The Architectural Bottleneck

The current system is fundamentally sequential:

```
Query 1 → Wait for Improver → Query 2 → Wait for Improver → Query 3 → ...
```

Each query blocks on its improver completing before the next query can run. This is because the N+1 requirement demands that Query N+1 benefits from the learning triggered by Query N. The improver must finish writing to `knowledge/` before the next learner session reads it.

This creates a **hard serialization constraint** that dominates benchmark runtime:

| Component | Time | Parallelizable? |
|-----------|------|-----------------|
| Learner query | ~30-60s | No (depends on previous improvement) |
| Wait for improver | ~30-60s | No (must complete before next query) |
| Validation queries | ~4-8min | Yes (no learning dependency) |
| Judge calls | ~1-2s each | Yes (independent) |

For a 27-query benchmark (3 epochs), the sequential train loop alone takes ~30-50 minutes, while validation (now parallelized) adds only ~5 minutes per epoch.

### Batched Improvements: The SGD Analogy

A more efficient architecture would batch improvements, analogous to mini-batch stochastic gradient descent:

```
Current (SGD with batch_size=1):
  Query 1 → Improve → Query 2 → Improve → ... → Query N → Improve

Proposed (mini-batch SGD):
  [Query 1, Query 2, ..., Query K] → Aggregate → Single Improvement
```

**How it would work:**

1. **Run K queries in parallel** (no improver, just collect session traces)
2. **Aggregate feedback** — Improver analyzes all K traces together
3. **Single knowledge update** — One atomic change to `knowledge/` based on patterns across K examples
4. **Repeat** until epoch complete

**Benefits:**

| Benefit | Why |
|---------|-----|
| **Efficiency** | K queries run in parallel; improver runs once per batch instead of K times |
| **Noise reduction** | Single-query flukes get averaged out; only patterns appearing across multiple examples trigger updates |
| **Reliability** | Fewer, more confident updates; less churn in knowledge files |
| **Better signal** | Improver sees patterns ("3 queries failed on FX calculations") instead of isolated incidents |

**Example with K=10:**

- Current: 10 queries × (30s query + 45s improve) = **12.5 minutes**
- Batched: 10 parallel queries (60s) + 1 aggregate improve (90s) = **2.5 minutes** (5x faster)

The improver prompt would change from "analyze this one session trace" to "analyze these 10 session traces, identify common patterns, and make a single consolidated update."

### Why We Didn't Do This

The N+1 demo requirement made batching impractical:

1. **Harder to visualize** — "Query 11 is better than Query 1" is less compelling than "Query 2 is better than Query 1"
2. **Delayed feedback** — First K queries show no improvement; learning only visible after first batch completes
3. **Batch size tuning** — Too small = noise; too large = slow feedback; needs experimentation

For a production system with hundreds of queries, batched improvements would be strictly better. The per-query approach was a demo optimization, not an architectural ideal.

### Hybrid Approach (Future Work)

The best of both worlds:

1. **Immediate updates** for critical errors (exceptions, completely wrong answers)
2. **Batched consolidation** every K queries for pattern recognition
3. **Epoch-level distillation** to prune noisy learnings and reinforce patterns

This mirrors how neural network training combines per-step gradient updates with periodic learning rate adjustments and checkpoint consolidation.

---

## Evaluations, Validations and Verifications

In order for this system to show measurable improvement, everything relied on defining metrics for success, and tests that could show tangible results.

This was difficult.

- How do we know if an answer is correct?
- If Haiku is getting all the answers correct, how do we measure progress?

Even with extremely nested questions requiring lots of complex queries and aggregating results, Haiku was still able to complete them and never made code errors.

Instead, I spent time spawning sub-agents across a broad range of queries that were ambiguous, complex, and unpredictable - and observed that the most challenging queries led to multiple back-tracks, empty tool-calls and internal reasoning, and this could be proxied by # tokens and # tool calls.

The new focus was now measuring efficiency of reasoning, tool-calling, and sub-task processes.

I thought about getting more into the weeds with hook validators, however all derivatives of metrics were too specific and not general enough to be a true signal of efficiency. Also, adding more verification hooks during tool calls would help the agent get to a better answer during the Nth run. I needed to record errors in the Nth run to improve and measure the N+1'th run, so this would have worked against me.

I took the 9 queries that led to the highest number of tool calls / tokens consumed, and then fed it to Claude Code Opus 4.5 with access to the full schema and pre-computed mappings of complex query formulae etc. and asked it to solve in order to get the gold-standard source of truth outputs. This would be our test-set to measure how much improvements were made to efficiency as we allowed traffic to fill out documentation.

Note, we intentionally leave all the docs blank to begin, as even the slightest direction and schematics saturated performance and efficiency to a point where progress was hard to measure (this data analysis task was too simple!!!) I even considered pre-populating it with intentionally misleading notes to showcase how much the system improved with N examples.

Now, with the system complete, you would run `python evals/benchmark.py run --no-improve` to get an initial baseline accuracy, then run `python evals/benchmark.py run` to essentially 'train' the knowledge base while benchmarking against the validation set, observing accuracy and efficiency metrics on the dashboard.

---

## Hindsight & Lessons Learned

Looking back on the project, several insights emerged that weren't obvious during development:

### Per-Query Noise

Per-query updates introduced noise. Some overly specific rules slipped through — learnings that applied to one edge case but didn't generalize. Batching would have filtered these by surfacing patterns across multiple examples. The N+1 requirement forced this trade-off, but a production system would benefit from both: immediate updates for critical fixes, batched consolidation for pattern recognition.

### Missing Metrics

I wish I had tracked **time/latency** and **backtrack count** from the start. Tokens and tool calls were useful proxies, but explicit backtracking detection (when the agent revised its approach mid-stream) would have been a cleaner signal for "the agent struggled here." Latency data would have helped quantify the user experience impact of different architectures.

### Freeform vs Structure

Keeping knowledge files freeform (markdown prose) rather than structured (JSON, YAML) was the right call. It gave the Improver flexibility to express nuanced guidance that wouldn't fit cleanly into predefined schemas. The agent could write "when you see X, consider Y" rather than forcing everything into rigid key-value patterns.

### Experiment Tracking

Tracking was ad-hoc — notes in markdown files, manual observation of patterns. This was enough to identify that `functions.py` was underutilized (the Improver rarely added reusable code there, preferring to update examples). A more structured experiment log would have made these patterns visible earlier.

### Agent Preferences

I never formally tested whether the agent preferred CSV or would perform better with SQLite. The pragmatic choice was CSV because it was simpler and the task didn't require joins or complex queries. But an A/B comparison might have revealed unexpected preferences in how models interact with data.

### Eval Generation

The 50 Opus sub-agents approach for finding struggle patterns was effective but expensive. In hindsight, a smaller targeted run with specific difficulty criteria might have found the same queries faster. The brute-force approach worked, but wasn't optimal.

### Undoing Best Practices

The most counter-intuitive lesson: sometimes you have to remove helpful features to create room for improvement. Validators, hooks, detailed schemas — these would all help a production agent succeed. But for a learning demonstration, they saturated performance before learning could show value. The goal shaped what "good engineering" meant.

---

## V1 Observed Limitations

Running V1 on real queries revealed cracks in the foundation. The minimal architecture that felt elegant in design showed its limitations under pressure.

**Detailed analysis:**
- [v1-observations.md](v1-observations.md) — Incident log and systemic issues
- [BLOG.md §3](BLOG.md#3-v1-in-practice-what-we-actually-observed) — Narrative walkthrough

**Key findings:**
- **Learner cognitive overload** — 5+ responsibilities per query; reflection logs dropped under load
- **Improver trusts self-assessment** — No independent verification; minimized errors accepted at face value
- **Error categorization gaps** — Reasoning errors fell through the cracks; `<errors>` interpreted as "code exceptions only"
- **Conservative learning threshold** — "Query-specific" became an escape hatch; real errors dismissed as one-off
- **SKIP criteria too broad** — Improver conflated query uniqueness with error uniqueness

---

## Features That Didn't Make the Cut

| Feature | What It Would Solve | Why Cut | What We Live With |
|---------|---------------------|---------|-------------------|
| **Orchestrator** | Coordinate multi-agent workflows, enforce mandatory steps | Workflow was deterministic — no non-deterministic flows needing management | Simple linear pipeline; no enforcement of mandatory steps (reflection logs get dropped) |
| **Separate Evaluator** | Independent judgment of errors, unbiased assessment | Merged into Improver for latency | Improver trusts Learner's self-assessment (see [v1-observations.md §4](v1-observations.md)) |
| **Hooks/Validators** | Guide agent during tool-calls, catch errors early | Would help performance but hurt learning demo | Agent struggles → creates learning signal; recurring issues (shell escaping) go unaddressed |
| **Full API Interface** | Type-safe deterministic queries, reduced LLM load | System too good even with zero prompting | Freeform pandas code generation; more tokens burned on code synthesis |
| **Batched Updates** | Filter noise, surface patterns across examples | N+1 requirement demanded per-query updates | Per-query noise; overly specific rules slip through |
| **Vector Store/Retrieval** | Scale to 1000s of learnings | 8-hour MVP; not enough data points yet | "Read everything" — works for small domain, won't scale |
| **Regression Testing** | Catch bad improvements automatically | Time constraints | Manual review of git diffs; risky improvements can land |
| **Semantic Cache** | Skip LLM calls for similar queries; reduce latency and cost | Time constraints; not enough repeat traffic to justify | Every query hits the LLM; duplicate work on semantically identical questions |

**Wild ideas considered (but never built):**
- **Adversarial examples** — Intentionally wrong knowledge to test recovery and unlearning
- **Self-modifying prompts** — Agent editing its own system instructions based on learnings

---

## Time Allocation

Honest breakdown of where time went:

| Phase | Allocation | Notes |
|-------|------------|-------|
| **Research** | ~30% | SDK docs, YouTube videos, Agent SDK patterns. First time with the SDK was significant overhead. |
| **MVP** | ~40% | First working version. Multiple iterations as architecture collapsed from 3-agent to 2-agent. |
| **Evaluations** | ~20% | Finding queries that challenged the model. 50 Opus sub-agents to probe for weaknesses. |
| **Polish & Docs** | ~10% | README, tracing, benchmarking dashboard. |

**Post-deadline iteration:** Refinement continued in personal time after submission. V1 observations and V2 roadmap emerged from this extended analysis.

**SDK learning curve:** Building with the Claude Agent SDK for the first time added overhead. Patterns like background subagents, session traces, and hook-based validators weren't obvious upfront.

---

## V2 Roadmap

Connecting observed limitations to planned fixes (bridges to presentation's V2 section):

| V1 Limitation | V2 Solution |
|---------------|-------------|
| Learner overloaded with reflection | Separate **Reflector/Evaluator** agent takes session trace as input |
| Improver trusts Learner | **Independent verification** of session trace; don't accept self-assessment at face value |
| "Read everything" doesn't scale | **Sub-agents for selective retrieval**; each reviews a knowledge file and bubbles up relevant context |
| Conservative learning threshold | Separate "error uniqueness" from "query uniqueness"; errors can generalize even if queries don't |
| No enforcement of mandatory steps | **Orchestrator with fallbacks**; if reflection missing, Evaluator generates from session trace |
| Per-query noise | **Batch consolidation layer**; immediate updates for critical fixes, periodic distillation for patterns |

**Grounding:** Stanford's ACE paper (Automatic Cognition Enhancement) + Agemo's approach to in-context learning. The V2 system applies ACE principles: localization (fine-grained retrieval), incremental adaptation (the four operations: find/add/edit/remove), and separated concerns across specialized agents.

---

## V2 Architecture: The Evaluation Problem

### V1's Fundamental Evaluation Problem

V1 uses an LLM judge comparing free-form text outputs. This is fundamentally flawed:

| Problem | Example |
|---------|---------|
| **No exact matching** | Is "$1.2M" the same as "$1,200,000"? LLM has to guess. |
| **Answer mixed with reasoning** | Output: "Based on my analysis, the revenue was $1.2M" — what's the actual answer? |
| **Ambiguous queries** | "What was revenue?" — which product? which period? gross or net? |
| **Subjective ground truth** | If the query is ambiguous, multiple answers could be "correct" |
| **No typed validation** | Can't use hooks to verify output schema — it's just prose |

The core issue: **we're comparing fuzzy interpretations of ambiguous questions**. Even a perfect judge can't give consistent scores when the inputs are ill-defined.

### V2 Solution: Query Compiler Pipeline

The solution is to treat query answering like a **compiler pipeline** — normalize the input before processing:

```
User Query (messy, ambiguous)
    ↓
┌─────────────────────────────────────────────────────────┐
│  SOLVER AGENT (3 phases)                                │
│                                                         │
│  [1. Disambiguator] ←→ User (clarifying questions)      │
│          ↓                                              │
│      Canonical Query (clean, unambiguous)               │
│          ↓                                              │
│  [2. Planner]                                           │
│          ↓                                              │
│      Execution Plan + Expected Type                     │
│          ↓                                              │
│  [3. Executor]                                          │
│          ↓                                              │
│      Typed Result (number | boolean | category | list)  │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  EVALUATOR AGENT                                        │
│                                                         │
│  Exact type-checked comparison against ground truth     │
│  No LLM judgment needed — just value equality           │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│  IMPROVER AGENT                                         │
│                                                         │
│  Receives structured feedback (not fuzzy assessments)   │
│  Updates knowledge based on concrete errors             │
└─────────────────────────────────────────────────────────┘
```

### Phase 1: Query Disambiguator

**Input:** Raw user query ("What was revenue last quarter?")

**Process:**
- Identifies ambiguities (which product? which metric? what timeframe?)
- Asks clarifying questions back to user (Agemo-style)
- User provides answers
- Outputs canonical query

**Output:** Unambiguous canonical query

```
User: "What was revenue last quarter?"
Disambiguator: "Which product? (A, B, C, D, or all)"
User: "Product A"
Disambiguator: "Gross Revenue or Net Revenue?"
User: "Gross"
Disambiguator: "Last quarter relative to today (Q4 2024) or a specific quarter?"
User: "Q4 2024"

Canonical Query: "Gross Revenue for Product A in Q4 2024, all countries, sum"
```

This is the **key insight**: once the query is canonical, the ground truth answer is deterministic. The "gold standard" is defined by the canonical query, not the original messy one.

### Phase 2: Logical Planner

**Input:** Canonical query

**Process:**
- Breaks down into logical steps
- Identifies required data filters
- Determines expected output type
- Produces verification criteria

**Output:** Execution plan + expected type

```yaml
canonical_query: "Gross Revenue for Product A in Q4 2024, all countries, sum"
steps:
  - filter: { product: "A", year: 2024, quarter: 4 }
  - filter: { L1: "Revenue", L2: "Gross Revenue" }
  - aggregate: sum
  - column: "Value"
expected_type: number
expected_unit: "$"
verification: "single numeric value, positive"
```

### Phase 3: Tool Executor

**Input:** Execution plan

**Process:**
- Translates plan to pandas/SQL
- Executes against dataset
- Formats output according to expected type

**Output:** Typed result

```python
@dataclass
class TypedResult:
    type: Literal["number", "boolean", "category", "list", "not_available"]
    value: float | bool | str | list[str] | None
    unit: str | None  # "$", "%", "count"
```

```python
TypedResult(type="number", value=4523891.23, unit="$")
```

### Evaluator: Exact Matching

With typed outputs, evaluation becomes trivial:

```python
def evaluate(expected: TypedResult, actual: TypedResult) -> bool:
    if expected.type != actual.type:
        return False

    if expected.type == "number":
        return abs(expected.value - actual.value) < 0.01  # tolerance

    if expected.type == "boolean":
        return expected.value == actual.value

    if expected.type == "category":
        return expected.value.lower() == actual.value.lower()

    if expected.type == "list":
        return set(expected.value) == set(actual.value)

    return expected.value == actual.value
```

**No LLM judge needed.** Just type-checked equality.

### Why This Works

| V1 Problem | V2 Solution |
|------------|-------------|
| Fuzzy LLM judge | Exact type-checked comparison |
| "Is $1.2M = $1,200,000?" | Both are `TypedResult(type="number", value=1200000.0)` |
| Answer mixed with reasoning | Executor outputs *only* the typed value |
| Ambiguous queries | Disambiguator canonicalizes first |
| No ground truth for ambiguous Qs | Canonical query *defines* the ground truth |
| Can't validate with hooks | Typed outputs enable schema validation hooks |

### Evaluation Dataset Format (V2)

V1 format (fuzzy):
```json
{"query": "What was revenue?", "answer": "Revenue was $1.2M"}
```

V2 format (typed):
```json
{
  "raw_query": "What was revenue?",
  "clarifications": [
    {"question": "Which product?", "answer": "A"},
    {"question": "Which period?", "answer": "Q1 2024"},
    {"question": "Gross or Net?", "answer": "Gross"}
  ],
  "canonical_query": "Gross Revenue for Product A in Q1 2024, all countries, sum",
  "expected": {
    "type": "number",
    "value": 1200000.0,
    "unit": "$"
  }
}
```

The clarifications can be pre-filled for benchmark datasets, or collected interactively for real usage.

### V1 Limitations Summary

For comparison against V2, V1's limitations are:

1. **Sequential bottleneck** — can't parallelize training (N+1 constraint)
2. **Per-query noise** — no pattern aggregation, overly specific learnings
3. **Fuzzy evaluation** — LLM judge comparing prose, no exact matching
4. **No query standardization** — ambiguous inputs produce inconsistent outputs
5. **Free-form outputs** — can't separate answer from reasoning
6. **Single-agent solver** — no separation of disambiguation/planning/execution
7. **Improver trusts learner** — no independent verification

**Project name:** `claude_ace`
