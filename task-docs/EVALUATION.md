# Agemo Take-Home Task Evaluation

**Candidate Submission Review**
**Reviewer**: Founding Team, Agemo
**Date**: January 22, 2026

---

## Executive Summary

This submission demonstrates a **well-architected self-improving financial analysis agent** that successfully addresses the core challenge of cross-session learning. The implementation shows strong software engineering fundamentals with clean code organization, comprehensive tracing, and a thoughtful multi-agent design.

**Overall Score: 78/100** (Strong Pass)

| Category | Weight | Score | Weighted |
|----------|--------|-------|----------|
| Execution | 40% | 80/100 | 32.0 |
| Continuous Learning Design | 30% | 75/100 | 22.5 |
| System Architecture | 15% | 85/100 | 12.75 |
| Communication | 10% | 80/100 | 8.0 |
| Production Readiness | 5% | 65/100 | 3.25 |
| **Total** | 100% | — | **78.5** |

---

## 1. Execution (40%) — Score: 80/100

### What Works Well

**Core Functionality Implemented**
- Natural language → pandas code generation ✓
- Code execution via Bash tool (subprocess) ✓
- Structured reflection logs with root cause analysis ✓
- Background improvement workflow ✓
- Full evaluation pipeline with train/test splits ✓

**Code Quality**
- Clean, well-organized module structure
- Proper async/await patterns throughout
- Comprehensive type hints in key areas
- Good separation of concerns (agent.py, improver.py, tracing.py, evaluate.py)

**Evaluation Results**
```
Training Set: 9/9 queries successful (100%)
Test Set: 8/8 queries successful (100%)
Total Reflection Logs: 70+ files generated
```

The agent successfully handles:
- Basic filtering queries
- Multi-step aggregations
- Edge case detection (Product E, Employee Headcount)
- Complex analytical queries (variance analysis, outlier detection)

### Areas for Improvement

**Cross-Session Learning Evidence is Incomplete**

The rubric specifically asks to demonstrate:
> 1. Initial state: Agent makes a mistake on Question A
> 2. Learning: Agent analyzes and creates persistent improvement
> 3. Fresh session: New conversation (simulating days later)
> 4. Improved state: Agent handles Question B correctly

**Finding**: While the infrastructure for learning exists, I could not find clear evidence of:
- A documented "before" state where the agent made mistakes
- File diffs showing knowledge accumulated from errors
- A "Session 2" demonstrating improved behavior from learned knowledge

The knowledge files (`schema.md`, `examples.md`) appear to have been **manually curated** rather than grown through the improvement loop. For example:
- `examples.md` has 4 positive examples but states "(No examples recorded)" under Negative Examples
- `functions.py` contains only commented-out template code
- `schema.md` edge cases section has good content but no git history showing when it was learned

**Answer Quality on Operating Margin Query**

One query returned a suboptimal answer:
```
Query: "Which product had the highest operating margin in Q3 2023?"
Expected: "Product C at -22.19%"
Agent returned: "The reflection log has been written successfully."
```

The agent wrote the reflection log but didn't output the actual answer to the user.

**Recommendation**: Need a clear demo workflow showing:
1. Run query → observe error
2. Run improver → see knowledge file diff
3. Run similar query → observe improvement

### Execution Score Breakdown

| Criterion | Points |
|-----------|--------|
| Agent runs and produces answers | 25/25 |
| Correct answers on evaluation sets | 20/25 |
| Demonstrated cross-session learning | 15/25 |
| Code quality and maintainability | 20/25 |
| **Total** | **80/100** |

---

## 2. Continuous Learning Design (30%) — Score: 75/100

### The Architecture

```
Learner (Haiku) → Reflection Log → Improver (Sonnet) → Knowledge Files
     ↑                                                      ↓
     └──────────────── Next Session ────────────────────────┘
```

**Strengths**

1. **Clear Learning Artifacts**: The reflection log format with XML tags is well-designed:
   - `<root_cause_analysis>` forces the model to categorize errors
   - `<suggested_improvements>` captures actionable fixes
   - Mandatory logging ensures no silent failures

2. **Decision Tree for Improvements**: The improver prompt has a clear decision tree:
   ```
   Wrong values/formulas → schema.md
   Non-existent data → schema.md (Edge Cases)
   Needed code pattern → examples.md
   Repeated code 3+ times → functions.py
   ```

3. **Quality Criteria**: The prompt explicitly prevents bad learnings:
   - "Generalizable (applies to class of queries)"
   - "SKIP when: Fix is too query-specific to generalize"

