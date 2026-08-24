"""Deterministic, publication-gated conference release artifacts."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TypeAlias
from urllib.parse import urlparse

from pydantic import BaseModel

from conference_overview.awards import (
    AwardAnnouncement,
    AwardRecord,
    AwardStatus,
    DeepRead,
    award_route_key,
    canonical_award_identity,
    validate_award,
    validate_deep_read,
)
from conference_overview.classification import (
    Assignment,
    ThemeAudit,
    assert_theme_publishable,
)
from conference_overview.metrics import (
    CrossVenueSpread,
    EmergingScore,
)
from conference_overview.metrics import (
    emerging_score as calculate_emerging_score,
)
from conference_overview.models import (
    AdvanceRecord,
    EvidenceClaim,
    EvidenceType,
    PaperRecord,
    SourceRef,
    ThemeDisclosure,
)
from conference_overview.registry import (
    canonicalize_official_host,
    official_award_hosts,
)
from conference_overview.validate import (
    PublicationBlocked,
    ValidationReport,
    assert_publishable,
    validate_records,
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
_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")
_NUMERIC_TOKEN_PATTERN = re.compile(
    r"(?<![\w.])[+-]?(?:\d+(?:[.,]\d+)*|\.\d+)(?:e[+-]?\d+)?"
    r"(?:\s?(?:%|％|pp|x))?(?!\w)",
    re.IGNORECASE,
)
_COMPARISON_SCHEMA_VERSION = "conference-comparison-v1"
_METRIC_FORMULA_VERSION = "conference-metrics-v1"
_EMERGING_SCORE_WEIGHTS = {
    "novelty": "0.20",
    "share_growth": "0.45",
    "spread_growth": "0.35",
}

MetricValue: TypeAlias = Decimal | int | EmergingScore | CrossVenueSpread


class ArtifactValidationError(ValueError):
    """Raised when typed inputs cannot be safely represented in artifacts."""


@dataclass(frozen=True)
class ReleaseBundle:
    """Typed inputs from the validated analysis pipeline for one release."""

    records: Sequence[PaperRecord]
    validation: ValidationReport
    taxonomy_version: str
    generated_at: datetime
    assignments: Sequence[Assignment] = field(default_factory=tuple)
    audits: Mapping[str, ThemeAudit] = field(default_factory=dict)
    metrics: Mapping[str, MetricValue] = field(default_factory=dict)
    awards: Sequence[AwardRecord] = field(default_factory=tuple)
    award_announcement: AwardAnnouncement = field(default_factory=AwardAnnouncement)
    award_deep_reads: Sequence[DeepRead] = field(default_factory=tuple)
    advances: Sequence[AdvanceRecord] = field(default_factory=tuple)
    theme_disclosures: Sequence[ThemeDisclosure] = field(default_factory=tuple)
    claims: Sequence[EvidenceClaim] = field(default_factory=tuple)
    sources: Sequence[SourceRef] = field(default_factory=tuple)
    excluded_records: Sequence[PaperRecord] = field(default_factory=tuple)
    previous_snapshot: Sequence[PaperRecord] | None = None


def _json_bytes(payload: object) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def _ordered_papers(records: Sequence[PaperRecord]) -> list[dict[str, object]]:
    return [
        record.model_dump(mode="json")
        for record in sorted(records, key=lambda item: item.paper_id)
    ]


def _decimal_payload(value: object) -> object:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ArtifactValidationError("artifact contains a non-finite Decimal")
        return str(value)
    if isinstance(value, Mapping):
        return {
            str(key): _decimal_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_decimal_payload(item) for item in value]
    return value


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


def _comparison_contract(bundle: ReleaseBundle) -> dict[str, object]:
    if not bundle.records:
        raise PublicationBlocked(
            "publication blocked: comparison scope requires at least one included record"
        )
    first = bundle.records[0]
    published_spread = bundle.metrics.get("cross_venue_spread")
    configured_venues = (
        list(published_spread.configured_venues)
        if isinstance(published_spread, CrossVenueSpread)
        else []
    )
    configured_venue_id = hashlib.sha256(
        json.dumps(
            configured_venues,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    identity: dict[str, object] = {
        "comparison_scope": {
            "denominator": {
                "artifact_field": "validation.included_count",
                "description": "validated included papers after explicit exclusions",
                "unit": "paper",
            },
            "excluded_records": "kept explicit and excluded from the denominator",
            "inclusion_statuses": ["complete", "partial"],
            "track": first.track,
            "venue": first.venue,
        },
        "metric_contract": {
            "cross_venue_spread": {
                "configured_venue_count": len(configured_venues),
                "configured_venue_id": configured_venue_id,
                "configured_venues": configured_venues,
                "denominator": "configured venue population",
                "formula": "venues_with_topic / configured_venue_count",
                "numerator": "configured venues with a positive topic count",
                "version": "cross-venue-spread-v1",
            },
            "emerging_score": {
                "formula": (
                    "0.45 * share_growth + 0.35 * spread_growth + 0.20 * novelty"
                ),
                "version": "emerging-score-v1",
                "weights": _EMERGING_SCORE_WEIGHTS,
            },
            "emitted_metrics": sorted(bundle.metrics),
            "formula_version": _METRIC_FORMULA_VERSION,
            "topic_share": {
                "denominator": "validation.included_count",
                "formula": (
                    "primary_topic_paper_count / validated_included_paper_count"
                ),
                "numerator": "one primary-topic assignment per included paper",
                "version": "topic-share-v1",
            },
        },
        "schema_version": _COMPARISON_SCHEMA_VERSION,
    }
    canonical = json.dumps(
        identity,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return {"contract_id": hashlib.sha256(canonical).hexdigest(), **identity}


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
    payload.update(
        {
            "definite_duplicate_count": report.definite_duplicate_count,
            "duplicate_candidate_count": report.duplicate_candidate_count,
            "duplicate_source_id_count": len(report.duplicate_source_ids),
            "duplicate_doi_count": len(report.duplicate_dois),
            "status_mismatch_count": len(report.status_mismatch_ids),
            "unresolved_record_count": len(report.unresolved_record_ids),
            "missing_abstract_count": len(report.missing_abstract_ids),
            "missing_pdf_count": len(report.missing_pdf_ids),
            "missing_doi_count": len(report.missing_doi_ids),
            "snapshot_addition_count": len(report.previous_snapshot_additions),
            "snapshot_removal_count": len(report.previous_snapshot_removals),
        }
    )
    return payload


def _source_payload(source: SourceRef) -> dict[str, object]:
    return source.model_dump(mode="json")


def _bundle_sources(bundle: ReleaseBundle) -> list[SourceRef]:
    source_by_identity: dict[tuple[str, str | None, str | None], SourceRef] = {}
    for source in (*bundle.sources, *(record.source for record in bundle.records)):
        retrieved_at = source.retrieved_at.isoformat() if source.retrieved_at else None
        identity = (str(source.url), source.sha256, retrieved_at)
        source_by_identity[identity] = source
    return [
        source_by_identity[key]
        for key in sorted(
            source_by_identity,
            key=lambda item: (item[0], item[1] or "", item[2] or ""),
        )
    ]


def _provenance_payload(bundle: ReleaseBundle) -> dict[str, object]:
    ordered_sources = _bundle_sources(bundle)
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
                "source_retrieved_at": source.model_dump(mode="json")["retrieved_at"],
            }
        )
    return payload


def _overview_payload(bundle: ReleaseBundle) -> dict[str, object]:
    validated_awards, award_policy = _validated_award_payload(bundle)
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
        "build_metadata": {
            "generated_at": bundle.generated_at.isoformat().replace("+00:00", "Z"),
            "producer": "conference_overview.reports.write_release",
            "schema_version": "release-build-v1",
        },
        "award_state": award_policy,
        "awards": validated_awards,
        "award_deep_reads": [
            deep_read.model_dump(mode="json")
            for deep_read in sorted(
                bundle.award_deep_reads, key=lambda item: item.paper_id
            )
        ],
        "advances": [
            advance.model_dump(mode="json")
            for advance in sorted(bundle.advances, key=lambda item: item.advance_id)
        ],
        "theme_disclosures": [
            disclosure.model_dump(mode="json")
            for disclosure in sorted(
                bundle.theme_disclosures, key=lambda item: item.theme
            )
        ],
        "comparison_contract": _comparison_contract(bundle),
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


def _validated_award_payload(
    bundle: ReleaseBundle,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if not bundle.records:
        return [], {
            "status": AwardStatus.NOT_VERIFIED.value,
            "evidence_url": None,
            "evidence_claim": None,
            "verification": {
                "allowed_hosts": [],
                "evidence_host": None,
                "validator": "validate_award-v1",
            },
        }
    first = bundle.records[0]
    allowed_hosts = official_award_hosts(first.venue, first.year, first.track)
    allowed = set(allowed_hosts)

    def verification(evidence_url: str | None) -> dict[str, object]:
        return {
            "allowed_hosts": sorted(allowed_hosts),
            "evidence_host": (
                canonicalize_official_host(urlparse(evidence_url).hostname or "")
                if evidence_url
                else None
            ),
            "validator": "validate_award-v1",
        }

    reparsed_awards = [
        AwardRecord.model_validate(award.model_dump(warnings=False))
        for award in bundle.awards
    ]
    payloads: list[dict[str, object]] = []
    for award in sorted(
        reparsed_awards, key=lambda item: (item.paper_id, item.award_type)
    ):
        validated = validate_award(award, allowed_hosts=allowed)
        if (
            award.status is AwardStatus.VERIFIED
            and validated.status is not AwardStatus.VERIFIED
        ):
            raise PublicationBlocked(
                "publication blocked: official award evidence failed configured host policy"
            )
        evidence_url = (
            str(validated.evidence_url) if validated.evidence_url is not None else None
        )
        payload = validated.model_dump(mode="json")
        identity = canonical_award_identity(validated.paper_id, validated.award_type)
        payload["canonical_identity"] = identity
        payload["route_key"] = award_route_key(identity)
        payload["verification"] = verification(evidence_url)
        payloads.append(payload)

    verified = [
        payload
        for payload in payloads
        if payload["status"] == AwardStatus.VERIFIED.value
    ]
    if verified:
        return payloads, {
            "status": AwardStatus.VERIFIED.value,
            "evidence_url": verified[0]["evidence_url"],
            "evidence_claim": None,
            "verification": verification(str(verified[0]["evidence_url"])),
        }

    announcement = bundle.award_announcement
    if announcement.status is AwardStatus.NOT_ANNOUNCED:
        probe = AwardRecord(
            paper_id="award-announcement-state",
            award_type="Award announcement status",
            status=AwardStatus.VERIFIED,
            evidence_url=announcement.evidence_url,
        )
        if (
            validate_award(probe, allowed_hosts=allowed).status
            is not AwardStatus.VERIFIED
        ):
            raise PublicationBlocked(
                "publication blocked: award announcement is not official"
            )
    return payloads, {
        "status": announcement.status.value,
        "evidence_url": (
            str(announcement.evidence_url)
            if announcement.evidence_url is not None
            else None
        ),
        "evidence_claim": (
            announcement.claim.model_dump(mode="json")
            if announcement.claim is not None
            else None
        ),
        "verification": verification(
            str(announcement.evidence_url)
            if announcement.evidence_url is not None
            else None
        ),
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
            f"- **{claim.evidence_type.value}** — {claim.claim} ({sources}{locator})"
        )
    lines.extend(["", "## Award verification", ""])
    if not bundle.awards:
        lines.append("No typed award records were supplied.")
    else:
        lines.append("Award verification statuses are recorded in `overview.json`.")
    lines.append("")
    return "\n".join(lines).encode()


def _reject_non_finite(value: object, *, path: str = "bundle") -> None:
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ArtifactValidationError(f"{path} contains a non-finite Decimal")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ArtifactValidationError(f"{path} contains a non-finite float")
        return
    if isinstance(value, BaseModel):
        _reject_non_finite(value.model_dump(mode="python", warnings=False), path=path)
        return
    if is_dataclass(value) and not isinstance(value, type):
        for item in fields(value):
            _reject_non_finite(getattr(value, item.name), path=f"{path}.{item.name}")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_non_finite(item, path=f"{path}.{key}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _reject_non_finite(item, path=f"{path}[{index}]")


def _authoritative_validation(bundle: ReleaseBundle) -> ValidationReport:
    if not bundle.validation.publishable:
        raise PublicationBlocked("publication blocked: validation marked unpublishable")
    authoritative = validate_records(
        bundle.records,
        bundle.excluded_records,
        expected_included=bundle.validation.expected_included,
        previous_snapshot=bundle.previous_snapshot,
    )
    if authoritative != bundle.validation:
        raise PublicationBlocked(
            "publication blocked: stale validation diagnostics disagree with bundle records"
        )
    assert_publishable(authoritative)
    return authoritative


def _validate_provenance(sources: Sequence[SourceRef]) -> None:
    if not sources:
        raise PublicationBlocked("publication blocked: provenance requires a source")
    for source in sources:
        if not str(source.url).strip():
            raise PublicationBlocked(
                "publication blocked: provenance source URL is blank"
            )
        if source.sha256 is None or _SHA256_PATTERN.fullmatch(source.sha256) is None:
            raise PublicationBlocked(
                "publication blocked: provenance requires a valid source SHA-256"
            )
        if (
            source.retrieved_at is None
            or source.retrieved_at.tzinfo is None
            or source.retrieved_at.utcoffset() is None
        ):
            raise PublicationBlocked(
                "publication blocked: provenance requires a timezone-aware retrieval time"
            )


def _validate_claims(claims: Sequence[EvidenceClaim]) -> None:
    for claim in claims:
        requires_locator = (
            claim.evidence_type is EvidenceType.PAPER_REPORTED
            or _NUMERIC_TOKEN_PATTERN.search(claim.claim) is not None
        )
        if requires_locator and claim.locator is None:
            raise PublicationBlocked(
                "publication blocked: paper-reported and numeric claims require a locator"
            )


def _validate_bundle(bundle: ReleaseBundle) -> ValidationReport:
    _reject_non_finite(bundle)
    authoritative_validation = _authoritative_validation(bundle)
    if not bundle.taxonomy_version.strip():
        raise ValueError("taxonomy_version must not be blank")
    if bundle.generated_at.tzinfo is None or bundle.generated_at.utcoffset() is None:
        raise PublicationBlocked(
            "publication blocked: build generated_at must be timezone-aware"
        )
    if any(not isinstance(claim, EvidenceClaim) for claim in bundle.claims):
        raise ValueError("technical prose entries must be typed EvidenceClaim objects")
    if any(not isinstance(award, AwardRecord) for award in bundle.awards):
        raise ValueError("awards must be typed AwardRecord objects")
    if any(
        not isinstance(deep_read, DeepRead) for deep_read in bundle.award_deep_reads
    ):
        raise ValueError("award deep reads must be typed DeepRead objects")
    if any(not isinstance(advance, AdvanceRecord) for advance in bundle.advances):
        raise ValueError("advances must be typed AdvanceRecord objects")
    if any(
        not isinstance(disclosure, ThemeDisclosure)
        for disclosure in bundle.theme_disclosures
    ):
        raise ValueError("theme disclosures must be typed ThemeDisclosure objects")
    _validate_claims(bundle.claims)
    if bundle.award_announcement.claim is not None:
        _validate_claims((bundle.award_announcement.claim,))
    _validate_provenance(_bundle_sources(bundle))

    published_emerging_score = bundle.metrics.get("emerging_score")
    if published_emerging_score is not None:
        try:
            expected_emerging_score = calculate_emerging_score(
                share_growth=published_emerging_score.components["share_growth"],
                spread_growth=published_emerging_score.components["spread_growth"],
                novelty=published_emerging_score.components["novelty"],
            )
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise PublicationBlocked(
                "publication blocked: emerging_score violates metric formula contract"
            ) from exc
        if published_emerging_score != expected_emerging_score:
            raise PublicationBlocked(
                "publication blocked: emerging_score violates metric formula contract"
            )
    published_spread = bundle.metrics.get("cross_venue_spread")
    if published_spread is not None:
        if not isinstance(published_spread, CrossVenueSpread):
            raise PublicationBlocked(
                "publication blocked: cross_venue_spread violates metric formula contract"
            )
        configured_venues = published_spread.configured_venues
        present_venues = published_spread.present_venues
        if (
            not isinstance(configured_venues, tuple)
            or not isinstance(present_venues, tuple)
            or any(not isinstance(venue, str) for venue in configured_venues)
            or any(not isinstance(venue, str) for venue in present_venues)
            or type(published_spread.present_venue_count) is not int
            or not isinstance(published_spread.present_venue_fraction, Decimal)
        ):
            raise PublicationBlocked(
                "publication blocked: cross_venue_spread contradicts its configured venue population"
            )
        canonical_configured = tuple(sorted(set(configured_venues)))
        canonical_present = tuple(sorted(set(present_venues)))
        configured_count = len(configured_venues)
        if (
            not configured_venues
            or any(not venue.strip() for venue in configured_venues)
            or configured_venues != canonical_configured
            or present_venues != canonical_present
            or not set(present_venues).issubset(configured_venues)
            or published_spread.present_venue_count != len(present_venues)
            or not 0 <= published_spread.present_venue_count <= configured_count
            or published_spread.present_venue_fraction
            != Decimal(published_spread.present_venue_count) / Decimal(configured_count)
        ):
            raise PublicationBlocked(
                "publication blocked: cross_venue_spread contradicts its configured venue population"
            )

    if bundle.records:
        first_scope = (
            bundle.records[0].venue,
            bundle.records[0].year,
            bundle.records[0].track,
        )
        if any(
            (record.venue, record.year, record.track) != first_scope
            for record in bundle.records
        ):
            raise PublicationBlocked(
                "publication blocked: records mix venue/year/track scope"
            )

    record_ids = [record.paper_id for record in bundle.records]
    record_id_set = set(record_ids)
    validated_awards, _award_state = _validated_award_payload(bundle)
    award_identities = [
        json.dumps(award["canonical_identity"], sort_keys=True)
        for award in validated_awards
    ]
    if len(award_identities) != len(set(award_identities)):
        raise PublicationBlocked(
            "publication blocked: duplicate normalized award identities"
        )
    verified_award_ids = {
        str(award["paper_id"])
        for award in validated_awards
        if award["status"] == AwardStatus.VERIFIED.value
    }
    if any(str(award["paper_id"]) not in record_id_set for award in validated_awards):
        raise PublicationBlocked(
            "publication blocked: award refers to an unknown paper"
        )
    deep_read_ids: list[str] = []
    for deep_read in bundle.award_deep_reads:
        deep_read = DeepRead.model_validate(deep_read.model_dump())
        validate_deep_read(deep_read)
        deep_read_ids.append(deep_read.paper_id)
        if deep_read.paper_id not in verified_award_ids:
            raise PublicationBlocked(
                "publication blocked: award deep read requires a verified official award"
            )
        _validate_claims(
            (
                deep_read.research_problem,
                deep_read.contribution,
                deep_read.method_summary,
                *deep_read.result_claims,
                *deep_read.why_it_matters,
                *deep_read.limitations,
                *deep_read.data_training_setup,
                *deep_read.prior_work_differences,
                *deep_read.reproducibility_assessment,
                *deep_read.transferable_implications,
            )
        )
    if len(deep_read_ids) != len(set(deep_read_ids)):
        raise PublicationBlocked(
            "publication blocked: duplicate award deep-read paper IDs"
        )

    advance_ids: list[str] = []
    for advance in bundle.advances:
        advance_ids.append(advance.advance_id)
        if not set(advance.supporting_paper_ids).issubset(record_id_set):
            raise PublicationBlocked(
                "publication blocked: advance refers to an unknown paper"
            )
        _validate_claims(advance.claims)
    if len(advance_ids) != len(set(advance_ids)):
        raise PublicationBlocked("publication blocked: duplicate advance IDs")

    disclosure_themes = [disclosure.theme for disclosure in bundle.theme_disclosures]
    if len(disclosure_themes) != len(set(disclosure_themes)):
        raise PublicationBlocked("publication blocked: duplicate theme disclosures")
    _validate_claims(
        tuple(disclosure.reason for disclosure in bundle.theme_disclosures)
    )

    assignment_ids = [assignment.paper_id for assignment in bundle.assignments]
    if len(assignment_ids) != len(set(assignment_ids)):
        raise PublicationBlocked("publication blocked: duplicate assignment paper IDs")
    missing = sorted(set(record_ids) - set(assignment_ids))
    unknown = sorted(set(assignment_ids) - set(record_ids))
    if missing:
        raise PublicationBlocked(f"publication blocked: missing assignments: {missing}")
    if unknown:
        raise PublicationBlocked(f"publication blocked: unknown assignments: {unknown}")
    if bundle.assignments:
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
    disclosed_primary_themes = {
        disclosure.theme for disclosure in bundle.theme_disclosures
    }
    for theme, audit in bundle.audits.items():
        try:
            assert_theme_publishable(audit)
        except PublicationBlocked:
            if theme not in disclosed_primary_themes:
                raise
    return authoritative_validation


def _render_artifacts(
    bundle: ReleaseBundle, validation: ValidationReport
) -> dict[str, bytes]:
    papers = _ordered_papers(bundle.records)
    return {
        "papers.json": _json_bytes(papers),
        "papers.csv": _csv_bytes(papers),
        "overview.json": _json_bytes(_overview_payload(bundle)),
        "overview.md": _markdown_bytes(bundle),
        "validation.json": _json_bytes(_validation_payload(validation)),
        "provenance.json": _json_bytes(_provenance_payload(bundle)),
    }


def _release_root(output_dir: Path) -> Path:
    requested = Path(output_dir)
    if requested.is_symlink():
        raise ValueError("release output path must not be a symlink")
    absolute = requested.absolute()
    if not absolute.name:
        raise ValueError("release output path must name a directory")
    absolute.parent.mkdir(parents=True, exist_ok=True)
    real_parent = absolute.parent.resolve(strict=True)
    output = real_parent / absolute.name
    if output.is_symlink():
        raise ValueError("release output path must not be a symlink")
    if output.exists() and not output.is_dir():
        raise ValueError("release output must be a directory")
    return output


def _artifact_digest(artifacts: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in _ARTIFACT_NAMES:
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(artifacts[name])
        digest.update(b"\0")
    return digest.hexdigest()


def _verify_generation(generation: Path, artifacts: Mapping[str, bytes]) -> None:
    if generation.is_symlink() or not generation.is_dir():
        raise ArtifactValidationError("immutable generation path is unsafe")
    if sorted(path.name for path in generation.iterdir()) != sorted(_ARTIFACT_NAMES):
        raise ArtifactValidationError("immutable generation artifact set is invalid")
    for name, expected in artifacts.items():
        path = generation / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
            raise ArtifactValidationError("immutable generation content is invalid")


def _replace_current_pointer(output: Path, pointer: bytes) -> None:
    file_descriptor, temporary_name = tempfile.mkstemp(dir=output, prefix=".current-")
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(pointer)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, output / "current.json")
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _remove_legacy_entries(output: Path) -> None:
    for path in output.iterdir():
        if path.name in {"current.json", "generations"}:
            continue
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)


def resolve_current_release(output_dir: Path) -> Path:
    """Resolve and validate the immutable generation selected by current.json."""
    requested = Path(output_dir)
    if requested.is_symlink():
        raise ArtifactValidationError("release output path must not be a symlink")
    output = requested.absolute()
    if output.is_symlink() or not output.is_dir():
        raise ArtifactValidationError("release output directory is unavailable")
    current = output / "current.json"
    generations = output / "generations"
    if current.is_symlink() or generations.is_symlink():
        raise ArtifactValidationError("release pointer layout contains a symlink")
    try:
        pointer = json.loads(current.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArtifactValidationError("release current pointer is invalid") from exc
    generation_value = (
        pointer.get("generation") if isinstance(pointer, Mapping) else None
    )
    artifact_hashes = (
        pointer.get("artifact_sha256") if isinstance(pointer, Mapping) else None
    )
    if not isinstance(generation_value, str):
        raise ArtifactValidationError("release current pointer has no generation")
    if (
        not isinstance(artifact_hashes, Mapping)
        or set(artifact_hashes) != set(_ARTIFACT_NAMES)
        or any(
            not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None
            for value in artifact_hashes.values()
        )
    ):
        raise ArtifactValidationError(
            "release current pointer has invalid artifact hashes"
        )
    generation_parts = Path(generation_value).parts
    if (
        len(generation_parts) != 2
        or generation_parts[0] != "generations"
        or _SHA256_PATTERN.fullmatch(generation_parts[1]) is None
    ):
        raise ArtifactValidationError("release current pointer is unsafe")
    generation = output / generation_parts[0] / generation_parts[1]
    if generation.is_symlink() or not generation.is_dir():
        raise ArtifactValidationError("release generation is unavailable")
    if sorted(path.name for path in generation.iterdir()) != sorted(_ARTIFACT_NAMES):
        raise ArtifactValidationError("release generation artifact set is incomplete")
    if any(
        (generation / name).is_symlink() or not (generation / name).is_file()
        for name in _ARTIFACT_NAMES
    ):
        raise ArtifactValidationError("release generation contains an unsafe artifact")
    if any(
        hashlib.sha256((generation / name).read_bytes()).hexdigest()
        != artifact_hashes[name]
        for name in _ARTIFACT_NAMES
    ):
        raise ArtifactValidationError("release generation artifact hash mismatch")
    return generation


def write_release(bundle: ReleaseBundle, output_dir: Path) -> None:
    """Publish one immutable generation and atomically select it as current."""
    validation = _validate_bundle(bundle)
    artifacts = _render_artifacts(bundle, validation)
    if tuple(artifacts) != _ARTIFACT_NAMES:
        raise RuntimeError("release renderer produced an incomplete artifact set")

    output = _release_root(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    current = output / "current.json"
    generations = output / "generations"
    if current.is_symlink() or generations.is_symlink():
        raise ValueError("release pointer layout must not contain symlinks")
    generations.mkdir(exist_ok=True)

    generation_name = _artifact_digest(artifacts)
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
        pointer = _json_bytes(
            {
                "artifact_sha256": {
                    name: hashlib.sha256(data).hexdigest()
                    for name, data in artifacts.items()
                },
                "generation": f"generations/{generation_name}",
            }
        )
        _remove_legacy_entries(output)
        _replace_current_pointer(output, pointer)
    except BaseException:
        shutil.rmtree(staged, ignore_errors=True)
        raise
