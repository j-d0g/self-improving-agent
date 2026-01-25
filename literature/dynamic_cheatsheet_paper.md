# Dynamic Cheatsheet: Test-Time Learning with Adaptive Memory

**Mirac Suzgun**<sup>1</sup>, **Mert Yuksekgonul**<sup>1</sup>, **Federico Bianchi**<sup>2</sup>, **Dan Jurafsky**<sup>1</sup>, **James Zou**<sup>1,2</sup>

<sup>1</sup> Stanford University  <sup>2</sup> Together AI

Correspondence: msuzgun@stanford.edu and jamesz@stanford.edu

arXiv:2504.07952v1 [cs.LG] 10 Apr 2025

**Code & Data**: http://github.com/suzgunmirac/dynamic-cheatsheet

---

## Abstract

Despite their impressive performance on complex tasks, current language models (LMs) typically operate in a vacuum: Each input query is processed separately, without retaining insights from previous attempts. Here, we present **Dynamic Cheatsheet (DC)**, a lightweight framework that endows a black-box LM with a persistent, evolving memory. Rather than repeatedly re-discovering or re-committing the same solutions and mistakes, DC enables models to store and reuse accumulated strategies, code snippets, and general problem-solving insights at inference time. This test-time learning enhances performance substantially across a range of tasks without needing explicit ground-truth labels or human feedback.

### Key Results

- **Claude 3.5 Sonnet's accuracy more than doubled on AIME math exams** once it began retaining algebraic insights across questions
- **GPT-4o's success rate on the Game of 24 puzzle increased from about 10% to 99%** after the model discovered and reused a Python-based solution
- In tasks prone to arithmetic mistakes, such as balancing equations, **DC enabled GPT-4o and Claude to reach near-perfect accuracy** by recalling previously validated code, whereas their baselines stagnated around 50%
- Claude achieved a **9% improvement in GPQA-Diamond** and an **8% boost on MMLU-Pro Engineering and Physics** problems

Crucially, DC's memory is self-curated, focusing on concise, transferable snippets rather than entire transcripts, thereby facilitating meta-learning and avoiding context ballooning. Unlike fine-tuning or static retrieval methods, DC adapts LMs' problem-solving skills on the fly, without modifying their underlying parameters.

---

## 1. Introduction

Modern large language models (LLMs) can tackle complex reasoning tasks, answer various questions, and generate extensive texts. Yet they still suffer from one critical limitation: **once deployed, these models are fixed prior to deployment and typically retain no explicit or implicit memory of past questions, successes, or mistakes during inference**. They approach each new problem *de novo*, often re-deriving the same insights—and re-committing the same errors. In contrast, human cognition stands on a foundation of incremental learning, continuously internalizing new experiences and solutions into a persistent mental model.

### The DC Framework

Dynamic Cheatsheet (DC) is a simple and intuitive framework that endows black-box LLMs with a persistent, evolving memory at inference time. Rather than:
- Fine-tuning weights (through dynamic evaluation or domain adaptation)
- Retrieving facts from a massive static corpus (as in traditional RAG systems)

DC dynamically curates a compact library of reusable strategies, solution sketches, and code snippets. Either before or after each query, DC enables the system to decide which lessons to store, what to discard, and how to refine existing entries—thus effectively "learning" from successes and failures.

### Workflow Overview (DC-Cu)

1. When presented with a new query, the LM first consults its external memory
2. It proposes a solution by combining retrieved insights with its own internal reasoning
3. Upon generating an answer, it proceeds to a **curation phase** that updates the memory:
   - If the approach seems correct/useful, DC codifies it for future use
   - If an error surfaces, DC may revise or prune faulty heuristics

This happens **without gradient-based parameter updates**, so computational overhead remains modest, and compatibility with black-box APIs (e.g., GPT-4 or Claude) is fully preserved.

### Key Observations

- **Game of 24**: GPT-4o's baseline (10%) increased to 99% under DC. Early in the test sequence, the model discovered a Python brute-force solver, stored it, and reused it for subsequent queries
- **Math Equation Balancer**: GPT-4o and Claude soared from 45-50% to 98-100% by "recalling" a code-based approach
- **Smaller models** (GPT-4o-mini) benefit from DC in limited amounts—they generate too few correct solutions initially, leaving the memory populated with flawed strategies

