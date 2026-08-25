import React from "react";

import type { TopicShareRow } from "../lib/views";

interface Props {
  rows: TopicShareRow[];
  denominator: number;
}

export default function TopicShareChart({ rows, denominator }: Props) {
  return (
    <div className="distribution-pair">
      <div
        className="topic-ruler"
        role="img"
        aria-label={`${denominator} 篇论文的主要主题占比`}
      >
        {rows.map((row) => (
          <div className="topic-ruler-row" key={row.topic}>
            <div className="topic-ruler-label">
              <span>{row.topicLabel}</span>
              <strong data-chart-value={row.shareLabel}>{row.shareLabel}</strong>
            </div>
            <span className="topic-ruler-track" aria-hidden="true">
              <span style={{ width: row.shareLabel }} />
            </span>
          </div>
        ))}
      </div>
      <div className="topic-table-wrap">
        <table>
          <caption>主要主题（primary topic）分布，共统计 {denominator} 篇论文。</caption>
          <thead>
            <tr><th scope="col">主要主题</th><th scope="col">论文数</th><th scope="col">占比</th></tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.topic}><th scope="row">{row.topicLabel}</th><td>{row.paperCount}</td><td>{row.shareLabel}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
