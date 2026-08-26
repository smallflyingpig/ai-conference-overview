import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";

import AwardMethodDiagram from "../src/components/AwardMethodDiagram";
import AwardResultClaim from "../src/components/AwardResultClaim";
import AwardEvidenceSections from "../src/components/AwardEvidenceSections";
import { loadOverview, type LoadedOverview } from "../src/lib/data";
import awardHostPolicy from "../../config/award-host-policy.json";
import { canonicalUrlHostname, configuredAwardHostPolicy } from "../src/lib/schema";
import {
  advanceCategories,
  awardChineseInsight,
  awardDetailRoutes,
  awardRouteKey,
  buildAdvances,
  buildAwardConferenceIndexes,
  buildAwardIndex,
  buildMethodologyView,
  evidenceLabel,
  filterPapers,
  validateDeepRead,
  type DeepRead,
} from "../src/lib/evidence";

const fixtureRoot = fileURLToPath(new URL("./fixtures/task9-release", import.meta.url));
const currentReleaseRoot = fileURLToPath(new URL("../../data/releases", import.meta.url));
const contentRoot = fileURLToPath(new URL("./fixtures/task-content", import.meta.url));
let release: LoadedOverview;
let currentRelease: LoadedOverview;
const execFileAsync = promisify(execFile);

function producerAwardFields(paperId: string, normalizedAwardType: string) {
  const canonicalIdentity = { paper_id: paperId, award_type: normalizedAwardType };
  return {
    canonical_identity: canonicalIdentity,
    route_key: `award-${createHash("sha256")
      .update(JSON.stringify([paperId, normalizedAwardType]))
      .digest("hex")}`,
  };
}

beforeAll(async () => {
  const [fixture, current] = await Promise.all([
    loadOverview("ACL", 2026, fixtureRoot, "long"),
    loadOverview("ACL", 2026, currentReleaseRoot, "long"),
  ]);
  if (fixture == null) throw new Error("validated fixture was not loaded");
  if (current == null) throw new Error("current validated release was not loaded");
  release = fixture;
  currentRelease = current;
});

const validDeepRead: DeepRead = {
  paper_id: "paper-a",
  research_problem: {
    claim: "The paper studies a disclosed problem.", evidence_type: "paper_reported",
    source_urls: ["https://aclanthology.org/paper-a.pdf"], locator: "Section 1",
  },
  contribution: {
    claim: "The paper contributes a disclosed method.", evidence_type: "paper_reported",
    source_urls: ["https://aclanthology.org/paper-a.pdf"], locator: "Section 2",
  },
  method_summary: {
    claim: "The disclosed method transforms inputs into predictions.", evidence_type: "paper_reported",
    source_urls: ["https://aclanthology.org/paper-a.pdf"], locator: "Section 3",
  },
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
  limitations: [{
    claim: "The paper evaluates one bounded setting.", evidence_type: "paper_reported",
    source_urls: ["https://aclanthology.org/paper-a.pdf"], locator: "Limitations",
  }],
  data_training_setup: [{
    claim: "The paper discloses its training data.", evidence_type: "paper_reported",
    source_urls: ["https://aclanthology.org/paper-a.pdf"], locator: "Section 4",
  }],
  prior_work_differences: [{
    claim: "The paper changes the training objective.", evidence_type: "paper_reported",
    source_urls: ["https://aclanthology.org/paper-a.pdf"], locator: "Section 2",
  }],
  reproducibility_assessment: [{
    claim: "The appendix discloses reproducibility details.", evidence_type: "paper_reported",
    source_urls: ["https://aclanthology.org/paper-a.pdf"], locator: "Appendix A",
  }],
  transferable_implications: [{
    claim: "The design may transfer to data-quality pipelines.", evidence_type: "inference",
    source_urls: ["https://aclanthology.org/paper-a.pdf"], locator: "Section 3",
  }],
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
      "官方信息",
      "论文原文结果",
      "多篇论文综合",
      "进一步判断",
    ]);
  });

  it("uses the generated venue-registry host policy artifact", () => {
    expect(configuredAwardHostPolicy("ACL", 2026, "long")).toEqual(
      awardHostPolicy.scopes["ACL/2026/long"],
    );
  });

  it("uses WHATWG hostname canonicalization for case, trailing dots, and IDN", () => {
    expect(canonicalUrlHostname("https://FAß.DE./awards")).toBe("xn--fa-hia.de");
    expect(canonicalUrlHostname("https://example.com。/awards")).toBe("example.com");
    expect(() => canonicalUrlHostname("https://example.com../awards"))
      .toThrow(/empty label|terminal dot/i);
    expect(canonicalUrlHostname("https://2026.aclweb.org。/awards"))
      .toBe(awardHostPolicy.scopes["ACL/2026/long"][0]);
  });

  it("rejects hostnames outside the producer STD3 DNS boundary", () => {
    expect(() => canonicalUrlHostname("https://bad_host.example/awards"))
      .toThrow(/STD3|hostname label/i);
    expect(() => canonicalUrlHostname("https://-bad.example/awards"))
      .toThrow(/STD3|hostname label/i);
    expect(() => canonicalUrlHostname("https://bad-.example/awards"))
      .toThrow(/STD3|hostname label/i);
    expect(() => canonicalUrlHostname(`https://${"a".repeat(64)}.example/awards`))
      .toThrow(/63 bytes|hostname label/i);
  });

  it("rejects a canonical hostname longer than 253 bytes", () => {
    const hostname = ["a".repeat(63), "b".repeat(63), "c".repeat(63), "d".repeat(61)].join(".");
    expect(hostname).toHaveLength(253);
    expect(canonicalUrlHostname(`https://${hostname}/awards`)).toBe(hostname);

    const overlong = `${hostname}x`;
    expect(overlong).toHaveLength(254);
    expect(() => canonicalUrlHostname(`https://${overlong}/awards`))
      .toThrow(/253 bytes|hostname/i);
  });
});

