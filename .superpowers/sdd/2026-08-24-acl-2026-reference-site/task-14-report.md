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

## Semantic assignment integration — 2026-08-25

The semantic-import code/test commit is `5f9b69c` (`feat: import ACL semantic
assignments`). It adds `conference-trends import-classification`, which requires
the exact eight modulo partitions, validates every row against taxonomy
`2026-08-24-v1`, rejects duplicate/missing/unexpected IDs, checks each ACL
numeric ID against its declared modulo-8 partition, and requires exact equality
with the normalized corpus ID set. The canonical output is deterministically
sorted by paper ID. An independent post-import comparison confirmed all 2,222
input decisions match the authoritative JSONL field-for-field after numeric
confidence normalization.

### Explicit semantic-labeling provenance

The classification manifest now identifies
`agent-semantic-batch-review-v1` with method
`explicit_agent_semantic_labeling`; it no longer identifies these assignments
as deterministic title-phrase proposals. The raw input identities are:

| Partition | Rows | Input file | SHA-256 |
|---:|---:|---|---|
| 0 | 277 | `acl2026-reclass-mod0.jsonl` | `29d678592e68b30b8be18ecc07577c9115b7bd94e36d222ec2211fa21716bc7b` |
| 1 | 278 | `acl2026-reclass-mod1.jsonl` | `f941163c7c2017c0e2971a4903295cb51e3d9bfb8dd88b82b2c123d8f9c1e4a8` |
| 2 | 278 | `acl2026-reclass-mod2.jsonl` | `083f76d8ca04f460c8e86e3349467168e8c9c91da2578c06c26e14ee56c339ba` |
| 3 | 278 | `acl2026-reclass-mod3.jsonl` | `abe4201389bc7735dc8e9df43de08bff7ab177a0c70dfc95a93437f88760a84f` |
| 4 | 278 | `acl2026-reclass-mod4.jsonl` | `c937f50d576b818c837c45b0bed56ce3fd222cea875069b5bceb3e8795e79ba6` |
| 5 | 278 | `acl2026-reclass-mod5.jsonl` | `d10b1504392a774829d8fbc2ff4f0caef96f162756d2f487247054894098b5aa` |
| 6 | 278 | `acl2026-reclass-mod6.jsonl` | `ac66d26011ccb34eba0b68d8bfb4892145ca31a054614a90d456051f5366a03b` |
| 7 | 277 | `acl2026-reclass-mod7.jsonl` | `bddb8b1e57a094618d88a612cc1eb5bd6d4ebd964ff7f7ece77857c2b83246d2` |

Canonical classification artifact identities:

- `assignments.jsonl`:
  `135c5463e39afaf5282504ec0f7c4f35757d8cd4de8d8258e19a0f4e5e7cc831`;
- `classification-manifest.json`:
  `b6a2935380be394a5590eb709a2193ad9e73cc84bfd205c4ba0657a3111e87c4`;
- `audit-samples.json`:
  `5a564fa69f63d614388d915142785f8fe1c34691c3a87d7048b0a58449cc0ce0`;
- empty `audit-decisions.json`:
  `eab5dbbd86ab6f870a92caef38f27f317ae21e7214fce35a34efa9244e679871`;
- `low-confidence-review-queue.json`:
  `4df66c285d95c6a746f32188393ca8236b13843d7c9d3825e3c3d693795bea07`;
- empty low-confidence decisions:
  `da7ed49008048a4ea4d6c6355d55fe7495f4bbfb8320bcf08d656cb39bdbdc6b`.

### New semantic distribution

This remains a one-year distribution, not a trend or a publication-safe theme
claim.

| Primary topic | Papers | Share of 2,222 |
|---|---:|---:|
| Evaluation | 500 | 22.50% |
| Trustworthiness | 348 | 15.66% |
| Learning and Optimization | 341 | 15.35% |
| Reasoning and Agents | 247 | 11.12% |
| Applications | 199 | 8.96% |
| Data and Retrieval | 168 | 7.56% |
| Multimodal Models | 146 | 6.57% |
| Multilingual and Inclusive NLP | 117 | 5.27% |
| NLP/CV Core Tasks | 103 | 4.64% |
| Foundation Models | 53 | 2.39% |

Exact numeric confidence distribution:

| Confidence | Count | Confidence | Count | Confidence | Count |
|---:|---:|---:|---:|---:|---:|
| 1.00 | 70 | 0.99 | 933 | 0.98 | 442 |
| 0.97 | 213 | 0.96 | 162 | 0.95 | 82 |
| 0.94 | 84 | 0.93 | 46 | 0.92 | 33 |
| 0.91 | 42 | 0.90 | 32 | 0.89 | 11 |
| 0.88 | 21 | 0.87 | 12 | 0.86 | 11 |
| 0.85 | 4 | 0.84 | 8 | 0.83 | 3 |
| 0.82 | 7 | 0.81 | 2 | 0.79 | 1 |
| 0.78 | 1 | 0.76 | 1 | 0.52 | 1 |

