import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AuditEntry } from "@/lib/api/admin-api";
import type { Permission } from "@/lib/api/auth";
import { auditEntryFixture } from "@/test/admin-fixtures";
import { errorResponse, jsonResponse, routeFetch } from "@/test/fetch";
import { renderInStore, testStore } from "@/test/render";

import { auditActionLabel } from "./audit-actions";
import { auditRange, auditTarget, AuditLogScreen, validDay } from "./audit-log-screen";

const replace = vi.fn();
let search = new URLSearchParams();
const STORE_ID = "f0da0f22-b9e0-4483-b144-e9f0f8703d13";
const PATH = `/s/${STORE_ID}/admin/audit-log`;
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => PATH,
  useSearchParams: () => search,
}));

const ANALYST: Permission[] = ["audit.read", "exceptions.read", "settings.read", "imports.read"];
const page = (items: AuditEntry[], total = items.length) => ({ items, page: 1, page_size: 50, total });

const entries: AuditEntry[] = [
  auditEntryFixture(),
  auditEntryFixture({
    id: "a2",
    action: "settings.update",
    actor_user_id: "user-1",
    actor_name: "Priya Raman",
    target_type: "store",
    target_id: STORE_ID,
    details: { before: { fulfillment_sla_hours: 48 }, after: { fulfillment_sla_hours: 36 } },
    request_id: "req-2",
  }),
  auditEntryFixture({
    id: "a3",
    action: "import.applied",
    actor_user_id: "u-gone",
    actor_name: null,
    target_type: "data_import",
    target_id: "i1",
    details: { import_type: "orders", created: 4 },
  }),
  auditEntryFixture({ id: "a4", action: "evaluation.run", actor_user_id: null, actor_name: null, target_type: "evaluation_run", target_id: "run-12345678", details: {} }),
  auditEntryFixture({
    id: "a5",
    action: "user.role_change",
    actor_user_id: "user-1",
    actor_name: "Priya Raman",
    store_id: null,
    target_type: "user",
    target_id: "u-staff",
    details: { membership_id: "m-staff", full_name: "Sam Ortiz", from_role: "STAFF", to_role: "MANAGER" },
  }),
];

function routes(items: AuditEntry[] = entries) {
  return routeFetch({
    "/audit-logs": jsonResponse(page(items)),
    "/members": jsonResponse({
      items: [
        { id: "u-staff", full_name: "Sam Ortiz", role: "STAFF", can_work_exceptions: true },
        { id: "user-1", full_name: "Priya Raman", role: "MANAGER", can_work_exceptions: true },
      ],
    }),
  });
}

beforeEach(() => {
  replace.mockReset();
  search = new URLSearchParams();
});

