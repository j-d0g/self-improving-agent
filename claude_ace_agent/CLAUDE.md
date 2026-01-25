# Agent Working Memory

> **Audience**: Agent SDK agents (Learner/Improver) - NOT for Claude Code CLI.
> The Learner reads this file via its system prompt before answering queries.
> The Improver reads and updates this file to track cross-session learnings.

---

## Quick Navigation

**READ FIRST** - before any task:
| Need | Read | Why |
|------|------|-----|
| Data structure | `knowledge/schema.md` | Column names, valid values, formulas |
| Code patterns | `knowledge/examples.md` | Working pandas code for common queries |
| Helper functions | `knowledge/functions.py` | Reusable utilities |
| Recent errors | `logs/sessions/*.json` | Session traces with execution details |

**WRITE TO** - after completing work:
| Output | Location | Format |
|--------|----------|--------|
| Session traces | `logs/sessions/session_*.json` | JSON execution trace (auto-saved) |
| Improver traces | `logs/improver/improver_*.json` | JSON execution trace (auto-saved) |
| Reflection logs | `logs/reflections/<run_id>.md` | XML-tagged markdown (human reference) |

---

## Directory Map

```
agent/
├── CLAUDE.md              # YOU ARE HERE - working memory (read via prompt)
├── agent.py               # Learner + background improver
├── evaluate.py            # Run train/test sets
├── tracing.py             # Execution trace utilities
│
├── knowledge/             # DURABLE - Improver updates these
│   ├── schema.md          # Data facts, column definitions, edge cases
│   ├── examples.md        # Query patterns with working code
│   └── functions.py       # Reusable helper functions
│
├── logs/                  # TRANSIENT - Learner creates these
│   ├── sessions/          # Session traces (JSON) - input to Improver
│   └── reflections/       # Self-reflection logs (human reference)
│
├── evals/
│   ├── train.json         # 9 queries - use for learning
│   ├── test.json          # 8 queries - use for benchmarking
│   └── benchmark.py       # Performance tracking
│
├── prompts/
│   ├── learner.txt        # Learner system prompt
│   └── improver.txt       # Improver system prompt
│
└── data/
    └── FUN_company_pl_actuals_dataset.csv  # 21,600 rows P&L data
```

---

## Current Focus Areas

<!-- Improver: Update priorities after each improvement cycle -->

| Priority | Area | Status | Notes |
|----------|------|--------|-------|
| High | L2 line item documentation | In progress | schema.md missing detailed L2 mappings |
| Medium | Negative examples | Pending | examples.md needs "queries that should fail" |
| Low | Function extraction | Pending | Repeated patterns → functions.py |

---

## Changelog

<!-- Improver: Log each change with date, what changed, and why -->

| Version | Date | Changes | Rationale |
|---------|------|---------|-----------|
| v0.1 | 2026-01-22 | Initial structure | Establish working memory pattern |

---

## Meta-Learnings

<!-- Improver: Add insights about the improvement process itself -->

### What's Working
- Session traces capture full execution context for analysis
- `schema.md` updates have the highest impact on accuracy

### What Needs Attention
- Learner often rewrites code that could be in `functions.py`
- `examples.md` lacks edge case coverage

---

## Knowledge File Health

<!-- Improver: Update after reviewing each file -->

| File | Last Reviewed | Status | Action Needed |
|------|---------------|--------|---------------|
| `knowledge/schema.md` | - | Partial | Add L2 line items |
| `knowledge/examples.md` | - | Minimal | Add negative examples |
| `knowledge/functions.py` | - | Empty | Extract common patterns |

---

## Patterns to Propagate

<!-- Improver: Track patterns discovered in session traces that should become examples -->

1. **Pending**: Rolling averages across time periods
2. **Pending**: "Last quarter" / "this decade" relative time handling
3. **Pending**: Product validation before filtering
4. **Pending**: Handling queries for non-existent data gracefully

---

## Open Questions

<!-- Track ambiguities requiring human input -->

- Should `functions.py` include visualization helpers?
- How to handle genuinely ambiguous queries (ask vs. assume)?
- Should negative examples go in `examples.md` or separate file?

---

## Improvement Workflow

1. **Read** session traces from `logs/sessions/`
2. **Identify** patterns, errors, root causes from execution details
3. **Update** appropriate knowledge file:
   - Wrong data values/structure → `schema.md`
   - Missing code pattern → `examples.md`
   - Repeated boilerplate → `functions.py`
