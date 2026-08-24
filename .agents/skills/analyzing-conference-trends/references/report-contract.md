# Report and publication contract

Read this reference before writing a release or rebuilding the site.

## Required report content

1. **Overview:** venue/year/track scope, included and excluded counts, topic distribution, representative papers, and freshness.
2. **Advances:** evidence-labeled synthesis for text, multimodal, agents/reasoning, data/training, and evaluation/trustworthiness.
3. **Awards:** every officially verified award and deep read, or an explicit `not_announced`/`not_verified` state.
4. **Methodology:** official sources, retrieval time and SHA-256, taxonomy version, metrics, denominators, classification/audit method, and known limits.
5. **Data health:** missing abstracts/PDFs/DOIs, unresolved records, status mismatches, duplicate candidates, and snapshot additions/removals.

The release generator emits exactly `papers.json`, `papers.csv`, `overview.json`, `overview.md`, `validation.json`, and `provenance.json` in an immutable generation. Consumers resolve the validated generation through `current.json`; they do not read stale files directly from an output root.

## Publication gate

Block publication when counts do not reconcile, required provenance is incomplete, records are unresolved, definite duplicates/status mismatches exist, assignments are incomplete, a primary-theme audit fails, evidence claims lack required sources/locators, awards are unverified, or serialization contains invalid/non-finite data.

An incomplete or failed run may be retained for diagnosis but must not replace the last publishable release. `build-site` consumes only a validated current release. Report the specific gate and remediation; do not downgrade a failure to a caveat.
