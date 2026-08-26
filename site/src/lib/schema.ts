import { createHash } from "node:crypto";

import { z } from "zod";
import awardHostPolicy from "../../../config/award-host-policy.json";

const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/i, "sha256 must be 64 hexadecimal characters");
const nonBlankSchema = z.string().trim().min(1);
const decimalSchema = z
  .string()
  .regex(
    /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[Ee][+-]?\d+)?$/,
    "must be a finite decimal string",
  );
const urlSchema = z.string().url().refine(
  (value) => {
    const protocol = new URL(value).protocol;
    return protocol === "http:" || protocol === "https:";
  },
  "URL must use http or https",
);
const stringPairSchema = z.tuple([z.string(), z.string()]);

interface ExactDecimal {
  sign: -1 | 0 | 1;
  digits: string;
  decimalPoint: bigint;
}

function exactDecimal(value: string): ExactDecimal {
  const match = value.match(
    /^(?<negative>-?)(?<integer>\d+)(?:\.(?<fraction>\d+))?(?:[Ee](?<exponent>[+-]?\d+))?$/,
  );
  if (match?.groups == null) {
    throw new Error("invalid finite decimal string");
  }
  const fraction = match.groups.fraction ?? "";
  const digits = `${match.groups.integer}${fraction}`.replace(/^0+/, "");
  if (digits.length === 0) {
    return { sign: 0, digits: "0", decimalPoint: 0n };
  }
  return {
    sign: match.groups.negative === "-" ? -1 : 1,
    digits,
    decimalPoint:
      BigInt(digits.length) - BigInt(fraction.length) + BigInt(match.groups.exponent ?? "0"),
  };
}

function compareExactDecimals(left: string, right: string): -1 | 0 | 1 {
  const first = exactDecimal(left);
  const second = exactDecimal(right);
  if (first.sign !== second.sign) return first.sign < second.sign ? -1 : 1;
  if (first.sign === 0) return 0;

  let magnitude: -1 | 0 | 1 = 0;
  if (first.decimalPoint !== second.decimalPoint) {
    magnitude = first.decimalPoint < second.decimalPoint ? -1 : 1;
  } else {
    const length = Math.max(first.digits.length, second.digits.length);
    for (let index = 0; index < length; index += 1) {
      const firstDigit = first.digits[index] ?? "0";
      const secondDigit = second.digits[index] ?? "0";
      if (firstDigit !== secondDigit) {
        magnitude = firstDigit < secondDigit ? -1 : 1;
        break;
      }
    }
  }
  return first.sign === 1 ? magnitude : magnitude === 0 ? 0 : magnitude === 1 ? -1 : 1;
}

function pythonDecimalRatio(
  numeratorValue: number,
  denominatorValue: number,
): string {
  const numerator = BigInt(numeratorValue);
  const denominator = BigInt(denominatorValue);
  if (numerator === 0n) return "0";

  let exponent = 0;
  let scaledNumerator = numerator;
  while (scaledNumerator < denominator) {
    scaledNumerator *= 10n;
    exponent -= 1;
  }

  const precision = 28;
  const scale = precision - 1 - exponent;
  const dividend = numerator * 10n ** BigInt(scale);
  let coefficient = dividend / denominator;
  const remainder = dividend % denominator;
  const doubledRemainder = remainder * 2n;
  if (
    doubledRemainder > denominator ||
    (doubledRemainder === denominator && coefficient % 2n === 1n)
  ) {
    coefficient += 1n;
  }
  if (coefficient.toString().length > precision) {
    coefficient /= 10n;
    exponent += 1;
  }
  return `${coefficient}E${exponent - (precision - 1)}`;
}

export const evidenceTypeSchema = z.enum([
  "official_metadata",
  "paper_reported",
  "cross_paper_synthesis",
  "inference",
]);

const numericClaimPattern = /(?<![\w.])[+-]?(?:\d+(?:[.,]\d+)*|\.\d+)(?:e[+-]?\d+)?(?:\s?(?:%|％|pp|x))?(?!\w)/i;

const evidenceClaimFields = {
    claim: nonBlankSchema,
    evidence_type: evidenceTypeSchema,
    source_urls: z.array(urlSchema).min(1),
    locator: nonBlankSchema.nullable().optional(),
  } as const;

export const evidenceClaimSchema = z
  .object(evidenceClaimFields)
  .superRefine((value, context) => {
    if (
      (value.evidence_type === "paper_reported" || numericClaimPattern.test(value.claim)) &&
      value.locator == null
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["locator"],
        message: "paper-reported and numeric claims require a locator",
      });
    }
  });

const assignmentSchema = z.object({
  confidence: decimalSchema,
  paper_id: nonBlankSchema,
  primary_topic: nonBlankSchema,
  rationale: nonBlankSchema,
  secondary_topics: z.array(nonBlankSchema),
  taxonomy_version: nonBlankSchema,
});

const themeAuditSchema = z
  .object({
    correct_count: z.number().int().nonnegative(),
    observed_precision: decimalSchema,
    sample_size: z.number().int().nonnegative().max(50),
    thresholds: z.object({
      minimum_observed_precision: z.literal("0.90"),
      minimum_wilson_lower_95: z.literal("0.80"),
    }),
    wilson_lower_95: decimalSchema,
  })
  .superRefine((value, context) => {
    if (value.correct_count > value.sample_size) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["correct_count"],
        message: "audit correct count exceeds its sample size",
      });
    }
  });

const classificationReviewSchema = z.object({
  confidence_threshold: z.literal("0.70"),
  low_confidence_ids: z.array(nonBlankSchema),
  pending_low_confidence_ids: z.array(nonBlankSchema),
  rejected_low_confidence_ids: z.array(nonBlankSchema),
  review_complete: z.boolean(),
  reviewed_low_confidence_ids: z.array(nonBlankSchema),
});

