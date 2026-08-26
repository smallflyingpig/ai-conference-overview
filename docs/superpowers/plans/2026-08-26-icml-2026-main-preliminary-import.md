# ICML 2026 Main Conference Preliminary Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import ICML 2026 Main Conference papers from official ICML/OpenReview data as a clearly labeled preliminary release, expose searchable English-abstract paper pages, and preserve the existing ACL release unchanged.

**Architecture:** Add an ICML-specific read-only adapter behind a small venue dispatcher while leaving the proven ACL parser and analysis path intact. A typed preliminary-publication context relaxes classification-only requirements without relaxing paper identity, source, reconciliation, hash, or route checks. The Astro site loads every selected venue/year release, renders a compact ICML conference page and English paper details, and keeps topic/trend/award sections unavailable until a later PMLR-backed final release.

**Tech Stack:** Python 3.11+, Pydantic 2, httpx, Typer, pytest, Astro 5, TypeScript, Zod 3, Vitest, Playwright, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-08-26-icml-2026-main-preliminary-import-design.md`

## Global Constraints

- Canonical scope is exactly `ICML / 2026 / main`; ICML does not use ACL's `long` label.
- Preliminary accepted-paper identity comes from the official OpenReview venue ID `ICML.cc/2026/Conference`; ICML virtual data enriches presentation and session metadata.
- Exclude Position Papers, Journal-to-Conference, workshops, tutorials, expo, and records whose Main Conference identity cannot be established.
- Merge poster, spotlight, and oral event rows by OpenReview forum ID; never count presentation rows as separate papers.
- Store immutable source bytes plus retrieval time, byte size, URL, and SHA-256; stop before writing selected output if pagination or reconciliation is incomplete.
- The preliminary site may publish paper discovery and English abstracts only. Distribution, trends, advances, awards, and Chinese summaries remain unavailable.
- Missing abstracts and PDFs are reported as missing metadata and are never inferred from titles.
- Preserve all current ACL artifacts, Chinese content packages, routes, and rendered behavior.
- Keep the existing exact-six release generation and hash-selected `current.json` contract.
- User-facing copy is Chinese except for precise conference, track, model, API, and paper identifiers. Do not expose internal terms such as “门禁、约束、核验、结论、证据、审计、契约、工件、赋值”.
- Mobile acceptance viewport is 390 × 844; page overflow must be at most 1 px and English abstract text must compute to at least 16 px.
- PMLR Volume 306 remains the final source. A 404 keeps the release preliminary and must not replace any selected generation.

---

## File Structure

- `config/venues.yaml`: register ICML 2026 Main Conference sources and final PMLR target.
- `config/award-host-policy.json`: checked-in generated host policy including the ICML scope with an empty host list.
- `src/conference_overview/models.py`: typed source-route and preliminary-publication models.
- `src/conference_overview/registry.py`: normalize configured adapter/source fields without changing ACL normalization.
- `src/conference_overview/adapters/icml.py`: parse official OpenReview notes and ICML virtual event/abstract data.
- `src/conference_overview/scope.py`: venue-neutral collection and release paths.
- `src/conference_overview/conference_pipeline.py`: dispatch collection, validation, preliminary release creation, snapshot rebuild, and PMLR status checks.
- `src/conference_overview/cli.py`: route `collect`, `validate`, and `analyze --write-release` through the venue-neutral functions.
- `src/conference_overview/reports.py`: serialize and validate preliminary release context while retaining the exact-six format.
- `site/src/lib/schema.ts`: mirror the preliminary release context and its conditional requirements.
- `site/src/lib/data.ts`: discover and load multiple selected releases safely.
- `site/src/lib/views.ts`: build distribution or papers-only conference views according to declared availability.
- `site/src/lib/evidence.ts`: aggregate papers from multiple releases and generate producer-authoritative route keys.
- `site/src/pages/index.astro`: render ACL and ICML cards from loaded releases.
- `site/src/pages/conferences/[venue]/[year].astro`: render distribution or preliminary papers-only variants.
- `site/src/pages/papers/index.astro`: add venue filtering and internal detail links.
- `site/src/pages/papers/[paperId].astro`: render ICML English-abstract details.
- `site/src/styles/global.css`: implement the approved compact desktop and 390 px mobile layout.
- `tests/fixtures/icml/`: small official-shape fixtures covering pagination, track separation, duplicate presentation rows, and missing abstracts.
- `tests/test_icml_adapter.py`, `tests/test_conference_pipeline.py`, `tests/test_reports.py`, `tests/test_cli.py`, `tests/test_registry.py`: Python behavior and failure-path coverage.
- `site/tests/fixtures/icml-preliminary-release/`, `site/tests/data.test.ts`, `site/tests/routes.test.ts`, `site/tests/evidence.test.ts`, `site/tests/styles.test.ts`, `site/tests/visual.spec.ts`: release, routing, rendering, and responsive coverage.
- `scripts/verify_icml_live_release.py`: read-only final acceptance of source hashes, counts, release pointer, and site routes.
- `README.md`: describe ICML's preliminary scope and regeneration commands.

---

### Task 1: Register the ICML source contract and venue-neutral scope paths

**Files:**
- Modify: `config/venues.yaml`
- Modify: `config/award-host-policy.json`
- Modify: `src/conference_overview/models.py`
- Modify: `src/conference_overview/registry.py`
- Create: `src/conference_overview/scope.py`
- Modify: `tests/test_registry.py`
- Create: `tests/test_scope.py`

**Interfaces:**
- Consumes: existing `normalize_request(venue: str, year: int, track: str | None) -> VenueRequest`.
- Produces: `VenueRequest.adapter`, `VenueRequest.source_urls`, `VenueRequest.final_source_url`, `VenueRequest.publication_status`, and `ScopePaths.for_request(root, request)`.

- [ ] **Step 1: Write registry tests that describe the ICML route**

Add to `tests/test_registry.py`:

```python
def test_icml_main_request_uses_official_preliminary_sources() -> None:
    request = normalize_request("icml", 2026, None)

    assert request.venue == "ICML"
    assert request.track == "main"
    assert request.adapter == "icml_virtual"
    assert request.source_key == "icml-2026-main-preliminary"
    assert request.publication_status == "preliminary_official_program"
    assert str(request.source_urls["papers_page"]) == (
        "https://icml.cc/virtual/2026/papers.html"
    )
    assert str(request.source_urls["events"]) == (
        "https://icml.cc/static/virtual/data/icml-2026-orals-posters.json"
    )
    assert str(request.source_urls["abstracts"]) == (
        "https://icml.cc/static/virtual/data/icml-2026-abstracts.json"
    )
    assert str(request.source_urls["openreview_group"]) == (
        "https://openreview.net/group?id=ICML.cc/2026/Conference"
    )
    assert str(request.final_source_url) == "https://proceedings.mlr.press/v306/"
    assert request.official_award_hosts == ()


