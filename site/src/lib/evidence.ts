import { createHash } from "node:crypto";

import type { LoadedOverview } from "./data";
import { projectPath } from "./paths";
export { awardFilterHref, parseAwardFilter } from "./award-filter";
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
  official_metadata: "官方信息",
  paper_reported: "论文原文结果",
  cross_paper_synthesis: "多篇论文综合",
  inference: "进一步判断",
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
    "Outstanding Position Paper": "杰出立场论文",
  }[awardType] ?? awardType;
}

export function awardStatusLabel(status: string): string {
  return { verified: "官方信息已确认", not_verified: "尚待官方确认", not_announced: "尚未公布" }[status] ?? status;
}

const awardInsights: Record<string, string> = {
  "acl:2026.acl-long.1301": "ImplicitMemBench 分别测量学习或启动效应、信息干扰和首次作答表现。17 个模型的总分都没有超过 66%，说明模型能显式找回信息，并不代表它已经形成稳定的行为适应。",
  "acl:2026.acl-long.1654": "Audio MultiChallenge 保留真人语音中的回溯、停顿、环境声和副语言信息。在 452 段录音和 1,712 条细粒度评分标准上，表现最好的系统 APR 也只有 54.65%。",
  "acl:2026.acl-long.1948": "VeriTaS 每季度更新数据，并记录声明日期、按时间筛选检索结果，以减少持续预训练造成的信息泄漏。模型在知识截止日之后表现持续下降，说明 benchmark 设计必须把时间变化纳入考虑。",
  "acl:2026.acl-long.937": "HSCodeComp 用 632 个商品测试层级编码规则，最佳 Agent 的十位编码完全匹配率为 46.83%。加入专家编写的 Decision Rules 后，效果反而没有提高，说明更多推理材料也可能带来干扰。",
  "acl:2026.acl-long.1886": "CAR-bench 要求状态判断、工具选择、执行结果、策略和停止条件同时正确，并分别报告 Pass@k 与 Pass^k。它揭示了一个重要差别：模型偶尔成功，不等于能够稳定部署。",
  "acl:2026.acl-long.734": "MediEval 用 HSR 和 TIR 追踪医学判断如何从一种错误转变为另一种错误。即使 macro-F1 提高，TIR 仍可能偏高，因此单一准确率指标不能说明临床风险已经消失。",
  "acl:2026.acl-long.689": "Imperfective Paradox 发现，降低完成体偏差会同时损害本应成立的非终结性蕴含。要判断缓解方法是否可靠，测试集必须同时平衡终结性与非终结性、成立与不成立两组反事实样例。",
  "acl:2026.acl-long.1550": "这项工作把工作记忆的容量限制落实到表示精度，而不只是局部注意范围。因此，评测需要分别观察编码质量和检索位置，不能把两者混为一谈。",
  "acl:2026.acl-long.421": "CoSToM 先用冻结的探针进行因果追踪，再通过激活—梯度桥接调节浅层 LoRA。它的核心思路是先定位起作用的内部机制，再施加尽可能小的干预。",
  "acl:2026.acl-long.1110": "GeoRA 根据 RLVR 的更新几何结构选择低能量子空间，并通过残差重参数化保持初始函数不变。这样可以让 PEFT 使用的参数子空间更贴近目标优化过程。",
  "acl:2026.acl-long.1436": "STEER 分解 token 熵的变化，并降低异常变化样本的权重。结果表明，更新策略时需要关注训练造成的分布变化，不能只看最终奖励。",
  "acl:2026.acl-long.1653": "GISP 每完成一轮剪枝，都会重新计算 |gradient × weight|，并保存不同稀疏度的检查点。相比一次性计算重要性，它把剪枝变成了持续重估的过程。",
  "acl:2026.acl-long.893": "PALU 只干预敏感片段最前面的 N 个 token，并把候选限制在冻结参考模型的 top-K 词表中。这种设计同时利用了时间和词表两类稀疏性，把干预范围压到最低。",
  "acl:2026.acl-long.1321": "CURE 把“批评是否正确”和“提示是否有用”拆成两种训练信号，再移除错误答案并重新求解，从而减少错误上下文造成的锚定效应。",
  "acl:2026.acl-long.148": "Evolutionary Guided Decoding 固定生成策略，通过多轮采样持续重训价值函数，以缓解评分模型在训练阶段和实际生成阶段面对的数据分布差异。",
  "acl:2026.acl-long.270": "Generative Montage 让 Writer、Editor、Director 和负责制造虚假共识的 Sybil publisher 各司其职，把局部真实的片段组合成整体误导。风险主要来自多轮对抗协作，而不只是 Agent 数量增加。",
  "acl:2026.acl-long.2132": "CxMP 发现，模型学习构式语义的速度慢于学习一般语法，而且偏差会随训练阶段变化。因此，单个训练检查点上的提升也可能只是模型更依赖某种启发式模式。",
  "acl:2026.acl-long.1739": "这项理论工作证明，局部注意力和全局注意力在表达能力上可以互补。WikiText-2 上的小规模实验只能说明方法可行，不能直接推及前沿大模型。",
  "acl:2026.acl-long.772": "CircularCSE 同时报告 V-Measure 和 circular CD-r，从而分别观察分类分离度和圆形几何结构的保真度。两项指标之间存在取舍，不能简单合并成一个“更好”的分数。",
  "acl:2026.acl-long.1340": "这项工作固定同形融合（syncretism）等整体结构，只改变形式的系统性，再用小型学习模型测量 CETL，为研究语言结构的反事实实验提供了一种可复用方法。",
  "acl:2026.acl-long.1657": "PolyGloss 把词素及其释义（gloss）交错排列，同时生成词素切分和注释，再用确定性解析器保证二者一一对应。",
  "acl:2026.acl-long.2203": "CIG 把对话中的信息增益拆成新颖性、相关性和影响范围，并通过语义记忆更新记录每一步信息变化，使处理过程可以追踪。",
  "acl:2026.acl-long.235": "RACE 把 RST 篇章树转换成关系图，并用低 FPR 指标评估多种文本。论文对数据划分的描述前后不一致，因此解读时必须保留这一限制。",
  "acl:2026.acl-long.144": "DIA-HARM 发现，改变方言数据的配比，会使“过度标记真实方言”和“对相关群体保护不足”两类风险发生反转。汇总 F1 和校准度都不足以完整描述这种变化。",
  "acl:2026.acl-long.1869": "Afri-MCQA 通过语言识别、语音识别和文本对照实验发现，模型处理母语语音文化问答时，错误往往从语言识别和转写环节开始，随后传导到推理阶段。",
  "acl:2026.acl-long.875": "Educational alignment 发现，用户满意度与四项教学质量指标之间没有显著相关性。对话更有参与感，并不代表学习效果更好。",
  "acl:2026.acl-long.2003": "ViLL-E 使用共享的生成主干网络和由 EOS 触发的池化头，同时支持文本生成与检索。不过，数据许可限制和外部重标流程提高了完整复现的成本。",
  "acl:2026.acl-long.24": "MauBERT 先注入发音和音素结构先验，再用少量目标语言数据进行适配。论文中的 ABX 结果反映语音表征能力，不能直接代表句法或语义能力。",
  "acl:2026.acl-long.419": "Lychee-FD 从不同层之间的梯度冲突和语义稀释出发设计分层模型。不过，实验大量使用合成对话，对真实开放麦克风环境的代表性仍然有限。",
  "acl:2026.acl-long.479": "Mind the (DH) Gap! 在风险选择任务中观察到推理型模型和对话型模型两个明显分组。模型与人类行为的最高相关系数仍只有 0.42，因此不能用模型的偏好代替真实的人类选择。",
};

