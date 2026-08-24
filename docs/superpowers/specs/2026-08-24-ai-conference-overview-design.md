# AI Conference Overview: Design Specification

Date: 2026-08-24
Status: Approved in writing
Project slug: `ai-conference-overview`
Repository: `git@github.com:smallflyingpig/ai-conference-overview.git`
License: MIT

## 1. Objective

Build a reusable conference-analysis skill and a GitHub Pages website that:

1. collects accepted-paper metadata from official conference sources;
2. produces reproducible overviews and topic distributions;
3. measures topic trends across venues and years using normalized metrics;
4. deeply analyzes officially verified award papers;
5. synthesizes advances in text LLMs, multimodal models, reasoning and agents, data and training, evaluation, safety, and interpretability; and
6. publishes validated results at `https://smallflyingpig.github.io/ai-conference-overview/`.

The initial end-to-end reference run is ACL 2026 long papers. The architecture must also support ICLR, ICML, CVPR, EMNLP, ICCV, ECCV, and NeurIPS. User input `NIPS` is normalized to `NEURIPS`.

## 2. Scope

### 2.1 Included

- Single-venue, single-year overviews.
- Cross-year and cross-venue topic comparisons.
- Official-track preservation alongside a common cross-venue taxonomy.
- Multi-label semantic classification with one primary topic.
- Deterministic statistics, topic metrics, representative-paper selection, and evidence manifests.
- Official award discovery and paper-level deep reading.
- A static, responsive GitHub Pages website.
- Versioned JSON, Markdown, and CSV artifacts suitable for independent inspection.

### 2.2 Excluded from the first release

- Citation-based impact rankings, which are too immature for newly accepted papers.
- Submission or acceptance-rate analysis unless an official denominator is available.
- Review-score analysis as a cross-venue metric.
- Automated publication of unverified award candidates.
- Scraping paywalled publisher pages when an official open proceedings source exists.
- Server-side services, user accounts, comments, or a database-backed website.

## 3. System Architecture

```text
User request or CLI
        |
        v
Venue registry and request normalization
        |
        v
Official-source adapters
  |-- ACL Anthology: ACL and EMNLP
  |-- OpenReview: ICLR and metadata supplements where needed
  |-- PMLR: ICML proceedings
  |-- CVF Open Access: CVPR and ICCV
  |-- ECVA: ECCV
  `-- NeurIPS Proceedings: NeurIPS
        |
        v
Canonical paper records + provenance manifest
        |
        +--------------------+
        |                    |
        v                    v
Deterministic analysis    Semantic analysis
counts, dedup, shares     taxonomy, themes, synthesis
        |                    |
        +----------+---------+
                   v
          Evidence and quality audit
                   |
        +----------+-----------+
        |                      |
        v                      v
Versioned data/reports     Astro static site
                               |
                               v
                     GitHub Pages deployment