const publicationContextSchema = z.object({
  status: z.enum(["preliminary_official_program", "final_proceedings"]),
  final_source_status: z.enum(["not_published", "available"]),
  final_source_url: z.string().url().refine(
    (value) => new URL(value).protocol === "https:",
    "final source URL must use HTTPS",
  ),
  notice: nonBlankSchema,
  analysis_availability: z.discriminatedUnion("distribution", [
    z.object({
      papers: z.literal(true),
      distribution: z.literal(false),
      trends: z.literal(false),
      advances: z.literal(false),
      awards: z.literal(false),
    }).strict(),
    z.object({
      papers: z.literal(true),
      distribution: z.literal(true),
      trends: z.literal(false),
      advances: z.literal(true),
      awards: z.literal(true),
    }).strict(),
  ]),
}).strict().superRefine((value, context) => {
  const expectedFinalSourceStatus = value.status === "final_proceedings"
    ? "available"
    : "not_published";
  if (value.final_source_status !== expectedFinalSourceStatus) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["final_source_status"],
      message: "publication status and final source status do not match",
    });
  }
});

const fullThemeReviewCorrectionSchema = z.object({
  corrected_primary_topic: nonBlankSchema,
  original_primary_topic: nonBlankSchema,
  paper_id: nonBlankSchema,
  source_file: nonBlankSchema,
}).strict();

const fullThemeReviewSourceSchema = z.object({
  assignment_blob_sha256: sha256Schema.optional(),
  correction_count: z.number().int().nonnegative(),
  keep_count: z.number().int().nonnegative(),
  paper_count: z.number().int().positive(),
  sha256: sha256Schema,
  source_assignment_file: nonBlankSchema.optional(),
  source_commit: z.string().regex(/^[0-9a-f]{40}$/).optional(),
  source_file: nonBlankSchema,
  source_theme: nonBlankSchema,
}).strict().superRefine((value, context) => {
  if (value.paper_count !== value.keep_count + value.correction_count) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["paper_count"],
      message: "full-theme review source counts do not reconcile",
    });
  }
  const bindings = [
    value.assignment_blob_sha256,
    value.source_assignment_file,
    value.source_commit,
  ];
  if (bindings.some((item) => item != null) && !bindings.every((item) => item != null)) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["assignment_blob_sha256"],
      message: "source assignment binding fields must be complete",
    });
  }
});

const movementMatrixSchema = z.record(
  nonBlankSchema,
  z.record(nonBlankSchema, z.number().int().positive()),
);

const fullThemeReviewStageFields = {
  base_assignments_sha256: sha256Schema,
  result_assignments_sha256: sha256Schema,
  correction_count: z.number().int().nonnegative(),
  corrections: z.array(fullThemeReviewCorrectionSchema),
  keep_count: z.number().int().nonnegative(),
  method: nonBlankSchema,
  movement_matrix: movementMatrixSchema,
  reviewed_count: z.number().int().positive(),
  sources: z.array(fullThemeReviewSourceSchema).min(1),
} as const;

const fullThemeReviewStageObjectSchema = z.object(fullThemeReviewStageFields).strict();
type FullThemeReviewStage = z.infer<typeof fullThemeReviewStageObjectSchema>;

function validateFullThemeReviewStage(
  value: FullThemeReviewStage,
  context: z.RefinementCtx,
): void {
  if (value.reviewed_count !== value.keep_count + value.correction_count) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["reviewed_count"],
      message: "full-theme review counts do not reconcile",
    });
  }
  if (value.corrections.length !== value.correction_count) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["corrections"],
      message: "full-theme correction count does not match correction rows",
    });
  }
  const correctedPaperIds = value.corrections.map((correction) => correction.paper_id);
  if (new Set(correctedPaperIds).size !== correctedPaperIds.length) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["corrections"],
      message: "full-theme correction paper IDs must be unique within a stage",
    });
  }
  const sourceFiles = value.sources.map((source) => source.source_file);
  const sourceThemes = value.sources.map((source) => source.source_theme);
  if (
    new Set(sourceFiles).size !== sourceFiles.length ||
    new Set(sourceThemes).size !== sourceThemes.length
  ) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["sources"],
      message: "full-theme review sources and source themes must be unique",
    });
  }
  const sourceByFile = new Map(
    value.sources.map((source) => [source.source_file, source]),
  );
  const expectedMovements = new Map<string, number>();
  for (const source of value.sources) {
    expectedMovements.set(
      `${source.source_theme}\0${source.source_theme}`,
      source.keep_count,
    );
    if (
      source.assignment_blob_sha256 != null &&
      source.assignment_blob_sha256 !== value.base_assignments_sha256
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["sources", value.sources.indexOf(source), "assignment_blob_sha256"],
        message: "source assignment binding does not match stage base assignments",
      });
    }
  }
  for (const [index, correction] of value.corrections.entries()) {
    const source = sourceByFile.get(correction.source_file);
    if (source == null || source.source_theme !== correction.original_primary_topic) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["corrections", index, "source_file"],
        message: "correction is not bound to its declared source theme",
      });
      continue;
    }
    const key = `${correction.original_primary_topic}\0${correction.corrected_primary_topic}`;
    expectedMovements.set(key, (expectedMovements.get(key) ?? 0) + 1);
  }
  const actualMovements = new Map<string, number>();
  for (const [sourceTheme, targets] of Object.entries(value.movement_matrix)) {
    for (const [targetTheme, count] of Object.entries(targets)) {
      actualMovements.set(`${sourceTheme}\0${targetTheme}`, count);
    }
  }
  const expected = [...expectedMovements].filter(([, count]) => count > 0).sort();
  const actual = [...actualMovements].sort();
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["movement_matrix"],
      message: "movement matrix does not match reviewed keep and correction rows",
    });
  }
  const sourceReviewed = value.sources.reduce((sum, source) => sum + source.paper_count, 0);
  const sourceKept = value.sources.reduce((sum, source) => sum + source.keep_count, 0);
  const sourceCorrected = value.sources.reduce(
    (sum, source) => sum + source.correction_count,
    0,
  );
  if (
    sourceReviewed !== value.reviewed_count ||
    sourceKept !== value.keep_count ||
    sourceCorrected !== value.correction_count
  ) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["sources"],
      message: "full-theme stage counts do not match source totals",
    });
  }
}

