import hashlib
import json
from pathlib import Path

import httpx
import pytest

from conference_overview.conference_pipeline import (
    build_preliminary_release,
    collect_scope,
)
from conference_overview.registry import normalize_request
from scripts.verify_icml_live_release import (
    VerificationError,
    capture_acl_baseline,
    verify_icml_live_release,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "icml"
ARTIFACT_NAMES = {
    "overview.json",
    "overview.md",
    "papers.csv",
    "papers.json",
    "provenance.json",
    "validation.json",
}


def _write_fake_acl_release(root: Path) -> None:
    release = root / "data/releases/ACL/2026"
    generation = release / "generations" / ("a" * 64)
    generation.mkdir(parents=True)
    hashes = {}
    for name in sorted(ARTIFACT_NAMES):
        data = f"acl fixture: {name}\n".encode()
        (generation / name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    (release / "current.json").write_text(
        json.dumps(
            {
                "artifact_sha256": hashes,
                "generation": f"generations/{'a' * 64}",
            }
        )
    )


def _icml_client() -> httpx.Client:
    payloads = {
        "icml-2026-orals-posters.json": (FIXTURE_DIR / "events-page-1.json").read_bytes(),
        "events?offset=2": (FIXTURE_DIR / "events-page-2.json").read_bytes(),
        "icml-2026-abstracts.json": (FIXTURE_DIR / "abstracts.json").read_bytes(),
    }
    openreview = (FIXTURE_DIR / "openreview-accepted.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for suffix, data in payloads.items():
            if url.endswith(suffix):
                return httpx.Response(200, content=data, request=request)
        if url.startswith("https://api2.openreview.net/notes?"):
            return httpx.Response(200, content=openreview, request=request)
        raise AssertionError(f"unexpected request: {url}")

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_live_verifier_requires_selected_icml_release(tmp_path: Path) -> None:
    _write_fake_acl_release(tmp_path)
    baseline = capture_acl_baseline(tmp_path)

    with pytest.raises(VerificationError, match="ICML release"):
        verify_icml_live_release(tmp_path, baseline)


def test_live_verifier_recomputes_release_manifest_and_routes(tmp_path: Path) -> None:
    _write_fake_acl_release(tmp_path)
    baseline = capture_acl_baseline(tmp_path)
    request = normalize_request("ICML", 2026, "main")
    with _icml_client() as client:
        collect_scope(request, tmp_path, client=client)
    build_preliminary_release(request, tmp_path, write_release=True)

    result = verify_icml_live_release(tmp_path, baseline)

    assert result["paper_count"] == 3
    assert result["route_count"] == 3
    assert result["missing_abstract_count"] == 1
    assert result["missing_pdf_count"] == 0


def test_live_verifier_rejects_changed_acl_pointer(tmp_path: Path) -> None:
    _write_fake_acl_release(tmp_path)
    baseline = capture_acl_baseline(tmp_path)
    pointer = tmp_path / "data/releases/ACL/2026/current.json"
    pointer.write_bytes(pointer.read_bytes() + b"\n")

    with pytest.raises(VerificationError, match="ACL current pointer"):
        verify_icml_live_release(tmp_path, baseline)
