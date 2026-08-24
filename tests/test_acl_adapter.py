from datetime import UTC, datetime
from pathlib import Path

import pytest

from conference_overview.adapters.acl import (
    AclSourceFormatError,
    enrich_acl_abstracts,
    parse_acl_award_badges,
    parse_acl_bibtex,
)
from conference_overview.models import RecordStatus, SourceRef, VenueRequest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "acl"
BIB_FIXTURE = FIXTURE_DIR / "2026-long-sample.bib"
HTML_FIXTURE = FIXTURE_DIR / "2026-long-sample.html"
DIV_SIBLINGS_FIXTURE = FIXTURE_DIR / "2026-long-div-siblings.html"
UNRECOGNIZED_HTML_FIXTURE = FIXTURE_DIR / "2026-long-unrecognized.html"
MISSING_PAPER_URL_FIXTURE = FIXTURE_DIR / "2026-long-missing-url-inproceedings.bib"
MISSING_PROCEEDINGS_URL_FIXTURE = FIXTURE_DIR / "2026-long-missing-url-proceedings.bib"


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
    included, excluded = parse_acl_bibtex(
        BIB_FIXTURE.read_bytes(), acl_request(), bib_source()
    )

    assert [paper.paper_id for paper in included] == [
        "acl:2026.acl-long.1",
        "acl:2026.acl-long.2",
    ]
    assert [paper.paper_id for paper in excluded] == ["acl:2026.acl-long.0"]
    assert all(paper.track == "long" for paper in included)
    assert excluded[0].status is RecordStatus.EXCLUDED


def test_acl_adapter_preserves_bibtex_metadata_for_included_papers() -> None:
    included, _ = parse_acl_bibtex(
        BIB_FIXTURE.read_bytes(), acl_request(), bib_source()
    )

    first = included[0]
    assert first.title == "Tool-Using Agents for NLP"
    assert first.normalized_title == "tool-using agents for nlp"
    assert first.authors == ["Smith, Alice", "Doe, John"]
    assert str(first.pdf_url) == "https://aclanthology.org/2026.acl-long.1.pdf"
    assert first.doi == "10.18653/v1/2026.acl-long.1"
    assert first.source == bib_source()


def test_acl_volume_html_adds_abstract_by_acl_id() -> None:
    included, _ = parse_acl_bibtex(
        BIB_FIXTURE.read_bytes(), acl_request(), bib_source()
    )

    enriched = enrich_acl_abstracts(included, HTML_FIXTURE.read_bytes(), html_source())

    assert enriched[0].abstract == "This paper studies tool-using agents."
    assert enriched[0].source == bib_source()


def test_acl_volume_html_does_not_join_abstracts_by_title() -> None:
    included, _ = parse_acl_bibtex(
        BIB_FIXTURE.read_bytes(), acl_request(), bib_source()
    )

    enriched = enrich_acl_abstracts(included, HTML_FIXTURE.read_bytes(), html_source())

    assert enriched[1].abstract is None


def test_acl_volume_html_keeps_div_card_abstracts_in_their_own_cards() -> None:
    included, _ = parse_acl_bibtex(
        BIB_FIXTURE.read_bytes(), acl_request(), bib_source()
    )

    enriched = enrich_acl_abstracts(
        included, DIV_SIBLINGS_FIXTURE.read_bytes(), html_source()
    )

    assert [paper.abstract for paper in enriched] == [
        "The first trusted abstract.",
        "The second trusted abstract.",
    ]


def test_acl_volume_html_rejects_nonempty_markup_without_trusted_pairs() -> None:
    included, _ = parse_acl_bibtex(
        BIB_FIXTURE.read_bytes(), acl_request(), bib_source()
    )

    with pytest.raises(
        AclSourceFormatError, match="zero trusted ACL ID/abstract pairs"
    ):
        enrich_acl_abstracts(
            included, UNRECOGNIZED_HTML_FIXTURE.read_bytes(), html_source()
        )


def test_acl_bibtex_rejects_inproceedings_without_canonical_acl_url() -> None:
    with pytest.raises(AclSourceFormatError, match="inproceedings entry broken-paper"):
        parse_acl_bibtex(
            MISSING_PAPER_URL_FIXTURE.read_bytes(), acl_request(), bib_source()
        )


def test_acl_bibtex_rejects_proceedings_without_canonical_acl_url() -> None:
    with pytest.raises(
        AclSourceFormatError, match="proceedings entry broken-proceedings"
    ):
        parse_acl_bibtex(
            MISSING_PROCEEDINGS_URL_FIXTURE.read_bytes(), acl_request(), bib_source()
        )


def test_acl_bibtex_rejects_a_truncated_final_entry() -> None:
    complete = BIB_FIXTURE.read_bytes()

    with pytest.raises(AclSourceFormatError, match="complete|entry"):
        parse_acl_bibtex(complete[:-3], acl_request(), bib_source())


def test_acl_volume_html_supports_the_official_2026_card_shape() -> None:
    included, _ = parse_acl_bibtex(
        BIB_FIXTURE.read_bytes(), acl_request(), bib_source()
    )
    html = b"""<!doctype html><div class=\"d-sm-flex align-items-stretch mb-3\">
      <div class=\"d-block me-2 list-button-row\">
        <span title=\"Outstanding Paper\" aria-label=\"Outstanding Paper\"><i></i></span>
      </div>
      <span class=d-block><strong><a href=/2026.acl-long.1/>Paper</a></strong></span>
    </div>
    <div class=\"card bg-light collapse abstract-collapse\" id=abstract-2026--acl-long--1>
      <div class=\"card-body p-3 small\">Official card abstract.</div>
    </div>"""

    enriched = enrich_acl_abstracts(included, html, html_source())
    badges = parse_acl_award_badges(html, html_source())

    assert enriched[0].abstract == "Official card abstract."
    assert badges == [
        {
            "acl_id": "2026.acl-long.1",
            "award_type": "Outstanding Paper",
            "evidence_locator": (
                "volume HTML paper row 2026.acl-long.1; "
                "span[title='Outstanding Paper'][aria-label='Outstanding Paper']"
            ),
        }
    ]
