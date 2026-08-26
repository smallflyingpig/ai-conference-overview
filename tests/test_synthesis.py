from datetime import UTC, datetime
from decimal import Decimal

from conference_overview.classification import Assignment, audit_theme
from conference_overview.models import PaperRecord, RecordStatus, SourceRef
from conference_overview.synthesis import build_single_year_advances


def _paper(index: int, topic: str) -> PaperRecord:
    slug = topic.lower().replace(" ", "-")
    return PaperRecord(
        paper_id=f"pmlr:v267:{slug}{index}25a",
        title=f"A contribution to {topic}",
        normalized_title=f"a contribution to {topic.lower()}",
        authors=["A. Author"],
        venue="ICML",
        year=2025,
        track="main",
        landing_url=f"https://proceedings.mlr.press/v267/{slug}{index}25a.html",
        source=SourceRef(
            name="PMLR Volume 267 metadata",
            url="https://proceedings.mlr.press/v267/assets/bib/citeproc.yaml",
            retrieved_at=datetime(2026, 8, 26, tzinfo=UTC),
            sha256="a" * 64,
        ),
        status=RecordStatus.COMPLETE,
        abstract=f"This paper studies {topic}.",
        pdf_url=f"https://proceedings.mlr.press/v267/{slug}{index}25a.pdf",
    )


def test_single_year_advances_cover_five_lanes_without_trend_language() -> None:
    topics = [
        "Foundation Models",
        "Multimodal Models",
        "Reasoning and Agents",
        "Learning and Optimization",
        "Evaluation",
    ]
    records = [_paper(index, topic) for index, topic in enumerate(topics)]
    assignments = [
        Assignment(
            paper_id=record.paper_id,
            primary_topic=topic,
            secondary_topics=(),
            confidence=Decimal("0.95"),
            rationale=f"The abstract directly studies {topic}.",
            taxonomy_version="2026-08-24-v1",
        )
        for record, topic in zip(records, topics, strict=True)
    ]
    audits = {topic: audit_theme([True] * 50) for topic in topics}

    advances = build_single_year_advances(records, assignments, audits)

    assert len(advances) == 5
    assert len({item.category for item in advances}) == 5
    assert all(item.supporting_paper_ids for item in advances)
    rendered = " ".join(
        claim.claim
        for advance in advances
        for claim in (
            *advance.claims,
            advance.core_problem,
            advance.technical_change,
            advance.evidence_boundary,
            *advance.implications,
        )
        if claim is not None
    )
    assert "同比" not in rendered
    assert "增长" not in rendered
    assert "趋势" not in rendered
    assert all(
        str(url).startswith("https://proceedings.mlr.press/v267/")
        for advance in advances
        for claim in advance.claims
        for url in claim.source_urls
    )


def test_text_lane_uses_the_configured_core_task_taxonomy_name() -> None:
    topics = [
        "NLP/CV Core Tasks",
        "Multimodal Models",
        "Reasoning and Agents",
        "Learning and Optimization",
        "Evaluation",
    ]
    records = [_paper(index, topic) for index, topic in enumerate(topics)]
    assignments = [
        Assignment(
            paper_id=record.paper_id,
            primary_topic=topic,
            secondary_topics=(),
            confidence=Decimal("0.95"),
            rationale=f"The abstract directly studies {topic}.",
            taxonomy_version="2026-08-24-v1",
        )
        for record, topic in zip(records, topics, strict=True)
    ]

    advances = build_single_year_advances(
        records,
        assignments,
        {topic: audit_theme([True] * 50) for topic in topics},
    )

    assert len(advances) == 5
    assert records[0].paper_id in advances[0].supporting_paper_ids
