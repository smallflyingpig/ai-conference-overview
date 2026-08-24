# AI Conference Overview

An evidence-backed research atlas for accepted-paper distributions, audited topic analysis,
cross-paper advances, and officially verified award-paper deep reads.

The static site is configured for GitHub Project Pages at
`https://smallflyingpig.github.io/ai-conference-overview/`. The current reference release is
**ACL 2026 Volume 1 (long papers)**: 2,223 official entries discovered, one proceedings record
explicitly excluded, and 2,222 papers included. It is a one-year **distribution/snapshot**, not a
trend.

## Venue scope

The reusable `analyzing-conference-trends` skill defines source and evidence policy for ACL,
EMNLP, ICLR, ICML, NeurIPS (`NIPS` is normalized to `NEURIPS`), CVPR, ICCV, and ECCV. The site
information architecture already exposes these venues as the adapter roadmap.

Only ACL 2026 long papers have an end-to-end collected, classified, audited, and published release
in this revision. Other venues require their official-source adapters and comparable validated
venue-year releases before the site may show results or call a multi-year pattern a trend.

## Evidence boundary

Published claims remain visibly separated:

- **Official metadata** comes from official proceedings or conference/program sources.
- **Paper-reported** findings retain the paper's setting and a locator; they are not independently
  reproduced results.
- **Cross-paper synthesis** combines named papers without pooling incompatible metrics.
- **Inference** is an explicitly labeled interpretation.

Topic counts are primary-assignment shares, not total topic prevalence in a multi-label corpus.
Audit precision measures reviewed assignments and does not establish recall. Themes that miss the
configured observed-precision and Wilson-lower-bound gates remain experimental and are withheld
from headlines. Award pages exist only for officially verified records with a contract-valid deep
read. Third-party papers, figures, metadata, and conference assets retain their original rights.

## Install

Python 3.11+ and Node.js 24 are used in CI.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cd site
npm ci
npx playwright install chromium
cd ..
```

The site award-source allowlist is generated from the authoritative `config/venues.yaml` registry.
After changing `official_award_hosts`, regenerate and review it:

```bash
.venv/bin/python scripts/generate_award_host_policy.py
```

## Reproduce an analysis

The command boundary is `conference-trends`. Collection writes immutable official-source
snapshots; validation failures do not replace the last publishable release.

```bash
.venv/bin/conference-trends collect --venues ACL --years 2026 --tracks long
.venv/bin/conference-trends validate --venues ACL --years 2026 --tracks long
.venv/bin/conference-trends export-classification --venues ACL --years 2026 --tracks long

# Explicit agent/human semantic labeling happens here using the exported JSONL contract.
.venv/bin/conference-trends import-classification \
  --input <reviewed-classification-directory> \
  --venues ACL --years 2026 --tracks long

.venv/bin/conference-trends validate --venues ACL --years 2026 --tracks long --audit
.venv/bin/conference-trends awards --venue ACL --year 2026 --track long
.venv/bin/conference-trends analyze \
  --venues ACL --years 2026 --tracks long --write-release
```

Semantic assignment, low-confidence review, stratified audit decisions, full-theme correction
stages, and award PDF deep reads are evidence-bearing review steps—not unattended provider calls.
The selected release is bound by `data/releases/ACL/2026/current.json` and artifact SHA-256 hashes.

## Test and preview the site

Run the same local acceptance gates used by CI:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q

cd site
npm test
npm run build
npm run test:e2e
npm run preview -- --host 127.0.0.1 --port 4321
```

Open `http://127.0.0.1:4321/ai-conference-overview/`. Playwright checks desktop and mobile
layouts, the ACL overview and table fallback, methodology lineage, all five advance lanes, the
30-record award index and a deep-read route, base-path-safe internal links, HTTP success, and
browser console errors.

An empty-data build is also publication-safe:

```bash
mkdir -p /tmp/ai-conference-overview-empty-releases
cd site
CONFERENCE_RELEASE_ROOT=/tmp/ai-conference-overview-empty-releases npm run build
```

It emits only the evidence-limited shell; it does not fabricate a conference page.

## GitHub Pages deployment

`.github/workflows/ci.yml` validates pushes, pull requests, and manual runs. The Pages workflow
repeats the full Python, site, empty-data, production-build, and browser acceptance gates before
uploading `site/dist`; deployment runs only for `main` pushes or a manual dispatch.

Before the first public release, configure **Settings → Pages → Source: GitHub Actions**, review the
`github-pages` environment protections, and obtain approval to push/merge the validated commit to
`main`. Then verify the workflow and public endpoint:

```bash
gh run watch --exit-status
curl --fail --location https://smallflyingpig.github.io/ai-conference-overview/
```

No scheduled source update is enabled by default because conference and award records can be
temporarily incomplete.

## License

Project-authored code, configuration, documentation, and explanatory site content are available
under the [MIT License](LICENSE). Linked third-party research artifacts are not relicensed.
