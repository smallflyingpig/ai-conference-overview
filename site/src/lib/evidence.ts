import type { LoadedOverview } from "./data";
import {
  deepReadArtifactSchema,
  type DeepReadArtifact,
  type FullRelease,
  type MethodDiagramArtifact,
} from "./schema";

export const evidenceTypes = [
  "official_metadata",
  "paper_reported",
  "cross_paper_synthesis",
  "inference",
] as const;
export type EvidenceType = (typeof evidenceTypes)[number];

const evidenceLabels: Record<EvidenceType, string> = {
  official_metadata: "官方元数据",
  paper_reported: "论文报告（paper-reported）",
  cross_paper_synthesis: "跨论文综合",
  inference: "推断",
};

export function evidenceLabel(type: EvidenceType): string {
  return evidenceLabels[type];
}

export function evidenceTone(type: EvidenceType): string {
  return {
    official_metadata: "official",
    paper_reported: "reported",
    cross_paper_synthesis: "synthesis",
    inference: "inference",
  }[type];
}

export const deepReadSchema = deepReadArtifactSchema;
export type DeepRead = DeepReadArtifact;
export type MethodDiagram = MethodDiagramArtifact;
export type ResultClaim = DeepRead["result_claims"][number];

export function validateDeepRead(input: unknown): DeepRead {
  return deepReadSchema.parse(input);
}

type Paper = FullRelease["papers"][number];
type Award = FullRelease["overview"]["awards"][number];

export interface AwardDetailView {
  award: Award;
  paper: Paper;
  deepRead: DeepRead;
}

export interface AwardRoute {
  params: { paperId: string };
  props: { detail: AwardDetailView };
}

export function awardRouteKey(award: Award): string {
  return award.route_key;
}

export function awardTypeLabel(awardType: string): string {
  return {
    "Best Paper": "最佳论文",
    "Best Resource Paper": "最佳资源论文",
    "Best Social Impact Paper": "最佳社会影响论文",
    "Best Theme Paper": "最佳主题论文",
    "Outstanding Paper": "杰出论文",
  }[awardType] ?? awardType;
}

export function awardStatusLabel(status: string): string {
  return { verified: "官方已验证", not_verified: "尚未验证", not_announced: "尚未公布" }[status] ?? status;
}

