import { fileURLToPath } from "node:url";

import { beforeAll, describe, expect, it } from "vitest";

import { loadChineseContent, type LoadedChineseContent } from "../src/lib/content-data";
import { loadOverview, type LoadedOverview } from "../src/lib/data";
import { buildAwardChineseReading } from "../src/lib/paper-reading";

const releaseRoot = fileURLToPath(
  new URL("./fixtures/task9-release", import.meta.url),
);
const contentRoot = fileURLToPath(
  new URL("./fixtures/task-content", import.meta.url),
);

let release: LoadedOverview;
let content: LoadedChineseContent;

beforeAll(async () => {
  const loadedRelease = await loadOverview("ACL", 2026, releaseRoot, "long");
  if (loadedRelease == null) throw new Error("release fixture is unavailable");
  const loadedContent = await loadChineseContent(loadedRelease, contentRoot);
  if (loadedContent == null) throw new Error("Chinese content fixture is unavailable");
  release = loadedRelease;
  content = loadedContent;
});

describe("award Chinese reading model", () => {
  it("presents the complete learning sequence for an award paper", () => {
    const reading = buildAwardChineseReading(release, content, "paper-a");

    expect(reading.quickRead).toEqual({
      researchProblem: "论文研究模型在复杂任务中的稳定表现。",
      coreMethod: "作者提出分阶段分析与动态调整方法。",
      mainFinding: "实验显示该方法改善了主要任务表现。",
    });
    expect(reading.abstractZh).toContain("复杂任务");
    expect(reading.sections.map((section) => section.heading)).toEqual([
      "研究背景",
      "方法怎么做",
      "为什么值得关注",
      "局限与适用范围",
      "对后续研究的启发",
    ]);
    expect(reading.sections.every((section) => section.paragraphs.length > 0)).toBe(true);
  });

  it("fails closed when an award paper has no matching Chinese deep read", () => {
    expect(() => buildAwardChineseReading(release, content, "paper-z"))
      .toThrow(/缺少获奖论文中文解读/);
  });
});
