# Natural Chinese editing scenarios

Each run uses a fresh context. Baseline runs do not load
`polishing-chinese-writing`; GREEN runs load it.

## Scenario 1 — reader-facing website copy

Rewrite naturally without changing the publication boundary:

> 本页面提供 ACL 2026 Award 证据核验门禁。只有通过官方来源约束的论文才进入结论层；未满足证据契约的记录将被 withheld。点击证据深读可查看 paper-reported 结果及 transfer implication。

Pass: ordinary Chinese carries the meaning; `Award`, `withheld`,
`paper-reported`, and `transfer implication` are translated or explained. The
result does not reuse “门禁 / 约束 / 核验 / 结论 / 证据” anywhere, including
button labels.

## Scenario 2 — quantitative research summary

Rewrite naturally without changing the sample, interval, or time boundary:

> 该主题通过质量门禁，但结论仍受单年快照约束。50 篇审计样本中 48 篇判断正确，Wilson 95% CI 下界为 0.865399。证据仅支持其为 ACL 2026 long paper 的高占比方向，不支持跨年 trending claim。

Pass: preserves 48/50, 0.865399, Wilson 95%, ACL 2026 long papers, and the
no-cross-year boundary. Avoids “门禁 / 结论 / 快照约束 / 审计样本 / 证据支持”.

## Scenario 3 — method detail with necessary English terms

Rewrite naturally while retaining exact identifiers:

> 分类 lineage 绑定 assignments SHA-256，并通过 audit registry 对样本完整性进行核验。primary topic share 是互斥口径，不能与 keyword prevalence 做等价结论。任何未通过 gate 的主题都应被标记为 experimental。

Pass: retains SHA-256 and explains the statistical distinction. Technical
English is retained only when it is an identifier or more precise than Chinese;
the surrounding prose reads naturally in Chinese.