const awardInsights: Record<string, string> = {
  "acl:2026.acl-long.1301": "ImplicitMemBench 将 learning/priming、interference 与首次作答分开；17 个模型整体均未超过 66%，说明显式检索成功不能替代行为适应证据。",
  "acl:2026.acl-long.1654": "Audio MultiChallenge 保留真人语音中的回溯、停顿、环境与副语言线索；452 段录音、1,712 条 atomic rubric 下，最强系统 APR 为 54.65%。",
  "acl:2026.acl-long.1948": "VeriTaS 通过季度更新、claim date 与 temporal retrieval filter 抑制持续预训练泄漏；知识截止日后的纵向退化表明时间必须进入 benchmark contract。",
  "acl:2026.acl-long.937": "HSCodeComp 在 632 个商品的层级规则任务上，最佳 agent 的 10-digit exact match 为 46.83%；增加 expert-written Decision Rules 并未带来更好结果，提示更多推理材料也可能引入 drift。",
  "acl:2026.acl-long.1886": "CAR-bench 将 state、tool、execution、policy 与 termination 设为联合通过条件，并区分 Pass@k 与 Pass^k，揭示“偶尔成功”不等于稳定部署。",
  "acl:2026.acl-long.734": "MediEval 以 HSR/TIR 追踪医学判断的错误跃迁；即使 macro-F1 提升，TIR 仍可能较高，因此不能把单一准确率外推为临床零风险。",
  "acl:2026.acl-long.689": "Imperfective Paradox 发现，压低 completion bias 会同时伤害本应成立的 atelic entailment；可靠 mitigation 必须加入 telic/atelic、成立/不成立双向平衡的 counterfactual controls。",
  "acl:2026.acl-long.1550": "该工作把 working-memory 约束施加到表示精度而不只 attention locality，迫使 encoding quality 与 retrieval locality 分开测量。",
  "acl:2026.acl-long.421": "CoSToM 先以冻结 probe 做 causal tracing，再用 activation-gradient bridge 调节浅层 LoRA；关键收益来自先定位机制、再施加最小干预。",
  "acl:2026.acl-long.1110": "GeoRA 根据 RLVR update geometry 选择 low-energy subspace，并以残差重参数化保持初始函数不变；价值在于让 PEFT subspace 与目标优化机制对齐。",
  "acl:2026.acl-long.1436": "STEER 分解 token entropy change 并下调异常变化；结果提示 policy update 应关注训练诱导出的分布变化，而不是只看最终 reward。",
  "acl:2026.acl-long.1653": "GISP 在每轮 pruning 后重算 |gradient × weight|，保存 nested sparsity checkpoint；它把一次性 saliency 改造成迭代重估过程。",
  "acl:2026.acl-long.893": "PALU 只干预 sensitive span 前 N 个 initiating token 的 frozen-reference top-K vocabulary，体现 temporal 与 vocabulary sparsity 下的最小必要干预。",
  "acl:2026.acl-long.1321": "CURE 将 critique correctness 与 hint utility 拆成两种训练信号，移除错误答案后重新求解，以降低错误上下文 anchoring。",
  "acl:2026.acl-long.148": "Evolutionary Guided Decoding 固定生成 policy、迭代采样并重训 value function，用于缓解 critic 的 train/deploy distribution gap。",
  "acl:2026.acl-long.270": "Generative Montage 通过 Writer、Editor、Director 与 Sybil publisher 的角色专门化，把局部真实片段组合成全局误导；风险来自对抗迭代而不只是 agent 数量。",
  "acl:2026.acl-long.2132": "CxMP 显示 construction semantics 的学习慢于一般语法能力，且偏置会随训练阶段变化；单 checkpoint 增益可能只是 heuristic 增强。",
  "acl:2026.acl-long.1739": "该理论工作形式化证明 local 与 global attention 的表达能力互补；小规模 WikiText-2 结果只能作为 sanity check，不能直接外推到 frontier LLM。",
  "acl:2026.acl-long.772": "CircularCSE 同时报告 V-Measure 与 circular CD-r，揭示几何结构 fidelity 与分类分离之间的 trade-off，不能压成单一“更好”。",
  "acl:2026.acl-long.1340": "该工作固定 syncretism 等粗结构，只扰动形式系统性，再用小 learner 测 CETL，为结构性 counterfactual 实验提供范式。",
  "acl:2026.acl-long.1657": "PolyGloss 使用 interleaved morpheme(gloss) serialization 联合生成 segmentation 与 gloss，并用确定性 parser 保证 hard alignment。",
  "acl:2026.acl-long.2203": "CIG 将 conversational information gain 分解为 novelty、relevance 与 implication scope，并用 semantic-memory update 形成可审计路径。",
  "acl:2026.acl-long.235": "RACE 将 RST discourse tree 映射为 relational graph，并用低 FPR 指标评估多类文本；论文中 split 描述存在内部不一致，解读保留该证据边界。",
  "acl:2026.acl-long.144": "DIA-HARM 显示 dialect 配比会让 over-flag authentic speech 与 under-protect communities 之间发生反转，aggregate F1 与 calibration 都不足以描述风险。",
  "acl:2026.acl-long.1869": "Afri-MCQA 通过 LID、ASR 与文本控制证明，native speech 的文化 VQA 失败常从语言识别和转写开始，再传导到 reasoning。",
  "acl:2026.acl-long.875": "Educational alignment 发现 satisfaction 与四项 pedagogical metric 无显著相关；engagement 不能替代 learning evidence。",
  "acl:2026.acl-long.2003": "ViLL-E 用共享生成 backbone 与 EOS-triggered pooling head 同时支持生成和检索，但许可型数据与外部重标使完整复现成本较高。",
  "acl:2026.acl-long.24": "MauBERT 先注入 articulatory/phone structured bias，再用少量目标语适配；ABX 结果不能直接代表 syntax 或 semantics 能力。",
  "acl:2026.acl-long.419": "Lychee-FD 以 layer-wise gradient conflict 与 semantic dilution 诊断驱动分层设计；其大量合成对话限制了 open-mic 外部效度。",
  "acl:2026.acl-long.479": "Mind the (DH) Gap! 在风险选择中观察到 reasoning model 与 conversational model 两簇；最高 LLM-human correlation 仍只有 0.42，不能把模型 preference 当成人类行为替代物。",
};

