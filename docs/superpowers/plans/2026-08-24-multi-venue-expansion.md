# Multi-Venue Conference Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the validated ACL reference pipeline to ICLR, ICML, CVPR, EMNLP, ICCV, ECCV, and NeurIPS and publish normalized cross-venue trends.

**Architecture:** Each source family implements the canonical adapter contract against immutable official-source snapshots. Venue-year reconciliation and semantic classification use the existing publication gates. Cross-venue metrics consume only validated releases and expose raw counts alongside normalized topic shares, enrichment, and spread.

**Tech Stack:** Existing Python/Astro stack plus official OpenReview API v2, PMLR proceedings HTML, CVF Open Access HTML, ECVA proceedings HTML, and NeurIPS Proceedings HTML.

**Spec:** `docs/superpowers/specs/2026-08-24-ai-conference-overview-design.md`

## Global Constraints

- Complete `docs/superpowers/plans/2026-08-24-acl-2026-reference-site.md` first.
- Every adapter is read-only and retains the official source URL, retrieval time, and SHA-256.
- Venue-native tracks and keywords are preserved alongside common topics.
- Accepted-paper scope is configured per venue-year and never inferred from generic search results.
- Cross-venue headlines use normalized shares; raw counts remain descriptive context.
- Three consecutive validated years are required for unqualified trend language.
- Awards remain officially verified per venue and year.
- New source-format assumptions require fixtures and a live reconciliation report.

## File Map

```text
src/conference_overview/adapters/openreview.py   ICLR accepted submissions
src/conference_overview/adapters/pmlr.py         ICML proceedings
src/conference_overview/adapters/cvf.py          CVPR and ICCV proceedings
src/conference_overview/adapters/ecva.py         ECCV proceedings
src/conference_overview/adapters/neurips.py      NeurIPS proceedings
config/venues.yaml                               venue/year source registry
tests/fixtures/<source-family>/                  immutable parsing fixtures
src/conference_overview/compare.py               normalized cross-venue bundles
site/src/pages/trends/                            comparison explorer
```

---

### Task 1: OpenReview Adapter for ICLR

**Files:**
- Create: `src/conference_overview/adapters/openreview.py`
- Create: `tests/fixtures/openreview/iclr-accepted.json`
- Create: `tests/test_openreview_adapter.py`
- Modify: `config/venues.yaml`

**Interfaces:**
- Produces: `parse_openreview_notes(payload, request, source) -> list[PaperRecord]`.

- [ ] **Step 1: Write failing accepted-status test**

```python
def test_openreview_includes_only_configured_acceptance_venues() -> None:
    records = parse_openreview_notes(fixture(), iclr_request(), source_ref())
    assert [record.paper_id for record in records] == ["openreview:accepted-1"]
    assert records[0].subject_areas == ["language models"]
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_openreview_adapter.py -v`

Expected: FAIL on missing adapter.

- [ ] **Step 3: Implement API v2 mapping**

Read `content.venueid.value`, `title.value`, `authors.value`, `abstract.value`, `keywords.value`, and `primary_area.value`. Include only venue IDs listed for that year in `config/venues.yaml`; poster/oral distinctions become native metadata, not separate acceptance inference.

- [ ] **Step 4: Verify fixture and live reconciliation**

Run: `python -m pytest tests/test_openreview_adapter.py -v && conference-trends validate --venues ICLR --years 2024:2026`

Expected: fixture PASS; live report records exact note count and official venue IDs.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/adapters/openreview.py config/venues.yaml tests/fixtures/openreview tests/test_openreview_adapter.py
git commit -m "feat: add ICLR OpenReview adapter"
```

### Task 2: PMLR Adapter for ICML

**Files:**
- Create: `src/conference_overview/adapters/pmlr.py`
- Create: `tests/fixtures/pmlr/icml-volume.html`
- Create: `tests/test_pmlr_adapter.py`
- Modify: `config/venues.yaml`

**Interfaces:**
- Produces: `parse_pmlr_volume(html, request, source) -> list[PaperRecord]`.

- [ ] **Step 1: Write failing HTML mapping test**

```python
def test_pmlr_preserves_landing_pdf_and_doi() -> None:
    paper = parse_pmlr_volume(fixture_html(), icml_request(), source_ref())[0]
    assert str(paper.landing_url).endswith("paper.html")
    assert str(paper.pdf_url).endswith("paper.pdf")
    assert paper.venue == "ICML"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_pmlr_adapter.py -v`

Expected: FAIL on missing PMLR parser.

- [ ] **Step 3: Implement volume parsing**

Parse only paper entries inside the official volume container. Derive stable IDs from PMLR paper slugs and preserve the volume URL in provenance. Do not treat editor/front-matter entries as papers.

- [ ] **Step 4: Verify GREEN and live count**

Run: `python -m pytest tests/test_pmlr_adapter.py -v && conference-trends validate --venues ICML --years 2024:2026`

Expected: PASS and an exact per-volume reconciliation report.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/adapters/pmlr.py config/venues.yaml tests/fixtures/pmlr tests/test_pmlr_adapter.py
git commit -m "feat: add ICML PMLR adapter"
```

