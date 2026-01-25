# Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models

**Qizheng Zhang**<sup>1*</sup>, **Changran Hu**<sup>2*</sup>, **Shubhangi Upasani**<sup>2</sup>, **Boyuan Ma**<sup>2</sup>, **Fenglu Hong**<sup>2</sup>, **Vamsidhar Kamanuru**<sup>2</sup>, **Jay Rainton**<sup>2</sup>, **Chen Wu**<sup>2</sup>, **Mengmeng Ji**<sup>2</sup>, **Hanchen Li**<sup>3</sup>, **Urmish Thakker**<sup>2</sup>, **James Zou**<sup>1</sup>, **Kunle Olukotun**<sup>1</sup>

<sup>1</sup> Stanford University  <sup>2</sup> SambaNova Systems, Inc.  <sup>3</sup> UC Berkeley
\* equal contribution

📧 qizhengz@stanford.edu, changran.hu@sambanovasystems.com

arXiv:2510.04618v1 [cs.LG] 6 Oct 2025

---

## Abstract

Large language model (LLM) applications such as agents and domain-specific reasoning increasingly rely on *context adaptation*—modifying inputs with instructions, strategies, or evidence, rather than weight updates. Prior approaches improve usability but often suffer from **brevity bias**, which drops domain insights for concise summaries, and from **context collapse**, where iterative rewriting erodes details over time. Building on the adaptive memory introduced by Dynamic Cheatsheet, we introduce **ACE (Agentic Context Engineering)**, a framework that treats contexts as evolving playbooks that accumulate, refine, and organize strategies through a modular process of generation, reflection, and curation. ACE prevents collapse with structured, incremental updates that preserve detailed knowledge and scale with long-context models. Across agent and domain-specific benchmarks, ACE optimizes contexts both offline (e.g., system prompts) and online (e.g., agent memory), consistently outperforming strong baselines: **+10.6% on agents** and **+8.6% on finance**, while significantly reducing adaptation latency and rollout cost. Notably, ACE could adapt effectively without labeled supervision and instead by leveraging natural execution feedback. On the AppWorld leaderboard, ACE matches the top-ranked production-level agent on the overall average and surpasses it on the harder test-challenge split, despite using a smaller open-source model. These results show that comprehensive, evolving contexts enable scalable, efficient, and self-improving LLM systems with low overhead.

---

## 1 Introduction

Modern AI applications based on large language models (LLMs), such as LLM agents [49, 52] and compound AI systems [55], increasingly depend on *context adaptation*. Instead of modifying model weights, context adaptation improves performance after model training by incorporating clarified instructions, structured reasoning steps, or domain-specific input formats directly into the model's inputs. Contexts underpin many AI system components, including system prompts that guide downstream tasks [4, 36], memory that carries past facts and experiences [41, 48], and factual evidence that reduces hallucination and supplements knowledge [6].

Adapting through contexts rather than weights offers several key advantages. Contexts are interpretable and explainable for users and developers [45, 47], allow rapid integration of new knowledge at runtime [7, 27], and can be shared across models or modules in a compound system [23]. Meanwhile, advances in long-context LLMs [39] and context-efficient inference such as KV cache reuse [17, 51] are making context-based approaches increasingly practical for deployment. As a result, context adaptation is emerging as a central paradigm for building capable, scalable, and self-improving AI systems.

Despite this progress, existing approaches to context adaptation face two key limitations:

1. **Brevity bias**: many prompt optimizers prioritize concise, broadly applicable instructions over comprehensive accumulation. For example, GEPA [4] highlights brevity as a strength, but such abstraction can omit domain-specific heuristics, tool-use guidelines, or common failure modes that matter in practice [16].

2. **Context collapse**: methods that rely on monolithic rewriting by an LLM often degrade into shorter, less informative summaries over time, causing sharp performance declines (Figure 2).

As applications such as agents and knowledge-intensive reasoning demand greater reliability, recent work has shifted toward saturating contexts with abundant, potentially useful information [11, 12, 22], enabled by advances in long-context LLMs [34, 39]. **We argue that contexts should function not as concise summaries, but as comprehensive, evolving playbooks—detailed, inclusive, and rich with domain insights.** Unlike humans, who often benefit from concise generalization, LLMs are more effective when provided with long, detailed contexts and can distill relevance autonomously [22, 31, 41].

