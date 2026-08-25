import React from "react";

import { type MethodDiagram } from "../lib/evidence";

interface Props { diagram: MethodDiagram }

export default function AwardMethodDiagram({ diagram }: Props) {
  const width = 760;
  const rowY = 92;
  const step = diagram.nodes.length > 1 ? 620 / (diagram.nodes.length - 1) : 0;
  const positions = new Map(
    diagram.nodes.map((node, index) => [node.identifier, { x: 70 + index * step, y: rowY }]),
  );
  return (
    <figure className="method-plate">
      <svg viewBox={`0 0 ${width} 190`} role="img" aria-label="论文方法示意图">
        <defs>
          <marker id="method-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" />
          </marker>
        </defs>
        {diagram.edges.map((edge) => {
          const start = positions.get(edge.source)!;
          const end = positions.get(edge.target)!;
          return (
            <g key={`${edge.source}-${edge.target}`} data-method-edge={`${edge.source}-${edge.target}`}>
              <line x1={start.x + 58} y1={start.y} x2={end.x - 58} y2={end.y} markerEnd="url(#method-arrow)" />
              <title>{edge.data_flow_rationale}</title>
            </g>
          );
        })}
        {diagram.nodes.map((node) => {
          const position = positions.get(node.identifier)!;
          return (
            <g key={node.identifier} data-method-node={node.identifier} transform={`translate(${position.x} ${position.y})`}>
              <rect x="-58" y="-38" width="116" height="76" />
              <text textAnchor="middle" y="-2">{node.label}</text>
              <text className="method-section" textAnchor="middle" y="18">{node.paper_section}</text>
            </g>
          );
        })}
      </svg>
      <figcaption className="graph-fallback">
        <strong>方法流程（文字版）</strong>
        <div>
          <p>主要步骤</p>
          <ul>{diagram.nodes.map((node) => <li key={node.identifier}>{node.label} — {node.paper_section}</li>)}</ul>
          <p>步骤之间的关系</p>
          {diagram.edges.length === 0 ? <p>论文没有说明步骤之间的关系。</p> : (
            <ul>{diagram.edges.map((edge) => (
              <li key={`${edge.source}-${edge.target}`}>
                {diagram.nodes.find((node) => node.identifier === edge.source)!.label} → {diagram.nodes.find((node) => node.identifier === edge.target)!.label} — {edge.data_flow_rationale}
              </li>
            ))}</ul>
          )}
        </div>
      </figcaption>
    </figure>
  );
}
