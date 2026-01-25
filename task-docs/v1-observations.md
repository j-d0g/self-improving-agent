# V1 Behavioral Observations

> Catalog of observed limitations, failure modes, and trade-offs in the current Learner-Improver pipeline.

---

## Incident Log

### Incident 001: Improver refuses to learn from self-corrected error

**Date:** 2024-01-24

**Query:** "Tell me what the total revenue difference between countries with more odd letters than even letters, and those with more than two vowels, during years that are divisible by 3?"

**What happened:**
1. Learner made a reasoning error: stated "2021 and 2024 are divisible by 3" (incorrect)
2. Learner self-corrected during execution when code showed only 2022
3. Learner logged the error in `<inefficiencies>` but wrote "None needed" in `<suggested_improvements>`
4. Improver read the reflection and accepted the Learner's self-assessment
5. Improver rationalized: "This was a one-off creative/puzzle query that isn't generalizable"
6. **Result:** No learning captured despite a clear reasoning failure

**Why this matters:**
- Self-corrected errors still represent wasted cycles
- The same divisibility reasoning error could occur in future queries
- The Improver's job is to prevent repeated mistakes, but it deferred to the Learner's judgment

---

### Incident 002: Learner forgets to write reflection log

**Date:** 2024-01-24

**What happened:**
- Learner answered a query but failed to write the mandatory reflection log
- Background Improver had nothing to process
- **Result:** No learning captured because the input artifact was never created

**Why this matters:**
- The Learner has too many overlapping concerns: interpret query, gather context, write code, execute, explain answer, AND write reflection
- Non-deterministic execution means any of these can be dropped under cognitive load
- The reflection log is "mandatory" per the prompt, but there's no enforcement mechanism

**Architectural insight:** A separate Evaluator/Reflector agent could:
- Receive the session trace as input (already captured automatically)
- Generate the reflection independently
- Remove this responsibility from the Learner entirely

---

### Incident 003: Shell escaping error wastes a turn (but Improver succeeds)

**Date:** 2024-01-24

**Query:** "year with best revenue and years with worst product"

**What happened:**
1. Learner's first Bash command failed due to f-string format specifiers (`:,.2f`) causing shell parsing issues
2. Learner self-corrected by switching to heredoc syntax
3. Learner wrote reflection, Improver processed it successfully
4. **Result:** Improver filled in Valid Products, added comparative analysis example

**Positive notes:**
- This is a success case for the Improver—it identified the shell escaping issue and added useful knowledge
- Correctly chose NOT to add shell syntax tips (outside scope of data knowledge)

**Remaining concern:**
- Shell escaping issues are recurring (this is a known footgun with `python3 -c`)
- Could be prevented by standardizing on heredoc in examples, but Improver declined to document

---

## Systemic Issues

### 1. Learner prompt: `<errors>` section is too narrow

**Location:** `prompts/learner.txt:85-86`

```markdown
<errors>
[List any errors, exceptions, or failures encountered during execution. "None" if clean run.]
</errors>
```

**Problem:** Learner interprets "errors" as code exceptions only. Reasoning errors, incorrect assumptions, and self-corrected mistakes go to `<inefficiencies>` instead—which the Improver treats as lower priority.

**Observed behavior:** Learner wrote "None - clean execution" in `<errors>` despite making a factual mistake about divisibility.

---

### 2. Learner prompt: `<suggested_improvements>` has no accountability

**Location:** `prompts/learner.txt:110-112`

```markdown
<suggested_improvements>
[What would have helped? New examples, documentation updates, helper functions, etc.]
</suggested_improvements>
```

**Problem:** No requirement to justify "None". Learner can dismiss its own errors without explanation.

**Observed behavior:** Learner wrote "None needed - this was a creative/puzzle-type query that wouldn't benefit from pre-built examples" without explaining why the divisibility error specifically wouldn't recur.

---

### 3. Improver prompt: SKIP criteria provide easy escape hatches

**Location:** `prompts/improver.txt:52-55`

```markdown
**SKIP when:**
- Error was random/typo (won't recur)
- Fix is too query-specific to generalize
- Root cause is ambiguous query (not fixable via docs)
```