export function awardChineseInsight(paperId: string): string {
  const insight = awardInsights[paperId];
  if (insight == null) {
    throw new Error(`缺少中文解读：${paperId}`);
  }
  return insight;
}

export function awardDetailRoutes(
  releaseOrReleases: LoadedOverview | LoadedOverview[] | null,
): AwardRoute[] {
  if (releaseOrReleases == null) return [];
  const releases = Array.isArray(releaseOrReleases) ? releaseOrReleases : [releaseOrReleases];
  const routes = releases.flatMap((release) => {
    if (
      release.overview.publication_context != null &&
      !release.overview.publication_context.analysis_availability.awards
    ) return [];
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
  });
  const keys = routes.map((route) => route.params.paperId);
  if (new Set(keys).size !== keys.length) {
    throw new Error("Award detail routes collide across published releases");
  }
  return routes;
}

export interface AwardIndexItem {
  award: Award;
  paper: Paper | null;
  hasDetail: boolean;
}

export function buildAwardIndex(
  release: LoadedOverview | null,
): { stateLabel: "不可用" | "尚未公布" | "尚待官方确认" | "官方信息已确认"; items: AwardIndexItem[] } {
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
      verified: "官方信息已确认",
      not_verified: "尚待官方确认",
      not_announced: "尚未公布",
    } as const;
  return {
    stateLabel: stateLabels[release.overview.award_state.status],
    items,
  };
}

