"""Generate site release selectors from the authoritative venue registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from conference_overview.registry import normalize_request
from conference_overview.scope import release_relative_parts

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "venues.yaml"
OUTPUT = ROOT / "site" / "src" / "generated" / "release-selectors.json"


def render_selectors(registry_path: Path = REGISTRY) -> bytes:
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))["venues"]
    if registry_path != REGISTRY:
        raise ValueError("alternate venue registries are not supported")
    selectors: list[dict[str, object]] = []
    for venue, definition in registry.items():
        for year, year_definition in definition.get("years", {}).items():
            for track in year_definition.get("tracks", {}):
                request = normalize_request(venue, int(year), track)
                selectors.append(
                    {
                        "venue": request.venue,
                        "year": request.year,
                        "track": request.track,
                        "is_default_track": request.is_default_track,
                        "release_path": "/".join(release_relative_parts(request)),
                    }
                )
    payload = {
        "schema_version": "release-selectors-v1",
        "selectors": sorted(
            selectors,
            key=lambda item: (item["venue"], item["year"], item["track"]),
        ),
    }
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render_selectors()
    if args.check:
        return 0 if OUTPUT.is_file() and OUTPUT.read_bytes() == expected else 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