const fullThemeReviewStageSchema = fullThemeReviewStageObjectSchema.superRefine(
  validateFullThemeReviewStage,
);
const fullThemeReviewChainSchema = z.object({
  ...fullThemeReviewStageFields,
  prior_stages: z.array(fullThemeReviewStageSchema).min(1),
  stage_index: z.number().int().min(2),
}).strict().superRefine((value, context) => {
  validateFullThemeReviewStage(value, context);
  if (value.stage_index !== value.prior_stages.length + 1) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["stage_index"],
      message: "full-theme review stage order does not match its prior-stage chain",
    });
  }
  for (const [index, source] of value.sources.entries()) {
    if (source.assignment_blob_sha256 == null) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["sources", index, "assignment_blob_sha256"],
        message: "chained full-theme review source requires an assignment binding",
      });
    }
  }
});
const fullThemeReviewLedgerSchema = z.union([
  fullThemeReviewChainSchema,
  fullThemeReviewStageSchema,
]);

const semanticBatchSchema = z.object({
  source_file: nonBlankSchema,
  sha256: sha256Schema,
  partition: z.number().int().min(0).max(7),
  paper_count: z.number().int().nonnegative(),
  partition_rule: nonBlankSchema,
}).strict();

const certificationSourceSchema = z.object({
  source_file: nonBlankSchema,
  sha256: sha256Schema,
  decision_count: z.number().int().positive(),
}).strict();

const classificationLineageSchema = z.object({
  schema_version: z.literal("classification-lineage-v1"),
  taxonomy_version: nonBlankSchema,
  classifier: nonBlankSchema,
  method: nonBlankSchema,
  assignments_sha256: sha256Schema,
  semantic_batches: z.array(semanticBatchSchema).length(8).refine(
    (rows) => rows.every((row, index) => row.partition === index),
    "semantic batch partitions must cover exactly 0 through 7",
  ),
  full_theme_review_stages: fullThemeReviewLedgerSchema,
  audit: z.object({
    sample_registry_sha256: sha256Schema,
    decision_registry_sha256: sha256Schema,
    sample_method: nonBlankSchema,
    sample_counts: z.record(z.number().int().positive().max(50)),
    certification_sources: z.array(certificationSourceSchema).min(1),
  }).strict(),
  low_confidence_review: z.object({
    queue_sha256: sha256Schema,
    decision_registry_sha256: sha256Schema,
    complete: z.boolean(),
    reviewed_count: z.number().int().nonnegative(),
    total_count: z.number().int().nonnegative(),
  }).strict(),
}).strict().superRefine((value, context) => {
  const lowReview = value.low_confidence_review;
  if (
    lowReview.reviewed_count > lowReview.total_count ||
    lowReview.complete !== (lowReview.reviewed_count === lowReview.total_count)
  ) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["low_confidence_review"],
      message: "low-confidence lineage counts do not match completion state",
    });
  }
  const certificationSources = value.audit.certification_sources;
  const certificationFiles = certificationSources.map((source) => source.source_file);
  const certificationDecisionCount = certificationSources.reduce(
    (sum, source) => sum + source.decision_count,
    0,
  );
  const auditSampleCount = Object.values(value.audit.sample_counts).reduce(
    (sum, count) => sum + count,
    0,
  );
  if (
    new Set(certificationFiles).size !== certificationFiles.length ||
    certificationDecisionCount !== auditSampleCount
  ) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["audit", "certification_sources"],
      message: "certification sources must uniquely reconcile to every audit sample",
    });
  }
  const reviewLedger = value.full_theme_review_stages;
  const reviewStages = "prior_stages" in reviewLedger
    ? [...reviewLedger.prior_stages, reviewLedger]
    : [reviewLedger];
  for (let index = 0; index + 1 < reviewStages.length; index += 1) {
    if (
      reviewStages[index].result_assignments_sha256 !==
      reviewStages[index + 1].base_assignments_sha256
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["full_theme_review_stages", "prior_stages", index],
        message: "full-theme review result chain does not bind the next stage base",
      });
    }
  }
  if (
    reviewStages[reviewStages.length - 1].result_assignments_sha256 !==
    value.assignments_sha256
  ) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      path: ["full_theme_review_stages", "result_assignments_sha256"],
      message: "full-theme review final result does not match published assignments",
    });
  }
});

const awardVerificationSchema = z.object({
  allowed_hosts: z.array(nonBlankSchema).refine((hosts) => new Set(hosts).size === hosts.length),
  evidence_host: nonBlankSchema.nullable(),
  validator: z.literal("validate_award-v1"),
});

export function configuredAwardHostPolicy(
  venue: string,
  year: number,
  track: string,
): string[] | null {
  const scopes: Record<string, string[]> = awardHostPolicy.scopes;
  return scopes[`${venue}/${year}/${track}`] ?? null;
}

function hostCoveredByPolicy(host: string, allowedHosts: string[]): boolean {
  const normalized = host.toLocaleLowerCase().replace(/\.$/, "");
  return allowedHosts.some((allowed) => {
    const policyHost = allowed.toLocaleLowerCase().replace(/\.$/, "");
    return normalized === policyHost || normalized.endsWith(`.${policyHost}`);
  });
}

export function canonicalUrlHostname(url: string): string {
  const hostname = new URL(url).hostname.toLowerCase();
  const canonical = hostname.endsWith(".") ? hostname.slice(0, -1) : hostname;
  if (canonical.endsWith(".") || canonical.split(".").some((label) => label.length === 0)) {
    throw new Error("hostname contains an empty label or more than one terminal dot");
  }
  const encodedLength = (value: string) => new TextEncoder().encode(value).byteLength;
  if (encodedLength(canonical) > 253) {
    throw new Error("hostname exceeds 253 bytes");
  }
  const std3Label = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;
  for (const label of canonical.split(".")) {
    if (encodedLength(label) > 63) {
      throw new Error("hostname label exceeds 63 bytes");
    }
    if (!std3Label.test(label)) {
      throw new Error("hostname label violates STD3 ASCII rules");
    }
  }
  return canonical;
}

