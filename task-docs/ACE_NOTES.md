# ACE Paper & Repository Study Notes

> **Purpose**: Understand ACE (Agentic Context Engineering) framework to inform agemo v2 improvements.
> **Created**: 2026-01-25

---

## Overview: ACE vs agemo Architecture Comparison

| Aspect | agemo (v1) | ACE |
|--------|------------|-----|
| Pipeline | Learner → Improver | Generator → Reflector → Curator |
| Agents | 2 | 3 (separation of concerns) |
| Reflection | Self-reflection (merged into Learner) | Separate Reflector agent |
| Knowledge format | Freeform markdown | Structured playbook with counters |
| Update granularity | Per-query | Per-query with batch consolidation |
| Bullet tracking | None | `helpful=X harmful=Y` counters |
| Retrieval | "Read everything" | Selective by bullet ID |
| Token budget | Unbounded | Configurable (default 80k tokens) |
| Deduplication | None | BulletpointAnalyzer (semantic embeddings) |

---

## Paper Key Claims

### The Problem ACE Solves

1. **Brevity bias**: Prompt optimizers prioritize concise instructions, dropping domain-specific heuristics
2. **Context collapse**: Monolithic rewriting degrades context over time (18k→122 tokens, 66.7%→57.1% accuracy)

### ACE Philosophy
> "Contexts should function not as concise summaries, but as comprehensive, evolving playbooks—detailed, inclusive, and rich with domain insights."

Unlike humans who benefit from concise generalization, LLMs are more effective with long, detailed contexts and can distill relevance autonomously.

### Results
- **+10.6% on agents** (AppWorld benchmark)
- **+8.6% on finance** (FiNER, Formula)
- **86.9% lower adaptation latency** than existing methods
- Works **without ground truth labels** (using execution feedback only)

---

## Three-Agent Pipeline Deep Dive

```
Generator ─────────────────┐
   │                       │
   ▼ (reasoning trace)     │
Reflector ◀────────────────┤
   │                       │
   ▼ (bullet tags)         │
Curator ───────────────────┘
   │
   ▼
Playbook (evolved knowledge)
```

### Generator (`ace/core/generator.py`)
- Produces answers using playbook knowledge
- Returns: response, bullet_ids (which bullets were used), metadata
- Gets reflection feedback for regeneration attempts

### Reflector (`ace/core/reflector.py`)
**The key innovation** - separates evaluation from curation

Output fields:
- `reasoning`: Chain of thought analysis
- `error_identification`: What went wrong
- `root_cause_analysis`: Why it occurred
- `correct_approach`: What should have been done
- `key_insight`: Strategy to remember
- `bullet_tags`: List of `{id, tag}` where tag ∈ {helpful, harmful, neutral}

**Even for correct answers**, Reflector tags helpful bullets to update counters.

### Curator (`ace/core/curator.py`)
Manages playbook through structured operations:

| Operation | Description | Required Fields |
|-----------|-------------|-----------------|
| ADD | New bullet | section, content |
| UPDATE | Modify existing | bullet_id, new_content |
| MERGE | Combine similar | bullet_ids, merged_content |
| DELETE | Remove low-value | bullet_id, reason |

**Delta update strategy**: Only the JSON operations are applied, not a full rewrite.

---

## Playbook Format

```
## STRATEGIES & INSIGHTS
[str-00001] helpful=5 harmful=0 :: Always verify data types before processing

## FORMULAS & CALCULATIONS
[cal-00002] helpful=8 harmful=0 :: NPV = Σ(Cash Flow / (1+r)^t)

## CODE SNIPPETS & TEMPLATES
[code-00003] helpful=2 harmful=1 :: def calculate_revenue(): ...

## COMMON MISTAKES TO AVOID
[err-00004] helpful=6 harmful=0 :: Don't forget timezone conversions

## PROBLEM-SOLVING HEURISTICS
[prob-00005] helpful=4 harmful=1 :: Break problems into smaller parts

## CONTEXT CLUES & INDICATORS
[ctx-00006] helpful=7 harmful=0 :: Look for quarterly patterns

## OTHERS
[misc-00007] helpful=1 harmful=0 :: Keep notes on domain specifics
```