### Task 3: CVF Adapter for CVPR and ICCV

**Files:**
- Create: `src/conference_overview/adapters/cvf.py`
- Create: `tests/fixtures/cvf/conference.html`
- Create: `tests/test_cvf_adapter.py`
- Modify: `config/venues.yaml`

**Interfaces:**
- Produces: `parse_cvf_conference(html, request, source) -> list[PaperRecord]`.

- [ ] **Step 1: Write failing title/author/PDF test**

```python
def test_cvf_record_uses_official_openaccess_urls() -> None:
    record = parse_cvf_conference(fixture_html(), cvpr_request(), source_ref())[0]
    assert record.paper_id.startswith("cvf:CVPR2026:")
    assert "openaccess.thecvf.com" in str(record.landing_url)
    assert str(record.pdf_url).endswith(".pdf")
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_cvf_adapter.py -v`

Expected: FAIL on missing CVF parser.

- [ ] **Step 3: Implement shared CVF parsing**

Parse the `All Papers` listing, deduplicate papers repeated under daily program sections by canonical landing URL, and keep supplementary files separate from the paper PDF.

- [ ] **Step 4: Verify both venues**

Run: `python -m pytest tests/test_cvf_adapter.py -v && conference-trends validate --venues CVPR,ICCV --years 2023:2026`

Expected: PASS; each venue-year has a separate official manifest and no daily-section duplicates.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/adapters/cvf.py config/venues.yaml tests/fixtures/cvf tests/test_cvf_adapter.py
git commit -m "feat: add CVF conference adapter"
```

### Task 4: ECVA Adapter for ECCV

**Files:**
- Create: `src/conference_overview/adapters/ecva.py`
- Create: `tests/fixtures/ecva/eccv.html`
- Create: `tests/test_ecva_adapter.py`
- Modify: `config/venues.yaml`

**Interfaces:**
- Produces: `parse_ecva_conference(html, request, source) -> list[PaperRecord]`.

- [ ] **Step 1: Write failing ECCV record test**

```python
def test_ecva_maps_paper_and_supplement_separately() -> None:
    record = parse_ecva_conference(fixture_html(), eccv_request(), source_ref())[0]
    assert record.venue == "ECCV"
    assert str(record.pdf_url).endswith(".pdf")
    assert record.paper_id.startswith("ecva:ECCV")
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_ecva_adapter.py -v`

Expected: FAIL on missing parser.

- [ ] **Step 3: Implement ECVA mapping**

Use canonical paper links as stable IDs, normalize multipart proceedings pages into one venue-year release, and retain the source part URL in each record's provenance.

- [ ] **Step 4: Verify GREEN and even-year coverage**

Run: `python -m pytest tests/test_ecva_adapter.py -v && conference-trends validate --venues ECCV --years 2022,2024,2026`

Expected: PASS for published years; an unpublished 2026 volume returns `incomplete_official_release` rather than an empty valid release.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/adapters/ecva.py config/venues.yaml tests/fixtures/ecva tests/test_ecva_adapter.py
git commit -m "feat: add ECCV ECVA adapter"
```

### Task 5: NeurIPS Proceedings Adapter

**Files:**
- Create: `src/conference_overview/adapters/neurips.py`
- Create: `tests/fixtures/neurips/proceedings.html`
- Create: `tests/test_neurips_adapter.py`
- Modify: `config/venues.yaml`

**Interfaces:**
- Produces: `parse_neurips_proceedings(html, request, source) -> list[PaperRecord]`.

- [ ] **Step 1: Write failing alias and proceedings test**

```python
def test_nips_request_emits_neurips_records() -> None:
    request = normalize_request("NIPS", 2025, None)
    record = parse_neurips_proceedings(fixture_html(), request, source_ref())[0]
    assert record.venue == "NEURIPS"
    assert record.paper_id.startswith("neurips:2025:")
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_neurips_adapter.py -v`

Expected: FAIL on missing parser.

- [ ] **Step 3: Implement proceedings mapping**

Parse official paper landing pages, titles, authors, abstracts when available, and PDF links. Preserve `NIPS` only as an input alias; stored records and URLs use the official venue naming for that year.

- [ ] **Step 4: Verify GREEN and live years**

Run: `python -m pytest tests/test_neurips_adapter.py -v && conference-trends validate --venues NEURIPS --years 2023:2025`

