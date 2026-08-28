# ACL 2026 Findings 接入与分析设计

日期：2026-08-28
状态：Spec 已通过，可进入实施
适用范围：ACL 2026 Findings

## 1. 目标

把 ACL Anthology 已发布的 ACL 2026 Findings 作为独立 Track 接入 AI Conference Overview，并分两阶段上线：

1. 第一阶段提供完整论文清单、英文摘要、检索和论文详情；
2. 第二阶段完成 AI 辅助主题分类、质量检查、中文摘要、主题分布和研究进展。

Findings 与 ACL 2026 Long Papers 使用不同的论文集合和统计分母。现有 Long Papers 页面、30 篇获奖论文解读、不可变数据版本及公开链接不得发生变化。

## 2. 官方来源与已确认范围

唯一用于确认论文收录范围的来源是 ACL Anthology：

- 卷页面：`https://aclanthology.org/volumes/2026.findings-acl/`
- BibTeX：`https://aclanthology.org/volumes/2026.findings-acl.bib`
- `source_key`：`2026.findings-acl`
- `venue`：`ACL`
- `year`：`2026`
- `track`：`findings`

2026-08-27 的只读检查结果：

- BibTeX `Content-Length`：1,785,439 字节；
- `@inproceedings`：2,163 条；
- `@proceedings`：1 条；
- 纳入论文：2,163 篇；
- 排除卷首记录：1 条。

这些数值是本次设计的起始数据，不写成长期不变的常量。正式采集仍需记录当次响应的 URL、时间、字节数和 SHA-256，并重新计算论文数量。

## 3. 不在本次范围内的内容

- 不把 Findings 合并进 Long Papers 的主题分布或统计分母；
- 不把 ACL Workshops、Short Papers 或其他卷收入 Findings；
- 不为 Findings 继承或复制 Long Papers 的获奖论文；
- 不把 Long 与 Findings 的数量差异描述为研究趋势；
- 第一阶段不生成中文摘要、主题图表或研究进展占位内容；
- 本设计不调整 ACL 2026 Long Papers 已发布数据的内容与哈希。

## 4. 多 Track 数据结构

### 4.1 兼容现有 Long Papers

采用兼容式多 Track 结构，不迁移现有 114MB ACL 2026 Long Papers release：

```text
data/releases/ACL/2026/
├── current.json                 # 现有 Long Papers，保持不变
├── generations/                # 现有 Long Papers，保持不变
└── tracks/
    └── findings/
        ├── current.json
        └── generations/<sha256>/
```

`config/venues.yaml` 为 ACL 2026 增加 `default_track: long`，并注册 `findings`。默认 Track 继续使用年份根目录；非默认 Track 使用 `tracks/<track>/`。这一规则应实现为共享路径解析函数，Python 生产端和网站读取端不得各自猜测路径。

为了避免前端重复维护会议配置，从 `config/venues.yaml` 生成一份经过检查的前端 release selector 文件。CI 检查生成结果是否与注册表一致。selector 至少包含 `venue`、`year`、`track` 和安全的 release 相对路径。

### 4.2 其他数据目录

沿用现有 `ScopePaths` 结构：

```text
data/manifests/acl/2026-findings.json
data/normalized/acl/2026-findings.jsonl
data/snapshots/acl/2026-findings/
data/analysis/acl/2026-findings/
data/classification/acl/2026-findings/
notes/acl-2026-findings-overview.md
```

Findings 不生成 award records、award deep reads 或 award PDF provenance。

## 5. 数据采集与检查

### 5.1 通用 ACL Anthology adapter

现有 ACL parser 已能根据 `VenueRequest` 解析 BibTeX、论文 ID、摘要、PDF 和 DOI，但 `conference_pipeline.collect_scope` 仍把 ACL 2026 Long Papers 写成固定组合。实现时应：

- 在注册表中给 ACL Track 明确配置 `adapter: acl_anthology`；
- 按 adapter 分派 ACL 数据采集，而不是判断 `ACL/2026/long`；
- 让 `collect_acl_scope`、`validate_acl_scope` 和 papers-only 分析读取任意受支持的 ACL Anthology Track；
- 保留论文原始 Track，不把 Findings 伪装成 `long`。

### 5.2 下载完整性

ACL Anthology 的大文件响应可能提前结束但仍返回成功状态。本项目已经在只读检查中观察到 BibTeX 第一次只取得 720,896 字节，而响应头声明 1,785,439 字节。因此采集必须同时检查：

