"""Deterministic source export and immutable Chinese content publication."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from conference_overview.chinese_content import (
    AwardDeepReadZh,
    ChineseContentBundle,
    ContentManifest,
    ContentPointer,
    ContentPublicationBlocked,
    PaperSummaryZh,
    validate_chinese_content_bundle,
)
from conference_overview.models import PaperRecord
from conference_overview.reports import resolve_current_release

_ARTIFACT_NAMES = (
    "paper-summaries.zh.jsonl",
    "award-deep-reads.zh.jsonl",
    "content-manifest.json",
)
_DATA_ARTIFACT_NAMES = _ARTIFACT_NAMES[:2]
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_ACL_NUMERIC_SUFFIX = re.compile(r"\.(\d+)$")


@dataclass(frozen=True)
class OfficialPdfSource:
    """Verified official PDF bytes represented without retaining the bytes."""

    byte_size: int
    sha256: str
    text: str


@dataclass(frozen=True)
class ContentSourceCoverage:
    """Observed ID coverage in deterministic source shards."""

    ordinary_count: int
    award_count: int
    total_count: int


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _canonical_jsonl_bytes(values: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(_canonical_json_bytes(value) for value in values)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _numeric_suffix(paper_id: str) -> int:
    match = _ACL_NUMERIC_SUFFIX.search(paper_id)
    if match is None:
        raise ContentPublicationBlocked(
            f"paper ID has no ACL numeric suffix: {paper_id}"
        )
    return int(match.group(1))


def _paper_order_key(paper_id: str) -> tuple[int, int | str]:
    match = _ACL_NUMERIC_SUFFIX.search(paper_id)
    if match is not None:
        return (0, int(match.group(1)))
    return (1, paper_id)


def _paper_shard_index(paper_id: str, shard_count: int) -> int:
    match = _ACL_NUMERIC_SUFFIX.search(paper_id)
    if match is not None:
        return int(match.group(1)) % shard_count
    return int(_sha256(paper_id.encode("utf-8"))[:16], 16) % shard_count


def extract_official_pdf_source(
    pdf_bytes: bytes, *, expected_length: int
) -> OfficialPdfSource:
    """Check complete PDF bytes and extract normalized text for authoring."""
    if (
        type(expected_length) is not int
        or expected_length <= 0
        or len(pdf_bytes) != expected_length
        or not pdf_bytes.startswith(b"%PDF")
        or not pdf_bytes.rstrip().endswith(b"%%EOF")
    ):
        raise ContentPublicationBlocked("official PDF bytes are truncated or invalid")
    try:
        reader = PdfReader(BytesIO(pdf_bytes), strict=True)
        text = " ".join(
            " ".join((page.extract_text() or "").split()) for page in reader.pages
        ).strip()
    except (PdfReadError, OSError, TypeError, ValueError) as exc:
        raise ContentPublicationBlocked("official PDF cannot be parsed") from exc
    if not text:
        raise ContentPublicationBlocked("official PDF yielded no source text")
    return OfficialPdfSource(
        byte_size=len(pdf_bytes),
        sha256=_sha256(pdf_bytes),
        text=text,
    )


def _fetch_official_pdf_source(url: str) -> OfficialPdfSource:
    hostname = urlparse(url).hostname
    if hostname != "aclanthology.org":
        raise ContentPublicationBlocked("ordinary PDF source is not ACL Anthology")
    try:
        response = httpx.get(url, follow_redirects=True, timeout=60)
        response.raise_for_status()
        content_length = response.headers.get("content-length")
        expected_length = int(content_length) if content_length is not None else -1
    except (httpx.HTTPError, ValueError) as exc:
        raise ContentPublicationBlocked("official PDF download failed") from exc
    return extract_official_pdf_source(
        response.content, expected_length=expected_length
    )


@dataclass(frozen=True)
class _ReleaseContentContext:
    papers: tuple[PaperRecord, ...]
    award_ids: frozenset[str]
    award_deep_reads: dict[str, Mapping[str, object]]
    award_pdf_provenance: dict[str, Mapping[str, object]]
    release_generation: str
    papers_sha256: str


def _require_supported_scope(request) -> None:
    scope = (request.venue, request.year, request.track, request.source_key)
    if scope not in {
        ("ACL", 2026, "long", "2026.acl-long"),
        ("ICML", 2025, "main", "pmlr-v267"),
    }:
        raise ContentPublicationBlocked(
            "Chinese content is not implemented for this conference scope"
        )


def _load_release_content_context(request, root: Path) -> _ReleaseContentContext:
    _require_supported_scope(request)
    release_root = root / f"data/releases/{request.venue}/{request.year}"
    generation = resolve_current_release(release_root)
    pointer = json.loads((release_root / "current.json").read_text(encoding="utf-8"))
    papers_bytes = (generation / "papers.json").read_bytes()
    overview = json.loads((generation / "overview.json").read_text(encoding="utf-8"))
    papers = tuple(
        PaperRecord.model_validate(item) for item in json.loads(papers_bytes)
    )
    awards = overview.get("awards")
    deep_reads = overview.get("award_deep_reads")
    if not isinstance(awards, list) or not isinstance(deep_reads, list):
        raise ContentPublicationBlocked("release award content is unavailable")
    award_ids = frozenset(
        str(item["paper_id"])
        for item in awards
        if isinstance(item, Mapping) and item.get("status") == "verified"
    )
    deep_read_by_id = {
        str(item["paper_id"]): item
        for item in deep_reads
        if isinstance(item, Mapping) and isinstance(item.get("paper_id"), str)
    }
    try:
        provenance_path = (
            root / "data/awards/acl/2026-long-deep-read-provenance.json"
            if request.venue == "ACL"
            else root / "data/awards/icml/2025-main-deep-read-provenance.json"
        )
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContentPublicationBlocked("award PDF provenance is unavailable") from exc
    pdfs = provenance.get("pdfs") if isinstance(provenance, Mapping) else None
    if not isinstance(pdfs, list):
        raise ContentPublicationBlocked("award PDF provenance is invalid")
    pdf_by_id: dict[str, Mapping[str, object]] = {}
    for item in pdfs:
        if not isinstance(item, Mapping) or not isinstance(item.get("paper_id"), str):
            raise ContentPublicationBlocked("award PDF provenance is invalid")
        paper_id = str(item["paper_id"])
        pdf_by_id[paper_id] = {
            "byte_size": item.get("byte_size"),
            "pdf_url": item.get("source_url"),
            "sha256": item.get("sha256"),
        }
    if set(deep_read_by_id) != set(award_ids) or set(pdf_by_id) != set(award_ids):
        raise ContentPublicationBlocked("award source ID coverage is invalid")
    generation_value = pointer.get("generation")
    if not isinstance(generation_value, str):
        raise ContentPublicationBlocked("release generation pointer is invalid")
    return _ReleaseContentContext(
        papers=papers,
        award_ids=award_ids,
        award_deep_reads=deep_read_by_id,
        award_pdf_provenance=pdf_by_id,
        release_generation=generation_value,
        papers_sha256=_sha256(papers_bytes),
    )


def _content_root(root: Path, request) -> Path:
    return root / f"data/content/{request.venue.lower()}/{request.year}-{request.track}"


def export_chinese_content_scope(
    request, root: Path, *, shard_count: int = 16
) -> list[Path]:
    """Export the current ACL release into deterministic authoring batches."""
    context = _load_release_content_context(request, root)
    ordinary_pdf_sources: dict[str, OfficialPdfSource] = {}
    for paper in context.papers:
        if paper.paper_id in context.award_ids or paper.abstract is not None:
            continue
        if paper.pdf_url is None:
            raise ContentPublicationBlocked(
                f"paper has neither abstract nor PDF: {paper.paper_id}"
            )
        ordinary_pdf_sources[paper.paper_id] = _fetch_official_pdf_source(
            str(paper.pdf_url)
        )
    return export_chinese_content_sources(
        papers=context.papers,
        award_ids=set(context.award_ids),
        award_deep_reads=context.award_deep_reads,
        award_pdf_provenance=context.award_pdf_provenance,
        ordinary_pdf_sources=ordinary_pdf_sources,
        output_dir=_content_root(root, request) / "source-batches",
        shard_count=shard_count,
    )


def check_chinese_content_sources_scope(request, root: Path) -> ContentSourceCoverage:
    """Check exact source-shard membership against the selected release."""
    context = _load_release_content_context(request, root)
    source_root = _content_root(root, request) / "source-batches"
    ordinary_paths = sorted(source_root.glob("paper-summary-source-*.jsonl"))
    award_path = source_root / "award-deep-read-source.jsonl"
    if len(ordinary_paths) != 16 or not award_path.is_file():
        raise ContentPublicationBlocked("Chinese content source shards are incomplete")
    ordinary_rows = [
        row
        for path in ordinary_paths
        for row in _read_jsonl_objects(path)
    ]
    award_rows = _read_jsonl_objects(award_path)
    ordinary_ids = [str(row.get("paper_id")) for row in ordinary_rows]
    award_ids = [str(row.get("paper_id")) for row in award_rows]
    if len(set(ordinary_ids)) != len(ordinary_ids) or len(set(award_ids)) != len(
        award_ids
    ):
        raise ContentPublicationBlocked("Chinese content source IDs are duplicated")
    expected = {paper.paper_id for paper in context.papers}
    if (
        set(award_ids) != set(context.award_ids)
        or set(ordinary_ids) != expected.difference(context.award_ids)
    ):
        raise ContentPublicationBlocked("Chinese content source ID coverage is invalid")
    return ContentSourceCoverage(
        ordinary_count=len(ordinary_ids),
        award_count=len(award_ids),
        total_count=len(ordinary_ids) + len(award_ids),
    )


def _safe_output_directory(output_dir: Path) -> Path:
    requested = Path(output_dir)
    if requested.is_symlink():
        raise ContentPublicationBlocked("content output path must not be a symlink")
    absolute = requested.absolute()
    absolute.parent.mkdir(parents=True, exist_ok=True)
    output = absolute.parent.resolve(strict=True) / absolute.name
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ContentPublicationBlocked("content output path is unsafe")
    output.mkdir(parents=True, exist_ok=True)
    return output


def export_chinese_content_sources(
    *,
    papers: Sequence[PaperRecord],
    award_ids: set[str],
    award_deep_reads: Mapping[str, Mapping[str, object]],
    award_pdf_provenance: Mapping[str, Mapping[str, object]],
    ordinary_pdf_sources: Mapping[str, OfficialPdfSource] | None = None,
    output_dir: Path,
    shard_count: int = 16,
) -> list[Path]:
    """Export deterministic ordinary-paper shards and one award source batch."""
    if shard_count < 1:
        raise ValueError("shard_count must be positive")
    paper_by_id = {paper.paper_id: paper for paper in papers}
    if len(paper_by_id) != len(papers) or not award_ids.issubset(paper_by_id):
        raise ContentPublicationBlocked("source paper IDs are invalid")
    ordinary_pdf_sources = ordinary_pdf_sources or {}
    output = _safe_output_directory(output_dir)
    shards: list[list[dict[str, object]]] = [[] for _ in range(shard_count)]
    for paper in sorted(papers, key=lambda item: _paper_order_key(item.paper_id)):
        if paper.paper_id in award_ids:
            continue
        normalized_abstract = (
            " ".join(paper.abstract.split()) if paper.abstract is not None else ""
        )
        row: dict[str, object] = {
            "abstract": normalized_abstract or None,
            "authors": paper.authors,
            "content_method": "title-abstract-grounded-summary-v1",
            "landing_url": str(paper.landing_url),
            "paper_id": paper.paper_id,
            "pdf_url": str(paper.pdf_url) if paper.pdf_url is not None else None,
            "source_abstract_sha256": (
                _sha256(normalized_abstract.encode("utf-8"))
                if normalized_abstract
                else None
            ),
            "title": paper.title,
            "track": paper.track,
            "venue": paper.venue,
            "year": paper.year,
        }
        if not normalized_abstract:
            pdf_source = ordinary_pdf_sources.get(paper.paper_id)
            if pdf_source is None or not pdf_source.text.strip():
                raise ContentPublicationBlocked(
                    f"paper requires an official PDF source: {paper.paper_id}"
                )
            row.update(
                {
                    "content_method": "official-pdf-grounded-summary-v1",
                    "source_pdf_byte_size": pdf_source.byte_size,
                    "source_pdf_sha256": pdf_source.sha256,
                    "source_text": pdf_source.text,
                }
            )
        shards[_paper_shard_index(paper.paper_id, shard_count)].append(row)

    paths: list[Path] = []
    width = max(2, len(str(shard_count - 1)))
    for index, rows in enumerate(shards):
        path = output / f"paper-summary-source-{index:0{width}d}.jsonl"
        path.write_bytes(_canonical_jsonl_bytes(rows))
        paths.append(path)

    award_rows: list[dict[str, object]] = []
    for paper_id in sorted(award_ids, key=_paper_order_key):
        deep_read = award_deep_reads.get(paper_id)
        provenance = award_pdf_provenance.get(paper_id)
        if deep_read is None or provenance is None:
            raise ContentPublicationBlocked(
                f"award source is incomplete: {paper_id}"
            )
        sha256 = provenance.get("sha256")
        byte_size = provenance.get("byte_size")
        pdf_url = provenance.get("pdf_url")
        if (
            not isinstance(sha256, str)
            or _SHA256_PATTERN.fullmatch(sha256) is None
            or type(byte_size) is not int
            or byte_size <= 0
            or not isinstance(pdf_url, str)
            or not pdf_url.strip()
        ):
            raise ContentPublicationBlocked(
                f"award PDF provenance is invalid: {paper_id}"
            )
        paper = paper_by_id[paper_id]
        award_rows.append(
            {
                "authors": paper.authors,
                "deep_read": dict(deep_read),
                "landing_url": str(paper.landing_url),
                "paper_id": paper_id,
                "pdf_byte_size": byte_size,
                "pdf_url": pdf_url,
                "source_pdf_sha256": sha256,
                "title": paper.title,
            }
        )
    award_path = output / "award-deep-read-source.jsonl"
    award_path.write_bytes(_canonical_jsonl_bytes(award_rows))
    paths.append(award_path)
    return paths


def _read_jsonl_objects(path: Path) -> list[dict[str, object]]:
    if path.is_symlink() or not path.is_file():
        raise ContentPublicationBlocked(f"JSONL source is unsafe: {path}")
    values: list[dict[str, object]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContentPublicationBlocked(
                f"invalid JSONL source at {path}:{line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise ContentPublicationBlocked(
                f"JSONL source row is not an object at {path}:{line_number}"
            )
        values.append(value)
    return values


def _read_jsonl_models(path: Path, model_type):
    if path.is_symlink() or not path.is_file():
        raise ContentPublicationBlocked(f"authored content file is unsafe: {path}")
    parsed = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            parsed.append(model_type.model_validate_json(line))
        except ValidationError as exc:
            raise ContentPublicationBlocked(
                f"invalid authored content at {path}:{line_number}"
            ) from exc
    return parsed


def load_authored_content(
    *,
    summary_files: Sequence[Path],
    award_path: Path,
    papers: Sequence[PaperRecord],
    award_ids: set[str],
    release_generation: str,
    papers_sha256: str,
    award_pdf_sha256: Mapping[str, str],
    award_source_text: Mapping[str, str],
    allow_incomplete: bool,
    ordinary_pdf_sha256: Mapping[str, str] | None = None,
    ordinary_pdf_source_text: Mapping[str, str] | None = None,
) -> ChineseContentBundle:
    """Load authored JSONL and validate it against authoritative paper sources."""
    summaries = [
        summary
        for path in summary_files
        for summary in _read_jsonl_models(path, PaperSummaryZh)
    ]
    award_deep_reads = _read_jsonl_models(award_path, AwardDeepReadZh)
    if allow_incomplete:
        selected_ids = {
            summary.paper_id for summary in summaries
        } | {deep_read.paper_id for deep_read in award_deep_reads}
        selected_papers = [paper for paper in papers if paper.paper_id in selected_ids]
        if len(selected_papers) != len(selected_ids):
            raise ContentPublicationBlocked("authored content contains unknown paper IDs")
        selected_award_ids = award_ids.intersection(selected_ids)
        return validate_chinese_content_bundle(
            papers=selected_papers,
            award_ids=selected_award_ids,
            summaries=summaries,
            award_deep_reads=award_deep_reads,
            release_generation=release_generation,
            papers_sha256=papers_sha256,
            award_pdf_sha256={
                paper_id: value
                for paper_id, value in award_pdf_sha256.items()
                if paper_id in selected_ids
            },
            award_source_text={
                paper_id: value
                for paper_id, value in award_source_text.items()
                if paper_id in selected_ids
            },
            ordinary_pdf_sha256=ordinary_pdf_sha256,
            ordinary_pdf_source_text=ordinary_pdf_source_text,
        )
    return validate_chinese_content_bundle(
        papers=papers,
        award_ids=award_ids,
        summaries=summaries,
        award_deep_reads=award_deep_reads,
        release_generation=release_generation,
        papers_sha256=papers_sha256,
        award_pdf_sha256=award_pdf_sha256,
        award_source_text=award_source_text,
        ordinary_pdf_sha256=ordinary_pdf_sha256,
        ordinary_pdf_source_text=ordinary_pdf_source_text,
    )


def _source_bindings(
    root: Path, request, context: _ReleaseContentContext
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    award_pdf_sha256 = {
        paper_id: str(value["sha256"])
        for paper_id, value in context.award_pdf_provenance.items()
    }
    award_source_text = {
        paper_id: json.dumps(value, ensure_ascii=False, sort_keys=True)
        for paper_id, value in context.award_deep_reads.items()
    }
    ordinary_pdf_sha256: dict[str, str] = {}
    ordinary_pdf_source_text: dict[str, str] = {}
    for path in sorted(
        (_content_root(root, request) / "source-batches").glob(
            "paper-summary-source-*.jsonl"
        )
    ):
        for row in _read_jsonl_objects(path):
            if row.get("content_method") != "official-pdf-grounded-summary-v1":
                continue
            paper_id = row.get("paper_id")
            sha256 = row.get("source_pdf_sha256")
            source_text = row.get("source_text")
            if (
                not isinstance(paper_id, str)
                or not isinstance(sha256, str)
                or not isinstance(source_text, str)
            ):
                raise ContentPublicationBlocked("ordinary PDF source row is invalid")
            ordinary_pdf_sha256[paper_id] = sha256
            ordinary_pdf_source_text[paper_id] = source_text
    return (
        award_pdf_sha256,
        award_source_text,
        ordinary_pdf_sha256,
        ordinary_pdf_source_text,
    )


def import_chinese_content_scope(
    request,
    root: Path,
    *,
    summary_files: Sequence[Path],
    award_path: Path,
    allow_incomplete: bool,
) -> ChineseContentBundle:
    """Import authored files against the currently selected release."""
    context = _load_release_content_context(request, root)
    (
        award_pdf_sha256,
        award_source_text,
        ordinary_pdf_sha256,
        ordinary_pdf_source_text,
    ) = _source_bindings(root, request, context)
    return load_authored_content(
        summary_files=summary_files,
        award_path=award_path,
        papers=context.papers,
        award_ids=set(context.award_ids),
        release_generation=context.release_generation,
        papers_sha256=context.papers_sha256,
        award_pdf_sha256=award_pdf_sha256,
        award_source_text=award_source_text,
        ordinary_pdf_sha256=ordinary_pdf_sha256,
        ordinary_pdf_source_text=ordinary_pdf_source_text,
        allow_incomplete=allow_incomplete,
    )


def build_chinese_content_scope(request, root: Path) -> Path:
    """Validate all authored content and select one immutable generation."""
    authored = _content_root(root, request) / "authored"
    summaries = sorted(authored.glob("paper-summaries-*.zh.jsonl"))
    award_path = authored / "award-deep-reads.zh.jsonl"
    bundle = import_chinese_content_scope(
        request,
        root,
        summary_files=summaries,
        award_path=award_path,
        allow_incomplete=False,
    )
    return write_chinese_content_bundle(
        bundle,
        _content_root(root, request),
        generated_at=datetime.now(UTC),
    )


def _bundle_artifacts(
    bundle: ChineseContentBundle, generated_at: datetime
) -> dict[str, bytes]:
    try:
        parsed = ChineseContentBundle.model_validate(bundle.model_dump())
    except ValidationError as exc:
        raise ContentPublicationBlocked("invalid Chinese content bundle") from exc
    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ContentPublicationBlocked("content generated_at must be timezone-aware")
    if (
        parsed.ordinary_count != len(parsed.summaries)
        or parsed.award_count != len(parsed.award_deep_reads)
        or parsed.total_count != parsed.ordinary_count + parsed.award_count
    ):
        raise ContentPublicationBlocked("content counts contradict records")
    paper_bytes = _canonical_jsonl_bytes(
        [summary.model_dump(mode="json") for summary in parsed.summaries]
    )
    award_bytes = _canonical_jsonl_bytes(
        [deep_read.model_dump(mode="json") for deep_read in parsed.award_deep_reads]
    )
    data_artifacts = {
        "paper-summaries.zh.jsonl": paper_bytes,
        "award-deep-reads.zh.jsonl": award_bytes,
    }
    manifest = ContentManifest(
        schema_version="chinese-content-manifest-v1",
        release_generation=parsed.release_generation,
        papers_sha256=parsed.papers_sha256,
        generated_at=generated_at,
        ordinary_count=parsed.ordinary_count,
        award_count=parsed.award_count,
        total_count=parsed.total_count,
        artifact_sha256={
            name: _sha256(data) for name, data in data_artifacts.items()
        },
    )
    return {
        **data_artifacts,
        "content-manifest.json": _canonical_json_bytes(
            manifest.model_dump(mode="json")
        ),
    }


def _generation_digest(artifacts: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in _ARTIFACT_NAMES:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(artifacts[name])
        digest.update(b"\0")
    return digest.hexdigest()


def _verify_generation(generation: Path, artifacts: Mapping[str, bytes]) -> None:
    if generation.is_symlink() or not generation.is_dir():
        raise ContentPublicationBlocked("immutable content generation is unsafe")
    if sorted(path.name for path in generation.iterdir()) != sorted(_ARTIFACT_NAMES):
        raise ContentPublicationBlocked("immutable content artifact set is invalid")
    for name, expected in artifacts.items():
        path = generation / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
            raise ContentPublicationBlocked("immutable content bytes differ")


def _replace_pointer(output: Path, pointer: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(dir=output, prefix=".current-")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(pointer)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output / "current.json")
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_chinese_content_bundle(
    bundle: ChineseContentBundle,
    output_dir: Path,
    *,
    generated_at: datetime,
) -> Path:
    """Write an immutable content generation and atomically select it."""
    artifacts = _bundle_artifacts(bundle, generated_at)
    output = _safe_output_directory(output_dir)
    generations = output / "generations"
    if generations.is_symlink():
        raise ContentPublicationBlocked("content generations path is unsafe")
    generations.mkdir(exist_ok=True)
    generation_name = _generation_digest(artifacts)
    generation = generations / generation_name
    staged = Path(tempfile.mkdtemp(dir=generations, prefix=".staging-"))
    try:
        for name, data in artifacts.items():
            (staged / name).write_bytes(data)
        if generation.exists() or generation.is_symlink():
            _verify_generation(generation, artifacts)
            shutil.rmtree(staged)
        else:
            staged.replace(generation)
        pointer = ContentPointer(
            generation=f"generations/{generation_name}",
            release_generation=bundle.release_generation,
            papers_sha256=bundle.papers_sha256,
            artifact_sha256={name: _sha256(data) for name, data in artifacts.items()},
        )
        _replace_pointer(
            output, _canonical_json_bytes(pointer.model_dump(mode="json"))
        )
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        raise
    return generation


def resolve_current_chinese_content(output_dir: Path) -> Path:
    """Resolve the selected generation after checking pointer and raw bytes."""
    output = Path(output_dir).absolute()
    if output.is_symlink() or not output.is_dir():
        raise ContentPublicationBlocked("content output directory is unavailable")
    current = output / "current.json"
    generations = output / "generations"
    if current.is_symlink() or generations.is_symlink():
        raise ContentPublicationBlocked("content pointer layout is unsafe")
    try:
        pointer = ContentPointer.model_validate_json(current.read_bytes())
    except (OSError, ValidationError) as exc:
        raise ContentPublicationBlocked("content current pointer is invalid") from exc
    parts = Path(pointer.generation).parts
    if len(parts) != 2 or parts[0] != "generations":
        raise ContentPublicationBlocked("content current pointer is unsafe")
    generation = output / parts[0] / parts[1]
    if generation.is_symlink() or not generation.is_dir():
        raise ContentPublicationBlocked("content generation is unavailable")
    if sorted(path.name for path in generation.iterdir()) != sorted(_ARTIFACT_NAMES):
        raise ContentPublicationBlocked("content artifact set is incomplete")
    for name in _ARTIFACT_NAMES:
        path = generation / name
        if path.is_symlink() or not path.is_file():
            raise ContentPublicationBlocked("content artifact is unsafe")
        if _sha256(path.read_bytes()) != pointer.artifact_sha256.get(name):
            raise ContentPublicationBlocked(f"content artifact hash mismatch: {name}")
    try:
        manifest = ContentManifest.model_validate_json(
            (generation / "content-manifest.json").read_bytes()
        )
    except ValidationError as exc:
        raise ContentPublicationBlocked("content manifest is invalid") from exc
    if (
        manifest.release_generation != pointer.release_generation
        or manifest.papers_sha256 != pointer.papers_sha256
        or set(manifest.artifact_sha256) != set(_DATA_ARTIFACT_NAMES)
        or any(
            _sha256((generation / name).read_bytes()) != expected
            for name, expected in manifest.artifact_sha256.items()
        )
    ):
        raise ContentPublicationBlocked("content manifest differs from pointer or bytes")
    return generation
