# ACL 2026 Findings Papers-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish all ACL 2026 Findings papers as an independent, searchable, immutable release while preserving the existing ACL 2026 Long release and URL.

**Architecture:** Make Track identity explicit at the registry boundary, derive release locations from one Python resolver, and generate the frontend selector from the same venue registry. Route every ACL Anthology Track through a request-driven adapter. The first Findings release contains papers and source metadata only; Astro exposes it through a Track-specific conference route and Track-aware paper filters without creating analysis or award placeholders.

**Tech Stack:** Python 3.11, Typer, Pydantic 2, httpx, PyYAML, pytest, Ruff, Astro 5, TypeScript, Zod, Vitest, Playwright, GitHub Actions, GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-08-28-acl-2026-findings-onboarding-design.md`

## Global Constraints

- Official scope is exactly ACL Anthology `2026.findings-acl`; the expected starting snapshot is 2,163 papers plus one excluded proceedings record.
- Recompute counts from downloaded bytes. If the official volume changes, record the diff instead of weakening the expected-count check silently.
- ACL 2026 Long remains the default Track at `data/releases/ACL/2026/`; its pointer, six artifact hashes, 30 award routes, and `/conferences/acl/2026/` URL must remain unchanged.
- ACL 2026 Findings is stored below `data/releases/ACL/2026/tracks/findings/` and served at `/conferences/acl/2026/findings/`.
- A selected generation contains exactly `papers.json`, `papers.csv`, `overview.json`, `overview.md`, `validation.json`, and `provenance.json`.
- Stage 1 sets only `analysis_availability.papers=true`; distribution, trends, advances, and awards are false and absent from the UI.
- Never attach ACL Long awards to Findings or use Long and Findings paper counts as a trend.
- Public prose is Chinese; official titles, identifiers, Track names, and established technical terms may remain English.
- Preserve unrelated worktree changes. Stage explicit paths only; never use `git add .` or `git add -A`.

---

### Task 1: Make default and non-default Track release paths authoritative

**Files:**
- Modify: `src/conference_overview/models.py`
- Modify: `src/conference_overview/registry.py`
- Modify: `src/conference_overview/scope.py`
- Modify: `config/venues.yaml`
- Modify: `src/conference_overview/venues.yaml`
- Test: `tests/test_registry.py`
- Test: `tests/test_scope.py`

**Interfaces:**
- Consumes: `normalize_request(venue, year, track) -> VenueRequest`.
- Produces: `VenueRequest.default_track`, `VenueRequest.is_default_track`, and `release_relative_parts(request) -> tuple[str, ...]`.
- Invariant: default Track resolves to `<VENUE>/<year>`; non-default Track resolves to `<VENUE>/<year>/tracks/<track>`.

- [ ] **Step 1: Add RED registry and path tests**

```python
def test_acl_findings_is_non_default_track() -> None:
    request = normalize_request("ACL", 2026, "findings")
    assert request.adapter == "acl_anthology"
    assert request.source_key == "2026.findings-acl"
    assert request.default_track == "long"
    assert request.is_default_track is False


def test_release_paths_keep_long_compatible_and_isolate_findings(tmp_path: Path) -> None:
    long = ScopePaths.for_request(tmp_path, normalize_request("ACL", 2026, "long"))
    findings = ScopePaths.for_request(tmp_path, normalize_request("ACL", 2026, "findings"))
    assert long.release == tmp_path / "data/releases/ACL/2026"
    assert findings.release == tmp_path / "data/releases/ACL/2026/tracks/findings"
```

- [ ] **Step 2: Run the focused RED tests**

Run: `.venv/bin/pytest tests/test_registry.py tests/test_scope.py -q`

Expected: FAIL because ACL has no configured default/Findings route and `ScopePaths.release` ignores Track.

- [ ] **Step 3: Add the registry fields and shared resolver**

```python
class VenueRequest(BaseModel):
    # existing fields remain
    default_track: str | None = None
    is_default_track: bool = True


