# Paper Chinese Reading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ACL 2026 的 2,192 篇普通 long paper 生成 150–250 字中文摘要页，并把 30 篇获奖论文改造成适合学习的中文深度解读页。

**Architecture:** 保留现有六文件 release，在 `data/content/` 下新增与 release generation、`papers.json` SHA-256 严格对应的不可变中文内容包。Python 负责导出、导入、完整性检查和内容包写入；Astro 只读取通过 Zod 检查的内容，按 paper ID 将 2,192 篇普通论文路由到摘要页、30 篇获奖论文路由到深读页。

**Tech Stack:** Python 3.12、Pydantic v2、Typer、pytest、Astro、TypeScript、Zod、React、Vitest、Playwright。

**Spec:** `docs/superpowers/specs/2026-08-25-paper-chinese-reading-design.md`

## Global Constraints

- 当前 ACL 2026 long-paper 范围固定为 2,222 篇：2,192 篇普通论文、30 篇官方获奖论文。
- 普通论文 `summary_zh` 必须为 150–250 个中文字符，并覆盖研究问题、核心方法和主要发现。
- 获奖论文必须依据已保存 SHA-256 的官方 PDF 编写中文深读，不能用普通摘要代替。
- 默认展示中文；英文 abstract 和英文 DeepRead 保留为可展开的原文参考。
- 模型名、数据集、benchmark、指标、公式、paper ID 和 SHA-256 保留精确英文。
- 数字只能来自对应官方 abstract 或 PDF；不扩大肯定、否定、因果关系或适用范围。
- 缺少网页 abstract 的论文必须使用官方 PDF；两者都不可用时停止完整内容包发布。
- 保留现有 release 的正好六个文件；中文内容使用独立不可变 generation 和 pointer。
- 所有站内链接必须支持 GitHub Pages base path `/ai-conference-overview/`。
- 不推送、不发布；本地页面交给用户 review 并获得许可后，才能进入 GitHub Pages 发布步骤。

---

## File Structure

### Python content domain

- Create: `src/conference_overview/chinese_content.py` — Pydantic models、来源绑定、字符统计、paper ID 覆盖和内容包检查。
- Create: `src/conference_overview/content_pipeline.py` — source batch 导出、summary/deep-read 导入、canonical JSONL、manifest 和 immutable generation 写入。
- Modify: `src/conference_overview/cli.py` — `export-chinese-content`、`import-chinese-content`、`build-chinese-content` 命令。
- Test: `tests/test_chinese_content.py` — 单条内容和完整 bundle 的失败场景。
- Test: `tests/test_content_pipeline.py` — 确定性分片、导入、manifest、pointer 和原子写入。

### Authored content

- Create: `docs/content/paper-summary-zh-guide.md` — 普通摘要与获奖深读的写作规则、正反例和数字处理方式。
- Create: `data/content/acl/2026-long/source-batches/*.jsonl` — 16 个确定性普通论文输入分片与 1 个获奖输入分片。
- Create: `data/content/acl/2026-long/authored/paper-summaries-*.zh.jsonl` — 16 个普通论文中文摘要分片。
- Create: `data/content/acl/2026-long/authored/award-deep-reads.zh.jsonl` — 30 篇获奖论文中文深读。
- Create: `data/content/acl/2026-long/review/summary-review-samples.json` — 按主要主题确定性抽取的中文摘要复读样本。
- Create: `data/content/acl/2026-long/review/summary-review-decisions.json` — 样本逐条判断与修改记录。
- Create: `data/content/acl/2026-long/generations/<sha256>/` — 三个正式内容文件。
- Create: `data/content/acl/2026-long/current.json` — 绑定 release generation 与 content generation 的指针。

### Site data and pages

