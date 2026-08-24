# Task 14 report

## Outcome and evidence boundary

Task 14 phases A–D are staged for the official ACL 2026 long-paper scope. The
corpus and award metadata are official-source backed, hash-bound, and complete
under the declared inclusion rule. The primary-topic distribution and five
advance lanes are explicitly preliminary assisted outputs: no theme has a
completed semantic audit, so all ten themes are experimental/withheld and none
is used as publication-safe headline evidence. Award PDF deep reads were not
performed; the release contains only the official volume-page inventory.

Code/orchestration commit:

- `bf5065e` — `feat: orchestrate ACL conference analysis`

## Phase A — Task 13 breaker and orchestration

- The TypeScript evidence boundary now performs WHATWG hostname
  canonicalization first, then enforces Python-equivalent STD3 ASCII labels:
  letters/digits/hyphen only, no leading or trailing hyphen, at most 63 bytes
  per label, and at most 253 bytes for the canonical hostname. Regressions cover
  underscore, bad hyphens, a 64-byte label, a valid 253-byte hostname, and a
  254-byte hostname.
- ACL `collect`, `validate`, `export-classification`, `analyze`, `awards`, and
  `build-site` CLI paths now call real orchestration. Unsupported venue routes
  return structured nonzero failures instead of falling through to ACL logic.
- The configured official BibTeX URL was corrected to
  <https://aclanthology.org/volumes/2026.acl-long.bib>. Fetching checks declared
  `Content-Length`; BibTeX parsing also requires valid UTF-8, a complete final
  entry, and equality between declared and parsed entry counts.
- Release-backed site building resolves the release root before changing into
  the `site/` working directory, validates `current.json`, and requires the ACL
  conference route to exist after the Astro build.

## Phase B — official collection and normalization

Official source snapshots selected by the collection manifest:

| Source | Retrieved at | Bytes | SHA-256 |
|---|---|---:|---|
| ACL Anthology BibTeX | `2026-08-24T16:50:50.968120Z` | 1,939,185 | `94ad985a1a34d59ffe2f42e44354f966d012137e010948fd0c5d62ad15e5c12e` |
| ACL Anthology volume HTML | `2026-08-24T16:50:50.991724Z` | 6,869,443 | `ff98541fd3ca2d68e150f41f4be20e2da89618ac18fca3c0b4fe7661cdfc6632` |

The content-addressed raw payloads are under
`data/snapshots/acl/2026-long/raw/`; retrieval-event manifests remain immutable.
Two complete collection executions produced four event manifests pointing to
the same two content-addressed payloads.

Reconciliation is observed from the source, not hard-coded:

- discovered BibTeX entries: 2,223;
- included `inproceedings` long papers: 2,222;
- explicitly excluded proceedings/front matter: one,
  `acl:2026.acl-long.0`;
- unresolved records, duplicate source IDs, definite duplicate pairs, and
  duplicate candidates: zero;
- exact landing and PDF URL coverage: 2,222 / 2,222;
- abstract coverage: 2,220 / 2,222 (99.91%); missing only
  `acl:2026.acl-long.1232` and `acl:2026.acl-long.1657`;
- DOI coverage: 2,220 / 2,222 (99.91%); missing only
  `acl:2026.acl-long.1224` and `acl:2026.acl-long.1476`.

Normalized artifact identities:

- JSONL SHA-256:
  `f21f58d513ae18c4bf70606e914dd0a3c02c9ee44f3ab27d81e2d83bc8c4d8db`;
- canonical record-set SHA-256:
  `ac0c4fdb0537cfa4d136f2039dbe35caef812ce328a1c9e2fc91b74491b00527`.

## Phase C — assisted classification and honest audit state

- Taxonomy: `2026-08-24-v1`.
- Deterministic export: 56 batches, maximum 40 papers per batch.
- Inputs used for every proposal: exact title plus official abstract when
  available. Every one of the 2,222 included ACL IDs has exactly one primary
  assignment, a confidence value, and an evidence-phrase rationale.
- Assisted classifier: `deterministic-title-abstract-assisted-v1`.
- Low-confidence assignments retained: 761. They are explicitly recorded as
  `pending_semantic_review`; none was dropped or silently promoted.
- Audit queues: a deterministic confidence-stratified sample of 50 candidates
  for each of the ten primary themes (500 candidates total).
- Completed semantic adjudications: zero. Consequently there is no measured
  precision or Wilson result. The release's zero-valued audit fields are the
  schema representation of a zero-size completed sample, not a precision claim.
- Publication decision: 0 audit-passed themes; all 10 are marked
  `experimental` and excluded from headline claims. The site renders this state
  directly and calls the charts preliminary assisted distributions.

Preliminary one-year distribution (not a trend):

