# AI Conference Overview

AI Conference Overview 是一个面向 AI 顶会的论文研究网站，集中展示接收论文的主题分布、值得关注的研究方向、跨论文进展和获奖论文中文解读。

**在线访问：[AI Conference Overview](https://smallflyingpig.github.io/ai-conference-overview/)**

当前版本收录 **ACL 2026 Long Papers**：从官方论文集发现 2,223 条记录，排除 1 条论文集前言后，共纳入 2,222 篇论文。由于目前只有 ACL 2026 一年的数据，网站展示的是当年论文分布，不能据此判断长期趋势。

## 网站里有什么

- **会议概览**：查看 ACL 2026 Long Papers 的论文规模、主题分布和主要研究问题。
- **分布与趋势**：比较各主题的论文数量与占比，并明确区分单年分布和多年趋势。
- **研究进展**：从 Text LLMs、Multimodal Models、Reasoning & Agents、Data & Training、Evaluation & Trust 五个方向梳理代表性工作。
- **获奖论文**：收录 30 篇官方获奖论文，提供三分钟导读、中文摘要、方法说明、关键结果、局限和研究启发。
- **论文索引**：浏览 2,222 篇论文，并按标题、作者和主题检索。
- **方法说明**：了解数据来源、分类方法、人工抽查结果和统计口径。

## 当前收录范围

| 会议 | 年份与 Track | 状态 |
| --- | --- | --- |
| ACL | 2026 Long Papers | 已完成论文收集、主题分类、人工抽查、研究综述和获奖论文解读 |
| EMNLP | 待接入 | 已定义数据适配方向 |
| ICLR | 待接入 | 已定义数据适配方向 |
| ICML | 2026 Main Conference | 接入和网页代码已完成；官方分页与 OpenReview 精确查询目前返回 403，因此尚未发布不完整的论文目录，等待官方接口恢复后再导入 |
| NeurIPS | 待接入 | 已定义数据适配方向 |
| CVPR | 待接入 | 已定义数据适配方向 |
| ICCV | 待接入 | 已定义数据适配方向 |
| ECCV | 待接入 | 已定义数据适配方向 |

仓库中的 `analyzing-conference-trends` skill 已包含这些会议的数据来源和分析规范。只有在完成相应会议、年份和 Track 的官方数据接入与质量检查后，网站才会展示对应结果。

## 如何理解网站中的分析

- 论文元数据来自官方论文集或会议官网。
- 论文实验结果会保留原始评测条件和对应位置，但不代表本项目独立复现了这些实验。
- 跨论文综述会列出所参考的具体论文，不会直接合并不可比较的指标。
- 主题占比按每篇论文的主要主题统计，不等同于多标签场景下某个主题的全部覆盖率。
- 人工抽查衡量已检查样本的分类准确程度，不能据此推断未发现主题的比例。
- 获奖论文页面只收录官方已经公布、且已完成论文 PDF 阅读的记录。
- 论文、图片、元数据和会议素材仍归原作者或原发布方所有。

## 仓库结构

```text
config/                     会议注册表与主题分类配置
data/                       官方数据、分类结果、分析结果和发布版本
site/                       Astro 静态网站
src/conference_overview/    数据收集、检查、分析与发布代码
tests/                      Python 测试
.agents/skills/             可复用的会议分析与中文润色 skill
```

## 安装环境

CI 使用 Python 3.11+ 和 Node.js 24。

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'

cd site
npm ci
npx playwright install chromium
cd ..
```

获奖信息允许访问的官方域名统一配置在 `config/venues.yaml`。修改 `official_award_hosts` 后，需要重新生成并检查前端使用的域名列表：

```bash
.venv/bin/python scripts/generate_award_host_policy.py
```

## 重新生成会议分析

项目使用 `conference-trends` 命令完成论文收集、检查、分类和发布。原始官方数据会保存为不可变版本；如果新数据未达到发布要求，程序不会替换上一个可用版本。

```bash
.venv/bin/conference-trends collect --venues ACL --years 2026 --tracks long
.venv/bin/conference-trends validate --venues ACL --years 2026 --tracks long
.venv/bin/conference-trends export-classification --venues ACL --years 2026 --tracks long

# 按导出的 JSONL 格式完成人工或 Agent 语义分类后再导入。
.venv/bin/conference-trends import-classification \
  --input <reviewed-classification-directory> \
  --venues ACL --years 2026 --tracks long

.venv/bin/conference-trends validate --venues ACL --years 2026 --tracks long --audit
.venv/bin/conference-trends awards --venue ACL --year 2026 --track long
.venv/bin/conference-trends analyze \
  --venues ACL --years 2026 --tracks long --write-release
```

主题分类、低置信度论文复查、分主题人工抽查、分类修正和获奖论文 PDF 阅读都需要明确的人工或 Agent 判断，不是无人值守的模型调用。当前发布版本由 `data/releases/ACL/2026/current.json` 选择，并使用 SHA-256 记录各文件内容。

### 导入 ICML 2026 Main Conference

ICML 没有 ACL 的 long/short 划分，本项目统一使用 `main`。Poster、Spotlight 和 Oral 只是展示形式，同一篇论文会合并为一条记录，不会被当成三个不同的 Track。

ICML 2026 的预发布数据以 OpenReview 中 `ICML.cc/2026/Conference` 的精确 venue ID 确定主会论文范围，再用 ICML 官网补充 session 和展示形式。Position Papers、Journal-to-Conference、Workshop、Tutorial 和 Expo 不在此范围内。PMLR Volume 306 上线后，项目会先生成差异报告，再决定是否切换到正式论文集版本。

```bash
# 先保存 ACL 当前版本，导入后用来确认 ACL 数据没有变化。
.venv/bin/python scripts/verify_icml_live_release.py \
  --write-acl-baseline /tmp/icml-import-acl-baseline.json --root .

.venv/bin/conference-trends collect \
  --venues ICML --years 2026 --tracks main
.venv/bin/conference-trends validate \
  --venues ICML --years 2026 --tracks main
.venv/bin/conference-trends analyze \
  --venues ICML --years 2026 --tracks main --write-release
.venv/bin/conference-trends reconcile-final \
  --venues ICML --years 2026 --tracks main

.venv/bin/python scripts/verify_icml_live_release.py \
  --acl-baseline /tmp/icml-import-acl-baseline.json --root .
```

只要官方分页、OpenReview 查询或总数对照失败，导入就会停止，也不会生成 `data/releases/ICML/2026/current.json`。项目不会改用第三方列表，也不会根据标题或 session 猜测论文所属 Track。

## 测试与本地预览

运行与 CI 相同的检查：

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q

cd site
npm test
npm run build
npm run test:e2e
npm run preview -- --host 127.0.0.1 --port 4321
```

打开 `http://127.0.0.1:4321/ai-conference-overview/`。Playwright 会检查桌面端和手机端布局、ACL 会议概览、研究进展、30 篇获奖论文、内部链接、页面响应和浏览器错误。

项目也支持在没有会议数据时安全构建：

```bash
mkdir -p /tmp/ai-conference-overview-empty-releases
cd site
CONFERENCE_RELEASE_ROOT=/tmp/ai-conference-overview-empty-releases npm run build
```

此时网站只生成基础页面，不会自动补造会议数据。

## GitHub Pages 部署

`.github/workflows/ci.yml` 负责常规检查，`.github/workflows/pages.yml` 负责 GitHub Pages 发布。每次向 `main` 推送后，Pages workflow 会依次运行 Python 检查、站点单测、空数据构建、正式构建和浏览器测试，通过后再上传并部署 `site/dist`。

查看部署进度：

```bash
gh run watch --exit-status
```

部署完成后访问：

```text
https://smallflyingpig.github.io/ai-conference-overview/
```

项目不会默认定时更新会议数据，因为会议论文集和获奖信息在公布阶段可能暂时不完整。

## 许可证

本项目编写的代码、配置、文档和网站说明使用 [MIT License](LICENSE)。通过链接引用的论文及其他第三方内容不包含在该许可证内。