describe("AuditLogScreen (S-15)", () => {
  it("lists events with actors, labels and linked targets", async () => {
    const fetchMock = routes();
    renderInStore(<AuditLogScreen />, testStore({ permissions: ANALYST, role: "ANALYST" }));
    expect(screen.getByText("Kestrel Home & Kitchen · append-only")).toBeInTheDocument();
    const table = await screen.findByRole("table");
    expect(await within(table).findByText("Resolved exception")).toBeInTheDocument();
    expect(within(table).getByText("exception.resolve")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "EXC-1042" })).toHaveAttribute("href", `/s/${STORE_ID}/exceptions/e1`);
    expect(within(table).getByRole("link", { name: "Store settings" })).toHaveAttribute("href", `/s/${STORE_ID}/admin/settings`);
    expect(within(table).getByRole("link", { name: "Orders import" })).toHaveAttribute("href", `/s/${STORE_ID}/imports/i1`);
    expect(within(table).getByText("Former member")).toBeInTheDocument();
    expect(within(table).getByText("System")).toBeInTheDocument();
    expect(within(table).getByText("Changed role")).toBeInTheDocument();
    expect(within(table).getByText("Sam Ortiz", { selector: "td span:not([class*=whitespace])" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Time (ET)" })).toBeInTheDocument();
    expect(screen.getByText("5 events")).toBeInTheDocument();

    const call = String(fetchMock.mock.calls.find(([url]) => String(url).includes("/audit-logs"))?.[0]);
    expect(call).toContain("page_size=50");
    expect(call).toMatch(/from=\d{4}-\d{2}-\d{2}T/);
    expect(call).not.toContain("action=");
  });

  it("expands a row to show its metadata, before and after", async () => {
    routes();
    const user = userEvent.setup();
    renderInStore(<AuditLogScreen />, testStore({ permissions: ANALYST }));
    const table = await screen.findByRole("table");
    const toggle = await within(table).findByRole("button", { name: /^Show details: Updated settings/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(within(table).getByText("fulfillment_sla_hours")).toBeInTheDocument();
    expect(within(table).getByText("48 → 36")).toBeInTheDocument();
    expect(within(table).getByText("req-2", { selector: "dd" })).toBeInTheDocument();
    await user.click(within(table).getByRole("button", { name: /^Hide details: Updated settings/ }));
    expect(within(table).queryByText("48 → 36")).not.toBeInTheDocument();
  });

  it("filters by action group through the URL", async () => {
    routes();
    const user = userEvent.setup();
    renderInStore(<AuditLogScreen />, testStore({ permissions: ANALYST }));
    await screen.findByRole("table");
    await user.selectOptions(screen.getByLabelText("Action"), "Exceptions");
    expect(replace).toHaveBeenCalledWith(`${PATH}?action=exception.`, { scroll: false });
    await user.selectOptions(screen.getByLabelText("Actor"), "Sam Ortiz");
    expect(replace).toHaveBeenCalledWith(`${PATH}?actor_user_id=u-staff`, { scroll: false });
  });

  it("sends the filters from the URL to the API", async () => {
    search = new URLSearchParams("period=all&action=user.&page_size=100");
    const fetchMock = routes([entries[4]]);
    renderInStore(<AuditLogScreen />, testStore({ permissions: ANALYST }));
    await screen.findByRole("table");
    const call = String(fetchMock.mock.calls.find(([url]) => String(url).includes("/audit-logs"))?.[0]);
    expect(call).toContain("action=user.");
    expect(call).toContain("page_size=100");
    expect(call).not.toContain("from=");
    expect(screen.getByRole("button", { name: "Remove filter Period: All time" })).toBeInTheDocument();
  });

  it("suggests a wider range when the period is empty", async () => {
    routes([]);
    const user = userEvent.setup();
    renderInStore(<AuditLogScreen />, testStore({ permissions: ANALYST }));
    expect(await screen.findByText("No audit events in this period")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show all time" }));
    expect(replace).toHaveBeenCalledWith(`${PATH}?period=all`, { scroll: false });
  });

  it("offers to clear filters that match nothing", async () => {
    search = new URLSearchParams("action=import.");
    routes([]);
    const user = userEvent.setup();
    renderInStore(<AuditLogScreen />, testStore({ permissions: ANALYST }));
    expect(await screen.findByText("No audit events match these filters")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(replace).toHaveBeenCalledWith(PATH, { scroll: false });
  });

  it("explains an inverted custom range instead of applying it", async () => {
    search = new URLSearchParams("period=custom");
    routes();
    renderInStore(<AuditLogScreen />, testStore({ permissions: ANALYST }));
    await screen.findByRole("table");
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-10-20" } });
    expect(replace).toHaveBeenLastCalledWith(`${PATH}?period=custom&from=2026-10-20`, { scroll: false });
    replace.mockClear();
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-10-10" } });
    expect(screen.getByText("The start date must be on or before the end date.")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("shows an error with retry when the log fails to load", async () => {
    routeFetch({ "/audit-logs": errorResponse(500, "INTERNAL_ERROR", "boom", { requestId: "req-x" }), "/members": jsonResponse({ items: [] }) });
    renderInStore(<AuditLogScreen />, testStore({ permissions: ANALYST }));
    expect(await screen.findByRole("heading", { name: "Couldn't load the audit log" })).toBeInTheDocument();
    expect(screen.getByText("req-x")).toBeInTheDocument();
  });

  it("shows permission denied without audit.read", () => {
    renderInStore(<AuditLogScreen />, testStore({ permissions: ["exceptions.read"], role: "STAFF" }));
    expect(screen.getByRole("heading", { name: "You don't have access to the audit log" })).toBeInTheDocument();
  });
});

describe("audit helpers", () => {
  it("covers whole store-local days for a custom range", () => {
    const now = new Date("2026-10-31T18:00:00Z");
    expect(auditRange("custom", { from: "2026-10-01", to: "2026-10-05" }, now, "America/New_York")).toEqual({
      from: "2026-10-01T04:00:00.000Z",
      to: "2026-10-06T04:00:00.000Z",
    });
    // Daylight saving ends on 2026-11-01, so the next store midnight is 05:00 UTC.
    expect(auditRange("custom", { from: "", to: "2026-11-01" }, now, "America/New_York")).toEqual({
      from: undefined,
      to: "2026-11-02T05:00:00.000Z",
    });
    expect(auditRange("7d", { from: "", to: "" }, now, "America/New_York")).toEqual({ from: "2026-10-25T04:00:00.000Z" });
    expect(auditRange("24h", { from: "", to: "" }, now, "America/New_York")).toEqual({ from: "2026-10-30T18:00:00.000Z" });
    expect(auditRange("all", { from: "", to: "" }, now, "America/New_York")).toEqual({});
    expect(validDay("2026-02-30")).toBeNull();
  });

  it("labels targets and links only records of this store", () => {
    const store = { id: STORE_ID, permissions: new Set<Permission>(["exceptions.read"]) };
    expect(auditTarget(auditEntryFixture(), store)).toEqual({ label: "EXC-1042", href: `/s/${STORE_ID}/exceptions/e1` });
    expect(auditTarget(auditEntryFixture({ store_id: "other" }), store)).toEqual({ label: "EXC-1042", href: undefined });
    expect(auditTarget(auditEntryFixture({ target_type: "user", target_id: "u9", details: {} }), store)).toEqual({ label: "Member u9" });
    expect(auditTarget(auditEntryFixture({ target_type: null, target_id: null }), store)).toBeNull();
  });

  it("refines assignment labels and falls back to the raw code", () => {
    expect(auditActionLabel({ action: "exception.assign", details: { claimed: true } })).toBe("Claimed exception");
    expect(auditActionLabel({ action: "exception.assign", details: { claimed: false, to_assignee_id: null } })).toBe("Unassigned exception");
    expect(auditActionLabel({ action: "authz.denied", details: {} })).toBe("authz.denied");
  });
});