| Assisted primary topic | Papers | Share of 2,222 |
|---|---:|---:|
| Foundation Models | 570 | 25.65% |
| Reasoning and Agents | 419 | 18.86% |
| Evaluation | 394 | 17.73% |
| Data and Retrieval | 265 | 11.93% |
| Learning and Optimization | 197 | 8.87% |
| Trustworthiness | 105 | 4.73% |
| NLP/CV Core Tasks | 92 | 4.14% |
| Multimodal Models | 66 | 2.97% |
| Multilingual and Inclusive NLP | 58 | 2.61% |
| Applications | 56 | 2.52% |

These values describe the current assisted label distribution only. They do not
support temporal, year-over-year, prevalence, or quality claims.

## Phase D — official awards and preliminary synthesis handoff

The official ACL volume HTML contains 30 exact award badge elements, all joined
to included papers by ACL ID:

- Best Paper (3): `689`, `1550`, `1739`;
- Best Resource Paper (4): `937`, `1301`, `1654`, `1948`;
- Best Social Impact Paper (3): `144`, `875`, `1869`;
- Best Theme Paper (2): `421`, `772`;
- Outstanding Paper (18): `24`, `148`, `235`, `270`, `419`, `479`, `734`,
  `893`, `1110`, `1321`, `1340`, `1436`, `1653`, `1657`, `1886`, `2003`,
  `2132`, `2203`.

`data/awards/acl/2026-long.yaml` records, for every badge, the normalized award
type, ACL paper ID, title, official landing/PDF URLs, official volume URL, and
exact badge locator. Its `deep_reads` list is empty. An independent count over
the captured HTML found the same type distribution (18 + 4 + 3 + 3 + 2 = 30).

The release also stages five title-and-abstract shortlist lanes, five official
paper links per lane. These are candidate reading queues rather than
paper-result claims:

- text LLMs: `1003`, `1004`, `1040`, `1043`, `1045`;
- multimodal models: `1438`, `1626`, `169`, `1888`, `1909`;
- reasoning/agents: `1`, `1016`, `1039`, `1047`, `1049`;
- data/training: `1013`, `1038`, `1054`, `1070`, `1073`;
- evaluation/trust: `1023`, `1024`, `1025`, `1037`, `1092`.

Each ID above is prefixed by `acl:2026.acl-long.` in the release, and each
shortlist claim is typed `cross_paper_synthesis` with official ACL landing URLs.
No numeric result was inferred from an abstract.

## Release identity

Selected generation:

`8c9067fa8c140b50cfc3b071dbe8ea106afba39550d9e2ca1b9dd9252041e576`

`current.json` binds exactly six artifacts:

| Artifact | SHA-256 |
|---|---|
| `overview.json` | `58b23ecadcbc5cd9175aa4a3c29d5e4eee5c0ca31c638feb910229a95206e9b0` |
| `overview.md` | `1e380d99594c72fb480694ebffe4fa294f20c3c669cf31f6862bd4caccc19468` |
| `papers.csv` | `57ee2562ac814b85db54128d0d10f48e46fd40403c6d93bdff3c90700a78e7ec` |
| `papers.json` | `2733f6028f5204070df43a6cccd2cec4d777369253ce55865747c1a4a50d3390` |
| `provenance.json` | `34820d4e5c2c96ae0e780bbd5f322c9328362a6fe0787129b2a43cb0c794be66` |
| `validation.json` | `47411d89142d133c2f8aeafdcfe9609f9e3b7352c5e7052772dad28f626cf6dc` |

The release-backed Astro output contains
`site/dist/conferences/acl/2026/index.html`. No award-paper detail route is
emitted because there are no deep-read artifacts.

## Verification commands and results

- `.venv/bin/pytest -q` — 222 passed.
- `.venv/bin/ruff check src tests` — clean.
- `cd site && npm test -- --run` — 106 passed across five files.
- `.venv/bin/conference-trends build-site --root .` — Astro check/build passed;
  the validated ACL route exists.
- `conference-trends validate ... --audit` — corpus publishable, ten themes
  explicitly withheld, 50 pending audit candidates per theme.
- `conference-trends awards ...` — 30 official inventory records, zero deep
  reads.
- unsupported `NEURIPS/2025` collection — structured `unsupported`, exit 2.
- missing release build path — structured `invalid_input`, exit 2.
- rendered checks — conference page contains `0 audit-passed · 10
  experimental`; advances are labeled preliminary; no award detail file exists.

## Remaining controller handoff

1. Semantically adjudicate the 500 stratified audit candidates, including the
   retained low-confidence cases represented in those queues. Publish a theme
   only if observed precision is at least 90% and the Wilson 95% lower bound is
   at least 80%; otherwise retain the experimental disclosure.
2. Review the 30-row official award inventory, select award papers for separate
   deep reads, and add only PDF-grounded claims with exact locators and method
   diagrams through the existing release gates.
3. Rerun analysis and select a new immutable generation after either audit or
   deep-read evidence changes. Do not mutate this generation.

## Round 1 remediation — 2026-08-25

