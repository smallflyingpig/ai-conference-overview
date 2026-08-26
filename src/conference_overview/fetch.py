import httpx

USER_AGENT = "ai-conference-overview/0.1"
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_ATTEMPTS = 3


class SourceFetchError(RuntimeError):
    def __init__(
        self,
        *,
        url: str,
        status_code: int | None = None,
        detail: str | None = None,
    ) -> None:
        self.url = url
        self.status_code = status_code
        error_detail = (
            detail
            if detail is not None
            else f"HTTP {status_code}"
            if status_code is not None
            else "transport error"
        )
        super().__init__(f"Could not fetch {url}: {error_detail}")


def fetch_bytes(url: str, client: httpx.Client) -> bytes:
    """Retrieve a source with bounded retries for transient failures only."""
    last_status_code: int | None = None

    for _ in range(MAX_ATTEMPTS):
        try:
            response = client.get(
                url,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.TransportError:
            continue

        if response.status_code == httpx.codes.OK:
            content = response.content
            declared_length = response.headers.get("content-length")
            if declared_length is not None:
                try:
                    expected_length = int(declared_length)
                except ValueError as exc:
                    raise SourceFetchError(
                        url=url,
                        status_code=response.status_code,
                        detail="invalid content length header",
                    ) from exc
                if expected_length != len(content):
                    raise SourceFetchError(
                        url=url,
                        status_code=response.status_code,
                        detail=(
                            "content length mismatch "
                            f"(expected {expected_length}, received {len(content)})"
                        ),
                    )
            return content
        if (
            response.status_code == httpx.codes.TOO_MANY_REQUESTS
            or 500 <= response.status_code < 600
        ):
            last_status_code = response.status_code
            continue
        raise SourceFetchError(url=url, status_code=response.status_code)

    raise SourceFetchError(url=url, status_code=last_status_code)
