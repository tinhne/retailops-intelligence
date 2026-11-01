import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { DEMO_STATE, demoStoreId, openTopException } from "./support";

/**
 * Accessibility review (T-083): axe-core with the WCAG 2.1 A/AA rule sets on every main screen,
 * plus keyboard checks. Serious and critical violations fail the test; the full results are
 * attached to the report for review.
 */
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

async function expectNoSeriousViolations(page: Page, screen: string): Promise<void> {
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  await test.info().attach(`axe-${screen}.json`, {
    body: JSON.stringify(results.violations, null, 2),
    contentType: "application/json",
  });
  const blocking = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.help} — ${v.nodes.map((n) => n.html.slice(0, 160)).slice(0, 3).join(" | ")}`);
  expect(blocking, `${screen}: serious or critical WCAG violations`).toEqual([]);
}

test("sign-in screen is accessible and keyboard operable", async ({ page }) => {
  await page.goto("/login");
  await expectNoSeriousViolations(page, "login");

  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Email")).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByLabel("Password", { exact: true })).toBeFocused();
});

test.describe("signed in as the demo viewer", () => {
  test.use({ storageState: DEMO_STATE });

  test("app screens have no serious WCAG 2.1 AA violations", async ({ page }) => {
    test.setTimeout(180_000);
    const storeId = demoStoreId();
    await page.goto(`/s/${storeId}/overview`);
    await expectNoSeriousViolations(page, "overview");

    for (const path of ["exceptions", "orders", "products", "inventory", "inventory/movements", "imports", "copilot", "admin/audit-log", "admin/settings"]) {
      await page.goto(`/s/${storeId}/${path}`);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expectNoSeriousViolations(page, path.replace("/", "-"));
    }

    await openTopException(page, storeId);
    await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
    await expectNoSeriousViolations(page, "exception-detail");
  });

  test("the skip link moves keyboard focus past the navigation", async ({ page }) => {
    await page.goto(`/s/${demoStoreId()}/overview`); // a fresh page load, as when a visitor opens a link
    await page.waitForLoadState("networkidle");
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Skip to content" });
    await expect(skip).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(skip).not.toBeFocused();
    await expect(page.locator("main")).toBeVisible();
  });
});
