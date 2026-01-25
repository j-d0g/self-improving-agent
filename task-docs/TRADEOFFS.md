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

Now, with the system complete, you would run [evaluate.py](http://evaluate.py) against test to get an initial baseline accuracy, then reset and run evaluate train-test to essentially 'train' the context before benchmarking the test accuracy after examples have been populated and observing the accuracy and efficiency metrics.

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
