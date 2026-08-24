import { createHash } from "node:crypto";

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

export const evidenceClaimSchema = z
  .object({
    claim: nonBlankSchema,
    evidence_type: evidenceTypeSchema,
    source_urls: z.array(urlSchema).min(1),
    locator: nonBlankSchema.nullable().optional(),
  })
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
    sample_size: z.number().int().positive().max(50),
    thresholds: z.object({
      minimum_observed_precision: z.literal("0.90"),
      minimum_wilson_lower_95: z.literal("0.80"),
    }),
    wilson_lower_95: decimalSchema,
  })
  .superRefine((value, context) => {
    if (compareExactDecimals(value.observed_precision, "0.90") < 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["observed_precision"],
        message: "audit observed precision is below 0.90",
      });
    }
    if (compareExactDecimals(value.wilson_lower_95, "0.80") < 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["wilson_lower_95"],
        message: "audit Wilson lower bound is below 0.80",
      });
    }
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
    assignments: z.array(assignmentSchema),
    audits: z.record(themeAuditSchema),
    awards: z.array(awardSchema),
    comparison_contract: comparisonContractSchema,
    evidence_claims: z.array(evidenceClaimSchema),
    metrics: z.record(metricSchema),
    paper_count: z.number().int().nonnegative(),
    taxonomy_version: nonBlankSchema,
  })
  .superRefine((value, context) => {
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
    if (assignmentIds.length !== value.paper_count) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["assignments"],
        message: "every included paper requires exactly one assignment",
      });
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
    if (missing.length > 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["overview", "assignments"],
        message: `missing assignments for papers: ${missing.join(", ")}`,
      });
    }
    if (unknown.length > 0) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["overview", "assignments"],
        message: `unknown assignment paper IDs: ${unknown.join(", ")}`,
      });
    }
  });

export type FullRelease = z.infer<typeof fullReleaseSchema>;

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