def release_relative_parts(request: VenueRequest) -> tuple[str, ...]:
    venue = _safe_segment(request.venue)
    year = _safe_segment(str(request.year))
    track = _safe_segment(require_track(request))
    return (venue, year) if request.is_default_track else (venue, year, "tracks", track)
```

Set `is_default_track` only after `normalize_request` resolves the configured default. Add `default_track: long`, `adapter: acl_anthology`, and final-publication metadata to ACL Long; register Findings with its official `.bib` and volume URLs. Keep source and packaged venue YAML byte-equivalent.

- [ ] **Step 4: Run focused and compatibility tests**

Run: `.venv/bin/pytest tests/test_registry.py tests/test_scope.py tests/test_package.py -q`

Expected: PASS; ICML 2025/2026 paths and ACL Long path remain unchanged.

- [ ] **Step 5: Commit the path contract**

```bash
git add config/venues.yaml src/conference_overview/venues.yaml src/conference_overview/models.py src/conference_overview/registry.py src/conference_overview/scope.py tests/test_registry.py tests/test_scope.py tests/test_package.py
git commit -m "feat: add track-aware release paths"
```

### Task 2: Generate frontend release selectors from the venue registry

**Files:**
- Create: `scripts/generate_release_selectors.py`
- Create: `site/src/generated/release-selectors.json`
- Modify: `site/src/lib/data.ts`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/pages.yml`
- Test: `tests/test_registry.py`
- Test: `site/tests/data.test.ts`

**Interfaces:**
- Produces generated rows `{ venue, year, track, release_path }` sorted by venue, year, and Track.
- Consumes `release_path` as slash-separated safe relative segments under `CONFERENCE_RELEASE_ROOT`.
- Commands: `python scripts/generate_release_selectors.py` and `python scripts/generate_release_selectors.py --check`.

- [ ] **Step 1: Write RED tests for exact generated paths and traversal rejection**

```ts
expect(configuredReleaseSelectors).toContainEqual({
  venue: "ACL", year: 2026, track: "findings", release_path: "ACL/2026/tracks/findings",
});
expect(configuredReleaseSelectors).toContainEqual({
  venue: "ACL", year: 2026, track: "long", release_path: "ACL/2026",
});
```

Add a fixture selector using `../outside` and assert `loadOverview` rejects it before filesystem access.

- [ ] **Step 2: Run the RED checks**

Run: `.venv/bin/pytest tests/test_registry.py -k selector -q && cd site && npm test -- --run tests/data.test.ts`

Expected: FAIL because selectors are hardcoded and the loader derives only `<venue>/<year>`.

- [ ] **Step 3: Implement deterministic generation and safe loading**

```python
row = {
    "venue": request.venue,
    "year": request.year,
    "track": request.track,
    "release_path": "/".join(release_relative_parts(request)),
}
```

In TypeScript, parse the generated JSON with Zod, split `release_path`, reject empty, dot, absolute, backslash, or mismatched venue/year/Track segments, and join only after validating the canonical release root. Change `loadOverview` to consume one `PublishedReleaseSelector` instead of independently reconstructing a path.

- [ ] **Step 4: Add stale-generation checks to CI and Pages**

Run `python scripts/generate_release_selectors.py --check` before site tests/build in both workflows. Do not regenerate during CI; a config change without the committed generated file must fail.

- [ ] **Step 5: Verify and commit**

Run: `.venv/bin/pytest tests/test_registry.py -q && cd site && npm test -- --run tests/data.test.ts`

```bash
git add scripts/generate_release_selectors.py site/src/generated/release-selectors.json site/src/lib/data.ts tests/test_registry.py site/tests/data.test.ts .github/workflows/ci.yml .github/workflows/pages.yml
git commit -m "feat: generate release selectors from venue config"
```

### Task 3: Route arbitrary registered ACL Anthology Tracks through one adapter

