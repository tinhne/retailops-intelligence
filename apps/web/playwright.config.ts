import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests (T-081) against a running stack: the compose stack in CI, or the local dev
 * servers. Nothing is started here, so the same suite runs against any deployment.
 *
 *   E2E_BASE_URL         web origin (default http://localhost:3000)
 *   E2E_STAFF_PASSWORD   the DEMO_STAFF_PASSWORD the stack was seeded with (staff journeys)
 *   E2E_SCREENSHOTS=1    run only the README screenshot capture (@screenshots)
 *
 * The journey changes shared data (imports, a resolution), so tests run serially in one worker.
 */
const screenshots = Boolean(process.env.E2E_SCREENSHOTS);
// Applied per project so the setup project (the shared demo sign-in) always runs.
const selection = screenshots ? { grep: /@screenshots/ } : { grepInvert: /@screenshots/ };

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    locale: "en-US",
    timezoneId: "America/New_York",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /\.setup\.ts$/ },
    {
      name: "desktop",
      dependencies: ["setup"],
      ...selection,
      testIgnore: /mobile\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "mobile",
      dependencies: ["setup"],
      ...selection,
      testMatch: /mobile\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true },
    },
  ],
});
