import pytest

from conference_overview.models import PaperRecord, RecordStatus, SourceRef
from conference_overview.validate import (
    PublicationBlocked,
    assert_publishable,
    validate_records,
)

_DEFAULT_DOI = object()


def paper(
    paper_id: str,
    title: str,
    *,
    abstract: str | None = "An abstract.",
    pdf: bool = True,
    doi: str | None | object = _DEFAULT_DOI,
) -> PaperRecord:
    doi_value = f"10.1000/{paper_id}" if doi is _DEFAULT_DOI else doi
    return PaperRecord(
        paper_id=paper_id,
        title=title,
        normalized_title=" ".join(title.casefold().split()),
        authors=["A. Author"],
        venue="ACL",
        year=2026,
        track="long",
        landing_url=f"https://aclanthology.org/{paper_id}/",
        source=SourceRef(
            name="ACL Anthology",
            url="https://aclanthology.org/volumes/2026.acl-long/",
        ),
        status=RecordStatus.COMPLETE,
        abstract=abstract,
        pdf_url=(f"https://aclanthology.org/{paper_id}.pdf" if pdf else None),
        doi=doi_value,
    )


def test_fuzzy_duplicate_blocks_without_deleting() -> None:
    records = [paper("p1", "A Study of Agents"), paper("p2", "A study of agents")]

    report = validate_records(records, [], expected_included=2)

    assert report.included_count == 2
    assert report.duplicate_candidates == [("p1", "p2")]
    assert records == [paper("p1", "A Study of Agents"), paper("p2", "A study of agents")]
    with pytest.raises(PublicationBlocked, match="duplicate candidates"):
        assert_publishable(report)


def test_expected_count_mismatch_blocks_publication() -> None:
    report = validate_records([paper("p1", "One")], [], expected_included=2)

    assert report.publishable is False
    with pytest.raises(PublicationBlocked, match="included count mismatch"):
        assert_publishable(report)


def test_report_reconciles_missingness_and_snapshot_changes() -> None:
    included = [
        paper("p1", "Present"),
        paper("p2", "New", abstract=None, pdf=False, doi=None),
    ]
    excluded = [paper("front-matter", "Proceedings")]
    previous_snapshot = [paper("p1", "Present"), paper("p3", "Removed")]

    report = validate_records(
        included,
        excluded,
        expected_included=2,
        previous_snapshot=previous_snapshot,
    )

    assert report.discovered_count == 3
    assert report.included_count == 2
    assert report.excluded_count == 1
    assert report.missing_abstract_ids == ["p2"]
    assert report.missing_pdf_ids == ["p2"]
    assert report.missing_doi_ids == ["p2"]
    assert report.previous_snapshot_additions == ["p2"]
    assert report.previous_snapshot_removals == ["p3"]
    assert report.publishable is True


def test_exact_source_id_and_doi_duplicates_block_publication() -> None:
    records = [
        paper("same-id", "First", doi="10.1000/one"),
        paper("same-id", "Second", doi="10.1000/two"),
        paper("third", "Third", doi="10.1000/two"),
    ]

    report = validate_records(records, [], expected_included=3)

    assert report.duplicate_source_ids == ["same-id"]
    assert report.duplicate_dois == ["10.1000/two"]
    with pytest.raises(PublicationBlocked, match="definite duplicates"):
        assert_publishable(report)


def test_absent_previous_snapshot_has_no_synthetic_changes() -> None:
    report = validate_records([paper("p1", "One")], [])

    assert report.previous_snapshot_additions == []
    assert report.previous_snapshot_removals == []