**Files:**
- Modify: `src/conference_overview/adapters/acl.py`
- Modify: `src/conference_overview/pipeline.py`
- Modify: `src/conference_overview/conference_pipeline.py`
- Modify: `src/conference_overview/fetch.py`
- Create: `tests/fixtures/acl/2026-findings-sample.bib`
- Create: `tests/fixtures/acl/2026-findings-sample.html`
- Test: `tests/test_acl_adapter.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_conference_pipeline.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Consumes: a registered `VenueRequest(adapter="acl_anthology", source_key=..., bibtex_url=..., volume_url=...)`.
- Produces: `collect_acl_scope`, `validate_acl_scope`, and normalized `PaperRecord`s whose Track equals the request Track.
- Produces: `parse_acl_volume_paper_ids(html, request, source) -> set[str]` using the exact request `source_key`.

- [ ] **Step 1: Add RED adapter-routing and completeness tests**

Cover ACL Long and Findings fixtures, regex escaping, a sibling volume ID, mismatched HTML/BibTeX ID sets, a truncated final BibTeX entry, truncated HTML, and a successful response whose body length differs from `Content-Length`.

```python
def test_collect_scope_dispatches_registered_findings(monkeypatch, tmp_path: Path) -> None:
    request = normalize_request("ACL", 2026, "findings")
    seed_acl_responses(monkeypatch, request, bib="2026-findings-sample.bib", html="2026-findings-sample.html")
    summary = collect_scope(request, tmp_path)
    assert summary["included"] == 2
    assert load_records(tmp_path)[0].track == "findings"
```

- [ ] **Step 2: Run RED tests**

Run: `.venv/bin/pytest tests/test_acl_adapter.py tests/test_fetch.py tests/test_pipeline.py tests/test_conference_pipeline.py -q`

Expected: FAIL at the hardcoded `ACL/2026/long` route or `2026.acl-long` HTML pattern.

- [ ] **Step 3: Replace scope literals with request-bound validation**

```python
def _require_acl_anthology(request: VenueRequest) -> None:
    if request.adapter != "acl_anthology" or not request.source_key:
        raise UnsupportedPipelineRoute("registered ACL Anthology route required")
    if not request.bibtex_url or not request.volume_url:
        raise UnsupportedPipelineRoute("ACL Anthology source URLs are incomplete")
```

Derive the HTML paper-ID pattern with `re.escape(request.source_key)`, build manifest scope fields from the request, and dispatch `collect_scope`/`validate_scope` by adapter. Retain `fetch_bytes` Content-Length enforcement and add a post-parse check that BibTeX ends after a complete entry before any canonical output is written.

- [ ] **Step 4: Verify no partial write occurs on corruption**

Run: `.venv/bin/pytest tests/test_fetch.py tests/test_acl_adapter.py tests/test_pipeline.py tests/test_conference_pipeline.py -q`

Expected: PASS; failed downloads leave normalized data, manifest, and release pointer absent or unchanged.

- [ ] **Step 5: Commit the generalized adapter**

```bash
git add src/conference_overview/adapters/acl.py src/conference_overview/pipeline.py src/conference_overview/conference_pipeline.py src/conference_overview/fetch.py tests/fixtures/acl/2026-findings-sample.bib tests/fixtures/acl/2026-findings-sample.html tests/test_acl_adapter.py tests/test_fetch.py tests/test_pipeline.py tests/test_conference_pipeline.py
git commit -m "feat: support registered ACL Anthology tracks"
```

### Task 4: Publish a venue-neutral papers-only release

**Files:**
- Modify: `src/conference_overview/conference_pipeline.py`
- Modify: `src/conference_overview/reports.py`
- Modify: `src/conference_overview/cli.py`
- Test: `tests/test_conference_pipeline.py`
- Test: `tests/test_reports.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes validated normalized records and `ScopePaths.release`.
- Produces a `ReleaseBundle` with papers-only `AnalysisAvailability` and a Chinese scope note.
- `analyze_scope` selects classified analysis only when assignments exist; otherwise every supported final-proceedings adapter uses papers-only mode.

