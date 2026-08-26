# ICML 2026 主会论文预发布导入设计

**日期：** 2026-08-26

**状态：** 视觉方案已确认，等待书面确认

**适用范围：** ICML 2026 Main Conference Papers

**目标：** 在 PMLR 正式论文集尚未上线时，从 ICML 官方会议程序导入主会论文，提供可检索的论文目录和英文摘要详情页；PMLR 发布后，再完成最终对照并移除预发布说明。

## 1. 背景

ICML 2026 已于 2026 年 7 月 11 日结束。Main Conference 于 7 月 7—9 日在首尔举行，论文录用结果已于 4 月 30 日公布。ICML 官网已经提供 2026 年论文列表，但预计对应的 PMLR Volume 306 目前尚未发布。

项目对 ICML 的最终收录以 PMLR 会议论文集为准。为了让读者在 PMLR 上线前使用 ICML 官网已经公开的论文信息，本次增加一份明确标注来源和适用范围的预发布版本。它可以用于论文浏览和检索，但不能替代最终论文集，也不能用于正式的主题分布、趋势或研究进展分析。

## 2. 本次范围

### 2.1 收录内容

- ICML 2026 Main Conference Papers；
- 论文标题、作者、ICML 官方页面和 OpenReview 论文页；
- ICML 官方数据中提供的英文摘要、官方 topic、session 和展示类型；
- 可确认的 PDF 链接；
- 原始官方数据、抓取时间、文件大小和 SHA-256；
- 论文目录、英文摘要详情页和会议范围说明页。

ICML 没有 ACL 的 long/short 划分。本项目使用 `main` 作为 track，不把它命名为 `long`。

### 2.2 不收录内容

- Position Papers；
- Journal-to-Conference；
- workshops、tutorials、expo 和其他活动；
- 无法确认属于 Main Conference 的条目；
- 逐篇中文摘要；
- 主题分布、趋势、Advances 和跨会议比较；
- 获奖论文解读。

## 3. 方案选择

本次采用“ICML 官网预发布、PMLR 最终对照”的两阶段方案。

没有选择直接等待 PMLR，因为会议已经结束，ICML 官网现有信息足以支持论文浏览；没有直接把 OpenReview 搜索结果作为完整录用名单，因为搜索结果可能混入其他 track，也不能证明收录范围完整。ICML 官网的官方会议程序用于本阶段导入，PMLR 会议论文集仍是最终版本的依据。

## 4. 数据来源与收录规则

### 4.1 官方来源

预发布版本使用以下官方页面和数据：

- ICML 2026 论文页：`https://icml.cc/virtual/2026/papers.html`；
- ICML 2026 活动数据入口：`https://icml.cc/static/virtual/data/icml-2026-orals-posters.json`；
- ICML 2026 摘要数据入口：`https://icml.cc/static/virtual/data/icml-2026-abstracts.json`；
- Main Conference 官方 OpenReview group：`https://openreview.net/group?id=ICML.cc/2026/Conference`；
- 最终对照目标：`https://proceedings.mlr.press/v306/`。

程序从官方静态数据入口开始，继续读取响应中的分页链接。ICML 当前响应可能把同站分页地址写成 `http://icml.cc/...`；程序只允许把这一种同主机地址改为 HTTPS 后访问。其他非 HTTPS 地址或其他主机一律拒绝。遇到分页循环、缺页、响应条数与 `count` 不一致或文件不完整时，停止本次导入。

### 4.2 Main Conference 判断

活动记录只有同时满足以下条件时，才可以进入 Main Conference 候选集合：

1. `sourceurl` 精确指向 `ICML.cc/2026/Conference` 官方 OpenReview group；
2. `paper_url` 是 `openreview.net/forum?id=<forum-id>`；
3. 记录处于公开状态；
4. `decision` 是当前官方数据使用的 `Accept (regular)` 或 `Accept (spotlight)`；oral 是额外的展示记录，不是另一种 track；
5. 标题、作者和来源字段完整。

Position Papers、Journal-to-Conference 或其他来源组即使出现在同一份 ICML feed 中，也不会进入发布数据。出现未知来源组或未知 decision 时，程序将其列入待处理清单，不根据标题或 session 猜测所属 track。

### 4.3 合并重复活动记录

同一篇论文可能同时有 poster、spotlight 或 oral 活动记录。程序以 OpenReview forum ID 作为论文身份，同一 ID 的多条活动记录合并为一篇论文，同时保留全部展示类型和 session。

合并前必须确认各记录的标题、作者和 OpenReview 地址一致。字段发生冲突时，该论文进入待处理清单；程序不能选择其中一条覆盖其他记录。

### 4.4 英文摘要

英文摘要必须来自 ICML 官方摘要数据或该论文的官方 OpenReview 记录。摘要与论文通过官方 event ID 或 OpenReview forum ID 对应，不能只按标题匹配。

缺少英文摘要不会导致整篇论文消失。详情页会明确写“官方数据暂未提供摘要”，并在数据统计中公布缺失数量。程序不能根据标题补写摘要。

