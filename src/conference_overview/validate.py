"""Reconcile canonical paper records before publishing a release."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import combinations

from conference_overview.models import PaperRecord, RecordStatus

_INCLUDED_STATUSES = frozenset(
    {RecordStatus.COMPLETE, RecordStatus.PARTIAL, RecordStatus.UNRESOLVED}
)


class PublicationBlocked(RuntimeError):
    """Raised when a validation report has unresolved publication gates."""


@dataclass(frozen=True)
class ValidationReport:
    """Deterministic reconciliation and review diagnostics for a record set."""

    discovered_count: int
    included_count: int
    excluded_count: int
    expected_included: int | None
    expected_count_matches: bool
    missing_abstract_ids: list[str]
    missing_pdf_ids: list[str]
    missing_doi_ids: list[str]
    duplicate_source_ids: list[str]
    duplicate_dois: list[str]
    definite_duplicate_pairs: list[tuple[str, str]]
    duplicate_candidates: list[tuple[str, str]]
    status_mismatch_ids: list[str]
    unresolved_record_ids: list[str]
    previous_snapshot_additions: list[str]
    previous_snapshot_removals: list[str]
    publishable: bool

    @property
    def duplicate_candidate_count(self) -> int:
        """Return the number of title-equality pairs that need review."""
        return len(self.duplicate_candidates)

    @property
    def definite_duplicate_count(self) -> int:
        """Return the number of exact source-ID or DOI duplicate pairs."""
        return len(self.definite_duplicate_pairs)


def _duplicate_keys(
    records: Sequence[PaperRecord], key: Callable[[PaperRecord], str | None]
) -> list[str]:
    occurrences: dict[str, int] = {}
    for record in records:
        value = key(record)
        if value is not None:
            occurrences[value] = occurrences.get(value, 0) + 1
    return [value for value, count in occurrences.items() if count > 1]


def _duplicate_pairs(
    records: Sequence[PaperRecord], key: Callable[[PaperRecord], str | None]
) -> list[tuple[str, str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for record in records:
        value = key(record)
        if value is not None:
            grouped[value].append(record.paper_id)
    return [pair for ids in grouped.values() for pair in combinations(ids, 2)]


def _present_text(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def validate_records(
    included: Sequence[PaperRecord],
    excluded: Sequence[PaperRecord],
    *,
    expected_included: int | None = None,
    previous_snapshot: Sequence[PaperRecord] | None = None,
) -> ValidationReport:
    """Report reconciliation diagnostics without deleting or changing records."""
    included_records = list(included)
    excluded_records = list(excluded)
    discovered_records = [*included_records, *excluded_records]

    duplicate_source_ids = _duplicate_keys(discovered_records, lambda record: record.paper_id)
    duplicate_dois = _duplicate_keys(
        discovered_records,
        lambda record: record.doi if _present_text(record.doi) else None,
    )
    source_id_pairs = _duplicate_pairs(discovered_records, lambda record: record.paper_id)
    doi_pairs = _duplicate_pairs(
        discovered_records,
        lambda record: record.doi if _present_text(record.doi) else None,
    )
    definite_duplicate_pairs = list(dict.fromkeys([*source_id_pairs, *doi_pairs]))
    duplicate_candidates = _duplicate_pairs(
        discovered_records,
        lambda record: record.normalized_title,
    )

    status_mismatch_ids = [
        record.paper_id
        for record in included_records
        if record.status is RecordStatus.EXCLUDED
    ] + [
        record.paper_id
        for record in excluded_records
        if record.status is not RecordStatus.EXCLUDED
    ]
    unresolved_record_ids = [
        record.paper_id
        for record in discovered_records
        if record.status is RecordStatus.UNRESOLVED
    ]
    current_ids = {
        record.paper_id
        for record in included_records
        if record.status in _INCLUDED_STATUSES
    }
    previous_ids = (
        {
            record.paper_id
            for record in previous_snapshot
            if record.status in _INCLUDED_STATUSES
        }
        if previous_snapshot is not None
        else None
    )
    expected_count_matches = (
        expected_included is None or len(included_records) == expected_included
    )
    publishable = (
        expected_count_matches
        and not definite_duplicate_pairs
        and not duplicate_candidates
        and not status_mismatch_ids
        and not unresolved_record_ids
    )

    return ValidationReport(
        discovered_count=len(discovered_records),
        included_count=len(included_records),
        excluded_count=len(excluded_records),
        expected_included=expected_included,
        expected_count_matches=expected_count_matches,
        missing_abstract_ids=[
            record.paper_id for record in included_records if not _present_text(record.abstract)
        ],
        missing_pdf_ids=[
            record.paper_id for record in included_records if record.pdf_url is None
        ],
        missing_doi_ids=[
            record.paper_id for record in included_records if not _present_text(record.doi)
        ],
        duplicate_source_ids=duplicate_source_ids,
        duplicate_dois=duplicate_dois,
        definite_duplicate_pairs=definite_duplicate_pairs,
        duplicate_candidates=duplicate_candidates,
        status_mismatch_ids=status_mismatch_ids,
        unresolved_record_ids=unresolved_record_ids,
        previous_snapshot_additions=(
            sorted(current_ids - previous_ids) if previous_ids is not None else []
        ),
        previous_snapshot_removals=(
            sorted(previous_ids - current_ids) if previous_ids is not None else []
        ),
        publishable=publishable,
    )


def assert_publishable(report: ValidationReport) -> None:
    """Raise a clear error when a report cannot safely replace a release."""
    reasons: list[str] = []
    if not report.expected_count_matches:
        reasons.append(
            "included count mismatch "
            f"(expected {report.expected_included}, found {report.included_count})"
        )
    if report.definite_duplicate_pairs:
        reasons.append("definite duplicates require resolution")
    if report.duplicate_candidates:
        reasons.append("duplicate candidates require review")
    if report.status_mismatch_ids:
        reasons.append("status/list mismatch requires correction")
    if report.unresolved_record_ids:
        reasons.append("unresolved records require resolution")
    if reasons:
        raise PublicationBlocked("publication blocked: " + "; ".join(reasons))
