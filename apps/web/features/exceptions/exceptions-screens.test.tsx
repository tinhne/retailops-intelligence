import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Permission } from "@/lib/api/auth";
import { errorResponse, jsonResponse, routeFetch } from "@/test/fetch";
import { detailFixture, eventFixture, listItemFixture, page } from "@/test/exception-fixtures";
import { renderInStore, testStore } from "@/test/render";

import { describeEvent, toTimelineItems } from "./detail/activity";
import { ExceptionScreen } from "./detail/exception-screen";
import { InboxScreen } from "./inbox-screen";

const replace = vi.fn();
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/exceptions",
  useSearchParams: () => search,
  useParams: () => ({ exceptionId: "exc-1" }),
}));

const VIEWER: Permission[] = ["dashboard.read", "exceptions.read", "orders.read", "catalog.read", "inventory.read", "imports.read"];
const MANAGER: Permission[] = [...VIEWER, "exceptions.work", "exceptions.assign", "exceptions.manage", "evaluations.run"];
const members = { items: [{ id: "u2", full_name: "Marcus Lee", role: "STAFF", can_work_exceptions: true }] };

beforeEach(() => {
  replace.mockReset();
  search = new URLSearchParams();
});

describe("InboxScreen (S-03)", () => {
  it("lists exceptions with a link per row and the view tabs", async () => {
    routeFetch({
      "/exceptions": jsonResponse(page([listItemFixture(), listItemFixture({ id: "exc-2", reference: "EXC-1010", title: "Order KHK-12023 is past its ship-by deadline", exception_type: "ORDER_FULFILLMENT_OVERDUE" })])),
      "/members": jsonResponse(members),
      "/analytics/dashboard": errorResponse(503, "X", "x"),
    });
    renderInStore(<InboxScreen />, testStore({ permissions: MANAGER }));

    // Both the table and the stacked list (shown below 768 px) are in the DOM; CSS picks one.
    await screen.findAllByRole("link", { name: /EXC-1002, Oversold/ });
    const table = screen.getByRole("table");
    expect(within(table).getByRole("link", { name: /EXC-1002, Oversold/ })).toHaveAttribute(
      "href",
      "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/exceptions/exc-1",
    );
    expect(within(table).getAllByText("$56.85")).toHaveLength(2);
    expect(screen.getByRole("link", { name: /All active/ })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: /Assigned to me/ })).toBeInTheDocument();
    expect(screen.getByText("2 exceptions")).toBeInTheDocument();
  });

  it("drops unknown filters from a shared link and normalises the URL", async () => {
    search = new URLSearchParams("view=active&severity=LOUD");
    const info = vi.spyOn(toast, "info");
    routeFetch({ "/exceptions": jsonResponse(page([])), "/members": jsonResponse(members), "/analytics/dashboard": errorResponse(503, "X", "x") });
    renderInStore(<InboxScreen />, testStore({ permissions: VIEWER }));
    await waitFor(() => expect(info).toHaveBeenCalledWith("Some filters in the link weren't recognised and were removed."));
    expect(replace).toHaveBeenCalledWith(expect.stringContaining("?view=active"), { scroll: false });
  });

  it("hides Assigned to me from roles that cannot work on exceptions", async () => {
    routeFetch({ "/exceptions": jsonResponse(page([])), "/members": jsonResponse(members), "/analytics/dashboard": errorResponse(503, "X", "x") });
    renderInStore(<InboxScreen />, testStore({ permissions: VIEWER }));
    await screen.findByRole("link", { name: /All active/ });
    expect(screen.queryByRole("link", { name: /Assigned to me/ })).not.toBeInTheDocument();
  });

  it("shows the per-view empty state and the filtered no-results state", async () => {
    search = new URLSearchParams("view=triage");
    routeFetch({ "/exceptions": jsonResponse(page([])), "/members": jsonResponse(members), "/analytics/dashboard": errorResponse(503, "X", "x") });
    const { unmount } = renderInStore(<InboxScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByText("Triage queue is clear")).toBeInTheDocument();
    unmount();

    search = new URLSearchParams("view=triage&severity=LOW");
    renderInStore(<InboxScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByText("No exceptions match these filters")).toBeInTheDocument();
  });
});