DC differs from naive "append the entire conversation history" approaches. Under DC, memory is carefully curated, focusing on succinct, useful, and transferable knowledge over raw transcripts.

---

## 2. Dynamic Cheatsheet (DC) Methodology

DC includes an external, non-parametric memory that evolves in tandem with the LLM's inference process. Rather than fine-tuning the underlying weights, DC tracks successes and failures of the model at test time, then selectively stores heuristics, strategies, or short textual artifacts that can guide the LLM in future instances.

### 2.1 DC: Building Blocks and Iterative Loop

The DC framework consists of two core modules: **generation** and **curation**. Both can operate on top of the same LM (prompted differently) or on separate LMs.

#### 2.1.1 Solution Generation with Memory

Consider a sequence of inputs (x₁, x₂, ..., xₙ), where each xᵢ ~ D_test indicates a new query sampled from the same distribution. At the i-th step, the model is provided with both the new query xᵢ and the current memory state Mᵢ:

```
ỹᵢ = Gen(xᵢ, Mᵢ)
```

Here, ỹᵢ is the candidate solution produced by the model. Mᵢ helps condition the model to reuse or adapt previously stored solutions, insights, techniques, or heuristics.

#### 2.1.2 Memory Curation Step

After the generator produces its answer ỹᵢ to xᵢ, the curator updates the memory:

```
Mᵢ₊₁ = Cur(Mᵢ, xᵢ, ỹᵢ)
```

During memory curation, Cur considers:
1. **Usefulness and generalizability** of the newly produced answer
2. **Refinement or removal** of existing memory entries
3. **Clarity and compactness** of the entire memory

The curator does not have access to ground-truth labels; it must assess correctness and efficiency by itself.

We refer to this version as **DC-Cu** (DC-Cumulative). Under DC-Cu, the system first performs solution generation based on current memory, then updates the memory by cumulatively expanding and refining items.

### 2.2 DC with Retrieval & Synthesis (DC-RS)

DC-Cu has two potential drawbacks:
1. It updates memory *after* processing a query, rather than refining it *before* generating a response
2. It does not store or revisit past input-output pairs unless explicitly retained

**DC-RS** addresses these by:
- Modifying the sequence of memory updates
- Introducing a retrieval mechanism (Retr) into the curation process

DC-RS workflow:

```
Rᵢ = Retr(xᵢ, {(xⱼ, ỹⱼ)}ⱼ<ᵢ, k)    # Retrieval
Mᵢ = Cur(Mᵢ₋₁, xᵢ, Rᵢ)            # Memory curation
ỹᵢ = Gen(xᵢ, Mᵢ)                   # Solution generation
```

### 2.3 Baselines

| Baseline | Description |
|----------|-------------|
| **BL (Baseline prompting)** | Plain "vanilla" prompting without any iterative memory or retrieval |
| **DC-∅ (Empty memory)** | DC baseline that always keeps memory effectively empty—isolates the effect of memory curation |
| **FH (Full-History Appending)** | Naively appends entire conversation history without curation or truncation |
| **DR (Dynamic Retrieval)** | Uses retrieval but no curation—retrieves similar past interactions and pastes them verbatim |

---

## 3. Experimental Setup

### 3.1 Tasks and Datasets

We focus on challenging tasks where contemporary LLMs still face limitations, prioritizing tasks that demand multi-step reasoning, heuristic search, strategic adaptation, and cumulative learning.

#### (a) AIME 2020-2025 Exam Questions
The American Invitational Mathematics Examination (AIME) is a prestigious high-school competition featuring complex problems across algebra, combinatorics, number theory, geometry, and probability.
- **AIME 2024**: 30 questions
- **AIME 2025**: 30 questions
- **AIME 2020-2024**: 133 questions

#### (b) GPQA-Diamond
A high-quality, difficult subset of the Graduate-Level Google-Proof Q&A benchmark containing 198 expert-validated questions across natural sciences (biology, chemistry, physics).

#### (c) Game of 24
A heuristic-driven arithmetic challenge where the objective is to form an expression that evaluates to 24 using four given numbers exactly once. Example: "7 7 8 11" → "8*(7+7-11)". We use 100 examples.

#### (d) Math Equation Balancer
Requires the model to complete equations by inserting appropriate operators. Example: "1 ? 2 ? 3 = 6" → "1 + 2 + 3 = 6" or "1 * 2 * 3 = 6". 250 arithmetic expressions.