export function awardChineseInsight(paperId: string): string {
  return awardInsights[paperId] ?? "该论文的中文核心解读仍在证据复核中；下方保留已验证的英文 DeepRead。";
}

export function awardDetailRoutes(
  release: LoadedOverview | null,
): AwardRoute[] {
  if (release == null) return [];
  const validDeepReads = new Map<string, DeepRead>();
  for (const candidate of release.overview.award_deep_reads) {
    const parsed = deepReadSchema.safeParse(candidate);
    if (parsed.success) validDeepReads.set(parsed.data.paper_id, parsed.data);
  }
  const paperById = new Map(release.papers.map((paper) => [paper.paper_id, paper]));
  return release.overview.awards.flatMap((award) => {
    if (award.status !== "verified" || award.evidence_url == null) return [];
    const paper = paperById.get(award.paper_id);
    const deepRead = validDeepReads.get(award.paper_id);
    if (paper == null || deepRead == null) return [];
    return [{
      params: { paperId: awardRouteKey(award) },
      props: { detail: { award, paper, deepRead } },
    }];
  });
}

export interface AwardIndexItem {
  award: Award;
  paper: Paper | null;
  hasDetail: boolean;
}

export function buildAwardIndex(
  release: LoadedOverview | null,
): { stateLabel: "不可用" | "尚未公布" | "尚未验证" | "已验证"; items: AwardIndexItem[] } {
  if (release == null) {
    return { stateLabel: "不可用", items: [] };
  }
  const detailIds = new Set(awardDetailRoutes(release).map((route) => route.params.paperId));
  const paperById = new Map(release.papers.map((paper) => [paper.paper_id, paper]));
  const items = release.overview.awards.map((award) => ({
    award,
    paper: paperById.get(award.paper_id) ?? null,
    hasDetail: detailIds.has(awardRouteKey(award)),
  }));
  const stateLabels = {
      verified: "已验证",
      not_verified: "尚未验证",
      not_announced: "尚未公布",
    } as const;
  return {
    stateLabel: stateLabels[release.overview.award_state.status],
    items,
  };
}

export interface PaperIndexRow {
  paperId: string;
  title: string;
  authors: string[];
  theme: string;
  abstract: string | null;
  officialUrl: string;
  pdfUrl: string | null;
  codeUrl: string | null;
}

export interface PaperFilters { query: string; theme: string | null }

export function filterPapers(release: LoadedOverview, filters: PaperFilters): PaperIndexRow[] {
  const themeByPaper = new Map(
    release.overview.assignments.map((assignment) => [assignment.paper_id, assignment.primary_topic]),
  );
  const query = filters.query.trim().toLocaleLowerCase();
  return release.papers
    .map((paper) => ({
      paperId: paper.paper_id,
      title: paper.title,
      authors: paper.authors,
      theme: themeByPaper.get(paper.paper_id) ?? "Unassigned",
      abstract: paper.abstract,
      officialUrl: paper.landing_url,
      pdfUrl: paper.pdf_url,
      codeUrl: paper.code_url,
    }))
    .filter((paper) => filters.theme == null || paper.theme === filters.theme)
    .filter((paper) => {
      if (!query) return true;
      return [paper.paperId, paper.title, ...paper.authors]
        .some((value) => value.toLocaleLowerCase().includes(query));
    })
    .sort((left, right) => left.title.localeCompare(right.title));
}

