"""Generate the site award-host policy from the authoritative venue registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from conference_overview.registry import canonicalize_official_hosts

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "venues.yaml"
OUTPUT = ROOT / "config" / "award-host-policy.json"


def render_policy(registry_path: Path = REGISTRY) -> bytes:
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))["venues"]
    scopes: dict[str, list[str]] = {}
    for venue, definition in registry.items():
        for year, year_definition in definition.get("years", {}).items():
            for track, route in year_definition.get("tracks", {}).items():
                hosts = list(
                    canonicalize_official_hosts(
                        route.get("official_award_hosts", [])
                    )
                )
                scopes[f"{venue}/{year}/{track}"] = hosts
    payload = {"schema_version": "award-host-policy-v1", "scopes": scopes}
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = render_policy()
    if args.check:
        return 0 if OUTPUT.is_file() and OUTPUT.read_bytes() == expected else 1
    OUTPUT.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