const awardSchema = z.object({
  paper_id: nonBlankSchema,
  award_type: nonBlankSchema,
  status: z.enum(["verified", "not_announced", "not_verified"]),
  evidence_url: urlSchema.nullable().optional(),
  official_citation: z.string().nullable().optional(),
  canonical_identity: z.object({
    paper_id: nonBlankSchema,
    award_type: nonBlankSchema,
  }),
  route_key: z.string().regex(/^award-[0-9a-f]{64}$/),
  verification: awardVerificationSchema,
}).superRefine((award, context) => {
  if (award.canonical_identity.paper_id !== award.paper_id) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["canonical_identity", "paper_id"], message: "canonical award identity paper does not match" });
  }
  const identity = JSON.stringify([
    award.canonical_identity.paper_id,
    award.canonical_identity.award_type,
  ]);
  const expectedRoute = `award-${createHash("sha256").update(identity).digest("hex")}`;
  if (award.route_key !== expectedRoute) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["route_key"], message: "award route key does not match producer identity" });
  }
  const actualHost = award.evidence_url == null ? null : canonicalUrlHostname(award.evidence_url);
  if (actualHost !== award.verification.evidence_host) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["verification", "evidence_host"], message: "award evidence host does not match its URL" });
  }
  if (award.status === "verified") {
    if (actualHost == null || !hostCoveredByPolicy(actualHost, award.verification.allowed_hosts)) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["status"], message: "verified award evidence is outside its official host policy" });
    }
  }
});

const awardStateSchema = z.object({
  status: z.enum(["verified", "not_announced", "not_verified"]),
  evidence_url: urlSchema.nullable(),
  evidence_claim: evidenceClaimSchema.nullable(),
  verification: awardVerificationSchema,
}).superRefine((state, context) => {
  const actualHost = state.evidence_url == null ? null : canonicalUrlHostname(state.evidence_url);
  if (actualHost !== state.verification.evidence_host) {
    context.addIssue({ code: z.ZodIssueCode.custom, path: ["verification", "evidence_host"], message: "award state host does not match its URL" });
  }
  if (state.status === "verified" || state.status === "not_announced") {
    if (actualHost == null || !hostCoveredByPolicy(actualHost, state.verification.allowed_hosts)) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["status"], message: "award state requires official host evidence" });
    }
  }
  if (state.status === "not_announced") {
    if (
      state.evidence_claim == null ||
      state.evidence_claim.evidence_type !== "official_metadata" ||
      state.evidence_url == null ||
      !state.evidence_claim.source_urls.includes(state.evidence_url)
    ) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["evidence_claim"], message: "not_announced requires retained official metadata evidence" });
    }
  }
});

const resultClaimSchema = z.object({
  ...evidenceClaimFields,
  evidence_type: z.literal("paper_reported"),
  metric: nonBlankSchema,
  value: decimalSchema,
  evaluation_setting: z.string().trim().min(1, "evaluation setting is required"),
  locator: z.string().trim().min(1, "paper locator is required"),
});
const methodNodeSchema = z.object({ identifier: nonBlankSchema, label: nonBlankSchema, paper_section: nonBlankSchema });
const methodEdgeSchema = z.object({ source: nonBlankSchema, target: nonBlankSchema, data_flow_rationale: nonBlankSchema });
export const methodDiagramArtifactSchema = z.object({
  nodes: z.array(methodNodeSchema).min(1),
  edges: z.array(methodEdgeSchema),
}).superRefine((diagram, context) => {
  const nodeIds = diagram.nodes.map((node) => node.identifier);
  const nodes = new Set(nodeIds);
  if (nodes.size !== nodeIds.length) context.addIssue({ code: z.ZodIssueCode.custom, path: ["nodes"], message: "diagram nodes must be unique" });
  const pairs = new Set<string>();
  diagram.edges.forEach((edge, index) => {
    if (!nodes.has(edge.source) || !nodes.has(edge.target)) context.addIssue({ code: z.ZodIssueCode.custom, path: ["edges", index], message: "diagram edge must connect disclosed nodes" });
    const pair = `${edge.source}\0${edge.target}`;
    if (pairs.has(pair)) context.addIssue({ code: z.ZodIssueCode.custom, path: ["edges", index], message: "diagram edges must be unique" });
    pairs.add(pair);
  });
});
const interpretiveClaimSchema = evidenceClaimSchema.refine(
  (claim) => claim.evidence_type !== "official_metadata",
  "interpretive sections cannot use official metadata",
);
const transferableClaimSchema = evidenceClaimSchema.refine(
  (claim) => ["cross_paper_synthesis", "inference"].includes(claim.evidence_type),
  "transferable implications require synthesis or inference evidence",
);
export const deepReadArtifactSchema = z.object({
  paper_id: nonBlankSchema,
  research_problem: evidenceClaimSchema,
  contribution: evidenceClaimSchema,
  method_summary: evidenceClaimSchema,
  result_claims: z.array(resultClaimSchema).min(1),
  why_it_matters: z.array(interpretiveClaimSchema).min(1),
  limitations: z.array(evidenceClaimSchema).min(1),
  data_training_setup: z.array(evidenceClaimSchema).min(1),
  prior_work_differences: z.array(evidenceClaimSchema).min(1),
  reproducibility_assessment: z.array(evidenceClaimSchema).min(1),
  transferable_implications: z.array(transferableClaimSchema).min(1),
  method_diagram: methodDiagramArtifactSchema.nullable(),
});

const advanceArtifactSchema = z.object({
  advance_id: nonBlankSchema,
  title: nonBlankSchema,
  category: z.enum(["text_llms", "multimodal_models", "reasoning_agents", "data_training", "evaluation_trust"]),
  supporting_paper_ids: z.array(nonBlankSchema).min(1).refine((ids) => new Set(ids).size === ids.length),
  claims: z.array(evidenceClaimSchema).min(1),
  research_questions: z.array(nonBlankSchema).min(1).optional(),
  core_problem: evidenceClaimSchema.nullable().optional(),
  technical_change: evidenceClaimSchema.nullable().optional(),
  evidence_boundary: evidenceClaimSchema.nullable().optional(),
  implications: z.array(evidenceClaimSchema).optional(),
});
const themeDisclosureSchema = z.object({
  theme: nonBlankSchema,
  status: z.enum(["withheld", "experimental"]),
  reason: evidenceClaimSchema,
});

const emergingScoreSchema = z.object({
  score: decimalSchema,
  components: z.object({
    share_growth: decimalSchema,
    spread_growth: decimalSchema,
    novelty: decimalSchema,
  }),
  weights: z.object({
    share_growth: decimalSchema,
    spread_growth: decimalSchema,
    novelty: decimalSchema,
  }),
});