export const advanceCategories = [
  { id: "text-llms", artifactKey: "text_llms", label: "文本 LLM" },
  { id: "multimodal-models", artifactKey: "multimodal_models", label: "多模态模型" },
  { id: "reasoning-agents", artifactKey: "reasoning_agents", label: "推理与 Agents" },
  { id: "data-training", artifactKey: "data_training", label: "数据 / Pretraining / Post-training" },
  { id: "evaluation-trust", artifactKey: "evaluation_trust", label: "评测 / Safety / Interpretability" },
] as const;

const advanceNarratives: Record<string, {
  title: string;
  researchQuestions: string[];
  coreProblem: string;
  technicalChange: string;
  evidenceBoundary: string;
  implication: string;
}> = {
  "audited-evidence-text_llms": {
    title: "文本 LLM：从语料 conditioning 到机制诊断",
    researchQuestions: ["文本模型应如何组织 pretraining context、扩展长上下文、避免专项适配造成灾难性损失，并诊断内部机制？"],
    coreProblem: "文本模型的进展同时受语料 conditioning、长上下文效率、分阶段适配和机制级诊断影响。",
    technicalChange: "KoCo 为预训练加入结构化知识坐标；LCA 联合压缩 KV state 与稀疏计算；Tower+ 串联 continued pretraining、SFT、preference learning 与 RL；multi-component causal tracing 用于诊断相互作用的内部路径。",
    evidenceBoundary: "这些论文覆盖不同模型家族与评测 setting；这里给出结构化比较，不意味着某一种 recipe 在所有场景都占优。",
    implication: "评估文本模型时，应联合观察 pretraining context、适配阶段、serving cost 与 causal diagnostics，而不是把质量压缩成一个标量。",
  },
  "audited-evidence-multimodal_models": {
    title: "多模态模型：组合、状态、检索与安全的联合约束",
    researchQuestions: ["多模态系统如何跨模态保持组合性、流式状态、检索结构、评估有效性与安全性？"],
    coreProblem: "多模态系统需要同时对齐组合概念、流式交互、结构化记忆、评估可靠性与 joint-modal safety。",
    technicalChange: "MACCO 建模 masked compositional concepts；AV-Dialog 融合流式音视频对话；Response-G1 用 scene graph 生成主动响应；MegaRAG 构建跨模态 knowledge-graph retrieval；MM-JudgeBias 与 CrossGuard 分别揭示 judge bias 和隐式联合模态攻击。",
    evidenceBoundary: "论文覆盖的模态、任务与 threat model 不同，不能把各自报告的增益合并为统一 effect size。",
    implication: "多模态评测应联合测试 grounding、时序状态、检索结构、judge robustness 与 cross-modal attack composition。",
  },
  "preliminary-examples-reasoning_agents": {
    title: "推理与 Agents：规划、工具、记忆与停止条件",
    researchQuestions: ["Agent 应如何拆分规划、工具使用、memory routing、浏览器状态、策略选择与 termination？"],
    coreProblem: "Agent 系统必须协调 planner-controller 分解、外部工具、持久状态、分支策略与停止决策。",
    technicalChange: "OctoTools 统一 tool card 与 planner-executor 角色；MoEC 通过 expert memory 路由子目标；SPIO 探索并选择多条 data-science plan；NestBrowse 将浏览器动作与高层信息检索控制解耦。",
    evidenceBoundary: "Reasoning and Agents 未通过最终主题 precision 门禁，因此这些论文仅作为实验性观察，不能支撑 headline prevalence 或 trend 结论。",
    implication: "Agent 评估应拆开 plan quality、tool-state transition、policy routing、recovery 与 stopping behavior，而不只报告最终任务成功率。",
  },
  "audited-evidence-data_training": {
    title: "数据与训练：从静态配比转向迭代反馈闭环",
    researchQuestions: ["Data conditioning、PEFT geometry、RLVR rollout 分布、critique loop、entropy weighting 与迭代重估之间如何相互作用？"],
    coreProblem: "训练质量取决于语料如何被 conditioning、参数子空间如何选择、rollout 如何被诱导，以及证据如何在迭代中重新估计。",
    technicalChange: "KoCo 与 Tower+ 改造预训练和适配阶段；GeoRA 让 PEFT 对齐 RLVR geometry；CURE 使用 critique-driven self-improvement；STEER 根据估计的 entropy change 加权 policy update；GISP 反复重估全局 pruning importance。",
    evidenceBoundary: "接收论文集合提供的是观察性元数据与 paper-reported 实验，不能单独证明任意通用 data-quality policy 的因果收益。",
    implication: "数据策略实验应记录策略诱导出的 rollout 分布和迭代式 model-data feedback，而不只记录静态来源计数或最终 benchmark delta。",
  },
  "audited-evidence-evaluation_trust": {
    title: "评测与可信：把动态分布和评估器纳入 contract",
    researchQuestions: ["面对 contamination、动态分布、judge bias、多模态攻击、记忆效应与重复试验，评测如何保持有效？"],
    coreProblem: "静态 accuracy 会掩盖 contamination、评估器偏差、多模态 jailbreak、隐式记忆效应，以及真实重复试验中的不一致行为。",
    technicalChange: "Rt-LRM、MM-JudgeBias、CrossGuard、MCV SafetyBench 与 DyReMe 分别压力测试推理、judge、攻击和动态诊断；ImplicitMemBench、VeriTaS 与 CAR-bench 进一步加入被动记忆、持续更新的事实核验和有状态重复可靠性证据。",
    evidenceBoundary: "各 benchmark 的构造选择和模型覆盖不同；数值结果只存在于链接论文或已验证 award DeepRead locator 中，这里不重新合并。",
    implication: "评测体系应持续刷新 case、平衡 counterfactual control、重复执行有状态试验，并在模型 accuracy 与 safety 之外同步度量 evaluator reliability。",
  },
};

