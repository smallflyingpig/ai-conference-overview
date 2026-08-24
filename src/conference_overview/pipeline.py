"""Evidence-bounded orchestration for the ACL 2026 long-paper reference run."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
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
from conference_overview.awards import AwardRecord, AwardStatus
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
    included, excluded = parse_acl_bibtex(bibtex, request, bib_source)
    enriched = enrich_acl_abstracts(included, html, html_source)

    expected_acl_ids = {record.paper_id.removeprefix("acl:") for record in enriched}
    html_acl_ids = {
        match.decode("ascii") for match in _HTML_PAPER_ID_PATTERN.findall(html)
    }
    missing_html_ids = sorted(expected_acl_ids - html_acl_ids)
    if missing_html_ids:
        raise AclSourceFormatError(
            source=html_source,
            detail=(
                "volume HTML is incomplete; missing exact ACL IDs: "
                f"{missing_html_ids[:10]}"
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
    low_confidence = [
        assignment.paper_id
        for assignment in assignments
        if assignment.confidence < Decimal("0.70")
    ]
    _atomic_write(
        paths.classification / "classification-manifest.json",
        _json_bytes(
            {
                "classifier": "deterministic-title-abstract-assisted-v1",
                "assignments_sha256": hashlib.sha256(assignment_bytes).hexdigest(),
                "input_fields": ["title", "abstract"],
                "low_confidence_ids": low_confidence,
                "low_confidence_review_state": "pending_semantic_review",
                "paper_count": len(assignments),
                "publication_status": "provisional_until_stratified_audit",
                "reviewed_low_confidence_ids": [],
                "taxonomy_version": _TAXONOMY_VERSION,
            }
        ),
    )
    _write_audit_samples(paths, included, assignments)
    return assignments


def _write_audit_samples(
    paths: ScopePaths,
    records: Sequence[PaperRecord],
    assignments: Sequence[Assignment],
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
    if not decisions_path.exists():
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
) -> tuple[dict[str, ThemeAudit], list[ThemeDisclosure], dict[str, object]]:
    themes = sorted({assignment.primary_topic for assignment in assignments})
    try:
        sample_registry = json.loads(
            (paths.classification / "audit-samples.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid audit sample registry") from exc
    sample_themes = (
        sample_registry.get("themes")
        if isinstance(sample_registry, Mapping)
        else None
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
    for assignment in assignments:
        ids_by_theme.setdefault(assignment.primary_topic, set()).add(
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
        try:
            assert_theme_publishable(audit)
        except PublicationBlocked:
            disclosures.append(
                ThemeDisclosure(
                    theme=theme,
                    status=ThemeDisclosureStatus.EXPERIMENTAL,
                    reason=EvidenceClaim(
                        claim=(
                            "This assisted primary theme does not satisfy both the "
                            "declared observed-precision and Wilson audit gates and is "
                            "excluded from headline claims."
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


def _preliminary_advances(
    records: Sequence[PaperRecord],
    assignments: Sequence[Assignment],
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
        advances.append(
            AdvanceRecord(
                advance_id=f"preliminary-{category.value}",
                title=f"Preliminary {category.value.replace('_', ' ')} shortlist",
                category=category,
                supporting_paper_ids=tuple(item.paper_id for item in candidates),
                claims=(
                    EvidenceClaim(
                        claim=(
                            "This shortlist groups title-and-abstract evidence within a "
                            "single ACL release; it is preliminary synthesis, not a trend "
                            "or a paper-result claim."
                        ),
                        evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                        source_urls=sources,
                        locator="official ACL title and abstract metadata",
                    ),
                ),
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


def _overview_note(
    *,
    validation: ValidationReport,
    assignments: Sequence[Assignment],
    audits: Mapping[str, ThemeAudit],
    audit_metadata: Mapping[str, object],
    advances: Sequence[AdvanceRecord],
    award_count: int,
) -> bytes:
    counts: dict[str, int] = {}
    for assignment in assignments:
        counts[assignment.primary_topic] = counts.get(assignment.primary_topic, 0) + 1
    lines = [
        "# ACL 2026 long-paper preliminary overview",
        "",
        (
            "This is a one-year distribution and hotspot snapshot, not a trend. "
            "Topic labels are deterministic assisted proposals and remain subject "
            "to the published stratified audit gates."
        ),
        "",
        "## Official corpus reconciliation",
        "",
        f"- Discovered: {validation.discovered_count}",
        f"- Included long papers: {validation.included_count}",
        f"- Excluded front matter: {validation.excluded_count}",
        f"- Missing abstracts: {len(validation.missing_abstract_ids)}",
        f"- Missing PDFs: {len(validation.missing_pdf_ids)}",
        f"- Missing DOIs: {len(validation.missing_doi_ids)}",
        "- Official source: <https://aclanthology.org/volumes/2026.acl-long/>",
        "",
        "## Preliminary primary-topic distribution",
        "",
        "| Primary topic | Papers | Share | Audit candidates | Reviewed | Audit state |",
        "|---|---:|---:|---:|---:|---|",
    ]
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
            f"{candidate_counts[theme]} | {review_counts[theme]} | "
            f"{'passed' if passes else 'experimental / withheld'} |"
        )
    lines.extend(
        [
            "",
            "## Five advances lanes handoff",
            "",
        ]
    )
    advance_by_category = {advance.category: advance for advance in advances}
    for category in _ADVANCE_TOPICS:
        advance = advance_by_category.get(category)
        if advance is None:
            lines.append(
                f"- **{category.value}**: no evidence-supported shortlist in the "
                "current assisted assignments."
            )
        else:
            lines.append(
                f"- **{category.value}**: {len(advance.supporting_paper_ids)} "
                "representative official paper links are retained in the release."
            )
    lines.extend(
        [
            "",
            "## Official award inventory",
            "",
            f"- Official volume-page award badges: {award_count}",
            "- Award PDF deep reads: pending controller handoff; no PDF-derived claim is included.",
            "",
        ]
    )
    return "\n".join(lines).encode()


def analyze_acl_scope(
    request: VenueRequest,
    root: Path,
    *,
    write_release: bool = False,
) -> dict[str, object]:
    """Validate assisted labels, audits, awards, and write preliminary synthesis."""
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
    audits, disclosures, audit_metadata = _load_theme_audits(paths, assignments)
    if not paths.awards.exists():
        parse_award_inventory_scope(request, root)
    awards = _load_award_records(paths)
    advances = _preliminary_advances(records, assignments)
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
    generated_at = max(
        source.retrieved_at for source in sources if source.retrieved_at is not None
    )
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
        metrics=metrics,
        awards=awards,
        award_deep_reads=(),
        advances=advances,
        theme_disclosures=disclosures,
        claims=claims,
        sources=sources,
    )
    summary: dict[str, object] = {
        "advance_lane_count": len(advances),
        "audit": audit_metadata,
        "award_inventory_count": len(awards),
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
            assignments=assignments,
            audits=audits,
            audit_metadata=audit_metadata,
            advances=advances,
            award_count=len(awards),
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
