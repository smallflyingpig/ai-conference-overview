"""Versioned semantic-classification exchange and publication audit gates."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from conference_overview.models import EvidenceType, PaperRecord
from conference_overview.validate import PublicationBlocked

_WILSON_Z_95 = Decimal("1.959963984540054")
_MINIMUM_PRECISION = Decimal("0.90")
_MINIMUM_WILSON_LOWER_95 = Decimal("0.80")
_MAX_AUDIT_SAMPLE_SIZE = 50
_PACKAGED_TAXONOMY_PATH = Path(__file__).with_name("taxonomy.yaml")
_SOURCE_TAXONOMY_PATH = Path(__file__).resolve().parents[2] / "config" / "taxonomy.yaml"
_DEFAULT_TAXONOMY_PATH = (
    _PACKAGED_TAXONOMY_PATH
    if _PACKAGED_TAXONOMY_PATH.exists()
    else _SOURCE_TAXONOMY_PATH
)

_EVIDENCE_LABEL_INSTRUCTIONS = {
    EvidenceType.OFFICIAL_METADATA.value: "Use only official venue metadata for this label.",
    EvidenceType.PAPER_REPORTED.value: "Use claims explicitly reported by the paper.",
    EvidenceType.CROSS_PAPER_SYNTHESIS.value: "Mark comparisons synthesized across papers.",
    EvidenceType.INFERENCE.value: "Mark interpretations that go beyond reported facts.",
}


@dataclass(frozen=True)
class Assignment:
    """One paper's validated common-taxonomy assignment."""

    paper_id: str
    primary_topic: str
    secondary_topics: tuple[str, ...]
    confidence: Decimal
    rationale: str
    taxonomy_version: str


@dataclass(frozen=True)
class ThemeAudit:
    """Auditable precision statistics for a single published theme."""

    sample_size: int
    correct_count: int
    observed_precision: Decimal
    wilson_lower_95: Decimal


@dataclass(frozen=True)
class _Taxonomy:
    version: str
    topics: tuple[dict[str, str], ...]

    @property
    def topic_names(self) -> frozenset[str]:
        return frozenset(topic["name"] for topic in self.topics)

    def to_payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "topics": [dict(topic) for topic in self.topics],
        }


def load_taxonomy(path: Path = _DEFAULT_TAXONOMY_PATH) -> dict[str, object]:
    """Load and validate the stable taxonomy configuration."""
    try:
        raw_taxonomy = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"could not read taxonomy: {path}") from exc
    return _coerce_taxonomy(raw_taxonomy).to_payload()


def _coerce_taxonomy(taxonomy: Mapping[str, object] | None) -> _Taxonomy:
    if taxonomy is None:
        return _coerce_taxonomy(load_taxonomy())
    version = taxonomy.get("version")
    topics = taxonomy.get("topics")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("taxonomy version is required")
    if (
        not isinstance(topics, Sequence)
        or isinstance(topics, (str, bytes))
        or not topics
    ):
        raise ValueError("taxonomy must define at least one topic")

    normalized_topics: list[dict[str, str]] = []
    topic_ids: set[str] = set()
    topic_names: set[str] = set()
    for topic in topics:
        if not isinstance(topic, Mapping):
            raise ValueError("taxonomy topic must be a mapping")  # noqa: TRY004
        topic_id = topic.get("id")
        name = topic.get("name")
        definition = topic.get("definition")
        if not all(
            isinstance(value, str) and value.strip()
            for value in (topic_id, name, definition)
        ):
            raise ValueError("taxonomy topics require id, name, and definition")
        if topic_id in topic_ids or name in topic_names:
            raise ValueError("taxonomy topic ids and names must be unique")
        topic_ids.add(topic_id)
        topic_names.add(name)
        normalized_topics.append(
            {"id": topic_id, "name": name, "definition": definition}
        )
    return _Taxonomy(version=version, topics=tuple(normalized_topics))


def _required_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {field}")
    return value.strip()