describe("ExceptionScreen (S-04)", () => {
  function detailRoutes(detail = detailFixture(), extra: Record<string, Response | (() => Response)> = {}) {
    return routeFetch({
      "/exceptions/exc-1": jsonResponse(detail),
      "/exceptions/exc-1/events": jsonResponse(page([eventFixture({})])),
      "/exceptions/exc-1/notes": jsonResponse(page([])),
      "/members": jsonResponse(members),
      ...extra,
    });
  }

  it("shows the deterministic investigation: priority, calculation, evidence and affected orders", async () => {
    detailRoutes();
    renderInStore(<ExceptionScreen />, testStore({ permissions: MANAGER }));

    expect(await screen.findByRole("heading", { level: 1, name: /Oversold: KHK-KT-012/ })).toBeInTheDocument();
    expect(screen.getByText("CRITICAL severity scores 50 points.")).toBeInTheDocument();
    expect(screen.getByText("available = on_hand − reserved (BR-101)")).toBeInTheDocument();
    const evidence = screen.getByRole("table", { name: "Evidence" });
    expect(within(evidence).getByText("−3 units")).toHaveClass("text-tone-danger-fg");
    expect(within(evidence).getByText("$56.85")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Affected orders (1)" })).toBeInTheDocument();
    expect(await screen.findByText("Detected by an evaluation")).toBeInTheDocument();
  });

  it("keeps every action visible but read-only for the public demo", async () => {
    const denied = (action: string) => ({ action, code: "PERMISSION_DENIED", reason: "Your role does not allow this action." });
    detailRoutes(
      detailFixture({
        available_actions: [],
        blocked_actions: ["acknowledge", "start", "claim", "resolve", "dismiss", "assign", "add_note", "set_due_date"].map(denied) as never,
      }),
    );
    renderInStore(<ExceptionScreen />, testStore({ permissions: VIEWER, isDemo: true, role: "VIEWER" }));

    const acknowledge = await screen.findByRole("button", { name: "Acknowledge" });
    expect(acknowledge).toHaveAttribute("aria-disabled", "true");
    expect(acknowledge).toHaveAccessibleDescription("The public demo is read-only.");
    expect(screen.queryByRole("button", { name: "Change due date" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Add a note")).not.toBeInTheDocument();
  });

  it("validates the resolve dialog and sends the version on screen", async () => {
    const fetchMock = detailRoutes(detailFixture(), {
      "/exceptions/exc-1/resolve": jsonResponse(detailFixture({ status: "RESOLVED", version: 4, available_actions: ["reopen"] })),
    });
    const success = vi.spyOn(toast, "success");
    renderInStore(<ExceptionScreen />, testStore({ permissions: MANAGER }));
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "More actions" }));
    await user.click(await screen.findByRole("menuitem", { name: /Resolve/ }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Resolve exception" }));
    expect(await within(dialog).findByText("Choose how it was resolved.")).toBeInTheDocument();
    expect(within(dialog).getByText("Enter at least 10 characters (currently 0).")).toBeInTheDocument();

    await user.selectOptions(within(dialog).getByLabelText("How was it resolved?"), "STOCK_REPLENISHED");
    // Whitespace does not count towards the 10-character minimum (as in the API).
    await user.type(within(dialog).getByLabelText("What was done"), "a b c d e f g h i");
    await user.click(within(dialog).getByRole("button", { name: "Resolve exception" }));
    expect(await within(dialog).findByText("Enter at least 10 characters (currently 9).")).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText("What was done"), " j");
    await user.click(within(dialog).getByRole("button", { name: "Resolve exception" }));

    await waitFor(() => expect(success).toHaveBeenCalledWith(expect.stringContaining("EXC-1002 resolved. Awaiting verification")));
    const call = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/resolve"));
    expect(JSON.parse(String(call?.[1]?.body))).toEqual({
      resolution_code: "STOCK_REPLENISHED",
      resolution_note: "a b c d e f g h i j",
      expected_version: 3,
    });
  });

  it("keeps the dialog and its input after a stale version, and refetches", async () => {
    let detailCalls = 0;
    detailRoutes(detailFixture(), {
      "/exceptions/exc-1": () => jsonResponse(detailFixture({ version: ++detailCalls === 1 ? 3 : 5 })),
      "/exceptions/exc-1/resolve": errorResponse(409, "STALE_VERSION", "The exception changed."),
    });
    const warning = vi.spyOn(toast, "warning");
    renderInStore(<ExceptionScreen />, testStore({ permissions: MANAGER }));
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "More actions" }));
    await user.click(await screen.findByRole("menuitem", { name: /Resolve/ }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("How was it resolved?"), "OTHER");
    await user.type(within(dialog).getByLabelText("What was done"), "Handled with the supplier.");
    await user.click(within(dialog).getByRole("button", { name: "Resolve exception" }));

    await waitFor(() =>
      expect(warning).toHaveBeenCalledWith("Someone else updated EXC-1002. The latest details are now shown. Review them and try again."),
    );
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(within(screen.getByRole("dialog")).getByLabelText("What was done")).toHaveValue("Handled with the supplier.");
    await waitFor(() => expect(detailCalls).toBeGreaterThanOrEqual(2));
  });

  it("shows not found for another store's exception", async () => {
    routeFetch({ "/exceptions/exc-1": errorResponse(404, "NOT_FOUND", "Not found.") });
    renderInStore(<ExceptionScreen />, testStore({ permissions: MANAGER }));
    expect(await screen.findByText("This exception doesn't exist or belongs to another store.")).toBeInTheDocument();
  });
});