- 实际字节数与 `Content-Length` 一致；
- BibTeX 以完整条目结束；
- 声明条目数与 parser 解析条目数一致；
- HTML 和 BibTeX 中的论文 ID 集合一致；
- 下载不完整时可以安全续传或重新下载，但不能写入规范化数据和 release。

### 5.3 数量关系

每次采集都重新计算并保存：

```text
discovered = included + excluded + unresolved
```

可以发布第一阶段数据的前提是：

- `included = 2163`，除非官方卷发生了可解释且已记录的变化；
- 卷首记录单独排除；
- `unresolved = 0`；
- 没有确定的重复论文；
- BibTeX、HTML、论文 landing page 的身份能够对应；
- 摘要、PDF、DOI 缺失情况被准确记录。

如果官方数据后来变化，生成增删差异报告，不静默改写旧快照。

## 6. 第一阶段：论文清单版

第一阶段执行：

```bash
conference-trends collect --venues ACL --years 2026 --tracks findings
conference-trends validate --venues ACL --years 2026 --tracks findings
conference-trends analyze --venues ACL --years 2026 --tracks findings --write-release
```

这一步生成严格的六文件不可变 release：

```text
papers.json
papers.csv
overview.json
overview.md
validation.json
provenance.json
```

`analysis_availability` 设置为：

```text
papers = true
distribution = false
trends = false
advances = false
awards = false
```

论文详情页显示标题、作者、ACL 2026 Findings、英文摘要、DOI、PDF 和 ACL Anthology 页面。未完成的内容直接不显示，不使用空图表或通用占位卡片。

任何数据检查、schema、六文件哈希或 `current.json` 检查失败时，不创建或更新 Findings 当前版本，也不影响 Long Papers 当前版本。

## 7. 第二阶段：完整分析版

### 7.1 AI 辅助主题分类

基于 2,163 篇论文的 title + abstract 导出分类输入。每篇论文必须包含：

- 一个 primary topic；
- 零个或多个不重复的 secondary topics；
- confidence；
- 简短分类理由；
- taxonomy version；
- AI 辅助复核状态。

分类输入和输出的 paper ID 必须精确一致，不得缺失、重复或增加记录。摘要存在时不得只根据标题分类。

### 7.2 分类质量检查

- 逐篇检查所有低置信度分类；
- 每个 primary topic 最多抽查 50 篇，少于 50 篇时全部检查；
- 抽样记录绑定当前分类结果、样本和处理结果的 SHA-256；
- 修改分类结果或 taxonomy 后，受影响的旧抽查结果失效。

主题进入正式会议概览需要同时满足：

- 抽查准确率不低于 90%；
- Wilson 95% 置信区间下界不低于 80%。

未达到标准的主题暂不用于概括 Findings 的主要方向。

### 7.3 中文摘要

为每篇 Findings 论文生成覆盖核心内容的中文摘要，至少说明：

- 研究问题；
- 核心方法；
- 论文报告的主要发现；
- 适用范围或重要限制。

中文摘要不逐段翻译，不补写摘要和论文未披露的实验结果。生成结果必须绑定 Findings release 和 `papers.json` SHA-256；抽样检查事实一致性和中文可读性后才能公开。

### 7.4 主题分布与研究进展

主题分布只使用 Findings 的 2,163 篇论文作为分母。页面同时显示论文数、占比、taxonomy version 和抽查状态。

研究进展按以下五类组织：

- Text LLMs；
- Multimodal Models；
- Reasoning & Agents；
- Data & Training；
- Evaluation & Trust。

每条综合列出代表论文和官方链接，并区分论文报告的内容、多篇论文共同呈现的方向和进一步判断。单年数据只描述主题分布、当年研究热点和技术问题，不使用“增长”“上升”或“长期趋势”等表述。

## 8. 网页信息结构

### 8.1 会议列表和会议页面

`/conferences/` 将 ACL 2026 显示为两个独立入口：

- ACL 2026 Long Papers：2,222 篇；
- ACL 2026 Findings：2,163 篇。

现有 Long Papers 地址保持不变：

```text
/conferences/acl/2026/
```

Findings 使用新地址：

```text
/conferences/acl/2026/findings/
```

两个页面共享会议页组件，但输入始终包含 Track。页面标题、统计范围、数据来源和链接文案必须明确写出 Long Papers 或 Findings。

### 8.2 论文索引

论文索引增加 Track 筛选，并把 Track 写入可分享查询参数。搜索结果显示会议、年份和 Track。现有论文详情路由继续使用 producer 生成的唯一 route key；`2026.acl-long.*` 和 `2026.findings-acl.*` 不得发生碰撞。

### 8.3 研究进展