def _as_finite_decimal(value: object, *, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number")  # noqa: TRY004
    try:
        confidence = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a finite number") from exc
    if not confidence.is_finite():
        raise ValueError(f"{field} must be a finite number")
    return confidence


def _as_confidence(value: object) -> Decimal:
    confidence = _as_finite_decimal(value, field="confidence")
    if not Decimal(0) <= confidence <= Decimal(1):
        raise ValueError("confidence must be within [0, 1]")
    return confidence


def validate_assignment(
    assignment: Mapping[str, object] | Assignment,
    taxonomy: Mapping[str, object] | None = None,
) -> Assignment:
    """Validate one multi-label assignment against its declared taxonomy version."""
    normalized_taxonomy = _coerce_taxonomy(taxonomy)
    if isinstance(assignment, Assignment):
        raw_assignment: Mapping[str, object] = {
            "paper_id": assignment.paper_id,
            "primary_topic": assignment.primary_topic,
            "secondary_topics": list(assignment.secondary_topics),
            "confidence": assignment.confidence,
            "rationale": assignment.rationale,
            "taxonomy_version": assignment.taxonomy_version,
        }
    elif isinstance(assignment, Mapping):
        raw_assignment = assignment
    else:
        raise ValueError("assignment must be a mapping")  # noqa: TRY004

    paper_id = _required_text(raw_assignment.get("paper_id"), field="paper_id")
    primary_topic = _required_text(
        raw_assignment.get("primary_topic"), field="primary_topic"
    )
    taxonomy_version = _required_text(
        raw_assignment.get("taxonomy_version"), field="taxonomy_version"
    )
    if taxonomy_version != normalized_taxonomy.version:
        raise ValueError(
            "taxonomy version mismatch "
            f"(expected {normalized_taxonomy.version}, found {taxonomy_version})"
        )
    if primary_topic not in normalized_taxonomy.topic_names:
        raise ValueError(f"unknown topic: {primary_topic}")

    raw_secondary_topics = raw_assignment.get("secondary_topics")
    if not isinstance(raw_secondary_topics, Sequence) or isinstance(
        raw_secondary_topics, (str, bytes)
    ):
        raise ValueError("secondary_topics must be a list")  # noqa: TRY004
    secondary_topics = tuple(
        _required_text(topic, field="secondary_topic") for topic in raw_secondary_topics
    )
    if len(set(secondary_topics)) != len(secondary_topics):
        raise ValueError("duplicate secondary topic")
    if primary_topic in secondary_topics:
        raise ValueError("primary topic cannot be repeated as a secondary topic")
    unknown_secondary_topics = set(secondary_topics) - normalized_taxonomy.topic_names
    if unknown_secondary_topics:
        raise ValueError(f"unknown topic: {min(unknown_secondary_topics)}")

    return Assignment(
        paper_id=paper_id,
        primary_topic=primary_topic,
        secondary_topics=secondary_topics,
        confidence=_as_confidence(raw_assignment.get("confidence")),
        rationale=_required_text(raw_assignment.get("rationale"), field="rationale"),
        taxonomy_version=taxonomy_version,
    )


def export_batches(
    records: Iterable[PaperRecord],
    taxonomy: Mapping[str, object] | None = None,
    size: int = 40,
) -> list[dict[str, object]]:
    """Create deterministic provider-agnostic classification batches."""
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ValueError("batch size must be a positive integer")
    normalized_taxonomy = _coerce_taxonomy(taxonomy)
    ordered_records = sorted(records, key=lambda record: record.paper_id)
    paper_ids = [record.paper_id for record in ordered_records]
    if len(set(paper_ids)) != len(paper_ids):
        raise ValueError("duplicate paper_id in export records")

    batches: list[dict[str, object]] = []
    for start in range(0, len(ordered_records), size):
        paper_payloads = [
            {
                "paper_id": record.paper_id,
                "title": record.title,
                "abstract": record.abstract,
                "venue_native_metadata": {
                    "venue": record.venue,
                    "year": record.year,
                    "track": record.track,
                    "keywords": list(record.keywords),
                    "subject_areas": list(record.subject_areas),
                    "native_metadata": dict(record.native_metadata),
                },
            }
            for record in ordered_records[start : start + size]
        ]
        batches.append(
            {
                "batch_index": len(batches) + 1,
                "taxonomy_version": normalized_taxonomy.version,
                "taxonomy": normalized_taxonomy.to_payload(),
                "evidence_label_instructions": dict(_EVIDENCE_LABEL_INSTRUCTIONS),
                "papers": paper_payloads,
            }
        )
    return batches


def load_assignments(
    path: Path,
    taxonomy: Mapping[str, object] | None = None,
    *,
    expected_paper_ids: Iterable[str] | None = None,
) -> list[Assignment]:
    """Load a JSONL assignment file without dropping low-confidence records."""
    normalized_taxonomy = _coerce_taxonomy(taxonomy)
    assignments: list[Assignment] = []
    seen_paper_ids: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"could not read assignments: {path}") from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            raw_assignment = json.loads(line, parse_float=Decimal)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"assignment on line {line_number}: invalid JSONL assignment"
            ) from exc
        try:
            if not isinstance(raw_assignment, Mapping):
                raise ValueError("assignment must be an object")  # noqa: TRY004
            parsed_assignment = validate_assignment(
                raw_assignment, normalized_taxonomy.to_payload()
            )
            if parsed_assignment.paper_id in seen_paper_ids:
                raise ValueError(f"duplicate paper_id: {parsed_assignment.paper_id}")
        except ValueError as exc:
            raise ValueError(f"assignment on line {line_number}: {exc}") from exc
        seen_paper_ids.add(parsed_assignment.paper_id)
        assignments.append(parsed_assignment)

    if expected_paper_ids is not None:
        expected = set(expected_paper_ids)
        missing_paper_ids = expected - seen_paper_ids
        unexpected_paper_ids = seen_paper_ids - expected
        if missing_paper_ids:
            raise ValueError(f"missing paper IDs: {sorted(missing_paper_ids)}")
        if unexpected_paper_ids:
            raise ValueError(f"unknown paper IDs: {sorted(unexpected_paper_ids)}")
    return assignments


