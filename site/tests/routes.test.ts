import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import TopicShareChart from "../src/components/TopicShareChart";
import { projectPath } from "../src/lib/paths";
import {
  buildConferenceView,
  buildTrendView,
  conferenceRoutes,
  type ConferenceRelease,
} from "../src/lib/views";

function fixtureRelease(): ConferenceRelease {
  return {
    venue: "ACL",
    year: 2026,
    release: {
      generation: `generations/${"b".repeat(64)}`,
      overview: {
        assignments: [
          {
            confidence: "0.95",
            paper_id: "paper-a",
            primary_topic: "Foundation Models",
            rationale: "Pretraining is the central method.",
            secondary_topics: ["Evaluation"],
            taxonomy_version: "v1",
          },
          {
            confidence: "0.91",
            paper_id: "paper-b",
            primary_topic: "Evaluation",
            rationale: "Evaluation is the central contribution.",
            secondary_topics: [],
            taxonomy_version: "v1",
          },
          {
            confidence: "0.93",
            paper_id: "paper-c",
            primary_topic: "Foundation Models",
            rationale: "Pretraining is the central method.",
            secondary_topics: [],
            taxonomy_version: "v1",
          },
        ],
        audits: {},
        awards: [],
        evidence_claims: [],
        metrics: {},
        paper_count: 3,
        taxonomy_version: "v1",
      },
      validation: {
        discovered_count: 4,
        included_count: 3,
        excluded_count: 1,
        missing_abstract_count: 1,
      },
      provenance: {
        sources: [
          {
            name: "ACL Anthology",
            url: "https://aclanthology.org/volumes/2026.acl-long/",
            retrieved_at: "2026-08-24T01:02:03Z",
            sha256: "a".repeat(64),
          },
        ],
        taxonomy_version: "v1",
      },
      papers: [
        { paper_id: "paper-a", title: "Alpha", landing_url: "https://example.com/a" },
        { paper_id: "paper-b", title: "Beta", landing_url: "https://example.com/b" },
        { paper_id: "paper-c", title: "Gamma", landing_url: "https://example.com/c" },
      ],
    },
  };
}

describe("conference routes", () => {
  it("creates the ACL 2026 conference route from validated release data", () => {
    expect(conferenceRoutes([fixtureRelease()])).toContainEqual({
      params: { venue: "acl", year: "2026" },
    });
  });

  it("creates no conference route without a validated release", () => {
    expect(conferenceRoutes([])).toEqual([]);
  });

  it("keeps generated conference links safe under the project base path", () => {
    expect(projectPath("/ai-conference-overview/", "conferences/acl/2026")).toBe(
      "/ai-conference-overview/conferences/acl/2026/",
    );
  });
});

describe("distribution view", () => {
  it("uses Distribution and Snapshot labels for a single year", () => {
    const view = buildConferenceView(fixtureRelease());
    expect(view.analysisLabel).toBe("Distribution");
    expect(view.periodLabel).toBe("2026 snapshot");
    expect(view.trendEligible).toBe(false);
  });

  it("keeps chart and semantic table values identical", () => {
    const rows = buildConferenceView(fixtureRelease()).topics;
    const html = renderToStaticMarkup(
      createElement(TopicShareChart, { rows, denominator: 3 }),
    );
    for (const row of rows) {
      expect(html).toContain(`data-chart-value="${row.shareLabel}"`);
      expect(html).toContain(`<td>${row.shareLabel}</td>`);
      expect(html).toContain(`<td>${row.paperCount}</td>`);
    }
  });

  it("publishes explicit denominators and data-health counts", () => {
    const view = buildConferenceView(fixtureRelease());
    expect(view.denominatorLabel).toBe("3 included long papers");
    expect(view.includedCount).toBe(3);
    expect(view.excludedCount).toBe(1);
    expect(view.abstractCoverageLabel).toBe("2 of 3 (66.7%)");
  });
});

describe("trends gate", () => {
  it("suppresses trend claims until three comparable years exist", () => {
    const view = buildTrendView([fixtureRelease()]);
    expect(view.mode).toBe("snapshot");
    expect(view.heading).toBe("Distribution / Snapshot / Hotspot");
    expect(view.trendWidgetsVisible).toBe(false);
    expect(view.missingRequirement).toMatch(/three comparable validated years/i);
  });

  it("explains the publication gate when no release is available", () => {
    const view = buildTrendView([]);
    expect(view.mode).toBe("empty");
    expect(view.availableVenues).toEqual([]);
    expect(view.missingRequirement).toMatch(/validated release/i);
  });
});

describe("distribution presentation", () => {
  it("defines a paired chart-table layout with mobile reflow and reduced-motion support", async () => {
    const css = await readFile(
      fileURLToPath(new URL("../src/styles/global.css", import.meta.url)),
      "utf8",
    );
    expect(css).toMatch(/\.distribution-pair\s*\{/);
    expect(css).toMatch(/@media \(max-width: 760px\)[\s\S]*\.distribution-pair/);
    expect(css).toMatch(/@media \(prefers-reduced-motion: no-preference\)/);
  });
});