```

The website never scrapes source pages at runtime. It consumes only validated, versioned analysis artifacts.

## 4. Components and Responsibilities

### 4.1 `analyzing-conference-trends` Skill

The skill routes natural-language conference-analysis requests to the deterministic pipeline and supplies the judgment rules that code alone cannot enforce:

- official-source preference and fallback boundaries;
- distinction between accepted papers, workshops, findings, short papers, and long papers;
- correct use of distribution versus trend terminology;
- cross-venue normalization requirements;
- topic-classification audit requirements;
- award verification and deep-reading requirements; and
- evidence labels for every generated claim.

The skill remains concise. Detailed source routing, taxonomy policy, evidence policy, and report contracts live in focused references. Repeated parsing and validation mechanics live in scripts and the Python package.

### 4.2 Venue Registry

`config/venues.yaml` declares:

- canonical venue name and aliases;
- supported years and track conventions;
- primary and optional secondary official sources;
- adapter type and source URL templates;
- whether abstracts, keywords, tracks, awards, and PDFs are normally available; and
- explicit exclusions such as front matter or workshop volumes.

The registry separates venue-specific facts from parsing code and permits year-specific overrides when a conference changes its proceedings format.

### 4.3 Source Adapters

Every adapter implements the same read-only contract:

```text
discover(request) -> source manifest
fetch(manifest) -> immutable raw snapshot
parse(snapshot) -> canonical paper records
validate(records, manifest) -> adapter quality report
```

Adapters must retain the source URL and raw source identifier for each record. They must not silently merge tracks or infer acceptance from arbitrary search results. Network retries are bounded; a partial fetch is reported as incomplete and cannot be published as a complete overview.

### 4.4 Canonical Paper Schema

Required fields:

- `paper_id`: stable source-qualified identifier;
- `title` and normalized title;
- `authors`;
- `venue`, `year`, and `track`;
- official landing-page URL;
- primary source name and retrieval timestamp; and
- record status: complete, partial, excluded, or unresolved.

Optional fields include abstract, keywords, subject areas, affiliations, DOI, PDF URL, code URL, award metadata, and official session information. Missing optional fields remain explicit nulls accompanied by coverage statistics.

### 4.5 Normalization and Deduplication

Deduplication uses source identifiers and DOI first, then normalized titles as a diagnostic fallback. Fuzzy title similarity identifies review candidates but never silently deletes a record. Track exclusions are explicit and counted.

The validation report reconciles:

- source entries discovered;
- proceedings/front matter excluded;
- canonical records emitted;
- duplicate candidates;
- missing abstracts, PDFs, tracks, and identifiers; and
- differences from a previous snapshot.

### 4.6 Topic Analysis

Each paper receives:

- one primary common-taxonomy label;
- zero or more secondary common-taxonomy labels;
- retained venue-native tracks, keywords, and subject areas;
- a classification confidence value;
- a short evidence-based rationale; and
- an audit status.

The initial common top-level taxonomy is:

1. Foundation Models;
2. Reasoning and Agents;
3. Data and Retrieval;
4. Learning and Optimization;
5. Evaluation;
6. Trustworthiness;
7. Multimodal Models;
8. Multilingual and Inclusive NLP;
9. Applications; and
10. NLP/CV Core Tasks.

Subtopics remain versioned in `config/taxonomy.yaml`. Emerging themes may be proposed from title and abstract clusters, but publication requires a human-readable name, representative papers, confidence, and a stated relationship to the stable taxonomy. Cluster numbers are never published as themes.

### 4.7 Trend Metrics

Raw paper counts are shown but not used alone for cross-venue trend claims.

| Metric | Definition | Interpretation |
|---|---|---|
| Topic Share | topic papers / included venue-year papers | Within-conference attention |
| YoY Share Delta | current share - prior-year share | Increase or decrease in percentage points |
| Venue Enrichment | venue topic share / pooled topic share | Venue specialization |
| Cross-venue Spread | number and share of venues containing the topic | Diffusion across communities |
| Emerging Score | documented combination of share growth, spread growth, and novelty | Ranking of candidate emerging themes |

The Emerging Score formula and component values are published. A one-year snapshot is described as a distribution or set of hotspots, never a trend. Trend claims normally require at least three consecutive years; shorter comparisons are explicitly qualified.

### 4.8 Advance Synthesis

The synthesis layer organizes supported advances under:

- Text LLMs;
- Multimodal Models;
- Reasoning and Agents;
- Data, Pretraining, and Post-training;
- Evaluation, Safety, and Interpretability; and
- domain-specific or cross-disciplinary advances when strongly represented.

Every advance links to supporting papers and labels its evidence type as `Official metadata`, `Paper-reported`, `Cross-paper synthesis`, or `Inference`. Paper-reported numerical claims retain their original experimental setting and source.

### 4.9 Award Verification and Deep Reading

Award status is obtained only from an official conference website, proceedings page, program, or program-chair announcement. If no official source is available, the status is `not_announced` or `not_verified`; candidate papers are not substituted.

Each verified award-paper analysis includes:

- award type and official evidence URL;
- research problem and significance;
- method architecture;
- data and training setup;
- evaluation setting and exact reported results;
- differences from prior work;
- limitations and reproducibility assessment;
- official award citation when available;
- a separately labeled synthesis of why the paper matters;
- transferable implications for text, multimodal, agent, or data pipelines; and
- paper, PDF, code, and dataset links when verified.

A method diagram is produced from the paper's disclosed architecture. It must not invent components absent from the paper.

## 5. Website Design

The site is an Astro static application deployed as a GitHub Project Pages site with base path `/ai-conference-overview/`.

### 5.1 Pages

- **Home:** overall conference cards, current emerging topics, modality summaries, and data-coverage status.
- **Conference/year:** overview, topic distribution, comparisons with prior years, representative papers, and awards.
- **Trends:** topic-by-venue heatmap, time-series shares, cross-venue spread, and filters for venue, year, modality, and theme.
- **Advances:** supported synthesis for text LLMs, multimodal models, agents, data/training, and evaluation/trustworthiness.
- **Awards:** searchable deep readings and architecture diagrams.
- **Papers:** filterable paper explorer with links to official pages and PDFs.
- **Methodology:** sources, taxonomy version, metrics, known gaps, build timestamp, and provenance.

### 5.2 Presentation Requirements

- Responsive desktop and mobile layouts.
- Accessible colors, labels, keyboard navigation, and tabular fallbacks for essential charts.
- Shareable stable URLs for venue-year, topic, advance, and award pages.
- Visible data freshness and completeness indicators.
- Every key statistic links to or identifies its underlying data artifact.
- No decorative ranking language that overstates incomplete evidence.

### 5.3 Build and Deployment

GitHub Actions performs data validation, tests, static build, and Project Pages deployment. The workflow supports manual `workflow_dispatch`. Scheduled source updates are not enabled by default because conference records and awards may be temporarily incomplete.

The configured remote repository is `smallflyingpig/ai-conference-overview`. The first public deployment still requires build and public-endpoint acceptance checks. Local implementation and static-site validation do not depend on enabling Pages early.

### 5.4 License

Project-authored source code, configuration, documentation, and website content are released under the MIT License. Third-party papers, metadata, figures, and conference assets retain their original rights and are linked or attributed rather than relicensed. Generated paper diagrams must be original explanatory renderings and must not copy protected figures verbatim.

## 6. Repository Structure

```text
ai-conference-overview/
|-- .agents/skills/analyzing-conference-trends/
|   |-- SKILL.md
|   |-- references/
|   |   |-- evidence-policy.md
|   |   |-- taxonomy-guide.md
|   |   |-- source-routing.md
|   |   `-- report-contract.md
|   `-- scripts/conference_trends.py
|-- config/
|   |-- venues.yaml
|   `-- taxonomy.yaml
|-- src/conference_overview/
|   |-- adapters/
|   |-- normalize.py
|   |-- classify.py
|   |-- metrics.py
|   |-- awards.py
|   `-- validate.py
|-- data/
|   |-- manifests/
|   |-- normalized/
|   |-- analysis/
|   `-- awards/
|-- site/
|-- tests/
`-- docs/
```

## 7. Interfaces

Natural-language examples:

- `分析 ACL 2026 long 的论文分布和大模型 advances`
- `比较 ICLR、ICML、NeurIPS 2024-2026 的 agent 研究趋势`
- `更新 CVPR 2026 overview，并深读 award papers`
- `重建 ai-conference-overview 网站`

CLI contract:

```bash
conference-trends analyze --venues ACL --years 2026 --tracks long
conference-trends compare --venues ICLR,ICML,NEURIPS --years 2024:2026
conference-trends awards --venue ACL --year 2026
conference-trends build-site
```

Unsupported venue/year combinations, incomplete proceedings, unknown tracks, and unverified awards return structured statuses and non-zero exit codes where publication safety would otherwise be compromised.

## 8. Error Handling and Publication Gates

The pipeline distinguishes:

- transient retrieval failure;
- source-format drift;
- incomplete official release;
- schema-validation failure;
- deduplication ambiguity;
- low-confidence classification;
- unavailable or unverified award status; and
- site build/deployment failure.

Incomplete or ambiguous data may be saved for inspection but cannot replace the last validated public snapshot. Every blocked publication produces an actionable validation report.

## 9. Testing Strategy

### 9.1 Skill Behavior

Skill development follows RED-GREEN-REFACTOR with realistic agent scenarios:

1. run baseline scenarios without the skill and record failures;
2. write the smallest guidance that corrects observed failures;
3. repeat the scenarios with the skill;
4. close demonstrated loopholes; and
5. validate skill metadata and discoverability.

Scenarios cover official-source selection, track boundaries, one-year trend overclaiming, raw-count cross-venue comparisons, unverified awards, evidence labeling, and incomplete data.

### 9.2 Code and Data

- Adapter fixture tests for representative official HTML, API, BibTeX, and XML structures.
- Contract tests for canonical record fields and structured errors.
- Exact reconciliation of official included-paper counts and explicit exclusions.
- Duplicate detection tests using identifiers, DOI, normalized titles, and ambiguous cases.
- Metric tests for denominators, percentage-point changes, enrichment, and spread.
- Award verification tests that reject unofficial-only evidence.
- Regression fixtures for source-format changes.

Live source tests are read-only and separate from deterministic fixture tests. A live failure does not rewrite expected fixtures automatically.

### 9.3 Taxonomy Audit

For each major published theme, inspect a stratified sample of up to 50 papers, or all papers when fewer than 50 exist. Publication requires:

- observed primary-label precision of at least 90%;
- Wilson 95% lower bound of at least 80%;
- disclosure of sample size and confidence interval;
- review of all low-confidence assignments; and
- reclassification after any taxonomy or prompt revision.

A theme that fails the gate remains marked experimental and is excluded from headline trend claims.

### 9.4 Site Acceptance

- Astro production build succeeds with `/ai-conference-overview/` as the base path.
- Internal links and asset paths resolve.
- Core routes render at desktop and mobile viewports.
- Essential charts have readable table fallbacks.
- Paper and evidence links are traceable from displayed claims.
- The deployed public URL `https://smallflyingpig.github.io/ai-conference-overview/` returns successfully.

