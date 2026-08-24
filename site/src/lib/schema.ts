import { z } from "zod";

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

export const evidenceTypeSchema = z.enum([
  "official_metadata",
  "paper_reported",
  "cross_paper_synthesis",
  "inference",
]);

export const evidenceClaimSchema = z.object({
  claim: nonBlankSchema,
  evidence_type: evidenceTypeSchema,
  source_urls: z.array(urlSchema).min(1),
  locator: nonBlankSchema.nullable().optional(),
});

const assignmentSchema = z.object({
  confidence: decimalSchema,
  paper_id: nonBlankSchema,
  primary_topic: nonBlankSchema,
  rationale: nonBlankSchema,
  secondary_topics: z.array(nonBlankSchema),
  taxonomy_version: nonBlankSchema,
});

const themeAuditSchema = z.object({
  correct_count: z.number().int().nonnegative(),
  observed_precision: decimalSchema,
  sample_size: z.number().int().positive().max(50),
  thresholds: z.object({
    minimum_observed_precision: decimalSchema,
    minimum_wilson_lower_95: decimalSchema,
  }),
  wilson_lower_95: decimalSchema,
});

const awardSchema = z.object({
  paper_id: nonBlankSchema,
  award_type: nonBlankSchema,
  status: z.enum(["verified", "not_announced", "not_verified"]),
  evidence_url: urlSchema.nullable().optional(),
  official_citation: z.string().nullable().optional(),
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

const crossVenueSpreadSchema = z.object({
  present_venue_count: z.number().int().nonnegative(),
  present_venue_fraction: decimalSchema,
});

const metricSchema = z.union([
  decimalSchema,
  z.number().int(),
  emergingScoreSchema,
  crossVenueSpreadSchema,
]);

export const overviewArtifactSchema = z.object({
  assignments: z.array(assignmentSchema),
  audits: z.record(themeAuditSchema),
  awards: z.array(awardSchema),
  evidence_claims: z.array(evidenceClaimSchema),
  metrics: z.record(metricSchema),
  paper_count: z.number().int().nonnegative(),
  taxonomy_version: nonBlankSchema,
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

export const provenanceArtifactSchema = z
  .object({
    sources: z.array(sourceSchema).min(1),
    taxonomy_version: nonBlankSchema,
    source_url: urlSchema.optional(),
    source_sha256: sha256Schema.optional(),
    source_retrieved_at: z.string().datetime({ offset: true }).optional(),
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
  });

export type ReleaseOverview = z.infer<typeof releaseOverviewSchema>;

export function parseOverview(input: unknown): ReleaseOverview {
  return releaseOverviewSchema.parse(input);
}