export interface AwardConferenceIndex {
  venue: string;
  year: number;
  stateLabel: ReturnType<typeof buildAwardIndex>["stateLabel"];
  items: AwardIndexItem[];
}

export function buildAwardConferenceIndexes(
  releases: LoadedOverview[],
): AwardConferenceIndex[] {
  return releases
    .filter((release) => release.overview.publication_context == null ||
      release.overview.publication_context.analysis_availability.awards)
    .map((release) => ({
      venue: release.scope.venue,
      year: release.scope.year,
      ...buildAwardIndex(release),
    }))
    .sort((left, right) =>
      right.year - left.year || left.venue.localeCompare(right.venue));
}

export interface PaperIndexRow {
  paperId: string;
  title: string;
  authors: string[];
  theme: string | null;
  venue: string;
  year: number;
  detailUrl: string | null;
  abstract: string | null;
  officialUrl: string;
  pdfUrl: string | null;
  codeUrl: string | null;
}

export interface PaperFilters {
  query: string;
  theme: string | null;
  venue?: string | null;
}

export function paperRouteKey(paperId: string): string {
  return `paper-${createHash("sha256").update(paperId).digest("hex")}`;
}

export function filterPapers(
  releaseOrReleases: LoadedOverview | LoadedOverview[],
  filters: PaperFilters,
): PaperIndexRow[] {
  const releases = Array.isArray(releaseOrReleases)
    ? releaseOrReleases
    : [releaseOrReleases];
  const query = filters.query.trim().toLocaleLowerCase();
  return releases
    .flatMap((release) => {
      const themeByPaper = new Map(
        release.overview.assignments.map((assignment) => [
          assignment.paper_id,
          assignment.primary_topic,
        ]),
      );
      const hasInternalDetails = release.overview.publication_context != null;
      return release.papers.map((paper) => ({
        paperId: paper.paper_id,
        title: paper.title,
        authors: paper.authors,
        theme: themeByPaper.get(paper.paper_id) ?? null,
        venue: paper.venue,
        year: paper.year,
        detailUrl: hasInternalDetails
          ? projectPath("/ai-conference-overview/", `papers/${paperRouteKey(paper.paper_id)}`)
          : null,
        abstract: paper.abstract,
        officialUrl: paper.landing_url,
        pdfUrl: paper.pdf_url,
        codeUrl: paper.code_url,
      }));
    })
    .filter((paper) => filters.venue == null || paper.venue === filters.venue)
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
  { id: "data-training", artifactKey: "data_training", label: "数据与训练（Pretraining / Post-training）" },
  { id: "evaluation-trust", artifactKey: "evaluation_trust", label: "评测、Safety 与 Interpretability" },
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
    title: "文本 LLM：从预训练语境设计到内部机制分析",
    researchQuestions: ["如何组织预训练上下文、提高长上下文效率、减少专项适配带来的能力损失，并解释模型内部机制？"],
    coreProblem: "文本模型的效果不只取决于模型规模，还受到预训练上下文、长文本计算效率、分阶段适配方法和内部机制的共同影响。",
    technicalChange: "KoCo 在预训练数据中加入结构化知识坐标；LCA 同时压缩 KV 状态并减少无效计算；Tower+ 依次使用持续预训练、SFT、偏好学习和强化学习；多组件因果追踪（multi-component causal tracing）则用来分析多个内部组件如何共同作用。",
    evidenceBoundary: "这些论文研究的模型、任务和评测方法并不相同。这里比较的是技术思路，不能据此断定某一种训练方法在所有场景中都更好。",
    implication: "评估文本模型时，应同时观察预训练上下文、适配阶段、推理成本和内部机制，不能用单一分数概括模型质量。",
  },
  "audited-evidence-multimodal_models": {
    title: "多模态模型：同时兼顾组合、状态、检索与安全",
    researchQuestions: ["多模态系统如何同时处理组合概念、流式交互状态、结构化检索、评测偏差和跨模态安全问题？"],
    coreProblem: "多模态系统既要理解不同模态之间的组合关系，也要维持流式交互状态、使用结构化记忆，并抵御多种模态共同构成的攻击。",
    technicalChange: "MACCO 学习被遮盖的组合概念；AV-Dialog 处理流式音视频对话；Response-G1 借助场景图决定何时主动响应；MegaRAG 用跨模态知识图谱进行检索；MM-JudgeBias 和 CrossGuard 分别分析评测模型偏差与隐式跨模态攻击。",
    evidenceBoundary: "这些论文覆盖的模态、任务和攻击方式不同，各自报告的提升不能合并成一个统一数值。",
    implication: "多模态评测需要同时检查信息定位、时序状态、检索结构、评测模型的稳定性，以及不同模态组合后的攻击风险。",
  },
  "preliminary-examples-reasoning_agents": {
    title: "推理与 Agents：规划、工具、记忆与停止条件",
    researchQuestions: ["Agent 应如何协调任务规划、工具调用、记忆选择、浏览器状态、策略分支和停止条件？"],
    coreProblem: "Agent 需要把高层规划与具体执行结合起来，同时管理外部工具、长期状态、不同策略分支和停止时机。",
    technicalChange: "OctoTools 统一描述工具能力，并分离规划与执行角色；MoEC 根据子目标选择专家记忆；SPIO 生成并筛选多条数据科学方案；NestBrowse 则把浏览器操作与高层信息检索分开学习。",
    evidenceBoundary: "“推理与 Agents”主题在最终 AI 辅助复核中没有达到精度标准，因此这些论文只用于初步观察，不能据此判断该主题的整体占比或长期趋势。",
    implication: "评估 Agent 时，应分别衡量规划质量、工具和状态变化、策略选择、失败恢复与停止行为，而不能只报告最终任务成功率。",
  },
  "audited-evidence-data_training": {
    title: "数据与训练：从静态配比转向迭代反馈闭环",
    researchQuestions: ["数据组织、PEFT 参数空间、RLVR 采样分布、批评反馈、熵权重和迭代重估会怎样共同影响训练？"],
    coreProblem: "训练效果既取决于语料组织方式，也取决于参数子空间的选择、采样分布的变化，以及模型反馈如何进入下一轮训练。",
    technicalChange: "KoCo 和 Tower+ 分别调整预训练语料与分阶段适配流程；GeoRA 让 PEFT 的参数空间贴近 RLVR 的优化方向；CURE 利用批评反馈改进答案；STEER 根据熵变化调整样本权重；GISP 在每轮剪枝后重新计算参数重要性。",
    evidenceBoundary: "这些接收论文提供了论文元数据和各自报告的实验结果，但不能单独证明某种通用数据质量策略一定带来因果收益。",
    implication: "数据策略实验除了记录数据来源和 benchmark 变化，还应跟踪采样分布如何变化，以及模型反馈怎样影响下一轮数据。",
  },
  "audited-evidence-evaluation_trust": {
    title: "评测与可信：把动态分布和评估器纳入整体设计",
    researchQuestions: ["面对数据污染、持续变化的任务分布、评测模型偏差、多模态攻击和记忆效应，如何让评测长期有效？"],
    coreProblem: "静态准确率会掩盖训练数据污染、评测模型偏差、多模态越狱、隐式记忆效应，以及模型在重复试验中的不一致表现。",
    technicalChange: "Rt-LRM、MM-JudgeBias、CrossGuard、MCV SafetyBench 和 DyReMe 分别测试推理模型、评测模型、多模态攻击与动态诊断；ImplicitMemBench、VeriTaS 和 CAR-bench 又加入了隐式记忆、持续更新的事实检查和有状态重复试验。",
    evidenceBoundary: "各 benchmark 的构造方式和覆盖模型不同。具体数值可查看所列论文或获奖论文解读中的章节与表格，这里不把它们合并比较。",
    implication: "评测体系应持续更新样例、平衡反事实对照，并多次运行有状态任务；除了模型的准确率和安全性，还要衡量评测器本身是否稳定可靠。",
  },
};

