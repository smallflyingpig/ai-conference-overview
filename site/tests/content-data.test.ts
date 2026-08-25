import { cp, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { loadChineseContent } from "../src/lib/content-data";
import { paperSummaryZhSchema } from "../src/lib/content-schema";
import { loadOverview } from "../src/lib/data";

const releaseRoot = fileURLToPath(
  new URL("./fixtures/task9-release", import.meta.url),
);
const contentRoot = fileURLToPath(
  new URL("./fixtures/task-content", import.meta.url),
);

async function release() {
  const value = await loadOverview("ACL", 2026, releaseRoot, "long");
  if (value == null) throw new Error("release fixture is unavailable");
  return value;
}

describe("Chinese content loader", () => {
  it("loads only content bound to the selected release and papers hash", async () => {
    const content = await loadChineseContent(await release(), contentRoot);

    expect(content?.paperSummaries).toHaveLength(1);
    expect(content?.awardDeepReads).toHaveLength(1);
    expect(content?.paperSummaries[0].paper_id).toBe("paper-z");
    expect(content?.awardDeepReads[0].paper_id).toBe("paper-a");
  });

  it("rejects a pointer bound to another release generation", async () => {
    const temporary = await mkdtemp(join(tmpdir(), "content-loader-"));
    await cp(contentRoot, temporary, { recursive: true });
    const pointerPath = join(temporary, "acl", "2026-long", "current.json");
    const pointer = JSON.parse(await readFile(pointerPath, "utf8"));
    pointer.release_generation = `generations/${"f".repeat(64)}`;
    await writeFile(pointerPath, `${JSON.stringify(pointer)}\n`);

    await expect(loadChineseContent(await release(), temporary)).rejects.toThrow(
      /selected release/,
    );
  });

  it("rejects an artifact changed after the pointer was written", async () => {
    const temporary = await mkdtemp(join(tmpdir(), "content-loader-"));
    await cp(contentRoot, temporary, { recursive: true });
    const pointerPath = join(temporary, "acl", "2026-long", "current.json");
    const pointer = JSON.parse(await readFile(pointerPath, "utf8"));
    const summaries = join(
      temporary,
      "acl",
      "2026-long",
      pointer.generation,
      "paper-summaries.zh.jsonl",
    );
    await writeFile(summaries, "forged\n");

    await expect(loadChineseContent(await release(), temporary)).rejects.toThrow(
      /hash mismatch/,
    );
  });

  it("rejects unknown fields in public summary records", () => {
    expect(() =>
      paperSummaryZhSchema.parse({
        schema_version: "paper-summary-zh-v1",
        paper_id: "paper-z",
        route_key: `paper-${"a".repeat(64)}`,
        venue: "ACL",
        year: 2026,
        track: "long",
        source_title: "Title paper-z",
        source_abstract_sha256: "b".repeat(64),
        source_pdf_sha256: null,
        one_sentence: "一句话概括。",
        summary_zh: "摘要".repeat(80),
        research_problem: "研究问题。",
        core_method: "核心方法。",
        main_findings: "主要发现。",
        scope_and_limitations: "适用范围。",
        content_method: "title-abstract-grounded-summary-v1",
        unexpected: true,
      }),
    ).toThrow();
  });
});
