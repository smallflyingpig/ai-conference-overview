import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeAll, describe, expect, it } from "vitest";

import TopicShareChart from "../src/components/TopicShareChart";
import TrendExplorer from "../src/components/TrendExplorer";
import { loadOverview, type LoadedOverview } from "../src/lib/data";
import { conferenceNavigationHref, projectPath } from "../src/lib/paths";
import {
  applyTrendFilters,
  buildConferenceView,
  buildTrendView,
  conferenceRoutes,
  parseTrendFilters,
  type TrendFilters,
} from "../src/lib/views";

const task9FixtureRoot = fileURLToPath(
  new URL("./fixtures/task9-release", import.meta.url),
);
let validatedRelease: LoadedOverview;

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value != null && typeof value === "object") {
    return `{${Object.entries(value as Record<string, unknown>)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => `${JSON.stringify(key)}:${canonicalJson(item)}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

beforeAll(async () => {
  const loaded = await loadOverview("ACL", 2026, task9FixtureRoot, "long");
  if (loaded == null) throw new Error("Task 9 validated fixture was not loaded");
  validatedRelease = loaded;
});

function releaseForYear(year: number): LoadedOverview {
  const release = structuredClone(validatedRelease);
  release.scope.year = year;
  release.papers.forEach((paper) => { paper.year = year; });
  return release;
}

function threeYears(): LoadedOverview[] {
  return [releaseForYear(2024), releaseForYear(2025), releaseForYear(2026)];
}

function changeComparisonContract(
  release: LoadedOverview,
  mutate: (contract: LoadedOverview["overview"]["comparison_contract"]) => void,
): void {
  const contract = release.overview.comparison_contract;
  mutate(contract);
  const { contract_id: _oldId, ...identity } = contract;
  contract.contract_id = createHash("sha256")
    .update(canonicalJson(identity))
    .digest("hex");
}

describe("conference routes", () => {
  it("creates the ACL 2026 conference route from a schema-validated release", () => {
    expect(conferenceRoutes([validatedRelease])).toContainEqual({
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

  it("does not link to a conference route that an empty build does not emit", () => {
    expect(conferenceNavigationHref("/ai-conference-overview/", false)).toBeNull();
    expect(conferenceNavigationHref("/ai-conference-overview/", true)).toBe(
      "/ai-conference-overview/conferences/acl/2026/",
    );
  });
});

describe("distribution view", () => {
  it("uses Distribution and Snapshot labels for a single year", () => {
    const view = buildConferenceView(validatedRelease);
    expect(view.analysisLabel).toBe("Distribution");
    expect(view.periodLabel).toBe("2026 snapshot");
    expect(view.trendEligible).toBe(false);
  });

  it("derives scope and accessible page name from the validated release", () => {
    const view = buildConferenceView(validatedRelease);
    expect(view.scopeLabel).toBe("ACL 2026 · long");
    expect(view.pageHeading).toBe("ACL 2026 long papers");
  });

  it("keeps chart and semantic table values identical", () => {
    const rows = buildConferenceView(validatedRelease).topics;
    const html = renderToStaticMarkup(
      createElement(TopicShareChart, { rows, denominator: 2 }),
    );
    for (const row of rows) {
      expect(html).toContain(`data-chart-value="${row.shareLabel}"`);
      expect(html).toContain(`<td>${row.shareLabel}</td>`);
      expect(html).toContain(`<td>${row.paperCount}</td>`);
    }
  });

  it("publishes explicit denominators and data-health counts", () => {
    const view = buildConferenceView(validatedRelease);
    expect(view.denominatorLabel).toBe("2 included long papers");
    expect(view.includedCount).toBe(2);
    expect(view.excludedCount).toBe(0);
    expect(view.abstractCoverageLabel).toBe("2 of 2 (100.00%)");
  });

  it("exposes failed audit themes as experimental instead of audited", () => {
    const release = structuredClone(validatedRelease);
    const theme = release.overview.assignments[0].primary_topic;
    release.overview.audits[theme] = {
      correct_count: 0,
      observed_precision: "0",
      sample_size: 0,
      thresholds: {
        minimum_observed_precision: "0.90",
        minimum_wilson_lower_95: "0.80",
      },
      wilson_lower_95: "0",
    };
    release.overview.theme_disclosures = [{
      theme,
      status: "experimental",
      reason: {
        claim: "Semantic audit decisions remain pending.",
        evidence_type: "inference",
        source_urls: ["https://aclanthology.org/volumes/2026.acl-long/"],
        locator: "classification audit registry",
      },
    }];

    const view = buildConferenceView(release);
    expect(view.topics.find((row) => row.topic === theme)?.auditStatus).toBe("experimental");
    expect(view.auditPassedThemeCount).toBe(view.topics.length - 1);
    expect(view.experimentalThemeCount).toBe(1);
  });
});

describe("trend comparability gate", () => {
  it("suppresses trend claims until three comparable years exist", () => {
    const view = buildTrendView([validatedRelease]);
    expect(view.mode).toBe("snapshot");
    expect(view.heading).toBe("Distribution / Snapshot / Hotspot");
    expect(view.trendWidgetsVisible).toBe(false);
    expect(view.missingRequirement).toMatch(/three comparable validated years/i);
  });

  it("accepts three consecutive releases with the same comparison contract", () => {
    expect(buildTrendView(threeYears()).mode).toBe("trend");
  });

  it("rejects a three-year window with different taxonomy versions", () => {
    const releases = threeYears();
    releases[0].overview.taxonomy_version = "different-taxonomy";
    expect(buildTrendView(releases).mode).toBe("snapshot");
  });

  it("rejects a three-year window with different track scopes", () => {
    const releases = threeYears();
    releases[0].scope.track = "short";
    releases[0].papers.forEach((paper) => { paper.track = "short"; });
    expect(buildTrendView(releases).mode).toBe("snapshot");
  });

  it("rejects a three-year window when a formula changes without changing JSON types", () => {
    const releases = threeYears();
    changeComparisonContract(releases[0], (contract) => {
      contract.metric_contract.topic_share.formula =
        "primary_topic_paper_count / discovered_paper_count";
    });
    expect(buildTrendView(releases).mode).toBe("snapshot");
  });

  it("rejects a three-year window when the denominator changes without changing JSON types", () => {
    const releases = threeYears();
    changeComparisonContract(releases[0], (contract) => {
      contract.comparison_scope.denominator.artifact_field = "validation.discovered_count";
    });
    expect(buildTrendView(releases).mode).toBe("snapshot");
  });

  it("rejects a three-year window when inclusion scope changes without changing JSON types", () => {
    const releases = threeYears();
    changeComparisonContract(releases[0], (contract) => {
      contract.comparison_scope.excluded_records =
        "excluded records are retained in the denominator";
    });
    expect(buildTrendView(releases).mode).toBe("snapshot");
  });

  it("rejects same-size configured venue population drift across three years", () => {
    const releases = threeYears();
    changeComparisonContract(releases[0], (contract) => {
      const spread = contract.metric_contract.cross_venue_spread;
      spread.configured_venues = ["ACL", "CVPR", "NAACL", "NeurIPS"];
      spread.configured_venue_count = spread.configured_venues.length;
      spread.configured_venue_id = createHash("sha256")
        .update(JSON.stringify(spread.configured_venues))
        .digest("hex");
    });
    expect(buildTrendView(releases).mode).toBe("snapshot");
  });

  it("explains the publication gate when no release is available", () => {
    const view = buildTrendView([]);
    expect(view.mode).toBe("empty");
    expect(view.availableVenues).toEqual([]);
    expect(view.missingRequirement).toMatch(/validated release/i);
  });
});

describe("typed trend filters", () => {
  it("honors venue, year, and theme filters in the view model", () => {
    const filters: TrendFilters = {
      venue: "ACL",
      year: 2025,
      modality: null,
      theme: "Foundation Models",
    };
    const view = buildTrendView(threeYears(), filters);
    expect(view.snapshots).toHaveLength(1);
    expect(view.snapshots[0].year).toBe(2025);
    expect(view.snapshots[0].topics.map((row) => row.topic)).toEqual(["Foundation Models"]);
    expect(view.filters).toEqual(filters);
  });

  it("recomputes the claim gate when client filtering narrows a trend to one year", () => {
    const base = buildTrendView(threeYears());
    const filtered = applyTrendFilters(base, {
      venue: null,
      year: 2025,
      modality: null,
      theme: null,
    });
    expect(base.mode).toBe("trend");
    expect(filtered.mode).toBe("snapshot");
    expect(filtered.trendWidgetsVisible).toBe(false);
  });

  it("parses only supported URL filter state", () => {
    const base = buildTrendView(threeYears());
    expect(
      parseTrendFilters(
        "?venue=ACL&year=2025&theme=Foundation+Models&modality=unsupported",
        base,
      ),
    ).toEqual({
      venue: "ACL",
      year: 2025,
      theme: "Foundation Models",
      modality: null,
    });
  });

  it("renders selected filter state and an accessible apply action", () => {
    const view = buildTrendView(threeYears());
    const html = renderToStaticMarkup(
      createElement(TrendExplorer, {
        view,
        action: "/ai-conference-overview/trends/",
        initialFilters: { venue: "ACL", year: 2025, theme: null, modality: null },
      }),
    );
    expect(html).toContain('<option value="ACL" selected="">ACL</option>');
    expect(html).toContain('<option value="2025" selected="">2025</option>');
    expect(html).toContain('<button type="submit">Apply filters</button>');
  });
});

describe("distribution presentation", () => {
  it("labels papers as audit-bounded evidence examples", async () => {
    const page = await readFile(
      fileURLToPath(new URL("../src/pages/conferences/[venue]/[year].astro", import.meta.url)),
      "utf8",
    );
    expect(page).toContain("Evidence examples");
    expect(page).toContain("Audit-labeled semantic assignments");
    expect(page).not.toContain("Representative papers");
  });

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
