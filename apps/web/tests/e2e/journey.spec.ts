import { expect, test, type Page } from "@playwright/test";

import { journeyFiles, journeyRunId, type JourneyFile } from "./journey-data";
import { STAFF, signIn, staffPassword } from "./support";

/**
 * The owner's 12 required end-to-end scenarios (docs/operations/TEST_STRATEGY.md §10), as one
 * serial journey on a seeded stack, signed in as the operations manager:
 *
 *  1 demo organization exists → 2 import products → 3 import orders → 4 run analysis →
 *  5 low stock detected → 6 overselling detected → 7 open the exception → 8 assign an owner →
 *  9 add an investigation note → 10 resolve → 11 audit history → 12 ask the copilot.
 */
test.describe.configure({ mode: "serial" });

test.skip(!staffPassword, "Set E2E_STAFF_PASSWORD to the DEMO_STAFF_PASSWORD the stack was seeded with.");

const run = journeyRunId();
const data = journeyFiles(run);
let page: Page;
let storeId = "";
let exceptionUrl = "";
let reference = "";

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
});

test.afterAll(async () => {
  await page.close();
});

async function importFile(file: JourneyFile): Promise<void> {
  await page.goto(`/s/${storeId}/imports/new`);
  // The option's label covers the card (a larger target), so click it as a person would.
  await page.locator("label", { hasText: file.label }).click();
  await expect(page.getByRole("radio", { name: file.label })).toBeChecked();
  await page.locator('input[type="file"]').setInputFiles({
    name: file.filename,
    mimeType: "text/csv",
    buffer: Buffer.from(file.csv),
  });
  await page.getByRole("button", { name: "Upload and validate" }).click();
  await page.waitForURL(/\/imports\/[0-9a-f-]{36}/);
  await expect(page.getByText("No issues found.", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: "Continue to apply" }).click();
  const apply = page.getByRole("button", { name: /^Apply \d+ rows?$/ });
  await expect(apply).toBeEnabled();
  await apply.click();
  await expect(page.getByText(/^Import completed\./)).toBeVisible();
  // The import-triggered analysis has run before the next file is uploaded.
  await expect(page.getByText("Analysis after import")).toBeVisible();
}

test("1. the seeded demo organization is ready for the manager", async () => {
  storeId = await signIn(page, STAFF.manager);
  await expect(page.getByText("Demo data", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

test("2. import products and their stock counts", async () => {
  await importFile(data.files[0]);
  await importFile(data.files[1]);
});

test("3. import orders and their lines", async () => {
  await importFile(data.files[2]);
  await importFile(data.files[3]);
});

test("4. run the operational analysis on demand", async () => {
  await page.goto(`/s/${storeId}/overview`);
  await page.getByRole("button", { name: "Run analysis" }).click();
  // Either this run finishes or the import-triggered one still holds the store lock.
  await expect(page.getByText(/^Analysis complete|already running|still running/).first()).toBeVisible();
});

test("5. low stock is detected for the imported product", async () => {
  await page.goto(`/s/${storeId}/exceptions?q=${encodeURIComponent(data.low)}`);
  await expect(page.getByRole("link", { name: new RegExp(`Below reorder point: ${data.low}`) })).toBeVisible();
});

test("6. overselling is detected with its affected order", async () => {
  await page.goto(`/s/${storeId}/exceptions?q=${encodeURIComponent(data.short)}`);
  const oversold = page.getByRole("link", { name: new RegExp(`Oversold: ${data.short}`) });
  await expect(oversold).toBeVisible();
  await oversold.click();
  await page.waitForURL(/\/exceptions\/[0-9a-f-]{36}/);
  exceptionUrl = page.url();
});

test("7. the exception shows its evidence, calculation and priority", async () => {
  await expect(page.getByRole("heading", { name: "Evidence" })).toBeVisible();
  await expect(page.getByRole("link", { name: `${run}-1` }).first()).toBeVisible();
  reference = (await page.getByText(/^EXC-\d+$/).first().textContent()) ?? "";
  expect(reference).toMatch(/^EXC-\d+$/);
});

test("8. assign an owner", async () => {
  await page.getByRole("button", { name: /^Assignee: .*, change$/ }).click();
  await page.getByRole("listbox", { name: "Assign to" }).getByRole("option", { name: new RegExp(STAFF.staff.name) }).click();
  await expect(page.getByText(`Assigned to ${STAFF.staff.name}`).first()).toBeVisible();
});

test("9. add an investigation note", async () => {
  const note = `E2E ${run}: cycle count confirmed one unit on the shelf; supplier asked to expedite.`;
  await page.getByLabel("Add a note").fill(note);
  await page.getByRole("button", { name: "Add note" }).click();
  await expect(page.getByText(note)).toBeVisible();
});

test("10. resolve the exception; it awaits verification", async () => {
  await page.getByRole("button", { name: "Acknowledge" }).click();
  // Acknowledged: Resolve moves from the More menu onto the action bar.
  await page.getByRole("button", { name: /Resolve…/ }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("How was it resolved?").selectOption("STOCK_REPLENISHED");
  await dialog.getByLabel("What was done").fill("Expedited replenishment confirmed by the supplier.");
  await dialog.getByRole("button", { name: "Resolve exception" }).click();
  await expect(page.getByText("Resolved — awaiting verification").first()).toBeVisible();
});

test("11. the audit log records the work on the exception", async () => {
  await page.goto(`/s/${storeId}/admin/audit-log`);
  await expect(page.getByRole("link", { name: reference }).first()).toBeVisible();
});

test("12. the copilot summarizes the situation from real records", async () => {
  await page.goto(`/s/${storeId}/copilot`);
  await page.getByRole("textbox", { name: "Question" }).fill("What needs attention today?");
  await page.getByRole("button", { name: "Send question" }).click();
  await expect(page.getByText(/^Generated by (the deterministic engine|LLM provider)/).first()).toBeVisible({ timeout: 45_000 });
  await expect(page.getByRole("link", { name: /^EXC-\d+/ }).first()).toBeVisible();
  // The exception page still shows the verification state the journey left.
  await page.goto(exceptionUrl);
  await expect(page.getByText("Resolved — awaiting verification").first()).toBeVisible();
});
