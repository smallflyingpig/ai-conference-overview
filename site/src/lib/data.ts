import { createHash } from "node:crypto";
import { lstat, readFile, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

import { z } from "zod";

import { parseOverview, type ReleaseOverview } from "./schema";

const artifactNames = [
  "papers.json",
  "papers.csv",
  "overview.json",
  "overview.md",
  "validation.json",
  "provenance.json",
] as const;

const sha256Schema = z.string().regex(/^[0-9a-f]{64}$/i);
const pointerSchema = z.object({
  generation: z.string().regex(/^generations\/[0-9a-f]{64}$/i),
  artifact_sha256: z.object(
    Object.fromEntries(artifactNames.map((name) => [name, sha256Schema])) as Record<
      (typeof artifactNames)[number],
      typeof sha256Schema
    >,
  ),
});

export interface LoadedOverview extends ReleaseOverview {
  generation: string;
}

const defaultReleaseRoot = fileURLToPath(
  new URL("../../../data/releases", import.meta.url),
);

async function readRegularFile(path: string): Promise<Buffer> {
  const stats = await lstat(path);
  if (!stats.isFile() || stats.isSymbolicLink()) {
    throw new Error(`Release artifact is not a regular file: ${path}`);
  }
  return readFile(path);
}

export async function loadOverview(
  venue: string,
  year: number,
  releaseRoot = defaultReleaseRoot,
): Promise<LoadedOverview | null> {
  if (!/^[A-Z0-9-]+$/.test(venue) || !Number.isInteger(year) || year < 1900 || year > 3000) {
    throw new Error("Invalid venue or year release selector");
  }

  const release = join(releaseRoot, venue, String(year));
  let pointerBytes: Buffer;
  try {
    pointerBytes = await readRegularFile(join(release, "current.json"));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }

  let rawPointer: unknown;
  try {
    rawPointer = JSON.parse(pointerBytes.toString("utf8"));
  } catch (error) {
    throw new Error("Release current pointer contains invalid JSON", { cause: error });
  }
  const pointer = pointerSchema.parse(rawPointer);
  const generation = join(release, ...pointer.generation.split("/"));
  const generationStats = await lstat(generation);
  if (!generationStats.isDirectory() || generationStats.isSymbolicLink()) {
    throw new Error("Release generation is not a regular directory");
  }
  const entries = (await readdir(generation)).sort();
  const expectedEntries = [...artifactNames].sort();
  if (JSON.stringify(entries) !== JSON.stringify(expectedEntries)) {
    throw new Error("Release generation has an incomplete artifact set");
  }

  const artifacts = new Map<string, Buffer>();
  for (const name of artifactNames) {
    const bytes = await readRegularFile(join(generation, name));
    const actualHash = createHash("sha256").update(bytes).digest("hex");
    if (actualHash !== pointer.artifact_sha256[name]) {
      throw new Error(`Release artifact hash mismatch: ${name}`);
    }
    artifacts.set(name, bytes);
  }

  const parseJsonArtifact = (name: "overview.json" | "validation.json" | "provenance.json") => {
    try {
      return JSON.parse(artifacts.get(name)!.toString("utf8"));
    } catch (error) {
      throw new Error(`Release artifact contains invalid JSON: ${name}`, { cause: error });
    }
  };
  const parsed = parseOverview({
    overview: parseJsonArtifact("overview.json"),
    validation: parseJsonArtifact("validation.json"),
    provenance: parseJsonArtifact("provenance.json"),
  });
  return { ...parsed, generation: pointer.generation };
}