### Format Components
- **Section slug**: `str`, `cal`, `code`, `err`, `prob`, `ctx`, `misc`
- **ID**: Sequential 5-digit numbering
- **Counters**: `helpful=X harmful=Y`
- **Separator**: `::`
- **Content**: Actual knowledge

---

## Training Loop (`ace.py:_train_single_sample`)

```
For each sample:
  1. Generator produces initial answer
  2. Check correctness

  If INCORRECT:
    For round in max_num_rounds (default 3):
      a. Reflector analyzes + tags bullets
      b. Update bullet counters
      c. Generator regenerates with reflection
      d. If now correct, break

  If CORRECT:
    a. Reflector tags helpful bullets (still runs!)
    b. Update bullet counters

  3. Every `curator_frequency` steps (default 1):
     a. Curator proposes operations
     b. BulletpointAnalyzer deduplicates (optional)

  4. Post-curator generation (measures improvement)
```

---

## Key Configuration Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `num_epochs` | 1 | Training passes over data |
| `max_num_rounds` | 3 | Reflection-regeneration attempts |
| `curator_frequency` | 1 | Run curator every N samples |
| `playbook_token_budget` | 80000 | Max tokens for playbook |
| `eval_steps` | 100 | Validation frequency |
| `save_steps` | 50 | Checkpoint frequency |
| `test_workers` | 20 | Parallel test evaluation |
| `bulletpoint_analyzer_threshold` | 0.90 | Semantic similarity for merge |

---

## Questions Answered

### How does ACE handle token budget?
- Configurable via `playbook_token_budget` (default 80k tokens)
- Curator receives budget in prompt, asked to respect it
- BulletpointAnalyzer merges similar bullets to stay under budget

### What's the curator frequency?
- Default: every step (`curator_frequency=1`)
- Can be adjusted for batch consolidation

### How does BulletpointAnalyzer detect similarity?
- Uses `sentence-transformers` for semantic embeddings
- Configurable threshold (default 0.90)
- Merges bullets above threshold

### What triggers ADD vs UPDATE vs MERGE vs DELETE?
- Curator LLM decides based on:
  - Current playbook state
  - Recent reflection
  - Token budget constraints
  - Playbook stats (bullet counts, usage patterns)

### Offline vs Online training?
- **Offline**: Train on train/val sets, test at start/end
- **Online**: Window-based training on test data (train → test → train → test...)
- Online enables adaptation during deployment

### Ground truth availability impact?
- Two Reflector prompts: with GT and without GT
- Without GT: Uses "environment feedback" (execution signals)
- Paper shows ACE still works without GT (+8.6% on finance)

---

## Critical Insights for agemo V2

### 1. Separation of Concerns is Essential
ACE separates evaluation (Reflector) from knowledge updates (Curator). agemo v1 merged these, causing:
- Improver trusts Learner's self-assessment
- No independent verification
- Cognitive overload on single agent

**V2 Action**: Add separate Evaluator agent that takes session trace as input.

### 2. Bullet Tracking Enables Quantitative Decisions
The `helpful/harmful` counters provide:
- Signal for which knowledge is working
- Basis for automated pruning
- Data for analyzing learning patterns

**V2 Action**: Add counters to examples.md entries.

### 3. Delta Updates Prevent Context Collapse
Monolithic rewriting degrades over time. ACE uses:
- Itemized bullets with unique IDs
- Structured operations (ADD/UPDATE/MERGE/DELETE)
- Incremental changes only

**V2 Action**: Move from freeform prose to structured knowledge format.

### 4. Reflector Runs Even on Correct Answers
This surfaces which knowledge was helpful, not just what went wrong.

**V2 Action**: Always run evaluation, not just on failures.

### 5. The Regeneration Loop
If Generator fails:
1. Reflector analyzes why
2. Generator tries again with reflection feedback
3. Repeat up to N times

