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

test("ACL 2026 中文页面保留 provenance 与表格 fallback", async ({ page }, testInfo) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/conferences/acl/2026/");

  await expect(page.getByRole("heading", { name: "ACL 2026 长论文" })).toBeVisible();
  await expect(page.getByRole("link", { name: "ACL Anthology BibTeX" })).toBeVisible();
  await expect(page.getByRole("table")).toContainText("Primary topic 分布");
  await expect(page.getByText("2026 单年 snapshot", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("acl-overview.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("方法论页面用中文呈现可审计 classification lineage", async ({ page }, testInfo) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/methodology/");

  await expect(page.getByRole("heading", { name: "分类 lineage" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "全主题复核链" })).toBeVisible();
  await expect(page.getByText("Assignments SHA-256", { exact: true })).toBeVisible();
  await expect(page.locator(".lineage-stages > li")).toHaveCount(2);
  await page.screenshot({ path: testInfo.outputPath("methodology.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("研究进展页面用中文叙述并保留五条英文关键词 lane", async ({ page }) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/advances/");

  for (const heading of [
    "文本 LLM",
    "多模态模型",
    "推理与 Agents",
    "数据 / Pretraining / Post-training",
    "评测 / Safety / Interpretability",
  ]) {
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
  await expect(
    page.getByRole("link", { name: /KoCo: Conditioning Language Model Pre-training/ }).first(),
  ).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("获奖论文索引进入中文解读并保留原始英文证据", async ({ page }) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/awards/");

  await expect(page.locator(".award-plate")).toHaveCount(30);
  const detailLink = page.getByRole("link", { name: "阅读详细解读" }).first();
  await expect(detailLink).toHaveAttribute("href", new RegExp(`^${basePath}awards/award-[0-9a-f]{64}/$`));
  await detailLink.click();
  await expect(page.getByRole("heading", { name: "核心解读" })).toBeVisible();
  await expect(page.getByText("查看原始英文 DeepRead")).toBeVisible();
  await expect(page.getByRole("link", { name: "官方获奖证据" })).toBeVisible();
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

  await expect(page.getByRole("navigation", { name: "主导航" })).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: testInfo.outputPath("home-mobile.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});