#### (e) MMLU-Pro (Engineering and Physics)
Professional-level subset of MMLU focused on physics (250 questions) and engineering (250 questions).

### 3.2 Language Models

- **GPT-4o** and **Claude 3.5 Sonnet** (state-of-the-art)
- **GPT-4o-mini** and **Claude 3.5 Haiku** (smaller counterparts)
- **DeepSeek R1** (reasoning-intensive)

### 3.3 Evaluation Protocol

All models format final answers in XML-style tags:
```xml
<answer>
(final answer)
</answer>
```

#### Accuracy Metrics

| Metric | Description | Applied To |
|--------|-------------|------------|
| **Soft Match (SM)** | Correct if matches ground truth ignoring minor formatting differences | GPQA-Diamond, MMLU-Pro |
| **Functionally Correct (FC)** | Correct if output satisfies task-specific constraints | Game of 24, Math Equation Balancer, AIME |

---

## 4. Main Results

### 4.1 DC enables test-time learning and reduces repetitive errors

**Game of 24 Example**: GPT-4o's baseline accuracy was just 10%. Under DC-RS, performance increased to **99%**. Early in the task sequence, GPT-4o discovered a Python-based brute-force method, encoded it into memory, and consistently retrieved it for subsequent examples.

The performance under DC-∅ (19%) highlights the impact of memory curation. The large gap between 19% (DC-∅) and 99% (DC-RS) confirms that effective memory usage is the main driver of GPT-4o's transformation.

In contrast, Claude 3.5 Sonnet showed marginal gain (12% to 14%), as it did not internalize a generalized approach but continued to rely on manual arithmetic solutions.

### 4.2 Performance Comparison Table

| Task | Claude 3.5 Sonnet | | | | | GPT-4o | | | | |
|------|-------------------|---|---|---|---|--------|---|---|---|---|
| | BL | DC-∅ | DR | DC-Cu | DC-RS | BL | DC-∅ | DR | DC-Cu | DC-RS |
| **AIME 2024** | 23.3 | 36.7 | 43.3 | **50.0** | 46.7 | 20.0 | 36.7 | 26.7 | 36.7 | **40.0** |
| **AIME 2025** | 6.7 | 23.3 | 23.3 | **36.7** | 30.0 | 6.7 | 10.0 | 10.0 | 16.7 | **20.0** |
| **AIME 2020-24** | 6.7 | 30.1 | 39.1 | 38.4 | **40.6** | 9.8 | 24.1 | 24.1 | 20.3 | **24.8** |
| **Game of 24** | 12.0 | 10.0 | 11.0 | **14.0** | **14.0** | 10.0 | 19.0 | 6.0 | 93.0 | **99.0** |
| **GPQA Diamond** | 59.6 | 60.1 | 63.6 | 61.1 | **68.7** | **57.1** | **57.1** | 55.1 | 58.1 | **57.1** |
| **Math Eqn. Balancer** | 44.8 | 56.4 | 60.4 | **100** | 97.8 | 50.0 | 88.0 | **100** | **100** | 99.2 |
| **MMLU Pro Eng.** | 61.2 | 57.2 | 65.2 | 66.8 | **67.6** | **53.2** | 51.6 | 48.8 | 44.0 | 51.2 |
| **MMLU Pro Physics** | 74.0 | 75.6 | 80.4 | 77.6 | **82.0** | **75.6** | 70.8 | **75.6** | 70.4 | 75.2 |

### 4.3 Memory curation provides gains over full-history-appending

| Task | Claude 3.5 Sonnet | | | GPT-4o | | |
|------|-------------------|---|---|--------|---|---|
| | BL | FH | DC-Cu | BL | FH | DC-RS |
| **AIME 2024** | 23.3 | 26.7 | **50.0** | 20.0 | 13.3 | **40.0** |
| **AIME 2025** | 6.7 | 6.7 | **36.7** | 6.7 | 3.3 | **20.0** |

Excessive uncurated input-output pairs can overwhelm the model's context window, dilute crucial insights, and significantly increase inference costs.

### 4.4 DC fosters efficient tool usage / code generation

A successful behavior under DC is the LLMs' inclination toward code generation for computationally intensive tasks. GPT-4o's near-complete reliance on Python scripts for Game of 24 exemplifies this shift—it recognized that code-based brute force is more systematic than manual arithmetic.

### 4.5 Model scale and capacity impact DC effectiveness