To address these limitations, we introduce **ACE (Agentic Context Engineering)**, a framework for comprehensive context adaptation in both offline settings (e.g., system prompt optimization) and online settings (e.g., test-time memory adaptation). Rather than compressing contexts into distilled summaries, ACE treats them as evolving playbooks that accumulate and organize strategies over time. Building on the agentic architecture of Dynamic Cheatsheet [41], ACE incorporates a modular workflow of generation, reflection, and curation, while adding structured, incremental updates guided by a **grow-and-refine** principle.

### Key Findings

- **ACE consistently outperforms strong baselines**, yielding average gains of 10.6% on agents and 8.6% on domain-specific benchmarks, across both offline and online adaptation settings.

- **ACE is able to construct effective contexts without labeled supervision**, instead leveraging execution feedback and environment signals—key ingredients for self-improving LLMs and agents.

- **On the AppWorld benchmark leaderboard** [5], ACE matches the top-ranked production-level agent IBM-CUGA [35] (powered by GPT-4.1) on average and surpasses it on the harder test-challenge split, while using a smaller open-source model (DeepSeek-V3.1).

- **ACE requires significantly fewer rollouts and lower dollar costs**, and achieves 86.9% lower adaptation latency (on average) than existing adaptive methods.

---

## 2 Background and Motivation

### 2.1 Context Adaptation

Context adaptation (or context engineering) refers to methods that improve model behavior by constructing or modifying inputs to an LLM, rather than altering its weights. The current state of the art leverages natural language feedback [4, 40, 54]. Representative methods include:

- **Reflexion** [40]: reflects on failures to improve agent planning
- **TextGrad** [54]: optimizes prompts via gradient-like textual feedback
- **GEPA** [4]: refines prompts iteratively based on execution traces
- **Dynamic Cheatsheet** [41]: constructs an external memory that accumulates strategies and lessons from past successes and failures during inference

### 2.2 Limitations of Existing Context Adaptation Methods

#### The Brevity Bias

A recurring limitation of context adaptation methods is brevity bias: the tendency of optimization to collapse toward short, generic prompts. Gao et al. [16] document this effect in prompt optimization for test generation, where iterative methods repeatedly produced near-identical instructions (e.g., "Create unit tests to ensure methods behave as expected"), sacrificing diversity and omitting domain-specific detail.

#### Context Collapse

In a case study on the AppWorld benchmark [43], we observe a phenomenon we call **context collapse**, which arises when an LLM is tasked with fully rewriting the accumulated context at each adaptation step. As the context grows large, the model tends to compress it into much shorter, less informative summaries, causing a dramatic loss of information. For instance, at step 60 the context contained 18,282 tokens and achieved an accuracy of 66.7, but at the very next step it collapsed to just 122 tokens, with accuracy dropping to 57.1—worse than the baseline accuracy of 63.7 without adaptation.

---

## 3 Agentic Context Engineering (ACE)

We present ACE (Agentic Context Engineering), a framework for scalable and efficient context adaptation in both offline (e.g., system prompt optimization) and online (e.g., test-time memory adaptation) scenarios. Instead of condensing knowledge into terse summaries or static instructions, ACE treats contexts as **evolving playbooks** that continuously accumulate, refine, and organize strategies over time.

### Architecture

ACE introduces a structured division of labor across three roles:

1. **Generator**: produces reasoning trajectories
2. **Reflector**: distills concrete insights from successes and errors
3. **Curator**: integrates these insights into structured context updates

This mirrors how humans learn—experimenting, reflecting, and consolidating—while avoiding the bottleneck of overloading a single model with all responsibilities.

### Key Innovations

1. **Dedicated Reflector** that separates evaluation and insight extraction from curation, improving context quality and downstream performance (§4.5)

2. **Incremental delta updates** (§3.1) that replace costly monolithic rewrites with localized edits, reducing both latency and compute cost (§4.6)

3. **Grow-and-refine mechanism** (§3.2) that balances steady context expansion with redundancy control

### 3.1 Incremental Delta Updates

A core design principle of ACE is to represent context as a collection of **structured, itemized bullets**, rather than a single monolithic prompt. Each bullet consists of:

1. **Metadata**: a unique identifier and counters tracking how often it was marked helpful or harmful
2. **Content**: a small unit such as a reusable strategy, domain concept, or common failure mode

This itemized design enables three key properties:
- **Localization**: only the relevant bullets are updated
- **Fine-grained retrieval**: the Generator can focus on the most pertinent knowledge
- **Incremental adaptation**: efficient merging, pruning, and de-duplication during inference

