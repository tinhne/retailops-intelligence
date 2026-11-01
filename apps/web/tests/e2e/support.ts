import fs from "node:fs";
import path from "node:path";

import { expect, type Page } from "@playwright/test";

/** Saved demo-viewer session written by demo.setup.ts (git-ignored). */
export const DEMO_AUTH_DIR = path.join(__dirname, ".auth");
export const DEMO_STATE = path.join(DEMO_AUTH_DIR, "demo.json");
export const DEMO_STORE_FILE = path.join(DEMO_AUTH_DIR, "demo-store.json");

export function demoStoreId(): string {
  const { storeId } = JSON.parse(fs.readFileSync(DEMO_STORE_FILE, "utf8")) as { storeId: string };
  return storeId;
}

/** The DEMO_STAFF_PASSWORD the stack was seeded with. Staff journeys skip without it. */
export const staffPassword = process.env.E2E_STAFF_PASSWORD ?? "";

export const STAFF = {
  owner: "owner@kestrel.example",
  manager: "manager@kestrel.example",
  staff: { email: "staff@kestrel.example", name: "Marcus Lee" },
} as const;

export function storeIdFrom(url: string): string {
  const match = /\/s\/([^/?#]+)/.exec(url);
  if (!match) throw new Error(`No store id in ${url}`);
  return match[1];
}

export async function signIn(page: Page, email: string): Promise<string> {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(staffPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/s\/[^/]+\/overview/);
  return storeIdFrom(page.url());
}

/** "Explore the demo": the passwordless, read-only viewer (ADR-0011). */
export async function exploreDemo(page: Page): Promise<string> {
  await page.goto("/login");
  await page.getByRole("button", { name: "Explore the demo" }).click();
  await page.waitForURL(/\/s\/[^/]+\/overview/);
  return storeIdFrom(page.url());
}

/** The design rule "no sideways scroll at 375 px", checked on the whole document. */
export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "page scrolls sideways").toBeLessThanOrEqual(0);
}

/** The highest-priority active exception in the inbox (the default sort). */
export async function openTopException(page: Page, storeId: string): Promise<void> {
  await page.goto(`/s/${storeId}/exceptions`);
  const first = page.getByRole("link", { name: /^EXC-\d+/ }).first();
  await expect(first).toBeVisible();
  await first.click();
  await page.waitForURL(/\/exceptions\/[0-9a-f-]{36}/);
}