- Create: `site/src/lib/content-schema.ts` — 与 Python 模型一致的 Zod schema 和跨文件检查。
- Create: `site/src/lib/content-data.ts` — 安全读取 content pointer、hash 检查、release 绑定和 fail-closed loader。
- Create: `site/src/lib/paper-reading.ts` — route key、普通/获奖映射和页面 view model。
- Create: `site/src/components/PaperReadingNav.astro` — 详情页页内学习导航。
- Create: `site/src/components/PaperSummarySections.astro` — 普通论文中文摘要结构。
- Create: `site/src/components/AwardQuickRead.astro` — 获奖论文“三分钟读懂”。
- Create: `site/src/pages/papers/[paperId].astro` — 2,192 个普通论文详情页。
- Modify: `site/src/pages/papers/index.astro` — 中文搜索字段和普通/获奖目标路由。
- Modify: `site/src/pages/awards/[paperId].astro` — 中文摘要优先的深读顺序。
- Modify: `site/src/pages/methodology.astro` — 中文内容覆盖、制作方法和抽查说明。
- Modify: `site/src/styles/global.css` — 阅读页排版、页内导航、长英文换行和移动端样式。
- Test: `site/tests/content-data.test.ts` — pointer、hash、schema、release mismatch 和 coverage。
- Test: `site/tests/paper-reading.test.ts` — route、view model 和两级内容分离。
- Modify: `site/tests/routes.test.ts` — 2,192 + 30 路由集合。
- Modify: `site/tests/visual.spec.ts` — 中文优先、原文折叠、站内链接和移动端阅读。

---

### Task 1: Define Chinese content contracts and writing guide

**Files:**
- Create: `src/conference_overview/chinese_content.py`
- Create: `tests/test_chinese_content.py`
- Create: `docs/content/paper-summary-zh-guide.md`

**Interfaces:**
- Consumes: `PaperRecord`, `DeepRead`, award paper ID set, release generation and `papers.json` SHA-256.
- Produces: `PaperSummaryZh`, `AwardQuickReadZh`, `AwardDeepReadZh`, `ContentManifest`, `ContentPointer`, `ChineseContentBundle`, `validate_chinese_content_bundle(...)`.

- [ ] **Step 1: Write failing model tests**

```python
def test_paper_summary_requires_150_to_250_chinese_characters() -> None:
    with pytest.raises(ValidationError):
        paper_summary(summary_zh="太短")

def test_bundle_requires_exact_partition_of_all_paper_ids() -> None:
    with pytest.raises(ContentPublicationBlocked, match="paper ID coverage"):
        validate_chinese_content_bundle(
            papers=[paper("p1"), paper("p2")],
            award_ids={"p2"},
            summaries=[paper_summary(paper_id="p1")],
            award_deep_reads=[],
            release_generation="generations/" + "a" * 64,
            papers_sha256="b" * 64,
        )

def test_numeric_chinese_claim_requires_source_token() -> None:
    with pytest.raises(ContentPublicationBlocked, match="numeric token"):
        validate_summary_sources(
            paper_summary(main_findings="准确率达到 99.9%。"),
            source_text="The method improves accuracy.",
        )
```

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `.venv/bin/python -m pytest tests/test_chinese_content.py -q`

Expected: FAIL because `conference_overview.chinese_content` does not exist.

- [ ] **Step 3: Implement strict Pydantic models**

```python
class PaperSummaryZh(BaseModel):
    schema_version: Literal["paper-summary-zh-v1"]
    paper_id: str
    route_key: str
    venue: str
    year: int
    track: str
    source_title: str
    source_abstract_sha256: str | None
    source_pdf_sha256: str | None = None
    one_sentence: str
    summary_zh: str
    research_problem: str
    core_method: str
    main_findings: str
    scope_and_limitations: str
    content_method: Literal[
        "title-abstract-grounded-summary-v1",
        "official-pdf-grounded-summary-v1",
    ]

class AwardQuickReadZh(BaseModel):
    research_problem: str
    core_method: str
    main_finding: str

class AwardDeepReadZh(BaseModel):
    schema_version: Literal["award-deep-read-zh-v1"]
    paper_id: str
    source_pdf_sha256: str
    quick_read: AwardQuickReadZh
    abstract_zh: str
    background: tuple[str, ...]
    method_walkthrough: tuple[str, ...]
    why_it_matters: tuple[str, ...]
    limitations: tuple[str, ...]
    research_implications: tuple[str, ...]
```

Count Chinese characters with Unicode ranges, trim every public string, require non-empty tuple items, and require exactly one source binding: abstract SHA for abstract-grounded content or PDF SHA for PDF-grounded content.

Define ordinary `route_key` as `paper-` plus the full SHA-256 of the UTF-8 paper ID. Validate the prefix and 64 lowercase hexadecimal characters. `ContentPointer` contains `generation`, `release_generation`, `papers_sha256` and exact hashes for the three content artifacts.

- [ ] **Step 4: Implement bundle-level checks**

`validate_chinese_content_bundle(...)` must:

