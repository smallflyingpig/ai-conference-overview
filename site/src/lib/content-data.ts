import { createHash } from "node:crypto";
import { lstat, readFile, readdir, realpath } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { isAbsolute, join, relative, sep } from "node:path";

import {
  awardDeepReadZhSchema,
  contentManifestSchema,
  contentPointerSchema,
  paperSummaryZhSchema,
  type AwardDeepReadZh,
  type ContentManifest,
  type PaperSummaryZh,
} from "./content-schema";
import type { LoadedOverview } from "./data";

const artifactNames = [
  "paper-summaries.zh.jsonl",
  "award-deep-reads.zh.jsonl",
  "content-manifest.json",
] as const;

const defaultContentRoot = fileURLToPath(
  new URL("../../../data/content", import.meta.url),
);

export interface LoadedChineseContent {
  generation: string;
  manifest: ContentManifest;
  paperSummaries: PaperSummaryZh[];
  awardDeepReads: AwardDeepReadZh[];
}

async function readRegularFile(path: string): Promise<Buffer> {
  const stats = await lstat(path);
  if (!stats.isFile() || stats.isSymbolicLink()) {
    throw new Error(`Chinese content artifact is not a regular file: ${path}`);
  }
  return readFile(path);
}

async function requireSafeDirectory(path: string, label: string): Promise<string> {
  const stats = await lstat(path);
  if (stats.isSymbolicLink() || !stats.isDirectory()) {
    throw new Error(`${label} is not a safe directory`);
  }
  return realpath(path);
}

function requireContained(parent: string, child: string, label: string): void {
  const relation = relative(parent, child);
  if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
    throw new Error(`${label} escapes its canonical content root`);
  }
}

function sha256(bytes: Buffer | string): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function parseJsonLines<T>(
  bytes: Buffer,
  parse: (value: unknown) => T,
  label: string,
): T[] {
  return bytes
    .toString("utf8")
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line, index) => {
      try {
        return parse(JSON.parse(line));
      } catch (error) {
        throw new Error(`${label} contains an invalid row at line ${index + 1}`, {
          cause: error,
        });
      }
    });
}

function requireUniqueSortedIds(values: Array<{ paper_id: string }>, label: string): Set<string> {
  const ids = values.map((value) => value.paper_id);
  if (new Set(ids).size !== ids.length) throw new Error(`${label} contains duplicate paper IDs`);
  const sorted = [...ids].sort((left, right) => left.localeCompare(right));
  if (JSON.stringify(ids) !== JSON.stringify(sorted)) {
    throw new Error(`${label} paper IDs are not canonically sorted`);
  }
  return new Set(ids);
}

function equalSets(left: Set<string>, right: Set<string>): boolean {
  return left.size === right.size && [...left].every((value) => right.has(value));
}

function validateReleaseBindings(
  release: LoadedOverview,
  summaries: PaperSummaryZh[],
  awardDeepReads: AwardDeepReadZh[],
): void {
  const paperById = new Map(release.papers.map((paper) => [paper.paper_id, paper]));
  const awardIds = new Set(
    release.overview.awards
      .filter((award) => award.status === "verified")
      .map((award) => award.paper_id),
  );
  const expectedSummaryIds = new Set(
    release.papers
      .map((paper) => paper.paper_id)
      .filter((paperId) => !awardIds.has(paperId)),
  );
  const summaryIds = requireUniqueSortedIds(summaries, "Chinese summaries");
  const deepReadIds = requireUniqueSortedIds(awardDeepReads, "Chinese award deep reads");
  if (!equalSets(summaryIds, expectedSummaryIds) || !equalSets(deepReadIds, awardIds)) {
    throw new Error("Chinese content paper ID coverage differs from the selected release");
  }
  const routeKeys = new Set<string>();
  for (const summary of summaries) {
    const paper = paperById.get(summary.paper_id);
    if (paper == null) throw new Error(`Unknown Chinese summary paper: ${summary.paper_id}`);
    const expectedRoute = `paper-${sha256(summary.paper_id)}`;
    if (summary.route_key !== expectedRoute || routeKeys.has(summary.route_key)) {
      throw new Error(`Chinese summary route key is invalid: ${summary.paper_id}`);
    }
    routeKeys.add(summary.route_key);
    if (
      summary.source_title !== paper.title ||
      summary.venue !== paper.venue ||
      summary.year !== paper.year ||
      summary.track !== paper.track
    ) {
      throw new Error(`Chinese summary scope differs from release: ${summary.paper_id}`);
    }
    if (summary.content_method === "title-abstract-grounded-summary-v1") {
      const normalizedAbstract = paper.abstract?.trim().replace(/\s+/g, " ");
      if (normalizedAbstract == null || summary.source_abstract_sha256 !== sha256(normalizedAbstract)) {
        throw new Error(`Chinese summary abstract hash mismatch: ${summary.paper_id}`);
      }
    }
  }
}

