# ICML 2025 主题分布与获奖论文分析设计

## 1. 目标

把已经发布的 ICML 2025 主会论文清单升级为可阅读、可复查的单年分析版：

- 对 PMLR Volume 267 的 3330 篇论文生成统一 taxonomy 下的主题分布；
- 总结 ICML 2025 的主要研究热点，但不把单年分布描述为时间趋势；
- 核对并详细解读 ICML 2025 的 5 篇 Outstanding Paper 和 2 篇 Outstanding Position Paper；
- 在网站中开放主题分布、代表论文、方法说明和获奖论文详情；
- 任何检查未完成时继续保留现有论文清单版，不覆盖线上可用版本。

本阶段不导入 ICML 2023、ICML 2024，不计算同比变化、Emerging Score 或三年趋势。Test of Time Awards 不属于 2025 年新接收论文，本阶段不纳入主会论文分布和 7 篇当年获奖论文详情。

## 2. 数据范围与来源

### 2.1 论文范围

- 会议：ICML
- 年份：2025
- Track：main
- 官方论文集：PMLR Volume 267，`https://proceedings.mlr.press/v267/`
- 已完成对账：3330 条发现记录、3330 条纳入记录、0 条排除、0 条待处理、0 条缺失摘要、0 条缺失 PDF、3330 条缺失 DOI

分析必须直接复用仓库中已经冻结的 PMLR HTML 和 citeproc YAML 快照，以及 `data/normalized/icml/2025-main.jsonl`。不得在分类过程中重新抓取并静默替换论文集合。

### 2.2 Awards 范围

官方依据为 ICML 2025 Awards 页面：`https://icml.cc/virtual/2025/awards_detail`。本阶段只处理能够与 Volume 267 论文记录精确匹配的以下类别：

- Outstanding Paper：5 篇；
- Outstanding Position Paper：2 篇。

每条 award 记录必须同时绑定官方 awards 页面、PMLR landing page 和官方 PDF。Workshop awards、Invited Talk、Test of Time Award 与 Test of Time Honorable Mention 不进入这 7 篇详情。

## 3. 处理架构

### 3.1 总体数据流

```text
冻结的 PMLR 论文集合
  -> 导出分类输入 JSONL
  -> title + abstract 语义分类
  -> 完整性与 taxonomy 校验
  -> 低置信度逐篇复查
  -> 每主题分层抽样检查
  -> 计算单年主题分布
  -> 生成研究热点与代表论文
  -> 核对 7 篇官方 awards
  -> PDF 详细阅读与中文解读
  -> 生成 immutable release
  -> Astro 构建与桌面/手机验收
```

新增逻辑应复用共享的 classification、metrics、reports、award validation 和 immutable release 机制。若现有 ACL orchestration 含有 ACL 专用路径或 paper ID 假设，应抽出 venue-neutral 边界，而不是把 ICML 数据伪装成 ACL 输入。

### 3.2 输出目录

- 分类及检查记录：`data/classification/icml/2025-main/`
- Award 清单、DeepRead 与 PDF provenance：`data/awards/icml/`
- 中文分析说明：`notes/icml-2025-main-overview.md`
- 不可变 release：`data/releases/ICML/2025/generations/<sha256>/`
- 当前版本指针：`data/releases/ICML/2025/current.json`

release 继续严格包含六个文件：`papers.json`、`papers.csv`、`overview.json`、`overview.md`、`validation.json`、`provenance.json`。

## 4. 主题分类与检查

### 4.1 分类规则

使用 `config/taxonomy.yaml` 中的 `2026-08-24-v1` taxonomy：

1. Foundation Models
2. Reasoning and Agents
3. Data and Retrieval
4. Learning and Optimization
5. Evaluation
6. Trustworthiness
7. Multimodal Models
8. Multilingual and Inclusive NLP
9. Applications
10. NLP/CV Core Tasks

每篇论文必须具有：

- 恰好一个 primary topic；
- 零个或多个不重复的 secondary topics；
- 分类置信度；
- 基于 title 和 abstract 的简短理由；
- taxonomy version、paper ID 和 review status。

分类输入和输出必须精确覆盖 3330 个 paper ID，不得缺失、重复或新增。摘要存在时不得仅依据标题分类。

### 4.2 人工复查要求

- 逐篇复查所有 confidence 低于 0.70 的分类；
- 每个 primary topic 分层抽取最多 50 篇，主题少于 50 篇时全量检查；
- 检查结果必须绑定当前 assignments SHA-256、sample SHA-256 和 decision SHA-256；
- 修改任何分类规则或 assignments 后，旧的检查结果立即失效，必须重新抽样。

一个主题只有同时达到以下标准，才能用于首页或会议页的正式热点概括：

- 抽样准确率不低于 90%；
- Wilson 95% 置信区间下界不低于 80%。

只要有一个 primary topic 未达到标准，分类产物就只保留作诊断，不更新线上 release。页面可以继续展示现有论文清单，但不能提前展示部分主题的数量、占比或热点概括。

## 5. 分布、热点与趋势边界

### 5.1 可发布指标

ICML 2025 只发布单年主题分布：

```text
topic share = 该 primary topic 的论文数 / 3330
```

页面同时展示原始数量、占比、分母、taxonomy version 和抽查状态。代表论文只能从完成分类检查且与主题一致的论文中选择，并链接 PMLR 官方页面。

### 5.2 研究热点

“研究热点”是对 ICML 2025 单年论文集合的描述，内容包括：

- 通过检查的主要主题；
- 主题内部反复出现的技术问题；
- 具有代表性的论文及其官方链接；
- 对 Text LLM、Multimodal、Reasoning/Agents、Data/Training、Evaluation/Safety 的跨论文综合。

