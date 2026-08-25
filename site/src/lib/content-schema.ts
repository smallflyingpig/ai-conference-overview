import { z } from "zod";

const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);
const generationSchema = z.string().regex(/^generations\/[0-9a-f]{64}$/);
const nonBlankSchema = z.string().trim().min(1);
const cjkPattern = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g;

export const paperSummaryZhSchema = z
  .object({
    schema_version: z.literal("paper-summary-zh-v1"),
    paper_id: nonBlankSchema,
    route_key: z.string().regex(/^paper-[0-9a-f]{64}$/),
    venue: nonBlankSchema,
    year: z.number().int(),
    track: nonBlankSchema,
    source_title: nonBlankSchema,
    source_abstract_sha256: sha256Schema.nullable(),
    source_pdf_sha256: sha256Schema.nullable(),
    one_sentence: nonBlankSchema,
    summary_zh: nonBlankSchema,
    research_problem: nonBlankSchema,
    core_method: nonBlankSchema,
    main_findings: nonBlankSchema,
    scope_and_limitations: nonBlankSchema,
    content_method: z.enum([
      "title-abstract-grounded-summary-v1",
      "official-pdf-grounded-summary-v1",
    ]),
  })
  .strict()
  .superRefine((value, context) => {
    const chineseCount = value.summary_zh.match(cjkPattern)?.length ?? 0;
    if (chineseCount < 150 || chineseCount > 250) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["summary_zh"],
        message: "summary_zh must contain 150 to 250 Chinese characters",
      });
    }
    const abstractBound = value.source_abstract_sha256 != null;
    const pdfBound = value.source_pdf_sha256 != null;
    if (abstractBound === pdfBound) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["source_abstract_sha256"],
        message: "summary requires exactly one source binding",
      });
    }
    if (
      (value.content_method === "title-abstract-grounded-summary-v1" && !abstractBound) ||
      (value.content_method === "official-pdf-grounded-summary-v1" && !pdfBound)
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["content_method"],
        message: "content method must match its source binding",
      });
    }
  });

const awardQuickReadZhSchema = z
  .object({
    research_problem: nonBlankSchema,
    core_method: nonBlankSchema,
    main_finding: nonBlankSchema,
  })
  .strict();

export const awardDeepReadZhSchema = z
  .object({
    schema_version: z.literal("award-deep-read-zh-v1"),
    paper_id: nonBlankSchema,
    source_pdf_sha256: sha256Schema,
    quick_read: awardQuickReadZhSchema,
    abstract_zh: nonBlankSchema,
    background: z.array(nonBlankSchema).min(1),
    method_walkthrough: z.array(nonBlankSchema).min(1),
    why_it_matters: z.array(nonBlankSchema).min(1),
    limitations: z.array(nonBlankSchema).min(1),
    research_implications: z.array(nonBlankSchema).min(1),
  })
  .strict();

export const contentManifestSchema = z
  .object({
    schema_version: z.literal("chinese-content-manifest-v1"),
    release_generation: generationSchema,
    papers_sha256: sha256Schema,
    generated_at: z.string().datetime({ offset: true }),
    ordinary_count: z.number().int().nonnegative(),
    award_count: z.number().int().nonnegative(),
    total_count: z.number().int().nonnegative(),
    artifact_sha256: z
      .object({
        "paper-summaries.zh.jsonl": sha256Schema,
        "award-deep-reads.zh.jsonl": sha256Schema,
      })
      .strict(),
  })
  .strict()
  .refine(
    (value) => value.total_count === value.ordinary_count + value.award_count,
    { message: "content manifest counts contradict one another" },
  );

export const contentPointerSchema = z
  .object({
    generation: generationSchema,
    release_generation: generationSchema,
    papers_sha256: sha256Schema,
    artifact_sha256: z
      .object({
        "paper-summaries.zh.jsonl": sha256Schema,
        "award-deep-reads.zh.jsonl": sha256Schema,
        "content-manifest.json": sha256Schema,
      })
      .strict(),
  })
  .strict();

export type PaperSummaryZh = z.infer<typeof paperSummaryZhSchema>;
export type AwardDeepReadZh = z.infer<typeof awardDeepReadZhSchema>;
export type ContentManifest = z.infer<typeof contentManifestSchema>;