| Task | Claude 3.5 Haiku | | | | GPT-4o-mini | | | |
|------|------------------|---|---|---|-------------|---|---|---|
| | BL | DC-∅ | DC-Cu | DC-RS | BL | DC-∅ | DC-Cu | DC-RS |
| **AIME 2024** | 10.0 | 26.7 | **36.7** | 30.0 | 16.7 | **20.0** | 13.3 | 13.3 |
| **AIME 2025** | 0.0 | **13.3** | **13.3** | 10.0 | 10.0 | **13.3** | **13.3** | **16.7** |
| **GPQA-Diamond** | 43.4 | 41.9 | 43.7 | **49.0** | **34.3** | **34.3** | 33.8 | 32.3 |

**Two drawbacks of smaller models under DC:**

1. **Generative competence**: For DC to be effective, the base model must produce correct solutions with sufficient frequency. Smaller models generate correct solutions less reliably, leading to a sparse or low-quality memory repository.

2. **Contextual and memory curation limitations**: Smaller models struggle with long-context understanding/generation and memory retrieval, leading to inefficient or irrelevant memory usage.

### 4.6 Test-time task similarity and example ordering can amplify DC's impact

DC thrives when test examples share structural similarities. In both Game of 24 and Math Equation Balancer, once GPT-4o identified an efficient solution, it reused it consistently for subsequent tasks. This suggests that **curriculum-style learning**, where simpler or archetypal problems are presented first, may potentially bootstrap performance.

---

## 5. Additional Analyses and Discussions

### Reasoning and Information Efficiency

DC reduces the need to "reinvent the wheel" for each query. By encoding and reusing well-established techniques, models can bypass repeated rediscovery of the same strategies, significantly cutting down reasoning overhead and token usage in subsequent queries.

### DC Performs Better Than Majority Voting (MV)

| Task | Claude 3.5 Sonnet | | | | |
|------|-------------------|---|---|---|---|
| | BL | MV(BL) | DC-∅ | MV(DC-∅) | DC-Cu |
| **AIME 2024** | 23.3 | 23.3 | 36.7 | 33.3 | **50.0** |
| **AIME 2025** | 6.7 | 6.7 | 23.3 | 23.3 | **36.7** |

Unlike MV, which passively aggregates outputs, DC actively refines knowledge over time, eliminating errors and improving solution quality.

### Clustering of Errors and Corrections

Errors and their corrections often cluster in latent embedding space. Once a model acquires a high-quality heuristic for a cluster of related queries, it can apply this knowledge to tightly embedded neighbors. However, faulty heuristics that slip into memory can be equally amplified—careful curation is required.

### Transferability of Memory Content Across Models

Larger models can sometimes produce higher-quality strategies that could benefit smaller models if transferred. However, if a smaller model lacks the generative capacity to interpret or refine those strategies correctly, performance can stall or degrade.

### Long-context Generation vs. Understanding

Most large LLMs excel at processing lengthy inputs but struggle to generate comparably long and well-organized outputs. DC's memory curation can demand precise reproduction or modification of prior knowledge. We observed instances where the model merely references or abbreviates existing memory instead of explicitly rewriting it.

### Retrieval Bottlenecks and Noise

While retrieval-based variants (DC-RS) can substantially improve accuracy, poorly filtered retrieval can introduce confusion, particularly with highly diverse or loosely related queries.

### Hierarchical and Modular Memory

As deployments scale, specialized domains may benefit from subdividing or hierarchically organizing memory—maintaining separate curated memories for topics like combinatorics or physics.

### Time and Token Complexity

Although DC requires memory curation after each query, it optimizes efficiency over time by reducing redundant computation. On AIME 2024, Claude Sonnet averaged:
- **BL**: 370 tokens
- **DC-∅**: 494 tokens
- **DC-RS**: 1035 tokens
- **DC-Cu**: 1831 tokens

### Smaller Models and R1 Experiments

Smaller models (GPT-4o-mini) show limited gains under DC. Additional experiments with "R1" models (DeepSeek R1, o1) showed minimal or inconsistent improvements—their solutions were far too verbose and long.

---

## Appendix A: Background & Related Work

### A.1 Test-time Learning (Online Learning)

Test-time learning encompasses methods where a model updates its predictions by incorporating information seen during inference, without full-scale offline finetuning. In computer vision, methods like test-time training mitigate domain shifts by optimizing a self-supervised loss on incoming data. In NLP, "dynamic evaluation" updates a language model with gradient steps on test-time data.