每条综合必须区分：official metadata、paper-reported、cross-paper synthesis 和 inference。论文数量较多不等同于技术进步，代表论文也不构成论文排名。

### 5.3 不发布的趋势指标

由于只有 ICML 2025 一个年份：

- 不计算同比 share delta；
- 不计算增长率；
- 不计算 Emerging Score；
- 不声称某主题“增长”“上升”“成为长期趋势”；
- 不把 ACL 2026 与 ICML 2025 的年份差异包装成时间趋势。

会议页和趋势页应明确显示：“当前只有 ICML 2025 单年数据，可以查看主题分布与研究热点，暂不能判断时间趋势。” `analysis_availability.trends` 保持为 `false`，主题分布完成后 `analysis_availability.distribution` 才能设为 `true`。

## 6. 获奖论文详细解读

### 6.1 结构

7 篇论文分别生成中文详情页，每页按适合学习的顺序呈现：

1. 三分钟读懂：用简洁中文说明问题、核心做法和主要发现；
2. 为什么值得关注：说明它解决了什么长期困难；
3. 方法拆解：只呈现论文明确披露的组件和关系；
4. 主要结果：每个数值保留实验 setting 和 section/table/figure/page locator；
5. 适用范围与局限：说明数据、任务、假设和外推边界；
6. 为什么可能获奖：明确标为综合判断，不冒充官方评语；
7. 对大模型研究的启发：区分论文原文与进一步推断；
8. 英文原文参考：链接官方 awards 页面、PMLR landing page 和 PDF locator。

### 6.2 内容要求

- 不复制论文受保护的原图；方法图只能用论文披露的节点和真实关系重新绘制；
- 不从摘要推断未披露的实验结果；
- 所有 numerical claims 必须带原始 setting 和 locator；
- 中文摘要应覆盖论文核心内容，但避免逐段翻译；
- Position Paper 必须明确标注其论证性质，不把政策主张写成实证结论；
- “为什么可能获奖”和“对大模型研究的启发”使用 cross-paper synthesis 或 inference 标签。

## 7. 网站呈现

### 7.1 ICML 2025 会议页

保留现有 scope、3330 篇论文和数据来源信息，并增加：

- 主题分布表和可读图形；
- 通过检查的主要研究热点；
- 各主题代表论文；
- 单年数据无法判断趋势的说明；
- 7 篇获奖论文入口；
- 数据完整度和分类检查状态。

### 7.2 Trends 页面

ICML 2025 可作为“单年快照”被选择，但图表不得显示伪造的折线或涨跌箭头。趋势区域显示年份不足说明，并引导用户回到 ICML 2025 主题分布。

### 7.3 Awards 页面

Awards 索引增加 ICML 2025 分组，ACL 2026 与 ICML 2025 不混排。卡片显示 award type、论文标题、作者和中文导读；详情路由继续使用 producer 生成的 collision-safe `route_key`。

所有新增页面延续中文叙述、保留必要英文论文标题和术语，并满足 390px 手机布局无横向溢出。

## 8. 失败处理与发布策略

以下情况必须在写入 `current.json` 前停止：

- 3330 篇分类没有精确覆盖；
- taxonomy、paper ID 或 assignments lineage 不一致；
- 低置信度复查未完成；
- 主题抽查记录不是由当前 assignments 生成；
- 任一 primary topic 未达到抽查标准；
- award 数量不是 7，或任一 award 无法与 PMLR 论文精确匹配；
- award 官方来源不在配置的 ICML host policy 中；
- DeepRead 缺少必要章节、PDF provenance、setting 或 locator；
- release 六文件不完整或 hash/current pointer 不一致；
- Astro schema 无法完整读取 release。

失败产物可以保留在临时或诊断目录，但不得覆盖当前已经发布的 papers-only release。

## 9. 验收标准

### 9.1 数据与 Python

- 3330/3330 assignments 精确覆盖，无重复、无额外 paper ID；
- 所有低置信度记录都有明确处理状态；
- 每个主题的 sample、decision、precision 和 Wilson lower bound 可复算；
- topic counts 总和为 3330，topic shares 使用同一分母；
- 7/7 awards 与 official page、PMLR landing page、PDF 精确绑定；
- 7/7 DeepReads 通过 schema、内容完整性和 locator 检查；
- immutable generation 恰好六个文件，current pointer 与文件 hash 一致；
- `pytest` 与 Ruff 全量通过。

### 9.2 网站与浏览器

- ICML 2025 页面展示主题分布、检查状态、代表论文和年份不足说明；
- Trends 页面不生成 ICML 的伪时间趋势；
- Awards 索引展示 7 篇 ICML 2025 awards，并能进入 7 个中文详情页；
- ACL 2026 原有分布和 30 篇 award 详情不回归；
- 空数据构建仍成功，且不生成不存在的会议或 award 详情；
- Vitest、Astro check/build 和 Playwright 全量通过；
- 桌面与 390px 手机端无横向溢出，折叠菜单、筛选和内部链接正常。

### 9.3 发布

- 先在本地 release-backed build 中完成验收；
- 用户明确授权后才 push `main` 触发 Pages；
- 部署后核对 workflow head SHA、公开 ICML 页面、Awards 索引、7 个详情路由和静态资源 HTTP 状态。

## 10. 明确不在本阶段处理的内容

- ICML 2023、2024 或更早年份；
- 时间趋势、同比变化和 Emerging Score；
- Test of Time Awards 详细解读；
- Workshop、Tutorial、Invited Talk 或其他非 Volume 267 主会论文；
- ICML 与 ACL 的跨会议排名；
- 依赖 citation count、社交媒体热度或非官方榜单的论文排序。
