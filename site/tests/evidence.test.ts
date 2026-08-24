import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";

import AwardMethodDiagram from "../src/components/AwardMethodDiagram";
import AwardResultClaim from "../src/components/AwardResultClaim";
import { loadOverview, type LoadedOverview } from "../src/lib/data";
import {
  advanceCategories,
  awardDetailRoutes,
  buildAwardIndex,
  buildMethodologyView,
  evidenceLabel,
  filterPapers,
  validateDeepRead,
  type DeepRead,
} from "../src/lib/evidence";

const fixtureRoot = fileURLToPath(new URL("./fixtures/task9-release", import.meta.url));
let release: LoadedOverview;

beforeAll(async () => {
  const loaded = await loadOverview("ACL", 2026, fixtureRoot, "long");
  if (loaded == null) throw new Error("validated fixture was not loaded");
  release = loaded;
});

const validDeepRead: DeepRead = {
  paper_id: "paper-a",
  result_claims: [
    {
      claim: "Accuracy reached 81.4%.",
      evidence_type: "paper_reported",
      source_urls: ["https://aclanthology.org/paper-a.pdf"],
      locator: "Table 2, p. 7",
      metric: "Accuracy",
      value: "81.4",
      evaluation_setting: "Held-out benchmark, test split",
    },
  ],
  why_it_matters: [
    {
      claim: "The disclosed pipeline may transfer to evaluation tooling.",
      evidence_type: "inference",
      source_urls: ["https://aclanthology.org/paper-a.pdf"],
      locator: "Method, section 3",
    },
  ],
  method_diagram: {
    nodes: [
      { identifier: "input", label: "Input records", paper_section: "Section 3.1" },
      { identifier: "model", label: "Model", paper_section: "Section 3.2" },
      { identifier: "output", label: "Predictions", paper_section: "Section 3.3" },
    ],
    edges: [
      { source: "input", target: "model", data_flow_rationale: "Records enter the disclosed model." },
      { source: "model", target: "output", data_flow_rationale: "The model emits predictions." },
    ],
  },
};

describe("evidence labels", () => {
  it("maps all four evidence classes to distinct reader-facing labels", () => {
    expect([
      evidenceLabel("official_metadata"),
      evidenceLabel("paper_reported"),
      evidenceLabel("cross_paper_synthesis"),
      evidenceLabel("inference"),
    ]).toEqual([
      "Official metadata",
      "Paper-reported",
      "Cross-paper synthesis",
      "Inference",
    ]);
  });
});

describe("award publication gate", () => {
  it("creates a detail route only for a verified award with a valid matching deep read", () => {
    expect(awardDetailRoutes(release, [validDeepRead])).toEqual([
      { params: { paperId: "paper-a" }, props: expect.any(Object) },
    ]);
  });

  it("does not create a route for an unverified award candidate", () => {
    const unverified = structuredClone(release);
    unverified.overview.awards[0].status = "not_verified";
    expect(awardDetailRoutes(unverified, [validDeepRead])).toEqual([]);
  });

  it("does not create a route when the deep read is absent", () => {
    expect(awardDetailRoutes(release, [])).toEqual([]);
  });

  it("requires numeric result metric, setting, source and locator", () => {
    const missingSetting = structuredClone(validDeepRead);
    missingSetting.result_claims[0].evaluation_setting = "";
    expect(() => validateDeepRead(missingSetting)).toThrow(/evaluation setting/i);

    const missingLocator: unknown = {
      ...structuredClone(validDeepRead),
      result_claims: [{ ...structuredClone(validDeepRead.result_claims[0]), locator: null }],
    };
    expect(() => validateDeepRead(missingLocator)).toThrow(/locator/i);
  });

  it("displays each numeric result with its setting and paper locator", () => {
    const withTwoSources = structuredClone(validDeepRead);
    withTwoSources.result_claims[0].source_urls.push("https://aclanthology.org/paper-a/");
    const claim = validateDeepRead(withTwoSources).result_claims[0];
    const html = renderToStaticMarkup(createElement(AwardResultClaim, { claim }));
    expect(html).toContain("Accuracy: 81.4");
    expect(html).toContain("Held-out benchmark, test split");
    expect(html).toContain("Table 2, p. 7");
    expect(html).toContain("https://aclanthology.org/paper-a.pdf");
    expect(html).toContain("https://aclanthology.org/paper-a/");
  });

  it("reports explicit safe states when no award is verified", () => {
    const noAnnouncement = structuredClone(release);
    noAnnouncement.overview.awards[0].status = "not_announced";
    expect(buildAwardIndex(noAnnouncement, []).stateLabel).toBe("Not announced");

    const unverified = structuredClone(release);
    unverified.overview.awards[0].status = "not_verified";
    expect(buildAwardIndex(unverified, []).stateLabel).toBe("Not verified");
  });
});

