import httpx
import pytest

from conference_overview.fetch import SourceFetchError, fetch_bytes


def test_fetch_returns_success_response_with_fixed_request_policy() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == "ai-conference-overview/0.1"
        assert request.extensions["timeout"] == {
            "connect": 30.0,
            "read": 30.0,
            "write": 30.0,
            "pool": 30.0,
        }
        return httpx.Response(200, content=b"volume-data", request=request)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        assert fetch_bytes("https://example.test/volume.bib", client) == b"volume-data"


def test_fetch_rejects_a_short_body_against_official_content_length() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"partial",
            headers={"content-length": "100"},
            request=request,
        )
    )

    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(SourceFetchError, match="content length"),
    ):
        fetch_bytes("https://example.test/volume.bib", client)


def test_fetch_retries_retryable_status_until_success() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        status_code = 503 if requests < 3 else 200
        return httpx.Response(status_code, content=b"volume-data", request=request)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        assert fetch_bytes("https://example.test/volume.bib", client) == b"volume-data"

    assert requests == 3


def test_fetch_stops_after_three_retryable_responses() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(429, request=request)

    transport = httpx.MockTransport(handler)

    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(SourceFetchError) as error,
    ):
        fetch_bytes("https://example.test/volume.bib", client)

    assert error.value.url == "https://example.test/volume.bib"
    assert error.value.status_code == 429
    assert requests == 3


def test_fetch_rejects_non_success_response_without_retry() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(404, request=request)

    transport = httpx.MockTransport(handler)

    with (
        httpx.Client(transport=transport) as client,
        pytest.raises(SourceFetchError) as error,
    ):
        fetch_bytes("https://example.test/volume.bib", client)

    assert error.value.status_code == 404
    assert requests == 1


def test_fetch_retries_transport_errors() -> None:
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests < 3:
            raise httpx.ConnectError("temporary network failure", request=request)
        return httpx.Response(200, content=b"volume-data", request=request)

    transport = httpx.MockTransport(handler)

    with httpx.Client(transport=transport) as client:
        assert fetch_bytes("https://example.test/volume.bib", client) == b"volume-data"

    assert requests == 3