- reparse every model from `model_dump()` to block `model_copy` bypasses;
- require ordinary summary IDs to equal all non-award paper IDs;
- require Chinese deep-read IDs to equal all verified award IDs;
- reject overlap, duplicates, unknown IDs and missing IDs;
- compare title, venue, year and track with `PaperRecord`;
- recompute every ordinary `route_key` from the full paper ID and reject collisions;
- compare abstract SHA-256 with normalized official abstract bytes;
- compare award PDF SHA-256 with existing verified PDF provenance;
- reject any Arabic-number token in Chinese fields that is absent from title + abstract or the bound DeepRead source text.

- [ ] **Step 5: Write the authoring guide**

The guide must define the exact 150–250-character rule, the six ordinary fields, the eight award sections, natural-Chinese examples, forbidden unsupported statements, rules for English terms, and the instruction “信息不足时直接说明，不补写通用局限”。

- [ ] **Step 6: Run tests and lint**

Run: `.venv/bin/python -m pytest tests/test_chinese_content.py -q`

Run: `.venv/bin/ruff check src/conference_overview/chinese_content.py tests/test_chinese_content.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/conference_overview/chinese_content.py tests/test_chinese_content.py docs/content/paper-summary-zh-guide.md
git commit -m "feat: define Chinese paper content contracts"
```

---

### Task 2: Build deterministic export, import, and immutable content packages

**Files:**
- Create: `src/conference_overview/content_pipeline.py`
- Modify: `src/conference_overview/cli.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Create: `tests/test_content_pipeline.py`

**Interfaces:**
- Consumes: `PaperSummaryZh`, `AwardDeepReadZh`, `ChineseContentBundle`, validated release selected by `current.json`.
- Produces: `export_chinese_content_sources(...) -> list[Path]`, `check_chinese_content_sources(...) -> SourceCoverage`, `load_authored_content(...) -> tuple[list[PaperSummaryZh], list[AwardDeepReadZh]]`, `write_chinese_content_bundle(...) -> Path` and four CLI commands.

- [ ] **Step 1: Write failing export tests**

```python
def test_export_partitions_non_awards_into_16_numeric_id_shards(tmp_path: Path) -> None:
    paths = export_chinese_content_sources(release_root, tmp_path, shard_count=16)
    ordinary = [path for path in paths if "paper-summary" in path.name]
    assert len(ordinary) == 16
    assert set(read_ids(ordinary)) == expected_non_award_ids
    assert read_ids(ordinary) == sorted(expected_non_award_ids, key=acl_numeric_suffix)

def test_export_puts_all_awards_in_a_separate_pdf_grounded_batch(tmp_path: Path) -> None:
    paths = export_chinese_content_sources(release_root, tmp_path, shard_count=16)
    assert read_ids([tmp_path / "award-deep-read-source.jsonl"]) == expected_award_ids

def test_export_fetches_and_hashes_pdf_when_web_abstract_is_missing(
    tmp_path: Path, respx_mock: MockRouter
) -> None:
    respx_mock.get(MISSING_ABSTRACT_PDF_URL).mock(
        return_value=Response(200, content=complete_pdf_fixture())
    )
    row = export_missing_abstract_source(missing_abstract_paper(), tmp_path)
    assert row["source_pdf_sha256"] == sha256(complete_pdf_fixture()).hexdigest()
    assert "paper body marker" in row["source_text"]
```

- [ ] **Step 2: Run the export tests and confirm RED**

Run: `.venv/bin/python -m pytest tests/test_content_pipeline.py -q`

Expected: FAIL because export functions are absent.

- [ ] **Step 3: Implement deterministic source export**

Ordinary source rows contain only `paper_id`, title, official abstract, topic, authors, official URLs and source hashes. Assign a paper to shard `numeric_suffix % 16`; sort every shard numerically. Award source rows additionally contain the validated English DeepRead and verified PDF provenance. Write canonical UTF-8 JSONL with a terminal newline.

Add `pypdf>=5,<7` as a direct dependency. For the one ordinary paper without a webpage abstract, fetch its official PDF with the same content-length, `%PDF` and `%%EOF` checks used for award PDFs, calculate SHA-256 from received bytes, and extract text with `pypdf.PdfReader`. Keep PDF bytes outside Git; export only the hash, byte size, official URL and extracted source text needed for authoring.

- [ ] **Step 4: Write failing import and pointer tests**

```python
def test_import_rejects_a_rehashed_but_stale_abstract(tmp_path: Path) -> None:
    authored = write_authored_summary(source_abstract_sha256="0" * 64)
    with pytest.raises(ContentPublicationBlocked, match="abstract SHA-256"):
        load_authored_content([authored], award_path, current_release)