describe("award publication gate", () => {
  it("groups analyzed award releases by conference and excludes papers-only releases", () => {
    const icml = structuredClone(release);
    icml.scope = { venue: "ICML", year: 2025, track: "main" };
    icml.papers[0].paper_id = "pmlr:v267:example25a";
    icml.papers[0].venue = "ICML";
    icml.papers[0].year = 2025;
    icml.papers[0].track = "main";
    icml.overview.publication_context = {
      status: "final_proceedings",
      final_source_status: "available",
      final_source_url: "https://proceedings.mlr.press/v267/",
      notice: "ICML 2025 单年分析。",
      analysis_availability: {
        papers: true, distribution: true, trends: false, advances: true, awards: true,
      },
    };
    const papersOnly = structuredClone(icml);
    papersOnly.scope.year = 2026;
    papersOnly.overview.publication_context!.analysis_availability = {
      papers: true, distribution: false, trends: false, advances: false, awards: false,
    };

    expect(buildAwardConferenceIndexes([release, icml, papersOnly]).map((group) =>
      `${group.venue}-${group.year}`)).toEqual(["ACL-2026", "ICML-2025"]);
  });

  it("requires a completed Chinese insight for every published award detail", () => {
    for (const award of currentRelease.overview.awards) {
      expect(awardChineseInsight(award.paper_id)).not.toMatch(/仍在整理中/);
    }
    expect(() => awardChineseInsight("acl:missing-award-insight")).toThrow(
      /缺少中文解读/,
    );
  });

  it("creates a detail route only for a verified award with a valid matching deep read", () => {
    const routes = awardDetailRoutes(release);
    expect(routes).toHaveLength(1);
    expect(routes[0].params.paperId).toMatch(/^award-[0-9a-f]{64}$/);
    expect(routes[0].params.paperId).not.toContain("paper-a");
  });

  it("creates safe award routes across releases and ignores papers-only releases", () => {
    const icml = structuredClone(release);
    icml.scope = { venue: "ICML", year: 2025, track: "main" };
    icml.papers[0].paper_id = "pmlr:v267:example25a";
    icml.papers[0].venue = "ICML";
    icml.papers[0].year = 2025;
    icml.papers[0].track = "main";
    icml.overview.awards[0] = {
      ...icml.overview.awards[0],
      paper_id: icml.papers[0].paper_id,
      ...producerAwardFields(icml.papers[0].paper_id, "outstanding paper"),
    };
    icml.overview.award_deep_reads[0].paper_id = icml.papers[0].paper_id;
    icml.overview.publication_context = {
      status: "final_proceedings",
      final_source_status: "available",
      final_source_url: "https://proceedings.mlr.press/v267/",
      notice: "ICML 2025 单年分析。",
      analysis_availability: {
        papers: true, distribution: true, trends: false, advances: true, awards: true,
      },
    };
    const papersOnly = structuredClone(icml);
    papersOnly.overview.publication_context!.analysis_availability = {
      papers: true, distribution: false, trends: false, advances: false, awards: false,
    };

    expect(awardDetailRoutes([release, icml])).toHaveLength(2);
    expect(awardDetailRoutes([papersOnly])).toEqual([]);
  });

  it("does not create a route for an unverified award candidate", () => {
    const unverified = structuredClone(release);
    unverified.overview.awards[0].status = "not_verified";
    expect(awardDetailRoutes(unverified)).toEqual([]);
  });

  it("does not create a route when the deep read is absent", () => {
    const missing = structuredClone(release);
    missing.overview.award_deep_reads = [];
    expect(awardDetailRoutes(missing)).toEqual([]);
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

    const inferredResult = structuredClone(validDeepRead);
    (inferredResult.result_claims[0] as { evidence_type: string }).evidence_type = "inference";
    expect(() => validateDeepRead(inferredResult)).toThrow(/paper_reported|literal/i);
  });

  it("supports an explicit non-numeric state only for a position paper", () => {
    const positionPaper = structuredClone(validDeepRead);
    positionPaper.result_claims = [];
    positionPaper.no_numeric_result = {
      paper_type: "position_paper",
      reason: {
        claim: "This position paper proposes a research agenda rather than a numeric benchmark result.",
        evidence_type: "paper_reported",
        source_urls: ["https://proceedings.mlr.press/v267/paper.pdf"],
        locator: "Abstract and Section 1",
      },
    };
    expect(validateDeepRead(positionPaper).no_numeric_result?.paper_type)
      .toBe("position_paper");

    const missingBoth = structuredClone(validDeepRead);
    missingBoth.result_claims = [];
    expect(() => validateDeepRead(missingBoth)).toThrow(/numeric result/i);

    const bothStates = structuredClone(positionPaper);
    bothStates.result_claims = structuredClone(validDeepRead.result_claims);
    expect(() => validateDeepRead(bothStates)).toThrow(/numeric result/i);
  });

  it("requires every approved deep-read section and interpretive transfer evidence", () => {
    for (const field of [
      "data_training_setup", "prior_work_differences",
      "reproducibility_assessment", "transferable_implications",
    ] as const) {
      const missing = structuredClone(validDeepRead);
      missing[field] = [];
      expect(() => validateDeepRead(missing)).toThrow();
    }
    const reportedTransfer = structuredClone(validDeepRead);
    reportedTransfer.transferable_implications[0].evidence_type = "paper_reported";
    expect(() => validateDeepRead(reportedTransfer)).toThrow(/transferable|synthesis|inference/i);
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
    noAnnouncement.overview.awards = [];
    noAnnouncement.overview.award_deep_reads = [];
    noAnnouncement.overview.award_state = {
      status: "not_announced",
      evidence_url: "https://2026.aclweb.org/awards/",
      evidence_claim: {
        claim: "The official program states that awards are not announced.",
        evidence_type: "official_metadata",
        source_urls: ["https://2026.aclweb.org/awards/"],
        locator: "Awards status",
      },
      verification: release.overview.award_state.verification,
    };
    expect(buildAwardIndex(noAnnouncement).stateLabel).toBe("尚未公布");

    const unverified = structuredClone(release);
    unverified.overview.awards[0].status = "not_verified";
    unverified.overview.award_deep_reads = [];
    unverified.overview.award_state.status = "not_verified";
    expect(buildAwardIndex(unverified).stateLabel).toBe("尚待官方确认");
    expect(buildAwardIndex(null).stateLabel).toBe("不可用");
  });

  it("uses a collision-resistant safe route key for malicious raw paper IDs", () => {
    const malicious = structuredClone(release);
    const raw = "../%2Fescape/paper";
    malicious.papers[0].paper_id = raw;
    malicious.overview.assignments[0].paper_id = raw;
    malicious.overview.awards[0].paper_id = raw;
    malicious.overview.award_deep_reads[0].paper_id = raw;
    const route = awardDetailRoutes(malicious)[0];
    expect(route.params.paperId).toMatch(/^award-[0-9a-f]{64}$/);
    expect(route.params.paperId).not.toMatch(/[/%]/);
  });

  it("uses paper and normalized award type as collision-safe route identity", () => {
    const multiple = structuredClone(release);
    multiple.overview.awards.push({
      ...structuredClone(multiple.overview.awards[0]),
      award_type: "Outstanding Paper",
      ...producerAwardFields("paper-a", "outstanding paper"),
    });
    const routes = awardDetailRoutes(multiple);
    expect(routes).toHaveLength(2);
    expect(new Set(routes.map((route) => route.params.paperId)).size).toBe(2);
    expect(routes.map((route) => route.props.detail.award.award_type).sort()).toEqual([
      "Best Paper", "Outstanding Paper",
    ]);
    expect(routes.every((route) => awardRouteKey(route.props.detail.award) === route.params.paperId))
      .toBe(true);
    expect(routes.every((route) => !/[/%]/.test(route.params.paperId))).toBe(true);
  });

  it("rejects a blank minimal deep read", () => {
    expect(() => validateDeepRead({ paper_id: "paper-a", result_claims: [], why_it_matters: [] }))
      .toThrow();
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
    expect(html).toContain("Input records → Model — Records enter the disclosed model.");
    expect(html).toContain("Model → Predictions — The model emits predictions.");
    expect(html).toContain("aria-label=\"论文方法示意图\"");
  });

  it("describes branched and disconnected graphs without inventing chain edges", () => {
    const branched = structuredClone(validDeepRead);
    branched.method_diagram = {
      nodes: [
        { identifier: "root", label: "Root", paper_section: "3.1" },
        { identifier: "left", label: "Left", paper_section: "3.2" },
        { identifier: "right", label: "Right", paper_section: "3.3" },
        { identifier: "audit", label: "Audit", paper_section: "Appendix A" },
      ],
      edges: [
        { source: "root", target: "left", data_flow_rationale: "Root dispatches left." },
        { source: "root", target: "right", data_flow_rationale: "Root dispatches right." },
      ],
    };
    const html = renderToStaticMarkup(createElement(AwardMethodDiagram, {
      diagram: validateDeepRead(branched).method_diagram!,
    }));
    expect(html).toContain("Root — 3.1");
    expect(html).toContain("Audit — Appendix A");
    expect(html).toContain("Root → Left — Root dispatches left.");
    expect(html).toContain("Root → Right — Root dispatches right.");
    expect(html).not.toContain("Left → Right");
  });

  it("rejects edges that do not connect disclosed nodes", () => {
    const invalid = structuredClone(validDeepRead);
    invalid.method_diagram!.edges[0].target = "invented";
    expect(() => validateDeepRead(invalid)).toThrow(/disclosed nodes/i);
  });
});

