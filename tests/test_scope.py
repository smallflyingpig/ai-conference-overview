from pathlib import Path

import pytest

from conference_overview.registry import normalize_request
from conference_overview.scope import ScopePaths


def test_icml_paths_are_isolated_from_acl(tmp_path: Path) -> None:
    paths = ScopePaths.for_request(
        tmp_path, normalize_request("ICML", 2026, "main")
    )

    assert paths.manifest == tmp_path / "data/manifests/icml/2026-main.json"
    assert paths.normalized == tmp_path / "data/normalized/icml/2026-main.jsonl"
    assert paths.snapshots == tmp_path / "data/snapshots/icml/2026-main"
    assert paths.analysis == tmp_path / "data/analysis/icml/2026-main"
    assert paths.release == tmp_path / "data/releases/ICML/2026"
    assert paths.notes == tmp_path / "notes/icml-2026-main-overview.md"


def test_scope_paths_reject_unsafe_segments(tmp_path: Path) -> None:
    request = normalize_request("ICML", 2026, "main").model_copy(
        update={"track": "../main"}
    )

    with pytest.raises(ValueError, match="safe scope segment"):
        ScopePaths.for_request(tmp_path, request)
