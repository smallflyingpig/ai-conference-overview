# ACL 2026 Long Papers：最终证据边界综览

本文只描述 ACL 2026 long-paper 的单年分布与热点（one-year distribution, not a trend），不把单年占比写成跨年趋势。

## 范围、覆盖与官方来源

- 官方卷共发现 2223 条记录；纳入 2222 篇 long paper，另有 1 条 proceedings front matter 单独排除。定位：官方卷页与 BibTeX 的双向 ID 对账。
- 摘要缺失 1 篇（acl:2026.acl-long.1232）；PDF 缺失 0 篇；DOI 缺失 2 篇。定位：`data/analysis/acl/2026-long/validation.json`。
- 官方入口：<https://aclanthology.org/volumes/2026.acl-long/>。

| 官方源 | 抓取时间（UTC） | SHA-256 |
|---|---|---|
| [ACL Anthology BibTeX](https://aclanthology.org/volumes/2026.acl-long.bib) | 2026-08-24T16:50:50.968120+00:00 | `94ad985a1a34d59ffe2f42e44354f966d012137e010948fd0c5d62ad15e5c12e` |
| [ACL Anthology volume HTML](https://aclanthology.org/volumes/2026.acl-long/) | 2026-08-24T16:50:50.991724+00:00 | `ff98541fd3ca2d68e150f41f4be20e2da89618ac18fca3c0b4fe7661cdfc6632` |

## 分类方法、审计门槛与限制

分类采用 agent semantic batch review：逐篇读取官方 title + abstract，给出单一 primary topic；随后经历独立审计修正和全主题复核。最终认证对每个主题使用固定、确定性的置信度分层样本（最多 50 篇），门槛同时要求 observed precision ≥ 0.90 且双侧 Wilson 95% 下界 ≥ 0.80。审计中的 false 只测量标签精度，不回写 topic。
限制：taxonomy 是分析框架而非 ACL 官方 track；一篇论文只能有一个 primary topic，会压缩跨主题贡献，因此 primary-assignment share 不等于研究问题的真实 prevalence；摘要审计不替代全文复核。该审计是确定性的置信度分层 precision 检查，不估计 recall，也不是随机总体抽样置信区间；样本较小的主题仍受 Wilson 下界约束。

## 主要研究问题

1. 测量效度与动态可靠性：评测如何抵抗污染、分布漂移、judge bias 与重复试验不一致？
2. 高效适配与推理：如何同时控制长上下文 KV/compute、PEFT、持续训练与推理成本？
3. 真实分布下的安全与公平：如何覆盖多模态联合攻击、过度拒绝、群体差异和现实混杂？
4. Grounding、retrieval 与 memory：外部证据、结构化检索和长期状态如何共同约束生成？
5. 多模态组合与流式交互：模型如何表示组合关系、时序证据、说话人和响应时机？
6. Agent 分解：如何分别评估 tool、state、policy、planner/controller 和 termination？

## 十主题单年分布与最终审计

| 主题 | 论文数 | 占比 | 审计正确/样本 | Precision | Wilson 95% 下界 | 状态 |
|---|---:|---:|---:|---:|---:|---|
| Evaluation | 576 | 25.92% | 49/50 | 0.9800 | 0.895046 | 通过 |
| Learning and Optimization | 450 | 20.25% | 48/50 | 0.9600 | 0.865399 | 通过 |
| Trustworthiness | 381 | 17.15% | 50/50 | 1.0000 | 0.928652 | 通过 |
| Data and Retrieval | 235 | 10.58% | 46/50 | 0.9200 | 0.811618 | 通过 |
| Multimodal Models | 213 | 9.59% | 47/50 | 0.9400 | 0.837829 | 通过 |
| Reasoning and Agents | 112 | 5.04% | 44/50 | 0.8800 | 0.761952 | 实验性 / withheld |
| Applications | 101 | 4.55% | 49/50 | 0.9800 | 0.895046 | 通过 |
| NLP/CV Core Tasks | 79 | 3.56% | 48/50 | 0.9600 | 0.865399 | 通过 |
| Foundation Models | 61 | 2.75% | 46/50 | 0.9200 | 0.811618 | 通过 |
| Multilingual and Inclusive NLP | 14 | 0.63% | 12/14 | 0.8571 | 0.600586 | 实验性 / withheld |

## 可进入 headline 的 8 个主题

只有通过双门槛的 Applications、Data and Retrieval、Evaluation、Foundation Models、Learning and Optimization、Multimodal Models、NLP/CV Core Tasks、Trustworthiness 可用于正式热点陈述。Multilingual and Inclusive NLP（12/14，0.8571，Wilson 0.600586）；Reasoning and Agents（44/50，0.8800，Wilson 0.761952）只保留为实验性观察，不进入 headline。定位：`data/classification/acl/2026-long/audit-decisions.json`。

## 五条 advances 证据链

- **text_llms（主题门槛通过，代表论文另行语义复核）**
  - 研究问题：How should text models condition pretraining, extend context, specialize without catastrophic loss, and diagnose internal mechanisms?
  - 支撑论文：[KoCo: Conditioning Language Model Pre-training on Knowledge Coordinates](https://aclanthology.org/2026.acl-long.1111/)（定位：Abstract）。
  - 支撑论文：[Latent-Condensed Transformer for Efficient Long Context Modeling](https://aclanthology.org/2026.acl-long.1176/)（定位：Abstract）。
  - 支撑论文：[TOWER+: Bridging Generality and Translation Specialization in Multilingual LLMs](https://aclanthology.org/2026.acl-long.1366/)（定位：Abstract）。
  - 支撑论文：[Multi-component Causal Tracing in Large Language Models](https://aclanthology.org/2026.acl-long.154/)（定位：Abstract）。
  - `跨论文综合`：Text-model progress couples corpus conditioning, long-context efficiency, staged adaptation, and mechanism-level diagnosis. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `论文明确披露`：KoCo adds structured knowledge coordinates to pretraining; LCA jointly compresses KV state and sparse computation; Tower+ stages continued pretraining, supervised, preference, and reinforcement learning; multi-component causal tracing diagnoses interacting internal pathways. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `跨论文综合`：The linked abstracts report distinct model families and evaluation settings; this lane is a structured comparison, not evidence that one recipe dominates across settings. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `推断`：Evaluate pretraining context, adaptation stages, serving cost, and causal diagnostics together rather than treating text-model quality as one scalar. 定位：Inference from the linked ACL paper abstracts。
- **multimodal_models（主题门槛通过，代表论文另行语义复核）**
  - 研究问题：How can multimodal systems preserve composition, streaming state, retrieval structure, evaluator validity, and safety across modalities?
  - 支撑论文：[Cross-Modal Masked Compositional Concept Modeling for Enhancing Visio-Linguistic Compositionality](https://aclanthology.org/2026.acl-long.1490/)（定位：Abstract）。
  - 支撑论文：[AV-Dialog: Spoken Dialogue Models with Audio-Visual Input](https://aclanthology.org/2026.acl-long.1954/)（定位：Abstract）。
  - 支撑论文：[Response-G1: Explicit Scene Graph Modeling for Proactive Streaming Video Understanding](https://aclanthology.org/2026.acl-long.2042/)（定位：Abstract）。
  - 支撑论文：[MegaRAG: Multimodal Knowledge Graph-Based Retrieval Augmented Generation](https://aclanthology.org/2026.acl-long.2218/)（定位：Abstract）。
  - 支撑论文：[MM-JudgeBias: A Benchmark for Evaluating Compositional Biases in MLLM-as-a-Judge](https://aclanthology.org/2026.acl-long.1162/)（定位：Abstract）。
  - 支撑论文：[CrossGuard: Safeguarding MLLMs against Joint-Modal Implicit Malicious Attacks](https://aclanthology.org/2026.acl-long.1178/)（定位：Abstract）。
  - `跨论文综合`：Multimodal systems must align compositional concepts, streaming interaction, structured memory, evaluation reliability, and joint-modal safety. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `论文明确披露`：MACCO models masked compositional concepts; AV-Dialog integrates streaming audio-visual dialogue; Response-G1 uses scene graphs for proactive response; MegaRAG builds cross-modal knowledge-graph retrieval; MM-JudgeBias and CrossGuard expose judge bias and implicit joint-modal attacks. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `跨论文综合`：The papers cover different modalities, tasks, and threat models, so their reported gains cannot be pooled into a common effect size. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `推断`：Multimodal evaluation should jointly test grounding, temporal state, retrieval structure, judge robustness, and cross-modal attack composition. 定位：Inference from the linked ACL paper abstracts。
- **reasoning_agents（实验性观察，不构成 headline trend）**
  - 研究问题：How should agents decompose planning, tool use, memory routing, browser state, policy choice, and termination?
  - 支撑论文：[OctoTools: A Multi-Agent Framework with Extensible Tools for Complex Reasoning](https://aclanthology.org/2026.acl-long.1/)（定位：Abstract）。
  - 支撑论文：[MoEC: A Memory-Routed Mixture-of-Experts Controller for Adaptive Minecraft Control](https://aclanthology.org/2026.acl-long.1027/)（定位：Abstract）。
  - 支撑论文：[SPIO: Ensemble and Selective Strategies via LLM-Based Multi-Agent Planning in Automated Data Science](https://aclanthology.org/2026.acl-long.1039/)（定位：Abstract）。
  - 支撑论文：[Nested Browser-Use Learning for Agentic Information Seeking](https://aclanthology.org/2026.acl-long.1049/)（定位：Abstract）。
  - `跨论文综合`：Agent systems must coordinate planner-controller decomposition with external tools, persistent state, branching strategies, and termination decisions. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `论文明确披露`：OctoTools standardizes tool cards and planner-executor roles; MoEC routes subgoals through expert memory; SPIO explores and selects multiple data-science plans; NestBrowse separates browser actions from higher-level information-seeking control. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `跨论文综合`：Reasoning and Agents failed the final theme precision gate, so these papers are experimental observations and cannot support a headline prevalence or trend claim. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `推断`：Agent evaluation should separate plan quality, tool-state transitions, policy routing, recovery, and stopping behavior rather than report only final-task success. 定位：Inference from the linked ACL paper abstracts。
- **data_training（主题门槛通过，代表论文另行语义复核）**
  - 研究问题：How do data conditioning, PEFT geometry, RLVR rollout distributions, critique loops, entropy weighting, and iterative re-estimation interact?
  - 支撑论文：[KoCo: Conditioning Language Model Pre-training on Knowledge Coordinates](https://aclanthology.org/2026.acl-long.1111/)（定位：Abstract）。
  - 支撑论文：[TOWER+: Bridging Generality and Translation Specialization in Multilingual LLMs](https://aclanthology.org/2026.acl-long.1366/)（定位：Abstract）。
  - 支撑论文：[GeoRA: Geometry-Aware Low-Rank Adaptation for RLVR](https://aclanthology.org/2026.acl-long.1110/)（定位：Abstract）。
  - 支撑论文：[CURE: Critique-Driven Unified Reinforcement Learning for Test-Time Self-Improvement](https://aclanthology.org/2026.acl-long.1321/)（定位：Abstract）。
  - 支撑论文：[Rethinking Entropy Interventions in RLVR: An Entropy Change Perspective](https://aclanthology.org/2026.acl-long.1436/)（定位：Abstract）。
  - 支撑论文：[From Local to Global: Revisiting Structured Pruning Paradigms for Large Language Models](https://aclanthology.org/2026.acl-long.1653/)（定位：Abstract）。
  - `跨论文综合`：Training quality depends on how corpora are conditioned, parameter subspaces are selected, rollouts are induced, and evidence is re-estimated across iterations. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `论文明确披露`：KoCo and Tower+ alter pretraining/adaptation stages; GeoRA aligns PEFT with RLVR geometry; CURE uses critique-driven self-improvement; STEER weights policy updates through estimated entropy change; GISP repeatedly re-estimates global pruning importance. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `跨论文综合`：The accepted-paper corpus is observational metadata plus paper-reported experiments; it does not by itself establish causal gains from any general data-quality policy. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `推断`：Data strategy experiments should log induced rollout distributions and iterative model-data feedback, not only static source counts or final benchmark deltas. 定位：Inference from the linked ACL paper abstracts。
- **evaluation_trust（主题门槛通过，代表论文另行语义复核）**
  - 研究问题：How can evaluation remain valid under contamination, dynamic distributions, judge bias, multimodal attacks, memory effects, and repeated trials?
  - 支撑论文：[Red Teaming Large Reasoning Models](https://aclanthology.org/2026.acl-long.1034/)（定位：Abstract）。
  - 支撑论文：[MM-JudgeBias: A Benchmark for Evaluating Compositional Biases in MLLM-as-a-Judge](https://aclanthology.org/2026.acl-long.1162/)（定位：Abstract）。
  - 支撑论文：[CrossGuard: Safeguarding MLLMs against Joint-Modal Implicit Malicious Attacks](https://aclanthology.org/2026.acl-long.1178/)（定位：Abstract）。
  - 支撑论文：[Jailbreaking Multimodal Large Language Models using Multi-Clip Video](https://aclanthology.org/2026.acl-long.1186/)（定位：Abstract）。
  - 支撑论文：[Inflated Excellence or True Performance? Rethinking Medical Diagnostic Benchmarks with Dynamic Evaluation](https://aclanthology.org/2026.acl-long.1218/)（定位：Abstract）。
  - 支撑论文：[ImplicitMemBench: Measuring Unconscious Behavioral Adaptation in Large Language Models](https://aclanthology.org/2026.acl-long.1301/)（定位：Abstract）。
  - 支撑论文：[VeriTaS: The First Dynamic Benchmark for Multimodal Automated Fact-Checking](https://aclanthology.org/2026.acl-long.1948/)（定位：Abstract）。
  - 支撑论文：[CAR-bench: Evaluating the Consistency and Limit-Awareness of LLM Agents under Real-World Uncertainty](https://aclanthology.org/2026.acl-long.1886/)（定位：Abstract）。
  - 支撑论文：[The Imperfective Paradox in Large Language Models](https://aclanthology.org/2026.acl-long.689/)（定位：Abstract）。
  - `跨论文综合`：Static accuracy can conceal contamination, evaluator bias, multimodal jailbreaks, implicit memory effects, and inconsistent behavior across repeated realistic trials. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `论文明确披露`：Rt-LRM, MM-JudgeBias, CrossGuard, MCV SafetyBench, and DyReMe stress reasoning, judges, attacks, and dynamic diagnosis; ImplicitMemBench, VeriTaS, and CAR-bench add passive memory, refreshed fact-checking, and repeated stateful reliability evidence. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `跨论文综合`：Benchmark construction choices and model coverage differ; numeric results are available only in the linked paper or validated award DeepRead locators and are not recombined here. 定位：Official ACL Anthology Abstract for every linked supporting paper。
  - `推断`：Evaluation programs should refresh cases, counterbalance controls, repeat stateful trials, and measure evaluator reliability alongside model accuracy and safety. 定位：Inference from the linked ACL paper abstracts。

## 面向五类研发问题的特殊含义

- Text LLM：把长上下文、预训练条件化、效率与可解释性放在同一评估面板中。
- Multimodal：重点检查跨模态组合性、时序交互与 judge bias，而不只看静态 VQA。
- Agents：Reasoning 主题未过审计门槛，因此工具调用、浏览器控制和控制器结果只作实验性线索。
- Data / Training：联合追踪数据结构、训练/合并策略、推理成本与部署约束。
- Evaluation / Safety：动态评测、污染、judge 可靠性与多模态攻击面应成为共同 guardrail。

## 官方奖项与详细阅读

- 官方卷页识别并绑定 30 条 award badge。定位：官方 ACL volume page。
- 已完成并通过 schema/PDF provenance gate 的详细阅读 30 条；参见 [ACL 2026 获奖论文详细阅读](./acl-2026-awards-deep-reads.md) 和站点 `/awards/`。