def test_icml_rejects_acl_track_name() -> None:
    request = normalize_request("ICML", 2026, "long")
    assert request.source_key is None
```

- [ ] **Step 2: Run the registry tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_registry.py -q
```

Expected: the ICML request has no configured year/track route or lacks `adapter`, `source_urls`, `final_source_url`, and `publication_status`.

- [ ] **Step 3: Add typed route fields and ICML configuration**

Extend `VenueRequest` in `src/conference_overview/models.py`:

```python
class VenueRequest(BaseModel):
    venue: str
    year: int
    track: str | None = None
    adapter: str | None = None
    source_key: str | None = None
    source_urls: dict[str, HttpUrl] = Field(default_factory=dict)
    final_source_url: HttpUrl | None = None
    publication_status: str | None = None
    bibtex_url: HttpUrl | None = None
    volume_url: HttpUrl | None = None
    official_award_hosts: tuple[str, ...] = Field(default_factory=tuple)
```

Add the following route under `ICML` in `config/venues.yaml`:

```yaml
  ICML:
    aliases:
      - ICML
    years:
      2026:
        default_track: main
        tracks:
          main:
            adapter: icml_virtual
            source_key: icml-2026-main-preliminary
            publication_status: preliminary_official_program
            source_urls:
              papers_page: https://icml.cc/virtual/2026/papers.html
              events: https://icml.cc/static/virtual/data/icml-2026-orals-posters.json
              abstracts: https://icml.cc/static/virtual/data/icml-2026-abstracts.json
              openreview_group: https://openreview.net/group?id=ICML.cc/2026/Conference
            final_source_url: https://proceedings.mlr.press/v306/
            official_award_hosts: []
```

Update `normalize_request()` to validate `source_urls` as a string-to-URL mapping and populate the new fields. Keep `bibtex_url` and `volume_url` unchanged for ACL.

Regenerate the checked-in host policy:

```bash
.venv/bin/python scripts/generate_award_host_policy.py
```

- [ ] **Step 4: Write venue-neutral path tests**

Create `tests/test_scope.py`:

```python
from pathlib import Path

import pytest

from conference_overview.registry import normalize_request
from conference_overview.scope import ScopePaths


def test_icml_paths_are_isolated_from_acl(tmp_path: Path) -> None:
    paths = ScopePaths.for_request(
        tmp_path, normalize_request("ICML", 2026, "main")
    )

    assert paths.manifest == tmp_path / "data/manifests/icml/2026-main.json"
    assert paths.normalized == tmp_path / "data/normalized/icml/2026-main.jsonl"
    assert paths.snapshots == tmp_path / "data/snapshots/icml/2026-main"
    assert paths.analysis == tmp_path / "data/analysis/icml/2026-main"
    assert paths.release == tmp_path / "data/releases/ICML/2026"
    assert paths.notes == tmp_path / "notes/icml-2026-main-overview.md"


def test_scope_paths_reject_unsafe_segments(tmp_path: Path) -> None:
    request = normalize_request("ICML", 2026, "main").model_copy(
        update={"track": "../main"}
    )
    with pytest.raises(ValueError, match="safe scope segment"):
        ScopePaths.for_request(tmp_path, request)
```

- [ ] **Step 5: Run the path tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_scope.py -q
```

Expected: import failure because `conference_overview.scope` does not exist.

- [ ] **Step 6: Implement `ScopePaths`**

Create `src/conference_overview/scope.py` with a frozen dataclass whose `for_request()` lowercases the venue only for data subdirectories, preserves the canonical uppercase venue for release directories, validates segments with `^[A-Za-z0-9-]+$`, and exposes the six paths asserted above. Do not replace the ACL-only `pipeline.ScopePaths` yet; this new class is consumed by the venue dispatcher in Task 3.

- [ ] **Step 7: Verify Task 1 GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_registry.py tests/test_scope.py -q
.venv/bin/python -m ruff check config src/conference_overview tests/test_registry.py tests/test_scope.py
.venv/bin/python scripts/generate_award_host_policy.py --check
```

Expected: all tests pass, Ruff reports no errors, and the generated host policy is current.

- [ ] **Step 8: Commit Task 1**

```bash
git add config/venues.yaml config/award-host-policy.json src/conference_overview/models.py src/conference_overview/registry.py src/conference_overview/scope.py tests/test_registry.py tests/test_scope.py
git commit -m "feat: register ICML 2026 main scope"
```

---

### Task 2: Parse official ICML and OpenReview records without mixing tracks

**Files:**
- Create: `src/conference_overview/adapters/icml.py`
- Create: `tests/fixtures/icml/events-page-1.json`
- Create: `tests/fixtures/icml/events-page-2.json`
- Create: `tests/fixtures/icml/abstracts.json`
- Create: `tests/fixtures/icml/openreview-accepted.json`
- Create: `tests/test_icml_adapter.py`

**Interfaces:**
- Consumes: configured ICML URLs from `VenueRequest.source_urls` and existing `SourceRef`/`PaperRecord` models.
- Produces: `FetchedIcmlSource`, `IcmlRawCorpus`, `IcmlParseResult`, `fetch_icml_sources()`, and `parse_icml_sources()`.

- [ ] **Step 1: Create minimal official-shape fixtures**

Use two pages whose combined event rows contain:

- one Main Conference regular poster;
- one Main Conference spotlight with both poster and oral rows sharing a forum ID;
- one Position Paper using `ICML.cc/2026/Position_Paper_Track`;
- one Journal-to-Conference row;
- one Main Conference paper without an abstract;
- a final page whose `next` is `null`.

The OpenReview fixture must contain exactly the three accepted Main Conference forum IDs and camera-ready title, authors, abstract, PDF value, `venueid: ICML.cc/2026/Conference`, and invitation IDs. The ICML fixture may contain only the two presented papers so the test proves that proceedings-only accepted papers remain included through OpenReview.

- [ ] **Step 2: Write RED parser tests**

Create `tests/test_icml_adapter.py` with focused tests:

```python
def test_parser_uses_openreview_venueid_as_the_accepted_population() -> None:
    result = parse_icml_sources(fixture_corpus(), icml_request())
    assert [paper.paper_id for paper in result.included] == [
        "icml:2026:forum-main-1",
        "icml:2026:forum-main-2",
        "icml:2026:forum-main-3",
    ]
    assert {paper.track for paper in result.included} == {"main"}
    assert all(
        paper.native_metadata["openreview_venueid"]
        == "ICML.cc/2026/Conference"
        for paper in result.included
    )


def test_parser_merges_poster_and_oral_rows_without_duplicate_papers() -> None:
    result = parse_icml_sources(fixture_corpus(), icml_request())
    spotlight = next(
        paper for paper in result.included
        if paper.paper_id == "icml:2026:forum-main-2"
    )
    assert spotlight.native_metadata["presentation_types"] == ["Oral", "Poster"]
    assert spotlight.native_metadata["event_ids"] == ["102", "202"]


def test_parser_excludes_non_main_openreview_venueids() -> None:
    result = parse_icml_sources(fixture_corpus(), icml_request())
    assert {paper.native_metadata["openreview_venueid"] for paper in result.excluded} == {
        "ICML.cc/2026/Position_Paper_Track",
        "ICML.cc/2026/Journal_Track",
    }


def test_parser_keeps_missing_abstract_as_partial() -> None:
    result = parse_icml_sources(fixture_corpus(), icml_request())
    paper = next(
        paper for paper in result.included
        if paper.paper_id == "icml:2026:forum-main-3"
    )
    assert paper.abstract is None
    assert paper.status is RecordStatus.PARTIAL


def test_parser_rejects_conflicting_duplicate_event_identity() -> None:
    corpus = fixture_corpus_with_conflicting_title()
    with pytest.raises(IcmlSourceFormatError, match="conflicting event identity"):
        parse_icml_sources(corpus, icml_request())
```

