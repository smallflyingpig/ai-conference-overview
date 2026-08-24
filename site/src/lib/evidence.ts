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
  official_metadata: "Official metadata",
  paper_reported: "Paper-reported",
  cross_paper_synthesis: "Cross-paper synthesis",
  inference: "Inference",
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
): { stateLabel: "Unavailable" | "Not announced" | "Not verified" | "Verified"; items: AwardIndexItem[] } {
  if (release == null) {
    return { stateLabel: "Unavailable", items: [] };
  }
  const detailIds = new Set(awardDetailRoutes(release).map((route) => route.params.paperId));
  const paperById = new Map(release.papers.map((paper) => [paper.paper_id, paper]));
  const items = release.overview.awards.map((award) => ({
    award,
    paper: paperById.get(award.paper_id) ?? null,
    hasDetail: detailIds.has(awardRouteKey(award)),
  }));
  const stateLabels = {
      verified: "Verified",
      not_verified: "Not verified",
      not_announced: "Not announced",
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
  { id: "text-llms", artifactKey: "text_llms", label: "Text LLMs" },
  { id: "multimodal-models", artifactKey: "multimodal_models", label: "Multimodal Models" },
  { id: "reasoning-agents", artifactKey: "reasoning_agents", label: "Reasoning and Agents" },
  { id: "data-training", artifactKey: "data_training", label: "Data / Pretraining / Post-training" },
  { id: "evaluation-trust", artifactKey: "evaluation_trust", label: "Evaluation / Safety / Interpretability" },
] as const;

export function buildAdvances(release: LoadedOverview) {
  const paperById = new Map(release.papers.map((paper) => [paper.paper_id, paper]));
  return advanceCategories.map((category) => ({
    ...category,
    advances: release.overview.advances
      .filter((advance) => advance.category === category.artifactKey)
      .map((advance) => ({
        title: advance.title,
        supportingPaperIds: advance.supporting_paper_ids,
        supportingPapers: advance.supporting_paper_ids.map((paperId) => ({
          paperId,
          title: paperById.get(paperId)!.title,
          officialUrl: paperById.get(paperId)!.landing_url,
        })),
        claims: advance.claims,
      })),
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
      { name: "Emerging Score", formula: metric.emerging_score.formula, numerator: "weighted share growth, spread growth, and novelty components", version: metric.emerging_score.version },
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
    withheldThemes: {
      themes: release.overview.theme_disclosures.map((item) => `${item.theme} (${item.status})`),
      note: release.overview.theme_disclosures.length === 0
        ? "A withheld or experimental theme registry is not published in this validated release."
        : `${release.overview.theme_disclosures.length} withheld or experimental theme disclosures are published with evidence.`,
      items: release.overview.theme_disclosures.map((item) => ({
        theme: item.theme,
        status: item.status,
        claim: item.reason.claim,
        evidenceType: item.reason.evidence_type,
        sourceUrls: item.reason.source_urls,
        locator: item.reason.locator ?? null,
      })),
    },
    knownLimitations: [
      "A one-year snapshot supports distribution and hotspot language, not a trend claim.",
      "Missing optional metadata is reported as coverage, never treated as a negative result.",
      "Advance lanes remain evidence-limited until claims include paper-level support and category assignments.",
    ],
  };
}
