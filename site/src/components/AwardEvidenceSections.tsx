import React from "react";

import type { DeepRead } from "../lib/evidence";
import { evidenceLabel, evidenceTone } from "../lib/evidence";

interface Props { deepRead: DeepRead }

export default function AwardEvidenceSections({ deepRead }: Props) {
  const sections = [
    ["Research problem", [deepRead.research_problem]],
    ["Contribution", [deepRead.contribution]],
    ["Method", [deepRead.method_summary]],
    ["Data / training setup", deepRead.data_training_setup],
    ["Differences from prior work", deepRead.prior_work_differences],
    ["Reproducibility assessment", deepRead.reproducibility_assessment],
    ["Transferable implications", deepRead.transferable_implications],
    ["Why it matters", deepRead.why_it_matters],
    ["Limitations", deepRead.limitations],
  ] as const;
  return <div className="deep-read-sections">
    {sections.map(([label, claims]) => <section key={label} className="why-ledger">
      <h2>{label}</h2>
      {claims.map((claim, claimIndex) => <article key={`${label}-${claimIndex}`}>
        <span className={`evidence-badge evidence-badge--${evidenceTone(claim.evidence_type)}`}>
          {evidenceLabel(claim.evidence_type)}
        </span>
        <p>{claim.claim}</p>
        <div>
          {claim.locator && <small>{claim.locator}</small>}
          <span className="claim-sources">
            {claim.source_urls.map((url, index) => <a href={url} key={url}>Source {index + 1}</a>)}
          </span>
        </div>
      </article>)}
    </section>)}
  </div>;
}
