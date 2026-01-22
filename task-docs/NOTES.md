# Personal Notes & Ideas

> This document contains personal notes, questions, ideas, and talking points gathered during the scoping and development process.

**Navigation:** [TASK](TASK.md) | [NOTES](NOTES.md) | [ARCHITECTURE](ARCHITECTURE.md) | [TRADEOFFS](TRADEOFFS.md) | [BLOG](BLOG.md)

**Previous:** [TASK.md](TASK.md) — Original requirements
**Next:** [ARCHITECTURE.md](ARCHITECTURE.md) — Early design exploration (see [CLAUDE.md](../CLAUDE.md) for final architecture)

---

## Brief

> Take-home tasks from agemo regarding building a self-improving agentic system for completing data analysis. Spend <8 hours on it.

## Progress Checklist

- [x] Read the task.
- [x] Watch Agent SDK Video
- [x] Take lots of notes, questions, ideas, trade-offs, design decisions and talking points.
- [x] Run through Agent SDK Tutorial
- [x] Review progress, feedback, thoughts.
- [x] Decide the first tasks.

---

# 1. Core Problem Understanding

> What is the actual challenge? Key requirements distilled.

**The Challenge:** Build a **self-improving data analysis chatbot** that:

1. **Analyzes tabular data** (CSV files) through natural language questions
2. **Detects when it makes mistakes** during analysis
3. **Learns from those mistakes** by creating persistent improvements
4. **Demonstrates meta-learning**: The agent gets better **across sessions** - not just within a single conversation

**Key Insight:** The core challenge isn't building a chatbot — it's designing a system where **Session N+1 is measurably better than Session N**.

---

# 2. Design Questions

> Questions that needed answers before building. These shaped the architecture.

**Resolution Key:**
- ✅ **Resolved** — Decision made, linked to where documented
- ⚠️ **Deprioritized** — Considered but not implemented (usually time constraints)
- ❓ **Open** — Not addressed in final implementation
- `[? ...]` — Gap requiring user input to clarify

## 2.1 Error Detection & Learning Timing