export function buildAdvances(release: LoadedOverview) {
  const paperById = new Map(release.papers.map((paper) => [paper.paper_id, paper]));
  return advanceCategories.map((category) => ({
    ...category,
    advances: release.overview.advances
      .filter((advance) => advance.category === category.artifactKey)
      .map((advance) => {
        const localized = advanceNarratives[advance.advance_id];
        return {
          title: localized?.title ?? advance.title,
          audited: advance.advance_id.startsWith("audited-evidence-"),
          supportingPaperIds: advance.supporting_paper_ids,
          supportingPapers: advance.supporting_paper_ids.map((paperId) => ({
            paperId,
            title: paperById.get(paperId)!.title,
            officialUrl: paperById.get(paperId)!.landing_url,
          })),
          claims: advance.claims,
          researchQuestions: localized?.researchQuestions ?? advance.research_questions ?? [],
          coreProblem: advance.core_problem == null ? null : { ...advance.core_problem, claim: localized?.coreProblem ?? advance.core_problem.claim },
          technicalChange: advance.technical_change == null ? null : { ...advance.technical_change, claim: localized?.technicalChange ?? advance.technical_change.claim },
          evidenceBoundary: advance.evidence_boundary == null ? null : { ...advance.evidence_boundary, claim: localized?.evidenceBoundary ?? advance.evidence_boundary.claim },
          implications: (advance.implications ?? []).map((claim, index) => ({ ...claim, claim: index === 0 && localized != null ? localized.implication : claim.claim })),
        };
      }),
  }));
}

