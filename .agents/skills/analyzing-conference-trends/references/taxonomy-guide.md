# Taxonomy assignment and audit

Read this reference before producing or consuming classification JSONL.

## Assignment contract

- Use the versioned common taxonomy in `config/taxonomy.yaml` while retaining venue-native tracks, keywords, and subject areas.
- Give every included paper exactly one primary label and zero or more distinct secondary labels.
- Preserve the exported paper ID, confidence, short evidence-based rationale, taxonomy version, and audit status.
- Do not classify from title alone when an abstract is available. Mark insufficient evidence or low confidence explicitly.
- A proposed emerging theme needs a human-readable name, representative papers, confidence, and relationship to the stable taxonomy. Never publish cluster numbers as themes.

Semantic labeling is an explicit agent/model step after `conference-trends export-classification`; validate every returned JSONL line before `analyze`. Do not silently skip, duplicate, or invent record IDs.

## Audit gate

For every primary theme, inspect a stratified sample of up to 50 papers, or all papers when fewer than 50 exist. Review every low-confidence assignment.

Headline publication requires both:

- observed primary-label precision at least 90%; and
- Wilson 95% lower bound at least 80%.

Publish sample size and confidence interval. After any taxonomy or prompt revision, reclassify and reaudit. A failing theme remains experimental and is excluded from headline trend claims and ranked emerging-theme outputs.