- [ ] **Step 1: Add RED tests for Findings papers-only behavior**

Assert exact six artifacts, a Track-local pointer, no assignments, no advances, no awards, all non-paper availability flags false, Chinese Findings wording, and unchanged Long pointer fixture.

- [ ] **Step 2: Run RED tests**

Run: `.venv/bin/pytest tests/test_conference_pipeline.py tests/test_reports.py tests/test_cli.py -k 'preliminary or papers_only or findings' -q`

Expected: FAIL because `build_preliminary_release` rejects `acl_anthology` and emits ICML-specific copy.

- [ ] **Step 3: Make the release builder scope-neutral**

```python
context = PublicationContext(
    status=request.publication_status or "final_proceedings",
    final_source_status="available",
    final_source_url=request.final_source_url or request.volume_url,
    notice=f"来自官方论文集的 {request.venue} {request.year} {track_label(request.track)} 论文清单。",
    analysis_availability=AnalysisAvailability(
        papers=True, distribution=False, trends=False, advances=False, awards=False,
    ),
)
```

Rename the internal function to `build_papers_only_release` while retaining a compatibility alias if tests or callers import `build_preliminary_release`. Write to a temporary generation, validate all six files, then atomically replace only the selected Track pointer.

- [ ] **Step 4: Verify CLI success and fail-closed behavior**

Run successful fixture collect/validate/analyze for Findings, then rerun with a corrupted normalized record and assert exit non-zero without changing either Findings or Long pointer.

- [ ] **Step 5: Commit the papers-only producer**

```bash
git add src/conference_overview/conference_pipeline.py src/conference_overview/reports.py src/conference_overview/cli.py tests/test_conference_pipeline.py tests/test_reports.py tests/test_cli.py
git commit -m "feat: publish track-scoped papers-only releases"
```

### Task 5: Add Track-aware conference routes and conference-list entries

**Files:**
- Create: `site/src/components/ConferenceOverview.astro`
- Modify: `site/src/pages/conferences/[venue]/[year].astro`
- Create: `site/src/pages/conferences/[venue]/[year]/[track].astro`
- Modify: `site/src/pages/conferences/index.astro`
- Modify: `site/src/components/ConferenceCard.astro`
- Modify: `site/src/lib/views.ts`
- Test: `site/tests/routes.test.ts`
- Test: `site/tests/data.test.ts`

**Interfaces:**
- Produces `defaultConferenceRoutes(releases)` and `nonDefaultConferenceRoutes(releases)` with explicit Track identity.
- Default URL: `/conferences/acl/2026/`; non-default URL: `/conferences/acl/2026/findings/`.
- Shared component consumes `ConferenceView`; neither route infers Track from venue/year alone.

- [ ] **Step 1: Write RED route and copy tests**

Assert two ACL 2026 cards, unique static paths, Long at the existing URL, Findings at the nested URL, `scopeLabel` containing “Findings”, and papers-only copy that does not say “Main Conference”.

- [ ] **Step 2: Run RED tests**

Run: `cd site && npm test -- --run tests/routes.test.ts tests/data.test.ts`

Expected: FAIL because `conferenceRoutes` emits duplicate venue/year params and the page contains Main-specific prose.

- [ ] **Step 3: Extract the shared page and split route generation**

```ts
export const defaultConferenceRoutes = (releases: ConferenceRelease[]) =>
  releases.filter((item) => item.selector.is_default_track);
export const nonDefaultConferenceRoutes = (releases: ConferenceRelease[]) =>
  releases.filter((item) => !item.selector.is_default_track);
```

If the selector schema stores only `release_path`, derive `is_default_track` by validated path shape and expose it on `LoadedOverview`. Add `trackLabel("long"|"findings"|"main")` for Chinese-facing labels. Move all conference markup into `ConferenceOverview.astro` and let both route files pass a fully built view.

