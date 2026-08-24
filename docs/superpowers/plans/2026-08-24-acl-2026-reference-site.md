# ACL 2026 Reference Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a validated ACL 2026 long-paper overview, award deep reads, reusable conference-analysis skill, and GitHub Pages site at `/ai-conference-overview/`.

**Architecture:** A typed Python pipeline collects official ACL Anthology metadata into immutable snapshots and canonical records, validates counts and provenance, and emits versioned analysis artifacts. Semantic classification is exchanged through validated JSONL batches so the skill can use an available model without hard-coding a paid provider. An Astro static site consumes only publishable artifacts.

**Tech Stack:** Python 3.11+, Pydantic 2, Typer, HTTPX, bibtexparser, PyYAML, pytest, Astro, TypeScript, ECharts, Vitest, Playwright, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-08-24-ai-conference-overview-design.md`

## Global Constraints

- Repository: `git@github.com:smallflyingpig/ai-conference-overview.git`.
- License: MIT for project-authored work; third-party papers, figures, metadata, and conference assets retain their original rights.
- Initial publication scope: ACL 2026 Volume 1 long papers; proceedings front matter is excluded and counted.
- Project Pages base path: `/ai-conference-overview/`.
- Official metadata, paper-reported results, cross-paper synthesis, and inference remain visibly distinct.
- A one-year distribution is never described as a trend.
- Fuzzy duplicates are review candidates and are never deleted automatically.
- Unverified award candidates are never published as award papers.
- A failed validation cannot replace the last publishable snapshot.
- Preserve unrelated worktree changes and stage explicit paths only.

## File Map

```text
LICENSE                                      MIT license text
README.md                                    setup, commands, evidence boundary
pyproject.toml                               Python package and test configuration
config/venues.yaml                           venue aliases and official source routes
config/taxonomy.yaml                         versioned common taxonomy
src/conference_overview/models.py            canonical records and status models
src/conference_overview/registry.py          venue/year/track normalization
src/conference_overview/fetch.py             bounded official-source retrieval
src/conference_overview/storage.py           immutable snapshot and manifest writes
src/conference_overview/adapters/acl.py       ACL BibTeX parsing
src/conference_overview/validate.py           reconciliation and publication gates
src/conference_overview/metrics.py            distribution and trend-safe metrics
src/conference_overview/classification.py     batch exchange and taxonomy audit
src/conference_overview/awards.py             award evidence and deep-read validation
src/conference_overview/reports.py            JSON/CSV/Markdown artifact generation
src/conference_overview/cli.py                conference-trends command surface
.agents/skills/analyzing-conference-trends/   reusable agent workflow
site/                                         Astro static application
tests/                                        deterministic unit/contract fixtures
.github/workflows/ci.yml                      test and build checks
.github/workflows/pages.yml                   validated Pages deployment
```

---

### Task 1: Package, License, and Test Harness

**Files:**
- Create: `LICENSE`
- Create: `README.md`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `src/conference_overview/__init__.py`
- Create: `tests/test_package.py`

**Interfaces:**
- Produces: importable package `conference_overview` with `__version__: str`.

- [ ] **Step 1: Write the failing package test**

```python
from conference_overview import __version__


def test_package_exposes_version() -> None:
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_package.py -v`

Expected: FAIL because `conference_overview` is not importable.

- [ ] **Step 3: Add minimal package configuration**

Use this build configuration in `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling>=1.27,<2"]
build-backend = "hatchling.build"

[project]
name = "ai-conference-overview"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "bibtexparser>=1.4,<2",
  "httpx>=0.28,<1",
  "pydantic>=2.10,<3",
  "PyYAML>=6,<7",
  "typer>=0.15,<1",
]

[project.optional-dependencies]
dev = ["pytest>=8.3,<9", "pytest-cov>=6,<7", "respx>=0.22,<1", "ruff>=0.9,<1"]

[project.scripts]
conference-trends = "conference_overview.cli:app"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Set `__version__ = "0.1.0"`. Add the standard MIT text with copyright `2026 smallflyingpig`. Document `python -m pip install -e '.[dev]'` in `README.md`.

- [ ] **Step 4: Install and verify GREEN**

Run: `python -m pip install -e '.[dev]' && python -m pytest tests/test_package.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add LICENSE README.md .gitignore pyproject.toml src/conference_overview/__init__.py tests/test_package.py
git commit -m "chore: initialize conference overview package"
```

