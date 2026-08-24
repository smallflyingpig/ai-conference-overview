import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
