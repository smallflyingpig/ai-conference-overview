# ACL 2026 获奖论文深读总览

## 证据口径与当前状态

本总览覆盖 ACL 2026 long track 官方 volume 页面标注的 30 篇获奖论文。论文事实只来自 ACL Anthology 官方 PDF；award 类别来自已对账的官方 volume HTML。30 条结构化 DeepRead 均通过 `DeepRead.model_validate` 与 `validate_deep_read`，并与 official inventory 逐 ID 绑定。两轮独立 QA 共发现 8 篇存在局部字段问题，所有 30 个替换均以 exact-old-value guard 应用；因此这里采用修正后的 model/metric/setting/locator，同时保留论文内部矛盾、私有数据和版本漂移等不确定性。

这里的“论文明确披露”与“跨论文综合”严格分开。下文具体数值是 paper-reported；对数据 pipeline、训练和评估的迁移判断属于 synthesis/inference，不代表原论文结论。PDF 的字节数和 SHA-256 来自下载的官方 PDF bytes；页数只保留为 source-note claimed metadata，未从 PDF bytes 独立验证，见 `data/awards/acl/2026-long-deep-read-provenance.json`。

## 关键节点、关键结论、关键认知

### 1. 评估从静态总分转向可诊断的部署闭环

- **ImplicitMemBench（1301）**把 learning/priming、interference 和 first-attempt test 分开；17 个模型整体均未超过 66%，说明显式检索成功不能替代行为适应证据。
- **Audio MultiChallenge（1654）**保留真人语音中的回溯、停顿、环境与副语言线索；452 段录音、1,712 条 atomic rubric 下，最强系统 APR 为 54.65%。
- **VeriTaS（1948）**用季度更新、claim date 和 temporal retrieval filter 抑制持续预训练泄漏；知识截止日后的纵向退化表明时间本身必须进入 benchmark contract。
- **HSCodeComp（937）**在 632 个商品的层级规则任务上，最佳 agent 10-digit exact match 为 46.83%，但该值来自省略 expert-written Decision Rules 的配置；完整配置并未更好，提示“增加推理材料”可能引入 drift。
- **CAR-bench（1886）**把 state、tool、execution、policy、termination 作为联合通过条件，再分开报告 Pass@k 和 Pass^k。Claude Opus 4.6 thinking 的 overall Pass^3 为 0.58，显示“偶尔成功”远不等于稳定部署。
- **MediEval（734）**以 HSR/TIR 追踪医学判断的错误跃迁。Llama-3.3-70B base macro-F1 为 70.7%，但 TIR 仍达 21.1%；CoRFu 在特定 Q1-vs-Q2 setting 得到 77.9% 与 0 TIR，后者不能外推为临床零风险。
- **Imperfective Paradox（689，Best Paper）**显示，压低 completion bias 的提示干预会同时伤害本应成立的 atelic entailment。因而 mitigation 不能只优化单向错误率，必须加入 telic/atelic、成立/不成立都平衡的 counterfactual controls。定位：Section 4.3、Section 5.2 与 Conclusion，PDF pp. 5–9。

核心认知：总分必须与 failure transition、consistency、时间泄漏和标注链一起报告。真实部署中的评估对象不仅是输入样本，也包括检索时间、工具状态、模拟用户和多轮轨迹。

### 2. 先定位机制，再实施最小干预

- **Memory efficiency（1550）**把工作记忆约束施加到表示精度而不只是 attention locality，迫使 encoding quality 与 retrieval locality 分开测。
- **CoSToM（421）**先以冻结 probe 做 causal tracing，再通过 activation-gradient bridge 调浅层 LoRA。独立 QA 更正了关键结果：2.39% 到 51.48% 是 Llama-3-8B-Instruct 在 layer 24 的 Agent-1 desire reconstruction accuracy，不是 Qwen2.5 answer probability。
- **GeoRA（1110）**依据 RLVR update geometry 选 low-energy subspace，并以残差重参数化保持初始函数不变；价值在于 subspace 诊断，而非默认沿用 SFT 的 principal components。
- **STEER（1436）**分解 token entropy change 并下调异常大的变化；Qwen2.5-Coder-14B 在私有 code-edit benchmark 上 exact match 45.1。QA 修正了模型家族名，私有 50K 数据仍是复现边界。
- **GISP（1653）**每轮剪枝后重算 `|gradient × weight|`，保存 nested sparsity checkpoints；20% task-calibrated pruning 下 GSM8K gold accuracy 为 67.93%。
- **PALU（893）**只干预 sensitive span 前 N 个 initiating tokens 的 frozen-reference top-K vocabulary；N=3、K=5,000 后收益趋于饱和，体现 temporal/vocabulary sparsity 下的最小必要干预。