## 5. 数据结构与文件

### 5.1 会议配置

`config/venues.yaml` 新增 `ICML / 2026 / main`：

- adapter：`icml_virtual`；
- source key：`icml-2026-main-preliminary`；
- 官方论文页、活动数据入口和摘要数据入口；
- Main Conference OpenReview group；
- PMLR Volume 306 最终对照地址；
- 当前发布状态：`preliminary_official_program`。

原有 ACL 配置和默认 track 保持不变。

### 5.2 规范化论文记录

ICML 论文沿用项目现有 `PaperRecord`，并使用以下约定：

- `paper_id`：`icml:2026:<openreview-forum-id>`；
- `venue`：`ICML`；
- `year`：`2026`；
- `track`：`main`；
- `landing_url`：ICML 官方论文页面；
- `pdf_url`：已确认的官方 PDF 地址，没有时为 `null`；
- `source`：指向对应的 ICML 官方数据文件；
- `status`：`complete`、`partial`、`excluded` 或 `unresolved`。

展示类型、session、ICML topic、OpenReview forum ID 和 event ID 作为来源字段保留。`poster`、`spotlight` 和 `oral` 是展示方式，不是三个不同 track，也不会生成三篇论文。

### 5.3 文件位置

本次导入生成独立文件，不覆盖 ACL 数据：

- `data/snapshots/icml/2026-main/`：不可原地修改的官方响应；
- `data/manifests/icml/2026-main.json`：来源、大小、SHA-256 和数量对账；
- `data/normalized/icml/2026-main.jsonl`：规范化论文；
- `data/analysis/icml/2026-main/`：收录范围和缺失情况；
- `data/releases/ICML/2026/`：不可原地修改的预发布版本；
- `notes/icml-2026-main-overview.md`：面向读者的中文范围说明。

ICML release 继续使用项目已有的六个核心文件格式，但在会议概览和来源信息中增加：

- `publication_status: preliminary_official_program`；
- `final_source_status: not_published`；
- `final_source_url: https://proceedings.mlr.press/v306/`；
- `analysis_availability`，明确 papers 可用，distribution、trends、advances 和 awards 暂不可用。

## 6. 程序结构

### 6.1 ICML adapter

新增 `src/conference_overview/adapters/icml.py`，只负责：

1. 读取和检查 ICML 官方分页数据；
2. 判断 Main Conference 身份；
3. 合并同一论文的多条展示记录；
4. 关联英文摘要；
5. 输出规范化论文、排除项和待处理项。

它不负责页面生成、主题分类或中文内容。

### 6.2 通用会议流程

当前采集流程偏向 ACL 的 BibTeX 和 volume HTML。本次把会议选择与 adapter 调用提取到通用入口，但保留 ACL 原有处理函数和输出内容：

```text
CLI request
    -> venue registry
    -> adapter dispatch
       |-- ACL adapter
       `-- ICML virtual adapter
    -> immutable snapshots
    -> canonical PaperRecord
    -> reconciliation report
    -> venue/year release
    -> Astro site