def test_writer_publishes_three_files_and_atomic_pointer(tmp_path: Path) -> None:
    generation = write_chinese_content_bundle(valid_bundle, tmp_path)
    assert sorted(path.name for path in generation.iterdir()) == [
        "award-deep-reads.zh.jsonl",
        "content-manifest.json",
        "paper-summaries.zh.jsonl",
    ]
    pointer = json.loads((tmp_path / "current.json").read_text())
    assert pointer["release_generation"] == valid_bundle.release_generation
    assert pointer["papers_sha256"] == valid_bundle.papers_sha256
```

- [ ] **Step 5: Implement import and immutable writer**

Write files to a temporary sibling directory, calculate file SHA-256 values, derive generation ID from canonical `content-manifest.json`, rename the completed directory into `generations/<sha256>`, and atomically replace `current.json`. Reject symlinks, path traversal, unexpected generation files and any attempt to overwrite different bytes at an existing generation.

- [ ] **Step 6: Add CLI commands**

```text
conference-trends export-chinese-content --venue ACL --year 2026 --track long --shards 16
conference-trends check-chinese-content-sources --venue ACL --year 2026 --track long
conference-trends import-chinese-content --venue ACL --year 2026 --track long --summaries-dir <dir> --awards <file>
conference-trends build-chinese-content --venue ACL --year 2026 --track long
```

`import-chinese-content --allow-incomplete` performs row-level and selected-shard membership checks, reports missing IDs and never writes `current.json`. Without that flag, incomplete coverage fails. Every failure returns exit code 2 and a structured JSON error without changing `current.json`.

- [ ] **Step 7: Run focused and CLI tests**

Run: `.venv/bin/python -m pytest tests/test_content_pipeline.py tests/test_cli.py -q`

Run: `.venv/bin/ruff check src/conference_overview/content_pipeline.py src/conference_overview/cli.py tests/test_content_pipeline.py`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/conference_overview/content_pipeline.py src/conference_overview/cli.py pyproject.toml uv.lock tests/test_content_pipeline.py tests/test_cli.py
git commit -m "feat: build immutable Chinese content packages"
```

---

### Task 3: Add a fail-closed site content loader

**Files:**
- Create: `site/src/lib/content-schema.ts`
- Create: `site/src/lib/content-data.ts`
- Create: `site/tests/content-data.test.ts`
- Create: `site/tests/fixtures/task-content/`

**Interfaces:**
- Consumes: release returned by `loadOverview(...)` and `data/content/<venue>/<year>-<track>/current.json`.
- Produces: `loadChineseContent(release: LoadedOverview, contentRoot?: string): Promise<LoadedChineseContent | null>`.

- [ ] **Step 1: Generate a minimal Python-authored fixture**

Use the Python writer from Task 2 to create a two-paper fixture containing one ordinary summary and one award deep read. Do not handcraft hashes in TypeScript.

- [ ] **Step 2: Write failing Zod and loader tests**

```ts
it("loads only content bound to the selected release and papers hash", async () => {
  const release = await loadOverview("ACL", 2026, releaseRoot, "long");
  const content = await loadChineseContent(release!, contentRoot);
  expect(content?.paperSummaries).toHaveLength(1);
  expect(content?.awardDeepReads).toHaveLength(1);
});

it.each(["release_generation", "papers_sha256", "artifact_sha256"])(
  "rejects a forged %s binding",
  async (field) => expect(loadMutatedContent(field)).rejects.toThrow(),
);
```

- [ ] **Step 3: Run focused Vitest and confirm RED**

Run: `cd site && npm test -- --run tests/content-data.test.ts`

Expected: FAIL because content schema and loader do not exist.

- [ ] **Step 4: Implement exact Zod schemas**

Mirror every Python field with `.strict()`. Add refinements for unique IDs, disjoint ordinary/award sets, manifest count equality, canonical sort order and exact artifact hashes. Do not use `Number` to compare hashes or counts encoded as strings.

- [ ] **Step 5: Implement secure loader**

