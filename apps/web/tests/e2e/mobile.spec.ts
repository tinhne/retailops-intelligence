import { expect, test } from "@playwright/test";

import { DEMO_STATE, demoStoreId, expectNoHorizontalScroll, openTopException } from "./support";

test.use({ storageState: DEMO_STATE });

/** 375 px smoke (DESIGN_SYSTEM: responsive from 360 px, no sideways scroll). */
test("core screens fit a 375 px phone", async ({ page }) => {
  const storeId = demoStoreId();
  await page.goto(`/s/${storeId}/overview`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoHorizontalScroll(page);

  for (const path of ["exceptions", "orders", "inventory", "imports", "copilot"]) {
    await page.goto(`/s/${storeId}/${path}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expectNoHorizontalScroll(page);
  }

  await openTopException(page, storeId);
  await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
  await expectNoHorizontalScroll(page);
});
