"""Strict parser for the official ICML current-paper awards table."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

from conference_overview.adapters.acl import normalize_title
from conference_overview.models import SourceRef

_CURRENT_PAPER_AWARDS = {
    "Outstanding Paper",
    "Outstanding Position Paper",
}


@dataclass(frozen=True)
class IcmlAwardBadge:
    title: str
    award_type: str
    event_url: str
    evidence_locator: str
    source: SourceRef


class _AwardsTableParser(HTMLParser):
    def __init__(self, source: SourceRef) -> None:
        super().__init__(convert_charrefs=True)
        self.source = source
        self.in_row = False
        self.cell_index = -1
        self.award_text: list[str] = []
        self.capture_title = False
        self.title_text: list[str] = []
        self.title_href: str | None = None
        self.rows: list[tuple[str, str, str]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        if tag == "tr":
            self.in_row = True
            self.cell_index = -1
            self.award_text = []
            self.title_text = []
            self.title_href = None
        elif self.in_row and tag == "td":
            self.cell_index += 1
        elif self.in_row and self.cell_index >= 1 and tag == "a":
            classes = set((attributes.get("class") or "").split())
            href = attributes.get("href")
            if "small-title" in classes and isinstance(href, str):
                self.capture_title = True
                self.title_href = href

    def handle_data(self, data: str) -> None:
        if not self.in_row:
            return
        if self.cell_index == 0:
            self.award_text.append(data)
        if self.capture_title:
            self.title_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.capture_title:
            self.capture_title = False
        elif tag == "tr" and self.in_row:
            award_type = " ".join("".join(self.award_text).split())
            title = " ".join("".join(self.title_text).split())
            if title and self.title_href:
                self.rows.append((award_type, title, self.title_href))
            self.in_row = False


def parse_icml_awards_html(
    data: bytes, source: SourceRef
) -> tuple[IcmlAwardBadge, ...]:
    """Return unique current-paper awards; exclude historical and workshop rows."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("ICML awards page is not UTF-8") from exc
    parser = _AwardsTableParser(source)
    parser.feed(text)
    unique: dict[tuple[str, str], IcmlAwardBadge] = {}
    for award_type, title, href in parser.rows:
        if award_type not in _CURRENT_PAPER_AWARDS:
            continue
        identity = (normalize_title(title), award_type)
        event_url = urljoin(str(source.url), href)
        unique.setdefault(
            identity,
            IcmlAwardBadge(
                title=title,
                award_type=award_type,
                event_url=event_url,
                evidence_locator=(
                    f"ICML 2025 Awards table; {award_type}; {href}"
                ),
                source=source,
            ),
        )
    if not unique:
        raise ValueError("ICML awards page contains no current-paper awards")
    return tuple(
        sorted(unique.values(), key=lambda item: (item.award_type, item.title))
    )