### 3.2 Grow-and-Refine

Beyond incremental growth, ACE ensures that contexts remain compact and relevant through periodic or lazy refinement. In grow-and-refine:
- Bullets with new identifiers are appended
- Existing bullets are updated in place (e.g., incrementing counters)
- A de-duplication step prunes redundancy by comparing bullets via semantic embeddings

---

## 4 Results

### Summary

- **Enabling High-Performance, Self-Improving Agents**: ACE boosts accuracy on the AppWorld benchmark by up to 17.1% by learning to engineer better contexts from execution feedback alone, without needing ground-truth labels.

- **Large Gains on Domain-Specific Benchmarks**: On complex financial reasoning benchmarks, ACE delivers an average performance gain of 8.6% over strong baselines.

- **Effective by Design**: Ablation studies confirm design choices are key to success.

- **Lower Cost and Adaptation Latency**: ACE achieves 86.9% lower adaptation latency on average, while requiring fewer rollouts and lower token dollar costs.

### 4.1 Tasks and Datasets

#### LLM Agent: AppWorld
AppWorld [43] is a suite of autonomous agent tasks involving API understanding, code generation, and environment interaction. It provides a realistic execution environment with common applications and APIs (e.g., email, file system) and tasks of two difficulty levels (normal and challenge).

#### Financial Analysis: FiNER and Formula
- **FiNER** [33]: requires labeling tokens in XBRL financial documents with one of 139 fine-grained entity types
- **Formula** [44]: focuses on extracting values from structured XBRL filings and performing computations to answer financial queries

### 4.2 Baselines and Methods

| Method | Description |
|--------|-------------|
| **Base LLM** | Evaluated directly without context engineering |
| **ICL** [3] | In-Context Learning with task demonstrations |
| **MIPROv2** [36] | Joint optimization of system instructions and demonstrations via Bayesian optimization |
| **GEPA** [4] | Genetic-Pareto prompt optimizer based on reflective prompt evolution |
| **Dynamic Cheatsheet (DC)** [41] | Test-time learning with adaptive external memory |
| **ACE (ours)** | Agentic context engineering framework |

### 4.3 Results on Agent Benchmark

| Method | GT Labels | Test-Normal |  | Test-Challenge |  | Average |
|--------|-----------|-------------|--|----------------|--|---------|
|        |           | TGC↑ | SGC↑ | TGC↑ | SGC↑ |  |
| **ReAct** | | 63.7 | 42.9 | 41.5 | 21.6 | 42.4 |
| **Offline Adaptation** |
| ReAct + ICL | ✓ | 64.3 | 46.4 | 46.0 | 27.3 | 46.0 |
| ReAct + GEPA | ✓ | 64.9 | 44.6 | 46.0 | 30.2 | 46.4 |
| ReAct + ACE | ✓ | **76.2** | **64.3** | **57.3** | **39.6** | **59.4** |
| ReAct + ACE | ✗ | 75.0 | 64.3 | 54.4 | 35.2 | 57.2 |
| **Online Adaptation** |
| ReAct + DC (CU) | ✗ | 65.5 | 58.9 | 52.3 | 30.8 | 51.9 |
| ReAct + ACE | ✗ | **69.6** | 53.6 | **66.0** | **48.9** | **59.5** |

### 4.4 Results on Domain-Specific Benchmark

| Method | GT Labels | FiNER (Acc↑) | Formula (Acc↑) | Average |
|--------|-----------|--------------|----------------|---------|
| Base LLM | | 70.7 | 67.5 | 69.1 |
| **Offline Adaptation** |
| ICL | ✓ | 72.3 | 67.0 | 69.6 |
| MIPROv2 | ✓ | 72.4 | 69.5 | 70.9 |
| GEPA | ✓ | 73.5 | 71.5 | 72.5 |
| ACE | ✓ | **78.3** | **85.5** | **81.9** |
| ACE | ✗ | 71.1 | 83.0 | 77.1 |
| **Online Adaptation** |
| DC (CU) | ✓ | 74.2 | 69.5 | 71.8 |
| DC (CU) | ✗ | 68.3 | 62.5 | 65.4 |
| ACE | ✓ | **76.7** | **76.5** | **76.6** |
| ACE | ✗ | 67.3 | 78.5 | 72.9 |