4. **Git-Based Versioning**: The `_commit_improvements()` method using git worktrees is a clever approach for tracking learning history:
   ```python
   git worktree add -b learnings <worktree_path> HEAD
   # ... apply changes ...
   git commit -m "learning: eval_q01_revenue (2026-01-21 12:30)"
   ```

**Weaknesses**

1. **No Retrieval Mechanism**: Knowledge is loaded in full every time. Works for this dataset but won't scale.
   > "This doesn't scale to thousands of learnings. But for a focused domain (P&L analysis), the knowledge base stays small enough to fit in context."

   Fair trade-off, but worth noting.

2. **Improvement Validation is Missing**: There's no automated check that improvements actually help. The design doc asks:
   > "Have you implemented any automated rollback mechanism?"

   The answer appears to be "no" — bad improvements would persist until manually caught.

3. **Limited Evidence of Actual Learning**: The 70+ reflection logs exist, but knowledge files don't show organic growth. Compare:
   - `schema.md`: Has edge cases documented, but unclear if these came from learner errors
   - `examples.md`: Only 4 examples, all positive (no negative examples logged)
   - `functions.py`: Empty (only templates)

4. **Background Improvement is Fire-and-Forget**: The improver runs in background but there's no verification:
   ```python
   task = asyncio.create_task(self._background_improve(reflection_log))
   _background_tasks.add(task)
   task.add_done_callback(_background_tasks.discard)
   ```

   Errors are logged but not surfaced to the user.

### Learning Design Score Breakdown

| Criterion | Points |
|-----------|--------|
| Innovation in storage/retrieval | 20/25 |
| What can be learned (types) | 20/25 |
| Evidence improvements actually help | 15/25 |
| Thoughtful quality criteria | 20/25 |
| **Total** | **75/100** |

---

## 3. System Architecture (15%) — Score: 85/100

### Strengths

**Clean Module Separation**
```
agent.py       - Core learner loop
improver.py    - Knowledge updates
tracing.py     - Shared metrics/dataclasses
evaluate.py    - Test runner
benchmark.py   - Performance tracking
```

Each module has a single responsibility and clean interfaces.

**Thoughtful Model Selection**
- **Learner**: Haiku (cheap, fast for routine queries)
- **Improver**: Sonnet (balanced for careful edits)
- Design doc mentions Opus for evaluation (though not implemented in this version)

**Comprehensive Tracing**
```python
@dataclass
class ExecutionTrace:
    query: str
    run_id: str
    timestamp: str
    agent_version: dict  # git commit tracking!
    total_tokens: int
    total_tool_calls: int
    turns: list  # Full thinking + tool calls
    final_answer: str
```

The `agent_version` field tracking git commit is production-worthy.

**Benchmark Dashboard**

The `benchmark.py` generates a polished HTML dashboard with:
- Token efficiency over time
- Tool call trends
- Latency tracking
- Run-to-run comparisons

This is beyond what was required and shows good product thinking.

### Weaknesses

**No Evaluator Agent (Despite Documentation)**

CLAUDE.md and DESIGN.md describe a three-agent pipeline:
```
Learner → Evaluator (Opus) → Improver
```

But the actual implementation has only two:
```
Learner → Improver (directly)
```

The evaluator that would **critique answers for correctness** is missing. This is a significant gap — the improver is applying fixes without external validation of whether the learner's answer was actually wrong.

**No Error Recovery in Agent Loop**

If a tool call fails, there's basic exception handling but no retry logic or graceful degradation:
```python
except Exception as e:
    logger.error(f"Error processing message: {e}", exc_info=True)
    # Continue processing - don't let one error stop the trace
```

### Architecture Score Breakdown

| Criterion | Points |
|-----------|--------|
| Clear separation of concerns | 25/25 |
| Justified technical choices | 20/25 |
| Scalable patterns | 20/25 |
| Documentation matches implementation | 20/25 |
| **Total** | **85/100** |

---

## 4. Communication (10%) — Score: 80/100

### Strengths

**Design Document is Thorough**

`DESIGN.md` covers:
- Architecture overview with diagrams
- Self-improvement mechanism
- Knowledge file structure with clear rationale
- Trade-off discussions
- Production considerations
- Connection to academic research (Agentic Context Engineering paper)

The document anticipates reviewer questions and addresses them proactively.

**README Files are Clear**

Both `README.md` and `agent/README.md` provide:
- Setup instructions
- Usage examples
- Architecture diagrams
- File structure explanations

**Honest About Gaps**

The design doc includes honest "Open Questions" about areas not fully implemented:
> "Is there automated rollback for bad improvements?"
> "What's your code execution strategy and sandboxing approach?"

### Weaknesses

**Unanswered Questions in Design Doc**