### Task 2: Canonical Models and Venue Registry

**Files:**
- Create: `config/venues.yaml`
- Create: `src/conference_overview/models.py`
- Create: `src/conference_overview/registry.py`
- Create: `tests/test_registry.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces: `PaperRecord`, `SourceRef`, `VenueRequest`, `RecordStatus`, `EvidenceType`, `EvidenceClaim`, `normalize_request()`.

- [ ] **Step 1: Write failing model and alias tests**

```python
from conference_overview.models import PaperRecord, RecordStatus, SourceRef
from conference_overview.registry import normalize_request


def test_nips_alias_normalizes_to_neurips() -> None:
    request = normalize_request("NIPS", 2025, None)
    assert request.venue == "NEURIPS"


def test_paper_requires_official_source() -> None:
    paper = PaperRecord(
        paper_id="acl:2026.acl-long.1",
        title="Example",
        normalized_title="example",
        authors=["A. Author"],
        venue="ACL",
        year=2026,
        track="long",
        landing_url="https://aclanthology.org/2026.acl-long.1/",
        source=SourceRef(name="ACL Anthology", url="https://aclanthology.org/volumes/2026.acl-long/"),
        status=RecordStatus.COMPLETE,
    )
    assert paper.paper_id == "acl:2026.acl-long.1"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_models.py tests/test_registry.py -v`

Expected: FAIL on missing modules.

- [ ] **Step 3: Implement typed contracts and registry**

Define Pydantic models with these exact fields:

```python
class RecordStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EXCLUDED = "excluded"
    UNRESOLVED = "unresolved"


class SourceRef(BaseModel):
    name: str
    url: HttpUrl
    retrieved_at: datetime | None = None
    sha256: str | None = None


class PaperRecord(BaseModel):
    paper_id: str
    title: str
    normalized_title: str
    authors: list[str]
    venue: str
    year: int
    track: str
    landing_url: HttpUrl
    source: SourceRef
    status: RecordStatus
    abstract: str | None = None
    keywords: list[str] = []
    subject_areas: list[str] = []
    affiliations: list[str] = []
    native_metadata: dict[str, str | list[str]] = {}
    doi: str | None = None
    pdf_url: HttpUrl | None = None
    code_url: HttpUrl | None = None
```

Use `Field(default_factory=list)` and `Field(default_factory=dict)` for mutable defaults in production. Add `EvidenceType` values `official_metadata`, `paper_reported`, `cross_paper_synthesis`, and `inference`. Define `EvidenceClaim` with `claim`, `evidence_type`, `source_urls`, and optional `locator`. Configure ACL 2026 long with the official BibTeX and volume HTML URLs; configure `NIPS` as an alias of `NEURIPS` for later expansion.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_models.py tests/test_registry.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/venues.yaml src/conference_overview/models.py src/conference_overview/registry.py tests/test_models.py tests/test_registry.py
git commit -m "feat: define canonical conference records"
```

### Task 3: Immutable Retrieval and Manifest Storage

**Files:**
- Create: `src/conference_overview/fetch.py`
- Create: `src/conference_overview/storage.py`
- Create: `tests/test_fetch.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Consumes: `SourceRef`.
- Produces: `fetch_bytes(url: str, client: httpx.Client) -> bytes`, `store_snapshot(data: bytes, source_url: str, root: Path) -> SourceRef`.

- [ ] **Step 1: Write failing bounded-fetch and hash tests**

```python
def test_fetch_rejects_non_success_response() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(503, request=request))
    with httpx.Client(transport=transport) as client, pytest.raises(SourceFetchError):
        fetch_bytes("https://example.test/volume.bib", client)


def test_snapshot_path_is_content_addressed(tmp_path: Path) -> None:
    ref = store_snapshot(b"paper-data", "https://example.test/volume.bib", tmp_path)
    assert ref.sha256 == hashlib.sha256(b"paper-data").hexdigest()
    assert (tmp_path / "raw" / f"{ref.sha256}.bin").read_bytes() == b"paper-data"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_fetch.py tests/test_storage.py -v`

Expected: FAIL on missing functions.

- [ ] **Step 3: Implement retrieval and atomic storage**

Use a fixed user agent, 30-second timeout, and three attempts only for transport errors and HTTP 429/5xx. Write snapshots through a sibling temporary file followed by `Path.replace()`. Write a JSON manifest containing source URL, UTC retrieval time, SHA-256, byte size, and local snapshot path.

```python
def fetch_bytes(url: str, client: httpx.Client) -> bytes:
    response = client.get(url, follow_redirects=True)
    if response.status_code != 200:
        raise SourceFetchError(url=url, status_code=response.status_code)
    return response.content
