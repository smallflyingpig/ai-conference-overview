import React from "react";

import type { DeepRead } from "../lib/evidence";
import { evidenceLabel, evidenceTone } from "../lib/evidence";

interface Props { deepRead: DeepRead }

export default function AwardEvidenceSections({ deepRead }: Props) {
  const sections = [
    ["研究问题", [deepRead.research_problem]],
    ["主要贡献", [deepRead.contribution]],
    ["方法", [deepRead.method_summary]],
    ["数据 / 训练设置", deepRead.data_training_setup],
    ["与既有工作的差异", deepRead.prior_work_differences],
    ["可复现性评估", deepRead.reproducibility_assessment],
    ["对后续研究的启发", deepRead.transferable_implications],
    ["为什么重要", deepRead.why_it_matters],
    ["局限", deepRead.limitations],
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
            {claim.source_urls.map((url, index) => <a href={url} key={url}>来源 {index + 1}</a>)}
          </span>
        </div>
      </article>)}
    </section>)}
  </div>;
}
