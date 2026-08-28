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

test("ACL 2026 中文页面保留数据来源与表格 fallback", async ({ page }, testInfo) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/conferences/acl/2026/");

  await expect(page.getByRole("heading", { name: "ACL 2026 长论文" })).toBeVisible();
  await expect(page.getByRole("link", { name: "ACL Anthology BibTeX" })).toBeVisible();
  await expect(page.getByRole("table")).toContainText("主要主题（primary topic）分布");
  await expect(page.getByText("2026 单年概览", { exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("acl-overview.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("ICML 2025 单年分析可以检索并进入英文详情", async ({ page }) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto(`${basePath}conferences/icml/2025/`);

  await expect(page.getByRole("heading", { name: "ICML 2025 主会论文" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "主题分布" })).toBeVisible();
  await expect(page.getByText("3330", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("预发布论文清单", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "查看本届 8 篇获奖论文解读" })).toBeVisible();

  await page.getByRole("link", { name: "浏览 ICML 2025 论文" }).click();
  await page.getByLabel("会议").selectOption("ICML");
  await page.getByLabel("搜索论文").fill("Lightweight Protocols for Distributed Private Quantile Estimation");
  await expect(page.locator("[data-paper-row]:visible")).toHaveCount(1);
  await page.locator("[data-paper-row]:visible h3 a").click();
  await expect(page.getByRole("heading", { name: "Lightweight Protocols for Distributed Private Quantile Estimation" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "英文摘要" })).toBeVisible();
  await expect(page.getByRole("link", { name: "官方页面" })).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("ACL 2026 Findings 论文详情优先呈现中文摘要和阅读要点", async ({ page }) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto(
    `${basePath}papers/paper-a607052ca803a5e814d992ba303dccbb82dfbcd483a8a95ebc64a70a9589f7b1/`,
  );

  await expect(page.getByText("ACL 2026 · Findings", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "一句话看懂" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "中文摘要" })).toBeVisible();
  for (const heading of ["研究问题", "核心方法", "主要发现", "适用范围"]) {
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
  const english = page.locator(".paper-original-abstract");
  await expect(english).not.toHaveAttribute("open", "");
  await english.getByText("查看英文摘要", { exact: true }).click();
  await expect(english.locator("[data-english-abstract]")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  expect(consoleErrors).toEqual([]);
});

test("会议概览菜单进入会议列表而不是单个会议", async ({ page }, testInfo) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto(basePath);
  if (testInfo.project.name === "mobile-chromium") {
    await page.getByRole("button", { name: "打开主导航" }).click();
  }
  await page.getByRole("link", { name: "会议概览" }).click();

  await expect(page).toHaveURL(`${basePath}conferences/`);
  await expect(page.getByRole("heading", { name: "选择会议和年份" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ACL 2026 长论文", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ACL 2026 Findings", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ICML 2025 主会论文", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /查看 ACL 2026 长论文/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /查看 ACL 2026 Findings/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /查看 ICML 2025 主会论文/ })).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("方法说明页面用中文呈现分类处理记录", async ({ page }, testInfo) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/methodology/");

  await expect(page.getByRole("heading", { name: "分类处理记录" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "全主题复查过程" })).toBeVisible();
  await expect(page.getByText("分类结果 SHA-256", { exact: true })).toBeVisible();
  await expect(page.locator(".lineage-stages > li")).toHaveCount(2);
  await page.screenshot({ path: testInfo.outputPath("methodology.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("研究进展页面按会议分开浏览并保留可分享地址", async ({ page }) => {
  const consoleErrors = watchConsoleErrors(page);
  await page.goto("/ai-conference-overview/advances/");

  await expect(page.getByRole("heading", { name: "ACL 2026", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ICML 2025", exact: true })).toBeVisible();
  await expect(page.locator(".advance-conference-detail:visible")).toHaveCount(0);
  await page.getByRole("link", { name: "ICML 2025 · 5 条主线", exact: true }).click();
  await expect(page).toHaveURL(/\/advances\/\?venue=ICML&year=2025&track=main#advance-ICML-2025-main$/);
  await expect(page.getByRole("link", { name: "ICML 2025 · 5 条主线", exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(page.getByRole("heading", { name: "ICML 2025 研究进展", exact: true })).toBeVisible();
  await expect(page.locator(".advance-conference-detail:visible .advance-lane")).toHaveCount(5);
  for (const heading of [
    "文本 LLM",
    "多模态模型",
    "推理与 Agents",
    "数据与训练（Pretraining / Post-training）",
    "评测、Safety 与 Interpretability",
  ]) {
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
  expect(consoleErrors).toEqual([]);
});

test("获奖论文索引进入中文解读并保留英文原文参考", async ({ page }, testInfo) => {
  const consoleErrors = watchConsoleErrors(page);
  if (testInfo.project.name === "mobile-chromium") {
    await page.setViewportSize({ width: 390, height: 844 });
  }
  await page.goto("/ai-conference-overview/awards/");

  await expect(page.locator(".award-plate")).toHaveCount(38);
  const detailLink = page.getByRole("link", { name: "查看详细解读" }).first();
  await expect(detailLink).toHaveAttribute("href", new RegExp(`^${basePath}awards/award-[0-9a-f]{64}/$`));
  await detailLink.click();
  await expect(page.getByRole("heading", { name: "三分钟读懂" })).toBeVisible();
  await expect(page.getByText("英文原文参考")).toBeVisible();
  await page.getByText("英文原文参考").click();
  await expect(page.getByText("节点编号只用于核对下方关系，不代表先后顺序。")).toBeVisible();
  const methodLabels = page.locator(
    "[data-method-node] > text:not(.method-section), [data-method-node] .method-node-label",
  );
  await expect(methodLabels.first()).toBeVisible();
  const methodLabelSizes = await methodLabels.evaluateAll((labels) =>
    labels.map((label) => Number.parseFloat(getComputedStyle(label).fontSize)),
  );
  expect(
    methodLabelSizes.every((size) => size >= 16),
    "流程图中的步骤名称应使用适合连续阅读的字号",
  ).toBe(true);
  const pageOverflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(pageOverflow, "展开方法流程后页面不应出现横向溢出").toBeLessThanOrEqual(1);
  await expect(page.getByRole("link", { name: "官方获奖页面" })).toBeVisible();
  expect(consoleErrors).toEqual([]);
});

test("ICML 2025 概览可以直接进入本届获奖论文并保留筛选地址", async ({ page }) => {
  await page.goto("/ai-conference-overview/conferences/icml/2025/");

  const awardEntry = page.getByRole("link", { name: "查看本届 8 篇获奖论文解读" });
  await expect(awardEntry).toHaveAttribute(
    "href",
    `${basePath}awards/?venue=ICML&year=2025#award-ICML-2025`,
  );
  await awardEntry.click();

  await expect(page).toHaveURL(/\/awards\/\?venue=ICML&year=2025#award-ICML-2025$/);
  await expect(page.getByRole("heading", { name: "ICML 2025", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "ACL 2026", exact: true })).toBeHidden();
  await expect(page.getByRole("link", { name: "ICML 2025 · 8 篇" })).toHaveAttribute(
    "aria-current",
    "page",
  );
});

test("ICML 2025 概览可以直接进入本届研究进展", async ({ page }) => {
  await page.goto("/ai-conference-overview/conferences/icml/2025/");

  await expect(page.getByRole("link", { name: "查看 ICML 2025 研究进展" })).toHaveAttribute(
    "href",
    `${basePath}advances/?venue=ICML&year=2025&track=main#advance-ICML-2025-main`,
  );
});

test("主导航使用明确的获奖论文解读名称", async ({ page }) => {
  await page.goto("/ai-conference-overview/papers/");
  const menuButton = page.getByRole("button", { name: "打开主导航" });
  if (await menuButton.isVisible()) await menuButton.click();
  await expect(page.getByRole("link", { name: "获奖论文解读", exact: true })).toBeVisible();
});

test("公开页面使用自然中文而不是内部工程术语", async ({ page }) => {
  const routes = new Set([
    basePath,
    `${basePath}conferences/`,
    `${basePath}conferences/acl/2026/`,
    `${basePath}conferences/icml/2025/`,
    `${basePath}trends/`,
    `${basePath}advances/`,
    `${basePath}awards/`,
    `${basePath}papers/`,
    `${basePath}methodology/`,
  ]);
  await page.goto(`${basePath}awards/`);
  for (const href of await page.getByRole("link", { name: "查看详细解读" }).evaluateAll(
    (links) => links.map((link) => link.getAttribute("href")).filter((href): href is string => href != null),
  )) {
    routes.add(href);
  }
  const awkwardTerms = ["门禁", "约束", "核验", "结论", "证据", "审计", "契约", "工件", "赋值"];
  const translationese = [
    "语料 conditioning",
    "评测 setting",
    "某一种 recipe",
    "统一 effect size",
    "joint-modal safety",
    "train/deploy distribution gap",
    "小 learner",
    "hard alignment",
    "open-mic 外部效度",
    "model preference",
    "paper-reported",
  ];

  for (const route of routes) {
    await page.goto(route);
    const visibleText = await page.locator("body").innerText();
    for (const term of [...awkwardTerms, ...translationese]) {
      expect(visibleText, `${route} should not expose ${term}`).not.toContain(term);
    }
  }

  await page.goto(`${basePath}awards/`);
  await expect(page.getByRole("heading", { name: /先确认获奖信息，?\s*再分析论文价值。?/ })).toBeVisible();
  await page.goto(`${basePath}methodology/`);
  await expect(page.getByRole("heading", { name: /每个数字，?\s*都能找到来源和计算方法。?/ })).toBeVisible();
});

test("internal links stay within the project base path and resolve", async ({ page }) => {
  const consoleErrors = watchConsoleErrors(page);
  const routes = [
    basePath,
    `${basePath}conferences/`,
    `${basePath}conferences/acl/2026/`,
    `${basePath}conferences/icml/2025/`,
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

test("mobile navigation starts compact and expands on demand", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "mobile-only layout acceptance");
  const consoleErrors = watchConsoleErrors(page);
  await page.goto(basePath);

  const menuButton = page.locator(".nav-toggle");
  const navigation = page.getByRole("navigation", { name: "主导航" });
  await expect(menuButton).toBeVisible();
  await expect(menuButton).toHaveAccessibleName("打开主导航");
  await expect(menuButton).toHaveAttribute("aria-expanded", "false");
  await expect(navigation).toBeHidden();

  await menuButton.click();
  await expect(menuButton).toHaveAttribute("aria-expanded", "true");
  await expect(menuButton).toHaveAccessibleName("关闭主导航");
  await expect(navigation).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await page.screenshot({ path: testInfo.outputPath("home-mobile.png"), fullPage: true });
  expect(consoleErrors).toEqual([]);
});

test("mobile first screens prioritize content over oversized headings", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "mobile-chromium", "mobile-only layout acceptance");
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto(basePath);
  const homeHeadingSize = await page.locator(".hero h1").evaluate((heading) =>
    Number.parseFloat(getComputedStyle(heading).fontSize),
  );
  expect(homeHeadingSize).toBeLessThanOrEqual(44);

  for (const route of ["papers/", "awards/", "advances/", "methodology/"]) {
    await page.goto(`${basePath}${route}`);
    const thesisHeight = await page.locator(".page-thesis").evaluate((thesis) =>
      thesis.getBoundingClientRect().height,
    );
    expect(thesisHeight, `${route} should expose content in the first screen`).toBeLessThanOrEqual(330);
    const dimensions = await page.evaluate(() => ({
      innerWidth: window.innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
    }));
    const overflow = dimensions.scrollWidth - dimensions.innerWidth;
    expect(dimensions.innerWidth, `${route} should preserve the configured phone viewport`).toBe(390);
    expect(overflow, `${route} should fit a phone viewport`).toBeLessThanOrEqual(1);
  }
});