function displayAdvanceLocator(
  locator: string | null | undefined,
): string | null | undefined {
  if (locator === "Official ACL Anthology Abstract for every linked supporting paper") {
    return "所列论文在 ACL Anthology 上的官方摘要";
  }
  if (locator === "Inference from the linked ACL paper abstracts") {
    return "根据所列论文的 ACL Anthology 官方摘要综合分析";
  }
  return locator;
}

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
          coreProblem: advance.core_problem == null ? null : { ...advance.core_problem, claim: localized?.coreProblem ?? advance.core_problem.claim, locator: displayAdvanceLocator(advance.core_problem.locator) },
          technicalChange: advance.technical_change == null ? null : { ...advance.technical_change, claim: localized?.technicalChange ?? advance.technical_change.claim, locator: displayAdvanceLocator(advance.technical_change.locator) },
          evidenceBoundary: advance.evidence_boundary == null ? null : { ...advance.evidence_boundary, claim: localized?.evidenceBoundary ?? advance.evidence_boundary.claim, locator: displayAdvanceLocator(advance.evidence_boundary.locator) },
          implications: (advance.implications ?? []).map((claim, index) => ({ ...claim, claim: index === 0 && localized != null ? localized.implication : claim.claim, locator: displayAdvanceLocator(claim.locator) })),
        };
      }),
  }));
}