Expected: PASS and exact official proceedings reconciliation.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/adapters/neurips.py config/venues.yaml tests/fixtures/neurips tests/test_neurips_adapter.py
git commit -m "feat: add NeurIPS proceedings adapter"
```

### Task 6: EMNLP via ACL Anthology Configuration

**Files:**
- Modify: `config/venues.yaml`
- Modify: `tests/test_registry.py`
- Create: `tests/fixtures/acl/emnlp-sample.bib`
- Modify: `tests/test_acl_adapter.py`

**Interfaces:**
- Consumes: existing ACL adapter.
- Produces: EMNLP main/long requests with explicit Findings exclusion unless requested.

- [ ] **Step 1: Write failing track-boundary test**

```python
def test_emnlp_main_does_not_include_findings() -> None:
    request = normalize_request("EMNLP", 2025, "main")
    assert request.source_key == "2025.emnlp-main"
    assert "findings" not in request.source_key
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_registry.py tests/test_acl_adapter.py -v`

Expected: FAIL because EMNLP routing is absent.

- [ ] **Step 3: Add explicit EMNLP volume routes**

Map each supported year/track to the official Anthology volume ID. Keep `main`, `long`, `short`, and `findings` distinct even when historical naming differs.

- [ ] **Step 4: Verify GREEN and reconciliation**

Run: `python -m pytest tests/test_registry.py tests/test_acl_adapter.py -v && conference-trends validate --venues EMNLP --years 2023:2025 --tracks main`

Expected: PASS with no Findings records in main-paper releases.

- [ ] **Step 5: Commit**

```bash
git add config/venues.yaml tests/test_registry.py tests/fixtures/acl/emnlp-sample.bib tests/test_acl_adapter.py
git commit -m "feat: configure EMNLP anthology volumes"
```

### Task 7: Cross-Venue Comparison Bundles

**Files:**
- Create: `src/conference_overview/compare.py`
- Create: `tests/test_compare.py`
- Modify: `src/conference_overview/cli.py`

**Interfaces:**
- Consumes: validated venue-year releases sharing a taxonomy version.
- Produces: `ComparisonBundle`, `compare_releases()`, CLI `compare`.

- [ ] **Step 1: Write failing normalization and version tests**

```python
def test_comparison_uses_shares_not_raw_counts() -> None:
    bundle = compare_releases([release("ACL", 100, 20), release("CVPR", 1000, 100)])
    assert bundle.rows["ACL"].topic_share == Decimal("0.20")
    assert bundle.rows["CVPR"].topic_share == Decimal("0.10")


def test_comparison_rejects_mixed_taxonomy_versions() -> None:
    with pytest.raises(IncompatibleRelease):
        compare_releases([release_with_version("v1"), release_with_version("v2")])


def test_emerging_components_are_serialized() -> None:
    bundle = compare_releases(three_year_fixture())
    topic = bundle.topics["Reasoning and Agents"]
    assert topic.emerging.weights == {"share_growth": "0.45", "spread_growth": "0.35", "novelty": "0.20"}
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_compare.py -v`

Expected: FAIL on missing comparison module.

- [ ] **Step 3: Implement comparison bundle**

Store raw count, denominator, topic share, YoY share delta, venue enrichment, cross-venue spread, consecutive-year coverage, missingness, and audit status. Normalize positive relative share growth to `[0, 1]`, spread growth as newly covered venues divided by configured venues, and novelty as `1 - min(prior_active_years / 3, 1)`. Pass these values to the Task 6 formula and serialize the inputs and weights. Suppress an Emerging Score when any component is missing or a topic audit is not publishable.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_compare.py tests/test_metrics.py -v`

Expected: PASS; ACL ranks above CVPR in the test despite lower raw count because its share is higher.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/compare.py src/conference_overview/cli.py tests/test_compare.py
git commit -m "feat: compare normalized cross-venue trends"
```

### Task 8: Multi-Venue Trend Explorer and Release

**Files:**
- Modify: `site/src/pages/trends/index.astro`
- Create: `site/src/components/VenueTopicHeatmap.tsx`
- Create: `site/src/components/TopicTimeline.tsx`
- Create: `site/src/components/TrendFilters.tsx`
- Modify: `site/tests/routes.test.ts`
- Modify: `README.md`

**Interfaces:**
- Consumes: `ComparisonBundle` artifacts.
- Produces: filterable venue/year/topic views and shareable query URLs.

- [ ] **Step 1: Write failing display-contract test**

```typescript
it("shows normalized share before raw count", () => {
  const row = comparisonRow({ topicShare: 0.2, rawCount: 20, total: 100 });
  expect(row.primaryMetric).toBe("20.0%");
  expect(row.context).toBe("20 of 100 papers");
});
```

- [ ] **Step 2: Verify RED**

Run: `cd site && npm test -- routes.test.ts`

Expected: FAIL on missing comparison formatter.

- [ ] **Step 3: Implement the explorer**

Add venue, year, modality, and topic filters; topic-by-venue heatmap; share timeline; spread indicator; audit/missingness badges; and an accessible table. Persist filters in the URL. Use `Not enough validated years` instead of rendering a trend arrow for shorter windows.

- [ ] **Step 4: Generate multi-venue releases and run acceptance**

Run:

```bash
conference-trends compare --venues ACL,EMNLP,ICLR,ICML,NEURIPS,CVPR,ICCV,ECCV --years 2024:2026 --write-release
python -m pytest -q
cd site && npm test && npm run build && npx playwright test
```

Expected: unavailable venue-years are visibly incomplete rather than zero; all complete releases share a taxonomy version; site tests PASS.

- [ ] **Step 5: Commit and deploy**

```bash
git add data/releases site/src site/tests README.md
git commit -m "feat: publish multi-venue conference trends"
git push origin main
gh run watch --exit-status
```

Expected: Pages deploy succeeds and the public trend explorer loads normalized multi-venue data.
