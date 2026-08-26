"""Read-only PMLR availability and deterministic reconciliation helpers."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from html import unescape

import httpx

from conference_overview.adapters.acl import normalize_title
from conference_overview.fetch import (
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
    SourceFetchError,
)
from conference_overview.models import (
    PaperRecord,
    RecordStatus,
    SourceRef,
    VenueRequest,
)


class FinalSourceStatus(str, Enum):
    NOT_PUBLISHED = "not_published"
    AVAILABLE = "available"


@dataclass(frozen=True)
class FetchedPmlrSource:
    status: FinalSourceStatus
    data: bytes | None = None
    source: SourceRef | None = None


class PmlrReconciliationError(ValueError):
    """Raised when preliminary and final identities cannot be matched safely."""


@dataclass(frozen=True)
class PmlrFieldDifference:
    preliminary_id: str
    final_id: str
    fields: tuple[str, ...]


@dataclass(frozen=True)
class PmlrDiffReport:
    preliminary_count: int
    final_count: int
    matched_count: int
    only_preliminary_ids: tuple[str, ...]
    only_final_ids: tuple[str, ...]
    field_differences: tuple[PmlrFieldDifference, ...]
    unresolved_pairs: tuple[tuple[str, str], ...] = ()


def _html_text(fragment: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def parse_pmlr_volume(
    data: bytes, request: VenueRequest, source: SourceRef
) -> tuple[PaperRecord, ...]:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PmlrReconciliationError("PMLR volume is not UTF-8") from exc
    if 'data-pmlr-volume="306"' not in text:
        raise PmlrReconciliationError("PMLR page is not Volume 306")
    records: list[PaperRecord] = []
    for match in re.finditer(
        r'<article class="paper" data-pmlr-id="(?P<id>[^"]+)">(?P<body>.*?)</article>',
        text,
        re.DOTALL,
    ):
        body = match.group("body")

        def field(pattern: str, fragment: str = body) -> str | None:
            found = re.search(pattern, fragment, re.DOTALL)
            return _html_text(found.group(1)) if found else None

        title = field(r'<h2 class="title">(.*?)</h2>')
        authors = field(r'<p class="authors">(.*?)</p>')
        landing = field(r'<a class="abstract" href="([^"]+)">')
        pdf = field(r'<a class="pdf" href="([^"]+)">')
        abstract = field(r'<p class="abstract-text">(.*?)</p>')
        doi = field(r'<span class="doi">(.*?)</span>')
        raw_id = match.group("id")
        if title is None or landing is None or not raw_id.startswith("v306-"):
            raise PmlrReconciliationError("PMLR paper entry is incomplete")
        records.append(
            PaperRecord(
                paper_id=f"pmlr:v306:{raw_id.removeprefix('v306-')}",
                title=title,
                normalized_title=normalize_title(title),
                authors=[item.strip() for item in (authors or "").split(",") if item.strip()],
                venue=request.venue,
                year=request.year,
                track=request.track or "main",
                landing_url=landing,
                source=source,
                status=RecordStatus.COMPLETE if abstract else RecordStatus.PARTIAL,
                abstract=abstract,
                doi=doi,
                pdf_url=pdf,
            )
        )
    if not records:
        raise PmlrReconciliationError("PMLR volume contains no recognizable papers")
    return tuple(sorted(records, key=lambda record: record.paper_id))


def fetch_final_source(
    request: VenueRequest, client: httpx.Client
) -> FetchedPmlrSource:
    if request.final_source_url is None:
        raise PmlrReconciliationError("request has no configured final source")
    url = str(request.final_source_url)
    try:
        response = client.get(
            url,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.TransportError as exc:
        raise SourceFetchError(url=url, detail="transport error") from exc
    if response.status_code == 404:
        return FetchedPmlrSource(FinalSourceStatus.NOT_PUBLISHED)
    if response.status_code != 200:
        raise SourceFetchError(url=url, status_code=response.status_code)
    text = response.text.casefold()
    if "volume 306" not in text or (
        "43rd international conference on machine learning" not in text
        and "43rd icml" not in text
    ):
        raise PmlrReconciliationError(
            "PMLR page does not identify Volume 306 and the 43rd ICML"
        )
    data = response.content
    return FetchedPmlrSource(
        FinalSourceStatus.AVAILABLE,
        data=data,
        source=SourceRef(
            name="PMLR Volume 306",
            url=url,
            retrieved_at=datetime.now(UTC),
            sha256=hashlib.sha256(data).hexdigest(),
        ),
    )


def check_final_source(
    request: VenueRequest, client: httpx.Client
) -> FinalSourceStatus:
    return fetch_final_source(request, client).status


def _match_key(record: PaperRecord) -> tuple[str, str] | None:
    forum = record.native_metadata.get("openreview_forum_id")
    if isinstance(forum, str) and forum.strip():
        return ("openreview", forum.strip())
    if record.doi is not None and record.doi.strip():
        return ("doi", record.doi.strip().casefold())
    return None


def reconcile_pmlr_records(
    preliminary: Sequence[PaperRecord], final: Sequence[PaperRecord]
) -> PmlrDiffReport:
    preliminary_by_key = {
        key: record for record in preliminary if (key := _match_key(record)) is not None
    }
    final_by_key = {
        key: record for record in final if (key := _match_key(record)) is not None
    }
    matches: dict[str, PaperRecord] = {}
    matched_final_ids: set[str] = set()
    for key, record in preliminary_by_key.items():
        candidate = final_by_key.get(key)
        if candidate is not None:
            matches[record.paper_id] = candidate
            matched_final_ids.add(candidate.paper_id)

    remaining_preliminary = [
        record for record in preliminary if record.paper_id not in matches
    ]
    remaining_final = [
        record for record in final if record.paper_id not in matched_final_ids
    ]
    preliminary_titles: dict[str, list[PaperRecord]] = defaultdict(list)
    final_titles: dict[str, list[PaperRecord]] = defaultdict(list)
    for record in remaining_preliminary:
        preliminary_titles[record.normalized_title].append(record)
    for record in remaining_final:
        final_titles[record.normalized_title].append(record)
    for title in sorted(set(preliminary_titles) & set(final_titles)):
        left = preliminary_titles[title]
        right = final_titles[title]
        if len(left) != 1 or len(right) != 1:
            raise PmlrReconciliationError(
                f"ambiguous normalized-title fallback: {title}"
            )
        matches[left[0].paper_id] = right[0]
        matched_final_ids.add(right[0].paper_id)

    differences: list[PmlrFieldDifference] = []
    preliminary_by_id = {record.paper_id: record for record in preliminary}
    for preliminary_id, final_record in sorted(matches.items()):
        preliminary_record = preliminary_by_id[preliminary_id]
        fields = tuple(
            field
            for field in ("abstract", "doi", "pdf_url")
            if getattr(preliminary_record, field) != getattr(final_record, field)
        )
        if fields:
            differences.append(
                PmlrFieldDifference(preliminary_id, final_record.paper_id, fields)
            )
    return PmlrDiffReport(
        preliminary_count=len(preliminary),
        final_count=len(final),
        matched_count=len(matches),
        only_preliminary_ids=tuple(
            sorted(record.paper_id for record in preliminary if record.paper_id not in matches)
        ),
        only_final_ids=tuple(
            sorted(record.paper_id for record in final if record.paper_id not in matched_final_ids)
        ),
        field_differences=tuple(differences),
    )
