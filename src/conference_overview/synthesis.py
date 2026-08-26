"""Evidence-labeled synthesis for audited single-year conference snapshots."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from conference_overview.classification import Assignment, ThemeAudit
from conference_overview.models import (
    AdvanceCategory,
    AdvanceRecord,
    EvidenceClaim,
    EvidenceType,
    PaperRecord,
)

_LANES: tuple[tuple[AdvanceCategory, tuple[str, ...], str, str], ...] = (
    (
        AdvanceCategory.TEXT_LLMS,
        ("Foundation Models", "NLP and CV Core Methods"),
        "基础模型如何改进表示、生成与适配？",
        "基础模型的能力提升需要同时处理表示方式、训练目标与适配效率。",
    ),
    (
        AdvanceCategory.MULTIMODAL_MODELS,
        ("Multimodal Models",),
        "多模态模型如何对齐不同模态并保持可控生成？",
        "多模态学习需要在对齐、组合推理和生成控制之间取得平衡。",
    ),
    (
        AdvanceCategory.REASONING_AGENTS,
        ("Reasoning and Agents",),
        "推理与 Agent 如何规划、调用工具并利用反馈？",
        "推理系统需要把规划、行动、反馈和停止条件组织为完整过程。",
    ),
    (
        AdvanceCategory.DATA_TRAINING,
        ("Data and Retrieval", "Learning and Optimization"),
        "数据、检索与优化方法如何共同提高学习效率？",
        "模型效果取决于数据组织、信息获取和优化过程的协同设计。",
    ),
    (
        AdvanceCategory.EVALUATION_TRUST,
        ("Evaluation", "Trustworthiness"),
        "评测与可信研究如何更准确地描述模型能力和风险？",
        "可靠评测需要同时关注测量有效性、不确定性、稳健性和安全边界。",
    ),
)


def build_single_year_advances(
    records: Sequence[PaperRecord],
    assignments: Sequence[Assignment],
    audits: Mapping[str, ThemeAudit],
) -> list[AdvanceRecord]:
    """Build five compact research lanes from audited single-year assignments."""
    records_by_id = {record.paper_id: record for record in records}
    advances: list[AdvanceRecord] = []
    for category, topics, question, problem in _LANES:
        candidates = sorted(
            (
                assignment
                for assignment in assignments
                if assignment.primary_topic in topics
                and assignment.primary_topic in audits
                and audits[assignment.primary_topic].sample_size > 0
            ),
            key=lambda item: (-item.confidence, item.paper_id),
        )[:3]
        if not candidates:
            continue
        papers = [records_by_id[item.paper_id] for item in candidates]
        urls = [paper.landing_url for paper in papers]
        titles = "、".join(paper.title for paper in papers)
        locator = "PMLR Volume 267 title and abstract for every linked paper"
        advances.append(
            AdvanceRecord(
                advance_id=f"icml-2025-{category.value}",
                title=f"ICML 2025 · {category.value.replace('_', ' ')}",
                category=category,
                supporting_paper_ids=tuple(item.paper_id for item in candidates),
                claims=(
                    EvidenceClaim(
                        claim=f"代表论文包括：{titles}。",
                        evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                        source_urls=urls,
                        locator=locator,
                    ),
                ),
                research_questions=(question,),
                core_problem=EvidenceClaim(
                    claim=problem,
                    evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                    source_urls=urls,
                    locator=locator,
                ),
                technical_change=EvidenceClaim(
                    claim="这些论文分别从方法结构、训练过程或评测方式提出改进。",
                    evidence_type=EvidenceType.PAPER_REPORTED,
                    source_urls=urls,
                    locator=locator,
                ),
                evidence_boundary=EvidenceClaim(
                    claim="这里概括的是不同论文在各自实验设置中的报告，不能合并为统一效果量。",
                    evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                    source_urls=urls,
                    locator=locator,
                ),
                implications=(
                    EvidenceClaim(
                        claim="后续研究可沿该问题框架比较方法、数据和评测设置。",
                        evidence_type=EvidenceType.INFERENCE,
                        source_urls=urls,
                        locator="Inference from the linked PMLR paper abstracts",
                    ),
                ),
            )
        )
    return advances
