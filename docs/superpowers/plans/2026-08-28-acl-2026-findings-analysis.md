# ACL 2026 Findings Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the published ACL 2026 Findings paper index with audited AI-assisted topic classification, one Chinese summary per paper, Track-specific topic distribution, and a five-lane research-advance overview, without inventing awards or temporal trends.

**Architecture:** Treat the selected Findings papers-only generation as the immutable semantic-analysis input. Generalize classified single-year publication so awards and curated synthesis are explicit capabilities instead of ICML-specific assumptions. Import hash-bound semantic reviews, audit them against deterministic samples, import Chinese summaries and curated advance notes through typed contracts, and select a new Findings generation only after every content and quality threshold passes.

**Tech Stack:** Python 3.11, Typer, Pydantic 2, PyYAML, pytest, Ruff, Astro 5, TypeScript, Zod, Vitest, Playwright, GitHub Actions, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-08-28-acl-2026-findings-onboarding-design.md`

## Global Constraints

- This plan starts only after the papers-only plan has selected a valid ACL/2026/findings generation.
- All 2,163 current paper IDs must receive exactly one primary topic; optional secondary topics are distinct and cannot repeat the primary topic.
- Classification uses title plus abstract whenever an abstract exists and is labeled “AI 辅助复核”.
- Review every low-confidence assignment. Audit `min(50, theme population)` papers for every primary topic using deterministic, assignment-bound samples.
- A theme is included in the public main-theme narrative only when observed precision is at least 0.90 and Wilson 95% lower bound is at least 0.80.
- Each paper receives a Chinese summary covering research question, method, paper-reported result, and scope/limitation. Do not invent results not stated by the paper.
- Findings has no award analysis. Its release contains zero award records/deep reads and `analysis_availability.awards=false`.
- All distribution shares use only the Findings included-paper count. The site must not infer growth from ACL Long versus Findings or from one year.
- Preserve the papers-only generation, ACL Long release, ICML releases, and all existing public routes as immutable history.
- Preserve unrelated worktree changes and stage explicit paths only.

---

### Task 1: Generalize audited single-year analysis and make awards an explicit capability

**Files:**
- Modify: `src/conference_overview/models.py`
- Modify: `src/conference_overview/registry.py`
- Modify: `src/conference_overview/conference_pipeline.py`
- Modify: `config/venues.yaml`
- Modify: `src/conference_overview/venues.yaml`
- Test: `tests/test_registry.py`
- Test: `tests/test_conference_pipeline.py`

**Interfaces:**
- Produces `VenueRequest.awards_enabled: bool` from Track config.
- `analyze_classified_scope` accepts any registered final single-year scope with complete semantic inputs.
- Award records and DeepReads are mandatory only when `awards_enabled=true`; otherwise both must be absent.

- [ ] **Step 1: Add RED capability and publication tests**

Create a small classified Findings fixture that has valid assignments/audits but no award files. Assert it reaches synthesis loading, while a Findings fixture with an award record is rejected. Keep the existing ICML test requiring all eight awards and deep reads.

- [ ] **Step 2: Run RED tests**

Run: `.venv/bin/pytest tests/test_registry.py tests/test_conference_pipeline.py -k 'classified or awards_enabled or findings' -q`

Expected: FAIL at the ICML/2025/main hardcoded guard or eight-award requirement.

- [ ] **Step 3: Add the explicit capability and remove venue literals**

```python
if request.awards_enabled:
    awards, deep_reads = require_complete_award_analysis(paths)
else:
    reject_unexpected_award_files(paths)
    awards, deep_reads = [], []
