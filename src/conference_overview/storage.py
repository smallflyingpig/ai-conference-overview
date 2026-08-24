import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from conference_overview.models import SourceRef


def _atomic_write(path: Path, data: bytes) -> None:
    """Write bytes to a sibling temporary file, then atomically replace path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(data)
        temporary_path.replace(path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def store_snapshot(data: bytes, source_url: str, root: Path) -> SourceRef:
    """Store an immutable content-addressed source snapshot and provenance manifest."""
    sha256 = hashlib.sha256(data).hexdigest()
    snapshot_relative_path = Path("raw") / f"{sha256}.bin"
    snapshot_path = root / snapshot_relative_path
    _atomic_write(snapshot_path, data)

    retrieved_at = datetime.now(UTC)
    manifest = {
        "source_url": source_url,
        "retrieved_at": retrieved_at.isoformat(),
        "sha256": sha256,
        "byte_size": len(data),
        "snapshot_path": snapshot_relative_path.as_posix(),
    }
    manifest_path = root / "manifests" / f"{sha256}.json"
    _atomic_write(
        manifest_path,
        json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )

    hostname = urlparse(source_url).netloc or source_url
    return SourceRef(
        name=hostname,
        url=source_url,
        retrieved_at=retrieved_at,
        sha256=sha256,
    )