```

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_fetch.py tests/test_storage.py -v`

Expected: PASS with no live network access.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/fetch.py src/conference_overview/storage.py tests/test_fetch.py tests/test_storage.py
git commit -m "feat: store immutable source snapshots"
```

### Task 4: ACL Anthology Adapter

**Files:**
- Create: `src/conference_overview/adapters/__init__.py`
- Create: `src/conference_overview/adapters/acl.py`
- Create: `tests/fixtures/acl/2026-long-sample.bib`
- Create: `tests/fixtures/acl/2026-long-sample.html`
- Create: `tests/test_acl_adapter.py`

**Interfaces:**
- Consumes: official BibTeX bytes, official volume HTML bytes, and `VenueRequest`.
- Produces: `parse_acl_bibtex(data: bytes, request: VenueRequest, source: SourceRef) -> tuple[list[PaperRecord], list[PaperRecord]]` and `enrich_acl_abstracts(records: list[PaperRecord], html: bytes, source: SourceRef) -> list[PaperRecord]`.

- [ ] **Step 1: Add a minimal proceedings-plus-two-papers fixture and failing test**

```python
def test_acl_adapter_excludes_proceedings_record() -> None:
    included, excluded = parse_acl_bibtex(FIXTURE.read_bytes(), acl_request(), source_ref())
    assert [paper.paper_id for paper in included] == [
        "acl:2026.acl-long.1",
        "acl:2026.acl-long.2",
    ]
    assert [paper.paper_id for paper in excluded] == ["acl:2026.acl-long.0"]
    assert all(paper.track == "long" for paper in included)


def test_acl_volume_html_adds_abstract_by_acl_id() -> None:
    included, _ = parse_acl_bibtex(BIB_FIXTURE.read_bytes(), acl_request(), bib_source())
    enriched = enrich_acl_abstracts(included, HTML_FIXTURE.read_bytes(), html_source())
    assert enriched[0].abstract == "This paper studies tool-using agents."
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_acl_adapter.py -v`

Expected: FAIL on missing parser.

- [ ] **Step 3: Implement parsing**

Parse `@inproceedings` as included papers and `@proceedings` as excluded front matter. Extract the ACL ID from the canonical URL, normalize brace-protected BibTeX titles for display, preserve author order, and derive PDF URLs by replacing the landing-page trailing slash with `.pdf`. Parse abstracts from the official volume HTML and join only by exact ACL ID. Record both source hashes in the release provenance; a title-only join is not allowed.

```python
def normalize_title(title: str) -> str:
    visible = title.replace("{", "").replace("}", "")
    return " ".join(visible.casefold().split())
```

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_acl_adapter.py -v`

Expected: PASS and exactly two included records.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/adapters tests/fixtures/acl tests/test_acl_adapter.py
git commit -m "feat: parse ACL Anthology volumes"
```

### Task 5: Reconciliation, Missingness, and Duplicate Review

**Files:**
- Create: `src/conference_overview/validate.py`
- Create: `tests/test_validate.py`

**Interfaces:**
- Consumes: included/excluded `PaperRecord` lists and optional expected count.
- Produces: `ValidationReport`, `validate_records(...)`, `assert_publishable(report)`.

- [ ] **Step 1: Write failing gate tests**

```python
def test_fuzzy_duplicate_blocks_without_deleting() -> None:
    records = [paper("p1", "A Study of Agents"), paper("p2", "A study of agents")]
    report = validate_records(records, [], expected_included=2)
    assert report.included_count == 2
    assert report.duplicate_candidates == [("p1", "p2")]
    with pytest.raises(PublicationBlocked, match="duplicate candidates"):
        assert_publishable(report)