```

Set `awards_enabled: false` for Findings and true for ACL Long/ICML 2025. Keep publication status, assignment completeness, low-confidence completion, audit thresholds, taxonomy coverage, normalized-corpus equality, and six-artifact checks mandatory for every scope.

- [ ] **Step 4: Verify compatibility and commit**

Run: `.venv/bin/pytest tests/test_registry.py tests/test_conference_pipeline.py tests/test_pipeline.py tests/test_reports.py -q`

```bash
git add config/venues.yaml src/conference_overview/venues.yaml src/conference_overview/models.py src/conference_overview/registry.py src/conference_overview/conference_pipeline.py tests/test_registry.py tests/test_conference_pipeline.py
git commit -m "refactor: generalize classified single-year releases"
```

### Task 2: Add a typed, Track-scoped curated-advance input

**Files:**
- Modify: `src/conference_overview/models.py`
- Modify: `src/conference_overview/synthesis.py`
- Modify: `src/conference_overview/scope.py`
- Modify: `src/conference_overview/conference_pipeline.py`
- Test: `tests/test_synthesis.py`
- Test: `tests/test_conference_pipeline.py`

**Interfaces:**
- New input: `data/analysis/acl/2026-findings/advances.zh.yaml`.
- Schema: exactly five lane IDs (`text_llms`, `multimodal_models`, `reasoning_agents`, `data_training`, `evaluation_trust`), each with Chinese question, summary, evidence boundary, implications, and nonempty representative paper IDs.
- Every representative ID must exist in the current Findings corpus; every paper link comes from the normalized official record, not authored YAML.

- [ ] **Step 1: Add RED schema and binding tests**

Reject a missing lane, duplicate lane, unknown paper ID, Long paper ID, blank Chinese section, duplicate representative, unlabeled inference, and a file whose `papers_sha256` differs from the selected papers-only release.

- [ ] **Step 2: Run RED tests**

Run: `.venv/bin/pytest tests/test_synthesis.py tests/test_conference_pipeline.py -k 'curated or advance or findings' -q`

Expected: FAIL because `build_single_year_advances` reads `_ICML_2025_CURATED` from code.

- [ ] **Step 3: Implement the contract and venue-neutral builder**

```python
class CuratedAdvanceLane(BaseModel):
    lane_id: AdvanceCategory
    question_zh: str = Field(min_length=1)
    summary_zh: str = Field(min_length=1)
    evidence_boundary_zh: str = Field(min_length=1)
    implications_zh: str = Field(min_length=1)
    representative_paper_ids: list[str] = Field(min_length=1)
```

Load the authored file from `ScopePaths.analysis`, reparse before use, bind it to the selected papers hash and current assignments hash, and resolve titles/URLs from `PaperRecord`. Move the current ICML curated content into the same data contract so ICML output remains unchanged.

- [ ] **Step 4: Verify and commit**

Run: `.venv/bin/pytest tests/test_synthesis.py tests/test_conference_pipeline.py -q`

```bash
git add src/conference_overview/models.py src/conference_overview/synthesis.py src/conference_overview/scope.py src/conference_overview/conference_pipeline.py data/analysis/icml/2025-main/advances.zh.yaml tests/test_synthesis.py tests/test_conference_pipeline.py
git commit -m "feat: load track-scoped research advances"
```

### Task 3: Export and import complete AI-assisted semantic assignments

**Files:**
- Modify: `src/conference_overview/pipeline.py`
- Modify: `src/conference_overview/cli.py`
- Create: `data/classification/acl/2026-findings/assignments.jsonl`
- Create: `data/classification/acl/2026-findings/classification-manifest.json`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Export batches contain at most 40 rows with paper ID, title, abstract, and taxonomy version.
- Import row fields: `paper_id`, `primary_topic`, `secondary_topics`, `confidence`, `rationale`, `taxonomy_version`, and `review_status="ai_assisted"`.
- Imported ID set must exactly equal the current normalized Findings ID set and bind to its record-set/papers SHA-256.

- [ ] **Step 1: Add RED exact-membership and semantic-input tests**

Reject missing/extra/duplicate IDs, duplicate topics, absent rationale, invalid confidence, wrong taxonomy, title-only classification when an abstract exists, stale source hash, and batch size above 40.

- [ ] **Step 2: Run RED tests**

Run: `.venv/bin/pytest tests/test_pipeline.py tests/test_cli.py -k 'classification and findings' -q`

Expected: FAIL where ACL imports are tied to Long-specific filenames or scope checks.

- [ ] **Step 3: Generalize export/import around `VenueRequest`**

Use the current `ScopePaths.classification` and normalized records. Sort serialization by canonical paper ID; record every raw batch path, byte size, SHA-256, method `explicit_agent_semantic_labeling`, taxonomy version, and corpus hash in the manifest.

- [ ] **Step 4: Perform the full 2,163-paper semantic review**

Export all batches, classify every title+abstract pair, and import the union. This is semantic work: do not replace it with keyword-only assignment. Retain confidence below the review threshold rather than inflating it to avoid review.

- [ ] **Step 5: Verify exact coverage and commit inputs separately**

Run a fresh loader that proves 2,163 unique assignments, exact paper-ID equality, valid topics, and stable serialization; then run `.venv/bin/pytest tests/test_classification.py tests/test_pipeline.py tests/test_cli.py -q`.

```bash
git add src/conference_overview/pipeline.py src/conference_overview/cli.py tests/test_pipeline.py tests/test_cli.py
git commit -m "feat: classify ACL Findings papers"
git add data/classification/acl/2026-findings/assignments.jsonl data/classification/acl/2026-findings/classification-manifest.json
git commit -m "data: add ACL Findings semantic assignments"
```

### Task 4: Complete low-confidence review and deterministic theme audits

**Files:**
- Create: `data/classification/acl/2026-findings/low-confidence-review-queue.json`
- Create: `data/classification/acl/2026-findings/low-confidence-decisions.json`
- Create: `data/classification/acl/2026-findings/audit-samples.json`
- Create: `data/classification/acl/2026-findings/audit-decisions.json`
- Modify: `src/conference_overview/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Low-confidence queue is the exhaustive set selected by the configured threshold and is bound to assignments SHA-256.
- Audit sample is produced only by the canonical confidence-stratified sampler and contains exactly `min(50, population)` current rows per primary topic.
- Decisions bind sample SHA-256, assignments SHA-256, title/abstract content, reviewer method, and status.

