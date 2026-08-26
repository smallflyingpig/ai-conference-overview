import type { LoadedOverview } from "./data";

export type ConferenceRelease = LoadedOverview;

export interface TopicShareRow {
  topic: string;
  topicLabel: string;
  auditStatus: "audit-passed" | "experimental" | "withheld";
  paperCount: number;
  share: number;
  shareLabel: string;
  preliminaryExample: {
    paperId: string;
    title: string;
    url: string;
  };
}

export interface ConferenceView {
  mode: "distribution" | "papers-only";
  venue: string;
  venueSlug: string;
  year: number;
  track: string;
  pageHeading: string;
  scopeLabel: string;
  analysisLabel: "Distribution";
  periodLabel: string;
  trendEligible: false;
  includedCount: number;
  excludedCount: number;
  discoveredCount: number;
  abstractCoverageLabel: string;
  denominatorLabel: string;
  retrievedAt: string;
  sourceName: string;
  sourceUrl: string;
  sourceHash: string;
  generation: string;
  taxonomyVersion: string;
  comparisonContract: string;
  auditPassedThemeCount: number;
  experimentalThemeCount: number;
  withheldThemeCount: number;
  topics: TopicShareRow[];
  publicationNotice: string | null;
  finalSourceUrl: string | null;
}

export interface ConferenceRoute {
  params: { venue: string; year: string };
}

export interface TrendFilters {
  venue: string | null;
  year: number | null;
  modality: string | null;
  theme: string | null;
}

export interface TrendView {
  mode: "empty" | "snapshot" | "trend";
  heading: string;
  trendWidgetsVisible: boolean;
  missingRequirement: string | null;
  availableVenues: string[];
  availableYears: number[];
  availableThemes: string[];
  filters: TrendFilters;
  snapshots: ConferenceView[];
}

export function conferenceRoutes(releases: ConferenceRelease[]): ConferenceRoute[] {
  return releases.map(({ scope }) => ({
    params: { venue: scope.venue.toLowerCase(), year: String(scope.year) },
  }));
}

function formatCoverage(available: number, denominator: number): string {
  if (denominator === 0) return "0 / 0（不适用）";
  return `${available} / ${denominator}（${((available / denominator) * 100).toFixed(2)}%）`;
}

const topicLabels: Record<string, string> = {
  "Evaluation": "评测",
  "Learning and Optimization": "学习与优化",
  "Trustworthiness": "可信与安全",
  "Data and Retrieval": "数据与检索",
  "Multimodal Models": "多模态模型",
  "Reasoning and Agents": "推理与 Agents",
  "Applications": "应用",
  "NLP/CV Core Tasks": "NLP/CV 核心任务",
  "Foundation Models": "基础模型",
  "Multilingual and Inclusive NLP": "多语言与包容性 NLP",
  "Unassigned": "未分类",
};

export function displayTopicLabel(topic: string): string {
  return topicLabels[topic] ?? topic;
}

export function auditStatusLabel(status: TopicShareRow["auditStatus"]): string {
  return { "audit-passed": "已通过人工抽查", experimental: "仅展示初步结果", withheld: "暂不纳入主要分析" }[status];
}

export function buildConferenceView(release: ConferenceRelease): ConferenceView {
  const { venue, year, track } = release.scope;
  const mismatchedPaper = release.papers.find(
    (paper) => paper.venue !== venue || paper.year !== year || paper.track !== track,
  );
  if (mismatchedPaper != null) {
    throw new Error(`Conference view scope mismatch: ${mismatchedPaper.paper_id}`);
  }
  const paperById = new Map(release.papers.map((paper) => [paper.paper_id, paper]));
  const assignmentsByTopic = new Map<string, typeof release.overview.assignments>();
  for (const assignment of release.overview.assignments) {
    const assignments = assignmentsByTopic.get(assignment.primary_topic) ?? [];
    assignments.push(assignment);
    assignmentsByTopic.set(assignment.primary_topic, assignments);
  }
  const denominator = release.validation.included_count;
  const disclosureByTheme = new Map(
    release.overview.theme_disclosures.map((item) => [item.theme, item.status]),
  );
  const topics = [...assignmentsByTopic.entries()]
    .map(([topic, assignments]): TopicShareRow => {
      const preliminaryExample = [...assignments].sort(
        (left, right) => Number(right.confidence) - Number(left.confidence),
      )[0];
      const paper = paperById.get(preliminaryExample.paper_id);
      if (paper == null) {
        throw new Error(`Preliminary example assignment has no paper: ${preliminaryExample.paper_id}`);
      }
      const share = denominator === 0 ? 0 : assignments.length / denominator;
      return {
        topic,
        topicLabel: displayTopicLabel(topic),
        auditStatus: disclosureByTheme.get(topic) ?? "audit-passed",
        paperCount: assignments.length,
        share,
        shareLabel: `${(share * 100).toFixed(1)}%`,
        preliminaryExample: {
          paperId: paper.paper_id,
          title: paper.title,
          url: paper.landing_url,
        },
      };
    })
    .sort((left, right) => right.paperCount - left.paperCount || left.topic.localeCompare(right.topic));
  const source = release.provenance.sources[0];
  const publicationContext = release.overview.publication_context;
  const papersOnly = publicationContext != null;
  return {
    mode: papersOnly ? "papers-only" : "distribution",
    venue,
    venueSlug: venue.toLowerCase(),
    year,
    track,
    pageHeading: papersOnly
      ? `${venue} ${year} 主会论文`
      : `${venue} ${year} 长论文`,
    scopeLabel: papersOnly
      ? `${venue} ${year} · Main Conference`
      : `${venue} ${year} · ${track === "long" ? "长论文" : track}`,
    analysisLabel: "Distribution",
    periodLabel: `${year} 单年概览`,
    trendEligible: false,
    includedCount: denominator,
    excludedCount: release.validation.excluded_count,
    discoveredCount: release.validation.discovered_count,
    abstractCoverageLabel: formatCoverage(
      denominator - release.validation.missing_abstract_count,
      denominator,
    ),
    denominatorLabel: `${denominator} 篇纳入统计的${track === "long" ? "长论文" : ` ${track} 类论文`}`,
    retrievedAt: source.retrieved_at,
    sourceName: source.name,
    sourceUrl: source.url,
    sourceHash: source.sha256,
    generation: release.generation,
    taxonomyVersion: release.overview.taxonomy_version,
    comparisonContract: comparisonKey(release),
    auditPassedThemeCount: topics.filter((row) => row.auditStatus === "audit-passed").length,
    experimentalThemeCount: topics.filter((row) => row.auditStatus === "experimental").length,
    withheldThemeCount: topics.filter((row) => row.auditStatus === "withheld").length,
    topics: papersOnly ? [] : topics,
    publicationNotice: publicationContext?.notice ?? null,
    finalSourceUrl: publicationContext?.final_source_url ?? null,
  };
}