const canonicalVenueListSchema = z
  .array(nonBlankSchema)
  .refine((values) => new Set(values).size === values.length, "venues must be unique")
  .refine(
    (values) => JSON.stringify(values) === JSON.stringify([...values].sort()),
    "venues must be sorted",
  );
const nonEmptyCanonicalVenueListSchema = z
  .array(nonBlankSchema)
  .min(1)
  .refine((values) => new Set(values).size === values.length, "venues must be unique")
  .refine(
    (values) => JSON.stringify(values) === JSON.stringify([...values].sort()),
    "venues must be sorted",
  );

const crossVenueSpreadSchema = z
  .object({
    configured_venues: nonEmptyCanonicalVenueListSchema,
    present_venue_count: z.number().int().safe().nonnegative(),
    present_venue_fraction: decimalSchema,
    present_venues: canonicalVenueListSchema,
  })
  .superRefine((value, context) => {
    const configured = new Set(value.configured_venues);
    if (value.present_venue_count !== value.present_venues.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["present_venue_count"],
        message: "present venue count does not match topic-presence venues",
      });
    }
    if (value.present_venues.some((venue) => !configured.has(venue))) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["present_venues"],
        message: "present venues must belong to the configured venue population",
      });
    }
    const denominator = value.configured_venues.length;
    if (
      !Number.isSafeInteger(value.present_venue_count) ||
      value.present_venue_count < 0 ||
      denominator <= 0
    ) {
      return;
    }
    const expectedFraction = pythonDecimalRatio(value.present_venue_count, denominator);
    if (compareExactDecimals(value.present_venue_fraction, expectedFraction) !== 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["present_venue_fraction"],
        message: "present venue fraction contradicts the configured venue population",
      });
    }
  });

const metricSchema = z.union([
  decimalSchema,
  z.number().int(),
  emergingScoreSchema,
  crossVenueSpreadSchema,
]);

const formulaSchema = z.object({
  denominator: nonBlankSchema,
  formula: nonBlankSchema,
  numerator: nonBlankSchema,
  version: nonBlankSchema,
});

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value != null && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

const comparisonContractSchema = z
  .object({
    contract_id: sha256Schema,
    schema_version: nonBlankSchema,
    comparison_scope: z.object({
      denominator: z.object({
        artifact_field: nonBlankSchema,
        description: nonBlankSchema,
        unit: nonBlankSchema,
      }),
      excluded_records: nonBlankSchema,
      inclusion_statuses: z
        .array(z.enum(["complete", "partial"]))
        .min(1)
        .refine((values) => new Set(values).size === values.length, "statuses must be unique"),
      track: nonBlankSchema,
      venue: nonBlankSchema,
    }),
    metric_contract: z.object({
      cross_venue_spread: formulaSchema.extend({
        configured_venue_count: z.number().int().safe().nonnegative(),
        configured_venue_id: sha256Schema,
        configured_venues: canonicalVenueListSchema,
      }),
      emerging_score: z.object({
        formula: nonBlankSchema,
        version: nonBlankSchema,
        weights: z.object({
          novelty: decimalSchema,
          share_growth: decimalSchema,
          spread_growth: decimalSchema,
        }),
      }),
      emitted_metrics: z
        .array(nonBlankSchema)
        .refine((values) => new Set(values).size === values.length, "metrics must be unique")
        .refine(
          (values) => JSON.stringify(values) === JSON.stringify([...values].sort()),
          "metrics must be sorted",
        ),
      formula_version: nonBlankSchema,
      topic_share: formulaSchema,
    }),
  })
  .superRefine((value, context) => {
    const population = value.metric_contract.cross_venue_spread;
    if (population.configured_venue_count !== population.configured_venues.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["metric_contract", "cross_venue_spread", "configured_venue_count"],
        message: "configured venue count does not match its population",
      });
    }
    const expectedPopulationId = createHash("sha256")
      .update(canonicalJson(population.configured_venues))
      .digest("hex");
    if (population.configured_venue_id !== expectedPopulationId) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["metric_contract", "cross_venue_spread", "configured_venue_id"],
        message: "configured venue population identity does not match its canonical payload",
      });
    }
    const { contract_id: _contractId, ...identity } = value;
    const expected = createHash("sha256").update(canonicalJson(identity)).digest("hex");
    if (value.contract_id !== expected) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["contract_id"],
        message: "comparison contract identity does not match its canonical payload",
      });
    }
  });

