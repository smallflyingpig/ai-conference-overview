import { z } from "zod";

import type { LoadedOverview } from "./data";
import type { FullRelease } from "./schema";

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

const httpUrl = z.string().url().refine((value) => ["http:", "https:"].includes(new URL(value).protocol));
const nonBlank = z.string().trim().min(1);
const evaluationSetting = z.string().trim().min(1, "evaluation setting is required");
const paperLocator = z.string().trim().min(1, "paper locator is required");
const evidenceClaim = z.object({
  claim: nonBlank,
  evidence_type: z.enum(evidenceTypes),
  source_urls: z.array(httpUrl).min(1),
  locator: nonBlank.nullable().optional(),
});
const resultClaim = evidenceClaim.extend({
  evidence_type: z.literal("paper_reported"),
  metric: nonBlank,
  value: z.string().regex(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[Ee][+-]?\d+)?$/, "finite numeric value required"),
  evaluation_setting: evaluationSetting,
  locator: paperLocator,
});
const methodNode = z.object({
  identifier: nonBlank,
  label: nonBlank,
  paper_section: nonBlank,
});
const methodEdge = z.object({
  source: nonBlank,
  target: nonBlank,
  data_flow_rationale: nonBlank,
});
const methodDiagram = z.object({
  nodes: z.array(methodNode).min(1),
  edges: z.array(methodEdge),
}).superRefine((diagram, context) => {
  const identifiers = diagram.nodes.map((node) => node.identifier);
  const identifierSet = new Set(identifiers);
  if (identifierSet.size !== identifiers.length) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["nodes"], message: "method diagram node identifiers must be unique" });
  }
  const pairs = new Set<string>();
  diagram.edges.forEach((edge, index) => {
    if (!identifierSet.has(edge.source) || !identifierSet.has(edge.target)) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["edges", index], message: "method diagram edges must connect disclosed nodes" });
    }
    const pair = `${edge.source}\0${edge.target}`;
    if (pairs.has(pair)) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["edges", index], message: "method diagram directed edges must be unique" });
    }
    pairs.add(pair);
  });
});

export const deepReadSchema = z.object({
  paper_id: nonBlank,
  result_claims: z.array(resultClaim),
  why_it_matters: z.array(evidenceClaim.refine(
    (claim) => claim.evidence_type !== "official_metadata",
    "why-it-matters cannot use official metadata as interpretation",
  )),
  method_diagram: methodDiagram.nullable(),
});

export type DeepRead = z.infer<typeof deepReadSchema>;
export type MethodDiagram = NonNullable<DeepRead["method_diagram"]>;
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

export function awardDetailRoutes(
  release: LoadedOverview | null,
  deepReads: readonly unknown[],
): AwardRoute[] {
  if (release == null) return [];
  const validDeepReads = new Map<string, DeepRead>();
  for (const candidate of deepReads) {
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
      params: { paperId: award.paper_id },
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
  deepReads: readonly unknown[],
): { stateLabel: "Not announced" | "Not verified" | "Verified"; items: AwardIndexItem[] } {
  if (release == null || release.overview.awards.length === 0) {
    return { stateLabel: "Not announced", items: [] };
  }
  const detailIds = new Set(awardDetailRoutes(release, deepReads).map((route) => route.params.paperId));
  const paperById = new Map(release.papers.map((paper) => [paper.paper_id, paper]));
  const items = release.overview.awards.map((award) => ({
    award,
    paper: paperById.get(award.paper_id) ?? null,
    hasDetail: detailIds.has(award.paper_id),
  }));
  if (items.some(({ award }) => award.status === "verified")) return { stateLabel: "Verified", items };
  if (items.some(({ award }) => award.status === "not_verified")) return { stateLabel: "Not verified", items };
  return { stateLabel: "Not announced", items };
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
  { id: "text-llms", label: "Text LLMs" },
  { id: "multimodal-models", label: "Multimodal Models" },
  { id: "reasoning-agents", label: "Reasoning and Agents" },
  { id: "data-training", label: "Data / Pretraining / Post-training" },
  { id: "evaluation-trust", label: "Evaluation / Safety / Interpretability" },
] as const;

export interface MethodologyView {
  sources: Array<{ name: string; url: string; sha256: string; retrievedAt: string }>;
  taxonomyVersion: string;
  scope: { venue: string; track: string; denominator: string; exclusions: string };
  formulas: Array<{ name: string; formula: string; numerator?: string; denominator?: string; version: string }>;
  missingness: { abstracts: number; pdfs: number; dois: number };
  audits: Array<{ theme: string; sampleSize: number; observedPrecision: string; wilsonLower95: string; correctCount: number }>;
  withheldThemes: { themes: string[]; note: string };
  knownLimitations: string[];
}

export function buildMethodologyView(release: LoadedOverview): MethodologyView {
  const comparison = release.overview.comparison_contract;
  const metric = comparison.metric_contract;
  return {
    sources: release.provenance.sources.map((source) => ({
      name: source.name,
      url: source.url,
      sha256: source.sha256,
      retrievedAt: source.retrieved_at,
    })),
    taxonomyVersion: release.overview.taxonomy_version,
    scope: {
      venue: comparison.comparison_scope.venue,
      track: comparison.comparison_scope.track,
      denominator: `${comparison.comparison_scope.denominator.artifact_field}: ${comparison.comparison_scope.denominator.description}`,
      exclusions: comparison.comparison_scope.excluded_records,
    },
    formulas: [
      { name: "Topic share", ...metric.topic_share },
      { name: "Cross-venue spread", ...metric.cross_venue_spread },
      { name: "Emerging Score", formula: metric.emerging_score.formula, version: metric.emerging_score.version },
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
    withheldThemes: {
      themes: [],
      note: "A withheld or experimental theme registry is not published in this validated release.",
    },
    knownLimitations: [
      "A one-year snapshot supports distribution and hotspot language, not a trend claim.",
      "Missing optional metadata is reported as coverage, never treated as a negative result.",
      "Advance lanes remain evidence-limited until claims include paper-level support and category assignments.",
    ],
  };
}

export function methodSequence(diagram: MethodDiagram): string[] {
  const labelById = new Map(diagram.nodes.map((node) => [node.identifier, node.label]));
  const incoming = new Map(diagram.nodes.map((node) => [node.identifier, 0]));
  for (const edge of diagram.edges) incoming.set(edge.target, (incoming.get(edge.target) ?? 0) + 1);
  const queue = diagram.nodes.filter((node) => incoming.get(node.identifier) === 0).map((node) => node.identifier);
  const ordered: string[] = [];
  while (queue.length > 0) {
    const identifier = queue.shift()!;
    ordered.push(labelById.get(identifier)!);
    for (const edge of diagram.edges.filter((candidate) => candidate.source === identifier)) {
      const remaining = (incoming.get(edge.target) ?? 1) - 1;
      incoming.set(edge.target, remaining);
      if (remaining === 0) queue.push(edge.target);
    }
  }
  return ordered.length === diagram.nodes.length ? ordered : diagram.nodes.map((node) => node.label);
}
