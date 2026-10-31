import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Permission } from "@/lib/api/auth";
import { errorResponse, jsonResponse, routeFetch } from "@/test/fetch";
import { importFixture, issueFixture } from "@/test/import-fixtures";
import { renderInStore, testStore } from "@/test/render";
import { mockXhr } from "@/test/xhr";

import { expiredAutomatically, expiresIn, ImportScreen } from "./import-screen";
import { ImportsScreen } from "./imports-screen";
import { fileProblem, NewImportScreen, pendingText } from "./new-import-screen";

const replace = vi.fn();
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/imports",
  useSearchParams: () => search,
  useParams: () => ({ importId: "i1" }),
}));

const STORE = "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13";
const VIEWER: Permission[] = ["dashboard.read", "exceptions.read", "orders.read", "catalog.read", "inventory.read", "imports.read"];
const MANAGER: Permission[] = [...VIEWER, "imports.run"];
const page = <T,>(items: T[]) => ({ items, page: 1, page_size: 25, total: items.length });
const members = { items: [{ id: "u1", full_name: "Morgan Lee", role: "MANAGER", can_work_exceptions: true }] };

beforeEach(() => {
  replace.mockReset();
  search = new URLSearchParams();
});

describe("ImportsScreen (S-11)", () => {
  it("lists imports with status, error counts and who uploaded them", async () => {
    routeFetch({
      "/imports": jsonResponse(page([importFixture({ status: "COMPLETED_WITH_ERRORS", mode: "VALID_ROWS_ONLY" })])),
      "/members": jsonResponse(members),
    });
    renderInStore(<ImportsScreen />, testStore({ permissions: MANAGER }));
    const table = (await screen.findAllByRole("table"))[0];
    expect(await within(table).findByRole("link", { name: "orders_2026-10-31.csv" })).toHaveAttribute("href", `${STORE}/imports/i1`);
    expect(within(table).getByText("Completed, rows skipped")).toBeInTheDocument();
    expect(await within(table).findByText("Morgan Lee")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "New import" })).toHaveAttribute("href", `${STORE}/imports/new`);
  });

  it("filters by several statuses at once", async () => {
    search = new URLSearchParams("status=FAILED&status=REJECTED");
    const fetchMock = routeFetch({ "/imports": jsonResponse(page([])), "/members": jsonResponse(members) });
    renderInStore(<ImportsScreen />, testStore({ permissions: MANAGER }));
    expect(await screen.findByText("Status: Failed, Rejected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Status, 2 selected" })).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain("status=FAILED&status=REJECTED");
    expect(await screen.findByText("No imports match these filters")).toBeInTheDocument();
  });

  it("keeps New import visible but disabled for the read-only demo", async () => {
    routeFetch({ "/imports": jsonResponse(page([])), "/members": jsonResponse(members) });
    renderInStore(<ImportsScreen />, testStore({ permissions: VIEWER, isDemo: true }));
    expect(await screen.findByText("No imports yet")).toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: "New import" });
    expect(buttons[0]).toHaveAttribute("aria-disabled", "true");
    expect(screen.getAllByText("The public demo is read-only.").length).toBeGreaterThan(0);
  });
});

