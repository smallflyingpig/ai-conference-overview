import { defineConfig, devices } from "@playwright/test";

const origin = "http://127.0.0.1:4321";

export default defineConfig({
  testDir: "./tests",
  testMatch: /visual\.spec\.ts/,
  outputDir: "test-results",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "line",
  use: {
    baseURL: origin,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"] },
    },
  ],
  webServer: {
    command: "npm run preview -- --host 127.0.0.1 --port 4321",
    url: `${origin}/ai-conference-overview/`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