Follow `site/src/lib/data.ts`: reject symlinked roots/files, require paths to remain inside their canonical roots, require exactly three generation files, hash raw bytes before JSON parsing, and compare pointer `release_generation` plus `papers_sha256` with the loaded release.

- [ ] **Step 6: Run focused and full site data tests**

Run: `cd site && npm test -- --run tests/content-data.test.ts tests/data.test.ts`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add site/src/lib/content-schema.ts site/src/lib/content-data.ts site/tests/content-data.test.ts site/tests/fixtures/task-content
git commit -m "feat: load release-bound Chinese paper content"
```

---

### Task 4: Produce and publish 30 award-paper Chinese deep reads

**Files:**
- Create: `data/content/acl/2026-long/source-batches/award-deep-read-source.jsonl`
- Create: `data/content/acl/2026-long/authored/award-deep-reads.zh.jsonl`
- Modify: `site/src/pages/awards/[paperId].astro`
- Create: `site/src/components/AwardQuickRead.astro`
- Modify: `site/src/components/AwardEvidenceSections.tsx`
- Modify: `site/src/styles/global.css`
- Modify: `site/tests/evidence.test.ts`
- Modify: `site/tests/visual.spec.ts`

**Interfaces:**
- Consumes: 30 verified award IDs, official PDF hashes, English DeepRead, `AwardDeepReadZh`.
- Produces: 30 authored Chinese deep reads and an award page whose default reading path is entirely Chinese.

- [ ] **Step 1: Export and verify the 30-record source batch**

Run: `.venv/bin/conference-trends export-chinese-content --venue ACL --year 2026 --track long --shards 16`

Check: award source file has 30 unique IDs, every row has `source_pdf_sha256`, and the set exactly equals the current verified award set.

- [ ] **Step 2: Write failing award-page tests**

```ts
it("renders every award with Chinese quick read before English source text", async () => {
  for (const route of awardRoutes) {
    const html = await renderRoute(route);
    expect(html).toContain("三分钟读懂");
    expect(html).toContain("中文摘要");
    expect(html.indexOf("三分钟读懂")).toBeLessThan(html.indexOf("英文原文参考"));
    expect(html).not.toContain("仍在整理中");
  }
});
```

- [ ] **Step 3: Author all 30 deep reads**

For every source row, read the bound PDF/English DeepRead and write all `AwardDeepReadZh` fields. Preserve exact model, dataset, benchmark and metric names. When a number appears, copy its experiment setting into the same paragraph or the adjacent result card. Write “为什么值得关注” as editorial interpretation, never as an invented official award citation.

- [ ] **Step 4: Validate all 30 records**

Run: `.venv/bin/conference-trends import-chinese-content --venue ACL --year 2026 --track long --summaries-dir data/content/acl/2026-long/authored --awards data/content/acl/2026-long/authored/award-deep-reads.zh.jsonl`

Expected at this phase: ordinary coverage is reported incomplete, while all 30 award records pass their individual schema, PDF binding and ID-set checks. The command must not publish `current.json` until ordinary coverage is complete.

- [ ] **Step 5: Rebuild the award reading layout**

Render `AwardQuickRead`, Chinese abstract, background, method walkthrough, key results, why it matters, limitations and research implications before a collapsed `<details>` titled “英文原文参考”. Keep the existing metric/value/setting/locator components inside the English reference section.

- [ ] **Step 6: Run award tests and build**

Run: `cd site && npm test -- --run tests/evidence.test.ts tests/visual.spec.ts`

Run: `cd site && npm run check && npm run build`

Expected: all 30 award routes render complete Chinese sections; build still succeeds with fixture content.

- [ ] **Step 7: Commit**

```bash
git add data/content/acl/2026-long/source-batches/award-deep-read-source.jsonl data/content/acl/2026-long/authored/award-deep-reads.zh.jsonl site/src/pages/awards/'[paperId]'.astro site/src/components/AwardQuickRead.astro site/src/components/AwardEvidenceSections.tsx site/src/styles/global.css site/tests/evidence.test.ts site/tests/visual.spec.ts
git commit -m "feat: add Chinese deep reads for award papers"
```

---

### Task 5: Produce 2,192 ordinary-paper summaries in reviewable shards

**Files:**
- Create: `data/content/acl/2026-long/source-batches/paper-summary-source-00.jsonl` through `paper-summary-source-15.jsonl`
- Create: `data/content/acl/2026-long/authored/paper-summaries-00.zh.jsonl` through `paper-summaries-15.zh.jsonl`

**Interfaces:**
- Consumes: the 16 deterministic source shards and `docs/content/paper-summary-zh-guide.md`.
- Produces: 16 schema-valid authored shards whose union is exactly the 2,192 non-award paper IDs.

- [ ] **Step 1: Check source shard membership**

Run: `.venv/bin/conference-trends check-chinese-content-sources --venue ACL --year 2026 --track long`

Expected: 16 ordinary shards, 2,192 unique IDs, no award IDs, numeric modulo membership correct, and one PDF-grounded ordinary record for the missing webpage abstract.

- [ ] **Step 2: Author shards 00–03**

For each paper, write the exact `PaperSummaryZh` fields from Task 1. Use only the row's official title + abstract, or the bound PDF text for the designated missing-abstract paper. Keep `summary_zh` at 150–250 Chinese characters and make each of `research_problem`, `core_method`, `main_findings`, and `scope_and_limitations` specific to that paper.

- [ ] **Step 3: Validate shards 00–03**

Run: `.venv/bin/conference-trends import-chinese-content --venue ACL --year 2026 --track long --summary-files data/content/acl/2026-long/authored/paper-summaries-{00,01,02,03}.zh.jsonl --allow-incomplete`

Expected: every row passes schema/source checks; reported ID coverage equals the union of source shards 00–03; no `current.json` is written.

- [ ] **Step 4: Commit shards 00–03**

```bash
git add data/content/acl/2026-long/source-batches/paper-summary-source-0{0,1,2,3}.jsonl data/content/acl/2026-long/authored/paper-summaries-0{0,1,2,3}.zh.jsonl
git commit -m "data: add ACL Chinese summaries shards 00 to 03"
```

- [ ] **Step 5: Author and validate shards 04–07**

Use the same field contract and source limits, then run:

`.venv/bin/conference-trends import-chinese-content --venue ACL --year 2026 --track long --summary-files data/content/acl/2026-long/authored/paper-summaries-{04,05,06,07}.zh.jsonl --allow-incomplete`

Expected: exact source membership for shards 04–07 and no pointer write.

- [ ] **Step 6: Commit shards 04–07**

```bash
git add data/content/acl/2026-long/source-batches/paper-summary-source-0{4,5,6,7}.jsonl data/content/acl/2026-long/authored/paper-summaries-0{4,5,6,7}.zh.jsonl
git commit -m "data: add ACL Chinese summaries shards 04 to 07"
```

- [ ] **Step 7: Author and validate shards 08–11**

Run the incomplete import against files 08, 09, 10 and 11. Confirm exact membership, natural Chinese, source hash equality and no pointer write.

- [ ] **Step 8: Commit shards 08–11**

```bash
git add data/content/acl/2026-long/source-batches/paper-summary-source-{08,09,10,11}.jsonl data/content/acl/2026-long/authored/paper-summaries-{08,09,10,11}.zh.jsonl
git commit -m "data: add ACL Chinese summaries shards 08 to 11"
```

- [ ] **Step 9: Author and validate shards 12–15**

Run the incomplete import against files 12, 13, 14 and 15. Confirm exact membership, natural Chinese, source hash equality and no pointer write.

- [ ] **Step 10: Commit shards 12–15**

```bash
git add data/content/acl/2026-long/source-batches/paper-summary-source-{12,13,14,15}.jsonl data/content/acl/2026-long/authored/paper-summaries-{12,13,14,15}.zh.jsonl
git commit -m "data: add ACL Chinese summaries shards 12 to 15"
```

- [ ] **Step 11: Run exact full-corpus checks**

Run: `.venv/bin/conference-trends import-chinese-content --venue ACL --year 2026 --track long --summaries-dir data/content/acl/2026-long/authored --awards data/content/acl/2026-long/authored/award-deep-reads.zh.jsonl`

Expected: 2,192 ordinary summaries + 30 award deep reads = 2,222 exact IDs; zero duplicates, unknown IDs, source-hash mismatches, invalid lengths or unsupported numeric tokens.

- [ ] **Step 12: Create a deterministic theme-stratified review sample**

For each primary topic, select `min(20, population)` records by sorting on SHA-256 of `paper_id + content_generation_seed`. Store the exact paper ID, title, Chinese summary and source abstract/PDF locator in `summary-review-samples.json`.

- [ ] **Step 13: Independently read every sampled summary**

For each sampled paper, record `accurate`, `needs_correction`, or `unsupported` plus a substantive Chinese note in `summary-review-decisions.json`. A correction records the exact old field value and replacement. Apply every accepted correction back to its authored shard, rerun source and length checks, then regenerate the sample from the unchanged seed and confirm identical sample membership.

- [ ] **Step 14: Commit review records and corrected shards**

```bash
git add data/content/acl/2026-long/authored data/content/acl/2026-long/review/summary-review-samples.json data/content/acl/2026-long/review/summary-review-decisions.json
git commit -m "data: review ACL Chinese paper summaries"
```

---

### Task 6: Publish the full immutable content generation

**Files:**
- Create: `data/content/acl/2026-long/generations/<sha256>/paper-summaries.zh.jsonl`
- Create: `data/content/acl/2026-long/generations/<sha256>/award-deep-reads.zh.jsonl`
- Create: `data/content/acl/2026-long/generations/<sha256>/content-manifest.json`
- Create: `data/content/acl/2026-long/current.json`
- Test: `tests/test_content_pipeline.py`

**Interfaces:**
- Consumes: all authored shards and current validated ACL release.
- Produces: one selected immutable content generation loadable by Python and Astro.

- [ ] **Step 1: Add a real-data publication regression**

The test loads the current release and all authored files, writes into a temporary directory, then asserts exact counts, release generation, papers SHA, three artifact hashes and generation ID.

- [ ] **Step 2: Run the regression and confirm RED**

Expected: FAIL until the checked-in authored corpus is complete and accepted by the writer.

- [ ] **Step 3: Build the selected content generation**

Run: `.venv/bin/conference-trends build-chinese-content --venue ACL --year 2026 --track long`

- [ ] **Step 4: Independently verify bytes and IDs**

Use a read-only script to recompute SHA-256 for all three files, compare them with both manifest and pointer, and assert that the ordinary and award ID sets are disjoint and total 2,222.

- [ ] **Step 5: Run Python tests and lint**

Run: `.venv/bin/python -m pytest tests/test_chinese_content.py tests/test_content_pipeline.py tests/test_reports.py tests/test_pipeline.py -q`

Run: `.venv/bin/ruff check src tests`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add data/content/acl/2026-long/generations data/content/acl/2026-long/current.json tests/test_content_pipeline.py
git commit -m "data: publish ACL 2026 Chinese paper content"
```

