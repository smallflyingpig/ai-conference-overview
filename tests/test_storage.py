import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from conference_overview.storage import store_snapshot


def test_snapshot_path_is_content_addressed(tmp_path: Path) -> None:
    data = b"paper-data"

    ref = store_snapshot(data, "https://example.test/volume.bib", tmp_path)

    assert ref.sha256 == hashlib.sha256(data).hexdigest()
    assert (tmp_path / "raw" / f"{ref.sha256}.bin").read_bytes() == data


def test_snapshot_records_manifest_with_provenance(tmp_path: Path) -> None:
    data = b"paper-data"
    source_url = "https://example.test/volume.bib"

    ref = store_snapshot(data, source_url, tmp_path)
    manifest_path = tmp_path / "manifests" / f"{ref.sha256}.json"
    manifest = json.loads(manifest_path.read_text())

    assert manifest["source_url"] == source_url
    assert manifest["sha256"] == hashlib.sha256(data).hexdigest()
    assert manifest["byte_size"] == len(data)
    assert manifest["snapshot_path"] == f"raw/{ref.sha256}.bin"
    assert datetime.fromisoformat(manifest["retrieved_at"]).tzinfo == UTC
    assert ref.retrieved_at == datetime.fromisoformat(manifest["retrieved_at"])


def test_snapshot_reuses_its_content_addressed_location(tmp_path: Path) -> None:
    first = store_snapshot(b"paper-data", "https://example.test/first.bib", tmp_path)
    second = store_snapshot(b"paper-data", "https://example.test/second.bib", tmp_path)

    assert first.sha256 == second.sha256
    assert list((tmp_path / "raw").iterdir()) == [
        tmp_path / "raw" / f"{first.sha256}.bin"
    ]