- [ ] **Step 1: Add adversarial RED binding tests**

Reject a rehashed equal-size sample swap, forged title/abstract, stale assignment hash, missing/extra decision, changed taxonomy, incomplete low-confidence queue, and decisions marked complete with blank rationale.

- [ ] **Step 2: Run RED tests**

Run: `.venv/bin/pytest tests/test_pipeline.py -k 'audit or low_confidence' -q`

- [ ] **Step 3: Reuse the authoritative builders and make threshold inputs explicit**

Do not accept caller-authored sample membership. Recompute the queue and sample from current assignments, then exact-compare full rows before accepting decisions. Persist observed precision, Wilson lower bound, sample size, false count, and pass/withheld status.

- [ ] **Step 4: Review all queued and sampled papers**

Use title+abstract, write substantive rationales, and correct assignments through the guarded correction importer when needed. Any correction invalidates and regenerates the affected sample; repeat until the final assignment-bound audit is complete.

- [ ] **Step 5: Enforce publication thresholds and commit**

Run a fresh audit loader and require every narrative-visible theme to meet precision `>=0.90` and Wilson lower bound `>=0.80`. Themes that fail remain withheld from main-direction prose; do not relabel judgments to force a pass.

```bash
git add src/conference_overview/pipeline.py tests/test_pipeline.py data/classification/acl/2026-findings/low-confidence-review-queue.json data/classification/acl/2026-findings/low-confidence-decisions.json data/classification/acl/2026-findings/audit-samples.json data/classification/acl/2026-findings/audit-decisions.json
git commit -m "data: audit ACL Findings topic assignments"
```

### Task 5: Generate and import one hash-bound Chinese summary per paper