### 4.5 Ablation Study

| Method | GT Labels | Test-Normal |  | Test-Challenge |  | Average |
|--------|-----------|-------------|--|----------------|--|---------|
|        |           | TGC↑ | SGC↑ | TGC↑ | SGC↑ |  |
| ReAct | | 63.7 | 42.9 | 41.5 | 21.6 | 42.4 |
| ReAct + ACE w/o Reflector or multi-epoch | ✓ | 70.8 | 55.4 | 55.9 | 38.1 | 55.1 |
| ReAct + ACE w/o multi-epoch | ✓ | 72.0 | 60.7 | 54.9 | 39.6 | 56.8 |
| ReAct + ACE | ✓ | **76.2** | **64.3** | **57.3** | 39.6 | **59.4** |

### 4.6 Cost and Speed Analysis

#### Offline (AppWorld)
| Method | Latency (s)↓ | # Rollouts↓ |
|--------|--------------|-------------|
| ReAct + GEPA | 53898 | 1434 |
| ReAct + ACE | **9517** (-82.3%) | **357** (-75.1%) |

#### Online (FiNER)
| Method | Latency (s)↓ | Token Cost ($)↓ |
|--------|--------------|-----------------|
| DC (CU) | 65104 | 17.7 |
| ACE | **5503** (-91.5%) | **2.9** (-83.6%) |

---

## 5 Discussion

### Longer Context ≠ Higher Serving Cost

Although ACE produces longer contexts than methods such as GEPA, this does not translate to linearly higher inference cost or GPU memory usage. Modern serving infrastructures are increasingly optimized for long-context workloads through techniques such as KV cache reuse [17, 51], compression [30, 32], and offload [25].

### Implications for Online and Continuous Learning

ACE offers a flexible and efficient alternative to conventional model fine-tuning, as adapting contexts is generally cheaper than updating model weights [9, 20, 26, 28]. Moreover, because contexts are human-interpretable, ACE enables **selective unlearning** [8, 10, 29]—whether due to privacy or legal constraints [1, 2], or when outdated or incorrect information is identified by domain experts.

---

## Appendix A: Related Work on Agent Memory

A growing body of work explores how agents can accumulate experience from past trajectories and leverage external (often non-parametric) memory to guide future actions:

- **AgentFly** [59]: extensible framework where memory evolves continuously
- **AWM (Agent Workflow Memory)** [46]: induces reusable workflows distilled from past trajectories
- **A-MEM** [48]: dynamically organized memory system inspired by the Zettelkasten method
- **Agentic Plan Caching** [58]: focuses on cost efficiency by extracting reusable plan templates

---

## Appendix B: Limitations and Challenges

A potential limitation of ACE is its reliance on a reasonably strong Reflector: if the Reflector fails to extract meaningful insights from generated traces or outcomes, the constructed context may become noisy or even harmful. We also note that not all applications require rich or detailed contexts. Tasks like HotPotQA [50] often benefit more from concise, high-level instructions than from long contexts.

Overall, ACE is most beneficial in settings that demand detailed domain knowledge, complex tool use, or environment-specific strategies that go beyond what is already embedded in model weights or simple system instructions.

---

## References

[1] General Data Protection Regulation article 17: Right to erasure. EU Regulation 2016/679, 2016.

[2] California consumer privacy act, civil code §1798.105: Right to delete. State of California Civil Code, 2018.

[3] Rishabh Agarwal, et al. Many-shot in-context learning. *Advances in Neural Information Processing Systems*, 37:76930–76966, 2024.

[4] Lakshya A Agrawal, et al. Gepa: Reflective prompt evolution can outperform reinforcement learning. *arXiv preprint arXiv:2507.19457*, 2025.

[5] AppWorld. Leaderboard. https://appworld.dev/leaderboard, 2025.

[6] Akari Asai, et al. Self-rag: Learning to retrieve, generate, and critique through self-reflection. 2024.

[7] Sebastian Borgeaud, et al. Improving language models by retrieving from trillions of tokens. *ICML*, pages 2206–2240. PMLR, 2022.

[8] Lucas Bourtoule, et al. Machine unlearning. *IEEE Symposium on Security and Privacy*, pages 141–159, 2021.

[9] Tom Brown et al. Language models are few-shot learners. In *NeurIPS*, 2020.

[10] Yinzhi Cao and Junfeng Yang. Towards making systems forget with machine unlearning. In *IEEE Symposium on Security and Privacy*, 2015.