---

### Task 7: Add ordinary paper routes and learning-oriented page components

**Files:**
- Create: `site/src/lib/paper-reading.ts`
- Create: `site/src/components/PaperReadingNav.astro`
- Create: `site/src/components/PaperSummarySections.astro`
- Create: `site/src/pages/papers/[paperId].astro`
- Modify: `site/src/pages/papers/index.astro`
- Modify: `site/src/styles/global.css`
- Create: `site/tests/paper-reading.test.ts`
- Modify: `site/tests/routes.test.ts`

**Interfaces:**
- Consumes: `LoadedOverview`, `LoadedChineseContent`.
- Produces: `paperReadingRoutes(...)`, `buildPaperReadingIndex(...)`, 2,192 ordinary routes and direct award links.

- [ ] **Step 1: Write failing route tests**

```ts
it("partitions every paper into one ordinary or award reading route", () => {
  const routes = paperReadingRoutes(release, content);
  expect(routes.ordinary).toHaveLength(2192);
  expect(routes.awards).toHaveLength(30);
  expect(new Set([...routes.ordinaryIds, ...routes.awardIds]).size).toBe(2222);
});

it("sends award index rows directly to award deep reads", () => {
  expect(indexRow(awardPaper).readingHref).toMatch(/\/awards\/award-[0-9a-f]+\/$/);
});
```

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `cd site && npm test -- --run tests/paper-reading.test.ts tests/routes.test.ts`

