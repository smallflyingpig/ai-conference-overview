import React from "react";

import { type MethodDiagram } from "../lib/evidence";

interface Props { diagram: MethodDiagram }

export default function AwardMethodDiagram({ diagram }: Props) {
  const nodeReferences = new Map(
    diagram.nodes.map((node, index) => [node.identifier, `N${index + 1}`]),
  );
  return (
    <figure className="method-plate" aria-label="论文方法示意图">
      <header className="method-plate__header">
        <span className="data-label">Method map</span>
        <strong>论文方法流程</strong>
        <p>先看论文列出的方法节点，再沿下方关系逐条阅读。节点编号只用于核对下方关系，不代表先后顺序。</p>
      </header>
      <ul className="method-flow">
        {diagram.nodes.map((node) => {
          return (
            <li className="method-flow__node" key={node.identifier} data-method-node={node.identifier}>
              <span className="method-node-index" aria-hidden="true">{nodeReferences.get(node.identifier)}</span>
              <div>
                <strong className="method-node-label">{node.label} — {node.paper_section}</strong>
              </div>
            </li>
          );
        })}
      </ul>
      <figcaption className="method-connections">
        <strong>步骤之间的关系</strong>
        {diagram.edges.length === 0 ? <p>论文没有说明步骤之间的关系。</p> : (
          <ol>{diagram.edges.map((edge) => {
            const source = diagram.nodes.find((node) => node.identifier === edge.source)!;
            const target = diagram.nodes.find((node) => node.identifier === edge.target)!;
            return (
              <li key={`${edge.source}-${edge.target}`} data-method-edge={`${edge.source}-${edge.target}`}>
                <span className="method-edge-index" aria-hidden="true">
                  {nodeReferences.get(edge.source)} <b>→</b> {nodeReferences.get(edge.target)}
                </span>
                <span className="method-edge-summary">
                  {source.label} → {target.label} — {edge.data_flow_rationale}
                </span>
              </li>
            );
          })}</ol>
        )}
      </figcaption>
    </figure>
  );
}
