# Natural Chinese editing evaluation

The micro-test used the reader-facing website scenario in
`polishing-chinese-scenarios.md`, including the user's explicit banned terms.
Each run used a fresh context. A response failed naturalness when it preserved
the literal calque “迁移启示 / 可迁移启示”.

## No-guidance control — 0/5 naturalness passes

1. “本页面汇总 ACL 2026 获奖论文，并以官方来源为准。仅收录已获官方信息支持的论文；信息尚不完整的条目暂不展示。点击‘深度解读’，可查看论文原文披露的结果及其可迁移启示。”
2. “本页面汇总 ACL 2026 获奖论文，仅收录已获官方来源确认的内容；信息不完整或出处不明确的记录暂不展示。点击‘深度阅读’，可查看论文报告的结果及其可迁移启示。”
3. “本页面汇总 ACL 2026 获奖论文，仅收录经官方来源确认的内容；信息尚不完整的条目暂不展示。点击‘深度解读’，可查看论文报告的实验结果及其迁移启示。”
4. “本页面汇总 ACL 2026 获奖论文，仅收录可由官方来源确认的内容；信息尚不完整的条目暂不展示。点击‘深度解读’，可查看论文报告的实验结果及其可迁移启示。”
5. “本页面汇总 ACL 2026 获奖论文，仅收录已由官方来源确认的内容；信息尚不完整的记录暂不展示。点击‘深度解读’，可查看论文原文披露的结果及其可迁移启示。”

## Skill-guided variant — 5/5 passes

1. “本页面汇集经官方来源确认的 ACL 2026 获奖论文；来源信息不完整的记录暂不展示。点击‘深度解读’，可查看论文报告的结果，以及对后续研究可能带来的启发。”
2. “本页面整理 ACL 2026 获奖论文。只有得到官方来源明确支持的论文才会纳入主要内容；官方信息不足的记录暂不展示。点击‘深度解读’，可查看论文报告的结果及其对后续研究的启发。”
3. “本页面汇集经官方渠道确认的 ACL 2026 获奖论文。仅收录有官方信息支持的论文；相关信息不足的记录暂不展示。点击‘论文深读’，可查看论文报告的结果及其对后续研究的启发。”
4. “本页面整理 ACL 2026 获奖论文，所有收录内容均以官方来源为准。官方信息不足的条目暂不展示。点击‘深入解读’，可查看论文作者报告的结果，以及这些工作对后续研究的启发。”
5. “本页面仅收录可由官方来源确认的 ACL 2026 获奖论文；官方信息不足或不符合收录标准的记录暂不展示。点击‘论文深读’，可查看论文报告的结果及其对后续研究的启发。”

All ten responses preserved the official-source and temporary-withholding
boundaries. All five skill-guided responses also removed the banned terms and
the literal transfer-implication calque.
