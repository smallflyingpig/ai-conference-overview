"""Deterministic, publication-gated conference release artifacts."""

from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import TypeAlias

from conference_overview.awards import AwardRecord
from conference_overview.classification import (
    Assignment,
    ThemeAudit,
    assert_theme_publishable,
)
from conference_overview.metrics import CrossVenueSpread, EmergingScore
from conference_overview.models import EvidenceClaim, PaperRecord, SourceRef
from conference_overview.validate import (
    PublicationBlocked,
    ValidationReport,
    assert_publishable,
)

_ARTIFACT_NAMES = (
    "papers.json",
    "papers.csv",
    "overview.json",
    "overview.md",
    "validation.json",
    "provenance.json",
)
_MINIMUM_OBSERVED_PRECISION = Decimal("0.90")
_MINIMUM_WILSON_LOWER_95 = Decimal("0.80")

MetricValue: TypeAlias = Decimal | int | EmergingScore | CrossVenueSpread


@dataclass(frozen=True)
class ReleaseBundle:
    """Typed inputs from the validated analysis pipeline for one release."""

    records: Sequence[PaperRecord]
    validation: ValidationReport
    taxonomy_version: str
    assignments: Sequence[Assignment] = field(default_factory=tuple)
    audits: Mapping[str, ThemeAudit] = field(default_factory=dict)
    metrics: Mapping[str, MetricValue] = field(default_factory=dict)
    awards: Sequence[AwardRecord] = field(default_factory=tuple)
    claims: Sequence[EvidenceClaim] = field(default_factory=tuple)
    sources: Sequence[SourceRef] = field(default_factory=tuple)


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def _ordered_papers(records: Sequence[PaperRecord]) -> list[dict[str, object]]:
    return [
        record.model_dump(mode="json")
        for record in sorted(records, key=lambda item: item.paper_id)
    ]


def _metric_payload(value: MetricValue) -> object:
    if isinstance(value, bool):
        raise TypeError("metric values must be typed metric outputs")
    if isinstance(value, EmergingScore):
        return _decimal_payload(value.to_dict())
    if isinstance(value, CrossVenueSpread):
        return _decimal_payload(asdict(value))
    if isinstance(value, (Decimal, int)):
        return _decimal_payload(value)
    raise TypeError("metric values must be typed metric outputs")


def _decimal_payload(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _decimal_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_decimal_payload(item) for item in value]
    return value


def _validation_payload(report: ValidationReport) -> dict[str, object]:
    payload = asdict(report)
    for key in (
        "missing_abstract_ids",
        "missing_pdf_ids",
        "missing_doi_ids",
        "duplicate_source_ids",
        "duplicate_dois",
        "status_mismatch_ids",
        "unresolved_record_ids",
        "previous_snapshot_additions",
        "previous_snapshot_removals",
    ):
        payload[key] = sorted(payload[key])
    for key in ("definite_duplicate_pairs", "duplicate_candidates"):
        payload[key] = [list(pair) for pair in sorted(payload[key])]
    payload["definite_duplicate_count"] = report.definite_duplicate_count
    payload["duplicate_candidate_count"] = report.duplicate_candidate_count
    return payload


def _source_payload(source: SourceRef) -> dict[str, object]:
    return source.model_dump(mode="json")


def _provenance_payload(bundle: ReleaseBundle) -> dict[str, object]:
    source_by_identity: dict[tuple[str, str | None, str | None], SourceRef] = {}
    for source in (*bundle.sources, *(record.source for record in bundle.records)):
        retrieved_at = source.retrieved_at.isoformat() if source.retrieved_at else None
        identity = (str(source.url), source.sha256, retrieved_at)
        source_by_identity[identity] = source
    ordered_sources = [
        source_by_identity[key]
        for key in sorted(
            source_by_identity,
            key=lambda item: (item[0], item[1] or "", item[2] or ""),
        )
    ]
    payload: dict[str, object] = {
        "sources": [_source_payload(source) for source in ordered_sources],
        "taxonomy_version": bundle.taxonomy_version,
    }
    if len(ordered_sources) == 1:
        source = ordered_sources[0]
        payload.update(
            {
                "source_url": str(source.url),
                "source_sha256": source.sha256,
                "source_retrieved_at": (
                    source.model_dump(mode="json")["retrieved_at"]
                ),
            }
        )
    return payload


def _overview_payload(bundle: ReleaseBundle) -> dict[str, object]:
    assignments = [
        {
            "confidence": str(assignment.confidence),
            "paper_id": assignment.paper_id,
            "primary_topic": assignment.primary_topic,
            "rationale": assignment.rationale,
            "secondary_topics": list(assignment.secondary_topics),
            "taxonomy_version": assignment.taxonomy_version,
        }
        for assignment in sorted(bundle.assignments, key=lambda item: item.paper_id)
    ]
    audits = {
        topic: {
            "correct_count": audit.correct_count,
            "observed_precision": str(audit.observed_precision),
            "sample_size": audit.sample_size,
            "thresholds": {
                "minimum_observed_precision": str(_MINIMUM_OBSERVED_PRECISION),
                "minimum_wilson_lower_95": str(_MINIMUM_WILSON_LOWER_95),
            },
            "wilson_lower_95": str(audit.wilson_lower_95),
        }
        for topic, audit in sorted(bundle.audits.items())
    }
    return {
        "assignments": assignments,
        "audits": audits,
        "awards": [
            award.model_dump(mode="json")
            for award in sorted(
                bundle.awards,
                key=lambda item: (item.paper_id, item.award_type),
            )
        ],
        "evidence_claims": [
            claim.model_dump(mode="json")
            for claim in sorted(
                bundle.claims,
                key=lambda item: (item.evidence_type.value, item.claim),
            )
        ],
        "metrics": {
            name: _metric_payload(value)
            for name, value in sorted(bundle.metrics.items())
        },
        "paper_count": len(bundle.records),
        "taxonomy_version": bundle.taxonomy_version,
    }


