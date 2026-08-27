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
        ("Foundation Models", "NLP/CV Core Tasks"),
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

_ICML_2025_CURATED: dict[AdvanceCategory, dict[str, object]] = {
    AdvanceCategory.TEXT_LLMS: {
        "title": "文本模型：从逐词预测走向灵活生成与长期协作",
        "paper_ids": ("pmlr:v267:kim25ah", "pmlr:v267:nagarajan25a", "pmlr:v267:wu25i"),
        "question": "文本模型如何摆脱固定 token 顺序、短视预测和被动应答？",
        "problem": "next-token prediction 便于扩展，但固定生成顺序、局部奖励与被动交互会限制开放式推理和长期协作。",
        "technical": "三项工作分别分析 masked diffusion 的任意 token 顺序、用可控任务测量 next-token prediction 的创造性边界，并以长期交互模拟训练 CollabLLM 主动澄清和协作。",
        "implication": "文本模型评测应把生成顺序、探索能力和多轮任务完成度拆开测量，而不只看单轮答案得分。",
    },
    AdvanceCategory.MULTIMODAL_MODELS: {
        "title": "多模态模型：统一模态接口并加强过程推理",
        "paper_ids": ("pmlr:v267:jain25b", "pmlr:v267:sun25x", "pmlr:v267:wang25av"),
        "question": "多模态模型如何连接空间、时间与语言，同时保留可解释的推理过程？",
        "problem": "2D/3D、音视频和时间序列具有不同结构，简单拼接模态难以同时完成对齐、推理和迁移。",
        "technical": "UniVLG 用共享 language-conditioned decoder 连接 2D 与 3D grounding；video-SALMONN-o1 引入音视频逐步推理数据和 process DPO；ITFormer 以轻量接口连接时间序列编码器与冻结 LLM。",
        "implication": "多模态训练应显式记录模态接口、对齐目标和推理监督，避免把性能提升笼统归因于模型规模。",
    },
    AdvanceCategory.REASONING_AGENTS: {
        "title": "推理与 Agent：拆分协作、工具调用与规划能力",
        "paper_ids": ("pmlr:v267:wu25i", "pmlr:v267:patil25a", "pmlr:v267:zhou25t"),
        "question": "Agent 如何从会调用工具，进一步发展为能协作、规划并根据环境反馈调整行为？",
        "problem": "Agent 的最终成功率混合了意图澄清、function calling、状态建模和长程规划，难以定位真实能力边界。",
        "technical": "CollabLLM 优化长期人机协作；BFCL 用可扩展的 AST 方法评测串行和并行 function calling；DINO-WM 在预训练视觉特征上预测未来状态并进行 zero-shot planning。",
        "implication": "Agent 基准应分别报告协作质量、工具调用正确性、世界模型误差和规划成功率。",
    },
    AdvanceCategory.DATA_TRAINING: {
        "title": "数据与训练：把缺失机制、数据配比和技能结构纳入优化",
        "paper_ids": ("pmlr:v267:givens25a", "pmlr:v267:xie25i", "pmlr:v267:li25dp"),
        "question": "缺失数据、动态数据混合和领域技能结构应如何进入训练目标？",
        "problem": "训练数据不仅有质量差异，还存在缺失、领域结构和新增数据带来的混合权重变化。",
        "technical": "missing data score matching 将 score matching 扩展到任意坐标缺失；Chameleon 用 domain embedding 的 leverage score 计算可迁移的数据配比；MASS 用数学 skill graph 选择预训练数据。",
        "implication": "数据策略实验应同时记录缺失机制、domain mixture 和技能覆盖，而不是只比较过滤后的 token 数量。",
    },
    AdvanceCategory.EVALUATION_TRUST: {
        "title": "评测与可信：从平均表现转向群体、不确定性与社会影响",
        "paper_ids": (
            "pmlr:v267:fischer-abaigar25a",
            "pmlr:v267:snell25a",
            "pmlr:v267:hazra25a",
        ),
        "question": "高风险决策中，模型评测如何同时覆盖最弱势群体、不确定性和社会影响？",
        "problem": "平均指标可能掩盖 worst-off 群体，传统不确定性方法有适用范围，AI safety 也容易忽略劳动转型等现实影响。",
        "technical": "相关工作分别比较 prediction 对识别 worst-off 的实际价值、把 conformal prediction 重新表述为 Bayesian quadrature，并主张将 future of work 纳入 AI safety 的核心范围。",
        "implication": "可信评测需要把平均效果、群体分布、不确定性覆盖率和部署后的社会影响分开报告。",
    },
}


def build_single_year_advances(
    records: Sequence[PaperRecord],
    assignments: Sequence[Assignment],
    audits: Mapping[str, ThemeAudit],
) -> list[AdvanceRecord]:
    """Build five compact research lanes from audited single-year assignments."""
    records_by_id = {record.paper_id: record for record in records}
    advances: list[AdvanceRecord] = []
    for category, topics, question, problem in _LANES:
        fallback_candidates = sorted(
            (
                assignment
                for assignment in assignments
                if assignment.primary_topic in topics
                and assignment.primary_topic in audits
                and audits[assignment.primary_topic].sample_size > 0
            ),
            key=lambda item: (-item.confidence, item.paper_id),
        )[:3]
        curated = _ICML_2025_CURATED[category]
        assignments_by_id = {item.paper_id: item for item in assignments}
        curated_ids = tuple(str(item) for item in curated["paper_ids"])
        candidates = [
            assignments_by_id[paper_id]
            for paper_id in curated_ids
            if paper_id in assignments_by_id
        ]
        if len(candidates) != len(curated_ids):
            candidates = fallback_candidates
        if not candidates:
            continue
        papers = [records_by_id[item.paper_id] for item in candidates]
        urls = [paper.landing_url for paper in papers]
        titles = "、".join(paper.title for paper in papers)
        uses_curated = tuple(item.paper_id for item in candidates) == curated_ids
        locator = "PMLR Volume 267 title and abstract for every linked paper"
        advances.append(
            AdvanceRecord(
                advance_id=f"icml-2025-{category.value}",
                title=str(curated["title"]),
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
                research_questions=(
                    str(curated["question"]) if uses_curated else question,
                ),
                core_problem=EvidenceClaim(
                    claim=str(curated["problem"]) if uses_curated else problem,
                    evidence_type=EvidenceType.CROSS_PAPER_SYNTHESIS,
                    source_urls=urls,
                    locator=locator,
                ),
                technical_change=EvidenceClaim(
                    claim=(
                        str(curated["technical"])
                        if uses_curated
                        else "这些论文分别从方法结构、训练过程或评测方式提出改进。"
                    ),
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
                        claim=(
                            str(curated["implication"])
                            if uses_curated
                            else "后续研究可沿该问题框架比较方法、数据和评测设置。"
                        ),
                        evidence_type=EvidenceType.INFERENCE,
                        source_urls=urls,
                        locator="Inference from the linked PMLR paper abstracts",
                    ),
                ),
            )
        )
    return advances
