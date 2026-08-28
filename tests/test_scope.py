from pathlib import Path

import pytest

from conference_overview.registry import normalize_request
from conference_overview.scope import ScopePaths, release_relative_parts


def test_icml_paths_are_isolated_from_acl(tmp_path: Path) -> None:
    paths = ScopePaths.for_request(
        tmp_path, normalize_request("ICML", 2026, "main")
    )

    assert paths.manifest == tmp_path / "data/manifests/icml/2026-main.json"
    assert paths.normalized == tmp_path / "data/normalized/icml/2026-main.jsonl"
    assert paths.snapshots == tmp_path / "data/snapshots/icml/2026-main"
    assert paths.analysis == tmp_path / "data/analysis/icml/2026-main"
    assert paths.classification == tmp_path / "data/classification/icml/2026-main"
    assert paths.awards == tmp_path / "data/awards/icml/2026-main.yaml"
    assert (
        paths.award_deep_reads
        == tmp_path / "data/awards/icml/2026-main-deep-reads.yaml"
    )
    assert (
        paths.award_deep_read_provenance
        == tmp_path / "data/awards/icml/2026-main-deep-read-provenance.json"
    )
    assert (
        paths.low_confidence_queue
        == tmp_path
        / "data/classification/icml/2026-main/low-confidence-review-queue.json"
    )
    assert (
        paths.low_confidence_decisions
        == tmp_path
        / "data/classification/icml/2026-main/low-confidence-decisions.json"
    )
    assert paths.release == tmp_path / "data/releases/ICML/2026"
    assert paths.notes == tmp_path / "notes/icml-2026-main-overview.md"


def test_scope_paths_reject_unsafe_segments(tmp_path: Path) -> None:
    request = normalize_request("ICML", 2026, "main").model_copy(
        update={"track": "../main"}
    )

    with pytest.raises(ValueError, match="safe scope segment"):
        ScopePaths.for_request(tmp_path, request)


def test_acl_default_and_findings_release_paths_are_isolated(tmp_path: Path) -> None:
    long_request = normalize_request("ACL", 2026, "long")
    findings_request = normalize_request("ACL", 2026, "findings")

    assert release_relative_parts(long_request) == ("ACL", "2026")
    assert release_relative_parts(findings_request) == (
        "ACL",
        "2026",
        "tracks",
        "findings",
    )
    assert ScopePaths.for_request(root=tmp_path, request=long_request).release == (
        tmp_path / "data/releases/ACL/2026"
    )
    assert ScopePaths.for_request(
        root=tmp_path, request=findings_request
    ).release == tmp_path / "data/releases/ACL/2026/tracks/findings"
