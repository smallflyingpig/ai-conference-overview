"""Independently verify the selected ICML preliminary release and ACL baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ARTIFACT_NAMES = {
    "papers.json",
    "papers.csv",
    "overview.json",
    "overview.md",
    "validation.json",
    "provenance.json",
}
EXPECTED_AVAILABILITY = {
    "papers": True,
    "distribution": False,
    "trends": False,
    "advances": False,
    "awards": False,
}
SHA256_LENGTH = 64


class VerificationError(RuntimeError):
    """Raised when a live-release invariant is not satisfied."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON artifact: {path}") from exc


def _safe_child(root: Path, relative: str, label: str) -> Path:
    relative_path = Path(relative)
    current = root
    for part in relative_path.parts:
        current /= part
        if current.is_symlink():
            raise VerificationError(f"{label} contains a symlink")
    candidate = current.resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise VerificationError(f"{label} leaves repository root") from exc
    if candidate.is_symlink() or not candidate.is_file():
        raise VerificationError(f"{label} is missing or unsafe")
    return candidate


def _release_inventory(root: Path, venue: str, year: int) -> dict[str, Any]:
    release = root / "data" / "releases" / venue / str(year)
    pointer_path = release / "current.json"
    if pointer_path.is_symlink() or not pointer_path.is_file():
        raise VerificationError(f"selected {venue} release is unavailable")
    pointer_bytes = pointer_path.read_bytes()
    pointer = _read_json(pointer_path)
    if not isinstance(pointer, Mapping):
        raise VerificationError(f"{venue} release pointer is not an object")
    generation_name = pointer.get("generation")
    hashes = pointer.get("artifact_sha256")
    if (
        not isinstance(generation_name, str)
        or not generation_name.startswith("generations/")
        or len(generation_name.removeprefix("generations/")) != SHA256_LENGTH
        or any(
            char not in "0123456789abcdef"
            for char in generation_name.removeprefix("generations/")
        )
        or not isinstance(hashes, Mapping)
        or set(hashes) != ARTIFACT_NAMES
    ):
        raise VerificationError(f"{venue} release pointer is invalid")
    generation = (release / generation_name).resolve()
    generations_root = (release / "generations").resolve()
    try:
        generation.relative_to(generations_root)
    except ValueError as exc:
        raise VerificationError(f"{venue} generation leaves its release root") from exc
    if generation.is_symlink() or not generation.is_dir():
        raise VerificationError(f"{venue} release generation is unavailable")
    if {path.name for path in generation.iterdir()} != ARTIFACT_NAMES:
        raise VerificationError(f"{venue} generation does not contain exactly six artifacts")
    actual_hashes: dict[str, str] = {}
    for name in sorted(ARTIFACT_NAMES):
        artifact = generation / name
        if artifact.is_symlink() or not artifact.is_file():
            raise VerificationError(f"unsafe {venue} release artifact: {name}")
        actual_hashes[name] = _sha256(artifact.read_bytes())
    if dict(hashes) != actual_hashes:
        raise VerificationError(f"{venue} release artifact hash mismatch")
    return {
        "pointer_sha256": _sha256(pointer_bytes),
        "generation": generation_name,
        "artifact_sha256": actual_hashes,
        "generation_path": generation,
    }


def capture_acl_baseline(root: Path) -> dict[str, Any]:
    inventory = _release_inventory(root.resolve(), "ACL", 2026)
    return {
        "schema_version": "icml-import-acl-baseline-v1",
        "pointer_sha256": inventory["pointer_sha256"],
        "generation": inventory["generation"],
        "artifact_sha256": inventory["artifact_sha256"],
    }


def _verify_acl_unchanged(root: Path, baseline: Mapping[str, Any]) -> None:
    if baseline.get("schema_version") != "icml-import-acl-baseline-v1":
        raise VerificationError("ACL baseline schema is unsupported")
    current = capture_acl_baseline(root)
    if current["pointer_sha256"] != baseline.get("pointer_sha256"):
        raise VerificationError("ACL current pointer changed during ICML import")
    if current != dict(baseline):
        raise VerificationError("ACL selected release changed during ICML import")