- [ ] **Step 3: Run parser tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_icml_adapter.py -q
```

Expected: import failure because the ICML adapter does not exist.

- [ ] **Step 4: Implement typed ICML parsing**

Create `src/conference_overview/adapters/icml.py` with these public shapes:

```python
@dataclass(frozen=True)
class FetchedIcmlSource:
    kind: str
    url: str
    data: bytes
    source: SourceRef


@dataclass(frozen=True)
class IcmlRawCorpus:
    event_pages: tuple[FetchedIcmlSource, ...]
    openreview_pages: tuple[FetchedIcmlSource, ...]


@dataclass(frozen=True)
class IcmlParseResult:
    included: tuple[PaperRecord, ...]
    excluded: tuple[PaperRecord, ...]
    unresolved: tuple[PaperRecord, ...]
    presentation_row_count: int
```

Implement `parse_icml_sources(corpus, request)` as follows:

1. decode every source as UTF-8 JSON and reject incomplete or non-object payloads;
2. derive the accepted population only from OpenReview notes whose `content.venueid.value` equals `ICML.cc/2026/Conference`;
3. build `paper_id` from the immutable forum ID, never from event ID or title;
4. enrich records from ICML events only when `paper_url` contains the same forum ID;
5. merge and sort `event_ids`, `presentation_types`, and `sessions` deterministically;
6. create explicit excluded records for known non-main venue IDs and unresolved records for unknown venue IDs or malformed accepted notes;
7. mark an included record `complete` when it has an abstract and `partial` otherwise;
8. sort each output tuple by `paper_id`.

Use OpenReview camera-ready title/authors/abstract as the canonical paper content. ICML event titles and author lists are comparison fields; a mismatch enters `unresolved` rather than overwriting camera-ready metadata.

- [ ] **Step 5: Add pagination and source-safety RED tests**

Add tests using `respx` and `httpx.Client`:

```python
@pytest.mark.parametrize("next_url", [
    "https://evil.example/api?page=2",
    "ftp://icml.cc/api?page=2",
])
def test_fetch_rejects_unsafe_pagination(next_url: str, client: httpx.Client) -> None:
    route_seed(next_url=next_url)
    with pytest.raises(IcmlSourceFormatError, match="pagination URL"):
        fetch_icml_sources(icml_request(), client)


def test_fetch_upgrades_only_icml_same_host_http_next(client: httpx.Client) -> None:
    route_seed(next_url="http://icml.cc/api/miniconf/events?offset=2")
    route_second_page("https://icml.cc/api/miniconf/events?offset=2")
    corpus = fetch_icml_sources(icml_request(), client)
    assert len(corpus.event_pages) == 2


def test_fetch_rejects_page_cycle_and_count_mismatch(client: httpx.Client) -> None:
    route_cycle_with_declared_count(3)
    with pytest.raises(IcmlSourceFormatError, match="cycle|count"):
        fetch_icml_sources(icml_request(), client)
```

- [ ] **Step 6: Run pagination tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_icml_adapter.py -q
```

Expected: parser tests pass but pagination tests fail because `fetch_icml_sources()` is absent.

- [ ] **Step 7: Implement bounded official-source collection**

Implement `fetch_icml_sources(request, client)` with:

- the configured ICML event seed;
- OpenReview API v2 accepted-note pages queried with exact `content.venueid=ICML.cc/2026/Conference`;
- `limit=1000`, monotonically increasing offsets, a maximum of 100 pages, and URL-set cycle detection;
- same-host `http://icml.cc/...` pagination canonicalized to HTTPS;
- all other schemes/hosts rejected before the request;
- `count` equality checked against accumulated rows;
- every fetched response passed through the existing content-length-aware `fetch_bytes()` and represented as `FetchedIcmlSource`.

If the OpenReview API returns an availability error after bounded retries, raise `SourceFetchError`. Do not fall back to a third-party mirror or infer the accepted population from the event schedule.

- [ ] **Step 8: Verify Task 2 GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_icml_adapter.py -q
.venv/bin/python -m ruff check src/conference_overview/adapters/icml.py tests/test_icml_adapter.py
```

Expected: all adapter tests pass and Ruff is clean.

- [ ] **Step 9: Commit Task 2**

```bash
git add src/conference_overview/adapters/icml.py tests/fixtures/icml tests/test_icml_adapter.py
git commit -m "feat: parse official ICML main papers"
```

---

### Task 3: Add venue dispatch, immutable collection, validation, and CLI support

**Files:**
- Create: `src/conference_overview/conference_pipeline.py`
- Modify: `src/conference_overview/cli.py`
- Create: `tests/test_conference_pipeline.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `ScopePaths`, ACL functions from `pipeline.py`, and ICML adapter functions from Task 2.
- Produces: `collect_scope()`, `validate_scope()`, `rebuild_scope_from_snapshots()`, and the existing CLI commands working for both ACL and ICML.

- [ ] **Step 1: Write RED dispatcher tests**

Create `tests/test_conference_pipeline.py`:

```python
def test_collect_scope_preserves_acl_dispatch(tmp_path: Path, monkeypatch) -> None:
    expected = object()
    monkeypatch.setattr(conference_pipeline, "collect_acl_scope", lambda *_: expected)
    assert collect_scope(normalize_request("ACL", 2026, "long"), tmp_path) is expected


def test_collect_icml_persists_sources_and_reconciled_records(
    tmp_path: Path, icml_client: httpx.Client
) -> None:
    request = normalize_request("ICML", 2026, "main")
    result = collect_scope(request, tmp_path, client=icml_client)
    manifest = json.loads(result.manifest_path.read_text())

    assert manifest["schema_version"] == "conference-collection-manifest-v1"
    assert manifest["scope"] == {"venue": "ICML", "year": 2026, "track": "main"}
    assert manifest["publication_status"] == "preliminary_official_program"
    assert manifest["counts"] == {
        "discovered": 5,
        "duplicate_candidates": 0,
        "excluded": 2,
        "included": 3,
        "unresolved": 0,
        "presentation_rows": 4,
    }
    assert all(Path(item["snapshot_path"]).is_relative_to("data/snapshots/icml/2026-main") for item in manifest["sources"])
```