function comparisonKey(release: ConferenceRelease): string {
  return JSON.stringify({
    venue: release.scope.venue,
    track: release.scope.track,
    taxonomyVersion: release.overview.taxonomy_version,
    comparisonScope: release.overview.comparison_contract.comparison_scope,
    metricFormulaContractId: release.overview.comparison_contract.contract_id,
  });
}

function hasComparableSnapshotWindow(snapshots: ConferenceView[]): boolean {
  const byContract = new Map<string, number[]>();
  for (const snapshot of snapshots) {
    const years = byContract.get(snapshot.comparisonContract) ?? [];
    years.push(snapshot.year);
    byContract.set(snapshot.comparisonContract, years);
  }
  return [...byContract.values()].some((years) => {
    const unique = [...new Set(years)].sort((a, b) => a - b);
    return unique.some((year, index) =>
      index >= 2 && unique[index - 2] === year - 2 && unique[index - 1] === year - 1,
    );
  });
}

const emptyFilters: TrendFilters = {
  venue: null,
  year: null,
  modality: null,
  theme: null,
};

function filterSnapshots(
  snapshots: ConferenceView[],
  filters: TrendFilters,
): ConferenceView[] {
  return snapshots
    .filter((snapshot) => filters.venue == null || snapshot.venue === filters.venue)
    .filter((snapshot) => filters.year == null || snapshot.year === filters.year)
    .map((snapshot) => ({
      ...snapshot,
      topics:
        filters.theme == null
          ? snapshot.topics
          : snapshot.topics.filter((topic) => topic.topic === filters.theme),
    }))
    .filter((snapshot) => filters.theme == null || snapshot.topics.length > 0)
    .filter(() => filters.modality == null);
}

export function buildTrendView(
  releases: ConferenceRelease[],
  filters: TrendFilters = emptyFilters,
): TrendView {
  const allSnapshots = releases.map(buildConferenceView);
  const snapshots = filterSnapshots(allSnapshots, filters);
  const availableVenues = [...new Set(allSnapshots.map((snapshot) => snapshot.venue))].sort();
  const availableYears = [...new Set(allSnapshots.map((snapshot) => snapshot.year))].sort((a, b) => a - b);
  const availableThemes = [...new Set(allSnapshots.flatMap((snapshot) => snapshot.topics.map((row) => row.topic)))].sort();
  if (releases.length === 0) {
    return {
      mode: "empty",
      heading: "尚无已发布的论文分布",
      trendWidgetsVisible: false,
      missingRequirement: "只有完成全部检查并正式发布的数据版本才会出现在这里。",
      availableVenues,
      availableYears,
      availableThemes,
      filters: { ...filters },
      snapshots,
    };
  }
  const trendEligible = hasComparableSnapshotWindow(snapshots);
  return {
    mode: trendEligible ? "trend" : "snapshot",
    heading: trendEligible ? "可比较的研究趋势" : "当前论文分布",
    trendWidgetsVisible: trendEligible,
    missingRequirement: trendEligible
      ? null
      : "研究趋势和同比变化至少需要三个连续且可以直接比较的年份。",
    availableVenues,
    availableYears,
    availableThemes,
    filters: { ...filters },
    snapshots,
  };
}

export function parseTrendFilters(search: string, view: TrendView): TrendFilters {
  const query = new URLSearchParams(search);
  const venue = query.get("venue");
  const yearValue = query.get("year");
  const parsedYear = yearValue == null ? null : Number(yearValue);
  const theme = query.get("theme");
  return {
    venue: venue != null && view.availableVenues.includes(venue) ? venue : null,
    year:
      parsedYear != null && Number.isInteger(parsedYear) && view.availableYears.includes(parsedYear)
        ? parsedYear
        : null,
    theme: theme != null && view.availableThemes.includes(theme) ? theme : null,
    modality: null,
  };
}

export function applyTrendFilters(view: TrendView, filters: TrendFilters): TrendView {
  const snapshots = filterSnapshots(view.snapshots, filters);
  const trendEligible = hasComparableSnapshotWindow(snapshots);
  return {
    ...view,
    mode: trendEligible ? "trend" : view.mode === "empty" ? "empty" : "snapshot",
    heading: trendEligible
      ? "可比较的研究趋势"
      : view.mode === "empty"
        ? "尚无已发布的论文分布"
        : "当前论文分布",
    trendWidgetsVisible: trendEligible,
    missingRequirement: trendEligible
      ? null
      : view.mode === "empty"
        ? view.missingRequirement
        : "研究趋势和同比变化至少需要三个连续且可以直接比较的年份。",
    filters: { ...filters },
    snapshots,
  };
}