This section supersedes the affected counts and artifact identities above. The
round-1 code/test commit is `f1d3039` (`fix: close ACL analysis review gaps`).

### Source completeness and normalization

- Collection now reconciles the exact ACL IDs in the HTML volume listing in
  both directions against every BibTeX paper ID plus the separately excluded
  proceedings/front-matter ID. A syntactically complete but shortened BibTeX
  response is rejected even when its self-declared `Content-Length` matches.
- The HTML parser now handles the HTML void-element set without corrupting its
  nesting stack. In the unchanged official HTML snapshot this restores the
  1,293-character abstract for `acl:2026.acl-long.1657`.
- Rebuilt strictly from the two existing, hash-verified immutable snapshots;
  no network retrieval occurred and the four existing retrieval-event
  manifests were unchanged. Source bytes and SHA-256 remain 1,939,185 /
  `94ad985a1a34d59ffe2f42e44354f966d012137e010948fd0c5d62ad15e5c12e`
  for BibTeX and 6,869,443 /
  `ff98541fd3ca2d68e150f41f4be20e2da89618ac18fca3c0b4fe7661cdfc6632`
  for HTML.
- Reconciliation remains 2,223 discovered = 2,222 included + one excluded
  front-matter record. Abstract coverage is now 2,221 / 2,222 (99.95%);
  only `acl:2026.acl-long.1232` is missing. PDF coverage remains 2,222 /
  2,222 and DOI coverage remains 2,220 / 2,222.
- Regenerated normalized JSONL SHA-256:
  `a2f7cd695465e4880044a721f53396d3cf5fc05548237a01f4d1c6257e81ee51`;
  canonical record-set SHA-256:
  `c3aebf3d53e99f9f97efa26d18c6ca90897c4b9c5002700be9635fea4cfb4873`.

### Track inference and exhaustive classification review

- `conference-trends awards --venue ACL --year 2026` now infers the sole
  configured `long` track and emits 30 official inventory rows with zero deep
  reads. An explicit `--track short` still returns structured `unsupported`
  with exit 2.
- The 500-item stratified audit sample remains a separate measurement sample.
  A deterministic exhaustive review queue now covers all 761 assignments below
  confidence `0.70`, including IDs not selected into an audit sample. Its
  SHA-256 is
  `4a57a51eb42f3cdc73be718c8fbf6068465c52158bfcd3d25ee3c253bdff57e3`.
  The decision registry SHA-256 is
  `96e83b7c3ae6baeca20d606b1bb6da6196673ace99635c26c8809cc23052ed42`.
- Current honest state is 761 total, zero reviewed, 761 pending, and zero
  rejected. Each theme is gated on both its stratified audit and all of its
  low-confidence decisions; therefore all ten remain experimental/withheld.
  The release and rendered methodology expose these completeness counts.
- Release generation time is now the actual timezone-aware generation time
  (`2026-08-24T17:42:11.511428Z`), distinct from the retained source retrieval
  timestamps. Confidence/ID-ranked lane picks are labeled `preliminary_examples`
  and explicitly make no representativeness or lane-purity claim.

### Regenerated release identity

The previous immutable generation remains present. `current.json` now selects
the new six-artifact generation
`c80b2ea7012315adf73a29e77e1ea453a536e6746f9baa543e10a6eb2e5ddb8f`:

| Artifact | SHA-256 |
|---|---|
| `overview.json` | `873e725a15b4fb7642e3ca9bb9480b5a70ee73f624e34e42ec368cd00666f8a3` |
| `overview.md` | `1e380d99594c72fb480694ebffe4fa294f20c3c669cf31f6862bd4caccc19468` |
| `papers.csv` | `192ed6e93ee76a52d90419bd0b205e9698bf8abbe5e9a17fdfd4d252137077d5` |
| `papers.json` | `1eeda7a7cd3891bd7048bf3b20c0b3bee317fa5ca1912cb08f3defb5a8d11343` |
| `provenance.json` | `34820d4e5c2c96ae0e780bbd5f322c9328362a6fe0787129b2a43cb0c794be66` |
| `validation.json` | `843799a1dd45ff8bcc5440de5d72a8c378bd5e47dd93e7ccecda695e974016aa` |

### Round 1 verification

- `.venv/bin/pytest -q` — 233 passed.
- `.venv/bin/ruff check .` — clean.
- `cd site && npm test` — 109 passed across five files.
- `cd site && npm run build` — Astro check reported zero diagnostics and built
  seven static pages, including `/conferences/acl/2026/` and `/methodology/`.
- `.venv/bin/conference-trends validate --venues ACL --years 2026 --tracks long`
  — validated 2,223 / 2,222 / one; publishable source corpus.
- Rendered methodology contains `761 assignments`, `761` pending, and `final
  publication remains gated`; the awards directory still contains no paper
  detail route because deep reads remain intentionally out of scope.
