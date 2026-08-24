# Official source routing

Read this reference before collection, track selection, or award verification. Registry configuration is authoritative for supported venue/year/track combinations.

| Venue | Canonical proceedings family | Track boundary |
|---|---|---|
| ACL, EMNLP | ACL Anthology | Keep long, short, Findings, workshops, and front matter separate. |
| ICLR | OpenReview | Require accepted venue/decision evidence; exclude withdrawn and rejected submissions. |
| ICML | PMLR | Use the conference proceedings volume; do not infer acceptance from search results. |
| CVPR, ICCV | CVF Open Access | Preserve year and official program/proceedings boundaries. |
| ECCV | ECVA | Preserve proceedings year and volume identity. |
| NeurIPS (`NIPS` alias) | NeurIPS Proceedings | Normalize the alias; preserve track and year. |

Prefer immutable official metadata snapshots. Secondary sources may locate an official record or fill a disclosed optional field, but cannot silently establish acceptance, track membership, totals, or awards. Reconcile discovered, included, excluded, unresolved, and duplicate-candidate counts before analysis. Fuzzy matches are review candidates, never automatic deletions.

## Awards

Eligible evidence is an official conference website, official proceedings/program, or attributable program-chair announcement issued through an official channel. A personal social-media post, news article, lab page, author claim, or search snippet is only a lead.

- Use `not_announced` when the official award announcement is not yet available.
- Use `not_verified` when a claimed award lacks eligible official evidence.
- Never substitute predicted winners for verified awards.
- After verification, keep the official evidence URL, award type, paper landing page, and retrieval provenance.

Deep-read from the paper/PDF. Original explanatory diagrams may include only components disclosed by the paper; do not copy a protected figure or invent architecture.