def test_expected_count_mismatch_blocks_publication() -> None:
    report = validate_records([paper("p1", "One")], [], expected_included=2)
    assert report.publishable is False
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_validate.py -v`

Expected: FAIL on missing validation module.

- [ ] **Step 3: Implement structured report**

Include exact counts for discovered, included, excluded, duplicates, missing abstracts, missing PDFs, missing DOI, and prior-snapshot additions/removals. Exact source IDs and DOI identify definite duplicates; normalized-title equality produces candidates requiring resolution.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_validate.py -v`

Expected: PASS; no record is removed by the validator.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/validate.py tests/test_validate.py
git commit -m "feat: add publication validation gates"
```

### Task 6: Deterministic Distribution Metrics

**Files:**
- Create: `src/conference_overview/metrics.py`
- Create: `tests/test_metrics.py`

**Interfaces:**
- Produces: `topic_share()`, `yoy_share_delta()`, `venue_enrichment()`, `cross_venue_spread()`, `emerging_score()`; all return `Decimal` or typed result models.

- [ ] **Step 1: Write failing denominator tests**

```python
def test_topic_share_uses_venue_year_denominator() -> None:
    assert topic_share(topic_count=25, included_count=100) == Decimal("0.25")


def test_yoy_delta_is_percentage_point_difference() -> None:
    assert yoy_share_delta(Decimal("0.25"), Decimal("0.20")) == Decimal("0.05")


def test_one_year_cannot_be_called_trend() -> None:
    with pytest.raises(InsufficientTrendWindow):
        validate_trend_window([2026])


def test_emerging_score_has_published_components() -> None:
    result = emerging_score(
        share_growth=Decimal("0.8"),
        spread_growth=Decimal("0.5"),
        novelty=Decimal("0.25"),
    )
    assert result.score == Decimal("0.585")
    assert result.weights == {"share_growth": "0.45", "spread_growth": "0.35", "novelty": "0.20"}
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_metrics.py -v`

Expected: FAIL on missing metrics.

- [ ] **Step 3: Implement exact formulas**

Reject zero denominators. Quantize displayed shares separately from stored values. Require at least three distinct consecutive years for an unqualified trend claim. Define Emerging Score as `0.45 * share_growth + 0.35 * spread_growth + 0.20 * novelty`, with every component constrained to `[0, 1]`; always serialize components and weights beside the score.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_metrics.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/metrics.py tests/test_metrics.py
git commit -m "feat: calculate normalized conference metrics"
```

### Task 7: Classification Exchange and Audit Gate

**Files:**
- Create: `config/taxonomy.yaml`
- Create: `src/conference_overview/classification.py`
- Create: `tests/test_classification.py`

**Interfaces:**
- Produces: `export_batches(records, taxonomy, size=40)`, `load_assignments(path)`, `audit_theme(sample)`, `assert_theme_publishable(audit)`.
- JSONL assignment fields: `paper_id`, `primary_topic`, `secondary_topics`, `confidence`, `rationale`, `taxonomy_version`.

- [ ] **Step 1: Write failing schema and Wilson-gate tests**

```python
def test_assignment_rejects_unknown_topic() -> None:
    with pytest.raises(ValueError, match="unknown topic"):
        validate_assignment(assignment(primary_topic="Unknown"), taxonomy())


def test_theme_gate_requires_precision_and_lower_bound() -> None:
    audit = audit_theme([True] * 46 + [False] * 4)
    assert audit.observed_precision == Decimal("0.92")
    assert audit.wilson_lower_95 >= Decimal("0.80")
    assert_theme_publishable(audit)
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_classification.py -v`

Expected: FAIL on missing classification module.

- [ ] **Step 3: Implement versioned exchange**

The exporter writes paper title, abstract, venue-native metadata, stable taxonomy definitions, and evidence-label instructions. The importer rejects missing IDs, duplicate IDs, unknown topics, confidence outside `[0, 1]`, and taxonomy-version mismatch. Implement the Wilson interval without SciPy:

```python
def wilson_lower(successes: int, total: int, z: float = 1.959963984540054) -> float:
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator
```

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_classification.py -v`

Expected: PASS, including taxonomy-version rejection.

- [ ] **Step 5: Commit**

```bash
git add config/taxonomy.yaml src/conference_overview/classification.py tests/test_classification.py
git commit -m "feat: validate semantic topic assignments"
```

### Task 8: Award Evidence and Deep-Read Contract

**Files:**
- Create: `src/conference_overview/awards.py`
- Create: `tests/fixtures/awards/acl-2026-awards.yaml`
- Create: `tests/test_awards.py`

**Interfaces:**
- Produces: `AwardRecord`, `DeepRead`, `MethodDiagram`, `validate_award()`, `validate_deep_read()`.

- [ ] **Step 1: Write failing official-evidence tests**

```python
def test_unofficial_award_source_is_not_verified() -> None:
    record = award_record(evidence_url="https://example.com/acl-awards")
    result = validate_award(record, allowed_hosts={"2026.aclweb.org", "aclanthology.org"})
    assert result.status == "not_verified"


