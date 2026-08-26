import json
from pathlib import Path

import httpx
import pytest

from conference_overview import conference_pipeline
from conference_overview.conference_pipeline import (
    collect_scope,
    rebuild_scope_from_snapshots,
    validate_scope,
)
from conference_overview.registry import normalize_request

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "icml"


def icml_client() -> httpx.Client:
    first = (FIXTURE_DIR / "events-page-1.json").read_bytes()
    second = (FIXTURE_DIR / "events-page-2.json").read_bytes()
    abstracts = (FIXTURE_DIR / "abstracts.json").read_bytes()
    openreview = (FIXTURE_DIR / "openreview-accepted.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url.endswith("icml-2026-orals-posters.json"):
            return httpx.Response(200, content=first, request=request)
        if url == "https://icml.cc/api/miniconf/events?offset=2":
            return httpx.Response(200, content=second, request=request)
        if url.endswith("icml-2026-abstracts.json"):
            return httpx.Response(200, content=abstracts, request=request)
        if url.startswith("https://api2.openreview.net/notes?"):
            return httpx.Response(200, content=openreview, request=request)
        raise AssertionError(f"unexpected request: {url}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_collect_scope_preserves_acl_dispatch(tmp_path: Path, monkeypatch) -> None:
    expected = object()
    monkeypatch.setattr(
        conference_pipeline, "collect_acl_scope", lambda *_args, **_kwargs: expected
    )

    assert collect_scope(normalize_request("ACL", 2026, "long"), tmp_path) is expected


def test_collect_icml_persists_sources_and_reconciled_records(
    tmp_path: Path,
) -> None:
    request = normalize_request("ICML", 2026, "main")
    with icml_client() as client:
        result = collect_scope(request, tmp_path, client=client)
    manifest = json.loads(result.manifest_path.read_text())

    assert manifest["schema_version"] == "conference-collection-manifest-v1"
    assert manifest["scope"] == {"venue": "ICML", "year": 2026, "track": "main"}
    assert manifest["publication_status"] == "preliminary_official_program"
    assert manifest["counts"] == {
        "discovered": 5,
        "duplicate_candidates": 0,
        "excluded": 2,
        "included": 3,
        "unresolved": 0,
        "presentation_rows": 4,
    }
    assert all(
        Path(item["snapshot_path"]).is_relative_to(
            "data/snapshots/icml/2026-main"
        )
        for item in manifest["sources"]
    )


def test_rebuild_rejects_modified_snapshot_before_writing_normalized(
    tmp_path: Path,
) -> None:
    request = normalize_request("ICML", 2026, "main")
    with icml_client() as client:
        result = collect_scope(request, tmp_path, client=client)
    manifest = json.loads(result.manifest_path.read_text())
    snapshot = tmp_path / manifest["sources"][0]["snapshot_path"]
    snapshot.write_bytes(snapshot.read_bytes() + b"x")
    normalized_before = result.normalized_path.read_bytes()

    with pytest.raises(ValueError, match="snapshot"):
        rebuild_scope_from_snapshots(request, tmp_path)
    assert result.normalized_path.read_bytes() == normalized_before


def test_validate_rejects_manifest_count_mutation(tmp_path: Path) -> None:
    request = normalize_request("ICML", 2026, "main")
    with icml_client() as client:
        result = collect_scope(request, tmp_path, client=client)
    manifest = json.loads(result.manifest_path.read_text())
    manifest["counts"]["included"] = 4
    result.manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="count"):
        validate_scope(request, tmp_path)
