import fs from "node:fs";

import { test as setup } from "@playwright/test";

import { DEMO_AUTH_DIR, DEMO_STATE, DEMO_STORE_FILE, exploreDemo } from "./support";

/**
 * One demo sign-in for every viewer test. The demo entry is rate limited per IP (5 a minute), so
 * tests reuse this session instead of each pressing "Explore the demo".
 */
setup("sign in to the public demo once", async ({ page }) => {
  const storeId = await exploreDemo(page);
  fs.mkdirSync(DEMO_AUTH_DIR, { recursive: true });
  fs.writeFileSync(DEMO_STORE_FILE, JSON.stringify({ storeId }));
  await page.context().storageState({ path: DEMO_STATE });
});
