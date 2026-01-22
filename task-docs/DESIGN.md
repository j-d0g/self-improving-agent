# Design Document: Self-Improving Financial Analysis Agent

> **Note:** This is the detailed design document. For the concise architecture reference, see [CLAUDE.md](../CLAUDE.md). For decision rationale, see [TRADEOFFS.md](TRADEOFFS.md).

**Navigation:** [TASK](TASK.md) | [NOTES](NOTES.md) | [DESIGN](DESIGN.md) | [TRADEOFFS](TRADEOFFS.md) | [BLOG](BLOG.md)

**Previous:** [NOTES.md](NOTES.md) — Personal notes and ideas
**Next:** [TRADEOFFS.md](TRADEOFFS.md) — Implementation decisions and rationale

---

## Overview

This system implements a **self-improving data analysis chatbot** that demonstrates cross-session learning. The core insight is treating the agent's context—its knowledge files, examples, and instructions—as an **evolvable artifact** that improves through structured feedback loops.

Inspired by [Agentic Context Engineering](https://arxiv.org/pdf/2510.04618) (arXiv:2510.04618), this approach shifts from static prompt engineering toward **context evolution**: the agent collaboratively improves its own operational context through iterative refinement cycles.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LEARNING LOOP                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   User Query                                                         │
│        │                                                             │
│        ▼                                                             │
│   ┌─────────────┐                      ┌─────────────┐              │
│   │   Learner   │─────reflection──────▶│  Improver   │              │
│   │   (Haiku)   │                      │  (Sonnet)   │              │
│   └─────────────┘                      └─────────────┘              │
│        │                                    │                        │
│        ▼                                    ▼                        │
│   logs/reflections/                    knowledge/                    │
│   logs/improvements/                        │                        │
│                                             │                        │
│   ◀──────────────── Next Session ──────────┘                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Two-Agent Pipeline

| Agent | Model | Role | Cost Profile |
|-------|-------|------|--------------|
| **Learner** | Haiku | Answers queries, executes code, writes self-reflection logs | Cheap, fast |
| **Improver** | Sonnet | Reads reflection logs, applies targeted fixes to knowledge files | Balanced |

**Why two agents instead of one?**

1. **Separation of concerns**: The learner focuses on answering; improvement happens asynchronously.
2. **Cost optimization**: Haiku handles queries cheaply. Sonnet only runs in background for improvements.
3. **Safety**: The improver is restricted to `knowledge/` only—it cannot modify agent code or prompts.

**Why Haiku for the learner?**

- **Cost**: Primary driver. High-volume queries benefit from Haiku's lower cost.
- **Sufficiency**: For structured data analysis (filtering, aggregation), Haiku performs well given good examples in knowledge files.
- **Learning loop synergy**: Haiku's occasional mistakes create learning opportunities that improve the knowledge base for all future sessions.

---

## Knowledge System Design

### The Core Insight

Most LLM systems use static prompts. This system treats **knowledge files as evolvable context**—they accumulate learnings across sessions and are read by the learner before every query.

### Knowledge File Structure

```
knowledge/
├── schema.md          # WHAT: Data facts, columns, formulas, edge cases
├── examples.md        # HOW: Query patterns with working code
└── functions.py       # CODE: Reusable parameterized helpers
```

**Why this structure?**

| File | Purpose | When Improver Updates It |
|------|---------|-------------------------|
| `schema.md` | Data facts, formulas, boundaries | Learner used wrong column/value/formula, or queried non-existent data |
| `examples.md` | Query patterns | Learner needed a working code example |
| `functions.py` | Code reuse | Same pattern appears 3+ times |

This structure keeps knowledge **consolidated** rather than fragmented. The learner reads fewer files, and the improver has clear targets for each type of learning.

### Trade-off: Sparse vs. Pre-populated

We chose to start knowledge files **sparse** (structure only, no content). This:

- Demonstrates genuine learning (files grow from empty)
- Avoids over-fitting to expected queries
- Makes improvement visible in file diffs

The downside: early queries may be less efficient as the learner explores without guidance.

**Hybrid approach implemented**: Knowledge files start with structural skeleton (column names, file purposes) but minimal content. The learner can succeed without prior examples, but each mistake triggers improvement. This balances:
- Demonstrating organic learning (files grow from near-empty)
- Basic guidance (column names prevent complete blind exploration)
- Visible improvement (git diff shows meaningful additions)

---

## Self-Improvement Mechanism

### What Triggers Improvement?

Every learner session produces a **reflection log** with structured XML sections:

```xml
<query>Original question</query>
<interpretation>How learner understood it</interpretation>
<process>Step-by-step execution</process>
<answer>Final result</answer>
<confidence>High/Medium/Low</confidence>
<errors>Any failures encountered</errors>
<inefficiencies>Suboptimal steps taken</inefficiencies>
<root_cause_analysis>Why issues occurred</root_cause_analysis>
<suggested_improvements>What would help next time</suggested_improvements>
```

The evaluator reads these logs and produces **improvement specifications**—structured instructions for exactly what to add and where.

### How Improvements Are Represented

Improvements are **plain markdown and Python files**. No vector store, no database, no embedding retrieval.

**Why files over a vector store?**

1. **Transparency**: You can read the knowledge. Git diff shows exactly what changed.
2. **Determinism**: No retrieval uncertainty. Learner reads all knowledge files every time.
3. **Debuggability**: When the agent fails, you can inspect the exact context it had.
4. **Version control**: Git history = learning history. You can see what was learned when.

**Trade-off**: This doesn't scale to thousands of learnings. But for a focused domain (P&L analysis), the knowledge base stays small enough to fit in context.

**Why "read everything" over retrieval**:
- **Domain size**: P&L data analysis has ~50-100 distinct concepts; all fit easily in context
- **Determinism**: No retrieval uncertainty. Every query sees the same knowledge.
- **Simplicity**: No embedding infrastructure, no similarity threshold tuning
- **Debuggability**: When the agent fails, you can inspect exactly what it knew

For larger domains, retrieval would become necessary, but this prototype prioritizes demonstrating the learning loop over scalability.

### How Improvements Are Applied

The improver receives a **decision tree** in its prompt:

```
1. Wrong column names/values/formulas? → schema.md
2. Queried non-existent data? → schema.md (Edge Cases section)
3. Needed working code pattern? → examples.md
4. Same code 3+ times? → functions.py
```

Plus **quality criteria**:

- **Generalizable**: Helps a class of queries, not just one
- **Minimal**: Adds only what's missing
- **Verified**: Based on actual observed error
- **Precise**: Uses exact values, not approximations

This prevents the improver from adding speculative or overly specific learnings.

---

## Code Execution Strategy

**Current approach**: The learner uses the Claude Agent SDK's `Bash` tool to execute Python code via subprocess. The workflow:

1. Learner writes Python code as a string
2. Executes via `python -c "..."` or writes to temp file and runs
3. Captures stdout for analysis

**Safety measures in prototype**:
- Code runs in the same environment as the agent (no sandboxing)
- No network restrictions, filesystem restrictions, or resource limits
- Suitable for prototype/development; NOT production-ready

**Production requirements** (not implemented):
- Container isolation (Docker/gVisor) for each code execution
- Resource limits (CPU time, memory, disk)
- Network isolation (no outbound connections)
- Filesystem restrictions (read-only except designated output dirs)
- Input sanitization to prevent prompt injection into code

---

## Evaluation Strategy

### Measuring Improvement Effectiveness

The system includes:

1. **Train/test evaluation sets** (`evals/train.json`, `evals/test.json`)
2. **Benchmark tracking** (`benchmark.py`) capturing:
   - Accuracy (correct answers)
   - Token efficiency (tokens per query)
   - Tool call efficiency (calls per query)
   - Latency
3. **Knowledge snapshots** before/after improvement cycles

### How We Prevent Bad Improvements

1. **Quality criteria**: Improver prompt explicitly lists what to avoid (one-off fixes, speculative learnings)
2. **Self-reflection**: Learner writes reflection logs that identify root causes, preventing surface-level fixes
3. **Audit trail**: `logs/improvements/` records every change with git diff
4. **Git history**: All changes tracked, enabling easy rollback

### Rollback Mechanism

**Implemented**: `rollback.py` provides utilities to manage improvements:

```bash
python rollback.py list              # List recent improvements
python rollback.py show <commit>     # Show what a commit changed
python rollback.py rollback <commit> # Revert to state before commit
python rollback.py history           # Show knowledge file git history
```

Bad improvement detection is currently manual—review `logs/improvements/` and git diffs. Production would need automated regression testing: run test set after each improvement, rollback if accuracy decreases.

---

## Connection to Agentic Context Engineering

The [arXiv paper](https://arxiv.org/pdf/2510.04618) describes a framework where models iteratively improve their own performance by dynamically evolving contextual information. Key parallels:

| Paper Concept | This Implementation |
|---------------|---------------------|
| Evolvable context | `knowledge/` files that accumulate learnings |
| Self-directed optimization | Evaluator critiques → Improver applies fixes |
| Feedback loop | Learner mistakes → logs → evaluation → knowledge updates |
| Context evolution | Git-tracked changes to knowledge files |

**Key difference**: The paper describes models modifying their own prompts. This system is more conservative—the improver can only modify `knowledge/` files, not agent prompts or code. This provides safety while still enabling meaningful learning.

---

## Production Considerations

### What Would Change for Production

1. **Authentication/authorization**: Currently assumes trusted users
2. **Rate limiting**: No throttling on expensive Opus evaluations
3. **Async evaluation**: Currently synchronous; would need background job queue
4. **Multi-tenant isolation**: Knowledge is global; would need per-user/org separation
5. **Monitoring**: Need observability into learning loop health

### Scalability Concerns

- **Knowledge file size**: Eventually hits context limits. Would need chunking or retrieval.
- **Evaluation cost**: Opus is expensive. Would need smart batching or cheaper evaluation model.
- **Git operations**: Current git workflow wouldn't scale to high-frequency commits.

### Security Considerations

- **Code execution sandboxing**: NOT implemented in prototype. Production requires container isolation.
- **Prompt injection**: Learner reads user queries directly—injection risk exists. Mitigation: input validation, query sanitization.
- **Knowledge poisoning**: Malicious queries could inject bad learnings. Mitigation: human review of improvement logs, regression testing.

---

## AI Tool Usage

This project was developed using Claude Code CLI for code generation and Claude Agent SDK for the agent implementation.

**Development assistance**:
- Claude Code CLI: Architecture design, code generation, debugging, documentation
- Manual implementation: System design decisions, prompt engineering, evaluation strategy

**What worked well**:
- Rapid iteration on agent prompts and knowledge file structure
- Generating boilerplate (tracing, logging, CLI argument parsing)
- Documentation and explanation of design decisions

**What required human judgment**:
- Trade-offs between simplicity and features
- Prompt engineering for effective self-reflection
- Evaluation criteria for measuring improvement

---

## Summary

This system demonstrates **cross-session learning** through:

1. **Structured reflection**: Every query produces a detailed log
2. **External critique**: Opus evaluator identifies root causes
3. **Targeted improvement**: Sonnet improver updates the right knowledge file
4. **Persistent context**: Knowledge files are read at the start of every session

The key insight from the Agentic Context Engineering paper—that context itself can be an evolvable artifact—is implemented here as **git-versioned markdown files** that grow over time.

The system trades sophistication (no vectors, no retrieval, no neural improvement selection) for **transparency and debuggability**. Every improvement is visible in a git diff. Every learner failure can be traced to its knowledge context.

---

## Remaining Considerations

1. **Automated regression testing**: Run test set after each improvement, rollback if accuracy drops
2. **Multi-tenant isolation**: Current knowledge is global; production needs per-user/org separation
3. **Scaling knowledge files**: When domain grows beyond context limits, add retrieval layer
4. **Rate limiting**: Throttle expensive operations (currently unbounded)
5. **Observability**: Dashboard for learning loop health (improvement rate, accuracy trends)