def _verify_manifest(root: Path, papers: list[dict[str, Any]]) -> dict[str, Any]:
    manifest_path = root / "data/manifests/icml/2026-main.json"
    manifest = _read_json(manifest_path)
    if not isinstance(manifest, Mapping):
        raise VerificationError("ICML collection manifest is not an object")
    if manifest.get("scope") != {"venue": "ICML", "year": 2026, "track": "main"}:
        raise VerificationError("ICML collection manifest has the wrong scope")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        raise VerificationError("ICML collection manifest has no sources")
    for index, item in enumerate(sources):
        if not isinstance(item, Mapping) or item.get("page_index") != index:
            raise VerificationError("ICML source page order is invalid")
        snapshot = _safe_child(root, str(item.get("snapshot_path")), "ICML snapshot")
        data = snapshot.read_bytes()
        if len(data) != item.get("byte_size") or _sha256(data) != item.get("sha256"):
            raise VerificationError("ICML snapshot hash or byte size mismatch")
    normalized = manifest.get("normalized")
    if not isinstance(normalized, Mapping):
        raise VerificationError("ICML normalized artifact is missing from manifest")
    normalized_path = _safe_child(root, str(normalized.get("path")), "ICML normalized JSONL")
    normalized_bytes = normalized_path.read_bytes()
    if _sha256(normalized_bytes) != normalized.get("sha256"):
        raise VerificationError("ICML normalized JSONL hash mismatch")
    try:
        records = [json.loads(line) for line in normalized_bytes.decode().splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError("ICML normalized JSONL is invalid") from exc
    included = [item for item in records if item.get("status") in {"complete", "partial"}]
    excluded = [item for item in records if item.get("status") == "excluded"]
    unresolved = [item for item in records if item.get("status") == "unresolved"]
    counts = manifest.get("counts")
    if not isinstance(counts, Mapping):
        raise VerificationError("ICML manifest counts are missing")
    expected_counts = {
        "discovered": len(records),
        "included": len(included),
        "excluded": len(excluded),
        "unresolved": len(unresolved),
    }
    if any(counts.get(name) != value for name, value in expected_counts.items()):
        raise VerificationError("ICML manifest counts disagree with normalized records")
    if counts.get("duplicate_candidates") != 0 or unresolved:
        raise VerificationError("ICML collection contains unresolved or duplicate candidates")
    if {item.get("paper_id") for item in included} != {
        item.get("paper_id") for item in papers
    }:
        raise VerificationError("ICML release papers differ from normalized included records")
    return {"source_count": len(sources), **expected_counts}


def verify_icml_live_release(
    root: Path, baseline: Mapping[str, Any]
) -> dict[str, Any]:
    root = root.resolve()
    _verify_acl_unchanged(root, baseline)
    try:
        inventory = _release_inventory(root, "ICML", 2026)
    except VerificationError as exc:
        raise VerificationError("selected ICML release is unavailable") from exc
    generation = inventory["generation_path"]
    papers = _read_json(generation / "papers.json")
    overview = _read_json(generation / "overview.json")
    validation = _read_json(generation / "validation.json")
    provenance = _read_json(generation / "provenance.json")
    if not isinstance(papers, list) or not all(isinstance(item, dict) for item in papers):
        raise VerificationError("ICML papers artifact is invalid")
    if not all(isinstance(item, Mapping) for item in (overview, validation, provenance)):
        raise VerificationError("ICML release metadata is invalid")
    context = overview.get("publication_context")
    if not isinstance(context, Mapping):
        raise VerificationError("ICML release has no publication context")
    if context.get("status") != "preliminary_official_program":
        raise VerificationError("ICML release is not marked preliminary")
    if context.get("analysis_availability") != EXPECTED_AVAILABILITY:
        raise VerificationError("ICML preliminary analysis availability is invalid")
    if provenance.get("publication_context") != context:
        raise VerificationError("ICML publication context differs across artifacts")
    paper_ids = [item.get("paper_id") for item in papers]
    if len(paper_ids) != len(set(paper_ids)):
        raise VerificationError("ICML release contains duplicate paper IDs")
    if not all(
        item.get("venue") == "ICML"
        and item.get("year") == 2026
        and item.get("track") == "main"
        and isinstance(item.get("native_metadata"), Mapping)
        and item["native_metadata"].get("openreview_venueid")
        == "ICML.cc/2026/Conference"
        for item in papers
    ):
        raise VerificationError("ICML release contains an out-of-scope paper")
    if not (
        len(papers) == validation.get("included_count") == overview.get("paper_count")
    ):
        raise VerificationError("ICML release paper counts disagree")
    missing_abstract_ids = sorted(
        item["paper_id"] for item in papers if not item.get("abstract")
    )
    missing_pdf_ids = sorted(
        item["paper_id"] for item in papers if not item.get("pdf_url")
    )
    if (
        validation.get("missing_abstract_ids") != missing_abstract_ids
        or validation.get("missing_abstract_count") != len(missing_abstract_ids)
        or validation.get("missing_pdf_ids") != missing_pdf_ids
        or validation.get("missing_pdf_count") != len(missing_pdf_ids)
    ):
        raise VerificationError("ICML missing-field counts disagree")
    route_keys = [
        f"paper-{hashlib.sha256(str(paper_id).encode()).hexdigest()}"
        for paper_id in paper_ids
    ]
    if len(route_keys) != len(set(route_keys)):
        raise VerificationError("ICML paper route keys are not unique")
    manifest_summary = _verify_manifest(root, papers)
    return {
        "generation": inventory["generation"],
        "paper_count": len(papers),
        "route_count": len(route_keys),
        "missing_abstract_count": len(missing_abstract_ids),
        "missing_pdf_count": len(missing_pdf_ids),
        **manifest_summary,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--write-acl-baseline", type=Path)
    modes.add_argument("--acl-baseline", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.write_acl_baseline is not None:
            baseline = capture_acl_baseline(args.root)
            args.write_acl_baseline.write_text(
                json.dumps(baseline, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(json.dumps({"status": "baseline_written", **baseline}, sort_keys=True))
            return 0
        if args.acl_baseline is None:
            raise VerificationError("--acl-baseline is required for live verification")
        baseline = _read_json(args.acl_baseline)
        if not isinstance(baseline, Mapping):
            raise VerificationError("ACL baseline is not an object")
        result = verify_icml_live_release(args.root, baseline)
        print(json.dumps({"status": "verified", **result}, sort_keys=True))
        return 0
    except VerificationError as exc:
        print(json.dumps({"status": "failed", "detail": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
