import { createHash } from "node:crypto";
import { lstat, readFile, readdir, realpath } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { isAbsolute, join, relative, sep } from "node:path";

import { z } from "zod";

import { configuredAwardHostPolicy, parseRelease, type FullRelease } from "./schema";

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

export interface LoadedOverview extends FullRelease {
  generation: string;
  papersSha256: string;
  scope: {
    venue: string;
    year: number;
    track: string;
  };
}

export interface PublishedReleaseSelector {
  venue: string;
  year: number;
  track: string;
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

async function requireSafeDirectory(path: string, label: string): Promise<string> {
  const stats = await lstat(path);
  if (stats.isSymbolicLink()) {
    throw new Error(`${label} must not be a symlink`);
  }
  if (!stats.isDirectory()) {
    throw new Error(`${label} is not a directory`);
  }
  return realpath(path);
}

function requireContained(parent: string, child: string, label: string): void {
  const relation = relative(parent, child);
  if (relation === ".." || relation.startsWith(`..${sep}`) || isAbsolute(relation)) {
    throw new Error(`${label} escapes its canonical release root`);
  }
}

export async function loadOverview(
  venue: string,
  year: number,
  releaseRoot = process.env.CONFERENCE_RELEASE_ROOT ?? defaultReleaseRoot,
  track = "long",
): Promise<LoadedOverview | null> {
  if (
    !/^[A-Z0-9-]+$/.test(venue) ||
    !Number.isInteger(year) ||
    year < 1900 ||
    year > 3000 ||
    !/^[a-z0-9-]+$/.test(track)
  ) {
    throw new Error("Invalid venue, year, or track release selector");
  }

  const release = join(releaseRoot, venue, String(year));
  let canonicalRoot: string;
  let canonicalVenue: string;
  let canonicalRelease: string;
  try {
    canonicalRoot = await requireSafeDirectory(releaseRoot, "Release root");
    canonicalVenue = await requireSafeDirectory(join(releaseRoot, venue), "Venue release directory");
    requireContained(canonicalRoot, canonicalVenue, "Venue release directory");
    canonicalRelease = await requireSafeDirectory(release, "Release directory");
    requireContained(canonicalVenue, canonicalRelease, "Release directory");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return null;
    throw error;
  }
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
  const canonicalGenerations = await requireSafeDirectory(
    join(release, "generations"),
    "Release generations directory",
  );
  requireContained(canonicalRelease, canonicalGenerations, "Release generations directory");
  const generation = join(release, ...pointer.generation.split("/"));
  const canonicalGeneration = await requireSafeDirectory(generation, "Release generation");
  requireContained(canonicalGenerations, canonicalGeneration, "Release generation");
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

  const parseJsonArtifact = (
    name: "papers.json" | "overview.json" | "validation.json" | "provenance.json",
  ) => {
    try {
      return JSON.parse(artifacts.get(name)!.toString("utf8"));
    } catch (error) {
      throw new Error(`Release artifact contains invalid JSON: ${name}`, { cause: error });
    }
  };
  const parsed = parseRelease({
    papers: parseJsonArtifact("papers.json"),
    overview: parseJsonArtifact("overview.json"),
    validation: parseJsonArtifact("validation.json"),
    provenance: parseJsonArtifact("provenance.json"),
  });
  const expectedAwardPolicy = configuredAwardHostPolicy(venue, year, track);
  if (
    expectedAwardPolicy == null ||
    JSON.stringify(parsed.overview.award_state.verification.allowed_hosts) !==
      JSON.stringify(expectedAwardPolicy)
  ) {
    throw new Error("Release differs from the configured award host policy");
  }
  const mismatchedPaper = parsed.papers.find(
    (paper) => paper.venue !== venue || paper.year !== year || paper.track !== track,
  );
  if (mismatchedPaper != null) {
    throw new Error(
      `Release scope mismatch for ${mismatchedPaper.paper_id}: expected ${venue}/${year}/${track}`,
    );
  }
  const comparisonScope = parsed.overview.comparison_contract.comparison_scope;
  if (comparisonScope.venue !== venue || comparisonScope.track !== track) {
    throw new Error(
      `Comparison contract scope mismatch: expected ${venue}/${track}`,
    );
  }
  return {
    ...parsed,
    generation: pointer.generation,
    papersSha256: pointer.artifact_sha256["papers.json"],
    scope: { venue, year, track },
  };
}

export async function loadPublishedOverviews(
  releaseRoot: string,
  selectors: PublishedReleaseSelector[],
): Promise<LoadedOverview[]> {
  const ordered = [...selectors].sort(
    (left, right) =>
      left.venue.localeCompare(right.venue) ||
      left.year - right.year ||
      left.track.localeCompare(right.track),
  );
  const releases = await Promise.all(
    ordered.map(({ venue, year, track }) =>
      loadOverview(venue, year, releaseRoot, track)
    ),
  );
  return releases.filter(
    (release): release is LoadedOverview => release != null,
  );
}