However, directly updating LM weights at test time is computationally expensive and requires parameter modification capability. For black-box APIs, such an approach is infeasible. DC allows an LM to iteratively record solutions in an external memory component, avoiding weight updates entirely.

Related reflexive approaches:
- **Reflexion**: Feedback loops to correct mistakes
- **Self-Refine**: Iterative refinement with self-feedback
- **TextGrad**: "Textual gradients" for improvement
- **Meta-Prompting**: Task-agnostic scaffolding

DC differs by focusing on storing generalizable heuristics that can be repeatedly retrieved and applied across tasks.

### A.2 Test-time Compute and Reasoning

Contemporary LLMs exhibit substantial improvements with additional inference-time strategies:
- Chain-of-thought prompting
- Tree-of-thought expansions
- Minimum Bayes risk decoding
- Majority-vote sampling

However, these expansions are typically ephemeral—subsequent tasks don't benefit from heavy compute spent earlier. DC aims to reduce repeated overhead by building memory that persists from one query to the next, effectively amortizing the cost of initial reflection across future tasks.

### A.3 Memory-augmented Generation and Reasoning

Modern retrieval-augmented LLM approaches consult external document corpora to improve factuality, but the retrieval corpus is almost always fixed prior to inference.

Related work on storing reasoning processes:
- **Thought-Retriever**: Logs chain-of-thought from past queries
- **Buffer-of-Thoughts (BoT)**: Distills high-level "thought templates"
- **A-MEM**: Memory mechanisms capturing user feedback on errors

DC emphasizes selectively storing the most relevant insights and heuristics, avoiding naive accumulation of full raw transcripts. DC remains fully external and training-free—"plug-and-play" with off-the-shelf models.

---

## Appendix B: Example Memory Contents

### GPT-4o's Memory After Game of 24 (DC-RS)

```xml
<memory_item>
<description>
Game 24 Solver Strategy: Solve the 24 Game by systematically testing combinations
of four numbers with arithmetic operations (+, -, *, /) and parentheses to achieve
a result of 24. Each number must be used exactly once.
</description>
<example>
Steps:
1. Understand the Problem:
   - Input: Four integers
   - Goal: Combine using arithmetic operations and parentheses to evaluate to 24
   - Constraints: Each number must be used exactly once

2. Approach:
   - Use brute force or systematic trial-and-error
   - Prioritize operations that simplify the problem
   - Check edge cases (repeated numbers, large/small values)

Python Code for Automation:
from itertools import permutations, product

def solve_24(numbers):
    ops = ['+', '-', '*', '/']
    for nums in permutations(numbers):
        for oprs in product(ops, repeat=3):
            expressions = [
                f"(({nums[0]} {oprs[0]} {nums[1]}) {oprs[1]} {nums[2]}) {oprs[2]} {nums[3]}",
                # ... additional expression patterns
            ]
            for expr in expressions:
                try:
                    if abs(eval(expr) - 24) < 1e-6:
                        return expr
                except ZeroDivisionError:
                    continue
    return "No solution"
</example>
</memory_item>
Count: 99
```

### Claude 3.5 Sonnet's Memory After AIME 2024 (DC-Cu)

```xml
<memory_item>
<description>
Systematic Problem Analysis Framework (Reference: Q1-Q20)
For complex mathematical problems:
1. State problem requirements clearly
2. List key observations and theorems applicable
3. Identify patterns and relationships
4. Break into manageable sub-problems
5. Verify against examples
6. Consider computational approach when analytical solution is complex
7. For grid problems, analyze movement patterns and symmetries
8. For combinatorial problems, use appropriate counting techniques
9. Implement verification code when possible
10. Consider edge cases and constraints
11. For grid coloring problems, consider row/column patterns
</description>
<example>
Example application:
1. Requirements: list all given conditions
2. Observations: identify applicable theorems
3. Patterns: look for structural relationships
4. Sub-problems: break into steps
5. Verification: test against examples
6. Implementation: use Python for verification
</example>
</memory_item>
Count: 20
```

---

## References

[1] Amari, S.-I. Natural gradient works efficiently in learning. *Neural computation*, 10(2):251–276, 1998.

[2] Asai, A., et al. Self-rag: Learning to retrieve, generate, and critique through self-reflection. In *ICLR*, 2023.

