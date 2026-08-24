import { createHash } from "node:crypto";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { loadOverview } from "../src/lib/data";
import { parseOverview } from "../src/lib/schema";

const overview = {
  assignments: [],
  audits: {},
  awards: [],
  evidence_claims: [],
  metrics: {},
  paper_count: 0,
  taxonomy_version: "2026-08-24-v1",
};

const validation = {
  record_set_sha256: "c".repeat(64),
  discovered_count: 0,
  included_count: 0,
  excluded_count: 0,
  expected_included: 0,
  expected_count_matches: true,
  definite_duplicate_pairs: [],
  duplicate_candidates: [],
  duplicate_source_ids: [],
  duplicate_dois: [],
  status_mismatch_ids: [],
  unresolved_record_ids: [],
  missing_abstract_ids: [],
  missing_pdf_ids: [],
  missing_doi_ids: [],
  previous_snapshot_additions: [],
  previous_snapshot_removals: [],
  definite_duplicate_count: 0,
  duplicate_candidate_count: 0,
  duplicate_source_id_count: 0,
  duplicate_doi_count: 0,
  status_mismatch_count: 0,
  unresolved_record_count: 0,
  missing_abstract_count: 0,
  missing_pdf_count: 0,
  missing_doi_count: 0,
  snapshot_addition_count: 0,
  snapshot_removal_count: 0,
  publishable: true,
};

const provenance = {
  sources: [
    {
      name: "ACL Anthology",
      url: "https://aclanthology.org/volumes/2026.acl-long/",
      retrieved_at: "2026-08-24T01:02:03Z",
      sha256: "a".repeat(64),
    },
  ],
  taxonomy_version: "2026-08-24-v1",
};

const artifactNames = [
  "papers.json",
  "papers.csv",
  "overview.json",
  "overview.md",
  "validation.json",
  "provenance.json",
] as const;

describe("parseOverview", () => {
  it("rejects a release without provenance", () => {
    expect(() => parseOverview({ overview, validation })).toThrow(/provenance/i);
  });

  it("rejects a release whose validation is not publishable", () => {
    expect(() =>
      parseOverview({
        overview,
        validation: { ...validation, publishable: false },
        provenance,
      }),
    ).toThrow(/publishable/i);
  });

  it("rejects incomplete provenance before rendering", () => {
    expect(() =>
      parseOverview({
        overview,
        validation,
        provenance: {
          ...provenance,
          sources: [{ ...provenance.sources[0], sha256: "short" }],
        },
      }),
    ).toThrow(/sha256/i);
  });
});

describe("loadOverview", () => {
  it("returns null when no release pointer has been published", async () => {
    const root = await mkdtemp(join(tmpdir(), "conference-site-empty-"));
    await expect(loadOverview("ACL", 2026, root)).resolves.toBeNull();
  });

  it("loads only the hashed immutable generation selected by current.json", async () => {
    const root = await mkdtemp(join(tmpdir(), "conference-site-release-"));
    const release = join(root, "ACL", "2026");
    const generationName = "b".repeat(64);
    const generation = join(release, "generations", generationName);
    await mkdir(generation, { recursive: true });

    const files: Record<(typeof artifactNames)[number], string> = {
      "papers.json": "[]\n",
      "papers.csv": "paper_id\n",
      "overview.json": `${JSON.stringify(overview)}\n`,
      "overview.md": "# Conference overview\n",
      "validation.json": `${JSON.stringify(validation)}\n`,
      "provenance.json": `${JSON.stringify(provenance)}\n`,
    };
    for (const [name, contents] of Object.entries(files)) {
      await writeFile(join(generation, name), contents);
    }
    await writeFile(
      join(release, "overview.json"),
      JSON.stringify({ ...overview, paper_count: 999 }),
    );
    await writeFile(
      join(release, "current.json"),
      JSON.stringify({
        generation: `generations/${generationName}`,
        artifact_sha256: Object.fromEntries(
          Object.entries(files).map(([name, contents]) => [
            name,
            createHash("sha256").update(contents).digest("hex"),
          ]),
        ),
      }),
    );

    const loaded = await loadOverview("ACL", 2026, root);
    expect(loaded?.overview.paper_count).toBe(0);
    expect(loaded?.generation).toBe(`generations/${generationName}`);
  });
});
