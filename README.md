# AI Conference Overview

Reference site and tooling for tracking AI conference trends.

## Development

Install the package and development dependencies:

```bash
python -m pip install -e '.[dev]'
```

The site award-source allowlist is generated from the authoritative
`config/venues.yaml` registry. After changing `official_award_hosts`, regenerate it:

```bash
python scripts/generate_award_host_policy.py
```