核心认知：filter、PEFT、pruning、unlearning 都应先建立 task-linked 可观测变量，再做局部动作，并在动作改变分布后重新估计。一次性 saliency 或单独 entropy 曲线不足以上线。

### 3. 训练与推理必须覆盖策略诱导出的新分布

- **CURE（1321）**把 critique correctness 与 hint utility 分成两种训练信号，丢弃错误答案本体后 fresh solve，避免错误上下文 anchoring；Qwen2.5-7B 八轮 math average 为 44.9。
- **Evolutionary Guided Decoding（148）**固定生成 policy、迭代采样并重训 value function，缓解 critic 的 train/deploy distribution gap。QA 明确了 20.42 是 AlpacaEval 2 的 Length-Controlled Win Rate；86.17 是 SALAD-Bench attack-enhanced split 上的 Safety Rate。
- **Generative Montage（270）**通过 Writer、Editor、Director 和 Sybil publisher 的角色专门化，把局部真片段组合成全局误导；multi-agent 平均 ASR 明显高于 single-agent ablation，说明对抗迭代而非 agent 数量本身构成风险。
- **CxMP（2132）**显示 construction semantics 的学习曲线慢于一般语法能力，且偏置呈阶段性变化；单个 checkpoint 的提升可能只是 heuristic 增强。

核心认知：scorer、critic 或 safety evaluator 不能只在原始分布校准。数据重组、当前策略 rollout、对抗编辑和训练阶段变化都可能造成 measurement drift。

### 4. 结构一致性与字段间 agreement 成为一等指标

- **Local attention expressivity（1739）**形式化证明 local/global attention 表达互补；WikiText-2 的 hybrid 优势只是小规模 sanity check，不能外推到 frontier LLM。
- **CircularCSE（772）**同时看 V-Measure 与 circular CD-r：几何结构 fidelity 与分类分离存在 trade-off，不宜合成单一“更好”。
- **Systematicity between Forms and Meanings（1340）**固定 syncretism 等粗结构、扰动形式系统性，再用小 learner 测 CETL；QA 将训练 horizon 从错误的 50 steps 更正为 50 epochs。
- **PolyGloss（1657）**用 interleaved `morpheme(gloss)` serialization 联合生成 segmentation/gloss，并由确定性 parser 保证 hard alignment；九语言平均 alignment score 为 1.000，但 convention 异质性仍需逐语言处理。
- **CIG（2203）**将 conversational information gain 分解为 novelty、relevance、implication scope，并通过 semantic-memory update 形成可审计路径；最强 proxy 仍受 claim extraction/NLI 级联误差约束。
- **RACE（235）**把 RST discourse tree 映射到 relational graph，以低 FPR 指标评估人类、LLM、polished 和 humanized 文本。论文正文写 70/20/10，而 Appendix count 实际对应 70/10/20；结构化记录采用 count-backed split 并显式保留矛盾。

核心认知：多字段 pipeline 需要分别度量字段质量、字段间一致性和结构 fidelity；反事实实验应保持语言、repo、token、难度等粗粒度因素，只扰动目标结构。

### 5. 多模态、多语与社会场景暴露了上游瓶颈

