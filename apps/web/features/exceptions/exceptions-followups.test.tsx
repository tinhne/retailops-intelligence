import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Permission } from "@/lib/api/auth";
import { errorResponse, jsonResponse, routeFetch } from "@/test/fetch";
import { detailFixture, eventFixture, listItemFixture, page } from "@/test/exception-fixtures";
import { renderInStore, testStore } from "@/test/render";

import { ExceptionScreen } from "./detail/exception-screen";
import { sourceHref } from "./detail/investigation";
import { verifiedExample } from "./detail/lifecycle-explainer";
import { COMPACT_KEY, InboxScreen } from "./inbox-screen";
import { neighbours, parseQueue, QUEUE_KEY, saveQueue } from "./queue";

const STORE_ID = "f0da0f22-b9e0-4483-b144-e9f0f8703d13";
const STORE = `/s/${STORE_ID}`;
const RUN = "7c3d2a10-5b4e-4f6a-9c8d-1e2f3a4b5c6d";
const replace = vi.fn();
const push = vi.fn();
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push }),
  usePathname: () => "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/exceptions",
  useSearchParams: () => search,
  useParams: () => ({ exceptionId: "exc-1" }),
}));

const VIEWER: Permission[] = ["dashboard.read", "exceptions.read", "orders.read", "catalog.read", "inventory.read", "imports.read"];
const MANAGER: Permission[] = [...VIEWER, "exceptions.work", "exceptions.assign", "exceptions.manage", "evaluations.run"];
const members = { items: [{ id: "u2", full_name: "Marcus Lee", role: "STAFF", can_work_exceptions: true }] };
const desktopMatchMedia = window.matchMedia;

/** Below 768 px every `min-width` query fails. */
function useNarrowScreen() {
  window.matchMedia = ((query: string) => ({ ...desktopMatchMedia(query), matches: false })) as typeof window.matchMedia;
}

beforeEach(() => {
  replace.mockReset();
  push.mockReset();
  search = new URLSearchParams();
  window.sessionStorage.clear();
  window.localStorage.clear();
});

afterEach(() => {
  window.matchMedia = desktopMatchMedia;
});

const inboxRoutes = (items = [listItemFixture()], extra: Record<string, Response> = {}) =>
  routeFetch({
    "/exceptions": jsonResponse(page(items)),
    "/members": jsonResponse(members),
    "/analytics/dashboard": errorResponse(503, "X", "x"),
    ...extra,
  });

