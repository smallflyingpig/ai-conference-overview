import subprocess
import sys
from pathlib import Path
from runpy import run_path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
render_policy = run_path(str(ROOT / "scripts/generate_award_host_policy.py"))[
    "render_policy"
]


def test_generated_award_host_policy_matches_venue_registry() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/generate_award_host_policy.py", "--check"],
        cwd=ROOT,
        check=False,
    )

    assert result.returncode == 0, (
        "config/award-host-policy.json drifted; run "
        "python scripts/generate_award_host_policy.py"
    )


def test_generated_policy_uses_registry_host_canonicalization(tmp_path: Path) -> None:
    registry = {
        "venues": {
            "ACL": {
                "years": {
                    2026: {
                        "tracks": {
                            "long": {
                                "official_award_hosts": [
                                    " ACLANTHOLOGY.ORG. ",
                                    "aclanthology.org",
                                    "BÜCHER.example.",
                                    "xn--bcher-kva.example",
                                    "BÜCHER.example。",
                                ]
                            }
                        }
                    }
                }
            }
        }
    }
    path = tmp_path / "venues.yaml"
    path.write_text(yaml.safe_dump(registry), encoding="utf-8")

    assert b'"ACL/2026/long"' in render_policy(path)
    assert render_policy(path).count(b"aclanthology.org") == 1
    assert b"xn--bcher-kva.example" in render_policy(path)
    assert render_policy(path).count(b"xn--bcher-kva.example") == 1


def test_generated_policy_rejects_double_terminal_dot(tmp_path: Path) -> None:
    path = tmp_path / "venues.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "venues": {
                    "ACL": {
                        "years": {
                            2026: {
                                "tracks": {
                                    "long": {"official_award_hosts": ["example.com.."]}
                                }
                            }
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="IDNA|hostname"):
        render_policy(path)
