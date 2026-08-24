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
限制：taxonomy 是分析框架而非 ACL 官方 track；一篇论文只能有一个 primary topic，会压缩跨主题贡献；摘要审计不替代全文复核；样本较小的主题受 Wilson 下界约束。

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

## 可进入 headline 的八个主题

只有通过双门槛的 Applications、Data and Retrieval、Evaluation、Foundation Models、Learning and Optimization、Multimodal Models、NLP/CV Core Tasks 和 Trustworthiness 可用于正式热点陈述。Reasoning and Agents（44/50，0.8800，Wilson 0.761952）与 Multilingual and Inclusive NLP（12/14，0.8571，Wilson 0.600586）只保留为实验性观察，不进入 headline。

## 五条 advances 证据链

- **text_llms（已审计综合）**：[Template-assisted Contrastive Learning of Task-oriented Dialogue Sentence Embeddings](https://aclanthology.org/2026.acl-long.1015/)。
  - `论文明确披露`：Template-assisted Contrastive Learning of Task-oriented Dialogue Sentence Embeddings reports the method and findings summarized in its official abstract; any quantitative result remains a paper-reported claim rather than an independent replication. 定位：ACL Anthology abstract: 2026.acl-long.1015。
  - `跨论文综合`：These named papers form a bounded cross-paper synthesis within audit-passed primary themes; the set illustrates the lane but does not claim semantic representativeness or temporal trend. 定位：official ACL titles and abstracts for the linked papers。
  - `推断`：A practical implication is to evaluate this lane as a coupled data, method, and measurement system; this interpretation goes beyond any single paper's reported result. 定位：inference from the linked ACL paper abstracts。
- **multimodal_models（已审计综合）**：[Cross-Modal Masked Compositional Concept Modeling for Enhancing Visio-Linguistic Compositionality](https://aclanthology.org/2026.acl-long.1490/)。
  - `论文明确披露`：Cross-Modal Masked Compositional Concept Modeling for Enhancing Visio-Linguistic Compositionality reports the method and findings summarized in its official abstract; any quantitative result remains a paper-reported claim rather than an independent replication. 定位：ACL Anthology abstract: 2026.acl-long.1490。
  - `跨论文综合`：These named papers form a bounded cross-paper synthesis within audit-passed primary themes; the set illustrates the lane but does not claim semantic representativeness or temporal trend. 定位：official ACL titles and abstracts for the linked papers。
  - `推断`：A practical implication is to evaluate this lane as a coupled data, method, and measurement system; this interpretation goes beyond any single paper's reported result. 定位：inference from the linked ACL paper abstracts。
- **reasoning_agents（实验性观察）**：[OctoTools: A Multi-Agent Framework with Extensible Tools for Complex Reasoning](https://aclanthology.org/2026.acl-long.1/)。
  - `跨论文综合`：These examples are selected deterministically by confidence and ACL ID from experimental primary-topic assignments; they make no semantic representativeness or lane-purity claim, trend claim, or paper-result claim. 定位：official ACL title and abstract metadata。
- **data_training（已审计综合）**：[SSSD: Simply-Scalable Speculative Decoding](https://aclanthology.org/2026.acl-long.1530/)。
  - `论文明确披露`：SSSD: Simply-Scalable Speculative Decoding reports the method and findings summarized in its official abstract; any quantitative result remains a paper-reported claim rather than an independent replication. 定位：ACL Anthology abstract: 2026.acl-long.1530。
  - `跨论文综合`：These named papers form a bounded cross-paper synthesis within audit-passed primary themes; the set illustrates the lane but does not claim semantic representativeness or temporal trend. 定位：official ACL titles and abstracts for the linked papers。
  - `推断`：A practical implication is to evaluate this lane as a coupled data, method, and measurement system; this interpretation goes beyond any single paper's reported result. 定位：inference from the linked ACL paper abstracts。
- **evaluation_trust（已审计综合）**：[Red Teaming Large Reasoning Models](https://aclanthology.org/2026.acl-long.1034/)。
  - `论文明确披露`：Red Teaming Large Reasoning Models reports the method and findings summarized in its official abstract; any quantitative result remains a paper-reported claim rather than an independent replication. 定位：ACL Anthology abstract: 2026.acl-long.1034。
  - `跨论文综合`：These named papers form a bounded cross-paper synthesis within audit-passed primary themes; the set illustrates the lane but does not claim semantic representativeness or temporal trend. 定位：official ACL titles and abstracts for the linked papers。
  - `推断`：A practical implication is to evaluate this lane as a coupled data, method, and measurement system; this interpretation goes beyond any single paper's reported result. 定位：inference from the linked ACL paper abstracts。

## 面向五类研发问题的特殊含义

- Text LLM：把长上下文、预训练条件化、效率与可解释性放在同一评估面板中。
- Multimodal：重点检查跨模态组合性、时序交互与 judge bias，而不只看静态 VQA。
- Agents：Reasoning 主题未过审计门槛，因此工具调用、浏览器控制和控制器结果只作实验性线索。
- Data / Training：联合追踪数据结构、训练/合并策略、推理成本与部署约束。
- Evaluation / Safety：动态评测、污染、judge 可靠性与多模态攻击面应成为共同 guardrail。

## 官方奖项与详细阅读

- 官方卷页识别并绑定 30 条 award badge。定位：官方 ACL volume page。
- 已完成并通过 schema/PDF provenance gate 的详细阅读 30 条；参见 [ACL 2026 获奖论文详细阅读](./acl-2026-awards-deep-reads.md) 和站点 `/awards/`。
