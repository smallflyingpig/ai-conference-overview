import React from "react";

import { evidenceLabel, evidenceTone, type ResultClaim } from "../lib/evidence";

interface Props { claim: ResultClaim }

export default function AwardResultClaim({ claim }: Props) {
  return (
    <article>
      <span className={`evidence-badge evidence-badge--${evidenceTone(claim.evidence_type)}`}>
        <span className="evidence-badge__mark" aria-hidden="true" />
        {evidenceLabel(claim.evidence_type)}
      </span>
      <div>
        <h3>{claim.metric}: {claim.value}</h3>
        <p>{claim.claim}</p>
      </div>
      <div>
        <dl>
          <div><dt>评测 setting</dt><dd>{claim.evaluation_setting}</dd></div>
          <div><dt>证据 locator</dt><dd>{claim.locator}</dd></div>
        </dl>
        <div className="claim-sources">
          {claim.source_urls.map((url, index) => (
            <a href={url} key={url}>打开来源 {index + 1}</a>
          ))}
        </div>
      </div>
    </article>
  );
}
