import { lstat, readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { z } from "zod";

import { awardDeepReadZhSchema, type AwardDeepReadZh } from "./content-schema";
import type { LoadedOverview } from "./data";

const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/);
const sourceRowSchema = z.object({
  paper_id: z.string().trim().min(1),
  source_pdf_sha256: sha256Schema,
});

const contentRoot = resolve(process.cwd(), "../data/content/acl/2026-long");
const authoredPath = resolve(contentRoot, "authored/award-deep-reads.zh.jsonl");
const sourcePath = resolve(contentRoot, "source-batches/award-deep-read-source.jsonl");

async function readRegularFile(path: string): Promise<Buffer> {
  const stats = await lstat(path);
  if (!stats.isFile() || stats.isSymbolicLink()) {
    throw new Error(`Award Chinese content is not a regular file: ${path}`);
  }
  return readFile(path);
}

function parseJsonLines<T>(bytes: Buffer, parse: (value: unknown) => T, label: string): T[] {
  return bytes
    .toString("utf8")
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line, index) => {
      try {
        return parse(JSON.parse(line));
      } catch (error) {
        throw new Error(`${label} contains an invalid row at line ${index + 1}`, { cause: error });
      }
    });
}

export async function loadAuthoredAwardContent(
  release: LoadedOverview,
): Promise<{ awardDeepReads: AwardDeepReadZh[] }> {
  const [authoredBytes, sourceBytes] = await Promise.all([
    readRegularFile(authoredPath),
    readRegularFile(sourcePath),
  ]);
  const awardDeepReads = parseJsonLines(
    authoredBytes,
    (value) => awardDeepReadZhSchema.parse(value),
    "Award Chinese content",
  );
  const sources = parseJsonLines(
    sourceBytes,
    (value) => sourceRowSchema.parse(value),
    "Award Chinese sources",
  );
  const sourceHashes = new Map(sources.map((source) => [source.paper_id, source.source_pdf_sha256]));
  const expectedIds = release.overview.awards
    .filter((award) => award.status === "verified")
    .map((award) => award.paper_id)
    .sort((left, right) => left.localeCompare(right));
  const actualIds = awardDeepReads.map((reading) => reading.paper_id);
  if (
    new Set(actualIds).size !== actualIds.length ||
    JSON.stringify([...actualIds].sort((left, right) => left.localeCompare(right))) !==
      JSON.stringify(expectedIds)
  ) {
    throw new Error("Award Chinese content differs from the selected release");
  }
  for (const reading of awardDeepReads) {
    if (sourceHashes.get(reading.paper_id) !== reading.source_pdf_sha256) {
      throw new Error(`Award Chinese content source differs: ${reading.paper_id}`);
    }
  }
  return { awardDeepReads };
}