export const overviewArtifactSchema = z
  .object({
    advances: z.array(advanceArtifactSchema),
    assignments: z.array(assignmentSchema),
    audits: z.record(themeAuditSchema),
    build_metadata: z.object({
      generated_at: z.string().datetime({ offset: true }),
      producer: z.literal("conference_overview.reports.write_release"),
      schema_version: z.literal("release-build-v1"),
    }),
    classification_review: classificationReviewSchema.optional(),
    classification_lineage: classificationLineageSchema.optional(),
    publication_context: publicationContextSchema.optional(),
    awards: z.array(awardSchema),
    award_state: awardStateSchema,
    award_deep_reads: z.array(deepReadArtifactSchema),
    comparison_contract: comparisonContractSchema,
    evidence_claims: z.array(evidenceClaimSchema),
    metrics: z.record(metricSchema),
    paper_count: z.number().int().nonnegative(),
    taxonomy_version: nonBlankSchema,
    theme_disclosures: z.array(themeDisclosureSchema),
  })
  .superRefine((value, context) => {
    const awardIdentities = value.awards.map((award) =>
      JSON.stringify([
        award.canonical_identity.paper_id,
        award.canonical_identity.award_type,
      ]));
    if (new Set(awardIdentities).size !== awardIdentities.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["awards"],
        message: "duplicate normalized award identities",
      });
    }
    const awardRoutes = value.awards.map((award) => award.route_key);
    if (new Set(awardRoutes).size !== awardRoutes.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["awards"],
        message: "duplicate award route keys",
      });
    }
    const emittedMetrics = value.comparison_contract.metric_contract.emitted_metrics;
    const actualMetrics = Object.keys(value.metrics).sort();
    if (JSON.stringify(emittedMetrics) !== JSON.stringify(actualMetrics)) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["comparison_contract", "metric_contract", "emitted_metrics"],
        message: "comparison metric contract does not match emitted metrics",
      });
    }
    if (Object.prototype.hasOwnProperty.call(value.metrics, "cross_venue_spread")) {
      const spreadResult = crossVenueSpreadSchema.safeParse(
        value.metrics.cross_venue_spread,
      );
      if (!spreadResult.success) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["metrics", "cross_venue_spread"],
          message: "cross_venue_spread must use the named cross-venue metric contract",
        });
      }
    }
    const crossVenueMetric = value.metrics.cross_venue_spread;
    const spreadContract = value.comparison_contract.metric_contract.cross_venue_spread;
    if (
      crossVenueMetric != null &&
      typeof crossVenueMetric === "object" &&
      "configured_venues" in crossVenueMetric
    ) {
      if (
        JSON.stringify(crossVenueMetric.configured_venues) !==
          JSON.stringify(spreadContract.configured_venues) ||
        crossVenueMetric.configured_venues.length !== spreadContract.configured_venue_count
      ) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["comparison_contract", "metric_contract", "cross_venue_spread"],
          message: "cross-venue metric population does not match its comparison contract",
        });
      }
    } else if (spreadContract.configured_venue_count !== 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["comparison_contract", "metric_contract", "cross_venue_spread"],
        message: "configured venue population requires an emitted cross-venue metric",
      });
    }
    const assignmentIds = value.assignments.map((assignment) => assignment.paper_id);
    const distributionAvailable =
      value.publication_context == null ||
      value.publication_context.analysis_availability.distribution;
    if (distributionAvailable && assignmentIds.length !== value.paper_count) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["assignments"],
        message: "every included paper requires exactly one assignment",
      });
    }
    if (
      value.publication_context != null &&
      !value.publication_context.analysis_availability.distribution
    ) {
      const unavailableContent =
        value.taxonomy_version !== "not-classified" ||
        value.assignments.length !== 0 ||
        Object.keys(value.audits).length !== 0 ||
        Object.keys(value.metrics).length !== 0 ||
        value.advances.length !== 0 ||
        value.awards.length !== 0 ||
        value.award_deep_reads.length !== 0 ||
        value.theme_disclosures.length !== 0 ||
        value.evidence_claims.length !== 0 ||
        value.classification_lineage != null;
      if (unavailableContent) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["publication_context"],
          message: "preliminary release contains unavailable analysis",
        });
      }
    }
    if (new Set(assignmentIds).size !== assignmentIds.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["assignments"],
        message: "duplicate assignment paper IDs",
      });
    }
    for (const [index, assignment] of value.assignments.entries()) {
      if (assignment.taxonomy_version !== value.taxonomy_version) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["assignments", index, "taxonomy_version"],
          message: "assignment taxonomy version does not match overview",
        });
      }
      if (!Object.prototype.hasOwnProperty.call(value.audits, assignment.primary_topic)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["audits", assignment.primary_topic],
          message: "missing audit for assignment primary theme",
        });
      }
    }
    const lineage = value.classification_lineage;
    if (lineage != null) {
      if (lineage.taxonomy_version !== value.taxonomy_version) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["classification_lineage", "taxonomy_version"],
          message: "classification lineage taxonomy does not match overview",
        });
      }
      const semanticPaperCount = lineage.semantic_batches.reduce(
        (sum, batch) => sum + batch.paper_count,
        0,
      );
      if (semanticPaperCount !== value.paper_count) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["classification_lineage", "semantic_batches"],
          message: "semantic batch counts do not match the published paper count",
        });
      }
      const auditCounts = Object.fromEntries(
        Object.entries(value.audits).map(([theme, audit]) => [theme, audit.sample_size]),
      );
      if (canonicalJson(lineage.audit.sample_counts) !== canonicalJson(auditCounts)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["classification_lineage", "audit", "sample_counts"],
          message: "lineage audit sample counts do not match published theme audits",
        });
      }
    }
    const lowConfidenceIds = value.assignments
      .filter((assignment) => compareExactDecimals(assignment.confidence, "0.70") < 0)
      .map((assignment) => assignment.paper_id)
      .sort();
    const classificationReview = value.classification_review;
    if (lowConfidenceIds.length > 0 && classificationReview == null) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["classification_review"],
        message: "low-confidence assignments require an exhaustive review registry",
      });
    }
    if (classificationReview != null) {
      const reviewed = classificationReview.reviewed_low_confidence_ids;
      const rejected = classificationReview.rejected_low_confidence_ids;
      const pending = classificationReview.pending_low_confidence_ids;
      const expectedPending = lowConfidenceIds.filter((paperId) => !reviewed.includes(paperId));
      const invalid =
        JSON.stringify(classificationReview.low_confidence_ids) !== JSON.stringify(lowConfidenceIds) ||
        new Set(reviewed).size !== reviewed.length ||
        reviewed.some((paperId) => !lowConfidenceIds.includes(paperId)) ||
        new Set(rejected).size !== rejected.length ||
        rejected.some((paperId) => !reviewed.includes(paperId)) ||
        JSON.stringify(pending) !== JSON.stringify(expectedPending) ||
        classificationReview.review_complete !== (expectedPending.length === 0);
      if (invalid) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["classification_review"],
          message: "low-confidence review registry is incomplete or inconsistent",
        });
      }
    }
    const disclosedThemes = new Set(value.theme_disclosures.map((item) => item.theme));
    for (const [theme, audit] of Object.entries(value.audits)) {
      const pending = new Set(classificationReview?.pending_low_confidence_ids ?? []);
      const rejected = new Set(classificationReview?.rejected_low_confidence_ids ?? []);
      const themeLowConfidenceComplete = !value.assignments.some(
        (assignment) =>
          assignment.primary_topic === theme &&
          (pending.has(assignment.paper_id) || rejected.has(assignment.paper_id)),
      );
      const passes =
        audit.sample_size > 0 &&
        compareExactDecimals(audit.observed_precision, "0.90") >= 0 &&
        compareExactDecimals(audit.wilson_lower_95, "0.80") >= 0 &&
        themeLowConfidenceComplete;
      if (!passes && !disclosedThemes.has(theme)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["audits", theme],
          message: "failed primary-theme audit must be experimental or withheld",
        });
      }
    }
  });