**V2 Action**: Allow Learner to retry with Evaluator feedback before considering the query complete.

---

## Mapping ACE → agemo V2

| ACE Component | agemo V2 Implementation |
|---------------|-------------------------|
| Generator | Learner (Haiku) - already exists |
| Reflector | **NEW**: Evaluator agent (separate from Improver) |
| Curator | Improver (Opus) - focus on knowledge updates only |
| Playbook | Evolve `knowledge/` files to use structured format |
| Bullet tracking | Add `helpful/harmful` counters |
| BulletpointAnalyzer | Consider for deduplication |
| max_num_rounds | Add retry loop in Learner |

### Proposed V2 Architecture

```
Query
  │
  ▼
┌─────────────┐
│   Learner   │──────────────┐
│   (Haiku)   │              │
└─────────────┘              │
       │                     │
       ▼ (session trace)     │
┌─────────────┐              │
│  Evaluator  │◀─────────────┤ (retry if failed)
│  (Sonnet?)  │              │
└─────────────┘              │
       │                     │
       ▼ (reflection + bullet tags)
┌─────────────┐
│  Improver   │
│   (Opus)    │
└─────────────┘
       │
       ▼
knowledge/
├── schema.md     [schema-00001] helpful=X ...
├── examples.md   [ex-00001] helpful=X ...
└── functions.py  (code snippets with IDs?)
```

---

## Implementation Priorities

### Phase 1: Structured Knowledge Format
- [ ] Convert examples.md to bullet format with IDs
- [ ] Add helpful/harmful counters
- [ ] Track which bullets are used per query

### Phase 2: Separate Evaluator
- [ ] Create Evaluator agent (runs on session trace)
- [ ] Implement bullet tagging
- [ ] Counter update logic

### Phase 3: Delta Updates
- [ ] Curator-style operations for Improver
- [ ] Avoid full file rewrites
- [ ] Implement MERGE/DELETE for cleanup

### Phase 4: Deduplication
- [ ] Semantic similarity detection
- [ ] Automatic merging of similar bullets
- [ ] Token budget management

---

---

## Implementation Deep Dive

### 1. Bullet Format & Parsing (`playbook_utils.py`)

**Regex pattern:**
```python
pattern = r'\[([^\]]+)\]\s*helpful=(\d+)\s*harmful=(\d+)\s*::\s*(.*)'
```

**Parsed result:**
```python
{
    'id': 'calc-00001',
    'helpful': 5,
    'harmful': 0,
    'content': 'Always verify data types before processing',
    'raw_line': '[calc-00001] helpful=5 harmful=0 :: Always verify data types...'
}
```

**Section slugs** (3-5 chars):
| Section Name | Slug |
|--------------|------|
| strategies_and_insights | `fin` |
| formulas_and_calculations | `calc` |
| code_snippets_and_templates | `code` |
| common_mistakes_to_avoid | `err` |
| problem_solving_heuristics | `prob` |
| context_clues_and_indicators | `ctx` |
| others | `misc` |

**ID format:** `{slug}-{5-digit-number}` (e.g., `calc-00042`)

---

### 2. Generator: How Bullets Are Used

**Prompt structure:**
```
You are an analysis expert tasked with answering questions using:
- Your knowledge
- A curated playbook of strategies and insights
- A reflection from previous mistakes

**Playbook:**
{full_playbook}

**Reflection:**
{reflection_from_reflector}

**Question:**
{question}

**Output JSON:**
{
  "reasoning": "[chain of thought]",
  "bullet_ids": ["calc-00001", "fin-00002"],  // <-- KEY: declares which bullets used
  "final_answer": "[answer]"
}
```

**Key insight:** Generator must output `bullet_ids` it referenced. This enables:
- Reflector knows which bullets to tag
- Tracking which bullets are actually used
- Identifying "cold" bullets that are never referenced

---

### 3. Reflector: Bullet Tagging

**Input:**
- Question
- Generator's reasoning trace
- Predicted answer
- Ground truth (optional)
- Environment feedback
- Bullets used (extracted from playbook by ID)

