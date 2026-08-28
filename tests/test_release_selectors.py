import json
import subprocess
import sys
from pathlib import Path
from runpy import run_path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/generate_release_selectors.py"


def render_selectors() -> bytes:
    assert SCRIPT.is_file(), "release selector generator is missing"
    return run_path(str(SCRIPT))["render_selectors"]()


def test_generated_release_selectors_match_the_venue_registry() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=ROOT,
        check=False,
    )

    assert result.returncode == 0, (
        "site/src/generated/release-selectors.json drifted; run "
        "python scripts/generate_release_selectors.py"
    )


def test_generated_release_selectors_preserve_default_and_nested_tracks() -> None:
    payload = json.loads(render_selectors())

    assert {
        "venue": "ACL",
        "year": 2026,
        "track": "long",
        "is_default_track": True,
        "release_path": "ACL/2026",
    } in payload["selectors"]
    assert {
        "venue": "ACL",
        "year": 2026,
        "track": "findings",
        "is_default_track": False,
        "release_path": "ACL/2026/tracks/findings",
    } in payload["selectors"]