export const validationArtifactSchema = z
  .object({
    record_set_sha256: sha256Schema,
    discovered_count: z.number().int().nonnegative(),
    included_count: z.number().int().nonnegative(),
    excluded_count: z.number().int().nonnegative(),
    expected_included: z.number().int().nonnegative().nullable(),
    expected_count_matches: z.literal(true),
    missing_abstract_ids: z.array(z.string()),
    missing_pdf_ids: z.array(z.string()),
    missing_doi_ids: z.array(z.string()),
    duplicate_source_ids: z.array(z.string()),
    duplicate_dois: z.array(z.string()),
    definite_duplicate_pairs: z.array(stringPairSchema),
    duplicate_candidates: z.array(stringPairSchema),
    status_mismatch_ids: z.array(z.string()),
    unresolved_record_ids: z.array(z.string()),
    previous_snapshot_additions: z.array(z.string()),
    previous_snapshot_removals: z.array(z.string()),
    definite_duplicate_count: z.literal(0),
    duplicate_candidate_count: z.literal(0),
    duplicate_source_id_count: z.literal(0),
    duplicate_doi_count: z.literal(0),
    status_mismatch_count: z.literal(0),
    unresolved_record_count: z.literal(0),
    missing_abstract_count: z.number().int().nonnegative(),
    missing_pdf_count: z.number().int().nonnegative(),
    missing_doi_count: z.number().int().nonnegative(),
    snapshot_addition_count: z.number().int().nonnegative(),
    snapshot_removal_count: z.number().int().nonnegative(),
    publishable: z.literal(true),
  })
  .superRefine((value, context) => {
    const checks: Array<[number, number, string]> = [
      [value.discovered_count, value.included_count + value.excluded_count, "discovered_count"],
      [value.definite_duplicate_count, value.definite_duplicate_pairs.length, "definite_duplicate_count"],
      [value.duplicate_candidate_count, value.duplicate_candidates.length, "duplicate_candidate_count"],
      [value.duplicate_source_id_count, value.duplicate_source_ids.length, "duplicate_source_id_count"],
      [value.duplicate_doi_count, value.duplicate_dois.length, "duplicate_doi_count"],
      [value.status_mismatch_count, value.status_mismatch_ids.length, "status_mismatch_count"],
      [value.unresolved_record_count, value.unresolved_record_ids.length, "unresolved_record_count"],
      [value.missing_abstract_count, value.missing_abstract_ids.length, "missing_abstract_count"],
      [value.missing_pdf_count, value.missing_pdf_ids.length, "missing_pdf_count"],
      [value.missing_doi_count, value.missing_doi_ids.length, "missing_doi_count"],
      [value.snapshot_addition_count, value.previous_snapshot_additions.length, "snapshot_addition_count"],
      [value.snapshot_removal_count, value.previous_snapshot_removals.length, "snapshot_removal_count"],
    ];
    for (const [actual, expected, path] of checks) {
      if (actual !== expected) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: [path], message: "count does not match its diagnostic list" });
      }
    }
    if (
      value.expected_included !== null &&
      value.expected_included !== value.included_count
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["expected_included"],
        message: "expected_included does not match included_count",
      });
    }
  });

export const sourceSchema = z.object({
  name: nonBlankSchema,
  url: urlSchema,
  retrieved_at: z.string().datetime({ offset: true }),
  sha256: sha256Schema,
});

export const paperArtifactSchema = z.object({
  paper_id: nonBlankSchema,
  title: nonBlankSchema,
  normalized_title: nonBlankSchema,
  authors: z.array(nonBlankSchema),
  venue: nonBlankSchema,
  year: z.number().int(),
  track: nonBlankSchema,
  landing_url: urlSchema,
  source: sourceSchema,
  status: z.enum(["complete", "partial", "excluded", "unresolved"]),
  abstract: z.string().nullable(),
  keywords: z.array(z.string()),
  subject_areas: z.array(z.string()),
  affiliations: z.array(z.string()),
  native_metadata: z.record(z.union([z.string(), z.array(z.string())])),
  doi: z.string().nullable(),
  pdf_url: urlSchema.nullable(),
  code_url: urlSchema.nullable(),
});

export const provenanceArtifactSchema = z
  .object({
    sources: z.array(sourceSchema).min(1),
    taxonomy_version: nonBlankSchema,
    source_url: urlSchema.optional(),
    source_sha256: sha256Schema.optional(),
    source_retrieved_at: z.string().datetime({ offset: true }).optional(),
    classification_lineage: classificationLineageSchema.optional(),
    publication_context: publicationContextSchema.optional(),
  })
  .superRefine((value, context) => {
    const aliases = [value.source_url, value.source_sha256, value.source_retrieved_at];
    const anyAlias = aliases.some((alias) => alias !== undefined);
    const allAliases = aliases.every((alias) => alias !== undefined);
    if (value.sources.length === 1 && !allAliases) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["source_url"],
        message: "single-source provenance requires all source aliases",
      });
      return;
    }
    if (value.sources.length !== 1 && anyAlias) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["sources"],
        message: "source aliases require exactly one canonical source",
      });
      return;
    }
    if (value.sources.length === 1) {
      const source = value.sources[0];
      if (
        value.source_url !== source.url ||
        value.source_sha256 !== source.sha256 ||
        value.source_retrieved_at !== source.retrieved_at
      ) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["sources", 0],
          message: "single-source aliases must equal the canonical source",
        });
      }
    }
  });

export const releaseOverviewSchema = z
  .object({
    overview: overviewArtifactSchema,
    validation: validationArtifactSchema,
    provenance: provenanceArtifactSchema,
  })
  .superRefine((value, context) => {
    if (value.overview.paper_count !== value.validation.included_count) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["overview", "paper_count"],
        message: "paper_count does not match validated included_count",
      });
    }
    if (value.overview.taxonomy_version !== value.provenance.taxonomy_version) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["provenance", "taxonomy_version"],
        message: "taxonomy version does not match overview",
      });
    }
    if (
      canonicalJson(value.overview.classification_lineage ?? null) !==
      canonicalJson(value.provenance.classification_lineage ?? null)
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["provenance", "classification_lineage"],
        message: "classification lineage differs between overview and provenance",
      });
    }
    if (
      canonicalJson(value.overview.publication_context ?? null) !==
      canonicalJson(value.provenance.publication_context ?? null)
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["provenance", "publication_context"],
        message: "publication context differs between overview and provenance",
      });
    }
  });

