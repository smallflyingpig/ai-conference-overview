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