**Output JSON:**
```json
{
  "reasoning": "[chain of thought analysis]",
  "error_identification": "[what went wrong]",
  "root_cause_analysis": "[why it occurred]",
  "correct_approach": "[what should have been done]",
  "key_insight": "[strategy to remember]",
  "bullet_tags": [
    {"id": "calc-00001", "tag": "helpful"},
    {"id": "fin-00002", "tag": "harmful"}
  ]
}
```

**Tags:** `helpful` | `harmful` | `neutral`

**Counter update logic:**
```python
for bullet_id, tag in bullet_tags:
    if tag == 'helpful':
        bullet.helpful += 1
    elif tag == 'harmful':
        bullet.harmful += 1
    # neutral: no change
```

---

### 4. Curator: Delta Operations

**Available operations** (only ADD currently implemented):

| Operation | Fields | Description |
|-----------|--------|-------------|
| ADD | `section`, `content` | New bullet with auto-generated ID |
| UPDATE | `bullet_id`, `content` | Replace existing bullet content |
| MERGE | `source_ids`, `content` | Combine bullets, delete sources |
| DELETE | `bullet_id`, `reason` | Remove bullet |

**ADD implementation:**
```python
slug = get_section_slug(section)      # e.g., "calc"
new_id = f"{slug}-{next_id:05d}"       # e.g., "calc-00042"
next_id += 1
new_line = f"[{new_id}] helpful=0 harmful=0 :: {content}"
# Insert after section header
```

**Curator prompt context:**
- Token budget (default 80k)
- Training progress (sample X of Y)
- Current playbook stats:
  ```json
  {
    "total_bullets": 45,
    "high_performing": 12,    // helpful > 5, harmful < 2
    "problematic": 3,         // harmful >= helpful
    "unused": 8,              // helpful + harmful = 0
    "by_section": {...}
  }
  ```

---

### 5. BulletpointAnalyzer: Deduplication

**Flow:**
1. Parse all bullets from playbook
2. Compute embeddings using `sentence-transformers` (`all-mpnet-base-v2`)
3. Normalize embeddings for cosine similarity
4. Build similarity matrix: `np.dot(embeddings, embeddings.T)`
5. Group bullets above threshold (default 0.90)
6. For each group:
   - LLM merges content into single bullet
   - Keep first bullet's ID
   - Sum helpful/harmful counts
   - Remove other bullets from group

**Merge prompt:**
```
Given these similar bulletpoints:
1. [calc-00001] helpful=3 harmful=0 :: Always check data types
2. [calc-00015] helpful=2 harmful=1 :: Verify column types before operations

Merge them into ONE bulletpoint:
- Keep ID from first entry: [calc-00001]
- Use combined counts: helpful=5 harmful=1
- Combine content to be comprehensive but concise
```

---

### 6. Bullet Usage Logging

**Log entry (`bullet_usage_log.jsonl`):**
```json
{
  "timestamp": "2025-01-25T14:30:00",
  "epoch": 1,
  "step": 42,
  "sample_id": "epoch_1_step_42",
  "bullet_ids_used": ["calc-00001", "fin-00003"],
  "bullets_with_content": [
    {"bullet_id": "calc-00001", "content": "Always verify..."},
    {"bullet_id": "fin-00003", "content": "Revenue = ..."}
  ],
  "is_correct": true,
  "sample_question": "What was Q1 revenue...",
  "reflection_summary": "The model correctly applied...",
  "bullet_count": 2
}
```

**Use case:** Curator can look up which samples used a bullet to understand its performance history.

---

### 7. The Complete Flow (Pseudocode)