Only `acl:2026.acl-long.1232` is below the `0.70` low-confidence threshold. It
is retained in a newly bound review queue with zero decisions and one pending
review. All previous classification-audit decisions were invalidated and reset;
the regenerated audit registry contains exactly 50 candidates for each of the
ten themes and zero completed decisions. Consequently all ten themes remain
explicitly experimental/withheld until fresh independent audits pass both
declared precision gates.

### Snapshot and release regeneration

The normalized corpus was rebuilt from the original hash-verified snapshots
without a network fetch. Source bytes, source SHA-256 values, the 2,223 / 2,222
/ one reconciliation, and the four immutable retrieval-event manifests remain
unchanged.

`current.json` now selects six-artifact generation
`4ac7654f93f39fd4a85dfd3d3a22d941c24e767275802698d419cad7bcdb95cf`:

| Artifact | SHA-256 |
|---|---|
| `overview.json` | `44c7c3ad631361e933fe29ae661fff331603c9995bb58b7e5e9e8cfd6b1ebad2` |
| `overview.md` | `1e380d99594c72fb480694ebffe4fa294f20c3c669cf31f6862bd4caccc19468` |
| `papers.csv` | `192ed6e93ee76a52d90419bd0b205e9698bf8abbe5e9a17fdfd4d252137077d5` |
| `papers.json` | `1eeda7a7cd3891bd7048bf3b20c0b3bee317fa5ca1912cb08f3defb5a8d11343` |
| `provenance.json` | `34820d4e5c2c96ae0e780bbd5f322c9328362a6fe0787129b2a43cb0c794be66` |
| `validation.json` | `843799a1dd45ff8bcc5440de5d72a8c378bd5e47dd93e7ccecda695e974016aa` |

The rendered site labels this as a preliminary semantic distribution, shows
one pending low-confidence review and the final-publication gate, builds seven
static pages, and still emits no award-paper detail route.

Verification after semantic integration:

- `.venv/bin/pytest -q` — 235 passed;
- `.venv/bin/ruff check .` — clean;
- `cd site && npm test` — 109 passed across five files;
- `cd site && npm run build` — zero diagnostics, seven pages;
- exact-six pointer hashes, 2,222 normalized/assignment IDs, eight input hashes,
  500 audit candidates, empty decision registries, and all ten withheld themes
  were checked directly.

## Post-semantic audit corrections and award DeepReads — 2026-08-25

This section supersedes the preceding semantic distribution and award handoff.
It does **not** claim final classification audit completion: the supplied audit
decisions were used to correct the authoritative assignments, which invalidates
those same measurements. Fresh post-correction audit decisions are therefore
empty, and all ten topic themes remain experimental/withheld.

Code/test commit: `b647728` (`feat: integrate ACL audit and award evidence`).

### Guarded classification corrections

- Two independent audit fragments cover the exact 500 prior sample IDs: 250
  each, with SHA-256
  `e6833acd27797335a9efa6201c5b2a96b61a375a447820310085bddf820c4fe3`
  and
  `3c6ce8ac9dbf23192a0e87c79544a4cab55c39062be43883740d8fb662529e01`.
- There were 24 corrected primary topics. Import requires each decision's old
  theme to match both the old sample and the live assignment and rejects
  duplicate/conflicting decisions. Corrected rows use confidence `0.99` and an
  `independent audit correction` rationale; the manifest records old/new topic,
  paper ID, decision source, and both source hashes.
- `acl:2026.acl-long.1232` remains `Data and Retrieval` at confidence `0.52`.
  Its explicit accept decision was rebound only after checking that the
  assignment was unchanged. Review source SHA-256 is
  `29f028815937a9c2981f44c9627c7dcd5b90de9e1770b552b12f370027a1a618`;
  the current queue has one row, one reviewed, zero pending, zero rejected.
- A fresh confidence-stratified queue contains 50 candidates per theme and the
  fresh audit decision registry is empty. Artifact identities are:
  assignments `c51895a7148b15c8a9756d6651ae013b85b2a17b64f8496d2fe1d17455333b6b`,
  manifest `60943f57e7894fd883a6e0d00d1a131c4ed34807d1d7e295d7f79da3a64c7a67`,
  samples `763db1f875e3f6e68f050845bc45aff1768d04f70705cf62b1f8b2d6fc64f507`,
  empty decisions `eab5dbbd86ab6f870a92caef38f27f317ae21e7214fce35a34efa9244e679871`,
  low queue `2eef098c0a380c6a3b204a4e0fc58f2765d706d372431db8f611ab08c25f4ddd`,
  and low decisions
  `07beab5f09533fc0f1dcd7708b83be0a01f95f84fc776d0201f924d0472e817b`.