**Files:**
- Modify: `src/conference_overview/content_pipeline.py`
- Modify: `src/conference_overview/cli.py`
- Create: `data/content/acl/2026-findings/authored/paper-summaries.zh.jsonl`
- Create: `data/content/acl/2026-findings/current.json`
- Create: `data/content/acl/2026-findings/generations/<sha256>/`
- Test: `tests/test_content_pipeline.py`
- Test: `tests/test_chinese_content.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Export/import/build commands use the registered Track and `ScopePaths.release`; no hardcoded scope allowlist.
- Each summary has nonempty `research_question_zh`, `method_zh`, `reported_findings_zh`, and `scope_limitations_zh`, plus paper ID and source hash bindings.
- Output contains exactly one summary for every current Findings paper and no award content.

- [ ] **Step 1: Add RED Track-path and content-contract tests**

Reject Long/Findings source mixing, missing/duplicate paper IDs, stale papers hash, English-only narrative, unsupported claims, copied abstract-only output, blank limitation, and any award-deep-read row.

- [ ] **Step 2: Run RED tests**

Run: `.venv/bin/pytest tests/test_content_pipeline.py tests/test_chinese_content.py tests/test_cli.py -k findings -q`

Expected: FAIL because `_require_supported_scope` and release-root resolution are hardcoded.

- [ ] **Step 3: Generalize content paths and producer checks**

Resolve the source release with the shared Track-aware resolver. Replace the tuple allowlist with registered capability checks. Reparse authored rows before writing, require exact membership, and bind the content manifest to `papers.json` SHA-256 plus the Findings release generation.

- [ ] **Step 4: Write and quality-check all 2,163 summaries**

Generate concise Chinese learning summaries from title+abstract and, where needed for ambiguous claims, the official paper. Each should let a reader understand the problem, technical change, reported outcome, and limitation without opening the English abstract. Run deterministic completeness/readability checks plus a stratified factual review sample; correct failures before import.

- [ ] **Step 5: Build, verify, and commit content**

Run:

```bash
.venv/bin/conference-trends import-chinese-content --venues ACL --years 2026 --tracks findings --input data/content/acl/2026-findings/authored/paper-summaries.zh.jsonl
.venv/bin/conference-trends build-chinese-content --venues ACL --years 2026 --tracks findings
.venv/bin/pytest tests/test_content_pipeline.py tests/test_chinese_content.py tests/test_cli.py -q
```

```bash
git add src/conference_overview/content_pipeline.py src/conference_overview/cli.py tests/test_content_pipeline.py tests/test_chinese_content.py tests/test_cli.py
git commit -m "feat: support track-scoped Chinese summaries"
git add data/content/acl/2026-findings
git commit -m "data: add ACL Findings Chinese summaries"
```

### Task 6: Curate the five Findings research-advance lanes

**Files:**
- Create: `data/analysis/acl/2026-findings/advances.zh.yaml`
- Modify: `notes/acl-2026-findings-overview.md`
- Test: `tests/test_synthesis.py`

**Interfaces:**
- Consumes only audited Findings assignments and current official paper records.
- Produces five evidence-labeled lanes: Text LLMs, Multimodal Models, Reasoning & Agents, Data & Training, Evaluation & Trust.
- Narrative distinguishes paper-reported findings, cross-paper synthesis, and further inference.

- [ ] **Step 1: Build candidate sets from audit-passed themes**

For each lane, rank candidates using topic membership and assignment confidence only as a reading queue. Do not publish rankings as scientific importance and do not use withheld themes to make headline claims.

- [ ] **Step 2: Read representative official papers and write the authored contract**

For each lane, include the key research question, technical change, reported evidence, limitation, representative paper IDs, and a cautious implication for text/multimodal foundation models. Use official ACL Anthology links resolved by the producer.

- [ ] **Step 3: Run synthesis validation**

Run: `.venv/bin/pytest tests/test_synthesis.py -q`

Expected: all five lanes present, all IDs in Findings, no duplicate representatives within a lane, hashes current, and no temporal-growth wording.

- [ ] **Step 4: Polish Chinese without changing claim strength**

Use the `polishing-chinese-writing` skill on the public prose. Preserve explicit uncertainty, paper-reported boundaries, sample limits, and technical terms.

- [ ] **Step 5: Commit the curated analysis**

```bash
git add data/analysis/acl/2026-findings/advances.zh.yaml notes/acl-2026-findings-overview.md tests/test_synthesis.py
git commit -m "data: synthesize ACL Findings research advances"
```

### Task 7: Make advances, methodology, and conference views Track-aware

**Files:**
- Modify: `site/src/lib/advance-filter.ts`
- Modify: `site/src/lib/evidence.ts`
- Modify: `site/src/lib/views.ts`
- Modify: `site/src/pages/advances/index.astro`
- Modify: `site/src/pages/methodology.astro`
- Modify: `site/src/components/ConferenceOverview.astro`
- Test: `site/tests/evidence.test.ts`
- Test: `site/tests/routes.test.ts`
- Test: `site/tests/content-data.test.ts`

**Interfaces:**
- Advance identity and URL key are `venue + year + track`.
- Share URL: `/advances/?venue=ACL&year=2026&track=findings#advance-ACL-2026-findings`.
- Conference view renders distribution and hotspots only when availability flags are true; awards remain hidden for Findings.