describe("timeline copy (S-04)", () => {
  const names = new Map([["u2", "Marcus Lee"]]);
  const ET = "America/New_York";

  it("describes lifecycle events in plain language", () => {
    const actor = { id: "u1", full_name: "Priya Raman" };
    expect(describeEvent(eventFixture({ event_type: "STATUS_CHANGED", actor_type: "USER", actor, from_status: "IN_PROGRESS", to_status: "RESOLVED", payload: { resolution_code: "STOCK_REPLENISHED", resolution_note: "Counted again." } }), names, ET)).toMatchObject({
      title: "Priya Raman changed status from In progress to Resolved",
      body: "Stock replenished: Counted again.",
    });
    expect(describeEvent(eventFixture({ event_type: "ASSIGNED", actor_type: "USER", actor, payload: { assignee_id: "u2", reason: "ASSIGNED" } }), names, ET).title).toBe("Priya Raman assigned Marcus Lee");
    expect(describeEvent(eventFixture({ event_type: "ASSIGNED", actor_type: "USER", actor, payload: { assignee_id: "u1", reason: "CLAIMED" } }), names, ET).title).toBe("Priya Raman claimed this exception");
    expect(describeEvent(eventFixture({ event_type: "SEVERITY_CHANGED", payload: { from: "HIGH", to: "CRITICAL" } }), names, ET).title).toBe("Severity changed from High to Critical");
    expect(describeEvent(eventFixture({ event_type: "REOPENED", payload: { reason: "VERIFICATION_FAILED", due_date_changed: { to: "2026-11-02T14:00:00Z" } } }), names, ET).title).toBe(
      "Reopened: verification failed, the condition was still present. Due date recalculated to Nov 2, 9:00 AM EST",
    );
  });

  it("merges notes with events, newest first, without duplicating NOTE_ADDED", () => {
    const items = toTimelineItems(
      [eventFixture({ id: "e1" }), eventFixture({ id: "e2", event_type: "NOTE_ADDED", occurred_at: "2026-10-31T19:00:00Z" })],
      [{ id: "n1", body: "Called the supplier.", source: "AI_DRAFT_ACCEPTED", author: { id: "u1", full_name: "Priya Raman" }, created_at: "2026-10-31T19:00:00Z" }],
      names,
      ET,
    );
    expect(items.map((item) => item.kind)).toEqual(["note", "event"]);
    expect(items[0]).toMatchObject({ body: "Called the supplier.", badge: "AI draft, accepted by Priya Raman" });
  });
});