Corrected preliminary distribution (one year, not a trend):

| Primary topic | Papers | Primary topic | Papers |
|---|---:|---|---:|
| Evaluation | 501 | Trustworthiness | 351 |
| Learning and Optimization | 343 | Reasoning and Agents | 241 |
| Applications | 196 | Data and Retrieval | 170 |
| Multimodal Models | 148 | Multilingual and Inclusive NLP | 114 |
| NLP/CV Core Tasks | 104 | Foundation Models | 54 |

Exact confidence counts are: 1.00: 70; 0.99: 955; 0.98: 438; 0.97: 210;
0.96: 161; 0.95: 79; 0.94: 83; 0.93: 44; 0.92: 33; 0.91: 40;
0.90: 31; 0.89: 10; 0.88: 21; 0.87: 11; 0.86: 9; 0.85: 4;
0.84: 8; 0.83: 3; 0.82: 7; 0.81: 2; 0.78: 1; 0.76: 1; 0.52: 1.

### Official award evidence integration

- Three independently authored batches merge to the exact 30 official award
  IDs. Input SHA-256 values are
  `9e3e7657ad079854154b7b79a4298e22bacbe4e7caf780774122bedd36d584a4`,
  `ac6b11b0181a742c5ba6e59aeca03a9082f53acbbf2dd019a0486b07f304f4a7`,
  and
  `2024c3ddd3f17f47095ed5fcdb602d8bbfe2c4c9b4089b18aa828a5185968747`.
- Independent QA found local defects in 8 papers and supplied 30 guarded field
  replacements. Patch-source SHA-256 values are
  `1c861fa826ab451c8daa58769244c5523be39f67370c9f994392e844e870991c`
  and
  `52d83883ef965bbfd324a07df9d63ed7f256297fc99e0ae6f92366ba70ec1a35`.
  Every replacement requires exact equality with its declared old value before
  mutation. After patching, all 30 records pass both the Pydantic DeepRead model
  and `validate_deep_read`, and their ID set equals the official inventory.
- The provenance manifest contains the SHA-256/byte size of all ten batch,
  patch, source-note, and QA-report inputs plus page count, PDF byte size, and
  PDF SHA-256 for all 30 papers. It supports both independently authored table
  column layouts and canonicalizes bare `2026.acl-long.N` IDs. Output hashes:
  DeepReads
  `43c6afba10011fd34015c8edfb97f854159184f5d0f101801885c11d0ab0df5d`,
  provenance
  `7fca6c0193cb12afd1584d0b0a9744a9075e026bc55082f5578806bbd2d0cd83`.
- `notes/acl-2026-awards-deep-reads.md` is a coherent Chinese synthesis of all
  three reading sets after QA correction, rather than concatenated batch notes.
  It separates paper-reported results from cross-paper inference and retains
  internal inconsistencies, private/drifting dependencies, statistical limits,
  and external-validity boundaries. Quality review scored 46/50: source
  authority 10, evidence traceability 10, factual boundary 10, synthesis 9,
  readability/actionability 7. Note SHA-256:
  `92a825b4df8c8ddb983350926fd18dad15c4c12e4f4968a0547fdf68943829b6`.

### Staging release and route proof

The release was generated at `2026-08-24T19:57:37.238376Z` and current selects
generation `eeac0e41ebb398cea7e102bc6737a2d386b826fd9a0969a171932fb47ddbdec2`.
The generation directory contains exactly the required six files, and each
pointer hash was recomputed successfully:

| Artifact | SHA-256 |
|---|---|
| `overview.json` | `b62a453b9241f8e2dd27447bb759d12d2315ff677bc6d3dd512f356395d0b4b8` |
| `overview.md` | `1e380d99594c72fb480694ebffe4fa294f20c3c669cf31f6862bd4caccc19468` |
| `papers.csv` | `192ed6e93ee76a52d90419bd0b205e9698bf8abbe5e9a17fdfd4d252137077d5` |
| `papers.json` | `1eeda7a7cd3891bd7048bf3b20c0b3bee317fa5ca1912cb08f3defb5a8d11343` |
| `provenance.json` | `34820d4e5c2c96ae0e780bbd5f322c9328362a6fe0787129b2a43cb0c794be66` |
| `validation.json` | `843799a1dd45ff8bcc5440de5d72a8c378bd5e47dd93e7ccecda695e974016aa` |

