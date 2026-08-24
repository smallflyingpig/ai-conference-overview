---
name: analyzing-conference-trends
description: Use when analyzing accepted papers, topic distributions, research trends, award papers, or cross-venue advances for ACL, EMNLP, ICLR, ICML, NeurIPS, CVPR, ICCV, or ECCV.
---

# Analyzing Conference Trends

## Core rule

Build claims from validated official-source records. Keep source facts, paper-reported findings, cross-paper synthesis, and inference distinguishable; never let a compelling narrative outrun the data window or publication gate.

## Workflow

1. Normalize the venue, year, and track. Treat `NIPS` as `NEURIPS`; never merge long, short, Findings, workshop, or front-matter records. Before collection or award work, read [source routing](references/source-routing.md).
2. Use `conference-trends` as the command boundary. Inspect `conference-trends --help`, then route through `collect`, `validate`, `export-classification`, `analyze`, `awards`, and `build-site` as needed. A structured `unsupported`, incomplete, or non-zero publication-safety result is a stop condition, not permission to improvise around the pipeline.
3. Semantic labeling is an explicit audited agent action between classification export and analysis. Before assigning labels, read [taxonomy guide](references/taxonomy-guide.md). Preserve the exported record IDs and JSONL contract.
4. Compute deterministic counts and normalized metrics before writing interpretation. Before any trend, comparison, advance, or numeric claim, read [evidence policy](references/evidence-policy.md).
5. Verify awards from an eligible official source before deep reading. If verification is absent, report `not_announced` or `not_verified`; optional paper spotlights must be labeled non-award content.
6. Before `--write-release` or `build-site`, read [report contract](references/report-contract.md). Publish only the immutable release selected by its validated current pointer. Do not replace the last publishable release after any failed gate.

## Output priorities

- Lead with decision value: coverage, distribution or qualified trend, supported advances, and data-health limits.
- Link every headline statistic and award assertion to its artifact or source.
- Retain raw counts for transparency, but use topic share, share delta, enrichment, or cross-venue spread for comparison.
- Deep reads reproduce only disclosed method components and preserve each numerical result's experimental setting.

## Common mistakes

| Mistake | Required correction |
|---|---|
| Calling one year's largest topic a trend | Call it a distribution, snapshot, or hotspot. |
| Ranking venue interest from raw counts | Normalize with a shared taxonomy and denominator. |
| Promoting award rumors | Keep them as leads; withhold award profiles. |
| Publishing low-confidence themes | Mark experimental and exclude from headlines. |