describe("NewImportScreen (S-12 step 1)", () => {
  it("checks the type and file before uploading", async () => {
    renderInStore(<NewImportScreen />, testStore({ permissions: MANAGER }));
    await userEvent.click(screen.getByRole("button", { name: "Upload and validate" }));
    expect(screen.getByText("Choose what you're importing.")).toBeInTheDocument();
    expect(screen.getByText("Choose a CSV file.")).toBeInTheDocument();
  });

  it("uploads the file with its type, shows the progress, then opens the preview", async () => {
    search = new URLSearchParams("type=orders");
    document.cookie = "ro_csrf=token-1; path=/";
    const xhr = mockXhr();
    renderInStore(<NewImportScreen />, testStore({ permissions: MANAGER }));
    expect(screen.getByRole("radio", { name: "3. Orders" })).toBeChecked();
    expect(screen.getByText(/Products should be imported first/)).toBeInTheDocument();

    const file = new File(["order_number\nKHK-1\n"], "orders.csv", { type: "text/csv" });
    await userEvent.upload(screen.getByLabelText("File"), file);
    expect(screen.getByText("orders.csv")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Upload and validate" }));

    const request = await waitFor(() => {
      expect(xhr.requests).toHaveLength(1);
      return xhr.requests[0];
    });
    expect(request.method).toBe("POST");
    expect(request.url).toBe(`/api/v1/stores/f0da0f22-b9e0-4483-b144-e9f0f8703d13/imports`);
    expect(request.headers["X-CSRF-Token"]).toBe("token-1");
    const body = request.body as FormData;
    expect(body.get("import_type")).toBe("orders");
    expect((body.get("file") as File).name).toBe("orders.csv");

    act(() => request.progress(42, 100));
    expect(screen.getByRole("progressbar", { name: "Upload progress" })).toHaveAttribute("aria-valuenow", "42");
    expect(screen.getByRole("button", { name: "Uploading 42%…" })).toHaveAttribute("aria-busy", "true");
    act(() => request.finishUpload());
    expect(screen.getByRole("progressbar", { name: "Validating the file" })).not.toHaveAttribute("aria-valuenow");
    expect(screen.getByRole("button", { name: "Validating…" })).toBeInTheDocument();
    act(() => request.respond(201, importFixture()));

    await waitFor(() => expect(replace).toHaveBeenCalledWith(`${STORE}/imports/i1`));
  });

  it("keeps the file selected when the upload fails", async () => {
    search = new URLSearchParams("type=orders");
    const xhr = mockXhr();
    renderInStore(<NewImportScreen />, testStore({ permissions: MANAGER }));
    await userEvent.upload(screen.getByLabelText("File"), new File(["x"], "orders.csv", { type: "text/csv" }));
    await userEvent.click(screen.getByRole("button", { name: "Upload and validate" }));
    await waitFor(() => expect(xhr.requests).toHaveLength(1));
    act(() => xhr.requests[0].failNetwork());
    expect(await screen.findByText("Upload failed. Check your connection and try again.")).toBeInTheDocument();
    expect(screen.getByText("orders.csv")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Upload and validate" }));
    await waitFor(() => expect(xhr.requests).toHaveLength(2));
    act(() => xhr.requests[1].respond(403, { error: { code: "PERMISSION_DENIED", message: "You need the Run imports permission.", details: [], request_id: "r-1" } }));
    expect(await screen.findByText("You need the Run imports permission.")).toBeInTheDocument();
    expect(pendingText({ phase: "uploading", fraction: null })).toBe("Uploading…");
  });

  it("rejects other file types and files over 5 MB", () => {
    expect(fileProblem(new File(["x"], "orders.xlsx"))).toBe("Only .csv files can be imported.");
    const big = new File(["x"], "orders.csv");
    Object.defineProperty(big, "size", { value: 7.2 * 1024 * 1024 });
    expect(fileProblem(big)).toBe("This file is 7.2 MB. The limit is 5 MB. Split it into smaller files.");
    expect(fileProblem(new File(["x"], "Orders.CSV"))).toBeNull();
  });

  it("is permission-denied without imports.run", () => {
    renderInStore(<NewImportScreen />, testStore({ permissions: VIEWER }));
    expect(screen.getByRole("heading", { name: "You don't have access to new imports" })).toBeInTheDocument();
  });
});

describe("ImportScreen (S-12 steps 2–4, S-13)", () => {
  function routes(record = importFixture(), extra: Record<string, Response | (() => Response)> = {}) {
    return routeFetch({
      "/imports/i1": jsonResponse(record),
      "/imports/i1/issues": jsonResponse(page([issueFixture()])),
      "/members": jsonResponse(members),
      ...extra,
    });
  }

  it("previews the counts, warnings, expected changes and issues", async () => {
    routes(
      importFixture({
        file_issues: [
          issueFixture({ id: "f1", row_number: null, column: null, code: "DUPLICATE_FILE", severity: "WARNING", message: "An identical file was already imported." }),
        ],
      }),
    );
    renderInStore(<ImportScreen />, testStore({ permissions: MANAGER }));
    expect(await screen.findByRole("heading", { level: 1, name: "orders_2026-10-31.csv" })).toBeInTheDocument();
    expect(screen.getByText("Ready to apply")).toBeInTheDocument();
    expect(screen.getByText(/An identical file was already imported/)).toBeInTheDocument();
    expect(screen.getByText(/3 timestamps had no UTC offset and were read as store time, America\/New_York/)).toBeInTheDocument();
    expect(screen.getByText("KHK-100611")).toBeInTheDocument();
    expect(screen.getByText("status, fulfillment_status")).toBeInTheDocument();
    expect(await screen.findByText("Not an ISO-8601 timestamp.")).toBeInTheDocument();
    expect(screen.getByText(/Export timestamps as ISO-8601/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Errors 4/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Download issues CSV" })).toBeInTheDocument();
  });

  it("blocks strict mode while rows have errors and applies valid rows only after consent", async () => {
    const applied = importFixture({
      status: "COMPLETED_WITH_ERRORS",
      mode: "VALID_ROWS_ONLY",
      applied_at: "2026-10-31T12:05:00Z",
      summary: { ...importFixture().summary, applied: { mode: "VALID_ROWS_ONLY", creates: 30, updates: 80, unchanged: 6, skipped: 4 } },
    });
    // The detail refetches after the apply, so the GET answers with the stored state.
    let current = importFixture();
    const fetchMock = routes(importFixture(), {
      "/imports/i1": () => jsonResponse(current),
      "/imports/i1/apply": () => {
        current = applied;
        return jsonResponse(applied);
      },
    });
    renderInStore(<ImportScreen />, testStore({ permissions: MANAGER }));
    await userEvent.click(await screen.findByRole("button", { name: /Continue to apply/ }));

    const strict = screen.getByRole("button", { name: "Apply 120 rows" });
    expect(strict).toHaveAttribute("aria-disabled", "true");
    expect(screen.getAllByText("Strict mode blocks apply while 4 rows have errors.").length).toBeGreaterThan(0);

    await userEvent.click(screen.getByRole("radio", { name: "Valid rows only" }));
    expect(screen.getByRole("button", { name: "Apply 116 rows, skip 4" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText(/Lines of skipped orders will fail with UNKNOWN_ORDER/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /I understand that 4 rows will be skipped/ }));
    await userEvent.click(screen.getByRole("button", { name: "Apply 116 rows, skip 4" }));

    expect(await screen.findByText(/Import completed. 116 rows applied, 4 skipped with your confirmation/)).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/apply"));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({ mode: "VALID_ROWS_ONLY", confirm_skipped_rows: 4 });
    expect((call?.[1]?.headers as Record<string, string>)["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("clears the consent when the server's skip count differs", async () => {
    routes(importFixture(), {
      "/imports/i1/apply": errorResponse(409, "IMPORT_SKIPPED_ROWS_NOT_CONFIRMED", "The confirmed count does not match."),
    });
    renderInStore(<ImportScreen />, testStore({ permissions: MANAGER }));
    await userEvent.click(await screen.findByRole("button", { name: /Continue to apply/ }));
    await userEvent.click(screen.getByRole("radio", { name: "Valid rows only" }));
    await userEvent.click(screen.getByRole("checkbox", { name: /I understand/ }));
    await userEvent.click(screen.getByRole("button", { name: "Apply 116 rows, skip 4" }));
    expect(await screen.findByText("The number of rows to skip changed. Review the issues and confirm again.")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /I understand/ })).not.toBeChecked();
  });

  it("discards after confirmation", async () => {
    const success = vi.spyOn(toast, "success");
    let current = importFixture();
    const fetchMock = routes(importFixture(), {
      "/imports/i1": () => jsonResponse(current),
      "/imports/i1/discard": () => {
        current = importFixture({ status: "DISCARDED", updated_at: "2026-10-31T12:10:00Z" });
        return jsonResponse(current);
      },
    });
    renderInStore(<ImportScreen />, testStore({ permissions: MANAGER }));
    await userEvent.click(await screen.findByRole("button", { name: "Discard import" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Discard import" }));
    await waitFor(() => expect(success).toHaveBeenCalledWith("Import discarded"));
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith("/discard"))).toBe(true);
    expect(await screen.findByText(/Discarded on/)).toBeInTheDocument();
  });

  it("explains a rejected file with the fix and a way to upload again", async () => {
    routes(
      importFixture({
        status: "REJECTED",
        row_count: null,
        expires_at: null,
        summary: { ...importFixture().summary, rows_total: 0, preview: [], issue_counts_by_code: { MISSING_COLUMNS: 1 } },
        file_issues: [issueFixture({ id: "f1", row_number: null, column: null, code: "MISSING_COLUMNS", message: "Missing required columns: placed_at, total." })],
      }),
    );
    renderInStore(<ImportScreen />, testStore({ permissions: MANAGER }));
    expect(await screen.findByText(/Missing required columns: placed_at, total/)).toBeInTheDocument();
    expect(screen.getByText(/Start from the downloadable template/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload a corrected file" })).toHaveAttribute("href", `${STORE}/imports/new?type=orders`);
  });

  it("searches issues by row number", async () => {
    const fetchMock = routes();
    renderInStore(<ImportScreen />, testStore({ permissions: MANAGER }));
    expect(await screen.findByText("Not an ISO-8601 timestamp.")).toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: "Row number" }), "4a1");
    expect(screen.getByRole("textbox", { name: "Row number" })).toHaveValue("41");
    await waitFor(() => {
      const urls = fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/issues"));
      expect(urls.at(-1)).toContain("row_number=41");
    });
  });

  it("links an applied import's analysis to the exceptions it detected", async () => {
    routes(
      importFixture({
        status: "COMPLETED",
        import_type: "inventory_adjustments",
        applied_at: "2026-10-31T12:05:00Z",
        evaluation_run_id: "run-7",
        summary: { ...importFixture().summary, rows_with_errors: 0, applied: { mode: "STRICT", creates: 30, updates: 80, unchanged: 6, skipped: 0 } },
      }),
      { "/evaluations/run-7": jsonResponse({ id: "run-7", status: "SUCCEEDED", counts: { created: 3, refreshed: 6, resolved: 1, reopened: 0 } }) },
    );
    renderInStore(<ImportScreen />, testStore({ permissions: MANAGER }));
    expect(await screen.findByText(/3 new exceptions · 6 refreshed/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View new exceptions" })).toHaveAttribute(
      "href",
      `${STORE}/exceptions?view=active&evaluation_run_id=run-7`,
    );
    expect(screen.getByRole("link", { name: "View ledger entries" })).toHaveAttribute("href", `${STORE}/inventory/movements?import_id=i1`);
  });

  it("validates a failed import again from its stored file", async () => {
    const success = vi.spyOn(toast, "success");
    let current = importFixture({ status: "FAILED", mode: "STRICT", failure_reason: "IMPORT_DATA_CHANGED: The data changed.", can_revalidate: true });
    const fetchMock = routes(importFixture(), {
      "/imports/i1": () => jsonResponse(current),
      "/imports/i1/revalidate": () => {
        current = importFixture();
        return jsonResponse(current);
      },
    });
    renderInStore(<ImportScreen />, testStore({ permissions: MANAGER }));
    expect(await screen.findByText("IMPORT_DATA_CHANGED: The data changed.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Validate again" }));
    await waitFor(() => expect(success).toHaveBeenCalledWith("Validated again. Review the preview before applying."));
    expect(await screen.findByRole("button", { name: /Continue to apply/ })).toBeInTheDocument();
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/revalidate"));
    expect(call?.[1]?.method).toBe("POST");
  });

  it("after a failed apply, shows the failure and restarts at the preview when validated again", async () => {
    const clean = importFixture({ summary: { ...importFixture().summary, rows_with_errors: 0, rows_valid: 120, issue_counts_by_code: {} } });
    let current = clean;
    routes(clean, {
      "/imports/i1": () => jsonResponse(current),
      "/imports/i1/apply": () => {
        current = importFixture({ ...clean, status: "FAILED", mode: "STRICT", failure_reason: "IMPORT_DATA_CHANGED: The data changed.", can_revalidate: true });
        return errorResponse(409, "IMPORT_DATA_CHANGED", "The data changed since this file was validated.");
      },
      "/imports/i1/revalidate": () => {
        current = clean;
        return jsonResponse(current);
      },
    });
    renderInStore(<ImportScreen />, testStore({ permissions: MANAGER }));
    await userEvent.click(await screen.findByRole("button", { name: /Continue to apply/ }));
    await userEvent.click(screen.getByRole("button", { name: "Apply 120 rows" }));

    expect(await screen.findByText("IMPORT_DATA_CHANGED: The data changed.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Validate again" }));
    expect(await screen.findByRole("button", { name: /Continue to apply/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Apply 120 rows" })).not.toBeInTheDocument();
  });

  it("asks for a new upload once a failed import's file is gone", async () => {
    routes(importFixture({ status: "FAILED", mode: "STRICT", failure_reason: "IMPORT_APPLY_FAILED: No data was changed.", can_revalidate: false }));
    renderInStore(<ImportScreen />, testStore({ permissions: MANAGER }));
    expect(await screen.findByText(/The file is no longer stored/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Validate again" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Upload a corrected file" })).toBeInTheDocument();
  });

  it("keeps Validate again visible but disabled without imports.run", async () => {
    routes(importFixture({ status: "FAILED", can_revalidate: true }));
    renderInStore(<ImportScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByRole("button", { name: "Validate again" })).toHaveAttribute("aria-disabled", "true");
  });

  it("tells an expired preview from a manual discard", () => {
    const expired = importFixture({ status: "DISCARDED", updated_at: "2026-11-01T12:30:00Z" });
    const manual = importFixture({ status: "DISCARDED", updated_at: "2026-10-31T13:00:00Z" });
    expect(expiredAutomatically(expired)).toBe(true);
    expect(expiredAutomatically(manual)).toBe(false);
    expect(expiresIn("2026-11-01T12:00:00Z", new Date("2026-10-31T12:02:00Z"))).toBe("23h 58m");
  });
});