Expected: FAIL because route helpers and page are absent.

- [ ] **Step 3: Implement producer-authoritative route keys and views**

Derive stable paper `route_key` in Python content output and consume it in TypeScript. `paperReadingRoutes` must reject missing/duplicate route keys and never normalize paper IDs independently in the browser.

- [ ] **Step 4: Build the ordinary reading page**

Render paper metadata, one-sentence summary, Chinese summary, research problem, core method, main findings, scope/limitations and collapsed official English abstract in that order. Add official/PDF/Code links and a return link to the filtered paper index.

- [ ] **Step 5: Update paper index and search**

Ordinary titles link to `/papers/<route-key>/`; award titles link to `/awards/<route-key>/`. Include Chinese one-sentence and summary text in `data-search`, but keep the visible row compact with a two-line Chinese preview.

- [ ] **Step 6: Add responsive reading styles**

Use a readable text measure of at most 72 characters, sticky page navigation only above the mobile breakpoint, `overflow-wrap: anywhere` for long English identifiers, and a single-column mobile flow.

- [ ] **Step 7: Run focused tests, Astro check and build**

Run: `cd site && npm test -- --run tests/paper-reading.test.ts tests/routes.test.ts`

Run: `cd site && npm run check && npm run build`

Expected: 2,229 total pages at this stage: the existing 37 pages plus 2,192 new ordinary pages; no duplicate award pages.