## 10. Initial ACL 2026 Reference Run

The first complete run must:

1. reconcile all ACL 2026 long papers with the official ACL Anthology volume;
2. exclude proceedings front/back matter explicitly;
3. publish coverage, missingness, and duplicate diagnostics;
4. produce the topic distribution and representative-paper set;
5. distinguish one-year hotspots from cross-year trends;
6. synthesize advances for text LLMs, multimodal models, agents, data/training, and evaluation/trustworthiness;
7. verify and deeply analyze all officially announced ACL 2026 long-paper awards;
8. generate the corresponding website pages and data artifacts; and
9. pass local build, data, citation, and visual QA before deployment.

## 11. Acceptance Criteria

The first release is accepted when:

- every included paper has a unique canonical ID, official source URL, venue, year, track, and title;
- included and excluded counts reconcile exactly with the official source snapshot;
- no duplicate is silently removed on fuzzy evidence alone;
- all published trend claims satisfy the stated time-window and normalization rules;
- taxonomy audit thresholds are met or failing themes are visibly withheld;
- every award is officially verified and every numerical deep-reading claim is traceable to the paper;
- evidence types distinguish official metadata, paper-reported results, synthesis, and inference;
- the static site builds and passes route, accessibility, and visual checks; and
- public deployment succeeds at `https://smallflyingpig.github.io/ai-conference-overview/`.

## 12. Implementation Sequence

1. Establish project packaging, schemas, fixtures, and tests.
2. Implement ACL Anthology collection and normalization for the ACL 2026 reference run.
3. Implement deterministic statistics, taxonomy audit artifacts, and report generation.
4. Implement official award verification and deep-reading artifacts.
5. Build the Astro website against validated local data.
6. Add remaining venue adapters one source family at a time.
7. Configure GitHub Pages for `smallflyingpig/ai-conference-overview` and perform public acceptance.

Each adapter and analysis capability is added test-first. The public site never advances past the last validated snapshot.
