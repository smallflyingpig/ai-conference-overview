import { describe, expect, it } from "vitest";

import { loadAuthoredAwardContent } from "../src/lib/authored-award-content";
import { loadOverview } from "../src/lib/data";

describe("authored award Chinese content", () => {
  it("loads all release-bound award readings when the full content bundle is absent", async () => {
    const release = await loadOverview("ACL", 2026);
    expect(release).not.toBeNull();

    const content = await loadAuthoredAwardContent(release!);
    const verifiedAwardIds = release!.overview.awards
      .filter((award) => award.status === "verified")
      .map((award) => award.paper_id)
      .sort((left, right) => left.localeCompare(right));

    expect(content.awardDeepReads).toHaveLength(30);
    expect(
      content.awardDeepReads
        .map((reading) => reading.paper_id)
        .sort((left, right) => left.localeCompare(right)),
    ).toEqual(verifiedAwardIds);
  });
});