Several `[QUESTION]` placeholders suggest the design doc was prepared for an interview discussion rather than as a complete standalone document:
```markdown
> **[QUESTION]**: I need to understand your code execution approach...
> **[QUESTION]**: Have you implemented any automated rollback mechanism?
> **[QUESTION]**: What AI tools did you use during development?
```

**Inconsistencies Between Docs and Implementation**

- CLAUDE.md says "three-agent pipeline" but implementation has two
- References to `evaluator.md` and `evaluator.txt` that don't exist in the main agent folder
- The prototype folder has different agent definitions that diverge from main

### Communication Score Breakdown

| Criterion | Points |
|-----------|--------|
| Design doc clarity | 25/30 |
| README completeness | 25/30 |
| Demo documentation | 15/20 |
| Honest about limitations | 15/20 |
| **Total** | **80/100** |

---

## 5. Production Readiness (5%) — Score: 65/100

### Strengths

**Structured Logging**
- JSON traces with full turn history
- Markdown reflection logs for human review
- Session aggregation with cost tracking

**Cost Awareness**
- Model selection based on cost/capability trade-offs
- Token counting per query
- Total cost tracking in metrics

**Virtual Environment Enforcement**
```markdown
## RULES!
- NEVER SET THIS UP WITHOUT A VIRTUAL ENVIRONMENT! ALWAYS USE A .venv.
```

### Weaknesses

**Code Execution Security**

The agent executes user-influenced pandas code via subprocess:
```python
allowed_tools=["Read", "Write", "Bash", "Grep", "Glob"]
```

The design doc explicitly flags this:
> "**Code execution sandboxing**: [NEEDS YOUR INPUT]"

For a production system, this would need:
- Container isolation
- Resource limits
- Input sanitization

**No Authentication/Authorization**
- No API key validation
- No rate limiting
- No multi-tenant isolation

**Limited Error Handling**
- Background task failures are logged but not retried
- No circuit breaker pattern for API failures
- No graceful degradation

### Production Score Breakdown

| Criterion | Points |
|-----------|--------|
| Logging and observability | 20/25 |
| Error handling | 10/25 |
| Security considerations | 15/25 |
| Deployment readiness | 20/25 |
| **Total** | **65/100** |

---

## Specific Feedback

### What I Liked

1. **The reflection log format is excellent** — structured XML with root cause analysis is genuinely useful for debugging and learning

2. **Benchmark dashboard shows product sensibility** — going beyond requirements to build visualization tools

3. **Git-based learning history** — using worktrees for isolated commits is creative and debuggable

4. **Honest design documentation** — acknowledges limitations rather than overselling

5. **Clean async Python** — proper use of asyncio patterns throughout

### What I'd Want to See in the Demo

1. **A live mistake → learning → improvement cycle**
   - Show the agent fail on a query
   - Show the improver updating knowledge
   - Show a fresh session handling a similar query correctly

2. **Git diff of knowledge growth**
   - Before: empty `examples.md`
   - After: populated with learned patterns

3. **Benchmark comparison** showing improvement over time
   - Run 1: baseline efficiency
   - Run 2: after improvements applied
   - Delta showing fewer tokens/tools per query

### Key Missing Pieces

1. **Evaluator agent** — the design describes one but it's not implemented
2. **Demonstrated learning** — infrastructure exists but I couldn't verify the loop completes
3. **Rollback mechanism** — mentioned as desirable but not implemented

---

## Final Recommendation

**Hire Signal: Positive**

This candidate demonstrates:
- Strong software engineering fundamentals
- Ability to design and implement complex multi-component systems
- Thoughtful architectural trade-offs
- Good documentation habits

**Concerns to Address in Interview**:

1. Why is there a gap between the documented three-agent pipeline and the two-agent implementation?

2. Can you walk me through a specific example where the learning loop completed end-to-end?

3. What would you prioritize to make this production-ready?

4. The reflection logs suggest the learner is already quite good at the P&L domain — was it hard to find cases where it actually failed and needed to learn?

---

## Score Summary

| Category | Weight | Score | Weighted |
|----------|--------|-------|----------|
| Execution | 40% | 80 | 32.0 |
| Continuous Learning Design | 30% | 75 | 22.5 |
| System Architecture | 15% | 85 | 12.75 |
| Communication | 10% | 80 | 8.0 |
| Production Readiness | 5% | 65 | 3.25 |
| **Total** | 100% | — | **78.5/100** |

**Grade: Strong Pass**

The candidate built a working system that demonstrates understanding of the core challenge. The execution is solid but needs clearer evidence that cross-session learning actually works in practice. Would recommend proceeding to onsite interview with focus on live demo of the learning loop.

---

*Evaluation completed by Agemo Founding Team*
