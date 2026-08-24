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
        aria-label={`Primary topic shares among ${denominator} included papers`}
      >
        {rows.map((row) => (
          <div className="topic-ruler-row" key={row.topic}>
            <div className="topic-ruler-label">
              <span>{row.topic}</span>
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
          <caption>Primary-topic distribution; denominator: {denominator} included papers.</caption>
          <thead>
            <tr><th scope="col">Primary topic</th><th scope="col">Papers</th><th scope="col">Share</th></tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.topic}><th scope="row">{row.topic}</th><td>{row.paperCount}</td><td>{row.shareLabel}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
