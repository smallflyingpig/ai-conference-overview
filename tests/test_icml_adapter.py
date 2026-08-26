import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from conference_overview.adapters.icml import (
    FetchedIcmlSource,
    IcmlRawCorpus,
    IcmlSourceFormatError,
    fetch_icml_sources,
    parse_icml_sources,
)
from conference_overview.models import RecordStatus, SourceRef, VenueRequest
from conference_overview.registry import normalize_request

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "icml"


def icml_request() -> VenueRequest:
    return normalize_request("ICML", 2026, "main")


def fetched(kind: str, name: str) -> FetchedIcmlSource:
    data = (FIXTURE_DIR / name).read_bytes()
    return FetchedIcmlSource(
        kind=kind,
        url=f"https://icml.cc/{name}",
        data=data,
        source=SourceRef(
            name=name,
            url=f"https://icml.cc/{name}",
            retrieved_at=datetime(2026, 8, 26, tzinfo=UTC),
            sha256="a" * 64,
        ),
    )


def fixture_corpus() -> IcmlRawCorpus:
    return IcmlRawCorpus(
        event_pages=(
            fetched("events", "events-page-1.json"),
            fetched("events", "events-page-2.json"),
        ),
        abstracts=fetched("abstracts", "abstracts.json"),
        openreview_pages=(fetched("openreview", "openreview-accepted.json"),),
    )


def test_parser_uses_openreview_venueid_as_the_accepted_population() -> None:
    result = parse_icml_sources(fixture_corpus(), icml_request())

    assert [paper.paper_id for paper in result.included] == [
        "icml:2026:forum-main-1",
        "icml:2026:forum-main-2",
        "icml:2026:forum-main-3",
    ]
    assert {paper.track for paper in result.included} == {"main"}
    assert all(
        paper.native_metadata["openreview_venueid"]
        == "ICML.cc/2026/Conference"
        for paper in result.included
    )


def test_parser_merges_poster_and_oral_rows_without_duplicate_papers() -> None:
    result = parse_icml_sources(fixture_corpus(), icml_request())
    spotlight = next(
        paper
        for paper in result.included
        if paper.paper_id == "icml:2026:forum-main-2"
    )

    assert spotlight.native_metadata["presentation_types"] == ["Oral", "Poster"]
    assert spotlight.native_metadata["event_ids"] == ["102", "202"]


def test_parser_excludes_non_main_openreview_venueids() -> None:
    result = parse_icml_sources(fixture_corpus(), icml_request())

    assert {
        paper.native_metadata["openreview_venueid"] for paper in result.excluded
    } == {
        "ICML.cc/2026/Position_Paper_Track",
        "ICML.cc/2026/Journal_Track",
    }


def test_parser_keeps_missing_abstract_as_partial() -> None:
    result = parse_icml_sources(fixture_corpus(), icml_request())
    paper = next(
        paper
        for paper in result.included
        if paper.paper_id == "icml:2026:forum-main-3"
    )

    assert paper.abstract is None
    assert paper.status is RecordStatus.PARTIAL


def test_parser_rejects_conflicting_duplicate_event_identity() -> None:
    corpus = fixture_corpus()
    page = json.loads(corpus.event_pages[1].data)
    page["results"][0]["name"] = "Conflicting Camera Ready Title"
    changed = corpus.event_pages[1].__class__(
        **{
            **corpus.event_pages[1].__dict__,
            "data": json.dumps(page).encode(),
        }
    )
    corpus = IcmlRawCorpus(
        event_pages=(corpus.event_pages[0], changed),
        abstracts=corpus.abstracts,
        openreview_pages=corpus.openreview_pages,
    )

    with pytest.raises(IcmlSourceFormatError, match="conflicting event identity"):
        parse_icml_sources(corpus, icml_request())


def _client_for_pages(*, next_url: str, declared_count: int = 4) -> httpx.Client:
    first = json.loads((FIXTURE_DIR / "events-page-1.json").read_text())
    first["next"] = next_url
    first["count"] = declared_count
    second = json.loads((FIXTURE_DIR / "events-page-2.json").read_text())
    second["count"] = declared_count
    abstracts = (FIXTURE_DIR / "abstracts.json").read_bytes()
    openreview = (FIXTURE_DIR / "openreview-accepted.json").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == str(icml_request().source_urls["events"]):
            return httpx.Response(200, json=first, request=request)
        if url == "https://icml.cc/api/miniconf/events?offset=2":
            return httpx.Response(200, json=second, request=request)
        if url == str(icml_request().source_urls["abstracts"]):
            return httpx.Response(200, content=abstracts, request=request)
        if url.startswith("https://api2.openreview.net/notes?"):
            return httpx.Response(200, content=openreview, request=request)
        raise AssertionError(f"unexpected request: {url}")

    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    "next_url",
    ["https://evil.example/api?page=2", "ftp://icml.cc/api?page=2"],
)
def test_fetch_rejects_unsafe_pagination(next_url: str) -> None:
    with (
        _client_for_pages(next_url=next_url) as client,
        pytest.raises(IcmlSourceFormatError, match="pagination URL"),
    ):
        fetch_icml_sources(icml_request(), client)


def test_fetch_upgrades_only_icml_same_host_http_next() -> None:
    with _client_for_pages(
        next_url="http://icml.cc/api/miniconf/events?offset=2"
    ) as client:
        corpus = fetch_icml_sources(icml_request(), client)

    assert len(corpus.event_pages) == 2
    assert str(corpus.event_pages[1].source.url).startswith("https://icml.cc/")


def test_fetch_rejects_page_cycle() -> None:
    with (
        _client_for_pages(next_url=str(icml_request().source_urls["events"])) as client,
        pytest.raises(IcmlSourceFormatError, match="cycle"),
    ):
        fetch_icml_sources(icml_request(), client)


def test_fetch_rejects_declared_count_mismatch() -> None:
    with (
        _client_for_pages(
            next_url="http://icml.cc/api/miniconf/events?offset=2",
            declared_count=5,
        ) as client,
        pytest.raises(IcmlSourceFormatError, match="count"),
    ):
        fetch_icml_sources(icml_request(), client)