export interface MethodologyView {
  build: { generatedAt: string; producer: string; schemaVersion: string };
  sources: Array<{ name: string; url: string; sha256: string; retrievedAt: string }>;
  taxonomyVersion: string;
  scope: { venue: string; year: number; track: string; inclusionStatuses: string[]; denominator: string; denominatorField: string; denominatorUnit: string; denominatorValue: number; exclusions: string };
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

function displayReviewMethod(method: string): string {
  if (method === "exhaustive title-and-abstract full-theme semantic review") {
    return "逐篇阅读标题和摘要，完成全主题语义复查";
  }
  return method;
}

function displaySampleMethod(method: string): string {
  if (method.startsWith("deterministic confidence-stratified precision audit")) {
    return "AI 辅助复核按置信度分层，每个主要主题（primary topic）最多检查 50 篇。主题不足 50 篇时检查全部论文，并要求全部分类正确；其余主题要求抽查准确率不低于 90%，且 Wilson 95% 下界不低于 0.80。该检查只衡量主主题分类的准确率，不衡量召回率。";
  }
  return method;
}

function displayClassifier(classifier: string): string {
  if (classifier === "agent-semantic-batch-review-v1") {
    return "分批语义分类（agent-semantic-batch-review-v1）";
  }
  return classifier;
}

function displayClassificationMethod(method: string): string {
  if (method === "explicit_agent_semantic_labeling") {
    return "逐篇阅读标题和摘要后明确标注主要主题";
  }
  if (method === "embedding_assisted_semantic_labeling") {
    return "AI 辅助主题分类：标题决定主要研究问题，摘要用于消除歧义";
  }
  return method;
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
        method: displayReviewMethod(stage.method),
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
      track: comparison.comparison_scope.track === "long" ? "长论文" : comparison.comparison_scope.track,
      inclusionStatuses: comparison.comparison_scope.inclusion_statuses.map((status) => ({
        complete: "信息完整",
        partial: "部分信息缺失",
      }[status] ?? status)),
      denominator: "明确排除不在范围内的记录后，实际纳入统计的论文数",
      denominatorField: comparison.comparison_scope.denominator.artifact_field,
      denominatorUnit: comparison.comparison_scope.denominator.unit === "paper" ? "篇论文" : comparison.comparison_scope.denominator.unit,
      denominatorValue: release.validation.included_count,
      exclusions: "排除项单独保留，不计入统计分母",
    },
    contractIds: {
      comparison: comparison.contract_id,
      formula: metric.formula_version,
      configuredVenuePopulation: metric.cross_venue_spread.configured_venue_id,
    },
    configuredVenues: metric.cross_venue_spread.configured_venues,
    emergingScoreWeights: metric.emerging_score.weights,
    formulas: [
      { name: "主要主题（primary topic）占比", formula: metric.topic_share.formula, numerator: "每篇纳入论文只计入一个主要主题", denominator: "纳入统计的论文数", version: metric.topic_share.version },
      { name: "跨会议覆盖率", formula: metric.cross_venue_spread.formula, numerator: "出现该主题的会议数", denominator: "配置中的会议总数", version: metric.cross_venue_spread.version },
      { name: "新兴主题得分", formula: metric.emerging_score.formula, numerator: "按权重合并主题占比变化、跨会议覆盖变化和新颖度", version: metric.emerging_score.version },
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
      classifier: displayClassifier(lineage.classifier),
      method: displayClassificationMethod(lineage.method),
      assignmentsSha256: lineage.assignments_sha256,
      semanticBatchCount: lineage.semantic_batches.length,
      fullThemeStageCount: fullThemeStages.length,
      fullThemeStages,
      auditSampleSha256: lineage.audit.sample_registry_sha256,
      auditDecisionSha256: lineage.audit.decision_registry_sha256,
      auditSampleMethod: displaySampleMethod(lineage.audit.sample_method),
      certificationSources: lineage.audit.certification_sources,
      lowQueueSha256: lineage.low_confidence_review.queue_sha256,
      lowDecisionSha256: lineage.low_confidence_review.decision_registry_sha256,
      lowComplete: lineage.low_confidence_review.complete,
    },
    withheldThemes: {
      themes: release.overview.theme_disclosures.map((item) => `${item.theme} (${item.status})`),
      note: release.overview.theme_disclosures.length === 0
        ? "当前数据版本没有需要暂时排除的主题。"
        : `当前有 ${release.overview.theme_disclosures.length} 个主题暂不纳入主要分析。`,
      items: release.overview.theme_disclosures.map((item) => ({
        theme: item.theme,
        status: item.status,
        claim: "该主题尚未同时达到分层 AI 辅助复核和低置信度逐篇复查的标准，因此暂不用于概括会议的主要研究方向。",
        evidenceType: item.reason.evidence_type,
        sourceUrls: item.reason.source_urls,
        locator: item.reason.locator ?? null,
      })),
    },
    knownLimitations: [
      "目前只有一年的数据，只能介绍主题分布和热点，不能判断长期趋势。",
      "摘要、PDF 或 DOI 等可选信息缺失时，只会影响覆盖率统计，不代表论文质量较差。",
      "每条研究主线都必须列出相关论文，并完成主题分类检查，之后才会纳入综合分析。",
    ],
  };
}