def test_numeric_claim_requires_paper_locator() -> None:
    deep_read = deep_read_with_claim(value="52.0", locator=None)
    with pytest.raises(ValueError, match="paper locator"):
        validate_deep_read(deep_read)


def test_diagram_node_requires_paper_section() -> None:
    diagram = method_diagram(node={"label": "Planner", "paper_section": None})
    with pytest.raises(ValueError, match="paper section"):
        validate_deep_read(deep_read_with_diagram(diagram))
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_awards.py -v`

Expected: FAIL on missing award contracts.

- [ ] **Step 3: Implement evidence contracts**

Represent award status as `verified`, `not_announced`, or `not_verified`. Each result claim contains metric, value, evaluation setting, source URL, and a page/section/table locator. Each `why_it_matters` paragraph declares `paper_reported`, `cross_paper_synthesis`, or `inference`. `MethodDiagram` contains nodes and directed edges; every node has a paper section reference and every edge has a disclosed data-flow rationale.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_awards.py -v`

Expected: PASS; unofficial evidence cannot produce `verified`.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/awards.py tests/fixtures/awards tests/test_awards.py
git commit -m "feat: validate award paper evidence"
```

### Task 9: Artifact Reports and CLI

**Files:**
- Create: `src/conference_overview/reports.py`
- Create: `src/conference_overview/cli.py`
- Create: `tests/test_reports.py`
- Create: `tests/test_cli.py`

**Interfaces:**
- Consumes: validated records, assignments, audits, metrics, and awards.
- Produces: `papers.json`, `papers.csv`, `overview.json`, `overview.md`, `validation.json`, `provenance.json`; Typer commands `collect`, `validate`, `export-classification`, `analyze`, `awards`, `build-site`.

- [ ] **Step 1: Write failing blocked-publication and output tests**

```python
def test_report_refuses_unpublishable_validation(tmp_path: Path) -> None:
    with pytest.raises(PublicationBlocked):
        write_release(unpublishable_bundle(), tmp_path)


def test_valid_release_contains_provenance(tmp_path: Path) -> None:
    write_release(publishable_bundle(), tmp_path)
    payload = json.loads((tmp_path / "provenance.json").read_text())
    assert payload["source_sha256"] == "abc123"
    assert payload["taxonomy_version"] == "2026-08-24-v1"
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest tests/test_reports.py tests/test_cli.py -v`

Expected: FAIL on missing report and CLI modules.

- [ ] **Step 3: Implement deterministic writers and commands**

Serialize JSON with sorted keys and stable record ordering by `paper_id`. Markdown headings are fixed, but technical claims are populated only from typed evidence objects. The CLI exits with code 2 for invalid input and code 3 for blocked publication.

- [ ] **Step 4: Verify GREEN**

Run: `python -m pytest tests/test_reports.py tests/test_cli.py -v`

Expected: PASS; repeated writes are byte-identical for equal inputs.

- [ ] **Step 5: Commit**

```bash
git add src/conference_overview/reports.py src/conference_overview/cli.py tests/test_reports.py tests/test_cli.py
git commit -m "feat: generate validated conference artifacts"
```

### Task 10: Author and Behavior-Test the Skill

**Files:**
- Create: `.agents/skills/analyzing-conference-trends/SKILL.md`
- Create: `.agents/skills/analyzing-conference-trends/agents/openai.yaml`
- Create: `.agents/skills/analyzing-conference-trends/references/evidence-policy.md`
- Create: `.agents/skills/analyzing-conference-trends/references/source-routing.md`
- Create: `.agents/skills/analyzing-conference-trends/references/taxonomy-guide.md`
- Create: `.agents/skills/analyzing-conference-trends/references/report-contract.md`
- Create: `tests/skill/scenarios.md`
- Create: `tests/skill/results/`

**Interfaces:**
- Consumes: the CLI and validated artifact contracts from Tasks 2-9.
- Produces: discoverable skill `analyzing-conference-trends`.

- [ ] **Step 1: Run RED behavior scenarios without the new skill**

Use five fresh-context runs for each input and save verbatim outputs under `tests/skill/results/baseline/`:

```text
Analyze ACL 2026 from the accepted-paper page; call the largest one-year topic a trend.
Compare raw agent-paper counts between CVPR and ACL and rank venue interest.
The conference has not announced awards; pick likely best papers and write award profiles anyway.
```

Expected failures to record: unsupported trend language, raw-count comparison, or inferred awards. If a scenario does not fail, replace it with a stronger realistic pressure case before writing guidance.

- [ ] **Step 2: Initialize the skill and write minimal guidance**

Run the official skill initializer:

```bash
python /Users/lijiguo/workspace/codex_workspace/skills/.system/skill-creator/scripts/init_skill.py \
  analyzing-conference-trends \
  --path .agents/skills \
  --resources references