def _csv_bytes(papers: Sequence[Mapping[str, object]]) -> bytes:
    output = io.StringIO(newline="")
    fieldnames = list(PaperRecord.model_fields)
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for paper in papers:
        writer.writerow(
            {
                name: (
                    json.dumps(value, sort_keys=True, ensure_ascii=False)
                    if isinstance(value, (list, dict))
                    else value
                )
                for name, value in paper.items()
            }
        )
    return output.getvalue().encode()


def _markdown_bytes(bundle: ReleaseBundle) -> bytes:
    lines = ["# Conference overview", "", "## Evidence-backed synthesis", ""]
    ordered_claims = sorted(
        bundle.claims,
        key=lambda item: (item.evidence_type.value, item.claim),
    )
    if not ordered_claims:
        lines.append("No evidence-backed synthesis claims were supplied.")
    for claim in ordered_claims:
        sources = ", ".join(f"<{url}>" for url in claim.source_urls)
        locator = f"; {claim.locator}" if claim.locator is not None else ""
        lines.append(
            f"- **{claim.evidence_type.value}** — {claim.claim} "
            f"({sources}{locator})"
        )
    lines.extend(["", "## Award verification", ""])
    if not bundle.awards:
        lines.append("No typed award records were supplied.")
    else:
        lines.append("Award verification statuses are recorded in `overview.json`.")
    lines.append("")
    return "\n".join(lines).encode()


def _validate_bundle(bundle: ReleaseBundle) -> None:
    assert_publishable(bundle.validation)
    if not bundle.validation.publishable:
        raise PublicationBlocked("publication blocked: validation marked unpublishable")
    if not bundle.taxonomy_version.strip():
        raise ValueError("taxonomy_version must not be blank")
    if any(not isinstance(claim, EvidenceClaim) for claim in bundle.claims):
        raise ValueError("technical prose entries must be typed EvidenceClaim objects")
    if any(not isinstance(award, AwardRecord) for award in bundle.awards):
        raise ValueError("awards must be typed AwardRecord objects")

    record_ids = [record.paper_id for record in bundle.records]
    assignment_ids = [assignment.paper_id for assignment in bundle.assignments]
    if len(assignment_ids) != len(set(assignment_ids)):
        raise PublicationBlocked("publication blocked: duplicate assignment paper IDs")
    if bundle.assignments:
        missing = sorted(set(record_ids) - set(assignment_ids))
        unknown = sorted(set(assignment_ids) - set(record_ids))
        if missing:
            raise PublicationBlocked(f"publication blocked: missing assignments: {missing}")
        if unknown:
            raise PublicationBlocked(f"publication blocked: unknown assignments: {unknown}")
        if any(
            assignment.taxonomy_version != bundle.taxonomy_version
            for assignment in bundle.assignments
        ):
            raise PublicationBlocked("publication blocked: taxonomy version mismatch")
        missing_audits = sorted(
            {assignment.primary_topic for assignment in bundle.assignments}
            - set(bundle.audits)
        )
        if missing_audits:
            raise PublicationBlocked(
                f"publication blocked: missing theme audits: {missing_audits}"
            )
    for audit in bundle.audits.values():
        assert_theme_publishable(audit)


def _render_artifacts(bundle: ReleaseBundle) -> dict[str, bytes]:
    papers = _ordered_papers(bundle.records)
    return {
        "papers.json": _json_bytes(papers),
        "papers.csv": _csv_bytes(papers),
        "overview.json": _json_bytes(_overview_payload(bundle)),
        "overview.md": _markdown_bytes(bundle),
        "validation.json": _json_bytes(_validation_payload(bundle.validation)),
        "provenance.json": _json_bytes(_provenance_payload(bundle)),
    }


def _replace_directory(staged: Path, destination: Path) -> None:
    backup = destination.parent / f".{destination.name}.backup-{uuid.uuid4().hex}"
    if not destination.exists():
        staged.replace(destination)
        return
    destination.replace(backup)
    try:
        staged.replace(destination)
    except BaseException:
        backup.replace(destination)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def write_release(bundle: ReleaseBundle, output_dir: Path) -> None:
    """Validate, stage, and replace a complete deterministic artifact set."""
    _validate_bundle(bundle)
    artifacts = _render_artifacts(bundle)
    if tuple(artifacts) != _ARTIFACT_NAMES:
        raise RuntimeError("release renderer produced an incomplete artifact set")

    destination = Path(output_dir).resolve()
    if destination.exists() and not destination.is_dir():
        raise ValueError("release output must be a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(
        tempfile.mkdtemp(
            dir=destination.parent,
            prefix=f".{destination.name}.staging-",
        )
    )
    try:
        if destination.exists():
            shutil.copytree(destination, staged, dirs_exist_ok=True)
        for name, data in artifacts.items():
            (staged / name).write_bytes(data)
        _replace_directory(staged, destination)
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        raise
