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
        <p className="eyebrow">证据筛选</p>
        <h1 id="filter-title">筛选已发布数据</h1>
        <form method="get" action={action} onSubmit={submit}>
          <label htmlFor="venue-filter">会议</label>
          <select
            id="venue-filter"
            name="venue"
            disabled={view.availableVenues.length === 0}
            value={filters.venue ?? ""}
            onChange={(event) => setFilters({ ...filters, venue: event.target.value || null })}
          >
            <option value="">{view.availableVenues.length === 0 ? "暂无已发布会议" : "全部已发布会议"}</option>
            {view.availableVenues.map((venue) => <option value={venue} key={venue}>{venue}</option>)}
          </select>
          <label htmlFor="year-filter">年份</label>
          <select
            id="year-filter"
            name="year"
            disabled={view.availableYears.length === 0}
            value={filters.year ?? ""}
            onChange={(event) => setFilters({ ...filters, year: event.target.value ? Number(event.target.value) : null })}
          >
            <option value="">{view.availableYears.length === 0 ? "暂无已发布年份" : "全部已发布年份"}</option>
            {view.availableYears.map((year) => <option value={year} key={year}>{year}</option>)}
          </select>
          <label htmlFor="theme-filter">主题</label>
          <select
            id="theme-filter"
            name="theme"
            disabled={view.availableThemes.length === 0}
            value={filters.theme ?? ""}
            onChange={(event) => setFilters({ ...filters, theme: event.target.value || null })}
          >
            <option value="">{view.availableThemes.length === 0 ? "暂无已分类主题" : "全部已分类主题"}</option>
            {view.availableThemes.map((theme) => <option value={theme} key={theme}>{view.snapshots.flatMap((snapshot) => snapshot.topics).find((row) => row.topic === theme)?.topicLabel ?? theme}</option>)}
          </select>
          <label htmlFor="modality-filter">模态</label>
          <select id="modality-filter" name="modality" disabled value="">
            <option value="">当前 release 未提供</option>
          </select>
          <button type="submit">应用筛选</button>
        </form>
        <p className="filter-note">这里只列出 validated artifact 中实际存在的字段；禁用项表示当前缺失的分析维度。</p>
        <noscript><p className="filter-note">未启用 JavaScript 时，提交操作只会把筛选条件保存在 URL 中，页面仍展示完整已发布数据。</p></noscript>
      </aside>

      <article className="trend-plane" aria-live="polite">
        <header>
          <p className="eyebrow">结论边界</p>
          <h2>{filtered.heading}</h2>
          {filtered.missingRequirement && <p className="gate-note" role="status">{filtered.missingRequirement}</p>}
        </header>

        {filtered.mode === "empty" || filtered.snapshots.length === 0 ? (
          <section className="empty-atlas" aria-labelledby="empty-title">
            <span className="status-mark" aria-hidden="true" />
            <div>
              <h3 id="empty-title">{view.mode === "empty" ? "尚无可展示的分析。" : "没有匹配的已发布 snapshot。"}</h3>
              <p>{view.mode === "empty" ? "只有 source、record set、classification audit 与 provenance 全部通过发布门禁后，会议分析才会出现。" : "请修改或清空筛选条件，返回经过验证的已发布数据。"}</p>
            </div>
          </section>
        ) : filtered.snapshots.map((snapshot) => (
          <section className="snapshot-strip" aria-labelledby={`${snapshot.venueSlug}-${snapshot.year}-title`} key={`${snapshot.venue}-${snapshot.year}`}>
            <div className="section-line">
              <div><p className="eyebrow">{snapshot.periodLabel}</p><h3 id={`${snapshot.venueSlug}-${snapshot.year}-title`}>{snapshot.venue} 热点</h3></div>
              <span>分母：{snapshot.denominatorLabel}</span>
            </div>
            {(snapshot.experimentalThemeCount > 0 || snapshot.withheldThemeCount > 0) && (
              <p className="filter-note">
                初步语义分布：{snapshot.experimentalThemeCount} 个实验性主题，{snapshot.withheldThemeCount} 个暂缓发布主题。
              </p>
            )}
            <TopicShareChart rows={snapshot.topics} denominator={snapshot.includedCount} />
          </section>
        ))}

        {!filtered.trendWidgetsVisible && filtered.mode !== "empty" && filtered.snapshots.length > 0 && (
          <section className="withheld-widget" aria-label="Trend 组件暂不可用">
            <p className="data-label">暂缓发布</p>
            <h3>时间序列与 year-over-year 结论</h3>
            <p>需要同一会议、track、taxonomy 与 metric contract 下连续三个年份的 release。</p>
          </section>
        )}
      </article>
    </div>
  );
}
