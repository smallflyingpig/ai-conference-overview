from datetime import UTC, datetime
from pathlib import Path

from conference_overview.adapters.acl import enrich_acl_abstracts, parse_acl_bibtex
from conference_overview.models import RecordStatus, SourceRef, VenueRequest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "acl"
BIB_FIXTURE = FIXTURE_DIR / "2026-long-sample.bib"
HTML_FIXTURE = FIXTURE_DIR / "2026-long-sample.html"


def acl_request() -> VenueRequest:
    return VenueRequest(venue="ACL", year=2026, track="long")


def bib_source() -> SourceRef:
    return SourceRef(
        name="ACL Anthology BibTeX",
        url="https://aclanthology.org/volumes/2026.acl-long.bib",
        retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
        sha256="b" * 64,
    )


def html_source() -> SourceRef:
    return SourceRef(
        name="ACL Anthology volume HTML",
        url="https://aclanthology.org/volumes/2026.acl-long/",
        retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
        sha256="h" * 64,
    )


def test_acl_adapter_excludes_proceedings_record() -> None:
    included, excluded = parse_acl_bibtex(BIB_FIXTURE.read_bytes(), acl_request(), bib_source())

    assert [paper.paper_id for paper in included] == [
        "acl:2026.acl-long.1",
        "acl:2026.acl-long.2",
    ]
    assert [paper.paper_id for paper in excluded] == ["acl:2026.acl-long.0"]
    assert all(paper.track == "long" for paper in included)
    assert excluded[0].status is RecordStatus.EXCLUDED


def test_acl_adapter_preserves_bibtex_metadata_for_included_papers() -> None:
    included, _ = parse_acl_bibtex(BIB_FIXTURE.read_bytes(), acl_request(), bib_source())

    first = included[0]
    assert first.title == "Tool-Using Agents for NLP"
    assert first.normalized_title == "tool-using agents for nlp"
    assert first.authors == ["Smith, Alice", "Doe, John"]
    assert str(first.pdf_url) == "https://aclanthology.org/2026.acl-long.1.pdf"
    assert first.doi == "10.18653/v1/2026.acl-long.1"
    assert first.source == bib_source()


def test_acl_volume_html_adds_abstract_by_acl_id() -> None:
    included, _ = parse_acl_bibtex(BIB_FIXTURE.read_bytes(), acl_request(), bib_source())

    enriched = enrich_acl_abstracts(included, HTML_FIXTURE.read_bytes(), html_source())

    assert enriched[0].abstract == "This paper studies tool-using agents."
    assert enriched[0].source == bib_source()


def test_acl_volume_html_does_not_join_abstracts_by_title() -> None:
    included, _ = parse_acl_bibtex(BIB_FIXTURE.read_bytes(), acl_request(), bib_source())

    enriched = enrich_acl_abstracts(included, HTML_FIXTURE.read_bytes(), html_source())

    assert enriched[1].abstract is None