**Problem:** "Fix is too query-specific to generalize" is overly broad. The Improver conflates the *query* being unique with the *error* being unique.

**Observed behavior:** Improver said "this type of query isn't generalizable" when the *error* (wrong divisibility reasoning) absolutely is generalizable.

---

### 4. Improver prompt: No instruction to critically evaluate Learner's self-assessment

**Location:** `prompts/improver.txt` (missing)

**Problem:** Improver has no guidance to independently analyze the reflection. It trusts `<suggested_improvements>: None` at face value.

**Observed behavior:** Improver stated "The reflection log explicitly states that no improvements are needed. The reasoning is sound..." without questioning whether the Learner's self-assessment was correct.

---

### 5. Learner has too many responsibilities (cognitive overload)

**Location:** `prompts/learner.txt` (entire file)

**Problem:** The Learner is responsible for:
1. Reading knowledge files (3+ files)
2. Interpreting the query
3. Writing and executing code
4. Explaining results to the user
5. Writing a structured reflection log with 9 sections

This creates cognitive overload and non-determinism. Under load, steps get skipped—most critically, the reflection log.

**Observed behavior:** Learner occasionally forgets to write the reflection log entirely, breaking the improvement pipeline.

**Design alternative:** Separate the "reflect" responsibility into a dedicated Evaluator agent that:
- Takes the session trace as input (already captured automatically)
- Generates reflection/analysis independently
- Removes this burden from the Learner

---

### 6. Improver prompt: Decision tree only handles data/formula errors

**Location:** `prompts/improver.txt:17-27`

```markdown
1. **Did the learner use wrong column names, values, or formulas?**
2. **Did the learner query something that doesn't exist?**
3. **Did the learner need a working code pattern?**
4. **Is the same code pattern used 3+ times?**
```

**Problem:** No path for "reasoning process errors" or "self-corrected mistakes". The decision tree assumes errors are always about data structure or code patterns.

**Observed behavior:** Improver had no framework for handling "Learner reasoned incorrectly about math" because it doesn't fit any decision tree branch.

---

## Trade-offs in Current Design

### Conservative vs. Aggressive Learning

**Current stance:** Conservative. The prompt explicitly says to AVOID "one-off fixes" and SKIP "query-specific" errors.

**Trade-off:**
- **Pro:** Prevents knowledge files from bloating with noise
- **Con:** Misses genuine learning opportunities when errors are mislabeled as "one-off"

**Observed failure mode:** Real errors dismissed as "too specific" because the query was unusual.

---

### Trust in Learner Self-Assessment

**Current stance:** High trust. Improver reads `<suggested_improvements>` and generally follows it.

**Trade-off:**
- **Pro:** Learner has full context of what happened; reduces Improver's cognitive load
- **Con:** Learner may minimize its own errors (self-serving bias)

**Observed failure mode:** Learner downplayed its divisibility mistake; Improver accepted this.

---

### Separation of Error Types

**Current stance:** `<errors>` for exceptions, `<inefficiencies>` for suboptimal approaches, `<dead_ends>` for abandoned paths.

**Trade-off:**
- **Pro:** Clear categorization for different failure modes
- **Con:** Reasoning errors fall through the cracks—not exceptions, not inefficiencies, not dead ends

**Observed failure mode:** Divisibility mistake logged as "inefficiency" rather than "error", reducing its perceived severity.

---

## Questions for V2 Design

1. Should the Improver independently verify the Learner's claims? (e.g., re-check if errors actually occurred)
2. How do we distinguish "genuinely one-off" errors from "errors that happen to appear in unusual queries"?
3. Should self-corrected errors be weighted differently than errors that caused wrong answers?
4. What's the right balance between knowledge file hygiene and capturing edge cases?
5. Should reflection be separated from the Learner into a dedicated Evaluator agent?
6. Can session traces replace reflection logs as the primary input to the Improver?

---

## References

- Reflection log (Incident 001): `logs/reflections/cb8936d6606c.md`
- Reflection log (Incident 003): `logs/reflections/a5d53804419b.md`
- Session trace (Incident 003): `logs/sessions/session_20260124_233542.json`
- Learner prompt: `prompts/learner.txt`
- Improver prompt: `prompts/improver.txt`
