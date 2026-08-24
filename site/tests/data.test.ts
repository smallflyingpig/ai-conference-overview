import { createHash } from "node:crypto";
import { cp, mkdir, mkdtemp, readFile, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

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
  source_url: "https://aclanthology.org/volumes/2026.acl-long/",
  source_sha256: "a".repeat(64),
  source_retrieved_at: "2026-08-24T01:02:03Z",
};

const artifactNames = [
  "papers.json",
  "papers.csv",
  "overview.json",
  "overview.md",
  "validation.json",
  "provenance.json",
] as const;

const task9FixtureRoot = fileURLToPath(
  new URL("./fixtures/task9-release", import.meta.url),
);

async function mutatedTask9Release(
  mutate: (overview: Record<string, any>) => void,
): Promise<string> {
  const temporary = await mkdtemp(join(tmpdir(), "conference-task9-release-"));
  const root = join(temporary, "releases");
  await cp(task9FixtureRoot, root, { recursive: true });
  const release = join(root, "ACL", "2026");
  const pointerPath = join(release, "current.json");
  const pointer = JSON.parse(await readFile(pointerPath, "utf8"));
  const overviewPath = join(release, pointer.generation, "overview.json");
  const changedOverview = JSON.parse(await readFile(overviewPath, "utf8"));
  mutate(changedOverview);
  const contents = `${JSON.stringify(changedOverview, null, 2)}\n`;
  await writeFile(overviewPath, contents);
  pointer.artifact_sha256["overview.json"] = createHash("sha256")
    .update(contents)
    .digest("hex");
  await writeFile(pointerPath, `${JSON.stringify(pointer, null, 2)}\n`);
  return root;
}

async function mutatedTask9Papers(
  mutate: (papers: Array<Record<string, any>>) => void,
): Promise<string> {
  const temporary = await mkdtemp(join(tmpdir(), "conference-task9-scope-"));
  const root = join(temporary, "releases");
  await cp(task9FixtureRoot, root, { recursive: true });
  const release = join(root, "ACL", "2026");
  const pointerPath = join(release, "current.json");
  const pointer = JSON.parse(await readFile(pointerPath, "utf8"));
  const papersPath = join(release, pointer.generation, "papers.json");
  const papers = JSON.parse(await readFile(papersPath, "utf8"));
  mutate(papers);
  const contents = `${JSON.stringify(papers, null, 2)}\n`;
  await writeFile(papersPath, contents);
  pointer.artifact_sha256["papers.json"] = createHash("sha256")
    .update(contents)
    .digest("hex");
  await writeFile(pointerPath, `${JSON.stringify(pointer, null, 2)}\n`);
  return root;
}

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

  it.each([
    ["duplicate source count", { duplicate_source_ids: ["paper-a"] }],
    ["expected included count", { expected_included: 999 }],
  ])("rejects validation incoherence in %s", (_name, change) => {
    expect(() =>
      parseOverview({
        overview,
        validation: { ...validation, ...change },
        provenance,
      }),
    ).toThrow(/count|diagnostic|expected/i);
  });

  it("rejects a URL scheme that Python HttpUrl would reject", () => {
    expect(() =>
      parseOverview({
        overview,
        validation,
        provenance: {
          ...provenance,
          sources: [{ ...provenance.sources[0], url: "ftp://example.com/source" }],
          source_url: "ftp://example.com/source",
        },
      }),
    ).toThrow(/url/i);
  });

  it("rejects single-source aliases that disagree with the canonical source", () => {
    expect(() =>
      parseOverview({
        overview,
        validation,
        provenance: { ...provenance, source_sha256: "d".repeat(64) },
      }),
    ).toThrow(/alias|source/i);
  });

  it("accepts finite Decimal serialization in scientific notation", () => {
    expect(() =>
      parseOverview({
        overview: { ...overview, metrics: { tiny_share: "1E-7" } },
        validation,
        provenance,
      }),
    ).not.toThrow();
  });
});

