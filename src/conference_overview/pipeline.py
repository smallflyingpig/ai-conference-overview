"""Evidence-bounded orchestration for the ACL 2026 long-paper reference run."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import yaml

from conference_overview.adapters.acl import (
    AclSourceFormatError,
    enrich_acl_abstracts,
    parse_acl_award_badges,
    parse_acl_bibtex,
)
from conference_overview.awards import (
    AwardRecord,
    AwardStatus,
    DeepRead,
    validate_deep_read,
)
from conference_overview.classification import (
    Assignment,
    ThemeAudit,
    assert_theme_publishable,
    audit_theme,
    export_batches,
    load_assignments,
    load_taxonomy,
)
from conference_overview.fetch import fetch_bytes
from conference_overview.metrics import topic_share
from conference_overview.models import (
    AdvanceCategory,
    AdvanceRecord,
    EvidenceClaim,
    EvidenceType,
    PaperRecord,
    RecordStatus,
    SourceRef,
    ThemeDisclosure,
    ThemeDisclosureStatus,
    VenueRequest,
)
from conference_overview.reports import (
    ReleaseBundle,
    resolve_current_release,
)
from conference_overview.reports import (
    write_release as publish_release,
)
from conference_overview.storage import store_snapshot
from conference_overview.validate import (
    PublicationBlocked,
    ValidationReport,
    assert_publishable,
    validate_records,
)

_ACL_SOURCE_KEY = "2026.acl-long"
_TAXONOMY_VERSION = "2026-08-24-v1"
_HTML_PAPER_ID_PATTERN = re.compile(
    rb"href=(?:[\"']?(?:https://aclanthology\.org)?/)?(2026\.acl-long\.\d+)/",
    re.IGNORECASE,
)
_SEMANTIC_PARTITION_PATTERN = re.compile(r"acl2026-reclass-mod([0-7])\.jsonl")
_DEEP_READ_FIELD_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?")
_PDF_PROVENANCE_ID_PATTERN = re.compile(r"(?:acl:)?(2026\.acl-long\.\d+)")
_PDF_PROVENANCE_SHA_PATTERN = re.compile(r"[0-9a-f]{64}")


class UnsupportedPipelineRoute(ValueError):
    """Raised when a venue route has no implemented adapter orchestration."""


@dataclass(frozen=True)
class ScopePaths:
    root: Path

    @property
    def manifest(self) -> Path:
        return self.root / "data/manifests/acl/2026-long.json"

    @property
    def normalized(self) -> Path:
        return self.root / "data/normalized/acl/2026-long.jsonl"

    @property
    def snapshots(self) -> Path:
        return self.root / "data/snapshots/acl/2026-long"

    @property
    def analysis(self) -> Path:
        return self.root / "data/analysis/acl/2026-long"

    @property
    def classification(self) -> Path:
        return self.root / "data/classification/acl/2026-long"

    @property
    def awards(self) -> Path:
        return self.root / "data/awards/acl/2026-long.yaml"

    @property
    def award_deep_reads(self) -> Path:
        return self.root / "data/awards/acl/2026-long-deep-reads.yaml"

    @property
    def award_deep_read_provenance(self) -> Path:
        return self.root / "data/awards/acl/2026-long-deep-read-provenance.json"

    @property
    def low_confidence_queue(self) -> Path:
        return self.classification / "low-confidence-review-queue.json"

    @property
    def low_confidence_decisions(self) -> Path:
        return self.classification / "low-confidence-decisions.json"

    @property
    def release(self) -> Path:
        return self.root / "data/releases/ACL/2026"

    @property
    def notes(self) -> Path:
        return self.root / "notes/acl-2026-long-overview.md"


@dataclass(frozen=True)
class CollectionResult:
    manifest_path: Path
    normalized_path: Path
    validation: ValidationReport


@dataclass(frozen=True)
class LowConfidenceReviewStatus:
    queued_ids: tuple[str, ...]
    accepted_ids: tuple[str, ...]
    rejected_ids: tuple[str, ...]
    pending_ids: tuple[str, ...]

    @property
    def reviewed_ids(self) -> tuple[str, ...]:
        return tuple(sorted((*self.accepted_ids, *self.rejected_ids)))


def _require_acl(request: VenueRequest) -> None:
    scope = (request.venue, request.year, request.track, request.source_key)
    if scope != ("ACL", 2026, "long", _ACL_SOURCE_KEY):
        raise UnsupportedPipelineRoute(
            "unsupported pipeline route: "
            f"{request.venue}/{request.year}/{request.track or '-'}"
        )
    if request.bibtex_url is None or request.volume_url is None:
        raise UnsupportedPipelineRoute(
            "unsupported pipeline route has no official sources"
        )


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as file:
        temporary = Path(file.name)
        file.write(data)
    try:
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def _jsonl_bytes(payloads: Sequence[Mapping[str, object]]) -> bytes:
    return b"".join(
        (
            json.dumps(
                payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            )
            + "\n"
        ).encode()
        for payload in payloads
    )


def _source_manifest(
    *,
    kind: str,
    source: SourceRef,
    data: bytes,
    snapshot_root: Path,
    repository_root: Path,
) -> dict[str, object]:
    snapshot = snapshot_root / "raw" / f"{source.sha256}.bin"
    return {
        "byte_size": len(data),
        "kind": kind,
        "name": source.name,
        "retrieved_at": source.model_dump(mode="json")["retrieved_at"],
        "sha256": source.sha256,
        "snapshot_path": snapshot.relative_to(repository_root).as_posix(),
        "url": str(source.url),
    }


def collect_acl_scope(
    request: VenueRequest,
    root: Path,
    *,
    client: httpx.Client | None = None,
) -> CollectionResult:
    """Fetch, content-check, normalize, and persist the official ACL scope."""
    _require_acl(request)
    paths = ScopePaths(Path(root))
    owns_client = client is None
    active_client = client or httpx.Client()
    try:
        bibtex = fetch_bytes(str(request.bibtex_url), active_client)
        html = fetch_bytes(str(request.volume_url), active_client)
    finally:
        if owns_client:
            active_client.close()

    bib_source = store_snapshot(
        bibtex, str(request.bibtex_url), paths.snapshots
    ).model_copy(update={"name": "ACL Anthology BibTeX"})
    html_source = store_snapshot(
        html, str(request.volume_url), paths.snapshots
    ).model_copy(update={"name": "ACL Anthology volume HTML"})
    return _normalize_acl_payloads(
        request,
        paths,
        bibtex=bibtex,
        html=html,
        bib_source=bib_source,
        html_source=html_source,
    )


def _normalize_acl_payloads(
    request: VenueRequest,
    paths: ScopePaths,
    *,
    bibtex: bytes,
    html: bytes,
    bib_source: SourceRef,
    html_source: SourceRef,
) -> CollectionResult:
    included, excluded = parse_acl_bibtex(bibtex, request, bib_source)
    enriched = enrich_acl_abstracts(included, html, html_source)

    expected_acl_ids = {
        record.paper_id.removeprefix("acl:") for record in (*enriched, *excluded)
    }
    html_acl_ids = {
        match.decode("ascii") for match in _HTML_PAPER_ID_PATTERN.findall(html)
    }
    missing_html_ids = sorted(expected_acl_ids - html_acl_ids)
    unexpected_html_ids = sorted(html_acl_ids - expected_acl_ids)
    if missing_html_ids or unexpected_html_ids:
        raise AclSourceFormatError(
            source=html_source,
            detail=(
                "volume HTML/BibTeX exact ACL ID mismatch; "
                f"missing from HTML: {missing_html_ids[:10]}; "
                f"unexpected in HTML: {unexpected_html_ids[:10]}"
            ),
        )

    validation = validate_records(
        enriched,
        excluded,
        expected_included=len(enriched),
    )
    records = sorted((*excluded, *enriched), key=lambda record: record.paper_id)
    normalized_bytes = _jsonl_bytes(
        [record.model_dump(mode="json") for record in records]
    )
    _atomic_write(paths.normalized, normalized_bytes)

    manifest = {
        "counts": {
            "discovered": validation.discovered_count,
            "duplicate_candidates": validation.duplicate_candidate_count,
            "excluded": validation.excluded_count,
            "included": validation.included_count,
            "unresolved": len(validation.unresolved_record_ids),
        },
        "excluded_ids": sorted(record.paper_id for record in excluded),
        "normalized": {
            "path": paths.normalized.relative_to(paths.root).as_posix(),
            "record_set_sha256": validation.record_set_sha256,
            "sha256": hashlib.sha256(normalized_bytes).hexdigest(),
        },
        "schema_version": "acl-collection-manifest-v1",
        "scope": {"track": "long", "venue": "ACL", "year": 2026},
        "sources": [
            _source_manifest(
                kind="bibtex",
                source=bib_source,
                data=bibtex,
                snapshot_root=paths.snapshots,
                repository_root=paths.root,
            ),
            _source_manifest(
                kind="html",
                source=html_source,
                data=html,
                snapshot_root=paths.snapshots,
                repository_root=paths.root,
            ),
        ],
    }
    _atomic_write(paths.manifest, _json_bytes(manifest))
    return CollectionResult(paths.manifest, paths.normalized, validation)


def _load_manifest(request: VenueRequest, root: Path) -> dict[str, object]:
    _require_acl(request)
    paths = ScopePaths(Path(root))
    try:
        manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid collection manifest: {paths.manifest}") from exc
    if manifest.get("scope") != {"track": "long", "venue": "ACL", "year": 2026}:
        raise ValueError("collection manifest scope does not match the requested route")
    return manifest


def rebuild_acl_scope_from_snapshots(
    request: VenueRequest, root: Path
) -> CollectionResult:
    """Re-normalize only from hash-verified immutable source snapshots."""
    paths = ScopePaths(Path(root))
    manifest = _load_manifest(request, root)
    raw_sources = manifest.get("sources")
    if not isinstance(raw_sources, list):
        raise TypeError("collection manifest has no source snapshots")

    def load_source(kind: str, expected_url: str) -> tuple[bytes, SourceRef]:
        matches = [
            source
            for source in raw_sources
            if isinstance(source, Mapping) and source.get("kind") == kind
        ]
        if len(matches) != 1:
            raise ValueError(f"collection manifest requires exactly one {kind} source")
        raw_source = matches[0]
        if raw_source.get("url") != expected_url:
            raise ValueError(f"collection manifest {kind} URL differs from registry")
        snapshot = paths.root / str(raw_source.get("snapshot_path"))
        data = snapshot.read_bytes()
        if len(data) != raw_source.get("byte_size") or hashlib.sha256(
            data
        ).hexdigest() != raw_source.get("sha256"):
            raise ValueError(f"immutable {kind} snapshot disagrees with its manifest")
        return data, SourceRef(
            name=str(raw_source.get("name")),
            url=expected_url,
            retrieved_at=raw_source.get("retrieved_at"),
            sha256=str(raw_source.get("sha256")),
        )

    bibtex, bib_source = load_source("bibtex", str(request.bibtex_url))
    html, html_source = load_source("html", str(request.volume_url))
    return _normalize_acl_payloads(
        request,
        paths,
        bibtex=bibtex,
        html=html,
        bib_source=bib_source,
        html_source=html_source,
    )


def load_scope_records(
    request: VenueRequest, root: Path
) -> tuple[list[PaperRecord], list[PaperRecord], tuple[SourceRef, ...]]:
    """Load normalized records only after rechecking immutable hashes and scope."""
    paths = ScopePaths(Path(root))
    manifest = _load_manifest(request, root)
    normalized = manifest.get("normalized")
    if not isinstance(normalized, Mapping):
        raise TypeError("collection manifest has no normalized artifact")
    data = paths.normalized.read_bytes()
    if hashlib.sha256(data).hexdigest() != normalized.get("sha256"):
        raise ValueError("normalized JSONL hash does not match the collection manifest")

    sources: list[SourceRef] = []
    raw_sources = manifest.get("sources")
    if not isinstance(raw_sources, list) or {
        source.get("kind") for source in raw_sources
    } != {
        "bibtex",
        "html",
    }:
        raise ValueError("collection manifest must retain BibTeX and HTML sources")
    for raw_source in raw_sources:
        if not isinstance(raw_source, Mapping):
            raise TypeError("collection source entry must be an object")
        snapshot = paths.root / str(raw_source["snapshot_path"])
        snapshot_data = snapshot.read_bytes()
        if len(snapshot_data) != raw_source.get("byte_size") or hashlib.sha256(
            snapshot_data
        ).hexdigest() != raw_source.get("sha256"):
            raise ValueError("immutable source snapshot disagrees with its manifest")
        sources.append(
            SourceRef(
                name=str(raw_source["name"]),
                url=str(raw_source["url"]),
                retrieved_at=raw_source["retrieved_at"],
                sha256=str(raw_source["sha256"]),
            )
        )

    records: list[PaperRecord] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(PaperRecord.model_validate_json(line))
        except ValueError as exc:
            raise ValueError(
                f"invalid normalized record on line {line_number}"
            ) from exc
    included = [
        record for record in records if record.status is not RecordStatus.EXCLUDED
    ]
    excluded = [record for record in records if record.status is RecordStatus.EXCLUDED]
    return included, excluded, tuple(sources)


def validate_acl_scope(request: VenueRequest, root: Path) -> ValidationReport:
    """Recompute source-count reconciliation from the persisted normalized corpus."""
    paths = ScopePaths(Path(root))
    manifest = _load_manifest(request, root)
    included, excluded, _sources = load_scope_records(request, root)
    counts = manifest.get("counts")
    if not isinstance(counts, Mapping) or not isinstance(counts.get("included"), int):
        raise TypeError("collection manifest has no observed included count")
    report = validate_records(
        included,
        excluded,
        expected_included=int(counts["included"]),
    )
    if report.record_set_sha256 != manifest["normalized"]["record_set_sha256"]:  # type: ignore[index]
        raise ValueError("normalized record-set hash does not match the manifest")
    _atomic_write(paths.analysis / "validation.json", _json_bytes(asdict(report)))
    return report


def export_classification_scope(
    request: VenueRequest,
    root: Path,
    *,
    batch_size: int = 40,
) -> list[Path]:
    """Write deterministic title-and-abstract exchange batches."""
    paths = ScopePaths(Path(root))
    report = validate_acl_scope(request, root)
    assert_publishable(report)
    included, _excluded, _sources = load_scope_records(request, root)
    batches = export_batches(included, load_taxonomy(), size=batch_size)
    output = paths.classification / "batches"
    batch_paths: list[Path] = []
    for batch in batches:
        path = output / f"batch-{int(batch['batch_index']):04d}.json"
        _atomic_write(path, _json_bytes(batch))
        batch_paths.append(path)
    _atomic_write(
        paths.classification / "batches-manifest.json",
        _json_bytes(
            {
                "batch_count": len(batches),
                "batch_size": batch_size,
                "paper_count": len(included),
                "taxonomy_version": load_taxonomy()["version"],
            }
        ),
    )
    return batch_paths


_TOPIC_PHRASES: dict[str, tuple[str, ...]] = {
    "Reasoning and Agents": (
        "agent",
        "reasoning",
        "tool use",
        "tool-using",
        "planning",
        "chain-of-thought",
    ),
    "Evaluation": (
        "benchmark",
        "evaluation",
        "metric",
        "diagnostic",
        "llm judge",
    ),
    "Trustworthiness": (
        "safety",
        "jailbreak",
        "bias",
        "fairness",
        "privacy",
        "hallucination",
        "robustness",
        "adversarial",
        "factuality",
    ),
    "Multimodal Models": (
        "multimodal",
        "vision-language",
        "visual question",
        "image-text",
        "video-language",
        "audio-language",
    ),
    "Multilingual and Inclusive NLP": (
        "multilingual",
        "cross-lingual",
        "low-resource",
        "dialect",
        "inclusive",
        "code-switch",
    ),
    "Data and Retrieval": (
        "retrieval",
        "retrieval-augmented",
        "rag",
        "knowledge graph",
        "data curation",
        "data selection",
        "corpus",
    ),
    "Learning and Optimization": (
        "optimization",
        "distillation",
        "fine-tuning",
        "finetuning",
        "reinforcement learning",
        "preference optimization",
        "training efficiency",
        "parameter-efficient",
    ),
    "Foundation Models": (
        "large language model",
        "language models",
        "foundation model",
        "pretrained language",
        "pre-trained language",
        "in-context learning",
        "prompting",
    ),
    "Applications": (
        "clinical",
        "medical",
        "legal",
        "education",
        "financial",
        "social science",
        "scientific discovery",
    ),
    "NLP/CV Core Tasks": (
        "translation",
        "summarization",
        "named entity",
        "information extraction",
        "question answering",
        "semantic parsing",
        "sentiment",
        "discourse",
        "syntax",
        "morphology",
    ),
}


def _assisted_assignment(record: PaperRecord) -> Assignment:
    title = record.title.casefold()
    abstract = (record.abstract or "").casefold()
    evidence: dict[str, list[str]] = {}
    scores: dict[str, int] = {}
    for topic, phrases in _TOPIC_PHRASES.items():
        title_hits = [phrase for phrase in phrases if phrase in title]
        abstract_hits = [
            phrase
            for phrase in phrases
            if phrase in abstract and phrase not in title_hits
        ]
        evidence[topic] = [*title_hits, *abstract_hits]
        scores[topic] = 4 * len(title_hits) + len(abstract_hits)
    ranked = sorted(scores, key=lambda topic: (-scores[topic], topic))
    primary = ranked[0] if scores[ranked[0]] > 0 else "NLP/CV Core Tasks"
    top_score = scores[primary]
    runner_up = max(
        (score for topic, score in scores.items() if topic != primary), default=0
    )
    secondary = tuple(
        topic
        for topic in ranked
        if topic != primary and scores[topic] >= max(2, top_score // 2)
    )[:2]
    confidence = (
        Decimal("0.90")
        if top_score >= 5 and top_score - runner_up >= 3
        else Decimal("0.80")
        if top_score >= 3 and top_score > runner_up
        else Decimal("0.65")
    )
    matched = evidence[primary]
    rationale = (
        "Deterministic assisted proposal from title and abstract phrases: "
        + ", ".join(matched[:4])
        if matched
        else (
            "Deterministic assisted fallback to the broad core-task topic because "
            "no stronger taxonomy phrase was observed in the title and abstract."
        )
    )
    return Assignment(
        paper_id=record.paper_id,
        primary_topic=primary,
        secondary_topics=secondary,
        confidence=confidence,
        rationale=rationale,
        taxonomy_version=_TAXONOMY_VERSION,
    )


def assisted_classify_scope(request: VenueRequest, root: Path) -> list[Assignment]:
    """Create explicit deterministic proposals from every title and abstract."""
    paths = ScopePaths(Path(root))
    included, _excluded, _sources = load_scope_records(request, root)
    assignments = [
        _assisted_assignment(record)
        for record in sorted(included, key=lambda item: item.paper_id)
    ]
    payloads = [
        {
            "confidence": str(assignment.confidence),
            "paper_id": assignment.paper_id,
            "primary_topic": assignment.primary_topic,
            "rationale": assignment.rationale,
            "secondary_topics": list(assignment.secondary_topics),
            "taxonomy_version": assignment.taxonomy_version,
        }
        for assignment in assignments
    ]
    assignment_bytes = _jsonl_bytes(payloads)
    _atomic_write(paths.classification / "assignments.jsonl", assignment_bytes)
    review_status, queue_sha256 = _write_low_confidence_review_queue(
        paths,
        included,
        assignments,
        assignments_sha256=hashlib.sha256(assignment_bytes).hexdigest(),
    )
    _write_classification_manifest(
        paths,
        assignments=assignments,
        assignments_sha256=hashlib.sha256(assignment_bytes).hexdigest(),
        review_status=review_status,
        queue_sha256=queue_sha256,
    )
    _write_audit_samples(paths, included, assignments)
    return assignments


def import_semantic_assignments_scope(
    request: VenueRequest,
    root: Path,
    input_paths: Sequence[Path],
) -> list[Assignment]:
    """Merge eight explicit agent-reviewed partitions into the canonical corpus."""
    _require_acl(request)
    paths = ScopePaths(Path(root))
    included, _excluded, _sources = load_scope_records(request, root)
    expected_ids = {record.paper_id for record in included}
    taxonomy = load_taxonomy()

    partition_paths: dict[int, Path] = {}
    for raw_path in input_paths:
        path = Path(raw_path)
        match = _SEMANTIC_PARTITION_PATTERN.fullmatch(path.name)
        if match is None:
            raise ValueError(
                "semantic assignment inputs must be named "
                "acl2026-reclass-mod0.jsonl through acl2026-reclass-mod7.jsonl"
            )
        partition = int(match.group(1))
        if partition in partition_paths:
            raise ValueError(f"duplicate semantic assignment partition: {partition}")
        partition_paths[partition] = path
    if set(partition_paths) != set(range(8)):
        raise ValueError(
            "semantic assignment import requires exact partitions 0 through 7"
        )

    assignments_by_id: dict[str, Assignment] = {}
    source_batches: list[dict[str, object]] = []
    for partition, path in sorted(partition_paths.items()):
        raw_bytes = path.read_bytes()
        partition_assignments = load_assignments(path, taxonomy)
        for assignment in partition_assignments:
            try:
                numeric_id = int(assignment.paper_id.rsplit(".", maxsplit=1)[-1])
            except ValueError as exc:
                raise ValueError(
                    f"semantic assignment has nonnumeric ACL ID: {assignment.paper_id}"
                ) from exc
            if numeric_id % 8 != partition:
                raise ValueError(
                    f"semantic assignment {assignment.paper_id} is in partition "
                    f"{partition}, expected {numeric_id % 8}"
                )
            if assignment.paper_id in assignments_by_id:
                raise ValueError(f"duplicate paper_id: {assignment.paper_id}")
            assignments_by_id[assignment.paper_id] = assignment
        source_batches.append(
            {
                "paper_count": len(partition_assignments),
                "partition": partition,
                "partition_rule": "ACL numeric paper ID modulo 8",
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "source_file": path.name,
            }
        )

    seen_ids = set(assignments_by_id)
    missing_ids = sorted(expected_ids - seen_ids)
    unexpected_ids = sorted(seen_ids - expected_ids)
    if missing_ids:
        raise ValueError(f"missing paper IDs: {missing_ids}")
    if unexpected_ids:
        raise ValueError(f"unknown paper IDs: {unexpected_ids}")

    assignments = [assignments_by_id[paper_id] for paper_id in sorted(expected_ids)]
    assignment_bytes = _jsonl_bytes(
        [
            {
                "confidence": str(assignment.confidence),
                "paper_id": assignment.paper_id,
                "primary_topic": assignment.primary_topic,
                "rationale": assignment.rationale,
                "secondary_topics": list(assignment.secondary_topics),
                "taxonomy_version": assignment.taxonomy_version,
            }
            for assignment in assignments
        ]
    )
    _atomic_write(paths.classification / "assignments.jsonl", assignment_bytes)
    assignments_sha256 = hashlib.sha256(assignment_bytes).hexdigest()
    review_status, queue_sha256 = _write_low_confidence_review_queue(
        paths,
        included,
        assignments,
        assignments_sha256=assignments_sha256,
        reset_decisions=True,
    )
    _write_classification_manifest(
        paths,
        assignments=assignments,
        assignments_sha256=assignments_sha256,
        review_status=review_status,
        queue_sha256=queue_sha256,
        classifier="agent-semantic-batch-review-v1",
        semantic_labeling={
            "method": "explicit_agent_semantic_labeling",
            "source_batches": source_batches,
        },
    )
    _write_audit_samples(paths, included, assignments, reset_decisions=True)
    return assignments


def _assignment_payloads(assignments: Sequence[Assignment]) -> list[dict[str, object]]:
    return [
        {
            "confidence": str(assignment.confidence),
            "paper_id": assignment.paper_id,
            "primary_topic": assignment.primary_topic,
            "rationale": assignment.rationale,
            "secondary_topics": list(assignment.secondary_topics),
            "taxonomy_version": assignment.taxonomy_version,
        }
        for assignment in assignments
    ]


def _full_theme_review_rows(
    path: Path, payload: object, base_sha256: str, root: Path, base_bytes: bytes
) -> tuple[str, list[Mapping[str, object]]]:
    if isinstance(payload, list):
        rows = payload
        declared_theme = None
    elif isinstance(payload, Mapping) and isinstance(payload.get("reviews"), list):
        rows = payload["reviews"]
        declared_theme = payload.get("source_primary_topic")
        declared_sha256 = payload.get("source_assignments_sha256")
        if declared_sha256 is not None and declared_sha256 != base_sha256:
            raise ValueError(f"full-theme review base hash mismatch: {path.name}")
    elif isinstance(payload, Mapping) and isinstance(payload.get("decisions"), list):
        rows = payload["decisions"]
        scope = payload.get("review_scope")
        declared_theme = (
            scope.get("old_primary_topic") if isinstance(scope, Mapping) else None
        )
    elif isinstance(payload, Mapping) and isinstance(payload.get("records"), list):
        rows = payload["records"]
        declared_theme = payload.get("reviewed_primary_topic")
        source_commit = payload.get("source_commit")
        source_file = payload.get("source_file")
        if (
            not isinstance(source_commit, str)
            or not re.fullmatch(r"[0-9a-f]{40}", source_commit)
            or not isinstance(source_file, str)
            or Path(source_file).is_absolute()
            or ".." in Path(source_file).parts
            or payload.get("record_count") != len(rows)
        ):
            raise ValueError(f"invalid full-theme review source binding: {path.name}")
        result = subprocess.run(
            ["git", "show", f"{source_commit}:{source_file}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
        if result.returncode != 0 or result.stdout != base_bytes:
            raise ValueError(f"full-theme review base hash mismatch: {path.name}")
    else:
        raise TypeError(f"invalid full-theme review artifact: {path.name}")
    if not rows or not all(isinstance(row, Mapping) for row in rows):
        raise TypeError(f"full-theme review rows are invalid: {path.name}")
    old_topics = {
        str(row.get("old_primary_topic", row.get("old_topic", row.get("old"))))
        for row in rows
    }
    if len(old_topics) != 1:
        raise ValueError(f"full-theme review mixes source themes: {path.name}")
    source_theme = old_topics.pop()
    if declared_theme is not None and declared_theme != source_theme:
        raise ValueError(f"full-theme review source-theme mismatch: {path.name}")
    return source_theme, rows  # type: ignore[return-value]


def import_full_theme_reviews_scope(
    request: VenueRequest,
    root: Path,
    input_paths: Sequence[Path],
) -> list[Assignment]:
    """Apply exhaustive theme reviews against one hash-bound assignment base."""
    _require_acl(request)
    paths = ScopePaths(Path(root))
    records, _excluded, _sources = load_scope_records(request, root)
    assignment_path = paths.classification / "assignments.jsonl"
    base_bytes = assignment_path.read_bytes()
    base_sha256 = hashlib.sha256(base_bytes).hexdigest()
    assignments = load_assignments(
        assignment_path,
        load_taxonomy(),
        expected_paper_ids=(record.paper_id for record in records),
    )
    base_by_id = {assignment.paper_id: assignment for assignment in assignments}
    manifest = json.loads(
        (paths.classification / "classification-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    if (
        not isinstance(manifest, Mapping)
        or manifest.get("assignments_sha256") != base_sha256
    ):
        raise ValueError("full-theme review base assignment hash is not manifest-bound")
    (
        classifier,
        semantic_labeling,
        audit_corrections,
        low_provenance,
        _old_full_reviews,
    ) = _load_classification_provenance(paths, base_sha256)
    taxonomy_topics = {
        str(topic["name"])
        for topic in load_taxonomy()["topics"]  # type: ignore[index]
    }
    theme_ids: dict[str, set[str]] = {}
    for assignment in assignments:
        theme_ids.setdefault(assignment.primary_topic, set()).add(assignment.paper_id)

    reviewed: dict[str, dict[str, object]] = {}
    source_ledger: list[dict[str, object]] = []
    movement_matrix: dict[str, dict[str, int]] = {}
    for raw_path in sorted(
        (Path(path) for path in input_paths), key=lambda path: path.name
    ):
        raw_bytes = raw_path.read_bytes()
        payload = json.loads(raw_bytes)
        source_theme, rows = _full_theme_review_rows(
            raw_path, payload, base_sha256, paths.root, base_bytes
        )
        if source_theme not in taxonomy_topics:
            raise ValueError(f"unknown full-theme review source: {source_theme}")
        file_ids: set[str] = set()
        correction_count = 0
        keep_count = 0
        for row in rows:
            paper_id = row.get("paper_id")
            old_topic = row.get(
                "old_primary_topic", row.get("old_topic", row.get("old"))
            )
            decision = row.get("decision", row.get("action"))
            corrected_topic = row.get(
                "corrected_primary_topic",
                row.get("corrected_topic", row.get("corrected")),
            )
            rationale = row.get("rationale")
            try:
                confidence = Decimal(str(row.get("confidence")))
            except Exception as exc:
                raise ValueError(f"invalid full-theme confidence: {paper_id}") from exc
            if not isinstance(paper_id, str) or paper_id in reviewed:
                raise ValueError(f"duplicate full-theme review paper ID: {paper_id}")
            if (
                old_topic != source_theme
                or base_by_id.get(paper_id) is None
                or base_by_id[paper_id].primary_topic != source_theme
            ):
                raise ValueError(f"full-theme old primary mismatch: {paper_id}")
            normalized_decision = (
                "keep"
                if decision in {"keep", "keep-correct"}
                else "correct"
                if decision in {"change", "correct", "move", "corrected"}
                else None
            )
            if (
                normalized_decision is None
                or corrected_topic not in taxonomy_topics
                or (normalized_decision == "keep" and corrected_topic != source_theme)
                or (
                    normalized_decision == "correct" and corrected_topic == source_theme
                )
                or not isinstance(rationale, str)
                or not rationale.strip()
                or confidence < 0
                or confidence > 1
            ):
                raise ValueError(f"invalid full-theme review decision: {paper_id}")
            file_ids.add(paper_id)
            reviewed[paper_id] = {
                "confidence": confidence,
                "corrected_topic": str(corrected_topic),
                "decision": normalized_decision,
                "rationale": rationale.strip(),
                "source_file": raw_path.name,
                "source_theme": source_theme,
            }
            destination = str(corrected_topic)
            movements = movement_matrix.setdefault(source_theme, {})
            movements[destination] = movements.get(destination, 0) + 1
            if normalized_decision == "correct":
                correction_count += 1
            else:
                keep_count += 1
        if file_ids != theme_ids.get(source_theme, set()):
            raise ValueError(
                f"full-theme review does not cover exact source-theme ID set: "
                f"{source_theme}"
            )
        source_entry: dict[str, object] = {
            "correction_count": correction_count,
            "keep_count": keep_count,
            "paper_count": len(rows),
            "sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "source_file": raw_path.name,
            "source_theme": source_theme,
        }
        if isinstance(payload, Mapping) and "source_commit" in payload:
            source_entry.update(
                {
                    "assignment_blob_sha256": base_sha256,
                    "source_assignment_file": payload["source_file"],
                    "source_commit": payload["source_commit"],
                }
            )
        source_ledger.append(source_entry)

    corrected_by_id = dict(base_by_id)
    corrections: list[dict[str, str]] = []
    for paper_id, review in reviewed.items():
        if review["decision"] == "keep":
            continue
        original = base_by_id[paper_id]
        corrected_topic = str(review["corrected_topic"])
        corrected_by_id[paper_id] = Assignment(
            paper_id=paper_id,
            primary_topic=corrected_topic,
            secondary_topics=tuple(
                topic for topic in original.secondary_topics if topic != corrected_topic
            ),
            confidence=review["confidence"],  # type: ignore[arg-type]
            rationale=(
                f"full-theme review correction: {original.primary_topic} -> "
                f"{corrected_topic}; {review['rationale']} "
                f"Original semantic rationale: {original.rationale}"
            ),
            taxonomy_version=original.taxonomy_version,
        )
        corrections.append(
            {
                "corrected_primary_topic": corrected_topic,
                "original_primary_topic": original.primary_topic,
                "paper_id": paper_id,
                "source_file": str(review["source_file"]),
            }
        )

    corrected = [corrected_by_id[paper_id] for paper_id in sorted(corrected_by_id)]
    assignment_bytes = _jsonl_bytes(_assignment_payloads(corrected))
    _atomic_write(assignment_path, assignment_bytes)
    assignments_sha256 = hashlib.sha256(assignment_bytes).hexdigest()

    old_low_decisions = json.loads(paths.low_confidence_decisions.read_bytes())
    old_reviews = old_low_decisions.get("reviews")
    if not isinstance(old_reviews, list):
        raise TypeError("invalid low-confidence decisions before full-theme review")
    for low_review in old_reviews:
        paper_id = (
            low_review.get("paper_id") if isinstance(low_review, Mapping) else None
        )
        if not isinstance(paper_id, str) or corrected_by_id.get(
            paper_id
        ) != base_by_id.get(paper_id):
            raise ValueError(
                f"low-confidence review cannot survive full-theme change: {paper_id}"
            )
    _empty_status, queue_sha256 = _write_low_confidence_review_queue(
        paths,
        records,
        corrected,
        assignments_sha256=assignments_sha256,
        reset_decisions=True,
    )
    rebound_low_decisions = dict(old_low_decisions)
    rebound_low_decisions["queue_sha256"] = queue_sha256
    _atomic_write(paths.low_confidence_decisions, _json_bytes(rebound_low_decisions))
    review_status, queue_sha256 = _load_low_confidence_reviews(
        paths, corrected, assignments_sha256=assignments_sha256
    )
    if isinstance(low_provenance, Mapping):
        low_provenance = dict(low_provenance)
        low_provenance["output_queue_sha256"] = queue_sha256
    full_theme_reviews = {
        "base_assignments_sha256": base_sha256,
        "correction_count": len(corrections),
        "corrections": sorted(corrections, key=lambda item: item["paper_id"]),
        "keep_count": len(reviewed) - len(corrections),
        "method": "exhaustive title-and-abstract full-theme semantic review",
        "movement_matrix": {
            source: dict(sorted(destinations.items()))
            for source, destinations in sorted(movement_matrix.items())
        },
        "reviewed_count": len(reviewed),
        "sources": source_ledger,
    }
    if isinstance(_old_full_reviews, Mapping):
        prior_stages = list(_old_full_reviews.get("prior_stages", []))
        prior_stages.append(
            {
                key: deepcopy(value)
                for key, value in _old_full_reviews.items()
                if key not in {"prior_stages", "stage_index"}
            }
        )
        full_theme_reviews["prior_stages"] = prior_stages
        full_theme_reviews["stage_index"] = len(prior_stages) + 1
    _write_classification_manifest(
        paths,
        assignments=corrected,
        assignments_sha256=assignments_sha256,
        review_status=review_status,
        queue_sha256=queue_sha256,
        classifier=classifier,
        semantic_labeling=semantic_labeling,
        audit_corrections=audit_corrections,
        low_confidence_review_provenance=low_provenance,
        full_theme_reviews=full_theme_reviews,
    )
    _write_audit_samples(paths, records, corrected, reset_decisions=True)
    return corrected


def apply_audit_corrections_scope(
    request: VenueRequest,
    root: Path,
    audit_paths: Sequence[Path],
    low_review_path: Path,
) -> list[Assignment]:
    """Apply independently reviewed primary-topic corrections with old-value guards."""
    _require_acl(request)
    paths = ScopePaths(Path(root))
    records, _excluded, _sources = load_scope_records(request, root)
    assignment_path = paths.classification / "assignments.jsonl"
    assignments = load_assignments(
        assignment_path,
        load_taxonomy(),
        expected_paper_ids=(record.paper_id for record in records),
    )
    original_by_id = {assignment.paper_id: assignment for assignment in assignments}
    original_sha256 = hashlib.sha256(assignment_path.read_bytes()).hexdigest()
    (
        classifier,
        semantic_labeling,
        _old_corrections,
        _old_low_provenance,
        full_theme_reviews,
    ) = _load_classification_provenance(paths, original_sha256)
    sample_registry = json.loads(
        (paths.classification / "audit-samples.json").read_text(encoding="utf-8")
    )
    sample_themes = sample_registry.get("themes")
    if not isinstance(sample_themes, Mapping):
        raise TypeError("audit sample registry must contain theme candidates")
    expected_review_ids: dict[str, str] = {}
    for theme, candidates in sample_themes.items():
        if not isinstance(theme, str) or not isinstance(candidates, list):
            raise TypeError("invalid audit sample theme")
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                raise TypeError("invalid audit sample candidate")
            paper_id = candidate.get("paper_id")
            if not isinstance(paper_id, str) or paper_id in expected_review_ids:
                raise ValueError("duplicate or invalid audit sample paper ID")
            expected_review_ids[paper_id] = theme

    taxonomy_topics = {
        str(topic["name"])
        for topic in load_taxonomy()["topics"]  # type: ignore[index]
    }
    reviewed: dict[str, tuple[str, Mapping[str, object]]] = {}
    audit_sources: list[dict[str, object]] = []
    for raw_path in audit_paths:
        path = Path(raw_path)
        raw_bytes = path.read_bytes()
        document = json.loads(raw_bytes)
        if (
            not isinstance(document, Mapping)
            or document.get("schema_version") != "classification-audit-v1"
            or document.get("taxonomy_version") != _TAXONOMY_VERSION
            or not isinstance(document.get("themes"), Mapping)
        ):
            raise ValueError("audit correction source contract mismatch")
        source_count = 0
        for theme, decisions in document["themes"].items():  # type: ignore[union-attr]
            if theme not in taxonomy_topics or not isinstance(decisions, list):
                raise ValueError("audit correction source has an invalid theme")
            for decision in decisions:
                source_count += 1
                if not isinstance(decision, Mapping):
                    raise TypeError("audit correction decision must be an object")
                paper_id = decision.get("paper_id")
                if not isinstance(paper_id, str) or paper_id in reviewed:
                    raise ValueError(
                        "conflicting or duplicate audit correction decision"
                    )
                if expected_review_ids.get(paper_id) != theme:
                    raise ValueError(
                        f"audit decision old primary mismatch for {paper_id}"
                    )
                assignment = original_by_id.get(paper_id)
                if assignment is None or assignment.primary_topic != theme:
                    raise ValueError(f"assignment old primary mismatch for {paper_id}")
                correct = decision.get("correct")
                note = decision.get("review_note")
                if (
                    not isinstance(correct, bool)
                    or not isinstance(note, str)
                    or not note.strip()
                ):
                    raise ValueError("audit correction decision is incomplete")
                corrected_topic = decision.get("corrected_primary_topic")
                if not correct and (
                    corrected_topic not in taxonomy_topics or corrected_topic == theme
                ):
                    raise ValueError(
                        "incorrect audit decision requires a new valid topic"
                    )
                if correct and corrected_topic is not None:
                    raise ValueError(
                        "correct audit decision cannot change the primary topic"
                    )
                reviewed[paper_id] = (path.name, decision)
        audit_sources.append(
            {
                "paper_count": source_count,
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "source_file": path.name,
            }
        )
    if set(reviewed) != set(expected_review_ids):
        missing = sorted(set(expected_review_ids) - set(reviewed))
        unexpected = sorted(set(reviewed) - set(expected_review_ids))
        raise ValueError(
            f"audit correction sources do not match samples; missing={missing}; "
            f"unexpected={unexpected}"
        )

    corrected_by_id = dict(original_by_id)
    correction_provenance: list[dict[str, str]] = []
    for paper_id, (source_file, decision) in reviewed.items():
        if decision["correct"]:
            continue
        original = original_by_id[paper_id]
        corrected_topic = str(decision["corrected_primary_topic"])
        corrected_by_id[paper_id] = Assignment(
            paper_id=paper_id,
            primary_topic=corrected_topic,
            secondary_topics=tuple(
                topic for topic in original.secondary_topics if topic != corrected_topic
            ),
            confidence=Decimal("0.99"),
            rationale=(
                "independent audit correction: primary topic changed from "
                f"{original.primary_topic} to {corrected_topic}; "
                f"{str(decision['review_note']).strip()}"
            ),
            taxonomy_version=original.taxonomy_version,
        )
        correction_provenance.append(
            {
                "corrected_primary_topic": corrected_topic,
                "original_primary_topic": original.primary_topic,
                "paper_id": paper_id,
                "source_file": source_file,
            }
        )

    low_review_path = Path(low_review_path)
    low_review_bytes = low_review_path.read_bytes()
    low_review = json.loads(low_review_bytes)
    current_queue_sha256 = hashlib.sha256(
        paths.low_confidence_queue.read_bytes()
    ).hexdigest()
    if (
        not isinstance(low_review, Mapping)
        or low_review.get("schema_version") != "low-confidence-review-decisions-v1"
        or low_review.get("taxonomy_version") != _TAXONOMY_VERSION
        or low_review.get("queue_sha256") != current_queue_sha256
        or not isinstance(low_review.get("reviews"), list)
    ):
        raise ValueError("low-confidence review source contract mismatch")
    for review in low_review["reviews"]:  # type: ignore[index]
        if not isinstance(review, Mapping) or not isinstance(
            review.get("paper_id"), str
        ):
            raise TypeError("invalid low-confidence review")
        paper_id = str(review["paper_id"])
        if corrected_by_id.get(paper_id) != original_by_id.get(paper_id):
            raise ValueError(
                f"low-confidence review cannot be reused after assignment change: {paper_id}"
            )

    corrected = [corrected_by_id[paper_id] for paper_id in sorted(corrected_by_id)]
    assignment_bytes = _jsonl_bytes(_assignment_payloads(corrected))
    _atomic_write(assignment_path, assignment_bytes)
    assignments_sha256 = hashlib.sha256(assignment_bytes).hexdigest()
    _empty_status, queue_sha256 = _write_low_confidence_review_queue(
        paths,
        records,
        corrected,
        assignments_sha256=assignments_sha256,
        reset_decisions=True,
    )
    rebound_low_review = dict(low_review)
    rebound_low_review["queue_sha256"] = queue_sha256
    _atomic_write(paths.low_confidence_decisions, _json_bytes(rebound_low_review))
    review_status, queue_sha256 = _load_low_confidence_reviews(
        paths, corrected, assignments_sha256=assignments_sha256
    )
    audit_corrections = {
        "correction_count": len(correction_provenance),
        "corrections": sorted(correction_provenance, key=lambda item: item["paper_id"]),
        "method": "independent audit correction",
        "reviewed_count": len(reviewed),
        "sources": audit_sources,
    }
    low_provenance = {
        "input_queue_sha256": current_queue_sha256,
        "output_queue_sha256": queue_sha256,
        "sha256": hashlib.sha256(low_review_bytes).hexdigest(),
        "source_file": low_review_path.name,
    }
    _write_classification_manifest(
        paths,
        assignments=corrected,
        assignments_sha256=assignments_sha256,
        review_status=review_status,
        queue_sha256=queue_sha256,
        classifier=classifier,
        semantic_labeling=semantic_labeling,
        audit_corrections=audit_corrections,
        low_confidence_review_provenance=low_provenance,
        full_theme_reviews=full_theme_reviews,
    )
    _write_audit_samples(paths, records, corrected, reset_decisions=True)
    return corrected


def _replace_deep_read_value(
    deep_read: dict[str, object], field_path: str, old: object, new: object
) -> None:
    current: object = deep_read
    segments = field_path.split(".")
    for index, segment in enumerate(segments):
        match = _DEEP_READ_FIELD_PATTERN.fullmatch(segment)
        if match is None or not isinstance(current, dict):
            raise ValueError(f"invalid deep-read patch path: {field_path}")
        key, list_index = match.groups()
        if key not in current:
            raise ValueError(f"unknown deep-read patch path: {field_path}")
        if index == len(segments) - 1 and list_index is None:
            if current[key] != old:
                raise ValueError(f"deep-read patch old value mismatch: {field_path}")
            current[key] = new
            return
        current = current[key]
        if list_index is not None:
            if not isinstance(current, list) or int(list_index) >= len(current):
                raise ValueError(f"invalid deep-read patch index: {field_path}")
            current = current[int(list_index)]
    raise ValueError(f"invalid terminal deep-read patch path: {field_path}")


def _parse_pdf_provenance_tables(text: str) -> list[tuple[str, int, int, str]]:
    """Parse the independently authored Markdown provenance-table layouts."""
    header: dict[str, int] | None = None
    parsed: list[tuple[str, int, int, str]] = []
    aliases = {
        "paper": "paper_id",
        "paper id": "paper_id",
        "paper_id": "paper_id",
        "pages": "pages",
        "pdf pages": "pages",
        "bytes": "byte_size",
        "sha-256": "sha256",
    }
    for row in (line for line in text.splitlines() if line.strip().startswith("|")):
        cells = [cell.strip().strip("`") for cell in row.strip().strip("|").split("|")]
        normalized = [aliases.get(cell.lower()) for cell in cells]
        if {"paper_id", "pages", "byte_size", "sha256"}.issubset(normalized):
            header = {name: normalized.index(name) for name in set(normalized) if name}
            continue
        if header is None or max(header.values()) >= len(cells):
            continue
        id_match = _PDF_PROVENANCE_ID_PATTERN.fullmatch(cells[header["paper_id"]])
        sha_match = _PDF_PROVENANCE_SHA_PATTERN.fullmatch(cells[header["sha256"]])
        if id_match is None or sha_match is None:
            continue
        parsed.append(
            (
                f"acl:{id_match.group(1)}",
                int(cells[header["pages"]].replace(",", "")),
                int(cells[header["byte_size"]].replace(",", "")),
                sha_match.group(0),
            )
        )
    return parsed


def _validate_complete_pdf(data: bytes, source_url: str) -> None:
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-1024:]:
        raise ValueError(f"official award PDF is incomplete or invalid: {source_url}")


def import_award_deep_reads_scope(
    request: VenueRequest,
    root: Path,
    deep_read_paths: Sequence[Path],
    patch_paths: Sequence[Path],
    note_paths: Sequence[Path],
    review_paths: Sequence[Path],
    *,
    client: httpx.Client | None = None,
) -> list[DeepRead]:
    """Merge, guarded-patch, validate, and bind award-paper DeepReads."""
    _require_acl(request)
    paths = ScopePaths(Path(root))
    if not paths.awards.exists():
        parse_award_inventory_scope(request, root)
    inventory = yaml.safe_load(paths.awards.read_text(encoding="utf-8"))
    awards = inventory.get("awards") if isinstance(inventory, Mapping) else None
    if not isinstance(awards, list):
        raise TypeError("official award inventory has no awards list")
    award_ids = {str(award["paper_id"]) for award in awards}
    award_pdf_urls = {str(award["paper_id"]): str(award["pdf_url"]) for award in awards}

    raw_by_id: dict[str, dict[str, object]] = {}
    sources: list[dict[str, object]] = []
    for raw_path in deep_read_paths:
        path = Path(raw_path)
        raw_bytes = path.read_bytes()
        payload = yaml.safe_load(raw_bytes)
        items = payload.get("deep_reads") if isinstance(payload, Mapping) else None
        if not isinstance(items, list):
            raise TypeError("deep-read source must contain a deep_reads list")
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("paper_id"), str):
                raise TypeError("deep-read item must be an object with paper_id")
            paper_id = str(item["paper_id"])
            if paper_id in raw_by_id:
                raise ValueError(f"duplicate award deep-read paper ID: {paper_id}")
            raw_by_id[paper_id] = deepcopy(item)
        sources.append(_input_source_payload(path, raw_bytes, "deep_read_batch"))
    if set(raw_by_id) != award_ids:
        raise ValueError(
            "award deep reads must bind exactly to official inventory IDs; "
            f"missing={sorted(award_ids - set(raw_by_id))}; "
            f"unexpected={sorted(set(raw_by_id) - award_ids)}"
        )

    applied_patches: list[dict[str, object]] = []
    for raw_path in patch_paths:
        path = Path(raw_path)
        raw_bytes = path.read_bytes()
        payload = yaml.safe_load(raw_bytes)
        raw_patches = None
        if isinstance(payload, Mapping):
            raw_patches = payload.get("patches", payload.get("corrections"))
        if not isinstance(raw_patches, list):
            raise TypeError("deep-read patch source has no patch list")
        for raw_patch in raw_patches:
            if not isinstance(raw_patch, Mapping):
                raise TypeError("deep-read patch must be an object")
            paper_id = raw_patch.get("paper_id")
            field_path = raw_patch.get("path", raw_patch.get("field_path"))
            if (
                not isinstance(paper_id, str)
                or paper_id not in raw_by_id
                or not isinstance(field_path, str)
                or raw_patch.get("operation", "replace") != "replace"
                or "old" not in raw_patch
                or "new" not in raw_patch
            ):
                raise ValueError("invalid deep-read replacement patch")
            _replace_deep_read_value(
                raw_by_id[paper_id], field_path, raw_patch["old"], raw_patch["new"]
            )
            applied_patches.append(
                {
                    "field_path": field_path,
                    "paper_id": paper_id,
                    "source_file": path.name,
                }
            )
        sources.append(_input_source_payload(path, raw_bytes, "qa_patch"))

    deep_reads = []
    for paper_id in sorted(raw_by_id):
        deep_read = DeepRead.model_validate(raw_by_id[paper_id])
        validate_deep_read(deep_read)
        deep_reads.append(deep_read)

    pdfs: dict[str, dict[str, object]] = {}
    for raw_path in note_paths:
        path = Path(raw_path)
        raw_bytes = path.read_bytes()
        text = raw_bytes.decode("utf-8")
        for paper_id, pages, byte_size, sha256 in _parse_pdf_provenance_tables(text):
            candidate = {
                "byte_size": byte_size,
                "pages": pages,
                "paper_id": paper_id,
                "sha256": sha256,
            }
            if paper_id in pdfs and pdfs[paper_id] != candidate:
                raise ValueError(f"conflicting PDF provenance for {paper_id}")
            pdfs[paper_id] = candidate
        sources.append(_input_source_payload(path, raw_bytes, "chinese_source_notes"))
    for raw_path in review_paths:
        path = Path(raw_path)
        raw_bytes = path.read_bytes()
        sources.append(_input_source_payload(path, raw_bytes, "independent_qa_report"))
    if pdfs and set(pdfs) != award_ids:
        raise ValueError("PDF provenance does not cover the exact award inventory")

    verified_at = datetime.now(UTC).isoformat()
    verified_pdfs: dict[str, dict[str, object]] = {}
    owns_client = client is None
    active_client = client or httpx.Client()
    try:
        for paper_id in sorted(award_ids):
            source_url = award_pdf_urls[paper_id]
            pdf_bytes = fetch_bytes(source_url, active_client)
            _validate_complete_pdf(pdf_bytes, source_url)
            actual_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
            claimed = pdfs.get(paper_id)
            if claimed is None or (
                claimed["byte_size"] != len(pdf_bytes)
                or claimed["sha256"] != actual_sha256
            ):
                raise ValueError(
                    "claimed PDF provenance does not match verified official bytes: "
                    f"{paper_id}"
                )
            verified_pdfs[paper_id] = {
                "byte_size": len(pdf_bytes),
                "pages": claimed["pages"],
                "paper_id": paper_id,
                "sha256": actual_sha256,
                "source_url": source_url,
                "verification_method": "downloaded_official_pdf_bytes",
            }
    finally:
        if owns_client:
            active_client.close()

    _atomic_write(
        paths.award_deep_reads,
        yaml.safe_dump(
            {
                "deep_reads": [item.model_dump(mode="json") for item in deep_reads],
                "schema_version": "acl-award-deep-reads-v1",
            },
            allow_unicode=True,
            sort_keys=True,
        ).encode(),
    )
    _atomic_write(
        paths.award_deep_read_provenance,
        _json_bytes(
            {
                "deep_read_count": len(deep_reads),
                "patch_count": len(applied_patches),
                "patches": applied_patches,
                "pdf_verification": {
                    "method": "downloaded_official_pdf_bytes",
                    "verified_at": verified_at,
                },
                "pdfs": [verified_pdfs[paper_id] for paper_id in sorted(verified_pdfs)],
                "schema_version": "acl-award-deep-read-provenance-v1",
                "sources": sources,
            }
        ),
    )
    return deep_reads


def _input_source_payload(path: Path, raw_bytes: bytes, kind: str) -> dict[str, object]:
    return {
        "byte_size": len(raw_bytes),
        "kind": kind,
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "source_file": path.name,
    }


def _write_classification_manifest(
    paths: ScopePaths,
    *,
    assignments: Sequence[Assignment],
    assignments_sha256: str,
    review_status: LowConfidenceReviewStatus,
    queue_sha256: str,
    classifier: str = "deterministic-title-abstract-assisted-v1",
    semantic_labeling: Mapping[str, object] | None = None,
    audit_corrections: Mapping[str, object] | None = None,
    low_confidence_review_provenance: Mapping[str, object] | None = None,
    full_theme_reviews: Mapping[str, object] | None = None,
) -> None:
    review_state = (
        "pending_semantic_review"
        if review_status.pending_ids
        else "reviewed_with_rejections"
        if review_status.rejected_ids
        else "complete"
    )
    payload: dict[str, object] = {
        "classifier": classifier,
        "assignments_sha256": assignments_sha256,
        "input_fields": ["title", "abstract"],
        "low_confidence_ids": list(review_status.queued_ids),
        "low_confidence_review_queue_sha256": queue_sha256,
        "low_confidence_review_state": review_state,
        "paper_count": len(assignments),
        "pending_low_confidence_ids": list(review_status.pending_ids),
        "publication_status": "provisional_until_stratified_audit",
        "rejected_low_confidence_ids": list(review_status.rejected_ids),
        "reviewed_low_confidence_ids": list(review_status.reviewed_ids),
        "taxonomy_version": _TAXONOMY_VERSION,
    }
    if semantic_labeling is not None:
        payload["semantic_labeling"] = dict(semantic_labeling)
    if audit_corrections is not None:
        payload["audit_corrections"] = dict(audit_corrections)
    if low_confidence_review_provenance is not None:
        payload["low_confidence_review_provenance"] = dict(
            low_confidence_review_provenance
        )
    if full_theme_reviews is not None:
        payload["full_theme_reviews"] = dict(full_theme_reviews)
    _atomic_write(
        paths.classification / "classification-manifest.json",
        _json_bytes(payload),
    )


def _write_low_confidence_review_queue(
    paths: ScopePaths,
    records: Sequence[PaperRecord],
    assignments: Sequence[Assignment],
    *,
    assignments_sha256: str,
    reset_decisions: bool = False,
) -> tuple[LowConfidenceReviewStatus, str]:
    records_by_id = {record.paper_id: record for record in records}
    low_confidence = sorted(
        (
            assignment
            for assignment in assignments
            if assignment.confidence < Decimal("0.70")
        ),
        key=lambda item: item.paper_id,
    )
    queue_bytes = _json_bytes(
        {
            "assignments_sha256": assignments_sha256,
            "confidence_threshold": "0.70",
            "papers": [
                {
                    "abstract": records_by_id[item.paper_id].abstract,
                    "confidence": str(item.confidence),
                    "paper_id": item.paper_id,
                    "proposed_primary_topic": item.primary_topic,
                    "rationale": item.rationale,
                    "title": records_by_id[item.paper_id].title,
                }
                for item in low_confidence
            ],
            "schema_version": "low-confidence-review-queue-v1",
            "taxonomy_version": _TAXONOMY_VERSION,
        }
    )
    _atomic_write(paths.low_confidence_queue, queue_bytes)
    queue_sha256 = hashlib.sha256(queue_bytes).hexdigest()
    if reset_decisions or not paths.low_confidence_decisions.exists():
        _atomic_write(
            paths.low_confidence_decisions,
            _json_bytes(
                {
                    "queue_sha256": queue_sha256,
                    "reviews": [],
                    "schema_version": "low-confidence-review-decisions-v1",
                    "status": "pending_semantic_review",
                    "taxonomy_version": _TAXONOMY_VERSION,
                }
            ),
        )
    return _load_low_confidence_reviews(
        paths,
        assignments,
        assignments_sha256=assignments_sha256,
    )


def _load_low_confidence_reviews(
    paths: ScopePaths,
    assignments: Sequence[Assignment],
    *,
    assignments_sha256: str,
) -> tuple[LowConfidenceReviewStatus, str]:
    try:
        queue_bytes = paths.low_confidence_queue.read_bytes()
        queue = json.loads(queue_bytes)
        decisions = json.loads(paths.low_confidence_decisions.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid low-confidence review registry") from exc
    expected_ids = tuple(
        sorted(
            assignment.paper_id
            for assignment in assignments
            if assignment.confidence < Decimal("0.70")
        )
    )
    papers = queue.get("papers") if isinstance(queue, Mapping) else None
    if (
        not isinstance(papers, list)
        or queue.get("schema_version") != "low-confidence-review-queue-v1"
        or queue.get("taxonomy_version") != _TAXONOMY_VERSION
        or queue.get("assignments_sha256") != assignments_sha256
    ):
        raise ValueError("low-confidence review queue contract mismatch")
    queued_ids = tuple(
        item.get("paper_id")
        for item in papers
        if isinstance(item, Mapping) and isinstance(item.get("paper_id"), str)
    )
    if queued_ids != expected_ids:
        raise ValueError("low-confidence review queue does not cover every exact ID")
    queue_sha256 = hashlib.sha256(queue_bytes).hexdigest()
    reviews = decisions.get("reviews") if isinstance(decisions, Mapping) else None
    if (
        not isinstance(reviews, list)
        or decisions.get("schema_version") != "low-confidence-review-decisions-v1"
        or decisions.get("taxonomy_version") != _TAXONOMY_VERSION
        or decisions.get("queue_sha256") != queue_sha256
    ):
        raise ValueError("low-confidence decision registry contract mismatch")
    reviewed: dict[str, str] = {}
    for review in reviews:
        if not isinstance(review, Mapping):
            raise TypeError("low-confidence review decision must be an object")
        paper_id = review.get("paper_id")
        decision = review.get("decision")
        review_note = review.get("review_note")
        if (
            not isinstance(paper_id, str)
            or paper_id not in expected_ids
            or paper_id in reviewed
            or decision not in {"accept", "reject"}
            or not isinstance(review_note, str)
            or not review_note.strip()
        ):
            raise ValueError("invalid or duplicate low-confidence review decision")
        reviewed[paper_id] = str(decision)
    accepted_ids = tuple(
        sorted(key for key, value in reviewed.items() if value == "accept")
    )
    rejected_ids = tuple(
        sorted(key for key, value in reviewed.items() if value == "reject")
    )
    pending_ids = tuple(sorted(set(expected_ids) - set(reviewed)))
    return (
        LowConfidenceReviewStatus(
            queued_ids=expected_ids,
            accepted_ids=accepted_ids,
            rejected_ids=rejected_ids,
            pending_ids=pending_ids,
        ),
        queue_sha256,
    )


def _write_audit_samples(
    paths: ScopePaths,
    records: Sequence[PaperRecord],
    assignments: Sequence[Assignment],
    *,
    reset_decisions: bool = False,
) -> None:
    records_by_id = {record.paper_id: record for record in records}
    grouped: dict[str, list[Assignment]] = {}
    for assignment in assignments:
        grouped.setdefault(assignment.primary_topic, []).append(assignment)
    samples: dict[str, list[dict[str, object]]] = {}
    for theme, theme_assignments in sorted(grouped.items()):
        ordered = sorted(
            theme_assignments,
            key=lambda item: (item.confidence, item.paper_id),
        )
        if len(ordered) <= 50:
            selected = ordered
        else:
            indices = [round(index * (len(ordered) - 1) / 49) for index in range(50)]
            selected = [ordered[index] for index in indices]
        samples[theme] = [
            {
                "abstract": records_by_id[item.paper_id].abstract,
                "confidence": str(item.confidence),
                "correct": None,
                "paper_id": item.paper_id,
                "proposed_primary_topic": item.primary_topic,
                "rationale": item.rationale,
                "review_note": None,
                "title": records_by_id[item.paper_id].title,
            }
            for item in selected
        ]
    _atomic_write(
        paths.classification / "audit-samples.json",
        _json_bytes(
            {
                "sampling": (
                    "deterministic confidence-stratified sample of up to 50 per primary theme"
                ),
                "taxonomy_version": _TAXONOMY_VERSION,
                "themes": samples,
            }
        ),
    )
    decisions_path = paths.classification / "audit-decisions.json"
    if reset_decisions or not decisions_path.exists():
        _atomic_write(
            decisions_path,
            _json_bytes(
                {
                    "method": (
                        "no completed semantic reviews; candidate labels remain "
                        "experimental"
                    ),
                    "schema_version": "classification-audit-v1",
                    "status": "pending_semantic_review",
                    "taxonomy_version": _TAXONOMY_VERSION,
                    "themes": {theme: [] for theme in sorted(samples)},
                }
            ),
        )


def _load_theme_audits(
    paths: ScopePaths,
    assignments: Sequence[Assignment],
    low_confidence_review: LowConfidenceReviewStatus,
) -> tuple[dict[str, ThemeAudit], list[ThemeDisclosure], dict[str, object]]:
    themes = sorted({assignment.primary_topic for assignment in assignments})
    try:
        sample_registry = json.loads(
            (paths.classification / "audit-samples.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid audit sample registry") from exc
    sample_themes = (
        sample_registry.get("themes") if isinstance(sample_registry, Mapping) else None
    )
    if not isinstance(sample_themes, Mapping):
        raise TypeError("audit sample registry must contain theme candidates")
    candidate_ids: dict[str, set[str]] = {}
    candidate_counts: dict[str, int] = {}
    for theme in themes:
        candidates = sample_themes.get(theme)
        if not isinstance(candidates, list):
            raise TypeError(f"audit sample registry is missing {theme}")
        ids = {
            item.get("paper_id")
            for item in candidates
            if isinstance(item, Mapping) and isinstance(item.get("paper_id"), str)
        }
        if len(ids) != len(candidates) or len(candidates) > 50:
            raise ValueError(f"invalid audit sample candidates for {theme}")
        candidate_ids[theme] = ids
        candidate_counts[theme] = len(ids)
    decisions_path = paths.classification / "audit-decisions.json"
    raw_themes: Mapping[str, object] = {}
    audit_method = "no completed semantic reviews; themes retained as experimental"
    if decisions_path.exists():
        try:
            decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid audit decision registry") from exc
        if (
            not isinstance(decisions, Mapping)
            or decisions.get("taxonomy_version") != _TAXONOMY_VERSION
        ):
            raise ValueError("audit decision taxonomy version mismatch")
        candidate_themes = decisions.get("themes")
        if not isinstance(candidate_themes, Mapping):
            raise ValueError("audit decision registry must contain theme reviews")
        raw_themes = candidate_themes
        audit_method = str(
            decisions.get("method") or "explicit semantic review of title and abstract"
        )

    ids_by_theme: dict[str, set[str]] = {}
    low_confidence_ids_by_theme: dict[str, set[str]] = {}
    for assignment in assignments:
        ids_by_theme.setdefault(assignment.primary_topic, set()).add(
            assignment.paper_id
        )
        if assignment.paper_id in low_confidence_review.queued_ids:
            low_confidence_ids_by_theme.setdefault(assignment.primary_topic, set()).add(
                assignment.paper_id
            )
    audits: dict[str, ThemeAudit] = {}
    review_counts: dict[str, int] = {}
    disclosures: list[ThemeDisclosure] = []
    volume_url = "https://aclanthology.org/volumes/2026.acl-long/"
    for theme in themes:
        raw_reviews = raw_themes.get(theme, [])
        if not isinstance(raw_reviews, list):
            raise TypeError(f"audit reviews for {theme} must be a list")
        if len(raw_reviews) > 50:
            raise ValueError(f"audit reviews for {theme} exceed the 50-paper cap")
        seen_ids: set[str] = set()
        decisions_for_theme: list[bool] = []
        for raw_review in raw_reviews:
            if not isinstance(raw_review, Mapping):
                raise TypeError(f"audit review for {theme} must be an object")
            paper_id = raw_review.get("paper_id")
            correct = raw_review.get("correct")
            if (
                not isinstance(paper_id, str)
                or paper_id not in ids_by_theme[theme]
                or paper_id not in candidate_ids[theme]
                or paper_id in seen_ids
                or type(correct) is not bool
            ):
                raise ValueError(f"invalid or duplicate audit decision for {theme}")
            seen_ids.add(paper_id)
            decisions_for_theme.append(correct)
        audit = audit_theme(decisions_for_theme)
        audits[theme] = audit
        review_counts[theme] = len(decisions_for_theme)
        theme_low_confidence = low_confidence_ids_by_theme.get(theme, set())
        theme_pending = theme_low_confidence.intersection(
            low_confidence_review.pending_ids
        )
        theme_rejected = theme_low_confidence.intersection(
            low_confidence_review.rejected_ids
        )
        try:
            assert_theme_publishable(
                audit,
                low_confidence_review_complete=not theme_pending,
                rejected_low_confidence_count=len(theme_rejected),
            )
        except PublicationBlocked:
            disclosures.append(
                ThemeDisclosure(
                    theme=theme,
                    status=ThemeDisclosureStatus.EXPERIMENTAL,
                    reason=EvidenceClaim(
                        claim=(
                            "This assisted primary theme does not satisfy every "
                            "stratified-audit and exhaustive low-confidence review "
                            "gate and is excluded from headline claims."
                        ),
                        evidence_type=EvidenceType.INFERENCE,
                        source_urls=[volume_url],
                        locator=(
                            "data/classification/acl/2026-long/audit-decisions.json"
                        ),
                    ),
                )
            )
    return (
        audits,
        disclosures,
        {
            "candidate_counts": candidate_counts,
            "method": audit_method,
            "low_confidence_review": {
                "pending_count": len(low_confidence_review.pending_ids),
                "rejected_count": len(low_confidence_review.rejected_ids),
                "reviewed_count": len(low_confidence_review.reviewed_ids),
                "theme_complete": {
                    theme: not bool(
                        low_confidence_ids_by_theme.get(theme, set()).intersection(
                            low_confidence_review.pending_ids
                        )
                    )
                    for theme in themes
                },
                "total_count": len(low_confidence_review.queued_ids),
            },
            "pending_counts": {
                theme: candidate_counts[theme] - review_counts[theme]
                for theme in themes
            },
            "review_counts": review_counts,
        },
    )


_ADVANCE_TOPICS: dict[AdvanceCategory, tuple[str, ...]] = {
    AdvanceCategory.TEXT_LLMS: ("Foundation Models",),
    AdvanceCategory.MULTIMODAL_MODELS: ("Multimodal Models",),
    AdvanceCategory.REASONING_AGENTS: ("Reasoning and Agents",),
    AdvanceCategory.DATA_TRAINING: (
        "Data and Retrieval",
        "Learning and Optimization",
    ),
    AdvanceCategory.EVALUATION_TRUST: ("Evaluation", "Trustworthiness"),
}


def _preliminary_examples(
    records: Sequence[PaperRecord],
    assignments: Sequence[Assignment],
    audits: Mapping[str, ThemeAudit] | None = None,
) -> list[AdvanceRecord]:
    records_by_id = {record.paper_id: record for record in records}
    advances: list[AdvanceRecord] = []
    for category, topics in _ADVANCE_TOPICS.items():
        candidates = sorted(
            (
                assignment
                for assignment in assignments
                if assignment.primary_topic in topics
            ),
            key=lambda item: (-item.confidence, item.paper_id),
        )[:5]
        if not candidates:
            continue
        sources = [records_by_id[item.paper_id].landing_url for item in candidates]
        audited = audits is not None and all(
            topic in audits
            and audits[topic].sample_size > 0
            and audits[topic].observed_precision >= Decimal("0.90")
            and audits[topic].wilson_lower_95 >= Decimal("0.80")
            for topic in topics
        )
        first = records_by_id[candidates[0].paper_id]
        if audited:
            claims = (
                EvidenceClaim(
                    claim=(
                        f"{first.title} reports the method and findings summarized in "
                        "its official abstract; any quantitative result remains a "
                        "paper-reported claim rather than an independent replication."
                    ),
                    evidence_type=EvidenceType.PAPER_REPORTED,
                    source_urls=[first.landing_url],
                    locator=f"ACL Anthology abstract: {first.paper_id.removeprefix('acl:')}",
                ),
                EvidenceClaim(
                    claim=(
                        "These named papers form a bounded cross-paper synthesis within "
                        "audit-passed primary themes; the set illustrates the lane but "
                        "does not claim semantic representativeness or temporal trend."
                    ),
                    evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                    source_urls=sources,
                    locator="official ACL titles and abstracts for the linked papers",
                ),
                EvidenceClaim(
                    claim=(
                        "A practical implication is to evaluate this lane as a coupled "
                        "data, method, and measurement system; this interpretation goes "
                        "beyond any single paper's reported result."
                    ),
                    evidence_type=EvidenceType.INFERENCE,
                    source_urls=sources,
                    locator="inference from the linked ACL paper abstracts",
                ),
            )
            advance_id = f"audited-evidence-{category.value}"
            title = f"Audited {category.value.replace('_', ' ')} evidence examples"
        else:
            claims = (
                EvidenceClaim(
                    claim=(
                        "These examples are selected deterministically by confidence "
                        "and ACL ID from experimental primary-topic assignments; they "
                        "make no semantic representativeness or lane-purity claim, trend "
                        "claim, or paper-result claim."
                    ),
                    evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                    source_urls=sources,
                    locator="official ACL title and abstract metadata",
                ),
            )
            advance_id = f"preliminary-examples-{category.value}"
            title = f"Preliminary {category.value.replace('_', ' ')} examples"
        advances.append(
            AdvanceRecord(
                advance_id=advance_id,
                title=title,
                category=category,
                supporting_paper_ids=tuple(item.paper_id for item in candidates),
                claims=claims,
            )
        )
    return advances


def _load_award_records(paths: ScopePaths) -> list[AwardRecord]:
    try:
        inventory = yaml.safe_load(paths.awards.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("invalid official award inventory") from exc
    awards = inventory.get("awards") if isinstance(inventory, Mapping) else None
    if not isinstance(awards, list):
        raise TypeError("official award inventory has no awards list")
    return [
        AwardRecord(
            paper_id=str(award["paper_id"]),
            award_type=str(award["award_type"]),
            status=AwardStatus.VERIFIED,
            evidence_url=str(award["evidence_url"]),
        )
        for award in awards
    ]


def _load_award_deep_reads(paths: ScopePaths) -> list[DeepRead]:
    if not paths.award_deep_reads.exists():
        return []
    try:
        payload = yaml.safe_load(paths.award_deep_reads.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ValueError("invalid award deep-read artifact") from exc
    items = payload.get("deep_reads") if isinstance(payload, Mapping) else None
    if not isinstance(items, list):
        raise TypeError("award deep-read artifact has no deep_reads list")
    deep_reads = [DeepRead.model_validate(item) for item in items]
    for deep_read in deep_reads:
        validate_deep_read(deep_read)
    try:
        provenance = json.loads(
            paths.award_deep_read_provenance.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "award deep reads require verified official PDF provenance"
        ) from exc
    verification = (
        provenance.get("pdf_verification") if isinstance(provenance, Mapping) else None
    )
    pdfs = provenance.get("pdfs") if isinstance(provenance, Mapping) else None
    if (
        not isinstance(verification, Mapping)
        or verification.get("method") != "downloaded_official_pdf_bytes"
        or not isinstance(verification.get("verified_at"), str)
        or not isinstance(pdfs, list)
    ):
        raise ValueError("award deep reads require verified official PDF provenance")
    try:
        verified_at = datetime.fromisoformat(str(verification["verified_at"]))
    except ValueError as exc:
        raise ValueError(
            "award deep reads require verified official PDF provenance"
        ) from exc
    if verified_at.tzinfo is None:
        raise ValueError("award deep reads require verified official PDF provenance")
    expected_ids = {item.paper_id for item in deep_reads}
    verified_ids: set[str] = set()
    for pdf in pdfs:
        if not isinstance(pdf, Mapping):
            raise TypeError("award deep reads require verified official PDF provenance")
        paper_id = pdf.get("paper_id")
        expected_url = (
            f"https://aclanthology.org/{paper_id.removeprefix('acl:')}.pdf"
            if isinstance(paper_id, str)
            else None
        )
        if (
            not isinstance(paper_id, str)
            or paper_id in verified_ids
            or pdf.get("verification_method") != "downloaded_official_pdf_bytes"
            or pdf.get("source_url") != expected_url
            or not isinstance(pdf.get("byte_size"), int)
            or pdf["byte_size"] <= 0
            or not isinstance(pdf.get("sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", str(pdf["sha256"])) is None
        ):
            raise ValueError(
                "award deep reads require verified official PDF provenance"
            )
        verified_ids.add(paper_id)
    if verified_ids != expected_ids:
        raise ValueError("award deep reads require verified official PDF provenance")
    return deep_reads


def _overview_note(
    *,
    validation: ValidationReport,
    records: Sequence[PaperRecord],
    sources: Sequence[SourceRef],
    assignments: Sequence[Assignment],
    audits: Mapping[str, ThemeAudit],
    audit_metadata: Mapping[str, object],
    advances: Sequence[AdvanceRecord],
    award_count: int,
    award_deep_read_count: int,
    classifier: str,
) -> bytes:
    counts: dict[str, int] = {}
    for assignment in assignments:
        counts[assignment.primary_topic] = counts.get(assignment.primary_topic, 0) + 1
    records_by_id = {record.paper_id: record for record in records}
    lines = [
        "# ACL 2026 Long Papers：最终证据边界综览",
        "",
        (
            "本文只描述 ACL 2026 long-paper 的单年分布与热点（one-year "
            "distribution, not a trend），不把单年占比写成跨年趋势。"
        ),
        "",
        "## 范围、覆盖与官方来源",
        "",
        (
            f"- 官方卷共发现 {validation.discovered_count} 条记录；纳入 "
            f"{validation.included_count} 篇 long paper，另有 {validation.excluded_count} "
            "条 proceedings front matter 单独排除。定位：官方卷页与 BibTeX 的双向 ID 对账。"
        ),
        (
            f"- 摘要缺失 {len(validation.missing_abstract_ids)} 篇（"
            f"{', '.join(validation.missing_abstract_ids) or '无'}）；PDF 缺失 "
            f"{len(validation.missing_pdf_ids)} 篇；DOI 缺失 {len(validation.missing_doi_ids)} "
            "篇。定位：`data/analysis/acl/2026-long/validation.json`。"
        ),
        "- 官方入口：<https://aclanthology.org/volumes/2026.acl-long/>。",
        "",
        "| 官方源 | 抓取时间（UTC） | SHA-256 |",
        "|---|---|---|",
    ]
    for source in sources:
        lines.append(
            f"| [{source.name}]({source.url}) | {source.retrieved_at.isoformat() if source.retrieved_at else '未记录'} | "
            f"`{source.sha256 or '未记录'}` |"
        )
    lines.extend(
        [
        "",
        "## 分类方法、审计门槛与限制",
        "",
        (
            "分类采用 agent semantic batch review：逐篇读取官方 title + abstract，给出单一 "
            "primary topic；随后经历独立审计修正和全主题复核。最终认证对每个主题使用固定、"
            "确定性的置信度分层样本（最多 50 篇），门槛同时要求 observed precision ≥ 0.90 "
            "且双侧 Wilson 95% 下界 ≥ 0.80。审计中的 false 只测量标签精度，不回写 topic。"
        ),
        (
            "限制：taxonomy 是分析框架而非 ACL 官方 track；一篇论文只能有一个 primary topic，"
            "会压缩跨主题贡献；摘要审计不替代全文复核；样本较小的主题受 Wilson 下界约束。"
        ),
        "",
        "## 十主题单年分布与最终审计",
        "",
        "| 主题 | 论文数 | 占比 | 审计正确/样本 | Precision | Wilson 95% 下界 | 状态 |",
        "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    candidate_counts = audit_metadata["candidate_counts"]
    review_counts = audit_metadata["review_counts"]
    if not isinstance(candidate_counts, Mapping) or not isinstance(
        review_counts, Mapping
    ):
        raise TypeError("audit metadata is missing candidate or review counts")
    for theme, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        audit = audits[theme]
        passes = (
            audit.sample_size > 0
            and audit.observed_precision >= Decimal("0.90")
            and audit.wilson_lower_95 >= Decimal("0.80")
        )
        lines.append(
            f"| {theme} | {count} | {count / validation.included_count:.2%} | "
            f"{audit.correct_count}/{audit.sample_size} | {audit.observed_precision:.4f} | "
            f"{audit.wilson_lower_95:.6f} | {'通过' if passes else '实验性 / withheld'} |"
        )
    lines.extend(
        [
            "",
            "## 可进入 headline 的八个主题",
            "",
            (
                "只有通过双门槛的 Applications、Data and Retrieval、Evaluation、Foundation "
                "Models、Learning and Optimization、Multimodal Models、NLP/CV Core Tasks "
                "和 Trustworthiness 可用于正式热点陈述。Reasoning and Agents（44/50，"
                "0.8800，Wilson 0.761952）与 Multilingual and Inclusive NLP（12/14，"
                "0.8571，Wilson 0.600586）只保留为实验性观察，不进入 headline。"
            ),
            "",
            "## 五条 advances 证据链",
            "",
        ]
    )
    advance_by_category = {advance.category: advance for advance in advances}
    for category in _ADVANCE_TOPICS:
        advance = advance_by_category.get(category)
        if advance is None:
            lines.append(
                f"- **{category.value}**: no evidence-supported shortlist in the "
                "current primary-topic assignments."
            )
        else:
            first = records_by_id[advance.supporting_paper_ids[0]]
            state = "已审计综合" if advance.advance_id.startswith("audited-") else "实验性观察"
            lines.append(f"- **{category.value}（{state}）**：[{first.title}]({first.landing_url})。")
            for claim in advance.claims:
                label = {
                    EvidenceType.PAPER_REPORTED: "论文明确披露",
                    EvidenceType.CROSS_PAPER_SYNTHESIS: "跨论文综合",
                    EvidenceType.INFERENCE: "推断",
                }.get(claim.evidence_type, "官方元数据")
                lines.append(
                    f"  - `{label}`：{claim.claim} 定位：{claim.locator or '链接页'}。"
                )
    lines.extend(
        [
            "",
            "## 面向五类研发问题的特殊含义",
            "",
            "- Text LLM：把长上下文、预训练条件化、效率与可解释性放在同一评估面板中。",
            "- Multimodal：重点检查跨模态组合性、时序交互与 judge bias，而不只看静态 VQA。",
            "- Agents：Reasoning 主题未过审计门槛，因此工具调用、浏览器控制和控制器结果只作实验性线索。",
            "- Data / Training：联合追踪数据结构、训练/合并策略、推理成本与部署约束。",
            "- Evaluation / Safety：动态评测、污染、judge 可靠性与多模态攻击面应成为共同 guardrail。",
            "",
            "## 官方奖项与详细阅读",
            "",
            f"- 官方卷页识别并绑定 {award_count} 条 award badge。定位：官方 ACL volume page。",
            (
                f"- 已完成并通过 schema/PDF provenance gate 的详细阅读 {award_deep_read_count} 条；"
                "参见 [ACL 2026 获奖论文详细阅读](./acl-2026-awards-deep-reads.md) 和站点 `/awards/`。"
            ),
            "",
        ]
    )
    return "\n".join(lines).encode()


def _load_classification_provenance(
    paths: ScopePaths, assignments_sha256: str
) -> tuple[
    str,
    Mapping[str, object] | None,
    Mapping[str, object] | None,
    Mapping[str, object] | None,
    Mapping[str, object] | None,
]:
    try:
        manifest = json.loads(
            (paths.classification / "classification-manifest.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid classification manifest") from exc
    if not isinstance(manifest, Mapping):
        raise TypeError("classification manifest must be an object")
    if manifest.get("assignments_sha256") != assignments_sha256:
        raise ValueError("classification manifest does not match assignments")
    classifier = manifest.get("classifier")
    if not isinstance(classifier, str) or not classifier.strip():
        raise ValueError("classification manifest has no classifier provenance")
    semantic_labeling = manifest.get("semantic_labeling")
    if semantic_labeling is not None and not isinstance(semantic_labeling, Mapping):
        raise TypeError("semantic labeling provenance must be an object")
    if classifier == "agent-semantic-batch-review-v1" and semantic_labeling is None:
        raise ValueError("agent semantic classification has no source provenance")
    audit_corrections = manifest.get("audit_corrections")
    low_review_provenance = manifest.get("low_confidence_review_provenance")
    full_theme_reviews = manifest.get("full_theme_reviews")
    if audit_corrections is not None and not isinstance(audit_corrections, Mapping):
        raise TypeError("audit correction provenance must be an object")
    if low_review_provenance is not None and not isinstance(
        low_review_provenance, Mapping
    ):
        raise TypeError("low-confidence review provenance must be an object")
    if full_theme_reviews is not None and not isinstance(full_theme_reviews, Mapping):
        raise TypeError("full-theme review provenance must be an object")
    return (
        classifier,
        semantic_labeling,
        audit_corrections,
        low_review_provenance,
        full_theme_reviews,
    )


def analyze_acl_scope(
    request: VenueRequest,
    root: Path,
    *,
    write_release: bool = False,
) -> dict[str, object]:
    """Validate topic labels, audits, awards, and write preliminary synthesis."""
    paths = ScopePaths(Path(root))
    validation = validate_acl_scope(request, root)
    assert_publishable(validation)
    records, excluded, sources = load_scope_records(request, root)
    assignment_path = paths.classification / "assignments.jsonl"
    if not assignment_path.exists():
        assisted_classify_scope(request, root)
    assignments = load_assignments(
        assignment_path,
        load_taxonomy(),
        expected_paper_ids=(record.paper_id for record in records),
    )
    assignment_bytes = assignment_path.read_bytes()
    assignments_sha256 = hashlib.sha256(assignment_bytes).hexdigest()
    (
        classifier,
        semantic_labeling,
        audit_corrections,
        low_review_provenance,
        full_theme_reviews,
    ) = _load_classification_provenance(paths, assignments_sha256)
    if not paths.low_confidence_queue.exists():
        low_confidence_review, queue_sha256 = _write_low_confidence_review_queue(
            paths,
            records,
            assignments,
            assignments_sha256=assignments_sha256,
        )
    else:
        low_confidence_review, queue_sha256 = _load_low_confidence_reviews(
            paths,
            assignments,
            assignments_sha256=assignments_sha256,
        )
    _write_classification_manifest(
        paths,
        assignments=assignments,
        assignments_sha256=assignments_sha256,
        review_status=low_confidence_review,
        queue_sha256=queue_sha256,
        classifier=classifier,
        semantic_labeling=semantic_labeling,
        audit_corrections=audit_corrections,
        low_confidence_review_provenance=low_review_provenance,
        full_theme_reviews=full_theme_reviews,
    )
    audits, disclosures, audit_metadata = _load_theme_audits(
        paths, assignments, low_confidence_review
    )
    if not paths.awards.exists():
        parse_award_inventory_scope(request, root)
    awards = _load_award_records(paths)
    award_deep_reads = _load_award_deep_reads(paths)
    advances = _preliminary_examples(records, assignments, audits)
    topic_counts: dict[str, int] = {}
    for assignment in assignments:
        topic_counts[assignment.primary_topic] = (
            topic_counts.get(assignment.primary_topic, 0) + 1
        )
    metrics = {
        f"topic_share:{theme}": topic_share(
            topic_count=count,
            included_count=validation.included_count,
        )
        for theme, count in topic_counts.items()
    }
    generated_at = datetime.now(UTC)
    claims = (
        EvidenceClaim(
            claim=(
                "The official ACL long-paper records support a one-year distribution "
                "and hotspot view only; they do not establish a trend."
            ),
            evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
            source_urls=[str(request.volume_url)],
            locator="ACL 2026 Volume 1 long-paper corpus manifest",
        ),
    )
    bundle = ReleaseBundle(
        records=records,
        excluded_records=excluded,
        validation=validation,
        taxonomy_version=_TAXONOMY_VERSION,
        generated_at=generated_at,
        assignments=assignments,
        audits=audits,
        low_confidence_ids=low_confidence_review.queued_ids,
        reviewed_low_confidence_ids=low_confidence_review.reviewed_ids,
        rejected_low_confidence_ids=low_confidence_review.rejected_ids,
        metrics=metrics,
        awards=awards,
        award_deep_reads=award_deep_reads,
        advances=advances,
        theme_disclosures=disclosures,
        claims=claims,
        sources=sources,
    )
    summary: dict[str, object] = {
        "advance_lane_count": len(advances),
        "audit": audit_metadata,
        "award_inventory_count": len(awards),
        "award_deep_read_count": len(award_deep_reads),
        "classification": {
            "classifier": classifier,
            "semantic_labeling": semantic_labeling,
        },
        "included_count": validation.included_count,
        "language": "distribution_or_hotspot_not_trend",
        "theme_counts": dict(sorted(topic_counts.items())),
        "withheld_themes": sorted(disclosure.theme for disclosure in disclosures),
    }
    _atomic_write(paths.analysis / "preliminary-analysis.json", _json_bytes(summary))
    _atomic_write(
        paths.notes,
        _overview_note(
            validation=validation,
            records=records,
            sources=sources,
            assignments=assignments,
            audits=audits,
            audit_metadata=audit_metadata,
            advances=advances,
            award_count=len(awards),
            award_deep_read_count=len(award_deep_reads),
            classifier=classifier,
        ),
    )
    if write_release:
        publish_release(bundle, paths.release)
    return summary


def build_site_scope(
    root: Path,
    *,
    release_dir: Path | None = None,
    site_dir: Path | None = None,
) -> Path:
    """Build the Astro site only from the selected validated ACL release."""
    paths = ScopePaths(Path(root).resolve())
    selected_release = (
        Path(release_dir).resolve() if release_dir is not None else paths.release
    )
    resolve_current_release(selected_release)
    selected_site = (
        Path(site_dir).resolve() if site_dir is not None else paths.root / "site"
    )
    release_root = selected_release.parent.parent
    environment = dict(os.environ)
    environment["CONFERENCE_RELEASE_ROOT"] = str(release_root)
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd=selected_site,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Astro site build failed: {detail}")
    dist = selected_site / "dist"
    conference_route = dist / "conferences/acl/2026/index.html"
    if not conference_route.is_file():
        raise RuntimeError("Astro build omitted the validated ACL conference route")
    return dist


def parse_award_inventory_scope(
    request: VenueRequest, root: Path
) -> list[dict[str, object]]:
    """Parse only official volume-page award badges; never inspect paper PDFs."""
    paths = ScopePaths(Path(root))
    manifest = _load_manifest(request, root)
    included, _excluded, sources = load_scope_records(request, root)
    source_payloads = manifest["sources"]
    html_payload = next(
        source for source in source_payloads if source["kind"] == "html"
    )  # type: ignore[union-attr]
    html = (paths.root / html_payload["snapshot_path"]).read_bytes()
    html_source = next(
        source for source in sources if str(source.url) == str(request.volume_url)
    )
    badges = parse_acl_award_badges(html, html_source)
    papers = {record.paper_id.removeprefix("acl:"): record for record in included}
    inventory: list[dict[str, object]] = []
    for badge in badges:
        paper = papers.get(badge["acl_id"])
        if paper is None:
            raise ValueError(
                f"official award badge refers to unknown paper {badge['acl_id']}"
            )
        inventory.append(
            {
                "acl_paper_id": badge["acl_id"],
                "award_type": badge["award_type"],
                "evidence_locator": badge["evidence_locator"],
                "evidence_url": str(request.volume_url),
                "landing_url": str(paper.landing_url),
                "paper_id": paper.paper_id,
                "pdf_url": str(paper.pdf_url) if paper.pdf_url is not None else None,
                "title": paper.title,
            }
        )
    inventory.sort(key=lambda item: (str(item["award_type"]), str(item["paper_id"])))
    payload = {
        "awards": inventory,
        "deep_reads": [],
        "scope": {"track": "long", "venue": "ACL", "year": 2026},
        "source": html_payload,
        "status": "official_inventory_complete_deep_reads_pending",
    }
    _atomic_write(
        paths.awards,
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=True).encode(),
    )
    return inventory
