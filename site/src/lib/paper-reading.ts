import type { LoadedChineseContent } from "./content-data";
import type { LoadedOverview } from "./data";

export interface AwardChineseReadingSection {
  heading: string;
  paragraphs: string[];
}

export interface AwardChineseReading {
  paperId: string;
  quickRead: {
    researchProblem: string;
    coreMethod: string;
    mainFinding: string;
  };
  abstractZh: string;
  sections: AwardChineseReadingSection[];
}

export function buildAwardChineseReading(
  release: LoadedOverview,
  content: LoadedChineseContent,
  paperId: string,
): AwardChineseReading {
  const paper = release.papers.find((candidate) => candidate.paper_id === paperId);
  const deepRead = content.awardDeepReads.find((candidate) => candidate.paper_id === paperId);
  if (paper == null || deepRead == null) {
    throw new Error(`缺少获奖论文中文解读：${paperId}`);
  }

  return {
    paperId,
    quickRead: {
      researchProblem: deepRead.quick_read.research_problem,
      coreMethod: deepRead.quick_read.core_method,
      mainFinding: deepRead.quick_read.main_finding,
    },
    abstractZh: deepRead.abstract_zh,
    sections: [
      { heading: "研究背景", paragraphs: deepRead.background },
      { heading: "方法怎么做", paragraphs: deepRead.method_walkthrough },
      { heading: "为什么值得关注", paragraphs: deepRead.why_it_matters },
      { heading: "局限与适用范围", paragraphs: deepRead.limitations },
      { heading: "对后续研究的启发", paragraphs: deepRead.research_implications },
    ],
  };
}