- [ ] **Step 8: Commit**

```bash
git add site/src/lib/paper-reading.ts site/src/components/PaperReadingNav.astro site/src/components/PaperSummarySections.astro site/src/pages/papers/'[paperId]'.astro site/src/pages/papers/index.astro site/src/styles/global.css site/tests/paper-reading.test.ts site/tests/routes.test.ts
git commit -m "feat: add Chinese reading pages for every paper"
```

---

### Task 8: Expose coverage and complete browser acceptance

**Files:**
- Modify: `site/src/pages/methodology.astro`
- Modify: `site/src/pages/index.astro`
- Modify: `site/tests/visual.spec.ts`
- Modify: `README.md`
- Create: `notes/acl-2026-chinese-content-report.md`

**Interfaces:**
- Consumes: selected release, selected Chinese content manifest and all generated routes.
- Produces: public coverage explanation, local-review report and final acceptance results.

- [ ] **Step 1: Write failing public-copy and browser tests**

Tests must assert:

- methodology shows `2,192 / 2,192` ordinary summaries and `30 / 30` award deep reads;
- every public paper index row reaches one Chinese reading page;
- ordinary pages show Chinese before “英文摘要”；
- award pages show “三分钟读懂” before “英文原文参考”；
- no page contains missing-content fallback text;
- desktop and mobile pages have no horizontal overflow;
- all internal links stay under `/ai-conference-overview/` and return HTTP 200.

- [ ] **Step 2: Run Playwright and confirm RED**

Run: `cd site && npm run test:e2e`

Expected: FAIL until coverage copy and final navigation are present.

- [ ] **Step 3: Add methodology and home-page summaries**

Explain that ordinary summaries come from official title + abstract, the single missing abstract uses its official PDF, award deep reads use full PDFs, and automated checks do not equal full manual reading. Display the content generation time and hashes without exposing filesystem paths.

- [ ] **Step 4: Write the content report**

Record release generation, papers SHA, content generation, three content hashes, counts, length distribution, missing-source handling, numeric-token failures corrected during authoring, theme-stratified sample sizes, build page count, build time and output size.

- [ ] **Step 5: Run full verification**

Run: `.venv/bin/python -m pytest -q`

Run: `.venv/bin/ruff check src tests scripts`

Run: `cd site && npm test -- --run`

Run: `cd site && npm run check`

Run: `cd site && npm run build`

Run: `cd site && npm run test:e2e`

Expected: all commands pass; production build emits 2,229 pages; empty-data build still emits only the six empty-safe pages and no paper detail routes.

- [ ] **Step 6: Inspect representative pages in the in-app browser**

Inspect at desktop and mobile widths:

- one ordinary text-LLM paper;
- one multimodal paper;
- one long-title paper;
- one paper without Code URL;
- the PDF-grounded missing-abstract paper;
- one Best Paper page;
- one Outstanding Paper page.

Leave the browser on the awards index for user review.

- [ ] **Step 7: Commit**

```bash
git add site/src/pages/methodology.astro site/src/pages/index.astro site/tests/visual.spec.ts README.md notes/acl-2026-chinese-content-report.md
git commit -m "docs: publish Chinese paper content coverage"
```

- [ ] **Step 8: Stop before external publication**

Report local commit hashes, tests, page count and review URL. Do not run `git push`, modify GitHub Pages settings or publish the site until the user explicitly approves the local review.