export interface MethodologyView {
  build: { generatedAt: string; producer: string; schemaVersion: string };
  sources: Array<{ name: string; url: string; sha256: string; retrievedAt: string }>;
  taxonomyVersion: string;
  scope: { venue: string; year: number; track: string; inclusionStatuses: string[]; denominator: string; denominatorUnit: string; denominatorValue: number; exclusions: string };
  contractIds: { comparison: string; formula: string; configuredVenuePopulation: string };
  configuredVenues: string[];
  emergingScoreWeights: { novelty: string; share_growth: string; spread_growth: string };
  formulas: Array<{ name: string; formula: string; numerator: string; denominator?: string; version: string }>;
  missingness: { abstracts: number; pdfs: number; dois: number };
  audits: Array<{ theme: string; sampleSize: number; observedPrecision: string; wilsonLower95: string; correctCount: number }>;
  classificationReview: {
    complete: boolean;
    lowConfidenceCount: number;
    pendingCount: number;
    rejectedCount: number;
    reviewedCount: number;
  };
  classificationLineage: {
    classifier: string;
    method: string;
    assignmentsSha256: string;
    semanticBatchCount: number;
    fullThemeStageCount: number;
    fullThemeStages: Array<{
      stageIndex: number;
      sourceThemes: string[];
      method: string;
      baseAssignmentsSha256: string;
      resultAssignmentsSha256: string;
      reviewedCount: number;
      keepCount: number;
      correctionCount: number;
      movements: Array<{ sourceTheme: string; targetTheme: string; count: number }>;
      sources: Array<{
        sourceFile: string;
        sourceTheme: string;
        sha256: string;
        paperCount: number;
        keepCount: number;
        correctionCount: number;
        assignmentBlobSha256: string | null;
        sourceAssignmentFile: string | null;
        sourceCommit: string | null;
      }>;
    }>;
    auditSampleSha256: string;
    auditDecisionSha256: string;
    auditSampleMethod: string;
    certificationSources: Array<{ source_file: string; sha256: string; decision_count: number }>;
    lowQueueSha256: string;
    lowDecisionSha256: string;
    lowComplete: boolean;
  } | null;
  withheldThemes: {
    themes: string[];
    note: string;
    items: Array<{ theme: string; status: "withheld" | "experimental"; claim: string; evidenceType: EvidenceType; sourceUrls: string[]; locator: string | null }>;
  };
  knownLimitations: string[];
}

