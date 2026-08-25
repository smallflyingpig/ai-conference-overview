import { describe, expect, it } from "vitest";

import { projectPath } from "../src/lib/paths";

describe("projectPath", () => {
  it("joins routes beneath a Project Pages base without dropping the separator", () => {
    expect(projectPath("/ai-conference-overview", "trends/"))
      .toBe("/ai-conference-overview/trends/");
  });

  it("returns a slash-terminated project root", () => {
    expect(projectPath("/ai-conference-overview/", ""))
      .toBe("/ai-conference-overview/");
  });

  it("fails safe to the configured Project Pages base when Astro exposes root BASE_URL", () => {
    expect(projectPath("/", "awards/award-a"))
      .toBe("/ai-conference-overview/awards/award-a/");
  });
});