Astro emits exactly 30 unique award detail routes. Every route is the safe form
`award-<64 lowercase hex>`; direct enumeration found no collision. The
conference page and all award pages are generated only from the validated
current release. Topic distributions remain staging-only because the new audit
decision registry is empty.

### Verification

- `.venv/bin/pytest -q` — 237 passed.
- `.venv/bin/ruff check .` — clean.
- `cd site && npm test -- --run` — 109 passed across five files.
- `cd site && npm run build` — Astro check: zero errors/warnings/hints; 37 pages
  built, including 30 unique award detail routes.
- Exact-six pointer validation — six filenames exactly, all six hashes match.
- Direct route validation — 30 routes, 30 unique, all safe; no collisions.

Remaining gate: obtain fresh post-correction decisions for the regenerated 50
per-theme audit samples. Until then no theme distribution is a final headline.

## Round 2 provenance remediation — 2026-08-25

This round fixes a single award-PDF provenance boundary. The prior importer
copied PDF size and SHA-256 from the independently authored Markdown notes; it
did not recompute them from official bytes. That allowed the stale
`acl:2026.acl-long.1340` claim (29,172,258 bytes,
`6ed9ae4a8ab652317ecb12513d79c1aae6741ef3acd7fdc80664802d64af6622`)
to enter the manifest.

### Boundary and regression

- The importer now downloads every inventory-bound PDF from its exact ACL
  Anthology URL. Existing `fetch_bytes` enforcement rejects Content-Length
  mismatches; an additional PDF boundary requires `%PDF-` plus a terminal
  `%%EOF`. SHA-256 and byte size are computed only from those verified bytes.
- Markdown PDF rows are treated as assertions, not authority. A claimed size or
  SHA mismatch raises before either DeepReads or provenance is written. The
  regression was observed RED against the old importer and GREEN after this
  change.
- Each output row records `source_url` and
  `verification_method=downloaded_official_pdf_bytes`; the manifest records a
  timezone-aware verification time. The release loader independently requires
  this method, valid time, safe official URL, positive byte size, valid SHA-256,
  unique IDs, and exact equality with the DeepRead ID set. A note-only legacy
  provenance file is now publication-blocking.
- PDFs were streamed only for verification and were not added to Git. The
  committed manifest is the immutable evidence record; no copyrighted PDF is
  included.

### Corrected official record

The official `https://aclanthology.org/2026.acl-long.1340.pdf` response was
re-fetched to its declared full Content-Length and independently checked with
`pdfinfo`:

- byte size: 27,185,425;
- SHA-256:
  `fb7f9235a9fd89aa4e0526d4b5201b1ec9209d6e3c67e83079180d54f9339a9d`;
- pages: 37.

The corrected 11–20 note input SHA-256 is
`92cf9d62f67368fa7edd62a17c6f5523dd258e147d37828985e337f449a7b91f`.
All 30 PDF rows were revalidated from official bytes. The DeepRead semantic
artifact is unchanged at
`43c6afba10011fd34015c8edfb97f854159184f5d0f101801885c11d0ab0df5d`;
the corrected provenance SHA-256 is
`33f3a49df32ccbb43d694da88f102b656061a84d464afcddbfe932a8b25eadd4`.

### Regenerated release and verification

`current.json` selects generation
`c3263d433e3eebffd30863015664792d1838e5127f1c94bf4661be0cae660973`.
Its directory contains exactly six artifacts and every pointer hash was
recomputed successfully:

| Artifact | SHA-256 |
|---|---|
| `overview.json` | `cd1c8553972387c20beb242af6d6bac92f8411e8b8fcf55340dfb56fca2341a6` |
| `overview.md` | `1e380d99594c72fb480694ebffe4fa294f20c3c669cf31f6862bd4caccc19468` |
| `papers.csv` | `192ed6e93ee76a52d90419bd0b205e9698bf8abbe5e9a17fdfd4d252137077d5` |
| `papers.json` | `1eeda7a7cd3891bd7048bf3b20c0b3bee317fa5ca1912cb08f3defb5a8d11343` |
| `provenance.json` | `34820d4e5c2c96ae0e780bbd5f322c9328362a6fe0787129b2a43cb0c794be66` |
| `validation.json` | `843799a1dd45ff8bcc5440de5d72a8c378bd5e47dd93e7ccecda695e974016aa` |

- focused RED/GREEN regression — passed after observing the intended failure;
- `.venv/bin/pytest -q` — 237 passed;
- `.venv/bin/ruff check .` — clean;
- `cd site && npm test -- --run` — 109 passed across five files;
- `cd site && npm run build` — zero diagnostics, 37 pages;
- exact-six pointer — six names and six hashes match;
- award routes — 30 total, 30 unique, all `award-<64 lowercase hex>`.

The classification state is unchanged: fresh topic audits remain empty and all
ten themes remain withheld.