export async function loadChineseContent(
  release: LoadedOverview,
  contentRoot = process.env.CONFERENCE_CONTENT_ROOT ?? defaultContentRoot,
): Promise<LoadedChineseContent | null> {
  const content = join(
    contentRoot,
    release.scope.venue.toLocaleLowerCase(),
    `${release.scope.year}-${release.scope.track}`,
  );
  let canonicalRoot: string;
  let canonicalVenue: string;
  let canonicalContent: string;
  try {
    canonicalRoot = await requireSafeDirectory(contentRoot, "Chinese content root");
    canonicalVenue = await requireSafeDirectory(
      join(contentRoot, release.scope.venue.toLocaleLowerCase()),
      "Chinese content venue directory",
    );
    requireContained(canonicalRoot, canonicalVenue, "Chinese content venue directory");
    canonicalContent = await requireSafeDirectory(content, "Chinese content directory");
    requireContained(canonicalVenue, canonicalContent, "Chinese content directory");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
  let pointerBytes: Buffer;
  try {
    pointerBytes = await readRegularFile(join(content, "current.json"));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
  const pointer = contentPointerSchema.parse(JSON.parse(pointerBytes.toString("utf8")));
  if (
    pointer.release_generation !== release.generation ||
    pointer.papers_sha256 !== release.papersSha256
  ) {
    throw new Error("Chinese content differs from the selected release");
  }
  const generations = await requireSafeDirectory(
    join(content, "generations"),
    "Chinese content generations directory",
  );
  requireContained(canonicalContent, generations, "Chinese content generations directory");
  const generation = join(content, ...pointer.generation.split("/"));
  const canonicalGeneration = await requireSafeDirectory(
    generation,
    "Chinese content generation",
  );
  requireContained(generations, canonicalGeneration, "Chinese content generation");
  const entries = (await readdir(generation)).sort();
  if (JSON.stringify(entries) !== JSON.stringify([...artifactNames].sort())) {
    throw new Error("Chinese content generation has an incomplete artifact set");
  }
  const artifacts = new Map<string, Buffer>();
  for (const name of artifactNames) {
    const bytes = await readRegularFile(join(generation, name));
    if (sha256(bytes) !== pointer.artifact_sha256[name]) {
      throw new Error(`Chinese content artifact hash mismatch: ${name}`);
    }
    artifacts.set(name, bytes);
  }
  const manifest = contentManifestSchema.parse(
    JSON.parse(artifacts.get("content-manifest.json")!.toString("utf8")),
  );
  if (
    manifest.release_generation !== pointer.release_generation ||
    manifest.papers_sha256 !== pointer.papers_sha256 ||
    manifest.artifact_sha256["paper-summaries.zh.jsonl"] !==
      sha256(artifacts.get("paper-summaries.zh.jsonl")!) ||
    manifest.artifact_sha256["award-deep-reads.zh.jsonl"] !==
      sha256(artifacts.get("award-deep-reads.zh.jsonl")!)
  ) {
    throw new Error("Chinese content manifest differs from pointer or bytes");
  }
  const paperSummaries = parseJsonLines(
    artifacts.get("paper-summaries.zh.jsonl")!,
    (value) => paperSummaryZhSchema.parse(value),
    "Chinese summaries",
  );
  const awardDeepReads = parseJsonLines(
    artifacts.get("award-deep-reads.zh.jsonl")!,
    (value) => awardDeepReadZhSchema.parse(value),
    "Chinese award deep reads",
  );
  if (
    manifest.ordinary_count !== paperSummaries.length ||
    manifest.award_count !== awardDeepReads.length ||
    manifest.total_count !== release.papers.length
  ) {
    throw new Error("Chinese content counts differ from records or release");
  }
  validateReleaseBindings(release, paperSummaries, awardDeepReads);
  return {
    generation: pointer.generation,
    manifest,
    paperSummaries,
    awardDeepReads,
  };
}