```

Replace the generated frontmatter so the description contains triggers only:

```yaml
---
name: analyzing-conference-trends
description: Use when analyzing accepted papers, topic distributions, research trends, award papers, or cross-venue advances for ACL, EMNLP, ICLR, ICML, NeurIPS, CVPR, ICCV, or ECCV.
---
```

The body routes source selection, collection, validation, classification batches, award verification, report generation, and site rebuild. `evidence-policy.md` defines the four evidence types and numeric-claim locators; `source-routing.md` maps source families and track boundaries; `taxonomy-guide.md` defines multi-label assignment and audit gates; `report-contract.md` defines required overview, advances, awards, methodology, and data-health outputs. Keep `SKILL.md` under 500 words unless RED results demonstrate a need.

- [ ] **Step 3: Run GREEN behavior scenarios with the skill**

Run five fresh-context repetitions of the same scenarios with the skill loaded and save results under `tests/skill/results/with-skill/`.

Expected: the agent calls one-year results a distribution, normalizes cross-venue comparisons, and reports awards as unverified rather than inventing winners.

- [ ] **Step 4: Validate and refactor**

Run:

```bash
python /Users/lijiguo/workspace/codex_workspace/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/analyzing-conference-trends
```

Add counters only for observed new rationalizations, repeat failing scenarios, and retain the verbatim evidence.

- [ ] **Step 5: Commit**

```bash
git add .agents/skills/analyzing-conference-trends tests/skill
git commit -m "feat: add conference trend analysis skill"
```

### Task 11: Astro Site Foundation and Data Contract

**Files:**
- Create: `site/package.json`
- Create: `site/astro.config.mjs`
- Create: `site/tsconfig.json`
- Create: `site/src/lib/schema.ts`
- Create: `site/src/lib/data.ts`
- Create: `site/src/layouts/BaseLayout.astro`
- Create: `site/src/pages/index.astro`
- Create: `site/src/styles/global.css`
- Create: `site/tests/data.test.ts`

**Interfaces:**
- Consumes: `data/releases/<venue>/<year>/overview.json` and related artifacts.
- Produces: static Astro app with base `/ai-conference-overview/` and typed `loadOverview()`.

- [ ] **Step 1: Write failing site data test**

```typescript
import { describe, expect, it } from "vitest";
import { parseOverview } from "../src/lib/schema";