研究进展的筛选键从 `venue + year` 扩展为 `venue + year + track`。第二阶段完成后增加：

```text
/advances/?venue=ACL&year=2026&track=findings#advance-ACL-2026-findings
```

默认页面分别列出 ACL Long、ACL Findings 和 ICML Main，不合并跨 Track 分析。

### 8.4 获奖论文与趋势

- Awards 只显示实际存在且正式查证的 Track；Findings 不生成空分组，也不显示 Long Papers 的 30 篇获奖论文；
- Trends 将 Long 和 Findings 作为两个独立单年数据集；
- 不绘制 Long 与 Findings 的伪时间折线，不把论文数量差异解释为研究方向变化。

### 8.5 方法说明

方法页面显示 Findings 的官方来源、抓取时间、SHA-256、论文范围、缺失字段、分类方法、抽查结果和单年数据限制。第一阶段只显示论文采集和完整性信息；第二阶段再增加分类与中文摘要说明。

## 9. 前端与数据安全

- 路径解析拒绝 `..`、绝对路径、符号链接逃逸和非法 Track；
- `current.json` 必须指向同一 Track 下的 `generations/<sha256>`；
- 六个文件的实际 SHA-256 必须与 pointer 一致；
- release 中每篇论文的 `venue/year/track` 必须与 selector 一致；
- 一个 Track 的读取错误不能由另一个 Track 的可用数据掩盖；
- Findings 构建失败时，ACL Long 和 ICML 页面仍使用原有不可变版本。

## 10. 测试与验收

### 10.1 Python

- registry 能解析 `ACL/2026/findings`，默认 Track 仍为 `long`；
- ACL pipeline 按 `acl_anthology` adapter 分派，不再只允许 long；
- 截断 BibTeX、截断 HTML、条目数不一致和 ID 集不一致均停止处理；
- 2,163 篇论文和 1 条卷首记录正确分开；
- Long 与 Findings 的 release 路径、pointer 和哈希相互独立；
- 第一阶段不会生成分类、研究进展或 award 内容；
- Ruff 和 Python 全量测试通过。

### 10.2 网站单测

- 前端 selector 由注册表生成且与 Python 路径规则一致；
- 同一 venue/year 的多个 Track 可以同时加载；
- conference route、paper filter 和 advance filter 包含正确 Track；
- Findings 不显示 award 分组；
- Long 与 ICML 现有 release 继续通过 schema 和哈希检查；
- 空数据构建继续成功。

### 10.3 浏览器验收

桌面端与 390px 手机端检查：

- 会议列表可以分别进入 Long 和 Findings；
- `/conferences/acl/2026/` 仍显示 Long Papers；
- `/conferences/acl/2026/findings/` 显示 2,163 篇 Findings；
- Papers 的 Track 筛选、搜索和详情链接正常；
- 第二阶段完成前不出现 Findings 主题分布和研究进展；
- 第二阶段完成后，Findings research advances 的分享 URL 正确；
- Findings 不出现获奖论文入口；
- GitHub Pages base path 下没有 404、控制台错误或横向溢出。

## 11. 发布顺序

1. 保存 ACL Long 当前 release 的 pointer 和六文件 SHA-256；
2. 实现多 Track 路径、ACL 通用 adapter 分派及测试；
3. 采集并发布 Findings papers-only release；
4. 完整构建同时包含 ACL Long、ACL Findings 和 ICML；
5. 本地检查桌面端与手机端；
6. 推送 `main`，等待 CI 和 GitHub Pages 成功；
7. 带 cache-busting 查询访问公开 Findings 页面，确认论文数量、Track、筛选和详情路由；
8. 第二阶段完成分类、中文摘要和研究进展后，重复完整发布流程。

只有公开网站已经显示与选中不可变 release 一致的内容，第一阶段或第二阶段才算完成。单纯完成采集、本地构建或触发 Pages workflow 都不算发布结束。

## 12. 失败处理

以下情况停止当前阶段，不更新 Findings `current.json`：

- 官方响应下载不完整；
- BibTeX、HTML 或 landing page 的论文身份无法对应；
- 数量关系不成立，存在待处理记录或确定的重复论文；
- release 文件不完整、哈希不一致或 scope 混入其他 Track；
- 第二阶段分类不完整、低置信度记录未处理或主题抽查未达到要求；
- 中文摘要无法绑定当前论文版本；
- 网站 schema、路由、桌面端或手机端检查失败；
- CI、Pages 或公开网址检查失败。

失败时保留诊断文件和上一个可用版本，报告具体失败环节，不降低检查要求，也不影响 ACL Long 的线上内容。