- [ ] **Step 1: Add RED filter and cross-Track isolation tests**

Assert distinct ACL Long/Findings advance groups, valid URL round-trip, invalid Track rejection, no cross-Track representative, Findings methodology lineage, Chinese summary availability, and no Findings award group.

- [ ] **Step 2: Run RED tests**

Run: `cd site && npm test -- --run tests/evidence.test.ts tests/routes.test.ts tests/content-data.test.ts`

Expected: FAIL because advance keys and anchors use only venue/year and methodology selects one release.

- [ ] **Step 3: Extend pure filters and view keys**

```ts
export interface AdvanceFilter { venue: string; year: number; track: string }
const key = `${venue}-${year}-${track}`;
const query = new URLSearchParams({ venue, year: String(year), track });
```

Render natural Track labels in cards/headings. Make methodology selectable per release or render one clearly separated section per Track, including source hash, denominator, taxonomy, audit method/results, summary binding, and the single-year limitation.

- [ ] **Step 4: Verify view-level evidence boundaries**

Build a fixture containing ACL Long and Findings. Assert separate denominators, Findings availability enabled only after the analyzed generation, zero Findings awards, no trend line between Tracks, and only audit-passed themes used in the “主要方向” prose.

- [ ] **Step 5: Commit the Track-aware analysis UI**

```bash
git add site/src/lib/advance-filter.ts site/src/lib/evidence.ts site/src/lib/views.ts site/src/pages/advances/index.astro site/src/pages/methodology.astro site/src/components/ConferenceOverview.astro site/tests/evidence.test.ts site/tests/routes.test.ts site/tests/content-data.test.ts
git commit -m "feat: present track-scoped conference analysis"
```

### Task 8: Select the analyzed release and complete public acceptance

**Files:**
- Modify: `data/releases/ACL/2026/tracks/findings/current.json`
- Create: `data/releases/ACL/2026/tracks/findings/generations/<sha256>/`
- Modify: `README.md`
- Modify: `.superpowers/sdd/2026-08-28-acl-2026-findings/task-02-report.md`
- Test: `tests/test_verify_acl_findings_live_release.py`
- Test: `site/tests/visual.spec.ts`

**Interfaces:**
- New Findings release serializes topic metrics, audit disclosures, classification lineage, five advances, and Chinese-content availability while keeping awards false.
- Public acceptance covers the conference page, paper index/details, advances share URL, methodology, and absence of Findings awards/trend claims.

- [ ] **Step 1: Generate the analyzed six-artifact release**

Run:

```bash
.venv/bin/conference-trends analyze --venues ACL --years 2026 --tracks findings --write-release
.venv/bin/python scripts/verify_acl_findings_live_release.py --require-analysis
```

Require exact six files, 2,163 papers, exact assignment/content membership, current lineage hashes, audit status, five advances, zero awards, and a Track-local pointer. Preserve the prior papers-only generation.

- [ ] **Step 2: Run all deterministic checks**

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
python scripts/generate_award_host_policy.py --check
python scripts/generate_release_selectors.py --check
cd site && npm test -- --run && npm run check && npm run build
```

- [ ] **Step 3: Run desktop and 390px browser acceptance**

Run: `cd site && PLAYWRIGHT_PORT=4399 npm run test:e2e`

Check separate Long/Findings navigation, Findings topic counts/shares, audit labels, Chinese summaries, five advance lanes, shareable Track filter, methodology lineage, no Findings award entry, no fake trend, no 404/console error, and no horizontal overflow.

- [ ] **Step 4: Self-review and commit the analyzed release**

Run `git diff --check`, inspect staged files, verify the Long and ICML pointers/hashes remain unchanged, verify both Findings generations, and scan public prose for unsupported growth/award claims.

```bash
git add data/releases/ACL/2026/tracks/findings README.md site/tests/visual.spec.ts tests/test_verify_acl_findings_live_release.py
git commit -m "data: publish ACL Findings analysis"
```

- [ ] **Step 5: Publish and verify GitHub Pages**

Push `main`, wait for CI and Pages success, then open the cache-busted public conference and advance URLs. Compare the live counts, Track, selected generation, audit labels, and representative-paper links with the immutable artifacts. Deployment is complete only after the live site matches the selected release.