- Do we want an agent to analyse errors during run-time, or offline as a reflective stage?
  - ✅ **Resolved:** Both. Learner does self-reflection at end of query (runtime), Improver runs async in background (offline). → [TRADEOFFS.md](TRADEOFFS.md#learner--improver-removed-evaluator-and-orchestrator)
- Is the creation of the persistent improvement during run-time, or also off-line?
  - ✅ **Resolved:** Async background agent — effectively offline from user's perspective. → [TRADEOFFS.md](TRADEOFFS.md#learner--improver-removed-evaluator-and-orchestrator)
- How are errors identified and validated? Errors at step level but also final answer level?
  - ✅ **Resolved:** Pivoted from correctness to efficiency metrics (tokens, tool calls) since Haiku got most answers correct. → [TRADEOFFS.md](TRADEOFFS.md#evaluations-validations-and-verifications)

## 2.2 What Does "Success" Look Like?

- How do we know what right/wrong is? (i.e an error, how can we detect that it has done the wrong thing?) What does success look like?
  - ✅ **Resolved:** Pivoted to efficiency metrics. Haiku got answers correct, so "success" became fewer tokens and tool calls. → [TRADEOFFS.md](TRADEOFFS.md#evaluations-validations-and-verifications)
    - If anything is subjective, file it out by assigning a specification agent that continuously asks the user questions until it can answer parts of ambiguity and has verifiable metrics for success.
      - ⚠️ **Deprioritized:** Spec agent not implemented — focused on simpler metrics instead.
    - An error can be the wrong result - it can also be the right final result, but reached inefficiently because wrong tool calls were made to slow down the process. Identifying the *kinds* of errors our system has will be important so that we can classify and target them.
      - ✅ **Adopted:** This insight drove the pivot to efficiency metrics.
    - An error can be performance: how many times is it repeating things such as on-the-fly script executions, and how can we distill these into reusable python scripts and skills?
      - ✅ **Adopted:** Functions saved to `knowledge/functions.py`.
    - Hallucination: do the fields or values even exist?
      - ⚠️ **Not needed:** Task was too in-distribution — never observed hallucination, so no detection mechanism was implemented.
    - Code execution errors - these are a good category, very deterministic! Identify common scripts run, and save them as python scripts permanently!
      - ✅ **Adopted:** Reusable functions in `knowledge/functions.py`.

## 2.3 Meta-Learning Implementation

- How do we want to handle or implement the meta-learning? New skills, scripts, functions, rules, titles (when to use x)?
  - ✅ **Resolved:** Knowledge files approach — `schema.md`, `examples.md`, `functions.py` updated by Improver. → [CLAUDE.md](../CLAUDE.md#knowledge-system)
    - Sounds like a perfect way to use skills, and improve skills / tools / commands. Maybe outsource deterministic steps to a script to avoid or reduce variability and error-prone?
      - ✅ **Partially adopted:** Functions in `functions.py`, but full skills system not implemented.
    - How is all this orchestrated though? Constantly iterate on improving the skills documentation markdown file.
      - ✅ **Resolved:** Improver agent updates knowledge files based on Learner's reflection logs.
        - Real time, or afterwards?
          - ✅ **Resolved:** Afterwards — async background agent. → [TRADEOFFS.md](TRADEOFFS.md#learner--improver-removed-evaluator-and-orchestrator)

## 2.4 Improvement Agent Influence

- How much influence do we give the improvement agents in terms of modifying existing docs when a mistake is made and improvements to the docs need to be added?
  - ✅ **Resolved:** Restricted to `knowledge/` directory only — cannot modify code or other files. → [CLAUDE.md](../CLAUDE.md#development-notes)
- How do we navigate large changes that might fix one Q&A, but break/worsen performance overall against other questions?
  - ⚠️ **Deprioritized:** Batching (10-50 examples before updating) was planned but deprioritized for N+1 demo requirement. Per-query updates accepted as potentially noisy trade-off. → [TRADEOFFS.md](TRADEOFFS.md#improvement-system)
  - ✅ **Resolved:** Git history serves as rollback mechanism — can manually revert if needed.

## 2.5 Dataset Flexibility

- What happens if we now plug a completely different dataset in? Does it still work?
  - ✅ **Resolved:** Designed for generalization — minimal skeleton that can easily accommodate a different dataset.
  - The task was already too easy, so adding dataset-specific features would have saturated measurable learnings. Kept intentionally generic.
- How rigid is our system to the current dataset - realistically, is this a problem where we want to only ever use a single dataset, or is the nature of this problem one that invites frequent changing and plug/play?
  - ✅ **Resolved:** Designed to be dataset-agnostic. The knowledge files (`schema.md`, `examples.md`, `functions.py`) can be replaced for a new dataset.
- If so, how can we look to even add the set-up process (i.e a /set-up-dataset skill that instantiates a repository based on running agents and sub-agents on the task)?
  - ⚠️ **Deprioritized:** Not implemented due to time constraints, but architecture supports this future extension.
    - What things can change? Columns and row entries, new kinds of data, how tolerant and adaptable is the system?
      - ✅ **Addressed by design:** Knowledge files are the only dataset-specific components — replace them for a new dataset.

## 2.6 Query Handling

- Vague queries like "How much money did predominantly caucasian countries make in …" - is that revenue or profit? How do we verify the countries mentioned?
  - ✅ **Resolved:** Learner makes assumptions but **explicitly states them** in its response. This keeps correctness scope on query accuracy, not language interpretation. If the user disagrees with the interpretation, they can correct it.
- Data Analysis Question Categories: each time a user asks a question, is it one that's currently well-documented under our pre-defined categorical workflows? How can we identify/extend/add it to our system if not?
  - ✅ **Partially resolved:** `knowledge/examples.md` stores query patterns. New patterns added by Improver based on Learner reflections.
- Storing a list of custom / weird composite queries, and what they mean (how they're translated to actions & query scripts)
  - ✅ **Partially resolved:** `knowledge/examples.md` serves this purpose.
    - But users might enter weird queries that don't make sense, but their direction and explanation might lead to the agent to make a false connection/rule if they're an outlier. Needs to be repetitive enough. (edge-case).
      - ⚠️ **Acknowledged risk:** Per-query updates may persist noisy examples. Batching would have mitigated this. → [TRADEOFFS.md](TRADEOFFS.md#improvement-system)

---

# 3. Implementation Ideas Considered

> Concrete approaches explored. Some were adopted, others deprioritized.

**Resolution Key:** Same as Section 2 — ✅ Adopted, ⚠️ Deprioritized, ❓ Open, `[? ...]` needs input.

## 3.1 Knowledge Persistence Strategy

- **Intentional design decision:** only allow claude to make decisions by saving scripts and skills in the repository. Do not let it execute raw code that hasn't been persisted. The idea is that we want actions to be tractable and measurable. If we just let it generate whatever, you get more variation and less building upon existing pipelines / ground/reference point to improve upon.
  - [? Was this enforced? The Learner appears to execute arbitrary pandas code at runtime. Is the "persistence" aspect about what the *Improver* saves to knowledge files, rather than constraining the Learner?]

- Examples doesn't mean entire customer examples of chats - it means example scripts that can be run to query a particular row, or entry.
  - ✅ **Adopted:** `knowledge/examples.md` stores reusable query patterns, not full chat logs.
    - i.e a csv query for a level 0 field or manipulation of level 0 fields
    - i.e a csv query for a level 2 field or manipulation of level 2 fields
    - i.e a csv query for composite / follow-up queries and how to compute that in code.
    - Then the agent can realise it's as simple as plug-and-play with the same formula but different fields to achieve the desired result.

## 3.2 Agent Architecture Ideas

- **Sub-agents for different tasks:** one for finding more information, one for deciding tools to call, one for analysing and determining errors, one for specs and disambiguating queries to generate deterministic workflow/plan/validation etc.
  - ⚠️ **Simplified:** Final system uses 2 agents (Learner + Improver) instead of multiple specialists. Task complexity didn't warrant full separation. → [TRADEOFFS.md](TRADEOFFS.md#learner--improver-removed-evaluator-and-orchestrator)

- **Sub-agents for context-management:** whenever you need to search down documentation files to make an isolated decision for a sub-task in the grander scheme, where the only thing that's important to the main agent is what decision to make next, sub-agents are great.
  - ⚠️ **Not implemented:** Learner handles everything in single context. Task was simple enough that context isolation wasn't needed.
    - Agent needs to now look into tools and decide what tool to use next. The process fluff (the path it takes to find the right context, the wrong context it found along the way, the mistakes and debugging during the isolated sub-task) can be outsourced to a sub-agent.

- **Spawn a sub-agent whenever an error is made**, to actively try to fix?
  - ⚠️ **Not implemented:** Errors handled via self-reflection + async Improver, not real-time sub-agent spawning.

## 3.3 Model Selection Strategy

- **Using Haiku for the actual generation, and Opus for the offline batch reflection/improvement.** More user requests, less often reflection, permanent improvement requires more intelligence than data analysis (simple task).
  - ✅ **Adopted:** Haiku 4.5 for Learner, Opus 4.5 for Improver. → [TRADEOFFS.md](TRADEOFFS.md#haiku-45-learner-opus-45-improver)

- Use a cheaper dumber model so that we can see the kinds of patterns that emerge.
  - ✅ **Adopted:** Haiku intentionally chosen to create room for measurable improvement.

- **Using ensemble of models (jury) for evaluation & judge feedback.** This is the backbone of our entire system, everything relies on having strong, relevant and unbiased feedback.
  - ⚠️ **Deprioritized:** Single-model evaluation (Opus) used instead. Jury would add latency and cost; Opus alone was sufficient for demo scope.
  - [? Was model jury considered seriously, or was it always stretch goal? Any learnings on when jury would be worth it?]

## 3.4 Batching & Learning Rate

- **Batching tiers:** every 1 for appending new logs to database, 10 for generalising errors and mistakes and learning patterns, 25 for updating commands and scripts, 100 for updating skills, docs etc.
  - ⚠️ **Deprioritized for N+1:** Per-query updates used instead. Batching would show improvement at N+50, not N+1. → [TRADEOFFS.md](TRADEOFFS.md#improvement-system)
  - **Post-build reflection:** This is probably the most significant trade-off. Per-query updates risk noise, but batching wouldn't satisfy the demo requirement.
  - [? In hindsight, was per-query the right call? Did you observe noise in the knowledge files, or was it fine?]

- i.e 1000 chats + suggestions, batch into 100 x 10, each 100 is analysed by a claude code agent, and contains a summary of the general problem trends and solutions, then another agent then compares these 10 to make the most important and recurring change. This minimises and controls how much change we make to ensure we aren't spiralling into worser performance. **The frequency at which we batch is our learning rate** - we can play with this.
  - 💡 **Insight preserved:** "Frequency of batching = learning rate" is a useful mental model. Worth revisiting if scaling beyond demo.

## 3.5 Evaluation & Benchmarking

- Develop a benchmark suite using claude code that forms a gold standard that's hidden from the agent and used to bench future performance.
  - ✅ **Adopted:** `evals/benchmark.py` + train/test split. Gold standard answers generated by Opus 4.5 ultrathink.

- **A way to test automatic learning / continual meta-learning:** get eval set of 50 queries (gold standard) with perfect answers and think about what's important: time, tokens, context, efficiency etc. Then run through these examples one-by-one, and observe how fast the performance improves with each test-case input so that we eventually get a graph of progress in the above metrics we care about - and the one with the best gains (rate of drop in cost) gives us our best system.
  - ✅ **Partially adopted:** 9 train + 8 test queries (smaller than 50). Tracks tokens + tool calls. Dashboard visualizes progress.

- **Our hyperparameters:** system prompt, agent architecture/loop, repository structure, any decisions we make.
  - ✅ **Adopted implicitly:** These were iterated on, but not formally tracked as "hyperparameters."
  - [? Did you keep notes on what prompt/architecture changes you tried and their effects? Or was it more ad-hoc?]

- Performance can be gauged by correctness, but also number of steps to complete, time to complete, tokens required to complete, redundant search calls or retries or errors made etc.
  - ✅ **Adopted:** Tokens + tool calls became primary metrics after correctness saturated. → [TRADEOFFS.md](TRADEOFFS.md#evaluations-validations-and-verifications)

- See trick questions and example questions. Test performance on those first and observe what kind of workflows might be needed. Then expand these questions to a larger suite (25-50 examples) and build an evaluation metric for things that matter.
  - ✅ **Adopted:** Started with trick questions that caused most tool calls/backtracking.

## 3.6 Other Technical Ideas

- **Sandbox environment** to allow security for free reign
  - ⚠️ **Not implemented:** Local execution trusted for demo. Would be needed for production.

- **Add custom tools/scripts** i.e dump json so we can store each log or result in a structured file rather than raw text in a markdown.
  - ✅ **Partially adopted:** Session traces stored as JSON in `logs/sessions/`. Reflections still markdown.

- **Add an error-patterns md file** containing analysis from different error patterns to learn from avoiding.
  - ⚠️ **Not implemented as separate file:** Error patterns absorbed into `schema.md` and `examples.md` instead of dedicated file.
  - [? Was this a conscious decision, or just how it evolved? Would a dedicated error-patterns file be useful?]

- **Agents keeping a scratchpad** on their working, then having two layers of verification: 1. deterministic rules & metrics, 2. a verification agent analysing the natural language scratch-pad, process and output.
  - ✅ **Partially adopted:** Learner writes reflection logs (scratchpad-like). Improver analyzes them. No deterministic rule verification layer.

- **Citations?** If this is data analysis, then it's a matter of reverse-engineering the process to validate the steps. If the process of learning the data is made explicit with thinking, citations, and references - then going backwards should simply prove it.
  - ⚠️ **Not implemented:** Would be valuable for auditability. Learner shows work but doesn't formally cite data sources.

- System prompt the identity of who might be a person who'd need to use this dataset for analysis, then generate queries based on them without giving them knowledge of the task for the best kind of role-prompting and unbiased questions.
  - [? Did you use this technique to generate eval queries, or were queries handcrafted?]

## 3.7 Cross-Session Learning (from video research)

> minute 49: talks about how can we reuse regular workflows across different agent sessions that are serving different users to allow learning and future improvement i.e generalisable scripts that take patterns from different users?

This is exactly what I want to know more about for my work! The person in the video says it's still so relatively new so there's lots of learning to be done, but one idea is having a shared forum for lots of agents to contribute to, update, and contribute/respond.

- ✅ **Core inspiration adopted:** This is exactly what the system does — Learner logs suggestions, Improver applies them to shared knowledge files.

But then giving each agent session ability to update the forum completely is subject to noise. Maybe they add their suggestion for improvement in a log, and then logs of these problem/suggestions are what's batched and the highest leverage problems are then identified for implementing?

- ✅ **Partially adopted:** Learner writes to `logs/reflections/`, Improver reads and applies. Batching deprioritized (see 3.4).
- **Post-build reflection:** The "log → batch → apply" pattern described here is exactly right. Current system does "log → immediately apply" which is noisier but satisfies N+1.

---

# 4. Insights & Learnings

> What I discovered along the way. These shaped the final approach.
>
> **Format:** Each insight shows the pre-build thinking, then a post-build reflection on whether it held true.

## 4.1 My Approach Mirrors Cody's

I'm applying a similar step cody takes: to disambiguate the task, Cody asks clarifying questions. This is a difficult task with lots of variables, so my first stage is similarly raising these types of questions that can allow me to pin-point areas of ambiguity and clarifying them before I begin implementing. This is important to know what the trade-offs and possible decisions are in building this out.

**Post-build:** ✅ This approach paid off. The questions in Section 2 directly shaped architecture decisions. Time spent scoping → less rework during implementation.
- [? Did the Learner agent also use clarifying questions, or does it just make assumptions?]

## 4.2 Start with MVP, Not Perfect Plan

There's lots of different questions and ideas I'm having now, but instead of trying to implement the perfect plan now, I'd like to avoid using AI immediately and dig in with my own hands in building an MVP of this chatbot, and seeing how it performs out the box - what are the patterns in what it does well and where errors arise?

This will tell me what AI can do out the box, and thus whether we actually need to engineer anything on top and what if anything. **Establishing our base, then working on the highest-leverage pain points will be our strategy.**

**Post-build:** ✅ This was the right call. Key discovery: Haiku was *too good* at correctness, which forced the pivot to efficiency metrics. Wouldn't have known this without MVP testing first.
- [? What was the timeline? How long MVP testing vs. building the improvement system?]

## 4.3 The Hardest Problem: Defining Success

Defining right and wrong, what success looks like, is proving to be quite a challenging question. All of our validation and improvement of our system will rely on being able to reliably detect when and where an issue is, and how to fix it.

**Post-build:** ✅ Confirmed as the hardest problem. Solution: pivoted from "correct vs. incorrect" to "efficient vs. inefficient" when correctness saturated. → [TRADEOFFS.md](TRADEOFFS.md#evaluations-validations-and-verifications)

## 4.4 Binary Pass/Fail Isn't Enough

I realised that a lot of the time the coding agents were just good enough to be able to solve a lot of these queries. Solving or not solving is binary and doesn't give us enough information sometimes, so I thought about other differentiating factors and improvements such as latency, token context usage, cost, number of linting errors, number of csv queries made. Of course, the most important is total number of correct in say, a test suite of 50, but these intermediates are also really important.

**Post-build:** ✅ This insight became central to the evaluation system. Final metrics: tokens + tool calls. Linting errors and CSV query count not tracked (Haiku didn't produce linting errors).
- [? Were there any metrics you wish you had tracked but didn't?]

## 4.5 Structure Trade-off

Trade-off between too much structure and not enough structure. In a system where we want continuous improvement from user data, less structure is probably better, so instead of building well designed APIs, it's more about scalability - how can we make the process of integrating feedback modular and scalable?

**Post-build:** ✅ Chose "less structure" — knowledge files are freeform markdown, not structured APIs. This allowed Improver flexibility in what/how to update.
- [? In hindsight, was this the right balance? Any cases where more structure would have helped?]

## 4.6 Establish Agent Baseline First

Establish a baseline for structure: test out the agent using lots of different kinds of tools, commands, bash scripts etc. Find out what the agent likes and doesn't like: the goal is to establish what the agent you're working with is good at, and what things might be out of distribution. Working with the agent's strengths to begin with will save you time or hassle.
- Does it like CSV or SQLite?
- Does it prefer to execute bash or pre-defined code? Grep or awk?
- What kinds of styles work best for tool-calling and bash styles?
- Different sub-agent system prompts?
- Does a system using a shared forum work? Or do we need a batch system?

**Post-build:** [? Did you run these experiments? What did you learn about Haiku's preferences?]
- CSV vs SQLite: [? Which did Haiku prefer?]
- Bash vs pre-defined code: [? Observation?]
- Shared forum vs batch: Shared forum (with per-query updates) used. Batch deprioritized.

## 4.7 What I'm Keen to Build (Wishlist vs. Reality)

| Wishlist Item | Built? | Notes |
|---------------|--------|-------|
| Skills, tools, rules, knowledge files | ✅ Partial | `knowledge/` directory with schema, examples, functions |
| Sub-agents for different tasks | ✅ Partial | Learner + Improver (not full specialist architecture) |
| Evaluation suite | ✅ Yes | `evaluate.py` + `benchmark.py` |
| Error analysis agent (batch) | ⚠️ No | Per-query Improver instead of batch analysis |
| Post-query efficiency review | ✅ Yes | Learner self-reflection + Improver analysis |

**Post-build:** Most of the core vision was implemented, simplified for demo scope. The "batch error analysis" was the main casualty of the N+1 requirement.

---

# 5. Open Questions

> Questions that remained unclear, were deprioritized, or need external input.
>
> **Status:** [? Were any of these questions asked to Aymeric? Mark which were answered vs. which you proceeded without answers for.]

## 5.1 Questions for Aymeric

> *Great questions that will simplify what I should optimise for, but also demonstrate my system thinking and trade-offs.*

[? **Meta-question:** Did you get to ask these, or did you proceed with assumptions? If asked, add answers inline.]

**Scope & Scale:**
- How many users are using this system daily?
  - [? Answered? Or assumed single-user demo scope?]
- How long does this system look to be maintained for?
  - [? Answered? Or assumed take-home scope only?]
- Do you see this system as something that should be able to evolve with interchanging datasets or evolving fields, or will it only ever be used to serve this exact dataset?
  - **Assumption made:** Designed for generalization anyway (see 2.5).

**Requirements Clarification:**
- Is context/latency required to reach an answer an important metric, or is correctness the only priority for this task?
  - **Decision made:** Efficiency (tokens/tool calls) became primary metric after correctness saturated.
- How do we want to handle edge-case queries, i.e vague questions that can't deterministically infer what to do next, or about completely wrong / off-track questions?
  - **Decision made:** Learner states assumptions explicitly (see 2.6).
- How should we treat each user query: stateless, so each query to the chatbot should be treated as an isolated query, or allow complex follow-ups to earlier results in the chat?
  - [? Which did you implement? Stateless or conversational?]
- When you say 'improving the N+1th run' - do you mean this literally (improvements need to be propagated to the system with immediate feedback loop) or can this be an offline batch job that propagates a queue of proposed updates as github PRs?
  - **Interpreted literally:** Per-query updates, not batched PRs. This shaped the entire architecture.

**Design Decisions:**
- How data-set agnostic do we want to make our system? Do we see this as being a one-time set-up, or is there a standardised set-up and onboarding system we want to establish to be able to plug and play this into a new dataset?
  - **Decision made:** Dataset-agnostic by design (see 2.5).
    - i.e top level readme mentions nothing about the dataset niche - just that you're a data analysis agent, and then the assets of this particular repo are modularised components that are generated and improved as the agent works.
    - Kind of like how we random init a neural network and then it will auto converge on the best solutions.
    - But then again, we shouldn't rely on pure random inits. Instead, we could define skills like /init-set-up or /generate-sysprompt or /batch-and-update-docs.
- How do we version this? Each update to the docs represents a new version of our system. Meaning past data points and performances will be outdated.
  - **Decision made:** Git history is versioning. Agent version tracked via commit hash in execution traces.
- How big a priority is put on how scalable the solution is, i.e syncing - multiple sessions adding to a joined database of sessions. Redis?
  - **Decision made:** Single-session demo scope. Redis/multi-session not implemented.
- Is the cost or latency of our system something we need to consider, or is its robustness the most important thing?
  - **Decision made:** Chose Haiku for cost/speed, Opus for quality where it matters.
    - Thinking of using a jury of our best models for feedback (gpt5.2, opus4.5, gemini3pro) because it's more expensive building the wrong foundations and having to restart than to build the right thing.
      - ⚠️ **Deprioritized:** Single-model (Opus) evaluation used.

**Process:**
- There are two ways I can think of building this system: the ideal way (self-consistent continual learning system that has agents that verify and evaluate past chains and update itself automatically), and then there are the kind where a human in the loop / user approves improvements/suggestions. Which is most important?
  - **Decision made:** Automatic improvement (no human approval loop). Improver applies changes directly.
- I am able to reverse-engineer parts of cody's internal documentation structure by asking it about the docs made available to it. Before asking it anything more specific, is this considered cheating?
  - [? Did you get an answer to this?]
- Aymeric and Osman told me Cody helped them build itself - would it be considered cheating if I used Cody as the AI tool to help me build this?
  - [? Did you get an answer / did you use Cody?]

## 5.2 Unresolved Technical Questions

> **Post-build status:** Most of these were descoped for demo. Marked as future considerations.

- **Microservice architecture?** Osman mentioned they believe entirely on scalability and statelessness and microservice architecture is a big part in making it all work. Wasn't sure what it meant or how though. Worth it or overkill here?
  - ⚠️ **Descoped:** Overkill for demo. Single-process Python script sufficient.

- **Keep skills, assets, things built** and contributed from usage iteration in a submodule or separate database that's synchronous.
  - ⚠️ **Descoped:** Knowledge files live in main repo. No submodule/database separation.

- **Usage from different sessions** need to be able to sync on a single source.
  - ⚠️ **Descoped:** Single-session assumption. Multi-session sync not implemented.

- **Keeping design of markdown knowledge as general purpose as possible** - instead of mapping out the perfect structure of the dataset as manual steps to build and initiate the system, make the context/prompts/knowledge markdowns the building blocks to be able to map it out itself.
  - ✅ **Adopted:** Knowledge files are freeform markdown. Improver evolves them based on usage.

- **Asking a claude code agent with zero context** on the dataset, dataset questions to see how it reasons step-by-step and how it gathers what it needs can give you an idea of what its preferences are.
  - [? Did you try this? Any learnings about zero-context agent behavior?]

---

# 6. Talking Points

> Key points to highlight when discussing this work.

[? **Note:** This section duplicates content from Section 4 (Insights). Options:
1. **Delete** — Content already lives in Section 4 with post-build reflections
2. **Keep as interview prep** — Distill into bullet points for quick reference
3. **Expand** — Add post-build talking points about what was learned

Which would you prefer?]

---

**Pre-build talking points (from Section 4):**

1. **I'm applying a similar step Cody takes:** to disambiguate the task, Cody asks clarifying questions. Similarly, I'm doing this as well as I scope out the task. This is a difficult task with lots of variables, so my first stage is similarly raising these types of questions that can allow me to pin-point areas of ambiguity and clarifying them before I begin implementing.
   - *See also: Section 4.1*

2. **Binary pass/fail isn't enough information:** I realised that a lot of the time the coding agents were just good enough to be able to solve a lot of these queries. Solving or not solving is binary and doesn't give us enough information sometimes, so I thought about other differentiating factors and improvements such as latency, token context usage, cost, number of linting errors, number of csv queries made.
   - *See also: Section 4.4*

[? **Post-build talking points to add?** Things like:
- "The hardest part was defining success metrics"
- "N+1 requirement forced per-query updates vs. batching"
- "Haiku was too good — had to pivot to efficiency metrics"
- Other key learnings?]