export type ReleaseOverview = z.infer<typeof releaseOverviewSchema>;

export const fullReleaseSchema = releaseOverviewSchema
  .and(z.object({ papers: z.array(paperArtifactSchema) }))
  .superRefine((value, context) => {
    if (value.papers.length !== value.validation.included_count) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["papers"],
        message: "papers.json count does not match validated included_count",
      });
    }
    const paperIds = value.papers.map((paper) => paper.paper_id);
    if (new Set(paperIds).size !== paperIds.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["papers"],
        message: "duplicate paper IDs in papers.json",
      });
    }
    for (const [index, paper] of value.papers.entries()) {
      if (paper.status !== "complete" && paper.status !== "partial") {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["papers", index, "status"],
          message: "published papers must have an included status",
        });
      }
      const canonicalSource = value.provenance.sources.some(
        (source) =>
          source.name === paper.source.name &&
          source.url === paper.source.url &&
          source.sha256 === paper.source.sha256 &&
          source.retrieved_at === paper.source.retrieved_at,
      );
      if (!canonicalSource) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["papers", index, "source"],
          message: "paper source is outside the release provenance scope",
        });
      }
      const firstPaper = value.papers[0];
      if (
        firstPaper != null &&
        (paper.venue !== firstPaper.venue ||
          paper.year !== firstPaper.year ||
          paper.track !== firstPaper.track)
      ) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["papers", index],
          message: "papers.json mixes venue, year, or track scopes",
        });
      }
      const comparisonScope = value.overview.comparison_contract.comparison_scope;
      if (
        paper.venue !== comparisonScope.venue ||
        paper.track !== comparisonScope.track
      ) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["overview", "comparison_contract", "comparison_scope"],
          message: "comparison scope does not match papers.json venue and track",
        });
      }
    }
    const assignmentIds = new Set(
      value.overview.assignments.map((assignment) => assignment.paper_id),
    );
    const paperIdSet = new Set(paperIds);
    const missing = paperIds.filter((paperId) => !assignmentIds.has(paperId));
    const unknown = [...assignmentIds].filter((paperId) => !paperIdSet.has(paperId));
    const distributionAvailable =
      value.overview.publication_context == null ||
      value.overview.publication_context.analysis_availability.distribution;
    if (distributionAvailable && missing.length > 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["overview", "assignments"],
        message: `missing assignments for papers: ${missing.join(", ")}`,
      });
    }
    if (distributionAvailable && unknown.length > 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["overview", "assignments"],
        message: `unknown assignment paper IDs: ${unknown.join(", ")}`,
      });
    }
    const officialPolicy = value.overview.award_state.verification.allowed_hosts;
    const firstPaperForPolicy = value.papers[0];
    const expectedAwardPolicy = firstPaperForPolicy == null
      ? []
      : configuredAwardHostPolicy(
          firstPaperForPolicy.venue,
          firstPaperForPolicy.year,
          firstPaperForPolicy.track,
        );
    if (firstPaperForPolicy != null && (
      expectedAwardPolicy == null || JSON.stringify(officialPolicy) !== JSON.stringify(expectedAwardPolicy)
    )) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["overview", "award_state", "verification", "allowed_hosts"], message: "release differs from the configured award host policy" });
    }
    for (const [index, award] of value.overview.awards.entries()) {
      if (JSON.stringify(award.verification.allowed_hosts) !== JSON.stringify(officialPolicy)) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: ["overview", "awards", index, "verification"], message: "award host policy differs from the release award-state policy" });
      }
      if (!paperIdSet.has(award.paper_id)) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: ["overview", "awards", index, "paper_id"], message: "award refers to an unknown paper" });
      }
    }
    const verifiedAwardIds = new Set(
      value.overview.awards.filter((award) => award.status === "verified").map((award) => award.paper_id),
    );
    if ((verifiedAwardIds.size > 0) !== (value.overview.award_state.status === "verified")) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["overview", "award_state", "status"], message: "award state contradicts verified award records" });
    }
    const deepReadIds = value.overview.award_deep_reads.map((deepRead) => deepRead.paper_id);
    if (new Set(deepReadIds).size !== deepReadIds.length) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["overview", "award_deep_reads"], message: "duplicate award deep-read paper IDs" });
    }
    deepReadIds.forEach((paperId, index) => {
      if (!paperIdSet.has(paperId) || !verifiedAwardIds.has(paperId)) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: ["overview", "award_deep_reads", index, "paper_id"], message: "deep read requires an included, officially verified award paper" });
      }
    });
    const advanceIds = value.overview.advances.map((advance) => advance.advance_id);
    if (new Set(advanceIds).size !== advanceIds.length) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["overview", "advances"], message: "duplicate advance IDs" });
    }
    value.overview.advances.forEach((advance, index) => {
      if (advance.supporting_paper_ids.some((paperId) => !paperIdSet.has(paperId))) {
        context.addIssue({ code: z.ZodIssueCode.custom, path: ["overview", "advances", index, "supporting_paper_ids"], message: "advance refers to an unknown paper" });
      }
    });
    const disclosureThemes = value.overview.theme_disclosures.map((item) => item.theme);
    if (new Set(disclosureThemes).size !== disclosureThemes.length) {
      context.addIssue({ code: z.ZodIssueCode.custom, path: ["overview", "theme_disclosures"], message: "duplicate theme disclosures" });
    }
  });

export type FullRelease = z.infer<typeof fullReleaseSchema>;
export type DeepReadArtifact = z.infer<typeof deepReadArtifactSchema>;
export type MethodDiagramArtifact = z.infer<typeof methodDiagramArtifactSchema>;

/**
 * Validate the overview, validation, and provenance artifacts together.
 * Paper-ID membership cannot be proven at this boundary; publication loaders
 * must call parseRelease with papers.json as well.
 */
export function parseOverview(input: unknown): ReleaseOverview {
  return releaseOverviewSchema.parse(input);
}

/** Validate all JSON release artifacts, including exact paper/assignment parity. */
export function parseRelease(input: unknown): FullRelease {
  return fullReleaseSchema.parse(input);
}