describe("complete award evidence rendering", () => {
  it("renders every section, source URL, and locator", () => {
    const html = renderToStaticMarkup(createElement(AwardEvidenceSections, {
      deepRead: validateDeepRead(validDeepRead),
    }));
    for (const heading of [
      "研究问题", "主要贡献", "方法", "数据 / 训练设置",
      "与既有工作的差异", "可复现性评估",
      "对后续研究的启发", "为什么重要", "局限",
    ]) expect(html).toContain(heading);
    expect((html.match(/https:\/\/aclanthology\.org\/paper-a\.pdf/g) ?? []).length)
      .toBeGreaterThanOrEqual(9);
    expect(html).toContain("Section 4");
    expect(html).toContain("Appendix A");
  });

  it("builds release-backed award and methodology pages with every section", async () => {
    const siteRoot = fileURLToPath(new URL("..", import.meta.url));
    await execFileAsync(join(siteRoot, "node_modules/.bin/astro"), ["build"], {
      cwd: siteRoot,
      env: {
        ...process.env,
        ASTRO_TELEMETRY_DISABLED: "1",
        CONFERENCE_RELEASE_ROOT: currentReleaseRoot,
      },
    });
    const award = currentRelease.overview.awards[0];
    const route = awardRouteKey(award);
    const awardHtml = await readFile(
      join(siteRoot, "dist/awards", route, "index.html"), "utf8",
    );
    const methodologyHtml = await readFile(
      join(siteRoot, "dist/methodology/index.html"), "utf8",
    );
    for (const heading of [
      "数据 / 训练设置", "与既有工作的差异",
      "可复现性评估", "对后续研究的启发",
    ]) expect(awardHtml).toContain(heading);
    expect(awardHtml).toContain("https://aclanthology.org/");
    for (const expected of [
      "阶段 1",
      "阶段 2",
      "共复查 655 篇：保留原分类 217 篇，调整分类 438 篇",
      "共复查 143 篇：保留原分类 112 篇，调整分类 31 篇",
      "c51895a7148b15c8a9756d6651ae013b85b2a17b64f8496d2fe1d17455333b6b",
      "0de77ca92db5c7f02286fe2084a8ca13504bc29ab5a5c15bea6528ff0094dcb6",
      "750e7de5f75221f7e451eb2ac765976c13cd1c3f8101b46f8b7f9c9a5ac50f6b",
      "a20fdfab1b691f0215a55d573d9eba22eb3f7cdbdc6f2165df81145bd38138e7",
      "分类版本",
    ]) expect(methodologyHtml).toContain(expected);

    await execFileAsync(join(siteRoot, "node_modules/.bin/astro"), ["build"], {
      cwd: siteRoot,
      env: {
        ...process.env,
        ASTRO_TELEMETRY_DISABLED: "1",
        CONFERENCE_RELEASE_ROOT: fixtureRoot,
        CONFERENCE_CONTENT_ROOT: contentRoot,
      },
    });
    const fixtureRoute = awardRouteKey(release.overview.awards[0]);
    const fixtureAwardHtml = await readFile(
      join(siteRoot, "dist/awards", fixtureRoute, "index.html"), "utf8",
    );
    for (const heading of [
      "三分钟读懂",
      "中文摘要",
      "研究背景",
      "方法怎么做",
      "主要结果与意义",
      "局限与适用范围",
      "对后续研究的启发",
      "英文原文参考",
    ]) expect(fixtureAwardHtml).toContain(heading);
    expect(fixtureAwardHtml.indexOf("三分钟读懂"))
      .toBeLessThan(fixtureAwardHtml.indexOf("英文原文参考"));
  }, 30_000);
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
  it("exposes every full-theme stage with counts, movement, and assignment chain", () => {
    const methodology = buildMethodologyView(currentRelease);
    const stages = methodology.classificationLineage?.fullThemeStages;

    expect(stages).toHaveLength(2);
    expect(stages?.[0]).toMatchObject({
      stageIndex: 1,
      baseAssignmentsSha256: "c51895a7148b15c8a9756d6651ae013b85b2a17b64f8496d2fe1d17455333b6b",
      resultAssignmentsSha256: "0de77ca92db5c7f02286fe2084a8ca13504bc29ab5a5c15bea6528ff0094dcb6",
      reviewedCount: 655,
      keepCount: 217,
      correctionCount: 438,
    });
    expect(stages?.[0].sources).toHaveLength(4);
    expect(stages?.[0].movements).toContainEqual({
      sourceTheme: "Applications",
      targetTheme: "Data and Retrieval",
      count: 22,
    });
    expect(stages?.[1]).toMatchObject({
      stageIndex: 2,
      baseAssignmentsSha256: "0de77ca92db5c7f02286fe2084a8ca13504bc29ab5a5c15bea6528ff0094dcb6",
      resultAssignmentsSha256: "750e7de5f75221f7e451eb2ac765976c13cd1c3f8101b46f8b7f9c9a5ac50f6b",
      reviewedCount: 143,
      keepCount: 112,
      correctionCount: 31,
    });
    expect(stages?.[1].sources[0]).toMatchObject({
      sourceTheme: "Reasoning and Agents",
      assignmentBlobSha256: "0de77ca92db5c7f02286fe2084a8ca13504bc29ab5a5c15bea6528ff0094dcb6",
      sourceCommit: "943b0fac246e9133f7f805bf24e1c87fb9f1b7d1",
    });
    expect(stages?.every((stage) => stage.method === "逐篇阅读标题和摘要，完成全主题语义复查")).toBe(true);
    expect(methodology.classificationLineage?.auditSampleMethod).toContain("按置信度分层");
    expect(methodology.classificationLineage?.auditSampleMethod).not.toContain("precision audit");
  });

  it("exposes source, scope, formulas, missingness, audits, and evidence limits", () => {
    const view = buildMethodologyView(release);
    expect(view.sources[0]).toMatchObject({
      url: "https://aclanthology.org/volumes/2026.acl-long/",
      sha256: "a".repeat(64),
      retrievedAt: "2026-08-24T01:02:03Z",
    });
    expect(view.build).toEqual({
      generatedAt: "2026-08-24T02:03:04Z",
      producer: "conference_overview.reports.write_release",
      schemaVersion: "release-build-v1",
    });
    expect(view.scope.denominator).toBe("明确排除不在范围内的记录后，实际纳入统计的论文数");
    expect(view.scope.denominatorField).toBe("validation.included_count");
    expect(view.scope).toMatchObject({
      year: 2026,
      inclusionStatuses: ["信息完整", "部分信息缺失"],
      denominatorUnit: "篇论文",
      denominatorValue: 2,
    });
    expect(view.contractIds.comparison).toMatch(/^[0-9a-f]{64}$/);
    expect(view.contractIds.formula).toBe("conference-metrics-v1");
    expect(view.configuredVenues).toEqual(["ACL", "EMNLP", "NAACL", "NeurIPS"]);
    expect(view.emergingScoreWeights).toEqual({ novelty: "0.20", share_growth: "0.45", spread_growth: "0.35" });
    expect(view.formulas.every((formula) => formula.numerator != null)).toBe(true);
    expect(view.formulas.map((formula) => formula.name)).toEqual([
      "主要主题（primary topic）占比",
      "跨会议覆盖率",
      "新兴主题得分",
    ]);
    expect(view.missingness).toEqual({ abstracts: 0, pdfs: 0, dois: 0 });
    expect(view.audits[0]).toMatchObject({
      sampleSize: 50,
      observedPrecision: "0.92",
      wilsonLower95: "0.8116175308165716535840671634",
    });
    expect(view.classificationReview).toEqual({
      complete: true,
      lowConfidenceCount: 0,
      pendingCount: 0,
      rejectedCount: 0,
      reviewedCount: 0,
    });
    expect(view.withheldThemes.themes).toEqual(["Sparse expert routing (experimental)"]);
    expect(view.withheldThemes.items[0]).toMatchObject({
      theme: "Sparse expert routing",
      status: "experimental",
      sourceUrls: ["https://aclanthology.org/paper-a.pdf"],
      locator: "Section 3",
    });
    expect(view.withheldThemes.note).toMatch(/当前有 1 个主题暂不纳入主要分析/);
  });

  it("exposes incomplete exhaustive low-confidence review counts", () => {
    const staged = structuredClone(release);
    staged.overview.assignments[0].confidence = "0.69";
    staged.overview.classification_review = {
      confidence_threshold: "0.70",
      low_confidence_ids: [staged.overview.assignments[0].paper_id],
      pending_low_confidence_ids: [staged.overview.assignments[0].paper_id],
      rejected_low_confidence_ids: [],
      review_complete: false,
      reviewed_low_confidence_ids: [],
    };

    expect(buildMethodologyView(staged).classificationReview).toEqual({
      complete: false,
      lowConfidenceCount: 1,
      pendingCount: 1,
      rejectedCount: 0,
      reviewedCount: 0,
    });
  });

  it("defines every required advance lane even when evidence is absent", () => {
    expect(advanceCategories.map((category) => category.label)).toEqual([
      "文本 LLM",
      "多模态模型",
      "推理与 Agents",
      "数据与训练（Pretraining / Post-training）",
      "评测、Safety 与 Interpretability",
    ]);
  });

  it("loads typed advances and supporting papers from the current release", () => {
    const lanes = buildAdvances(release);
    expect(lanes.find((lane) => lane.id === "data-training")?.advances[0]).toMatchObject({
      title: "Evidence-backed data quality",
      supportingPaperIds: ["paper-a"],
      supportingPapers: [{ paperId: "paper-a", officialUrl: "https://aclanthology.org/paper-a/" }],
    });
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