Add mutation tests that alter one snapshot byte, remove one page, change the scope, duplicate a paper ID, and change the manifest count. Each must make `rebuild_scope_from_snapshots()` or `validate_scope()` fail before writing a new validation result.

- [ ] **Step 2: Run dispatcher tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_conference_pipeline.py -q
```

Expected: import failure because `conference_pipeline.py` does not exist.

- [ ] **Step 3: Implement the venue-neutral dispatcher**

Create `src/conference_overview/conference_pipeline.py`:

```python
def collect_scope(
    request: VenueRequest,
    root: Path,
    *,
    client: httpx.Client | None = None,
) -> CollectionResult:
    if request.adapter == "icml_virtual":
        return collect_icml_scope(request, root, client=client)
    if (request.venue, request.year, request.track) == ("ACL", 2026, "long"):
        return collect_acl_scope(request, root, client=client)
    raise UnsupportedPipelineRoute(
        f"unsupported pipeline route: {request.venue}/{request.year}/{request.track or '-'}"
    )


def validate_scope(request: VenueRequest, root: Path) -> ValidationReport:
    if request.adapter == "icml_virtual":
        return validate_icml_scope(request, root)
    return validate_acl_scope(request, root)
```

Implement ICML persistence using `ScopePaths.for_request()`, `store_snapshot()`, atomic writes, canonical sorted JSONL, `validate_records()`, and a `conference-collection-manifest-v1` manifest. Persist known non-main records as excluded and malformed/unknown records as unresolved so all source rows remain countable.

`rebuild_scope_from_snapshots()` must load every source listed in the manifest, check regular-file status, byte size, SHA-256, source URL, kind, page order, and exact source set, then call the same pure normalization function used by live collection.

- [ ] **Step 4: Write RED CLI tests for ICML**

Add to `tests/test_cli.py`:

```python
def test_icml_collect_routes_to_generic_orchestration(tmp_path: Path, monkeypatch) -> None:
    def fake_collect(request, root):
        assert (request.venue, request.year, request.track) == ("ICML", 2026, "main")
        return SimpleNamespace(
            manifest_path=tmp_path / "data/manifests/icml/2026-main.json",
            normalized_path=tmp_path / "data/normalized/icml/2026-main.jsonl",
            validation=SimpleNamespace(
                discovered_count=5, excluded_count=2, included_count=3
            ),
        )

    monkeypatch.setattr(cli_module, "collect_scope", fake_collect)
    result = runner.invoke(app, [
        "collect", "--venues", "ICML", "--years", "2026",
        "--tracks", "main", "--root", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert payload(result)["included_count"] == 3
```

- [ ] **Step 5: Run CLI test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_icml_collect_routes_to_generic_orchestration -q
```

Expected: failure because the CLI does not import or call `collect_scope`.

- [ ] **Step 6: Route CLI collection and validation through the dispatcher**

Replace direct calls to `collect_acl_scope()` and `validate_acl_scope()` in the corresponding commands with `collect_scope()` and `validate_scope()`. Preserve the JSON response keys and exit codes. Update help text from “ACL source snapshots” to “official conference source snapshots.” Keep classification, awards, and Chinese-content commands ACL-only; an ICML call to those commands must return structured `unsupported` status rather than entering ACL code.

- [ ] **Step 7: Verify Task 3 GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_conference_pipeline.py tests/test_cli.py tests/test_pipeline.py -q
.venv/bin/python -m ruff check src/conference_overview/conference_pipeline.py src/conference_overview/cli.py tests/test_conference_pipeline.py tests/test_cli.py
```

Expected: new ICML tests and all ACL pipeline regressions pass.

- [ ] **Step 8: Commit Task 3**

```bash
git add src/conference_overview/conference_pipeline.py src/conference_overview/cli.py tests/test_conference_pipeline.py tests/test_cli.py
git commit -m "feat: orchestrate preliminary conference imports"
```

---

### Task 4: Publish a typed papers-only preliminary release

**Files:**
- Modify: `src/conference_overview/models.py`
- Modify: `src/conference_overview/reports.py`
- Modify: `src/conference_overview/conference_pipeline.py`
- Modify: `src/conference_overview/cli.py`
- Modify: `tests/test_reports.py`
- Modify: `tests/test_conference_pipeline.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: validated ICML normalized records and the existing exact-six `write_release()` function.
- Produces: `PublicationContext`, `AnalysisAvailability`, `build_preliminary_release()`, and `analyze --write-release` for ICML.

- [ ] **Step 1: Write RED preliminary release contract tests**

Add to `tests/test_reports.py`:

```python
def preliminary_context() -> PublicationContext:
    return PublicationContext(
        status="preliminary_official_program",
        final_source_status="not_published",
        final_source_url="https://proceedings.mlr.press/v306/",
        notice="来自 ICML 官方会议程序，等待 PMLR 最终对照。",
        analysis_availability=AnalysisAvailability(
            papers=True,
            distribution=False,
            trends=False,
            advances=False,
            awards=False,
        ),
    )


def test_preliminary_release_allows_papers_without_classification(tmp_path: Path) -> None:
    bundle = ReleaseBundle(
        records=icml_records(),
        validation=validation_for(icml_records()),
        taxonomy_version="not-classified",
        generated_at=datetime(2026, 8, 26, tzinfo=UTC),
        sources=icml_sources(),
        publication_context=preliminary_context(),
    )
    write_release(bundle, tmp_path)
    overview = json.loads((resolve_current_release(tmp_path) / "overview.json").read_text())
    assert overview["publication_context"]["status"] == "preliminary_official_program"
    assert overview["assignments"] == []


@pytest.mark.parametrize("forged_field", ["distribution", "trends", "advances", "awards"])
def test_preliminary_release_rejects_unavailable_analysis_payloads(
    forged_field: str, tmp_path: Path
) -> None:
    bundle = preliminary_bundle_with_declared_feature(forged_field)
    with pytest.raises(PublicationBlocked, match="preliminary release"):
        write_release(bundle, tmp_path)
```

Also assert that a normal ACL `ReleaseBundle` without `publication_context` renders byte-identical artifacts to a stored pre-change fixture.

- [ ] **Step 2: Run release tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_reports.py -q
```

Expected: `PublicationContext` and `AnalysisAvailability` do not exist, or classification parity blocks the papers-only release.

- [ ] **Step 3: Implement conditional publication validation**

Add typed models:

```python
class AnalysisAvailability(BaseModel):
    papers: bool
    distribution: bool
    trends: bool
    advances: bool
    awards: bool


class PublicationContext(BaseModel):
    status: Literal["preliminary_official_program"]
    final_source_status: Literal["not_published"]
    final_source_url: HttpUrl
    notice: str
    analysis_availability: AnalysisAvailability
```

Add `publication_context: PublicationContext | None = None` to `ReleaseBundle`. In `_validate_bundle()`:

- preserve all existing behavior when context is `None`;
- for preliminary context require `taxonomy_version == "not-classified"`;
- require no assignments, audits, low-confidence registries, metrics, theme disclosures, advances, claims, awards, deep reads, or classification lineage;
- require `papers=True` and every other availability flag `False`;
- continue enforcing record/source identity, validation counts, source hashes, award host policy, exact-six generation, and timezone-aware build time.

Serialize `publication_context` only when present, so the current ACL overview bytes do not change.

- [ ] **Step 4: Write RED preliminary analysis orchestration tests**

Add to `tests/test_conference_pipeline.py`:

```python
def test_build_preliminary_release_selects_exact_six_generation(tmp_path: Path) -> None:
    collect_icml_fixture_scope(tmp_path)
    summary = build_preliminary_release(
        normalize_request("ICML", 2026, "main"), tmp_path
    )
    generation = resolve_current_release(tmp_path / "data/releases/ICML/2026")
    assert sorted(path.name for path in generation.iterdir()) == [
        "overview.json", "overview.md", "papers.csv", "papers.json",
        "provenance.json", "validation.json",
    ]
    assert summary["publication_status"] == "preliminary_official_program"
```

- [ ] **Step 5: Run orchestration test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_conference_pipeline.py::test_build_preliminary_release_selects_exact_six_generation -q
```

Expected: failure because `build_preliminary_release()` does not exist.

- [ ] **Step 6: Implement preliminary release creation and CLI routing**

`build_preliminary_release(request, root)` must:

1. call `validate_scope()` and `assert_publishable()` for paper/source consistency;
2. load only hash-checked normalized records and sources;
3. construct the exact `PublicationContext` shown above;
4. write a Chinese `notes/icml-2026-main-overview.md` containing scope, included/excluded/unresolved counts, missing abstracts/PDFs, source URLs, hashes, and the PMLR status;
5. call `write_release()` with no classification or analysis payloads;
6. return paths, counts, publication status, and generation hash.

Route `conference-trends analyze --venues ICML --years 2026 --tracks main --write-release` to this function. Without `--write-release`, return the same summary without selecting a new generation.

- [ ] **Step 7: Verify Task 4 GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_reports.py tests/test_conference_pipeline.py tests/test_cli.py -q
.venv/bin/python -m ruff check src/conference_overview/models.py src/conference_overview/reports.py src/conference_overview/conference_pipeline.py src/conference_overview/cli.py
```

Expected: papers-only preliminary release passes, forged analysis payloads fail, and ACL release tests remain green.

- [ ] **Step 8: Commit Task 4**

```bash
git add src/conference_overview/models.py src/conference_overview/reports.py src/conference_overview/conference_pipeline.py src/conference_overview/cli.py tests/test_reports.py tests/test_conference_pipeline.py tests/test_cli.py
git commit -m "feat: publish papers-only preliminary releases"
```

---

### Task 5: Make the site load multiple releases and enforce the preliminary contract

**Files:**
- Modify: `site/src/lib/schema.ts`
- Modify: `site/src/lib/data.ts`
- Create: `site/tests/fixtures/icml-preliminary-release/`
- Modify: `site/tests/data.test.ts`
- Modify: `site/tests/routes.test.ts`

**Interfaces:**
- Consumes: the Python `publication_context` JSON and existing exact-six release pointer.
- Produces: `loadOverview()` support for `main`, `loadPublishedOverviews()`, and a typed preliminary release available to pages.

- [ ] **Step 1: Generate a Python-owned ICML fixture**

Extend the Python fixture helper used by site tests to call `write_release()` with three ICML fixture records and the Task 4 publication context. Check in only the exact-six generation plus `current.json` under `site/tests/fixtures/icml-preliminary-release/ICML/2026/`; do not hand-author the JSON.

- [ ] **Step 2: Write RED Zod contract tests**

Add to `site/tests/data.test.ts`:

```typescript
it("loads a papers-only ICML preliminary release", async () => {
  const release = await loadOverview("ICML", 2026, icmlFixtureRoot, "main");
  expect(release?.overview.publication_context).toEqual({
    status: "preliminary_official_program",
    final_source_status: "not_published",
    final_source_url: "https://proceedings.mlr.press/v306/",
    notice: "来自 ICML 官方会议程序，等待 PMLR 最终对照。",
    analysis_availability: {
      papers: true,
      distribution: false,
      trends: false,
      advances: false,
      awards: false,
    },
  });
  expect(release?.overview.assignments).toEqual([]);
});

it.each(["assignments", "audits", "metrics", "advances", "awards"])(
  "rejects preliminary releases carrying forbidden %s content",
  async (field) => {
    const root = await mutateIcmlFixtureAndRehash((overview) => {
      injectForbiddenPreliminaryPayload(overview, field);
    });
    await expect(loadOverview("ICML", 2026, root, "main")).rejects.toThrow(
      /preliminary release/,
    );
  },
);
```

- [ ] **Step 3: Run site data tests and verify RED**

Run:

```bash
cd site
npm test -- tests/data.test.ts
```

Expected: the Python-valid preliminary fixture is rejected because Zod requires one assignment per paper and does not know `publication_context`.

- [ ] **Step 4: Mirror the Python conditional schema exactly**

Add a strict Zod schema for `publication_context`. Apply the same conditional rules in both `overviewArtifactSchema.superRefine()` and `fullReleaseSchema.superRefine()` so the overview-level parser cannot reject a Python-valid preliminary release or accept a forged one:

- keep exact assignment/paper parity when the context is absent;
- when status is `preliminary_official_program`, require `taxonomy_version === "not-classified"`, empty classification/analysis/award fields, and the exact availability booleans;
- require `final_source_url` to use HTTPS and `final_source_status` to equal `not_published`;
- retain paper/source/scope parity, exact-six hashes, award-host policy parity, and validation count checks.

Factor the preliminary checks into one pure helper consumed by both refinements. Add a regression that parses `overviewArtifactSchema` directly, proving that a valid preliminary overview passes and an overview with one forged assignment fails before `fullReleaseSchema` is involved.

Do not use `.passthrough()` for the new object. Reject unknown or nullable fields.

- [ ] **Step 5: Write RED multi-release discovery tests**

Add:

```typescript
it("discovers selected ACL and ICML releases in stable order", async () => {
  const releases = await loadPublishedOverviews(combinedFixtureRoot, [
    { venue: "ACL", year: 2026, track: "long" },
    { venue: "ICML", year: 2026, track: "main" },
  ]);
  expect(releases.map((release) => release.scope)).toEqual([
    { venue: "ACL", year: 2026, track: "long" },
    { venue: "ICML", year: 2026, track: "main" },
  ]);
});
```

- [ ] **Step 6: Run discovery test and verify RED**

Run:

```bash
npm test -- tests/data.test.ts
```

Expected: failure because `loadPublishedOverviews()` does not exist.

- [ ] **Step 7: Implement explicit multi-release loading**

Add:

```typescript
export interface ReleaseSelector {
  venue: string;
  year: number;
  track: string;
}

export async function loadPublishedOverviews(
  releaseRoot = process.env.CONFERENCE_RELEASE_ROOT ?? defaultReleaseRoot,
  selectors: ReleaseSelector[] = [
    { venue: "ACL", year: 2026, track: "long" },
    { venue: "ICML", year: 2026, track: "main" },
  ],
): Promise<LoadedOverview[]> {
  const loaded = await Promise.all(
    selectors.map(({ venue, year, track }) =>
      loadOverview(venue, year, releaseRoot, track)
    ),
  );
  return loaded.filter((item): item is LoadedOverview => item != null);
}
```

Use an explicit selector list rather than scanning arbitrary directories. Keep all existing safe-directory, no-symlink, containment, exact artifact set, SHA-256, scope, and host-policy checks.

- [ ] **Step 8: Verify Task 5 GREEN**

Run:

```bash
npm test -- tests/data.test.ts tests/routes.test.ts
npm run build
```

Expected: Vitest passes and Astro produces the fixture-backed pages without diagnostics.

- [ ] **Step 9: Commit Task 5**

```bash
git add site/src/lib/schema.ts site/src/lib/data.ts site/tests/fixtures/icml-preliminary-release site/tests/data.test.ts site/tests/routes.test.ts
git commit -m "feat: load preliminary multi-conference releases"
```

---

### Task 6: Build conference, paper-index, and English paper-detail views

**Files:**
- Modify: `site/src/lib/views.ts`
- Modify: `site/src/lib/evidence.ts`
- Modify: `site/src/lib/paths.ts`
- Modify: `site/src/pages/index.astro`
- Modify: `site/src/pages/conferences/[venue]/[year].astro`
- Modify: `site/src/pages/papers/index.astro`
- Create: `site/src/pages/papers/[paperId].astro`
- Modify: `site/src/styles/global.css`
- Modify: `site/tests/evidence.test.ts`
- Modify: `site/tests/routes.test.ts`
- Modify: `site/tests/styles.test.ts`
- Modify: `site/tests/visual.spec.ts`

**Interfaces:**
- Consumes: `LoadedOverview[]` and typed `publication_context` from Task 5.
- Produces: `ConferenceView` with `mode: "distribution" | "papers-only"`, `PaperIndexRow` with venue/year/detail route, and static ICML detail routes.

- [ ] **Step 1: Write RED view-model and route tests**

Add to `site/tests/routes.test.ts` and `site/tests/evidence.test.ts`:

```typescript
it("builds a papers-only ICML conference view", async () => {
  const release = await loadOverview("ICML", 2026, icmlFixtureRoot, "main");
  const view = buildConferenceView(release!);
  expect(view.mode).toBe("papers-only");
  expect(view.pageHeading).toBe("ICML 2026 主会论文");
  expect(view.scopeLabel).toBe("ICML 2026 · Main Conference");
  expect(view.publicationNotice).toBe("来自 ICML 官方会议程序，等待 PMLR 最终对照。");
  expect(view.topics).toEqual([]);
});

it("aggregates ACL and ICML paper rows with internal detail routes", () => {
  const rows = filterPapers([aclRelease, icmlRelease], {
    query: "", theme: null, venue: null,
  });
  const icml = rows.find((paper) => paper.venue === "ICML")!;
  expect(icml.detailUrl).toMatch(/^\/ai-conference-overview\/papers\/paper-[0-9a-f]{64}\/$/);
  expect(icml.theme).toBeNull();
});

it("creates stable routes from the full paper identity", () => {
  const first = icmlRelease.papers[0];
  expect(paperRouteKey(first.paper_id)).toBe(
    `paper-${createHash("sha256").update(first.paper_id).digest("hex")}`,
  );
});
```

- [ ] **Step 2: Run view-model tests and verify RED**

Run:

```bash
cd site
npm test -- tests/routes.test.ts tests/evidence.test.ts
```

Expected: `ConferenceView` has no mode/publication notice, `filterPapers()` accepts one release only, and paper route helpers do not exist.

- [ ] **Step 3: Implement typed papers-only views**

Update `ConferenceView` so `mode` determines valid fields:

```typescript
type ConferenceView =
  | DistributionConferenceView
  | PapersOnlyConferenceView;
```

Both variants expose venue, year, track, counts, source metadata, generation, and abstract coverage. The distribution variant retains the current ACL topic fields. The papers-only variant exposes `publicationNotice`, `finalSourceUrl`, inclusion labels, exclusion labels, and an empty topic collection.

Change `filterPapers()` to accept `LoadedOverview[]` plus `{ query, theme, venue }`. A paper without classification has `theme: null`. Derive `routeKey` with full SHA-256 of `paper_id`; never truncate the hash and never recompute from title or authors.

- [ ] **Step 4: Write RED rendered-page tests**

Add assertions that a fixture-backed Astro build:

- emits `/conferences/acl/2026/` and `/conferences/icml/2026/`;
- emits exactly one `/papers/paper-<sha>/` route per ICML paper;
- displays the preliminary notice and inclusion/exclusion lists;
- does not render topic charts, advances, awards, or Chinese-summary placeholders on ICML pages;
- links ACL paper rows as before and ICML titles to internal detail pages;
- exposes a conference selector and title/author search on `/papers/`.

Use DOM parsing or a release-backed child Astro build, not string snapshots of component source.

- [ ] **Step 5: Run rendered-page tests and verify RED**

Run:

```bash
npm test -- tests/routes.test.ts tests/evidence.test.ts
```

Expected: build or DOM assertions fail because pages still load ACL directly and no paper detail route exists.

- [ ] **Step 6: Implement the approved responsive pages**

Update the pages to call `loadPublishedOverviews()` once per build boundary:

- Home renders one conference card per release; ICML card says “预发布”.
- Conference `getStaticPaths()` builds routes from all releases and passes a discriminated view.
- ACL retains its current distribution markup.
- ICML renders compact identity, status, counts, included/excluded scope, and the paper-directory link.
- Paper index renders a venue filter, nullable theme labels, and internal ICML detail links.
- `papers/[paperId].astro` generates only papers-only release routes and shows title, authors, official abstract or the exact missing message, source notice, ICML/OpenReview/PDF links, and a back link.

Use the approved visual hierarchy: no full-screen hero, no decorative numbering that implies a process, and one orange status accent. Reuse existing colors and fonts.

- [ ] **Step 7: Add 390 px CSS and RED style assertions**

Add source-level checks to `site/tests/styles.test.ts` for:

- the ICML conference layout collapsing to one column under 760 px;
- paper controls collapsing to one column;
- detail abstract `font-size` resolving to at least `1rem`;
- `overflow-wrap: anywhere` on long IDs/URLs;
- no fixed widths wider than the viewport.

Run:

```bash
npm test -- tests/styles.test.ts
```

Expected: new ICML selectors or mobile declarations are absent.

- [ ] **Step 8: Add browser acceptance tests**

Extend `site/tests/visual.spec.ts`:

```typescript
test("ICML preliminary conference and paper detail are readable", async ({ page }, testInfo) => {
  if (testInfo.project.name === "mobile-chromium") {
    await page.setViewportSize({ width: 390, height: 844 });
  }
  await page.goto("/ai-conference-overview/conferences/icml/2026/");
  await expect(page.getByRole("heading", { name: "ICML 2026 主会论文" })).toBeVisible();
  await expect(page.getByText("来自 ICML 官方会议程序，等待 PMLR 最终对照。")).toBeVisible();
  await expect(page.getByRole("heading", { name: "主题分布" })).toHaveCount(0);

  await page.goto("/ai-conference-overview/papers/");
  await page.getByLabel("会议").selectOption("ICML");
  await page.locator("[data-paper-row]:not([hidden]) a[data-paper-detail]").first().click();
  const abstractSize = await page.locator("[data-english-abstract]").evaluate(
    (node) => Number.parseFloat(getComputedStyle(node).fontSize),
  );
  expect(abstractSize).toBeGreaterThanOrEqual(16);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
});
```

Also extend the internal-link test to cover the ICML conference page and every generated ICML detail route.

- [ ] **Step 9: Verify Task 6 GREEN**

Run:

```bash
npm test
npm run build
npm run test:e2e
```

Expected: Vitest, Astro check/build, desktop Chromium, and 390 px mobile Chromium pass with no console errors or internal 404s.

- [ ] **Step 10: Commit Task 6**

```bash
git add site/src/lib/views.ts site/src/lib/evidence.ts site/src/lib/paths.ts site/src/pages/index.astro site/src/pages/conferences/'[venue]'/'[year]'.astro site/src/pages/papers/index.astro site/src/pages/papers/'[paperId]'.astro site/src/styles/global.css site/tests/evidence.test.ts site/tests/routes.test.ts site/tests/styles.test.ts site/tests/visual.spec.ts
git commit -m "feat: present ICML preliminary paper pages"
```

---

### Task 7: Add a safe PMLR availability check and future reconciliation contract

**Files:**
- Create: `src/conference_overview/adapters/pmlr.py`
- Modify: `src/conference_overview/conference_pipeline.py`
- Modify: `src/conference_overview/cli.py`
- Create: `tests/fixtures/pmlr/icml-2026-small.html`
- Create: `tests/test_pmlr_adapter.py`
- Modify: `tests/test_conference_pipeline.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: preliminary ICML records and configured `final_source_url`.
- Produces: `FinalSourceStatus`, `PmlrDiffReport`, `check_final_source()`, `reconcile_pmlr_records()`, and `conference-trends reconcile-final`.

- [ ] **Step 1: Write RED PMLR status and diff tests**

Create `tests/test_pmlr_adapter.py`:

```python
def test_pmlr_404_is_not_published_without_writing() -> None:
    status = check_final_source(icml_request(), client_responding(404))
    assert status == FinalSourceStatus.NOT_PUBLISHED


def test_pmlr_diff_requires_exact_one_to_one_identity() -> None:
    report = reconcile_pmlr_records(preliminary_records(), pmlr_records())
    assert report.preliminary_count == 3
    assert report.final_count == 3
    assert report.matched_count == 3
    assert report.only_preliminary_ids == ()
    assert report.only_final_ids == ()
    assert report.field_differences[0].fields == ("abstract", "doi", "pdf_url")


def test_pmlr_diff_rejects_ambiguous_title_fallback() -> None:
    with pytest.raises(PmlrReconciliationError, match="ambiguous"):
        reconcile_pmlr_records(preliminary_records(), duplicated_title_records())
```

- [ ] **Step 2: Run PMLR tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_pmlr_adapter.py -q
```

Expected: adapter module and reconciliation types do not exist.

- [ ] **Step 3: Implement read-only status and pure reconciliation**

`check_final_source()` performs one bounded official request. HTTP 404 returns `NOT_PUBLISHED`; 200 is accepted only if the page identifies PMLR Volume 306 and the 43rd ICML; transport errors remain errors rather than being converted to 404.

`parse_pmlr_volume()` extracts stable PMLR IDs, title, authors, abstract, DOI, landing URL, and PDF URL from a complete volume fixture. `reconcile_pmlr_records()` matches OpenReview links/IDs first, DOI second, and normalized title only as a review candidate. Fuzzy or duplicate title matches raise an error.

Serialize the diff report with counts, only-on-one-side IDs, field-level differences, unresolved pairs, source hash, and generated time. The function has no filesystem side effects.

- [ ] **Step 4: Write RED CLI no-write tests**

Add a test that `reconcile-final` on a 404 returns:

```json
{"command":"reconcile-final","status":"not_published","venue":"ICML","year":2026,"track":"main"}
```

and leaves the ICML `current.json`, generations directory, and analysis directory byte-identical.

- [ ] **Step 5: Run CLI test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli.py -k reconcile_final -q
```

Expected: Typer reports that `reconcile-final` is not a known command.

- [ ] **Step 6: Implement `reconcile-final` without automatic publication**

When PMLR returns 404, print structured `not_published` and write nothing. When available, save the verified PMLR snapshot and diff report under `data/analysis/icml/2026-main/pmlr-reconciliation/<source-sha256>/`; do not select a new release. A final PMLR-backed release requires a separate explicit command after `matched_count == final_count`, both one-sided lists are empty, and unresolved count is zero.

- [ ] **Step 7: Verify Task 7 GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_pmlr_adapter.py tests/test_conference_pipeline.py tests/test_cli.py -q
.venv/bin/python -m ruff check src/conference_overview/adapters/pmlr.py src/conference_overview/conference_pipeline.py src/conference_overview/cli.py tests/test_pmlr_adapter.py
```

Expected: 404 is safe and no-write; fixture reconciliation is deterministic and ambiguity fails closed.

- [ ] **Step 8: Commit Task 7**

```bash
git add src/conference_overview/adapters/pmlr.py src/conference_overview/conference_pipeline.py src/conference_overview/cli.py tests/fixtures/pmlr tests/test_pmlr_adapter.py tests/test_conference_pipeline.py tests/test_cli.py
git commit -m "feat: prepare ICML PMLR reconciliation"
```

---

### Task 8: Run the official ICML import, generate the release, and complete acceptance

**Files:**
- Create: `scripts/verify_icml_live_release.py`
- Modify: `README.md`
- Create: `data/snapshots/icml/2026-main/**`
- Create: `data/manifests/icml/2026-main.json`
- Create: `data/normalized/icml/2026-main.jsonl`
- Create: `data/analysis/icml/2026-main/**`
- Create: `data/releases/ICML/2026/**`
- Create: `notes/icml-2026-main-overview.md`

**Interfaces:**
- Consumes: the implemented CLI, official ICML/OpenReview endpoints, and the existing ACL release.
- Produces: one selected immutable ICML preliminary generation, live site routes, count/hash inventory, and an acceptance report.

- [ ] **Step 1: Write the live-release verifier before collecting data**

Create `scripts/verify_icml_live_release.py` that exits non-zero unless all conditions hold:

```python
assert pointer_artifact_names == {
    "papers.json", "papers.csv", "overview.json", "overview.md",
    "validation.json", "provenance.json",
}
assert overview["publication_context"]["status"] == "preliminary_official_program"
assert overview["publication_context"]["analysis_availability"] == {
    "papers": True,
    "distribution": False,
    "trends": False,
    "advances": False,
    "awards": False,
}
assert len(papers) == validation["included_count"] == overview["paper_count"]
assert len({paper["paper_id"] for paper in papers}) == len(papers)
assert {paper["venue"] for paper in papers} == {"ICML"}
assert {paper["year"] for paper in papers} == {2026}
assert {paper["track"] for paper in papers} == {"main"}
assert all(
    paper["native_metadata"]["openreview_venueid"]
    == "ICML.cc/2026/Conference"
    for paper in papers
)
```

The script must independently recompute artifact hashes, snapshot hashes, manifest counts, missing abstract/PDF counts, and all paper route keys. It must also confirm that the ACL current pointer and six artifact hashes equal a pre-run inventory captured in `/tmp/icml-import-acl-baseline.json`. The dedicated `--write-acl-baseline PATH` mode writes only that ACL inventory and exits zero without requiring an ICML release; normal verification remains read-only and requires both the baseline and ICML release.

- [ ] **Step 2: Run the verifier and verify RED**

Run:

```bash
.venv/bin/python scripts/verify_icml_live_release.py --root .
```

Expected: failure because no selected ICML release exists.

- [ ] **Step 3: Capture the ACL baseline and collect official ICML data**

Run:

```bash
.venv/bin/python scripts/verify_icml_live_release.py --write-acl-baseline /tmp/icml-import-acl-baseline.json --root .
.venv/bin/conference-trends collect --venues ICML --years 2026 --tracks main
.venv/bin/conference-trends validate --venues ICML --years 2026 --tracks main
```

If official pagination, OpenReview availability, or count reconciliation fails, stop here. Record the exact official error and leave `data/releases/ICML/2026/current.json` absent. Do not use a mirror, cached third-party list, or partial feed.

- [ ] **Step 4: Inspect the real reconciliation before publishing**

Read the generated manifest and normalized records. Record:

- total OpenReview accepted notes;
- ICML virtual presentation rows;
- unique Main Conference papers;
- Position and Journal-to-Conference exclusions;
- unresolved records;
- duplicate candidates;
- missing abstracts and PDFs;
- every source URL, byte size, retrieval time, and SHA-256.

Require unresolved and duplicate-candidate counts to equal zero. Manually inspect at least one regular paper, one spotlight, one oral-enriched paper, one proceedings-only paper, one excluded Position Paper, and every unusual decision/source group reported by the manifest.

- [ ] **Step 5: Generate the preliminary release**

Run:

```bash
.venv/bin/conference-trends analyze --venues ICML --years 2026 --tracks main --write-release
.venv/bin/conference-trends reconcile-final --venues ICML --years 2026 --tracks main
```

Expected: exact-six ICML generation is selected; `reconcile-final` reports `not_published` while PMLR Volume 306 remains unavailable and does not change the selected generation.

- [ ] **Step 6: Update reader documentation**

Update `README.md` so the current scope table says:

```markdown
| ICML | 2026 Main Conference | 已导入 ICML 官网预发布论文数据，等待 PMLR Volume 306 最终对照；暂不提供中文摘要和主题分析 |
```

Add the exact collect/validate/analyze/reconcile commands and explain that presentation type is not a track.

- [ ] **Step 7: Run full Python and site verification**

Run from the repository root:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python scripts/generate_award_host_policy.py --check
.venv/bin/python scripts/verify_icml_live_release.py --acl-baseline /tmp/icml-import-acl-baseline.json --root .
cd site
npm test
npm run build
npm run test:e2e
```

Then run the empty-data build:

```bash
mkdir -p /tmp/ai-conference-overview-empty-releases
cd site
CONFERENCE_RELEASE_ROOT=/tmp/ai-conference-overview-empty-releases npm run build
```

Expected: Python and TypeScript tests pass; Ruff is clean; the host policy is current; the live verifier passes; the production build includes ACL, ICML, 30 award pages, and one ICML detail page per included paper; the empty build emits no conference or paper-detail routes.

- [ ] **Step 8: Inspect rendered desktop and mobile pages**

Start the preview and inspect:

```bash
cd site
npm run preview -- --host 127.0.0.1 --port 4321
```

Check `/ai-conference-overview/conferences/icml/2026/`, `/ai-conference-overview/papers/`, one long-title ICML detail, and one missing-abstract detail at desktop width and 390 × 844. Confirm the preliminary notice is visible, Chinese-summary placeholders are absent, paper links resolve, and no page has horizontal overflow.

- [ ] **Step 9: Commit code documentation separately from generated data**

First commit verifier and README:

```bash
git add scripts/verify_icml_live_release.py README.md
git commit -m "docs: document ICML preliminary release"
```

Then inspect and commit only ICML data paths:

```bash
git status --short
git diff --stat -- data/snapshots/icml data/manifests/icml data/normalized/icml data/analysis/icml data/releases/ICML notes/icml-2026-main-overview.md
git add data/snapshots/icml data/manifests/icml data/normalized/icml data/analysis/icml data/releases/ICML notes/icml-2026-main-overview.md
git diff --cached --check
git commit -m "data: add ICML 2026 main preliminary release"
```

- [ ] **Step 10: Run fresh post-commit acceptance**

Repeat the full commands from Step 7, then run:

```bash
git status --short
git log -8 --oneline
```

Expected: all checks pass, ACL baseline remains identical, ICML release hashes match its pointer, and the tracked worktree is clean.

---

## Plan Self-Review Checklist

- [ ] Every requirement in the approved Spec maps to Tasks 1–8.
- [ ] Track separation is based on exact official venue identity, not title or session text.
- [ ] The preliminary release cannot carry classification, trends, advances, awards, or Chinese summaries.
- [ ] OpenReview/ICML outages stop publication without a third-party fallback.
- [ ] PMLR 404 is a no-write state; an available volume produces a difference report before any final release.
- [ ] ACL byte/hash preservation is checked before and after the live import.
- [ ] Python and Zod implement the same conditional preliminary-release rules.
- [ ] Desktop, 390 px mobile, empty-data, GitHub Pages base-path, console-error, and internal-link checks are included.
- [ ] Generated official data is committed separately from code and documentation.
