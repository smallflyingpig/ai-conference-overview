from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from conference_overview.chinese_content import (
    AwardDeepReadZh,
    AwardQuickReadZh,
    ContentPublicationBlocked,
    PaperSummaryZh,
    paper_route_key,
    validate_chinese_content_bundle,
    validate_summary_sources,
)
from conference_overview.models import PaperRecord, RecordStatus, SourceRef

_ABSTRACT_SHA256 = "01c8e4f38e1b92444f0f93f96a27a950e4cc0eb3d414aee7072afae974a693f6"
_LONG_SUMMARY = (
    "这项研究围绕语言模型的稳定学习展开，先分析现有方法在复杂输入下容易出现的偏差，"
    "再提出结合结构信息与动态选择机制的新方法。实验覆盖多个公开任务，并与常用基线进行比较。"
    "结果显示，该方法在主要设置下表现更稳定，同时减少了无效计算。作者也指出，当前实验集中在"
    "有限的数据和模型规模上，能否推广到其他语言与更大系统仍需继续研究。论文没有进一步报告真实部署环境中的表现。"
)


def paper(paper_id: str, *, title: str | None = None) -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        title=title or f"Paper {paper_id}",
        normalized_title=(title or f"Paper {paper_id}").casefold(),
        authors=["A. Author"],
        venue="ACL",
        year=2026,
        track="long",
        landing_url="https://aclanthology.org/2026.acl-long.1/",
        source=SourceRef(
            name="ACL Anthology",
            url="https://aclanthology.org/volumes/2026.acl-long/",
            retrieved_at=datetime(2026, 8, 24, tzinfo=UTC),
            sha256="a" * 64,
        ),
        status=RecordStatus.COMPLETE,
        abstract="Official abstract without numbers.",
        pdf_url="https://aclanthology.org/2026.acl-long.1.pdf",
    )


def paper_summary(
    paper_id: str = "acl:2026.acl-long.1", **updates: object
) -> PaperSummaryZh:
    values: dict[str, object] = {
        "schema_version": "paper-summary-zh-v1",
        "paper_id": paper_id,
        "route_key": paper_route_key(paper_id),
        "venue": "ACL",
        "year": 2026,
        "track": "long",
        "source_title": f"Paper {paper_id}",
        "source_abstract_sha256": _ABSTRACT_SHA256,
        "one_sentence": "论文提出一种更稳定的语言模型学习方法。",
        "summary_zh": _LONG_SUMMARY,
        "research_problem": "现有方法在复杂输入下容易出现不稳定表现。",
        "core_method": "方法结合结构信息与动态选择机制。",
        "main_findings": "论文报告该方法在多个公开任务上表现更稳定。",
        "scope_and_limitations": "实验范围限于论文使用的数据和模型规模。",
        "content_method": "title-abstract-grounded-summary-v1",
    }
    values.update(updates)
    return PaperSummaryZh.model_validate(values)


def award_deep_read(paper_id: str = "acl:2026.acl-long.2") -> AwardDeepReadZh:
    return AwardDeepReadZh(
        schema_version="award-deep-read-zh-v1",
        paper_id=paper_id,
        source_pdf_sha256="c" * 64,
        quick_read=AwardQuickReadZh(
            research_problem="论文研究模型在复杂任务中的稳定表现。",
            core_method="作者提出分阶段分析与动态调整方法。",
            main_finding="实验显示该方法改善了主要任务表现。",
        ),
        abstract_zh="论文系统研究模型在复杂任务中的稳定性，并提出分阶段分析方法。",
        background=("现有方法难以区分不同错误来源。",),
        method_walkthrough=("先分析输入，再动态选择处理步骤。",),
        why_it_matters=("这项工作提供了更细致的分析方法。",),
        limitations=("实验只覆盖论文报告的数据范围。",),
        research_implications=("后续研究可以继续检查不同任务中的稳定性。",),
    )


def test_paper_summary_requires_150_to_250_chinese_characters() -> None:
    with pytest.raises(ValidationError, match="150 to 250"):
        paper_summary(summary_zh="太短")


def test_paper_route_key_is_full_sha256_of_utf8_paper_id() -> None:
    assert paper_route_key("acl:2026.acl-long.1") == (
        "paper-e7c91a8a0e0c06e1505eec4b2ab799d5e8160f31070f733ed9754d40313bf253"
    )


def test_abstract_grounded_summary_requires_only_abstract_hash() -> None:
    with pytest.raises(ValidationError, match="exactly one source binding"):
        paper_summary(source_pdf_sha256="d" * 64)


def test_pdf_grounded_summary_requires_only_pdf_hash() -> None:
    summary = paper_summary(
        source_abstract_sha256=None,
        source_pdf_sha256="d" * 64,
        content_method="official-pdf-grounded-summary-v1",
    )

    assert summary.source_pdf_sha256 == "d" * 64


def test_numeric_chinese_claim_requires_source_token() -> None:
    summary = paper_summary(
        main_findings="论文报告准确率达到百分之九十九点九。",
    )
    forged = summary.model_copy(
        update={"main_findings": "论文报告准确率达到 99.9%。"}
    )

    with pytest.raises(ContentPublicationBlocked, match="numeric token"):
        validate_summary_sources(forged, "The method improves accuracy.")


def test_numeric_source_check_accepts_equivalent_percent_suffix() -> None:
    summary = paper_summary().model_copy(
        update={"main_findings": "论文报告准确率达到 46.83%。"}
    )

    validate_summary_sources(summary, "Exact match value: 46.83")


def test_bundle_requires_exact_partition_of_all_paper_ids() -> None:
    papers = [
        paper("acl:2026.acl-long.1"),
        paper("acl:2026.acl-long.2"),
    ]

    with pytest.raises(ContentPublicationBlocked, match="paper ID coverage"):
        validate_chinese_content_bundle(
            papers=papers,
            award_ids={"acl:2026.acl-long.2"},
            summaries=[paper_summary()],
            award_deep_reads=[],
            release_generation="generations/" + "a" * 64,
            papers_sha256="b" * 64,
            award_pdf_sha256={"acl:2026.acl-long.2": "c" * 64},
            award_source_text={"acl:2026.acl-long.2": "Official paper text."},
        )


def test_bundle_reparses_model_copy_bypasses_before_publication() -> None:
    invalid = paper_summary().model_copy(update={"summary_zh": "太短"})

    with pytest.raises(ContentPublicationBlocked, match="invalid Chinese content"):
        validate_chinese_content_bundle(
            papers=[paper("acl:2026.acl-long.1")],
            award_ids=set(),
            summaries=[invalid],
            award_deep_reads=[],
            release_generation="generations/" + "a" * 64,
            papers_sha256="b" * 64,
            award_pdf_sha256={},
            award_source_text={},
        )


def test_bundle_accepts_exact_ordinary_and_award_partition() -> None:
    papers = [
        paper("acl:2026.acl-long.1"),
        paper("acl:2026.acl-long.2"),
    ]

    bundle = validate_chinese_content_bundle(
        papers=papers,
        award_ids={"acl:2026.acl-long.2"},
        summaries=[paper_summary()],
        award_deep_reads=[award_deep_read()],
        release_generation="generations/" + "a" * 64,
        papers_sha256="b" * 64,
        award_pdf_sha256={"acl:2026.acl-long.2": "c" * 64},
        award_source_text={"acl:2026.acl-long.2": "Official paper text."},
    )

    assert bundle.ordinary_count == 1
    assert bundle.award_count == 1
    assert bundle.total_count == 2