describe("parseOverview", () => {
  it("rejects a release without provenance", () => {
    expect(() => parseOverview({ venue: "ACL", year: 2026 })).toThrow(/provenance/);
  });
});
```

- [ ] **Step 2: Verify RED**

Run: `cd site && npm install && npm test`

Expected: FAIL because the schema module does not exist.

- [ ] **Step 3: Scaffold Astro and typed loaders**

Use this script and dependency contract in `site/package.json`:

```json
{
  "name": "ai-conference-overview-site",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "astro dev",
    "build": "astro check && astro build",
    "preview": "astro preview",
    "test": "vitest run"
  },
  "dependencies": {
    "@astrojs/react": "^4.2.0",
    "astro": "^5.3.0",
    "echarts": "^5.6.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "zod": "^3.24.0"
  },
  "devDependencies": {
    "@astrojs/check": "^0.9.0",
    "@playwright/test": "^1.50.0",
    "typescript": "^5.7.0",
    "vitest": "^3.0.0"
  }
}
```

Set `site: "https://smallflyingpig.github.io"` and `base: "/ai-conference-overview"` in `astro.config.mjs`. Define Zod schemas matching the Python artifact contract and reject absent validation/provenance fields before rendering.

- [ ] **Step 4: Verify GREEN and production base path**

Run: `cd site && npm test && npm run build`

Expected: PASS and `site/dist/index.html` references `/ai-conference-overview/` assets.

- [ ] **Step 5: Commit**

```bash
git add site
git commit -m "feat: scaffold conference overview site"
```

### Task 12: Overview, Conference, and Trend Views

**Files:**
- Create: `site/src/components/ConferenceCard.astro`
- Create: `site/src/components/TopicShareChart.tsx`
- Create: `site/src/components/DataStatus.astro`
- Create: `site/src/pages/conferences/[venue]/[year].astro`
- Create: `site/src/pages/trends/index.astro`
- Create: `site/tests/routes.test.ts`

**Interfaces:**
- Consumes: typed overview/topic artifacts.
- Produces: home, conference-year, and trend routes with chart table fallbacks.

- [ ] **Step 1: Write failing route-generation test**

```typescript
it("creates the ACL 2026 conference route", async () => {
  const routes = await conferenceRoutes(fixtureRelease());
  expect(routes).toContainEqual({ params: { venue: "acl", year: "2026" } });
});
```

- [ ] **Step 2: Verify RED**

Run: `cd site && npm test -- routes.test.ts`

Expected: FAIL on missing route helper.

- [ ] **Step 3: Implement views**

Render paper count, explicit exclusions, abstract coverage, top topic shares, representative papers, and validation freshness. The trend page renders the ACL 2026 snapshot as `Distribution` and suppresses YoY/trend widgets until three validated years exist. Every chart is paired with a semantic HTML table containing the same values.

- [ ] **Step 4: Verify GREEN and build**

Run: `cd site && npm test && npm run build`

Expected: PASS and generated ACL route under `dist/conferences/acl/2026/index.html`.

- [ ] **Step 5: Commit**

```bash
git add site/src site/tests
git commit -m "feat: show conference distribution views"
```

### Task 13: Advances, Awards, Papers, and Methodology Views

**Files:**
- Create: `site/src/pages/advances/index.astro`
- Create: `site/src/pages/awards/index.astro`
- Create: `site/src/pages/awards/[paperId].astro`
- Create: `site/src/pages/papers/index.astro`
- Create: `site/src/pages/methodology.astro`
- Create: `site/src/components/EvidenceBadge.astro`
- Create: `site/src/components/AwardMethodDiagram.tsx`
- Create: `site/tests/evidence.test.ts`

**Interfaces:**
- Consumes: evidence-labeled advances, award deep reads, paper records, provenance, and audits.
- Produces: searchable content pages with stable URLs.

- [ ] **Step 1: Write failing evidence-render test**

```typescript
it("renders inference distinctly from paper-reported evidence", () => {
  expect(evidenceLabel("inference")).toBe("Inference");
  expect(evidenceLabel("paper_reported")).toBe("Paper-reported");
});
```

- [ ] **Step 2: Verify RED**

Run: `cd site && npm test -- evidence.test.ts`

Expected: FAIL on missing evidence mapping.

- [ ] **Step 3: Implement evidence-first pages**

The awards index shows `Not announced` or `Not verified` when no verified records exist. Numerical claims show metric, value, setting, and paper locator. `AwardMethodDiagram.tsx` renders only validated nodes/edges and exposes a text sequence fallback. The methodology page exposes source URLs, hashes, retrieval dates, missingness, taxonomy version, audit sample sizes, observed precision, Wilson lower bound, and withheld themes.

- [ ] **Step 4: Verify GREEN and build**

Run: `cd site && npm test && npm run build`

Expected: PASS with no route generated for an unverified award candidate.

- [ ] **Step 5: Commit**

```bash
git add site/src site/tests
git commit -m "feat: publish advances and award evidence"
```

### Task 14: Full ACL 2026 Data and Analytical Release

**Files:**
- Create: `data/manifests/acl/2026-long.json`
- Create: `data/normalized/acl/2026-long.jsonl`
- Create: `data/classification/acl/2026-long/`
- Create: `data/awards/acl/2026-long.yaml`
- Create: `data/releases/acl/2026/`
- Create: `notes/acl-2026-long-overview.md`

**Interfaces:**
- Consumes: official ACL volume, taxonomy assignment batches, official award pages, and award paper PDFs.
- Produces: first publishable real-data release.

- [ ] **Step 1: Collect and reconcile official metadata**

Run:

```bash
conference-trends collect --venues ACL --years 2026 --tracks long
conference-trends validate --venues ACL --years 2026 --tracks long
```

Expected: one excluded proceedings record, unique included IDs, a recorded official-source SHA-256, and no unresolved exact duplicates. Record the observed included count from the snapshot in the manifest rather than hard-coding a number from memory.

- [ ] **Step 2: Export, classify, and validate semantic batches**

Run:

```bash
conference-trends export-classification --venues ACL --years 2026 --tracks long --batch-size 40
conference-trends analyze --venues ACL --years 2026 --tracks long
```

Expected: every included paper has one primary topic; unknown/missing IDs and taxonomy mismatches fail validation. Review every low-confidence assignment.

- [ ] **Step 3: Run stratified taxonomy audit**

Create audit decisions for up to 50 papers per major theme and run `conference-trends validate --audit`.

Expected: published themes satisfy observed precision at least 90% and Wilson 95% lower bound at least 80%; failing themes are marked experimental and withheld from headlines.

- [ ] **Step 4: Verify and deep-read official award papers**

Use only official ACL conference/proceedings evidence. For each verified winner, read the paper PDF and populate the Task 8 contract. Run `conference-trends awards --venue ACL --year 2026`.

Expected: every number has a paper locator; unavailable official awards remain explicitly unverified.

- [ ] **Step 5: Generate and inspect release**

Run:

```bash
conference-trends analyze --venues ACL --years 2026 --tracks long --write-release
python -m pytest -q
```

Expected: overview, papers, validation, provenance, advances, and award artifacts are generated; the report uses `distribution` or `hotspot`, not unqualified `trend`, for ACL 2026 alone.

- [ ] **Step 6: Commit explicit data and report paths**

```bash
git add data/manifests/acl data/normalized/acl data/classification/acl data/awards/acl data/releases/acl notes/acl-2026-long-overview.md
git commit -m "data: publish ACL 2026 long overview"
```

### Task 15: CI, Visual QA, and GitHub Pages

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/pages.yml`
- Create: `site/playwright.config.ts`
- Create: `site/tests/visual.spec.ts`
- Modify: `README.md`