- **DIA-HARM（144）**显示 dialect 数据配比会让 over-flag authentic speech 与 under-protect communities 之间反转，且许多错误置信度超过 0.95；aggregate F1 和 calibration 都不够。
- **Afri-MCQA（1869）**通过 LID、ASR 和文本控制表明，native speech 的文化 VQA 失败常从语言识别/转写开始，再传导到 reasoning。
- **Educational alignment（875）**发现 satisfaction 与四项 pedagogical metrics 无显著相关，且 unrestricted setting 中 92% 对话被判为 answer-seeking；engagement 不是 learning evidence。
- **ViLL-E（2003）**用共享生成 backbone 加 EOS-triggered pooling head 同时支持生成与检索；三阶段训练含许可型 Shutterstock 和 Claude 重标，完整复现成本高。
- **MauBERT（24）**先注入 articulatory/phone structured bias，再用至多 10 小时目标语适配；未见语言 zero-shot ABX 平均 5.39%，但 ABX 不能代表 syntax/semantics。
- **Lychee-FD（419）**以 layer-wise gradient conflict 和 semantic dilution 诊断驱动 shared/semantic/acoustic/control 分层；约 140K 对话主要来自合成，open-mic 外部效度仍不足。
- **Mind the (DH) Gap!（479）**在风险选择中观察 reasoning-model 与 conversational-model 两簇，最高 LLM-human correlation 也只有 0.42；不应把模型 preference 当作人类行为替代物。

核心认知：多语/多模态系统应优先报告 LID、ASR、alignment、semantic channel 等前置环节；社会影响评估必须按群体和错误方向拆分，不能用总均值或满意度代替实际效用。

## 30 篇论文索引

| Award | Papers |
|---|---|
| Best Paper | 1550 Memory efficiency；1739 Local attention expressivity；689 Imperfective paradox |
| Best Resource Paper | 1301 ImplicitMemBench；1654 Audio MultiChallenge；1948 VeriTaS；937 HSCodeComp |
| Best Social Impact Paper | 144 DIA-HARM；1869 Afri-MCQA；875 Educational alignment |
| Best Theme Paper | 421 CoSToM；772 CircularCSE |
| Outstanding Paper | 1110 GeoRA；1321 CURE；1340 Form-meaning systematicity；1436 STEER；148 Evolutionary Guided Decoding；1653 GISP；1657 PolyGloss；1886 CAR-bench；2003 ViLL-E；2132 CxMP；2203 CIG；235 RACE；24 MauBERT；270 Generative Montage；419 Lychee-FD；479 DH Gap；734 MediEval；893 PALU |

每个编号对应 `acl:2026.acl-long.<id>`。站点中的 30 个详情页承载逐篇 research problem、method、数值结果、limitations、reproducibility、transferable implications 和可追溯方法图；本文件只做跨篇组织，不重复 YAML 全量字段。

## 尚未消除的证据缺口

- **内部不一致**：HSCodeComp benchmark timestamp 在正文/Limitations 间不一致；RACE 的 prose split 与 Appendix counts 不一致；ViLL-E/Lychee-FD 存在标题或模型展示命名差异。这里保留而不擅自裁决。
- **私有或漂移依赖**：VeriTaS gated data 与外部网页、STEER 私有 code-edit、ViLL-E Shutterstock/Claude 重标、CAR-bench proprietary endpoints/Gemini simulator、CxMP GPT-5 生成判分都会阻碍完全重现。
- **统计强度**：GeoRA 主结果 single run，GISP 多数结果 seed 0；多项 judge/simulator 评估有额外测量误差。
- **外推边界**：多项工作只覆盖 verifiable reward、英语或单域，ABX/几何指标/模拟环境结果都不能直接提升为通用能力或真实部署结论。

## 面向代码预训练与数据 pipeline 的迁移建议（跨论文综合）

1. 对 parsing/filter/dedup/mixing 分别定义结构一致性、错误方向、coverage 与稳定性指标；不要用单一 edu score 或 aggregate benchmark 替代。
2. 做 matched counterfactual：保持语言、repo、token、difficulty、license 等不变，只扰动待验证信号；同时报告误杀、漏过与下游 held-out PPL/能力。
3. 分轮过滤或去重，每轮重算重要性、coverage 与 failure clusters，保存 nested 数据版本；用 equal-token/equal-mixture 冷启或 CPT 实验闭环。
4. scorer/critic 在重组后的 PR/Issue、func/repo-level 分布重新校准，检查 train-deploy drift；短 gate 或 proxy 上升不得直接写成最终收益。
5. 对 code agent 评估同时报告 Pass@k、Pass^k、tool/state/policy failure 以及 rule-depth 分桶，区分“有一次做对”与可重复可靠性。

以上建议是基于 30 篇论文方法的综合推断，尚需在目标 code-related 数据和模型 setting 上做独立实验验证。