```python
def train_single_sample(sample, playbook, config):
    # 1. GENERATE
    response = generator.generate(
        question=sample.question,
        playbook=playbook,
        reflection="(empty)"
    )
    answer = extract_answer(response)
    bullet_ids = response.bullet_ids
    is_correct = check_answer(answer, sample.target)

    # 2. REFLECT (runs for BOTH correct and incorrect)
    used_bullets = extract_playbook_bullets(playbook, bullet_ids)

    reflection, bullet_tags = reflector.reflect(
        question=sample.question,
        reasoning_trace=response,
        predicted_answer=answer,
        ground_truth=sample.target,
        bullets_used=used_bullets
    )

    # Update counters
    playbook = update_bullet_counts(playbook, bullet_tags)

    # 3. RETRY LOOP (only if incorrect)
    if not is_correct:
        for round in range(max_rounds):
            response = generator.generate(
                question=sample.question,
                playbook=playbook,
                reflection=reflection  # <-- Uses reflection feedback
            )
            answer = extract_answer(response)
            if check_answer(answer, sample.target):
                break
            # Get new reflection for next round
            reflection, bullet_tags = reflector.reflect(...)
            playbook = update_bullet_counts(playbook, bullet_tags)

    # 4. CURATE (every curator_frequency steps)
    if step % curator_frequency == 0:
        operations = curator.curate(
            current_playbook=playbook,
            recent_reflection=reflection,
            token_budget=80000,
            playbook_stats=get_playbook_stats(playbook)
        )
        playbook = apply_operations(playbook, operations)

        # Optional: deduplicate
        if use_bulletpoint_analyzer:
            playbook = analyzer.analyze(playbook, threshold=0.90)

    return playbook
```

---

## Session Log

| Query/Action | Notes |
|--------------|-------|
| Initial exploration | Mapped ACE structure, read TRADEOFFS.md |
| Read ace_paper.md | Key claims: +10.6% agents, +8.6% finance, 86.9% lower latency |
| Read ace.py | Understood training loop, configuration params |
| Read reflector.py | Bullet tagging is the key innovation |
| Read curator.py | Delta operations: ADD/UPDATE/MERGE/DELETE |
| Read prompts | Structured JSON output, reasoning required |
| Read playbook_utils.py | Bullet parsing regex, counter updates, operation application |
| Read bulletpoint_analyzer.py | Embeddings with sentence-transformers, FAISS similarity |
| Read logger.py | Bullet usage tracking, curator diff logging |

---

## Open Questions

- [ ] How to adapt bullet format for code in functions.py?
- [ ] Should Evaluator use same model as Improver or different?
- [ ] How to handle queries where no bullets are used?
- [ ] What's the right curator_frequency for agemo's use case?
- [ ] How to track bullet usage when knowledge is freeform?

---

## Dynamic Cheatsheet vs ACE

ACE builds on Dynamic Cheatsheet (DC). Key differences:

| Aspect | Dynamic Cheatsheet | ACE |
|--------|-------------------|-----|
| Roles | 2 (Generator + Curator) | 3 (+ Reflector) |
| Memory format | Freeform with usage counters | Structured bullets with helpful/harmful |
| Updates | Full rewrite | Delta operations (ADD/UPDATE/MERGE/DELETE) |
| Deduplication | None (relies on curator prompt) | BulletpointAnalyzer with embeddings |
| Bullet tracking | Usage count only | `helpful=X harmful=Y` + ID linking |

### What ACE Improved

1. **Dedicated Reflector** - Separates error analysis from curation (better signal quality)
2. **Delta updates** - Prevents context collapse that plagued DC
3. **Semantic deduplication** - FAISS embeddings + LLM merging
4. **Bullet ID tracking** - Generator outputs which bullets it used, Reflector tags them

### DC Performance Context
- +99% on Game of 24 (GPT-4o)
- +2x on AIME (Claude Sonnet)

ACE trades raw performance for **efficiency and scalability** (86.9% lower latency, online training).

---

## References

- [ACE Paper](ace_paper.md) - Stanford/SambaNova, arXiv:2510.04618v1
- [Dynamic Cheatsheet](https://github.com/suzgunmirac/dynamic-cheatsheet) - The precursor work ACE builds on
- [agemo TRADEOFFS.md](TRADEOFFS.md) - V1 limitations and V2 roadmap