- [ ] **Step 4: Build fixture pages and assert availability boundaries**

Run: `cd site && CONFERENCE_RELEASE_ROOT=tests/fixtures/task-findings-release npm run build`

Expected: Long and Findings pages exist; Findings HTML contains the paper count/source and contains no topic chart, advance link, trend widget, or award link.

- [ ] **Step 5: Commit the route structure**

```bash
git add site/src/components/ConferenceOverview.astro site/src/pages/conferences/\[venue\]/\[year\].astro site/src/pages/conferences/\[venue\]/\[year\]/\[track\].astro site/src/pages/conferences/index.astro site/src/components/ConferenceCard.astro site/src/lib/views.ts site/tests/routes.test.ts site/tests/data.test.ts
git commit -m "feat: add track-specific conference pages"
```

### Task 6: Add shareable Track filters to the paper index

**Files:**
- Create: `site/src/lib/paper-filter.ts`
- Modify: `site/src/lib/evidence.ts`
- Modify: `site/src/pages/papers/index.astro`
- Test: `site/tests/evidence.test.ts`
- Test: `site/tests/routes.test.ts`
- Test: `site/tests/visual.spec.ts`

**Interfaces:**
- Query parameters: `venue`, `year`, `track`, `theme`, and `q`.
- Rows expose `data-venue`, `data-year`, and `data-track`.
- Filter changes call `history.replaceState` with a stable, shareable URL.

- [ ] **Step 1: Add RED parser, filtering, and UI tests**

Test a valid `?venue=ACL&year=2026&track=findings`, invalid segments, URL round-trip, Long/Findings separation, and a paper-ID collision guard across both corpora.

- [ ] **Step 2: Run RED tests**

Run: `cd site && npm test -- --run tests/evidence.test.ts tests/routes.test.ts`

Expected: FAIL because the index has only venue/theme filters and does not preserve query state.

- [ ] **Step 3: Implement the pure filter helper and wire the form**

```ts
export interface PaperFilter {
  q: string; venue: string | null; year: number | null; track: string | null; theme: string | null;
}
```

Initialize controls from `window.location.search`, filter on all populated fields, display natural Track labels on rows, and update the URL without reloading. Conference-page “浏览论文” links must preselect the page's venue/year/Track.

- [ ] **Step 4: Verify desktop and 390px behavior**

Run: `cd site && npm test -- --run tests/evidence.test.ts tests/routes.test.ts && PLAYWRIGHT_PORT=4399 npm run test:e2e -- --project=chromium --project=mobile`

Expected: filter round-trip works, paper details open, there is no horizontal overflow, and mobile controls remain usable.

- [ ] **Step 5: Commit the paper experience**

```bash
git add site/src/lib/paper-filter.ts site/src/lib/evidence.ts site/src/pages/papers/index.astro site/src/components/ConferenceOverview.astro site/tests/evidence.test.ts site/tests/routes.test.ts site/tests/visual.spec.ts
git commit -m "feat: filter papers by conference track"
```

### Task 7: Collect the official corpus and select the immutable Findings release

**Files:**
- Create: `data/manifests/acl/2026-findings.json`
- Create: `data/normalized/acl/2026-findings.jsonl`
- Create: `data/snapshots/acl/2026-findings/`
- Create: `data/analysis/acl/2026-findings/validation.json`
- Create: `data/releases/ACL/2026/tracks/findings/current.json`
- Create: `data/releases/ACL/2026/tracks/findings/generations/<sha256>/`
- Create: `notes/acl-2026-findings-overview.md`
- Create: `scripts/verify_acl_findings_live_release.py`
- Test: `tests/test_verify_acl_findings_live_release.py`

**Interfaces:**
- Consumes only the configured official ACL Anthology URLs.
- Produces a source manifest with retrieval time, HTTP metadata, byte sizes, SHA-256 values, counts, and normalized record-set SHA-256.
- Verification script compares the selected Findings generation, scope, exact-six files, counts, and the recorded ACL Long baseline.

