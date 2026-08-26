"""Parse official ICML virtual-program and OpenReview records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import httpx

from conference_overview.adapters.acl import normalize_title
from conference_overview.fetch import fetch_bytes
from conference_overview.models import (
    PaperRecord,
    RecordStatus,
    SourceRef,
    VenueRequest,
)

_MAIN_VENUE_ID = "ICML.cc/2026/Conference"
_KNOWN_NON_MAIN_VENUE_IDS = frozenset(
    {
        "ICML.cc/2026/Position_Paper_Track",
        "ICML.cc/2026/Journal_Track",
    }
)
_OPENREVIEW_API = "https://api2.openreview.net/notes"
_MAX_PAGES = 100
_OPENREVIEW_LIMIT = 1000


class IcmlSourceFormatError(ValueError):
    """Raised when an official ICML payload cannot be interpreted safely."""


@dataclass(frozen=True)
class FetchedIcmlSource:
    kind: str
    url: str
    data: bytes
    source: SourceRef


@dataclass(frozen=True)
class IcmlRawCorpus:
    event_pages: tuple[FetchedIcmlSource, ...]
    abstracts: FetchedIcmlSource
    openreview_pages: tuple[FetchedIcmlSource, ...]


@dataclass(frozen=True)
class IcmlParseResult:
    included: tuple[PaperRecord, ...]
    excluded: tuple[PaperRecord, ...]
    unresolved: tuple[PaperRecord, ...]
    presentation_row_count: int


def _json_object(fetched: FetchedIcmlSource) -> dict[str, Any]:
    try:
        payload = json.loads(fetched.data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IcmlSourceFormatError(
            f"{fetched.kind} source is not valid UTF-8 JSON: {fetched.url}"
        ) from exc
    if not isinstance(payload, dict):
        raise IcmlSourceFormatError(
            f"{fetched.kind} source must be a JSON object: {fetched.url}"
        )
    return payload


def _fetched(kind: str, url: str, data: bytes) -> FetchedIcmlSource:
    return FetchedIcmlSource(
        kind=kind,
        url=url,
        data=data,
        source=SourceRef(
            name=f"ICML 2026 {kind}",
            url=url,
            retrieved_at=datetime.now(UTC),
            sha256=hashlib.sha256(data).hexdigest(),
        ),
    )


def _canonical_event_page_url(url: str, *, seed: str) -> str:
    parsed = urlparse(url)
    seed_parsed = urlparse(seed)
    if parsed.scheme not in {"http", "https"} or parsed.hostname != seed_parsed.hostname:
        raise IcmlSourceFormatError(f"unsafe pagination URL: {url}")
    if parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
        raise IcmlSourceFormatError(f"unsafe pagination URL: {url}")
    return urlunparse(("https", parsed.netloc.split(":", 1)[0], parsed.path, "", parsed.query, ""))


def _fetch_event_pages(seed_url: str, client: httpx.Client) -> tuple[FetchedIcmlSource, ...]:
    pages: list[FetchedIcmlSource] = []
    visited: set[str] = set()
    next_url: str | None = _canonical_event_page_url(seed_url, seed=seed_url)
    declared_count: int | None = None
    row_count = 0

    while next_url is not None:
        if len(pages) >= _MAX_PAGES:
            raise IcmlSourceFormatError("event pagination exceeds 100 pages")
        if next_url in visited:
            raise IcmlSourceFormatError(f"event pagination cycle at {next_url}")
        visited.add(next_url)
        data = fetch_bytes(next_url, client)
        page = _fetched("events", next_url, data)
        payload = _json_object(page)
        count = payload.get("count")
        results = payload.get("results")
        if not isinstance(count, int) or count < 0 or not isinstance(results, list):
            raise IcmlSourceFormatError("event page has invalid count or results")
        if declared_count is None:
            declared_count = count
        elif count != declared_count:
            raise IcmlSourceFormatError("event page count changed during pagination")
        row_count += len(results)
        pages.append(page)
        raw_next = payload.get("next")
        if raw_next is not None and not isinstance(raw_next, str):
            raise IcmlSourceFormatError("event pagination URL must be text or null")
        next_url = (
            _canonical_event_page_url(raw_next, seed=seed_url)
            if raw_next is not None
            else None
        )

    if declared_count is None or row_count != declared_count:
        raise IcmlSourceFormatError(
            f"event count mismatch: declared {declared_count}, received {row_count}"
        )
    return tuple(pages)


def _openreview_page_url(offset: int) -> str:
    return f"{_OPENREVIEW_API}?{urlencode({'content.venueid': _MAIN_VENUE_ID, 'limit': _OPENREVIEW_LIMIT, 'offset': offset})}"


def _fetch_openreview_pages(client: httpx.Client) -> tuple[FetchedIcmlSource, ...]:
    pages: list[FetchedIcmlSource] = []
    offset = 0
    declared_count: int | None = None
    note_count = 0
    while declared_count is None or note_count < declared_count:
        if len(pages) >= _MAX_PAGES:
            raise IcmlSourceFormatError("OpenReview pagination exceeds 100 pages")
        url = _openreview_page_url(offset)
        data = fetch_bytes(url, client)
        page = _fetched("openreview", url, data)
        payload = _json_object(page)
        count = payload.get("count")
        notes = payload.get("notes")
        if not isinstance(count, int) or count < 0 or not isinstance(notes, list):
            raise IcmlSourceFormatError("OpenReview page has invalid count or notes")
        if declared_count is None:
            declared_count = count
        elif count != declared_count:
            raise IcmlSourceFormatError("OpenReview count changed during pagination")
        if not notes and note_count < declared_count:
            raise IcmlSourceFormatError("OpenReview pagination stopped before count")
        pages.append(page)
        note_count += len(notes)
        offset += len(notes)
    if note_count != declared_count:
        raise IcmlSourceFormatError(
            f"OpenReview count mismatch: declared {declared_count}, received {note_count}"
        )
    return tuple(pages)


def fetch_icml_sources(
    request: VenueRequest, client: httpx.Client
) -> IcmlRawCorpus:
    """Fetch the bounded set of official sources required for ICML parsing."""
    if request.adapter != "icml_virtual" or request.track != "main":
        raise IcmlSourceFormatError("request is not the configured ICML main scope")
    required = {"events", "abstracts", "openreview_group", "papers_page"}
    if set(request.source_urls) != required:
        raise IcmlSourceFormatError("ICML request does not declare the exact source set")

    events_url = str(request.source_urls["events"])
    abstracts_url = str(request.source_urls["abstracts"])
    return IcmlRawCorpus(
        event_pages=_fetch_event_pages(events_url, client),
        abstracts=_fetched(
            "abstracts", abstracts_url, fetch_bytes(abstracts_url, client)
        ),
        openreview_pages=_fetch_openreview_pages(client),
    )


def _content_value(content: object, field: str) -> object:
    if not isinstance(content, Mapping):
        return None
    wrapped = content.get(field)
    if not isinstance(wrapped, Mapping):
        return None
    return wrapped.get("value")


def _forum_id_from_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != "openreview.net":
        return None
    forum_values = parse_qs(parsed.query).get("id", [])
    if len(forum_values) != 1 or not forum_values[0].strip():
        return None
    return forum_values[0].strip()


def _clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split())
    return normalized or None


def _authors(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalized for item in value if (normalized := _clean_text(item))]


def _event_authors(row: Mapping[str, object]) -> list[str]:
    raw = row.get("authors")
    if not isinstance(raw, list):
        return []
    return [
        name
        for item in raw
        if isinstance(item, Mapping)
        and (name := _clean_text(item.get("fullname"))) is not None
    ]


def _venue_id_from_event(row: Mapping[str, object]) -> str | None:
    sourceurl = row.get("sourceurl")
    if not isinstance(sourceurl, str):
        return None
    parsed = urlparse(sourceurl)
    if parsed.scheme != "https" or parsed.hostname != "openreview.net":
        return None
    groups = parse_qs(parsed.query).get("id", [])
    return groups[0] if len(groups) == 1 else None


def _record_from_note(
    note: Mapping[str, object],
    *,
    request: VenueRequest,
    source: SourceRef,
    event_rows: tuple[Mapping[str, object], ...],
) -> PaperRecord:
    content = note.get("content")
    forum = _clean_text(note.get("forum"))
    note_id = _clean_text(note.get("id")) or "unknown"
    title = _clean_text(_content_value(content, "title"))
    authors = _authors(_content_value(content, "authors"))
    venueid = _clean_text(_content_value(content, "venueid"))
    malformed = forum is None or title is None or venueid is None
    stable_id = forum or f"unresolved-{note_id}"

    event_ids: list[str] = []
    presentation_types: list[str] = []
    sessions: list[str] = []
    for row in event_rows:
        event_id = row.get("id")
        event_type = _clean_text(row.get("eventtype") or row.get("event_type"))
        session = _clean_text(row.get("session"))
        if event_id is not None:
            event_ids.append(str(event_id))
        if event_type is not None:
            presentation_types.append(event_type)
        if session is not None:
            sessions.append(session)

    native_metadata: dict[str, str | list[str]] = {
        "openreview_venueid": venueid or "unknown",
        "openreview_note_id": note_id,
        "event_ids": sorted(set(event_ids)),
        "presentation_types": sorted(set(presentation_types)),
        "sessions": sorted(set(sessions)),
    }
    abstract = _clean_text(_content_value(content, "abstract"))
    pdf = _clean_text(_content_value(content, "pdf"))
    status = (
        RecordStatus.UNRESOLVED
        if malformed or venueid not in {_MAIN_VENUE_ID, *_KNOWN_NON_MAIN_VENUE_IDS}
        else RecordStatus.EXCLUDED
        if venueid in _KNOWN_NON_MAIN_VENUE_IDS
        else RecordStatus.COMPLETE
        if abstract is not None
        else RecordStatus.PARTIAL
    )
    return PaperRecord(
        paper_id=f"icml:{request.year}:{stable_id}",
        title=title or f"Unresolved OpenReview note {note_id}",
        normalized_title=normalize_title(title or f"unresolved {note_id}"),
        authors=authors,
        venue=request.venue,
        year=request.year,
        track=request.track or "main",
        landing_url=f"https://openreview.net/forum?id={stable_id}",
        source=source,
        status=status,
        abstract=abstract,
        keywords=_authors(_content_value(content, "keywords")),
        native_metadata=native_metadata,
        pdf_url=urljoin("https://openreview.net", pdf) if pdf else None,
    )


def parse_icml_sources(
    corpus: IcmlRawCorpus, request: VenueRequest
) -> IcmlParseResult:
    """Normalize an ICML corpus, using exact OpenReview venue identity."""
    event_rows_by_forum: dict[str, list[Mapping[str, object]]] = {}
    presentation_row_count = 0
    for page in corpus.event_pages:
        payload = _json_object(page)
        rows = payload.get("results")
        if not isinstance(rows, list):
            raise IcmlSourceFormatError("event page results must be a list")
        presentation_row_count += len(rows)
        for raw_row in rows:
            if not isinstance(raw_row, Mapping):
                raise IcmlSourceFormatError("event row must be an object")
            forum = _forum_id_from_url(raw_row.get("paper_url"))
            if forum is None:
                continue
            existing = event_rows_by_forum.setdefault(forum, [])
            title = _clean_text(raw_row.get("name"))
            authors = _event_authors(raw_row)
            if existing:
                prior_title = _clean_text(existing[0].get("name"))
                prior_authors = _event_authors(existing[0])
                if title != prior_title or authors != prior_authors:
                    raise IcmlSourceFormatError(
                        f"conflicting event identity for OpenReview forum {forum}"
                    )
            existing.append(raw_row)

    _json_object(corpus.abstracts)
    notes: list[tuple[Mapping[str, object], SourceRef]] = []
    for page in corpus.openreview_pages:
        payload = _json_object(page)
        raw_notes = payload.get("notes")
        if not isinstance(raw_notes, list):
            raise IcmlSourceFormatError("OpenReview notes must be a list")
        for note in raw_notes:
            if not isinstance(note, Mapping):
                raise IcmlSourceFormatError("OpenReview note must be an object")
            notes.append((note, page.source))

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for note, source in notes:
        forum = _clean_text(note.get("forum"))
        rows = tuple(event_rows_by_forum.get(forum or "", []))
        record = _record_from_note(note, request=request, source=source, event_rows=rows)
        if record.paper_id in seen_ids:
            raise IcmlSourceFormatError(f"duplicate OpenReview paper ID: {record.paper_id}")
        seen_ids.add(record.paper_id)
        records.append(record)

    noted_forums = {
        forum
        for note, _ in notes
        if (forum := _clean_text(note.get("forum"))) is not None
    }
    for forum, rows in event_rows_by_forum.items():
        if forum in noted_forums:
            continue
        venueid = _venue_id_from_event(rows[0])
        if venueid not in _KNOWN_NON_MAIN_VENUE_IDS:
            continue
        title = _clean_text(rows[0].get("name")) or f"Excluded ICML event {forum}"
        records.append(
            PaperRecord(
                paper_id=f"icml:{request.year}:{forum}",
                title=title,
                normalized_title=normalize_title(title),
                authors=_event_authors(rows[0]),
                venue=request.venue,
                year=request.year,
                track=request.track or "main",
                landing_url=f"https://openreview.net/forum?id={forum}",
                source=corpus.event_pages[0].source,
                status=RecordStatus.EXCLUDED,
                native_metadata={"openreview_venueid": venueid},
            )
        )

    included = tuple(
        sorted(
            (record for record in records if record.status in {RecordStatus.COMPLETE, RecordStatus.PARTIAL}),
            key=lambda record: record.paper_id,
        )
    )
    excluded = tuple(
        sorted(
            (record for record in records if record.status is RecordStatus.EXCLUDED),
            key=lambda record: record.paper_id,
        )
    )
    unresolved = tuple(
        sorted(
            (record for record in records if record.status is RecordStatus.UNRESOLVED),
            key=lambda record: record.paper_id,
        )
    )
    return IcmlParseResult(
        included=included,
        excluded=excluded,
        unresolved=unresolved,
        presentation_row_count=presentation_row_count,
    )