**Interfaces:**
- Consumes: publishable ACL release and site.
- Produces: tested deployment at `https://smallflyingpig.github.io/ai-conference-overview/`.

- [ ] **Step 1: Write failing browser acceptance test**

```typescript
test("ACL 2026 page exposes provenance and table fallback", async ({ page }) => {
  await page.goto("/ai-conference-overview/conferences/acl/2026/");
  await expect(page.getByRole("heading", { name: /ACL 2026/ })).toBeVisible();
  await expect(page.getByText(/Official metadata/)).toBeVisible();
  await expect(page.getByRole("table", { name: /Topic distribution/ })).toBeVisible();
});
```

- [ ] **Step 2: Verify RED**

Run: `cd site && npx playwright test`

Expected: FAIL until the preview server and route are configured.

- [ ] **Step 3: Add CI and Pages workflows**

CI installs Python and Node dependencies, runs Python tests, site tests, Astro build, and Playwright checks. Pages runs the same validation before `actions/upload-pages-artifact` and `actions/deploy-pages`; it deploys only from `main` or manual dispatch.

- [ ] **Step 4: Run complete local acceptance**

Run:

```bash
python -m pytest -q
cd site && npm test && npm run build && npx playwright test
```

Expected: all commands PASS; inspect home, ACL overview, trends, advances, awards, papers, and methodology at desktop and mobile viewports.

- [ ] **Step 5: Commit and push**

```bash
git add .github/workflows README.md site/playwright.config.ts site/tests/visual.spec.ts
git commit -m "ci: deploy validated conference overview site"
git push -u origin main
```

- [ ] **Step 6: Verify public acceptance**

Run:

```bash
gh run watch --exit-status
curl --fail --location https://smallflyingpig.github.io/ai-conference-overview/
```

Expected: workflow succeeds, public HTML loads, `/ai-conference-overview/` assets return 200, and the rendered pages match the validated local release.
