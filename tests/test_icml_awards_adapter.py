from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from conference_overview.adapters.acl import normalize_title
from conference_overview.adapters.icml_awards import parse_icml_awards_html
from conference_overview.models import SourceRef

FIXTURE = Path(__file__).parent / "fixtures/icml/icml-2025-awards-small.html"


def official_source() -> SourceRef:
    return SourceRef(
        name="ICML 2025 Awards",
        url="https://icml.cc/virtual/2025/awards_detail",
        retrieved_at=datetime(2026, 8, 26, tzinfo=UTC),
        sha256="a" * 64,
    )


def test_icml_award_inventory_keeps_exact_current_paper_categories() -> None:
    badges = parse_icml_awards_html(FIXTURE.read_bytes(), official_source())

    assert Counter(item.award_type for item in badges) == {
        "Outstanding Paper": 6,
        "Outstanding Position Paper": 2,
    }
    assert len({normalize_title(item.title) for item in badges}) == 8
    assert {item.title for item in badges}.isdisjoint(
        {"Batch Normalization", "A Workshop Paper"}
    )


def test_icml_award_duplicate_rendering_keeps_one_stable_locator() -> None:
    badges = parse_icml_awards_html(FIXTURE.read_bytes(), official_source())
    collab = [item for item in badges if item.title.startswith("CollabLLM")]

    assert len(collab) == 1
    assert collab[0].event_url == "https://icml.cc/virtual/2025/oral/6"
    assert collab[0].evidence_locator == (
        "ICML 2025 Awards table; Outstanding Paper; /virtual/2025/oral/6"
    )