```

`collect`、`validate` 和 `build-site` 根据配置选择 adapter。ACL 2026 的源文件、分析结果、中文内容包和网页路由不得变化。

### 6.3 多会议网站读取

网站构建时读取所有已经选中的 venue/year release，而不是只读取 ACL 当前版本。每个 release 先独立通过 schema 检查，再进入站点数据集合。一个会议的数据错误不能被另一个会议的数据掩盖。

预发布 ICML release 只开放会议页、论文目录和英文摘要详情页。页面组件读取 `analysis_availability` 后决定显示哪些栏目，不用空图表或通用占位卡片模拟尚未完成的分析。

## 7. 页面设计

视觉稿位于 brainstorming 本地会话中，不进入 Git。正式实现延续当前网站的深蓝、钴蓝和浅灰色体系，不重新设计整站。

### 7.1 ICML 会议页

路径：`/conferences/icml/2026/`

桌面端采用左侧会议信息、右侧主要内容的双栏布局。第一屏保持紧凑，依次显示：

1. `ICML 2026`、Main Conference 和举办时间；
2. “预发布数据”状态条；
3. 当前收录数量、唯一纳入的 track 和最终对照来源；
4. 明确的“本次收录”和“本次不包含”列表；
5. 进入 ICML 论文目录的链接。

页面不显示主题分布、趋势、Advances 或奖项空卡片。说明文字使用普通中文，不把内部字段名直接展示给读者。

### 7.2 论文目录

路径：`/papers/`

现有目录增加会议筛选项 `ICML 2026`。搜索覆盖英文标题和作者；本轮没有中文摘要，因此搜索结果中也不显示中文内容入口。

每条 ICML 记录显示标题、作者、会议和官方链接。点击标题进入英文摘要详情页。ACL 论文原有中文摘要页和获奖深读页继续使用原来的链接。

### 7.3 ICML 论文详情页

路径：`/papers/<route-key>/`

页面按以下顺序显示：

1. 英文标题；
2. 作者和 `ICML 2026 · Main Conference`；
3. 官方英文摘要；
4. 数据来源和“等待 PMLR 最终对照”说明；
5. ICML 官方页面、OpenReview、PDF 和返回目录链接。

本轮不显示中文摘要模块，也不显示“中文摘要稍后补充”之类的空内容。官方数据没有摘要或 PDF 时，页面只说明对应信息暂未提供。

### 7.4 手机端

在 390 px 宽度下：

- 顶部导航使用现有折叠菜单；
- 会议页改为单列，标题不超过约两行的视觉高度；
- 论文筛选项纵向排列；
- 英文摘要正文不小于 16 px；
- 长标题、作者、OpenReview ID 和 URL 可以换行；
- 页面不产生横向滚动。

## 8. PMLR 发布后的最终对照

检测到 PMLR Volume 306 上线后，程序不会直接替换当前版本，而是先生成差异报告：

- ICML 预发布数据和 PMLR 的论文总数；
- 仅存在于一侧的论文；
- 标题、作者、摘要、PDF 和 DOI 的差异；
- 预发布阶段的待处理记录；
- 一一对应成功的论文数量。

只有所有 PMLR 论文都有明确对应关系、重复和待处理数量为零，并且收录范围确认仍是 Main Conference 时，才生成 `final_proceedings` release。切换后保留预发布快照和差异报告，不能原地改写历史数据。

## 9. 异常处理

- 官方分页链接缺失、形成循环或跨到非允许主机：停止导入；
- `count`、实际读取条数和分页记录无法对上：停止导入；
- 同一 OpenReview forum ID 的标题或作者冲突：列入待处理清单，不发布该论文；
- 未知 source group 或 decision：列入待处理清单，不猜测所属 track；
- 缺少摘要或 PDF：保留论文并公布缺失数量，不生成推测内容；
- source snapshot 的大小或 SHA-256 与 manifest 不一致：停止构建；
- ICML release schema 错误：不生成 ICML 页面；
- ACL release 错误或发生非预期变化：整站构建失败，不能用 ICML 页面掩盖回归；
- PMLR 仍返回 404：保留预发布状态，不反复创建相同版本。

## 10. 验收标准

### 10.1 Python

- registry 能把 `ICML / 2026 / main` 路由到 `icml_virtual` adapter；
- adapter 能读取多页官方响应，并能发现缺页、分页循环、跨主机和数量不一致；
- 只保留 `ICML.cc/2026/Conference` Main Conference 条目；
- Position、Journal-to-Conference 和其他来源组进入排除或待处理清单；
- oral、spotlight 和 poster 记录按 OpenReview forum ID 合并且不丢失展示信息；
- 标题或作者冲突会失败，不会静默覆盖；
- 英文摘要按官方 ID 关联，缺失数量准确；
- manifest 中 discovered、included、excluded、unresolved 和 duplicate-candidate 数量能够对上；
- 相同官方输入可重复生成相同的规范化 JSONL 和 release 文件；
- ACL 现有 Python 测试全部通过。

### 10.2 网站

- 首页出现 ICML 2026 卡片和“预发布”状态；
- `/conferences/icml/2026/` 可以访问并准确显示范围；
- `/papers/` 可以筛选 ICML 2026，并能按标题和作者搜索；
- 每篇已收录 ICML 论文都有唯一详情路由；
- ICML 详情页显示英文摘要和官方链接，不显示中文摘要空模块；
- distribution、trends、advances 和 awards 未开放时不生成误导性栏目；
- ACL 当前会议页、论文详情页和 30 个获奖页面保持可访问；
- Astro schema 检查和静态构建通过。

### 10.3 浏览器

- 桌面端检查会议页、论文目录、长标题详情页和缺少摘要的详情页；
- 390 × 844 视口下检查折叠菜单、筛选区、正文和按钮；
- `document.documentElement.scrollWidth - window.innerWidth <= 1`；
- 英文摘要计算字号至少为 16 px；
- GitHub Pages base path 下所有内部链接正确；
- 浏览器控制台没有脚本错误或资源 404。

### 10.4 真实官方数据

- 保存本次抓取的官方 URL、时间、文件字节数和 SHA-256；
- 报告官方 feed 中各 source group、decision 和展示类型的原始数量；
- 报告合并前活动记录数、合并后论文数、排除数、待处理数和摘要缺失数；
- 人工抽查 Main Conference、oral、spotlight、普通 poster、未知来源和重复展示记录；
- 完成 release 哈希检查和一次包含 ACL、ICML 两个会议的完整网站构建。

## 11. 发布边界

ICML 2026 预发布页面可以公开，但必须同时满足以下要求：

- 页面始终显示“来自 ICML 官方会议程序，等待 PMLR 最终对照”；
- 不使用“完整论文集”“最终收录”或同等含义的说法；
- 不基于当前数据发布主题分布、趋势、Advances 或获奖论文分析；
- 不把展示类型当作论文 track；
- 不把缺失摘要解释为论文没有摘要；
- PMLR 发布后保留差异报告和旧版本，完成检查后再切换状态。