export function buildMethodologyView(release: LoadedOverview): MethodologyView {
  const comparison = release.overview.comparison_contract;
  const metric = comparison.metric_contract;
  const lineage = release.overview.classification_lineage;
  const fullThemeStages = lineage == null
    ? []
    : (() => {
      const ledger = lineage.full_theme_review_stages;
      const rawStages = "prior_stages" in ledger
        ? [...ledger.prior_stages, ledger]
        : [ledger];
      return rawStages.map((stage, index) => ({
        stageIndex: index + 1,
        sourceThemes: stage.sources.map((source) => source.source_theme),
        method: stage.method,
        baseAssignmentsSha256: stage.base_assignments_sha256,
        resultAssignmentsSha256: stage.result_assignments_sha256,
        reviewedCount: stage.reviewed_count,
        keepCount: stage.keep_count,
        correctionCount: stage.correction_count,
        movements: Object.entries(stage.movement_matrix).flatMap(
          ([sourceTheme, targets]) => Object.entries(targets).map(
            ([targetTheme, count]) => ({ sourceTheme, targetTheme, count }),
          ),
        ),
        sources: stage.sources.map((source) => ({
          sourceFile: source.source_file,
          sourceTheme: source.source_theme,
          sha256: source.sha256,
          paperCount: source.paper_count,
          keepCount: source.keep_count,
          correctionCount: source.correction_count,
          assignmentBlobSha256: source.assignment_blob_sha256 ?? null,
          sourceAssignmentFile: source.source_assignment_file ?? null,
          sourceCommit: source.source_commit ?? null,
        })),
      }));
    })();
  return {
    build: {
      generatedAt: release.overview.build_metadata.generated_at,
      producer: release.overview.build_metadata.producer,
      schemaVersion: release.overview.build_metadata.schema_version,
    },
    sources: release.provenance.sources.map((source) => ({
      name: source.name,
      url: source.url,
      sha256: source.sha256,
      retrievedAt: source.retrieved_at,
    })),
    taxonomyVersion: release.overview.taxonomy_version,
    scope: {
      venue: comparison.comparison_scope.venue,
      year: release.scope.year,
      track: comparison.comparison_scope.track,
      inclusionStatuses: comparison.comparison_scope.inclusion_statuses,
      denominator: `${comparison.comparison_scope.denominator.artifact_field}: ${comparison.comparison_scope.denominator.description}`,
      denominatorUnit: comparison.comparison_scope.denominator.unit,
      denominatorValue: release.validation.included_count,
      exclusions: comparison.comparison_scope.excluded_records,
    },
    contractIds: {
      comparison: comparison.contract_id,
      formula: metric.formula_version,
      configuredVenuePopulation: metric.cross_venue_spread.configured_venue_id,
    },
    configuredVenues: metric.cross_venue_spread.configured_venues,
    emergingScoreWeights: metric.emerging_score.weights,
    formulas: [
      { name: "Topic share", ...metric.topic_share },
      { name: "Cross-venue spread", ...metric.cross_venue_spread },
      { name: "Emerging Score", formula: metric.emerging_score.formula, numerator: "加权 share growth、spread growth 与 novelty 分量", version: metric.emerging_score.version },
    ],
    missingness: {
      abstracts: release.validation.missing_abstract_count,
      pdfs: release.validation.missing_pdf_count,
      dois: release.validation.missing_doi_count,
    },
    audits: Object.entries(release.overview.audits).map(([theme, audit]) => ({
      theme,
      sampleSize: audit.sample_size,
      observedPrecision: audit.observed_precision,
      wilsonLower95: audit.wilson_lower_95,
      correctCount: audit.correct_count,
    })),
    classificationReview: {
      complete: release.overview.classification_review?.review_complete ?? true,
      lowConfidenceCount: release.overview.classification_review?.low_confidence_ids.length ?? 0,
      pendingCount: release.overview.classification_review?.pending_low_confidence_ids.length ?? 0,
      rejectedCount: release.overview.classification_review?.rejected_low_confidence_ids.length ?? 0,
      reviewedCount: release.overview.classification_review?.reviewed_low_confidence_ids.length ?? 0,
    },
    classificationLineage: lineage == null ? null : {
      classifier: lineage.classifier,
      method: lineage.method,
      assignmentsSha256: lineage.assignments_sha256,
      semanticBatchCount: lineage.semantic_batches.length,
      fullThemeStageCount: fullThemeStages.length,
      fullThemeStages,
      auditSampleSha256: lineage.audit.sample_registry_sha256,
      auditDecisionSha256: lineage.audit.decision_registry_sha256,
      auditSampleMethod: lineage.audit.sample_method,
      certificationSources: lineage.audit.certification_sources,
      lowQueueSha256: lineage.low_confidence_review.queue_sha256,
      lowDecisionSha256: lineage.low_confidence_review.decision_registry_sha256,
      lowComplete: lineage.low_confidence_review.complete,
    },
    withheldThemes: {
      themes: release.overview.theme_disclosures.map((item) => `${item.theme} (${item.status})`),
      note: release.overview.theme_disclosures.length === 0
        ? "当前 validated release 未发布暂缓或实验性主题 registry。"
        : `已发布 ${release.overview.theme_disclosures.length} 个带证据的暂缓或实验性主题 disclosure。`,
      items: release.overview.theme_disclosures.map((item) => ({
        theme: item.theme,
        status: item.status,
        claim: "该 assisted primary theme 未同时满足分层 audit 与穷尽式低置信度复核门禁，因此不进入 headline 结论。",
        evidenceType: item.reason.evidence_type,
        sourceUrls: item.reason.source_urls,
        locator: item.reason.locator ?? null,
      })),
    },
    knownLimitations: [
      "单年 snapshot 只能支撑分布与热点表述，不能支撑 trend 结论。",
      "缺失的可选元数据只按 coverage 报告，不被当作负面结果。",
      "Advance lane 只有在结论包含 paper-level 支撑与类别 assignment 后，才不再标记为 evidence-limited。",
    ],
  };
}