[3] Bengio, Y., et al. Curriculum learning. In *ICML*, pp. 41–48, 2009.

[4] Besta, M., et al. Graph of thoughts: Solving elaborate problems with large language models. In *AAAI*, volume 38, pp. 17682–17690, 2024.

[5] Borgeaud, S., et al. Improving language models by retrieving from trillions of tokens. In *ICML*, pp. 2206–2240. PMLR, 2022.

[6] Cobbe, K., et al. Training verifiers to solve math word problems. *arXiv preprint arXiv:2110.14168*, 2021.

[7] Feng, T., et al. Thought-retriever: Don't just retrieve raw data, retrieve thoughts, 2024.

[8] Graves, A., et al. Neural turing machines. *arXiv preprint arXiv:1410.5401*, 2014.

[9] Guu, K., et al. Retrieval augmented language model pre-training. In *ICML*, pp. 3929–3938. PMLR, 2020.

[10] Karpukhin, V., et al. Dense passage retrieval for open-domain question answering. In *EMNLP*, pp. 6769–6781, 2020.

[11] Khandelwal, U., et al. Generalization through memorization: Nearest neighbor language models. In *ICLR*, 2020.

[12] Kojima, T., et al. Large language models are zero-shot reasoners. *NeurIPS*, 35:22199–22213, 2022.

[13] Krause, B., et al. Dynamic evaluation of transformer language models. *arXiv preprint arXiv:1904.08378*, 2019.

[14] Lewis, P., et al. Retrieval-augmented generation for knowledge-intensive nlp tasks. *NeurIPS*, 33:9459–9474, 2020.

[15] Liu, N. F., et al. Lost in the middle: How language models use long contexts. *Transactions of the ACL*, 12:157–173, 2024.

[16] Madaan, A., et al. Self-refine: Iterative refinement with self-feedback. *NeurIPS*, 36:46534–46594, 2023.

[17] Rein, D., et al. GPQA: A graduate-level google-proof q&a benchmark. In *First Conference on Language Modeling*, 2024.

[18] Shinn, N., et al. Reflexion: Language agents with verbal reinforcement learning. *NeurIPS*, 36:8634–8652, 2023.

[19] Shi, F., et al. Language models are multilingual chain-of-thought reasoners. In *ICLR*, 2023.

[20] Sun, Y., et al. Test-time training with self-supervision for generalization under distribution shifts. In *ICML*, pp. 9229–9248. PMLR, 2020.

[21] Suzgun, M. and Kalai, A. T. Meta-prompting: Enhancing language models with task-agnostic scaffolding. *arXiv preprint arXiv:2401.12954*, 2024.

[22] Suzgun, M., et al. Challenging big-bench tasks and whether chain-of-thought can solve them. In *Findings of ACL*, pp. 13003–13051, 2023.

[23] Wang, X., et al. Self-consistency improves chain of thought reasoning in language models. In *ICLR*, 2023.

[24] Wang, Y., et al. MMLU-pro: A more robust and challenging multi-task language understanding benchmark. In *NeurIPS Datasets and Benchmarks Track*, 2024.

[25] Wei, J., et al. Chain-of-thought prompting elicits reasoning in large language models. *NeurIPS*, 35:24824–24837, 2022.

[26] Weston, J., et al. Memory networks. *arXiv preprint arXiv:1410.3916*, 2014.

[27] Yang, L., et al. Buffer of thoughts: Thought-augmented reasoning with large language models. *NeurIPS*, 37:113519–113544, 2025.

[28] Yao, S., et al. Tree of Thoughts: Deliberate problem solving with large language models, 2023.

[29] Yuksekgonul, M., et al. Optimizing generative ai by backpropagating language model feedback. *Nature*, 639:609–616, 2025.

[30] Zelikman, E., et al. Star: Bootstrapping reasoning with reasoning. *NeurIPS*, 35:15476–15488, 2022.

[31] Zhang, T., et al. RAFT: Adapting language model to domain specific RAG. In *First Conference on Language Modeling*, 2024.

---

## Acknowledgments

We thank Batu El, Sabri Eyuboglu, Tayfun Gur, Emily Shen, Jake Silberg, Elana Simon, and Kyle Swanson for their helpful comments and suggestions. We also thank the members of the James Zou Lab at Stanford for their feedback in the early stages of this project. Suzgun gratefully acknowledges the support of an HAI-SAP Fellowship.
