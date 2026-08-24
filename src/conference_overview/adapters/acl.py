"""Parse ACL Anthology BibTeX volumes and their abstract enrichment HTML."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import bibtexparser

from conference_overview.models import (
    PaperRecord,
    RecordStatus,
    SourceRef,
    VenueRequest,
)

_ACL_ID_PATTERN = re.compile(r"\d{4}\.[a-z0-9-]+(?:\.\d+)?", re.IGNORECASE)


class AclSourceFormatError(ValueError):
    """Raised when an authoritative ACL source cannot be safely interpreted."""

    def __init__(self, *, source: SourceRef, detail: str) -> None:
        self.source = source
        self.detail = detail
        super().__init__(f"ACL source format error for {source.url}: {detail}")


def normalize_title(title: str) -> str:
    """Return a stable comparison key for a BibTeX title."""
    visible = title.replace("{", "").replace("}", "")
    return " ".join(visible.casefold().split())


def _display_title(title: str) -> str:
    return " ".join(title.replace("{", "").replace("}", "").split())


def _acl_id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.netloc and parsed.netloc.casefold() != "aclanthology.org":
        return None
    candidate = parsed.path.strip("/")
    if _ACL_ID_PATTERN.fullmatch(candidate):
        return candidate
    return None


def _paper_id(acl_id: str) -> str:
    if acl_id.rsplit(".", maxsplit=1)[-1].isdigit():
        return f"acl:{acl_id}"
    return f"acl:{acl_id}.0"


def _authors(author_field: str) -> list[str]:
    return [
        _display_title(author)
        for author in re.split(r"\s+and\s+", author_field, flags=re.IGNORECASE)
        if author.strip()
    ]


def _record_from_entry(entry: dict[str, str], request: VenueRequest, source: SourceRef) -> PaperRecord:
    landing_url = entry.get("url", "")
    acl_id = _acl_id_from_url(landing_url)
    if acl_id is None:
        raise AclSourceFormatError(
            source=source,
            detail=(
                f"{entry['ENTRYTYPE']} entry {entry.get('ID', '<unknown>')} "
                "has no canonical ACL landing URL"
            ),
        )

    title = _display_title(entry.get("title", ""))
    is_proceedings = entry["ENTRYTYPE"].casefold() == "proceedings"
    return PaperRecord(
        paper_id=_paper_id(acl_id),
        title=title,
        normalized_title=normalize_title(title),
        authors=_authors(entry.get("author", "")),
        venue=request.venue,
        year=request.year,
        track=request.track or "unknown",
        landing_url=landing_url,
        source=source,
        status=RecordStatus.EXCLUDED if is_proceedings else RecordStatus.COMPLETE,
        doi=entry.get("doi"),
        pdf_url=f"{landing_url.rstrip('/')}.pdf",
    )


def parse_acl_bibtex(
    data: bytes, request: VenueRequest, source: SourceRef
) -> tuple[list[PaperRecord], list[PaperRecord]]:
    """Parse ACL papers and retain proceedings front matter as exclusions."""
    bibliography = bibtexparser.loads(data.decode("utf-8"))
    included: list[PaperRecord] = []
    excluded: list[PaperRecord] = []

    for entry in bibliography.entries:
        entry_type = entry["ENTRYTYPE"].casefold()
        if entry_type not in {"inproceedings", "proceedings"}:
            continue
        record = _record_from_entry(entry, request, source)
        if entry_type == "inproceedings":
            included.append(record)
        else:
            excluded.append(record)

    return included, excluded


@dataclass
class _HtmlElement:
    tag: str
    is_paper_container: bool
    paper_id: str | None = None


def _is_paper_container(tag: str, classes: set[str], acl_id: str | None) -> bool:
    return (
        tag in {"article", "li"}
        or (tag in {"div", "section"} and "card" in classes)
        or acl_id is not None
    )


class _VolumeAbstractParser(HTMLParser):
    """Collect explicit ACL-ID/abstract pairs from a volume page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.abstracts: dict[str, str] = {}
        self._elements: list[_HtmlElement] = []
        self._active_abstract: tuple[str, int, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").casefold().split())
        link_paper_id = _acl_id_from_url(attributes.get("href") or "")
        container_paper_id = _acl_id_from_url(attributes.get("id") or "")
        element = _HtmlElement(
            tag=tag,
            is_paper_container=_is_paper_container(tag, classes, container_paper_id),
            paper_id=container_paper_id,
        )
        self._elements.append(element)

        if link_paper_id is not None:
            container = self._nearest_paper_container()
            if container is not None and container is not element:
                container.paper_id = link_paper_id

        if "abstract" in classes:
            container = self._nearest_paper_container()
            if container is not None and container.paper_id is not None:
                self._active_abstract = (container.paper_id, len(self._elements), [])

    def _nearest_paper_container(self) -> _HtmlElement | None:
        return next(
            (element for element in reversed(self._elements) if element.is_paper_container),
            None,
        )

    def handle_data(self, data: str) -> None:
        if self._active_abstract is not None:
            self._active_abstract[2].append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._elements:
            return
        self._elements.pop()
        if self._active_abstract is None or len(self._elements) >= self._active_abstract[1]:
            return
        paper_id, _, parts = self._active_abstract
        abstract = " ".join("".join(parts).split())
        if abstract:
            self.abstracts[paper_id] = abstract
        self._active_abstract = None


def enrich_acl_abstracts(
    records: list[PaperRecord], html: bytes, source: SourceRef
) -> list[PaperRecord]:
    """Add HTML abstracts only when their canonical ACL IDs exactly match.

    Each record deliberately retains its BibTeX ``source``. The caller must retain
    ``source`` independently in release provenance so BibTeX and HTML hashes stay
    distinguishable instead of creating a synthetic combined source on a record.
    """
    parser = _VolumeAbstractParser()
    parser.feed(html.decode("utf-8"))
    parser.close()
    if html.strip() and not parser.abstracts:
        raise AclSourceFormatError(
            source=source,
            detail="nonempty HTML yielded zero trusted ACL ID/abstract pairs",
        )

    enriched: list[PaperRecord] = []
    for record in records:
        acl_id = record.paper_id.removeprefix("acl:")
        abstract = parser.abstracts.get(acl_id)
        enriched.append(record.model_copy(update={"abstract": abstract}) if abstract else record)
    return enriched
