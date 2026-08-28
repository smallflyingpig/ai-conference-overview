from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from conference_overview.classification import Assignment, audit_theme
from conference_overview.models import PaperRecord, RecordStatus, SourceRef
from conference_overview.synthesis import (
    build_single_year_advances,
    load_curated_advances,
)


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


def test_icml_curated_advances_explain_concrete_technical_changes() -> None:
    curated = [
        ("kim25ah", "Foundation Models"),
        ("nagarajan25a", "Foundation Models"),
        ("wu25i", "Reasoning and Agents"),
        ("jain25b", "Multimodal Models"),
        ("sun25x", "Multimodal Models"),
        ("wang25av", "Multimodal Models"),
        ("patil25a", "Evaluation"),
        ("zhou25t", "Reasoning and Agents"),
        ("givens25a", "Learning and Optimization"),
        ("xie25i", "Foundation Models"),
        ("li25dp", "Data and Retrieval"),
        ("fischer-abaigar25a", "Applications"),
        ("snell25a", "Trustworthiness"),
        ("hazra25a", "Trustworthiness"),
    ]
    records = []
    for index, (suffix, topic) in enumerate(curated):
        record = _paper(index, topic).model_copy(
            update={
                "paper_id": f"pmlr:v267:{suffix}",
                "title": suffix,
                "normalized_title": suffix,
                "landing_url": f"https://proceedings.mlr.press/v267/{suffix}.html",
                "pdf_url": f"https://proceedings.mlr.press/v267/{suffix}.pdf",
            }
        )
        records.append(record)
    source = Path("data/analysis/icml/2025-main/advances.zh.yaml")
    advances = load_curated_advances(
        source,
        records,
        papers_sha256="799c627fff018b6832a705be6ce932e637ffa42336dfd6a7cf1988b84261703d",
        assignments_sha256="4fb2df6a6aef991133f4686b1381ab6c517e8e2dcf6da40ec153edab288ab117",
        scope_key="icml-2025-main",
    )
    rendered = " ".join(item.core_problem.claim for item in advances)

    assert len(advances) == 5
    assert "masked diffusion" in rendered
    assert "2D 与 3D" in rendered
    assert "function calling" in rendered
    assert "missing data" in rendered
    assert "worst-off" in rendered


def test_curated_advances_are_hash_bound_and_reject_cross_scope_papers(
    tmp_path: Path,
) -> None:
    topics = [
        "Foundation Models",
        "Multimodal Models",
        "Reasoning and Agents",
        "Learning and Optimization",
        "Evaluation",
    ]
    records = [_paper(index, topic) for index, topic in enumerate(topics)]
    lane_ids = [
        "text_llms", "multimodal_models", "reasoning_agents",
        "data_training", "evaluation_trust",
    ]
    payload = {
        "schema_version": "curated-advances-v1",
        "papers_sha256": "a" * 64,
        "assignments_sha256": "b" * 64,
        "lanes": [
            {
                "lane_id": lane_id,
                "title_zh": f"研究方向 {index}",
                "question_zh": "这个方向解决什么问题？",
                "summary_zh": "论文提出了可核对的方法变化。",
                "evidence_boundary_zh": "只概括各论文自行报告的实验。",
                "implications_zh": "后续可以在统一设置下继续比较。",
                "representative_paper_ids": [records[index].paper_id],
            }
            for index, lane_id in enumerate(lane_ids)
        ],
    }
    source = tmp_path / "advances.zh.yaml"
    source.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")

    advances = load_curated_advances(
        source,
        records,
        papers_sha256="a" * 64,
        assignments_sha256=payload["assignments_sha256"],
        scope_key="acl-2026-findings",
    )
    assert len(advances) == 5

    payload["lanes"][0]["representative_paper_ids"] = ["acl:2026.acl-long.1"]
    source.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match="current conference scope"):
        load_curated_advances(
            source,
            records,
            papers_sha256="a" * 64,
            assignments_sha256=payload["assignments_sha256"],
            scope_key="acl-2026-findings",
        )