[11] Tianxiang Chen, et al. Flora: Effortless context construction to arbitrary length and scale. *arXiv preprint arXiv:2507.19786*, 2025.

[12] Yeounoh Chung, et al. Is long context all you need? leveraging llm's extended context for nl2sql. *arXiv preprint arXiv:2501.12372*, 2025.

[13] DeepSeek-AI. Deepseek-v3 technical report, 2024.

[14] DSPy. dspy.gepa: Reflective prompt optimizer. https://dspy.ai/api/optimizers/GEPA/overview/, 2025.

[15] DSPy. dspy.miprov2. https://dspy.ai/api/optimizers/MIPROv2/, 2025.

[16] Shuzheng Gao, et al. The prompt alchemist: Automated llm-tailored prompt optimization for test case generation. *arXiv preprint arXiv:2501.01329*, 2025.

[17] In Gim, et al. Prompt cache: Modular attention reuse for low-latency inference. *Proceedings of Machine Learning and Systems*, 6:325–338, 2024.

[18] Neel Guha, et al. Legalbench: A collaboratively built benchmark for measuring legal reasoning in large language models. *Advances in neural information processing systems*, 36:44123–44279, 2023.

[19] Ishaan Gulrajani and David Lopez-Paz. In search of lost domain generalization. In *ICLR*, 2021.

[20] Edward J. Hu, et al. LoRA: Low-rank adaptation of large language models. *arXiv:2106.09685*, 2021.

[21] Maxwell L Hutchinson, et al. Overcoming data scarcity with transfer learning. *arXiv preprint arXiv:1711.05099*, 2017.

[22] Mingjian Jiang, et al. Putting it all into context: Simplifying agents with lclms. *arXiv preprint arXiv:2505.08120*, 2025.

[23] Tushar Khot, et al. Decomposed prompting: A modular approach for solving complex tasks. *arXiv preprint arXiv:2210.02406*, 2022.

[24] Pang Wei Koh, et al. Wilds: A benchmark of in-the-wild distribution shifts. *ICML*, pages 5637–5664. PMLR, 2021.

[25] Wonbeom Lee, et al. InfiniGen: Efficient generative inference of large language models with dynamic KV cache management. In *18th USENIX Symposium on Operating Systems Design and Implementation (OSDI 24)*, pages 155–172, 2024.

[26] Brian Lester, et al. The power of scale for parameter-efficient prompt tuning. In *EMNLP*, 2021.

[27] Patrick Lewis, et al. Retrieval-augmented generation for knowledge-intensive nlp tasks. *Advances in neural information processing systems*, 33:9459–9474, 2020.

[28] Xiang Lisa Li and Percy Liang. Prefix-tuning: Optimizing continuous prompts for generation. *ACL*, 2021.

[29] Shiyang Liu et al. Rethinking machine unlearning for large language models. *arXiv:2402.08787*, 2024.

[30] Yuhan Liu, et al. Cachegen: Kv cache compression and streaming for fast large language model serving. In *Proceedings of the ACM SIGCOMM 2024 Conference*, pages 38–56, 2024.

[31] Zhining Liu, et al. Selfelicit: Your language model secretly knows where is the relevant evidence. *arXiv preprint arXiv:2502.08767*, 2025.

[32] Zirui Liu, et al. Kivi: A tuning-free asymmetric 2bit quantization for kv cache. *arXiv preprint arXiv:2402.02750*, 2024.

[33] Lefteris Loukas, et al. Finer: Financial numeric entity recognition for xbrl tagging. *arXiv preprint arXiv:2203.06482*, 2022.

[34] Yansheng Mao, et al. Lift: Improving long context understanding through long input fine-tuning. *arXiv preprint arXiv:2412.13626*, 2024.

[35] Sami Marreed, et al. Towards enterprise-ready computer using generalist agent. *arXiv preprint arXiv:2503.01861*, 2025.

[36] Krista Opsahl-Ong, et al. Optimizing instructions and demonstrations for multi-stage language model programs. *arXiv preprint arXiv:2406.11695*, 2024.

[37] Sinno Jialin Pan and Qiang Yang. A survey on transfer learning. *IEEE Transactions on Knowledge and Data Engineering*, 22(10):1345–1359, 2010.

[38] Shishir G Patil, et al. Gorilla: Large language model connected with massive apis. *Advances in Neural Information Processing Systems*, 37:126544–126565, 2024.