describe("original method diagram", () => {
  it("keeps validated nodes, edges, and the text sequence in parity", () => {
    const deepRead = validateDeepRead(validDeepRead);
    const html = renderToStaticMarkup(
      createElement(AwardMethodDiagram, { diagram: deepRead.method_diagram! }),
    );
    expect((html.match(/data-method-node=/g) ?? [])).toHaveLength(3);
    expect((html.match(/data-method-edge=/g) ?? [])).toHaveLength(2);
    expect(html).toContain("Input records → Model → Predictions");
    expect(html).toContain("aria-label=\"Original explanatory method diagram\"");
  });

  it("rejects edges that do not connect disclosed nodes", () => {
    const invalid = structuredClone(validDeepRead);
    invalid.method_diagram!.edges[0].target = "invented";
    expect(() => validateDeepRead(invalid)).toThrow(/disclosed nodes/i);
  });
});

describe("paper research index", () => {
  it("searches title and authors and filters by audited primary theme", () => {
    expect(filterPapers(release, { query: "author", theme: "Foundation Models" }))
      .toHaveLength(2);
    expect(filterPapers(release, { query: "paper-z", theme: null }).map((paper) => paper.paperId))
      .toEqual(["paper-z"]);
    expect(filterPapers(release, { query: "not present", theme: null })).toEqual([]);
  });

  it("retains null optional fields without turning them into negative findings", () => {
    const papers = filterPapers(release, { query: "", theme: null });
    expect(papers.every((paper) => paper.officialUrl.startsWith("https://"))).toBe(true);
    expect(papers.some((paper) => paper.codeUrl == null)).toBe(true);
  });
});

describe("methodology audit ledger", () => {
  it("exposes source, scope, formulas, missingness, audits, and evidence limits", () => {
    const view = buildMethodologyView(release);
    expect(view.sources[0]).toMatchObject({
      url: "https://aclanthology.org/volumes/2026.acl-long/",
      sha256: "a".repeat(64),
      retrievedAt: "2026-08-24T01:02:03Z",
    });
    expect(view.scope.denominator).toContain("validation.included_count");
    expect(view.formulas.map((formula) => formula.name)).toEqual([
      "Topic share",
      "Cross-venue spread",
      "Emerging Score",
    ]);
    expect(view.missingness).toEqual({ abstracts: 0, pdfs: 0, dois: 0 });
    expect(view.audits[0]).toMatchObject({
      sampleSize: 50,
      observedPrecision: "0.92",
      wilsonLower95: "0.8116175308165716535840671634",
    });
    expect(view.withheldThemes.note).toMatch(/not published|none withheld/i);
  });

  it("defines every required advance lane even when evidence is absent", () => {
    expect(advanceCategories.map((category) => category.label)).toEqual([
      "Text LLMs",
      "Multimodal Models",
      "Reasoning and Agents",
      "Data / Pretraining / Post-training",
      "Evaluation / Safety / Interpretability",
    ]);
  });
});

describe("research-atlas continuation", () => {
  it("keeps semantic trace colors, keyboard focus, mobile reflow, and reduced motion", async () => {
    const css = await readFile(fileURLToPath(new URL("../src/styles/global.css", import.meta.url)), "utf8");
    expect(css).toContain(".evidence-badge--official");
    expect(css).toContain(".evidence-badge--reported");
    expect(css).toContain(".evidence-badge--synthesis");
    expect(css).toContain(".evidence-badge--inference");
    expect(css).toMatch(/\.research-filter[^}]*:focus-visible/);
    expect(css).toMatch(/@media \(max-width: 760px\)[\s\S]*\.evidence-shell/);
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)/);
  });
});