describe("loadOverview", () => {
  it("accepts a release generated by Python Task 9 write_release", async () => {
    const loaded = await loadOverview("ACL", 2026, task9FixtureRoot);

    expect(loaded?.overview.paper_count).toBe(2);
    expect(loaded?.papers.map((paper) => paper.paper_id)).toEqual([
      "paper-a",
      "paper-z",
    ]);
  });

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

  it("rejects an external release tree reached through a symlinked ancestor", async () => {
    const root = await mkdtemp(join(tmpdir(), "conference-site-symlink-root-"));
    const external = await mkdtemp(join(tmpdir(), "conference-site-symlink-external-"));
    const release = join(external, "release");
    const generationName = "e".repeat(64);
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
    await mkdir(join(root, "ACL"), { recursive: true });
    await symlink(release, join(root, "ACL", "2026"), "dir");

    await expect(loadOverview("ACL", 2026, root)).rejects.toThrow(/symlink|escape/i);
  });

  it.each([
    ["missing assignments", (value: any) => value.assignments.pop(), /assignment/i],
    [
      "assignment taxonomy mismatch",
      (value: any) => { value.assignments[0].taxonomy_version = "wrong-version"; },
      /taxonomy/i,
    ],
    ["missing primary-theme audit", (value: any) => { value.audits = {}; }, /audit/i],
    [
      "observed precision below gate",
      (value: any) => { value.audits["Foundation Models"].observed_precision = "0.89"; },
      /precision|audit/i,
    ],
    [
      "audit below Wilson gate",
      (value: any) => { value.audits["Foundation Models"].wilson_lower_95 = "0.79"; },
      /wilson|audit/i,
    ],
    [
      "qualitative paper-reported claim without locator",
      (value: any) => {
        value.evidence_claims = [{
          claim: "The paper reports a qualitative improvement.",
          evidence_type: "paper_reported",
          source_urls: ["https://aclanthology.org/paper-a.pdf"],
          locator: null,
        }];
      },
      /locator/i,
    ],
    [
      "numeric inference claim without locator",
      (value: any) => {
        value.evidence_claims = [{
          claim: "The inferred improvement is 12%.",
          evidence_type: "inference",
          source_urls: ["https://aclanthology.org/paper-a.pdf"],
          locator: null,
        }];
      },
      /locator/i,
    ],
    [
      "unknown assignment paper ID",
      (value: any) => { value.assignments[0].paper_id = "paper-ghost"; },
      /unknown|assignment/i,
    ],
    [
      "duplicate assignment paper ID",
      (value: any) => { value.assignments[1].paper_id = value.assignments[0].paper_id; },
      /duplicate|assignment/i,
    ],
  ])("rejects a coherently hashed Task 9 release with %s", async (_name, mutate, error) => {
    const root = await mutatedTask9Release(mutate);
    await expect(loadOverview("ACL", 2026, root)).rejects.toThrow(error);
  });

  it.each(["toString", "__proto__"])(
    "does not treat prototype property %s as a theme audit",
    async (prototypeTopic) => {
      const root = await mutatedTask9Release((value) => {
        value.assignments.forEach((assignment: any) => {
          assignment.primary_topic = prototypeTopic;
        });
        value.audits = {};
      });

      await expect(loadOverview("ACL", 2026, root)).rejects.toThrow(/audit/i);
    },
  );

  it.each([
    ["observed precision", "observed_precision", "0.899999999999999999999999999999999999"],
    ["Wilson lower bound", "wilson_lower_95", "0.799999999999999999999999999999999999"],
  ])("compares %s below its gate without Number rounding", async (_name, field, decimal) => {
    const root = await mutatedTask9Release((value) => {
      value.audits["Foundation Models"][field] = decimal;
    });

    await expect(loadOverview("ACL", 2026, root)).rejects.toThrow(/precision|wilson|audit/i);
  });

  it("accepts exact Decimal audit boundaries in scientific notation", async () => {
    const root = await mutatedTask9Release((value) => {
      value.audits["Foundation Models"].observed_precision = "9E-1";
      value.audits["Foundation Models"].wilson_lower_95 = "8E-1";
    });

    await expect(loadOverview("ACL", 2026, root)).resolves.toMatchObject({
      overview: { paper_count: 2 },
    });
  });

  it("rejects a coherently rehashed ACL 2026 long release containing EMNLP 2025 short papers", async () => {
    const root = await mutatedTask9Papers((papers) => {
      papers.forEach((paper) => {
        paper.venue = "EMNLP";
        paper.year = 2025;
        paper.track = "short";
      });
    });

    await expect(loadOverview("ACL", 2026, root, "long")).rejects.toThrow(
      /scope|venue|year|track/i,
    );
  });

  it("returns the validated selector scope rather than inferring a hardcoded view label", async () => {
    const loaded = await loadOverview("ACL", 2026, task9FixtureRoot, "long");
    expect(loaded?.scope).toEqual({ venue: "ACL", year: 2026, track: "long" });
  });

  it("rejects paper source metadata outside the canonical provenance scope", async () => {
    const root = await mutatedTask9Papers((papers) => {
      papers[0].source.name = "Unverified mirror";
    });

    await expect(loadOverview("ACL", 2026, root, "long")).rejects.toThrow(
      /provenance|source|scope/i,
    );
  });
});
