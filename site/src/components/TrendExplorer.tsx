import React, { useEffect, useMemo, useState } from "react";

import {
  applyTrendFilters,
  parseTrendFilters,
  type TrendFilters,
  type TrendView,
} from "../lib/views";
import TopicShareChart from "./TopicShareChart";

interface Props {
  view: TrendView;
  action: string;
  initialFilters?: TrendFilters;
}

const noFilters: TrendFilters = {
  venue: null,
  year: null,
  modality: null,
  theme: null,
};

function queryFor(filters: TrendFilters): string {
  const query = new URLSearchParams();
  if (filters.venue != null) query.set("venue", filters.venue);
  if (filters.year != null) query.set("year", String(filters.year));
  if (filters.theme != null) query.set("theme", filters.theme);
  if (filters.modality != null) query.set("modality", filters.modality);
  const serialized = query.toString();
  return serialized.length === 0 ? "" : `?${serialized}`;
}

export default function TrendExplorer({ view, action, initialFilters = noFilters }: Props) {
  const [filters, setFilters] = useState<TrendFilters>(initialFilters);
  useEffect(() => {
    setFilters(parseTrendFilters(window.location.search, view));
  }, [view]);
  const filtered = useMemo(() => applyTrendFilters(view, filters), [view, filters]);

  const submit = (event: React.SyntheticEvent<HTMLFormElement, SubmitEvent>) => {
    event.preventDefault();
    window.history.replaceState(null, "", `${action}${queryFor(filters)}`);
  };

  return (
    <div className="trends-shell">
      <aside className="trend-controls" aria-labelledby="filter-title">
        <p className="eyebrow">Evidence controls</p>
        <h1 id="filter-title">Filter the published set</h1>
        <form method="get" action={action} onSubmit={submit}>
          <label htmlFor="venue-filter">Venue</label>
          <select
            id="venue-filter"
            name="venue"
            disabled={view.availableVenues.length === 0}
            value={filters.venue ?? ""}
            onChange={(event) => setFilters({ ...filters, venue: event.target.value || null })}
          >
            <option value="">{view.availableVenues.length === 0 ? "No published venues" : "All published venues"}</option>
            {view.availableVenues.map((venue) => <option value={venue} key={venue}>{venue}</option>)}
          </select>
          <label htmlFor="year-filter">Year</label>
          <select
            id="year-filter"
            name="year"
            disabled={view.availableYears.length === 0}
            value={filters.year ?? ""}
            onChange={(event) => setFilters({ ...filters, year: event.target.value ? Number(event.target.value) : null })}
          >
            <option value="">{view.availableYears.length === 0 ? "No published years" : "All published years"}</option>
            {view.availableYears.map((year) => <option value={year} key={year}>{year}</option>)}
          </select>
          <label htmlFor="theme-filter">Theme</label>
          <select
            id="theme-filter"
            name="theme"
            disabled={view.availableThemes.length === 0}
            value={filters.theme ?? ""}
            onChange={(event) => setFilters({ ...filters, theme: event.target.value || null })}
          >
            <option value="">{view.availableThemes.length === 0 ? "No classified themes" : "All classified themes"}</option>
            {view.availableThemes.map((theme) => <option value={theme} key={theme}>{theme}</option>)}
          </select>
          <label htmlFor="modality-filter">Modality</label>
          <select id="modality-filter" name="modality" disabled value="">
            <option value="">Not available in this release</option>
          </select>
          <button type="submit">Apply filters</button>
        </form>
        <p className="filter-note">Controls list only fields present in validated artifacts. Disabled controls name the missing dimension.</p>
        <noscript><p className="filter-note">Without JavaScript, submitting preserves filter state in the URL while the full published set remains visible.</p></noscript>
      </aside>

      <article className="trend-plane" aria-live="polite">
        <header>
          <p className="eyebrow">Claim boundary</p>
          <h2>{filtered.heading}</h2>
          {filtered.missingRequirement && <p className="gate-note" role="status">{filtered.missingRequirement}</p>}
        </header>

        {filtered.mode === "empty" || filtered.snapshots.length === 0 ? (
          <section className="empty-atlas" aria-labelledby="empty-title">
            <span className="status-mark" aria-hidden="true" />
            <div>
              <h3 id="empty-title">{view.mode === "empty" ? "No analysis is visible yet." : "No published snapshot matches."}</h3>
              <p>{view.mode === "empty" ? "A conference appears only after its source, record set, classification audit, and provenance pass publication gates." : "Change or clear a filter to return to the validated published set."}</p>
            </div>
          </section>
        ) : filtered.snapshots.map((snapshot) => (
          <section className="snapshot-strip" aria-labelledby={`${snapshot.venueSlug}-${snapshot.year}-title`} key={`${snapshot.venue}-${snapshot.year}`}>
            <div className="section-line">
              <div><p className="eyebrow">{snapshot.periodLabel}</p><h3 id={`${snapshot.venueSlug}-${snapshot.year}-title`}>{snapshot.venue} hotspots</h3></div>
              <span>Denominator: {snapshot.denominatorLabel}</span>
            </div>
            {(snapshot.experimentalThemeCount > 0 || snapshot.withheldThemeCount > 0) && (
              <p className="filter-note">
                Preliminary semantic distribution: {snapshot.experimentalThemeCount} experimental and {snapshot.withheldThemeCount} withheld themes.
              </p>
            )}
            <TopicShareChart rows={snapshot.topics} denominator={snapshot.includedCount} />
          </section>
        ))}

        {!filtered.trendWidgetsVisible && filtered.mode !== "empty" && filtered.snapshots.length > 0 && (
          <section className="withheld-widget" aria-label="Trend widgets unavailable">
            <p className="data-label">WITHHELD</p>
            <h3>Time series and year-over-year claims</h3>
            <p>Three consecutive releases with the same venue, track, taxonomy, and metric contract are required.</p>
          </section>
        )}
      </article>
    </div>
  );
}