- [ ] **Step 1: Record the ACL Long compatibility baseline**

Capture the existing Long `current.json` bytes, pointer SHA-256, and all six referenced artifact hashes in the Task report or verification fixture. Do not modify the Long release.

- [ ] **Step 2: Run official collection and validation**

Run:

```bash
.venv/bin/conference-trends collect --venues ACL --years 2026 --tracks findings
.venv/bin/conference-trends validate --venues ACL --years 2026 --tracks findings
```

Expected: `discovered = included + excluded + unresolved`, included 2,163, excluded 1 proceedings record, unresolved 0, no duplicates, and complete BibTeX/HTML ID reconciliation. If official data differs, stop and document the source-level delta.

- [ ] **Step 3: Publish and independently verify the six artifacts**

Run:

```bash
.venv/bin/conference-trends analyze --venues ACL --years 2026 --tracks findings --write-release
.venv/bin/python scripts/verify_acl_findings_live_release.py
```

The verifier must recompute all pointer hashes, require exactly six generation files, require every paper scope to be ACL/2026/findings, require all non-paper availability flags false, and byte-compare the Long baseline.

- [ ] **Step 4: Commit source facts and release data separately**

```bash
git add data/manifests/acl/2026-findings.json data/normalized/acl/2026-findings.jsonl data/snapshots/acl/2026-findings data/analysis/acl/2026-findings/validation.json notes/acl-2026-findings-overview.md scripts/verify_acl_findings_live_release.py tests/test_verify_acl_findings_live_release.py
git commit -m "data: collect ACL 2026 Findings papers"
git add data/releases/ACL/2026/tracks/findings
git commit -m "data: publish ACL 2026 Findings paper index"
```

### Task 8: Run full local, browser, CI, and public-site acceptance

**Files:**
- Modify: `README.md`
- Modify: `.superpowers/sdd/2026-08-28-acl-2026-findings/task-01-report.md`
- Test: `tests/test_workflows.py`
- Test: `site/tests/visual.spec.ts`

**Interfaces:**
- Local preview: `/ai-conference-overview/conferences/acl/2026/findings/`.
- Public URL: `https://smallflyingpig.github.io/ACL-2026-trending/ai-conference-overview/conferences/acl/2026/findings/` unless repository Pages configuration reports a different canonical base.

- [ ] **Step 1: Run the complete Python and frontend suites**

Run:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
python scripts/generate_award_host_policy.py --check
python scripts/generate_release_selectors.py --check
cd site && npm test -- --run && npm run check && npm run build
```

- [ ] **Step 2: Run full Playwright acceptance**

Run: `cd site && PLAYWRIGHT_PORT=4399 npm run test:e2e`

Verify desktop and 390px Long/Findings navigation, Findings count and source, Track-filter URL round-trip, at least one Findings detail page, no Findings awards/advances/topics, no console error, no 404, and no horizontal overflow.

- [ ] **Step 3: Self-review scope and compatibility**

Run `git diff --check`, inspect every staged path, rerun the Findings verifier, and byte-compare the ACL Long pointer plus six hashes with the recorded baseline. Confirm the generation directory contains exactly six files and production data contains no downloaded PDFs.

- [ ] **Step 4: Update README and commit acceptance evidence**

Document the new Findings route, the papers-only status, official source, and the two-stage boundary in Chinese. Record exact test counts, source hashes, selected generation, and browser routes in the Task report.

```bash
git add README.md tests/test_workflows.py site/tests/visual.spec.ts
git commit -m "test: verify ACL Findings publication"
```

- [ ] **Step 5: Publish and verify the live site**

Push `main`, monitor CI and Pages to success, then open the cache-busted public Findings URL. Compare the rendered count, Track label, source URL, and a paper detail route with the selected immutable release. A workflow trigger alone is not completion.