[39] Bowen Peng, et al. Yarn: Efficient context window extension of large language models. *arXiv preprint arXiv:2309.00071*, 2023.

[40] Noah Shinn, et al. Reflexion: Language agents with verbal reinforcement learning. *Advances in Neural Information Processing Systems*, 36:8634–8652, 2023.

[41] Mirac Suzgun, et al. Dynamic cheatsheet: Test-time learning with adaptive memory. *arXiv preprint arXiv:2504.07952*, 2025.

[42] Mirac Suzgun, et al. Dynamic cheatsheet: Test-time learning with adaptive memory. https://github.com/suzgunmirac/dynamic-cheatsheet, 2025.

[43] Harsh Trivedi, et al. Appworld: A controllable world of apps and people for benchmarking interactive coding agents. *arXiv preprint arXiv:2407.18901*, 2024.

[44] Dannong Wang, et al. Finlora: Benchmarking lora methods for fine-tuning llms on financial datasets. *arXiv preprint arXiv:2505.19819*, 2025.

[45] Xuezhi Wang, et al. Self-consistency improves chain of thought reasoning in language models. *arXiv preprint arXiv:2203.11171*, 2022.

[46] Zora Zhiruo Wang, et al. Agent workflow memory. *arXiv preprint arXiv:2409.07429*, 2024.

[47] Jason Wei, et al. Chain-of-thought prompting elicits reasoning in large language models. *Advances in neural information processing systems*, 35:24824–24837, 2022.

[48] Wujiang Xu, et al. A-mem: Agentic memory for llm agents. *arXiv preprint arXiv:2502.12110*, 2025.

[49] John Yang, et al. Swe-agent: Agent-computer interfaces enable automated software engineering. *Advances in Neural Information Processing Systems*, 37:50528–50652, 2024.

[50] Zhilin Yang, et al. Hotpotqa: A dataset for diverse, explainable multi-hop question answering. *arXiv preprint arXiv:1809.09600*, 2018.

[51] Jiayi Yao, et al. Cacheblend: Fast large language model serving for rag with cached knowledge fusion. In *Proceedings of the Twentieth European Conference on Computer Systems*, pages 94–109, 2025.

[52] Shunyu Yao, et al. React: Synergizing reasoning and acting in language models. In *International Conference on Learning Representations (ICLR)*, 2023.

[53] Jiacheng Ye, et al. Generating data for symbolic language with large language models. *arXiv preprint arXiv:2305.13917*, 2023.

[54] Mert Yuksekgonul, et al. Textgrad: Automatic "differentiation" via text. *arXiv preprint arXiv:2406.07496*, 2024.

[55] Matei Zaharia, et al. The shift from models to compound ai systems. https://bair.berkeley.edu/blog/2024/02/18/compound-ai-systems/, 2024.

[56] Genghan Zhang, et al. Adaptive self-improvement llm agentic system for ml library development. *arXiv preprint arXiv:2502.02534*, 2025.

[57] Qizheng Zhang, et al. Caravan: Practical online learning of In-Network ML models with labeling agents. In *18th USENIX Symposium on Operating Systems Design and Implementation (OSDI 24)*, pages 325–345, 2024.

[58] Qizheng Zhang, et al. Cost-efficient serving of llm agents via test-time plan caching. *arXiv preprint arXiv:2506.14852*, 2025.

[59] Huichi Zhou, et al. Agentfly: Fine-tuning llm agents without fine-tuning llms. *arXiv preprint arXiv:2508.16153*, 2025.

[60] Fuzhen Zhuang, et al. A comprehensive survey on transfer learning. *arXiv:1911.02685*, 2019.

---

## Appendix D: Prompts

The paper includes detailed prompts for all components of the ACE framework:

- **Figure 6**: ICL-baseline Generator prompt on AppWorld
- **Figure 7**: Dynamic Cheatsheet Generator prompt on AppWorld
- **Figure 8**: GEPA prompt on AppWorld
- **Figure 9**: ACE Generator prompt on AppWorld
- **Figure 10**: ACE Reflector prompt on AppWorld
- **Figure 11**: ACE Curator prompt on AppWorld
- **Figure 12**: ACE Generator prompt on FINER
- **Figure 13**: ACE Reflector prompt on FINER
- **Figure 14**: ACE Curator prompt on FINER

*(See original paper for full prompt texts)*
