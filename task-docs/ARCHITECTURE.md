# System Architecture & Design

> **Note:** This document captures **early design exploration** — ideas considered before implementation. For the **final architecture** that was actually built, see [CLAUDE.md](../CLAUDE.md).

**Navigation:** [TASK](TASK.md) | [NOTES](NOTES.md) | [ARCHITECTURE](ARCHITECTURE.md) | [TRADEOFFS](TRADEOFFS.md) | [BLOG](BLOG.md)

**Previous:** [NOTES.md](NOTES.md) — Ideas that informed this design
**Next:** [TRADEOFFS.md](TRADEOFFS.md) — Implementation decisions and compromises

---

## What Was Actually Built

The final implementation diverged from some early proposals. Key differences:

| Proposed | Actually Built | Why |
|----------|---------------|-----|
| FastAPI, Pydantic, Redis | Simple Python scripts with file-based state | Task was simpler than anticipated; infrastructure overkill |
| Multiple specialist eval agents | Single Improver agent (Opus 4.5) | Merged for simplicity; Opus capable enough to handle combined tasks |
| Complex validation metrics | Tokens + tool calls only | Haiku aced correctness; efficiency became the measurable signal |
| `.claude/agents/` structure | `agent/` with Agent SDK | Using Python SDK, not Claude Code CLI agents |

**See:** [CLAUDE.md](../CLAUDE.md) for the architecture diagram and actual file structure.

---

## Early Design Exploration

> The sections below capture brainstorming and proposals from the design phase. Some were adopted, others deprioritized. See [TRADEOFFS.md](TRADEOFFS.md) for rationale.

---

## Architecture & Features *(Proposed — not implemented)*

- Sandbox environment
- FastAPI, Pydantic, Redis for state management

*Outcome: Deprioritized — simple file-based approach sufficient for demo scope.*

---

## Next Steps *(Historical — completed)*

### ADK

- [x]  Set-Up minimal Agent SDK with Dataset.
- [x]  See how it works out the box as an MVP.
- [x]  Get a rough idea of how it's working.

### Claude Code Simulations

- [x]  See Ideas above. Implement, iterate, and progress.

*Outcome: Completed — see `agent/agent.py` for implementation.*

---

## Types of Eval Agents *(Proposed — partially adopted)*

> We don't need agents that compare the right answer - this should be a deterministic check. We need agents that evaluate thinking steps, efficiency, and where things could be added to improve that.

*Outcome: Merged into single Improver agent. Reflective self-review kept in Learner. See [TRADEOFFS.md](TRADEOFFS.md#learner--improver-removed-evaluator-and-orchestrator).*

| Type | Pros | Limitations |
| --- | --- | --- |
| Reflective: agent reflects its own steps.  | Reviewing detailed steps, efficiencies and qualitative feedback on what was useful and not useful achieving the goal, and what could have been useful to add to help in future. | Bias. Answers focus on its process based on available resources. Context is bloated so may miss something a specialist agent could catch with a more hollistic view. |
| Docs Gaps & Direction Agent | Determines if changes could be made to improve in the docs to make a process more seamless, i.e new notes, rules, sign-posts. |  |
| Functions Coding Agent | Determines if new functions could be added to make a process more seamless / reduce operations. |  |
| Query Interpreter Agent | Determines if patterns, rules or new kinds of confusing queries could be added to help the agent clarify and translate requests into structured query. |  |
| Refactor Agent | Asked to scan the repository - if lists of rules, patterns, examples or functions begin to grow unreasonably, this agent extracts common patterns and compacts and distributes learnings. | While removing examples risks temporarily compressing the immediate performance gains on past mistakes, it allows for more efficient long-term memory consolidation of ideas for gradual but permanent improvement. |
| Overall Agent | Less LLM calls: simply analyse entire thought chain and give holistic feedback. More generic, less prone to noise. Replaces need for multiple specialist agents, so less complex. | Might miss nuanced efficiency gains in tool-calling. |

- Reflective: agent reflects its own steps. Good for detailed review.

---

## Types of Validation Metrics *(Proposed — simplified)*

*Outcome: Focused on Tier 2 (efficiency) since Tier 1 correctness was saturated. See [TRADEOFFS.md](TRADEOFFS.md#evaluations-validations-and-verifications).*

### Tier 1 (Primary)

- #: Total Correct Answers of System.
- Bool: Correct Answer Reached

### Tier 2 (Efficiency)

- #: Tokens
- #: Total Tool Calls.

### Tier 3 (Detailed)

- #: Code Execution Errors.
- #: Code Execution Count
- #: Docs Read to Reach Answer
    - (Should prompt agent stop reading docs when confident you can run the required query in the most efficient and effective way - i.e knowledge acquired or simple query)

### Bool Validators

- Bool: Before writing code.
    - Read docs
    - Read schema
    - Read
- Bool: Read function templates before writing code.
    - For easy questions, trades-off latency for robustness for complex queries.
- Bool: Read schema before reading csv.
- Bool: Validate entry exists before filtering.

---

## Repository Structure *(Proposed — evolved)*

```
- .claude
    - agents
        - data analyst.md
        - evaluator.md
        - improver.md
    - skills
        - review/SKILL.md
        - improve/SKILL.md
- knowledge
    - learnings.md
    - examples.md
- readme.md
- schema.md
- agent.py # or whatever it's meant to be called
```

*Outcome: Actual structure uses `agent/` directory with Python SDK, not `.claude/agents/`. See [CLAUDE.md](../CLAUDE.md#key-files) for final structure.*

---

## Evaluation Approach *(Proposed — implemented with modifications)*

I also want an evaluation suite of 10 moderate to difficult test-cases as per this tier list:

…

I want to bench these 10 examples via an iteratively improving system that rewards:

- total correct #1
- total tokens #3
- total tool calls #4

We initially bench a model with no context but the 10 queries to observe the above metrics. My guess is that 4.5 haiku even does quite well on this, so we'll keep regressing until the scores actually show something we can improve on.

We generate the ground truth answers to those 10 using Opus 4.5 on ultra-think to ensure they're definitely valid. Then, once ready, we'll

- save git repository at beginner state.

### Open Questions *(Resolved)*

Question: how do I know once my system is working?

- Do I have a train set and test set, run it through the 10 training examples and evaluate the test performance?
- Do I run it against the same example multiple times one after another to show the stats improving?
- Do I run it against the same 5 examples multiple times to show each example getting better?

*Outcome: Train/test split approach adopted. 9 training queries populate knowledge, then test against 8 held-out queries. See `agent/evaluate.py`.*
