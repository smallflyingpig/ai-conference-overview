import { expect, test, type Page } from "@playwright/test";

const basePath = "/ai-conference-overview/";

function watchConsoleErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  return errors;
}

test("ACL 2026 page exposes provenance and table fallback", async ({ page }, testInfo) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/conferences/acl/2026/");

  await expect(page.getByRole("heading", { name: /ACL 2026 long papers/i })).toBeVisible();
  await expect(page.getByRole("link", { name: "ACL Anthology BibTeX" })).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Primary-topic distribution");
  await expect(page.getByText(/one-year snapshot/i)).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("acl-overview.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("methodology renders auditable classification lineage", async ({ page }, testInfo) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/methodology/");

  await expect(page.getByRole("heading", { name: "Classification lineage" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Full-theme review chain" })).toBeVisible();
  await expect(page.getByText("Assignments SHA-256", { exact: true })).toBeVisible();
  await expect(page.locator(".lineage-stages > li")).toHaveCount(2);
  await page.screenshot({ path: testInfo.outputPath("methodology.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("advances keeps all five evidence lanes visible", async ({ page }) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/advances/");

  for (const heading of [
    "Text LLMs",
    "Multimodal Models",
    "Reasoning and Agents",
    "Data / Pretraining / Post-training",
    "Evaluation / Safety / Interpretability",
  ]) {
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
  await expect(
    page.getByRole("link", { name: /KoCo: Conditioning Language Model Pre-training/ }).first(),
  ).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("award index links to a fully evidenced detail reading", async ({ page }) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/awards/");

  await expect(page.locator(".award-plate")).toHaveCount(30);
  const detailLink = page.getByRole("link", { name: "Read evidence plate" }).first();
  await expect(detailLink).toHaveAttribute("href", new RegExp(`^${basePath}awards/award-[0-9a-f]{64}/$`));
  await detailLink.click();
  await expect(page.getByRole("heading", { name: "Paper-reported results" })).toBeVisible();
  await expect(page.getByRole("img", { name: "Original explanatory method diagram" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Official award evidence" })).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("internal links stay within the project base path and resolve", async ({ page }) => {
  const consoleErrors = watchConsoleErrors(page);
  const routes = [
    basePath,
    `${basePath}conferences/acl/2026/`,
    `${basePath}trends/`,
    `${basePath}advances/`,
    `${basePath}awards/`,
    `${basePath}papers/`,
    `${basePath}methodology/`,
  ];
  const internalLinks = new Set<string>();

  for (const route of routes) {
    const response = await page.goto(route);
    expect(response?.ok(), `${route} should return a successful response`).toBe(true);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow, `${route} should fit the configured viewport`).toBeLessThanOrEqual(1);
    const hrefs = await page.locator("a[href]").evaluateAll((links) =>
      links.map((link) => link.getAttribute("href")).filter((href): href is string => href != null),
    );
    for (const href of hrefs) {
      if (href.startsWith("/")) {
        expect(href, `${route} contains a root-relative link outside the project base`).toMatch(
          /^\/ai-conference-overview(?:\/|$)/,
        );
        internalLinks.add(href);
      }
    }
  }

  for (const href of internalLinks) {
    const response = await page.request.get(href);
    expect(response.ok(), `${href} should resolve`).toBe(true);
  }
  expect(consoleErrors).toEqual([]);
});

test("mobile navigation and content fit the viewport", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "mobile-only layout acceptance");
  const consoleErrors = watchConsoleErrors(page);
  await page.goto(basePath);

  await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: testInfo.outputPath("home-mobile.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});
