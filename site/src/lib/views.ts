export interface ConferenceRelease {
  venue: string;
  year: number;
  release: {
    generation: string;
    overview: {
      [key: string]: unknown;
      assignments: Array<{
        confidence: string;
        paper_id: string;
        primary_topic: string;
        rationale: string;
        secondary_topics: string[];
        taxonomy_version: string;
      }>;
      taxonomy_version: string;
    };
    validation: {
      [key: string]: unknown;
      discovered_count: number;
      included_count: number;
      excluded_count: number;
      missing_abstract_count: number;
    };
    provenance: {
      [key: string]: unknown;
      sources: Array<{
        name: string;
        url: string;
        retrieved_at: string;
        sha256: string;
      }>;
      taxonomy_version: string;
    };
    papers: Array<{
      [key: string]: unknown;
      paper_id: string;
      title: string;
      landing_url: string;
      track?: string;
    }>;
  };
}

export interface TopicShareRow {
  topic: string;
  paperCount: number;
  share: number;
  shareLabel: string;
  representativePaper: {
    paperId: string;
    title: string;
    url: string;
  };
}

export interface ConferenceView {
  venue: string;
  venueSlug: string;
  year: number;
  scopeLabel: string;
  analysisLabel: "Distribution";
  periodLabel: string;
  trendEligible: false;
  includedCount: number;
  excludedCount: number;
  discoveredCount: number;
  abstractCoverageLabel: string;
  denominatorLabel: string;
  retrievedAt: string;
  sourceName: string;
  sourceUrl: string;
  sourceHash: string;
  generation: string;
  taxonomyVersion: string;
  topics: TopicShareRow[];
}

export interface ConferenceRoute {
  params: { venue: string; year: string };
}

export interface TrendFilters {
  venue: string | null;
  year: number | null;
  modality: string | null;
  theme: string | null;
}

export interface TrendView {
  mode: "empty" | "snapshot" | "trend";
  heading: string;
  trendWidgetsVisible: boolean;
  missingRequirement: string | null;
  availableVenues: string[];
  availableYears: number[];
  availableThemes: string[];
  filters: TrendFilters;
  snapshots: ConferenceView[];
}

export function conferenceRoutes(releases: ConferenceRelease[]): ConferenceRoute[] {
  return releases.map(({ venue, year }) => ({
    params: { venue: venue.toLowerCase(), year: String(year) },
  }));
}

function formatCoverage(available: number, denominator: number): string {
  if (denominator === 0) return "0 of 0 (not applicable)";
  return `${available} of ${denominator} (${((available / denominator) * 100).toFixed(1)}%)`;
}

export function buildConferenceView(input: ConferenceRelease): ConferenceView {
  const { release, venue, year } = input;
  const paperById = new Map(release.papers.map((paper) => [paper.paper_id, paper]));
  const assignmentsByTopic = new Map<string, typeof release.overview.assignments>();
  for (const assignment of release.overview.assignments) {
    const assignments = assignmentsByTopic.get(assignment.primary_topic) ?? [];
    assignments.push(assignment);
    assignmentsByTopic.set(assignment.primary_topic, assignments);
  }
  const denominator = release.validation.included_count;
  const topics = [...assignmentsByTopic.entries()]
    .map(([topic, assignments]) => {
      const representative = [...assignments].sort(
        (left, right) => Number(right.confidence) - Number(left.confidence),
      )[0];
      const paper = paperById.get(representative.paper_id);
      if (paper == null) {
        throw new Error(`Representative assignment has no paper: ${representative.paper_id}`);
      }
      const share = denominator === 0 ? 0 : assignments.length / denominator;
      return {
        topic,
        paperCount: assignments.length,
        share,
        shareLabel: `${(share * 100).toFixed(1)}%`,
        representativePaper: {
          paperId: paper.paper_id,
          title: paper.title,
          url: paper.landing_url,
        },
      };
    })
    .sort((left, right) => right.paperCount - left.paperCount || left.topic.localeCompare(right.topic));
  const source = release.provenance.sources[0];
  const tracks = [...new Set(release.papers.map((paper) => paper.track).filter(Boolean))].join(", ");
  return {
    venue,
    venueSlug: venue.toLowerCase(),
    year,
    scopeLabel: `${venue} ${year} · ${tracks || "validated scope"}`,
    analysisLabel: "Distribution",
    periodLabel: `${year} snapshot`,
    trendEligible: false,
    includedCount: denominator,
    excludedCount: release.validation.excluded_count,
    discoveredCount: release.validation.discovered_count,
    abstractCoverageLabel: formatCoverage(
      denominator - release.validation.missing_abstract_count,
      denominator,
    ),
    denominatorLabel: `${denominator} included long papers`,
    retrievedAt: source.retrieved_at,
    sourceName: source.name,
    sourceUrl: source.url,
    sourceHash: source.sha256,
    generation: release.generation,
    taxonomyVersion: release.overview.taxonomy_version,
    topics,
  };
}

function hasComparableThreeYearWindow(releases: ConferenceRelease[]): boolean {
  const byVenue = new Map<string, number[]>();
  for (const release of releases) {
    const years = byVenue.get(release.venue) ?? [];
    years.push(release.year);
    byVenue.set(release.venue, years);
  }
  return [...byVenue.values()].some((years) => {
    const unique = [...new Set(years)].sort((a, b) => a - b);
    return unique.some((year, index) =>
      index >= 2 && unique[index - 2] === year - 2 && unique[index - 1] === year - 1,
    );
  });
}

export function buildTrendView(releases: ConferenceRelease[]): TrendView {
  const snapshots = releases.map(buildConferenceView);
  const availableVenues = [...new Set(releases.map((release) => release.venue))].sort();
  const availableYears = [...new Set(releases.map((release) => release.year))].sort((a, b) => a - b);
  const availableThemes = [...new Set(snapshots.flatMap((snapshot) => snapshot.topics.map((row) => row.topic)))].sort();
  const filters: TrendFilters = { venue: null, year: null, modality: null, theme: null };
  if (releases.length === 0) {
    return {
      mode: "empty",
      heading: "No distribution published",
      trendWidgetsVisible: false,
      missingRequirement: "A validated release must pass every publication gate before it appears here.",
      availableVenues,
      availableYears,
      availableThemes,
      filters,
      snapshots,
    };
  }
  const trendEligible = hasComparableThreeYearWindow(releases);
  return {
    mode: trendEligible ? "trend" : "snapshot",
    heading: trendEligible ? "Comparable research trends" : "Distribution / Snapshot / Hotspot",
    trendWidgetsVisible: trendEligible,
    missingRequirement: trendEligible
      ? null
      : "Trend and year-over-year claims require at least three comparable validated years.",
    availableVenues,
    availableYears,
    availableThemes,
    filters,
    snapshots,
  };
}