def wilson_lower(
    successes: int,
    total: int,
    z: Decimal | float | str = _WILSON_Z_95,
) -> Decimal:
    """Return the two-sided 95% Wilson lower confidence bound using Decimal math."""
    if (
        isinstance(successes, bool)
        or isinstance(total, bool)
        or not isinstance(successes, int)
        or not isinstance(total, int)
        or total <= 0
        or not 0 <= successes <= total
    ):
        raise ValueError("successes must be between zero and a positive total")
    decimal_z = _as_finite_decimal(z, field="z")
    if decimal_z <= 0:
        raise ValueError("z must be greater than zero")
    probability = Decimal(successes) / Decimal(total)
    squared_z = decimal_z * decimal_z
    denominator = Decimal(1) + squared_z / Decimal(total)
    centre = probability + squared_z / (Decimal(2) * Decimal(total))
    margin = (
        decimal_z
        * (
            (
                probability * (Decimal(1) - probability)
                + squared_z / (Decimal(4) * total)
            )
            / Decimal(total)
        ).sqrt()
    )
    return (centre - margin) / denominator


def audit_theme(sample: Sequence[bool]) -> ThemeAudit:
    """Calculate auditable classification precision for one reviewed sample."""
    if len(sample) > _MAX_AUDIT_SAMPLE_SIZE:
        raise ValueError(
            f"audit sample must contain at most {_MAX_AUDIT_SAMPLE_SIZE} decisions"
        )
    if any(type(decision) is not bool for decision in sample):
        raise ValueError("audit sample decisions must be booleans")
    sample_size = len(sample)
    correct_count = sum(sample)
    if sample_size == 0:
        return ThemeAudit(
            sample_size=0,
            correct_count=0,
            observed_precision=Decimal(0),
            wilson_lower_95=Decimal(0),
        )
    return ThemeAudit(
        sample_size=sample_size,
        correct_count=correct_count,
        observed_precision=Decimal(correct_count) / Decimal(sample_size),
        wilson_lower_95=wilson_lower(correct_count, sample_size),
    )


def assert_theme_publishable(audit: ThemeAudit) -> None:
    """Block publication unless both declared audit thresholds are satisfied."""
    reasons: list[str] = []
    if audit.sample_size == 0:
        reasons.append("empty audit sample")
    if audit.observed_precision < _MINIMUM_PRECISION:
        reasons.append(
            "observed precision "
            f"{audit.observed_precision} is below {_MINIMUM_PRECISION}"
        )
    if audit.wilson_lower_95 < _MINIMUM_WILSON_LOWER_95:
        reasons.append(
            "Wilson 95% lower bound "
            f"{audit.wilson_lower_95} is below {_MINIMUM_WILSON_LOWER_95}"
        )
    if reasons:
        raise PublicationBlocked("theme publication blocked: " + "; ".join(reasons))