describe("InboxScreen follow-ups (S-03)", () => {
  it("switches density and shows the Last detected column, remembered per browser", async () => {
    inboxRoutes();
    renderInStore(<InboxScreen />, testStore({ permissions: MANAGER }));
    const user = userEvent.setup();
    const table = await screen.findByRole("table");
    await within(table).findAllByRole("link", { name: /EXC-1002/ });
    expect(within(table).getAllByRole("row")[1]).toHaveClass("h-11");
    expect(within(table).queryByRole("columnheader", { name: "Last detected" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Density: comfortable" }));
    await user.click(await screen.findByRole("menuitemradio", { name: "Compact" }));
    expect(within(table).getAllByRole("row")[1]).toHaveClass("h-9");
    expect(window.localStorage.getItem(COMPACT_KEY)).toBe("true");

    await user.click(screen.getByRole("button", { name: "Density: compact" }));
    await user.click(await screen.findByRole("menuitemcheckbox", { name: /Last detected/ }));
    expect(within(table).getByRole("columnheader", { name: "Last detected" })).toBeInTheDocument();
  });

  it("filters to the exceptions an evaluation run detected and names the run", async () => {
    search = new URLSearchParams(`view=active&evaluation_run_id=${RUN}`);
    const fetchMock = inboxRoutes([listItemFixture()], {
      [`/evaluations/${RUN}`]: jsonResponse({ id: RUN, status: "SUCCEEDED", started_at: "2026-10-31T12:05:00Z", counts: {} }),
    });
    renderInStore(<InboxScreen />, testStore({ permissions: MANAGER }));
    expect(await screen.findByText("From evaluation run Oct 31, 8:05 AM EDT")).toBeInTheDocument();
    const urls = fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/exceptions?"));
    expect(urls.some((url) => url.includes(`evaluation_run_id=${RUN}`))).toBe(true);

    await userEvent.click(screen.getByRole("button", { name: "Remove filter From evaluation run Oct 31, 8:05 AM EDT" }));
    expect(replace).toHaveBeenLastCalledWith(`${STORE}/exceptions?view=active`, { scroll: false });
  });

  it("collapses the filters into a sheet with Apply and Reset below 768 px", async () => {
    useNarrowScreen();
    search = new URLSearchParams("view=active&category=PAYMENT");
    inboxRoutes();
    renderInStore(<InboxScreen />, testStore({ permissions: MANAGER }));
    const user = userEvent.setup();

    expect(screen.queryByRole("button", { name: "Severity" })).not.toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Filters, 1 active" }));
    const sheet = await screen.findByRole("dialog", { name: "Filters" });
    expect(within(sheet).getByRole("checkbox", { name: "Payment" })).toBeChecked();

    await user.click(within(sheet).getByRole("button", { name: "Reset" }));
    expect(within(sheet).getByRole("checkbox", { name: "Payment" })).not.toBeChecked();
    expect(replace).not.toHaveBeenCalled(); // Reset only clears the draft
    await user.click(within(sheet).getByRole("checkbox", { name: "Critical" }));
    await user.click(within(sheet).getByRole("button", { name: "Apply" }));

    expect(replace).toHaveBeenLastCalledWith(`${STORE}/exceptions?view=active&severity=CRITICAL`, { scroll: false });
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Filters" })).not.toBeInTheDocument());
  });

  it("remembers the rows on screen as the queue for the investigation page", async () => {
    inboxRoutes([listItemFixture(), listItemFixture({ id: "exc-2", reference: "EXC-1010" })]);
    renderInStore(<InboxScreen />, testStore({ permissions: MANAGER }));
    await waitFor(() => expect(window.sessionStorage.getItem(QUEUE_KEY)).not.toBeNull());
    expect(parseQueue(window.sessionStorage.getItem(QUEUE_KEY), STORE_ID)).toEqual({
      listHref: `${STORE}/exceptions?view=active`,
      items: [
        { id: "exc-1", reference: "EXC-1002" },
        { id: "exc-2", reference: "EXC-1010" },
      ],
    });
  });
});

describe("queue helpers", () => {
  const queue = { listHref: `${STORE}/exceptions?view=triage`, items: ["a", "b", "c"].map((id) => ({ id, reference: `EXC-${id}` })) };

  it("finds neighbours and ignores exceptions outside the queue", () => {
    expect(neighbours(queue, "b")).toEqual({ previous: queue.items[0], next: queue.items[2], position: 2, total: 3 });
    expect(neighbours(queue, "a")?.previous).toBeUndefined();
    expect(neighbours(queue, "z")).toBeNull();
  });

  it("rejects another store's queue and malformed storage", () => {
    expect(parseQueue(JSON.stringify(queue), "another-store")).toBeNull();
    expect(parseQueue("{not json", STORE_ID)).toBeNull();
    expect(parseQueue(JSON.stringify({ listHref: queue.listHref, items: [{ id: 1 }] }), STORE_ID)).toBeNull();
  });
});

describe("ExceptionScreen follow-ups (S-04)", () => {
  function detailRoutes(detail = detailFixture(), extra: Record<string, Response | (() => Response)> = {}) {
    return routeFetch({
      "/exceptions/exc-1": jsonResponse(detail),
      "/exceptions/exc-1/events": jsonResponse(page([eventFixture({})])),
      "/exceptions/exc-1/notes": jsonResponse(page([])),
      "/members": jsonResponse(members),
      ...extra,
    });
  }
  const rememberQueue = () =>
    saveQueue({
      listHref: `${STORE}/exceptions?view=active`,
      items: [
        { id: "exc-0", reference: "EXC-1001" },
        { id: "exc-1", reference: "EXC-1002" },
        { id: "exc-2", reference: "EXC-1003" },
      ],
    });

  it("steps through the queue the person came from", async () => {
    rememberQueue();
    detailRoutes();
    renderInStore(<ExceptionScreen />, testStore({ permissions: MANAGER }));
    const queue = await screen.findByRole("navigation", { name: "Queue" });
    expect(within(queue).getByText("2 of 3")).toBeInTheDocument();
    expect(within(queue).getByRole("link", { name: "Previous: EXC-1001" })).toHaveAttribute("href", `${STORE}/exceptions/exc-0`);
    expect(within(queue).getByRole("link", { name: "Next in queue: EXC-1003" })).toHaveAttribute("href", `${STORE}/exceptions/exc-2`);
  });

  it("offers no queue navigation without a remembered list", async () => {
    detailRoutes();
    renderInStore(<ExceptionScreen />, testStore({ permissions: MANAGER }));
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("navigation", { name: "Queue" })).not.toBeInTheDocument();
  });

  it("offers Next in queue on the resolve toast", async () => {
    rememberQueue();
    detailRoutes(detailFixture(), {
      "/exceptions/exc-1/resolve": jsonResponse(detailFixture({ status: "RESOLVED", version: 4, available_actions: ["reopen"] })),
    });
    const success = vi.spyOn(toast, "success");
    renderInStore(<ExceptionScreen />, testStore({ permissions: MANAGER }));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "More actions" }));
    await user.click(await screen.findByRole("menuitem", { name: /Resolve/ }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("How was it resolved?"), "OTHER");
    await user.type(within(dialog).getByLabelText("What was done"), "Recounted the shelf stock.");
    await user.click(within(dialog).getByRole("button", { name: "Resolve exception" }));

    await waitFor(() => expect(success).toHaveBeenCalled());
    const [, options] = success.mock.calls[0] as [string, { action: { label: string; onClick: () => void } }];
    expect(options.action.label).toBe("Next in queue");
    options.action.onClick();
    expect(push).toHaveBeenCalledWith(`${STORE}/exceptions/exc-2`);
  });

  it("moves the actions into a sticky bottom bar with a More sheet below 768 px", async () => {
    useNarrowScreen();
    detailRoutes(
      detailFixture({
        available_actions: ["acknowledge", "start", "claim", "resolve", "add_note", "assign", "set_due_date"],
        blocked_actions: [{ action: "dismiss", code: "PERMISSION_DENIED", reason: "No." }] as never,
      }),
    );
    renderInStore(<ExceptionScreen />, testStore({ permissions: [...VIEWER, "exceptions.work", "exceptions.assign"] }));
    const user = userEvent.setup();
    const bar = await screen.findByRole("toolbar", { name: "Exception actions" });
    expect(bar).toHaveClass("fixed", "bottom-0");
    expect(within(bar).getByRole("button", { name: "Acknowledge" })).toBeInTheDocument();

    await user.click(within(bar).getByRole("button", { name: "More actions" }));
    const sheet = await screen.findByRole("dialog", { name: "Actions" });
    const dismiss = within(sheet).getByRole("button", { name: /Dismiss…/ });
    expect(dismiss).toHaveAttribute("aria-disabled", "true");
    expect(dismiss).toHaveTextContent("Dismissing requires the Manage exceptions permission.");
    await user.click(within(sheet).getByRole("button", { name: /Resolve…/ }));
    expect(await screen.findByRole("dialog", { name: "Resolve EXC-1002" })).toBeInTheDocument();
  });

  it("jumps to a section from On this page", async () => {
    const scrolled: string[] = [];
    Element.prototype.scrollIntoView = function scrollIntoView(this: Element) {
      scrolled.push(this.id);
    };
    detailRoutes();
    renderInStore(<ExceptionScreen />, testStore({ permissions: MANAGER }));
    const jump = await screen.findByRole("combobox", { name: "On this page" });
    expect(within(jump).getAllByRole("option").map((option) => option.textContent)).toEqual([
      "Jump to a section",
      "Why this priority",
      "How this was detected",
      "Evidence",
      "Affected orders",
      "Activity",
      "Details",
    ]);
    await userEvent.selectOptions(jump, "evidence");
    expect(scrolled).toEqual(["evidence"]);
    expect(screen.getByRole("heading", { name: "Evidence" })).toHaveFocus();
  });

  it("links evidence sources and affected orders to their pages", async () => {
    detailRoutes(
      detailFixture({
        evidence: {
          facts: [
            { key: "on_hand", label: "On hand", value: 5, unit: "units", estimate: false, volatile: false, source: { type: "inventory_balance", id: "p1", label: "Inventory balance of KHK-KT-012" } },
            { key: "supplier", label: "Supplier", value: "Evergreen", unit: null, estimate: false, volatile: false, source: { type: "supplier", id: "s1", label: "Evergreen Woodworks" } },
          ],
          records: {
            affected_orders: [{ order_id: "o1", order_number: "KHK-12015", uncovered_quantity: 1, value_at_risk: "18.95" }],
            rejected_import_rows: [{ import_id: "imp-3", source: { type: "data_import", id: "imp-3", label: "Data import" } }],
          },
          notes: [],
        },
      }),
    );
    renderInStore(<ExceptionScreen />, testStore({ permissions: MANAGER }));
    expect(await screen.findByRole("link", { name: "Inventory balance of KHK-KT-012" })).toHaveAttribute("href", `${STORE}/products/p1`);
    expect(screen.getByText("Evergreen Woodworks").closest("a")).toBeNull();
    expect(screen.getByRole("link", { name: "KHK-12015" })).toHaveAttribute("href", `${STORE}/orders/o1`);
    expect(screen.getByRole("link", { name: "Data import" })).toHaveAttribute("href", `${STORE}/imports/imp-3`);
  });

  it("keeps sources as text without the permission to open them", () => {
    const source = { type: "order", id: "o1", label: "Order KHK-1" };
    expect(sourceHref(STORE_ID, new Set(["orders.read"]), source)).toBe(`${STORE}/orders/o1`);
    expect(sourceHref(STORE_ID, new Set([]), source)).toBeUndefined();
    expect(sourceHref(STORE_ID, new Set(["catalog.read"]), { type: "product", id: "p1", label: "KHK" })).toBe(`${STORE}/products/p1`);
  });

  it("explains how resolution works to viewers, with live examples", async () => {
    const denied = (action: string) => ({ action, code: "PERMISSION_DENIED", reason: "Your role does not allow this action." });
    detailRoutes(detailFixture({ available_actions: [], blocked_actions: ["acknowledge", "start", "resolve", "dismiss"].map(denied) as never }), {
      "/exceptions": jsonResponse(
        page([
          listItemFixture({ id: "auto", reference: "EXC-1004", status: "RESOLVED", resolution_code: "CONDITION_CLEARED", verified_at: null }),
          listItemFixture({ id: "manual", reference: "EXC-1007", status: "RESOLVED", resolution_code: "STOCK_REPLENISHED", verified_at: "2026-10-31T14:00:00Z" }),
        ]),
      ),
    });
    renderInStore(<ExceptionScreen />, testStore({ permissions: VIEWER, role: "VIEWER" }));
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "How resolution works" }));
    expect(await screen.findByText("Resolved — awaiting verification")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "A verified example: EXC-1007" })).toHaveAttribute("href", `${STORE}/exceptions/manual`);
  });

  it("shows the explainer to viewers only", async () => {
    detailRoutes();
    renderInStore(<ExceptionScreen />, testStore({ permissions: MANAGER }));
    await screen.findByRole("heading", { level: 1 });
    expect(screen.queryByRole("button", { name: "How resolution works" })).not.toBeInTheDocument();
    expect(verifiedExample([listItemFixture({ resolution_code: "SUPERSEDED", verified_at: "2026-10-31T14:00:00Z" })])).toBeUndefined();
  });
});
