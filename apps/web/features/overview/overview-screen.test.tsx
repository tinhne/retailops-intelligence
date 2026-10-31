import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { toast } from "sonner";
import { describe, expect, it, vi } from "vitest";

import type { Permission } from "@/lib/api/auth";
import { errorResponse, jsonResponse, routeFetch } from "@/test/fetch";
import { dashboardFixture, trendsFixture } from "@/test/fixtures";
import { renderInStore, testStore } from "@/test/render";

import { completionMessage } from "../evaluations/run-analysis-button";
import { staleAge } from "./freshness-strip";
import { hasNoData, OverviewScreen } from "./overview-screen";
import { shipmentPoints, shipmentSummary } from "./shipments-chart";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));

const VIEWER: Permission[] = [
  "dashboard.read",
  "exceptions.read",
  "orders.read",
  "catalog.read",
  "inventory.read",
  "imports.read",
  "analytics.read",
  "copilot.use",
  "audit.read",
  "settings.read",
];
const MANAGER: Permission[] = [...VIEWER, "exceptions.work", "exceptions.assign", "exceptions.manage", "evaluations.run", "imports.run"];

const emptyPage = { items: [], page: 1, page_size: 1, total: 0 };

function routes(overrides: Record<string, Response | (() => Response) | Error> = {}) {
  return routeFetch({
    "/analytics/dashboard": jsonResponse(dashboardFixture()),
    "/analytics/trends": jsonResponse(trendsFixture([{ date: "2026-10-30", on: 20, late: 1 }, { date: "2026-10-31", on: 9, late: 0 }])),
    "/exceptions": jsonResponse({ ...emptyPage, total: 2 }),
    "/imports": jsonResponse(emptyPage),
    ...overrides,
  });
}

describe("OverviewScreen (S-02)", () => {
  it("shows the KPIs, the attention list and the side cards from the dashboard", async () => {
    routes();
    renderInStore(<OverviewScreen />, testStore({ permissions: VIEWER, isDemo: true, role: "VIEWER" }));

    expect(await screen.findByText("Needs attention")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Overview" })).toBeInTheDocument();
    expect(screen.getByText("2 P1 · 6 P2")).toBeInTheDocument();
    expect(screen.getByText("94.1%")).toBeInTheDocument();
    expect(screen.getByText("412 of 438 on time")).toBeInTheDocument();
    expect(screen.getByText(/Scheduled · Succeeded/)).toBeInTheDocument();
    expect(screen.getByText("No CSV imports yet.")).toBeInTheDocument();

    const attention = screen.getByRole("list", { name: "Active exceptions by priority" });
    expect(within(attention).getAllByRole("listitem")).toHaveLength(2);
    expect(within(attention).getByText("EXC-1010")).toBeInTheDocument();
    expect(within(attention).getByRole("img", { name: "Priority P1, score 72 of 100" })).toBeInTheDocument();
    expect(within(attention).getByText(/^Overdue/)).toBeInTheDocument();
    expect(within(attention).getByText("Marcus Lee")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Open triage queue (2)" })).toHaveAttribute(
      "href",
      "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/exceptions?view=triage",
    );
  });

  it("shows value at risk per category only, with no total, and none for data quality (BR-404)", async () => {
    routes();
    renderInStore(<OverviewScreen />, testStore({ permissions: VIEWER }));

    const table = await screen.findByRole("table");
    const row = (name: string) => within(table).getByRole("row", { name: new RegExp(`^${name}`) });
    expect(within(row("Inventory")).getByText("$345.70")).toBeInTheDocument();
    expect(within(row("Payment")).getByText("$86.16")).toBeInTheDocument();
    expect(within(row("Data quality")).getByLabelText("None")).toBeInTheDocument();
    expect(within(table).queryByText(/total/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Not a measure of loss/)).toBeInTheDocument();
  });

  it("links to built screens only", async () => {
    routes();
    renderInStore(<OverviewScreen />, testStore({ permissions: VIEWER }));
    await screen.findByText("Needs attention");
    const hrefs = screen.queryAllByRole("link").map((link) => link.getAttribute("href") ?? "");
    // Exceptions (T-062) and orders (T-063) exist; inventory is not built yet.
    expect(hrefs.filter((href) => href.includes("/inventory"))).toEqual([]);
    expect(hrefs).toContain("/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/orders?overdue=true&sort=ship_by");
    expect(hrefs).toContain("/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/exceptions?view=active");
    expect(screen.getByRole("link", { name: /EXC-1010, Order KHK-12023/ })).toHaveAttribute(
      "href",
      "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/exceptions/e1",
    );
  });

  it("says when nothing needs attention", async () => {
    routes({ "/analytics/dashboard": jsonResponse(dashboardFixture({ attention: [] })) });
    renderInStore(<OverviewScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByText("Nothing needs attention")).toBeInTheDocument();
  });

  it("replaces the dashboard with an empty state when the store has no data", async () => {
    const empty = dashboardFixture();
    empty.inventory = { ...empty.inventory, active_products: 0 };
    empty.active_exceptions = { ...empty.active_exceptions, total: 0 };
    routes({ "/analytics/dashboard": jsonResponse({ ...empty, attention: [] }) });
    renderInStore(<OverviewScreen />, testStore({ permissions: VIEWER }));

    expect(await screen.findByText("No data yet")).toBeInTheDocument();
    expect(screen.getByText("Ask an owner or manager to import data.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Orders" })).toHaveAttribute(
      "href",
      "/api/v1/stores/f0da0f22-b9e0-4483-b144-e9f0f8703d13/imports/templates/orders",
    );
    expect(screen.queryByText("Needs attention")).not.toBeInTheDocument();
  });

  it("shows one error with retry when the dashboard fails, and loads again on retry", async () => {
    let calls = 0;
    routes({
      "/analytics/dashboard": () =>
        ++calls === 1
          ? errorResponse(404, "NOT_FOUND", "Store not found.", { requestId: "req-9" })
          : jsonResponse(dashboardFixture()),
    });
    renderInStore(<OverviewScreen />, testStore({ permissions: VIEWER }));

    expect(await screen.findByText("Couldn't load the overview")).toBeInTheDocument();
    expect(screen.getByText("req-9")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Needs attention")).toBeInTheDocument();
  });

  it("explains a missing permission instead of loading", () => {
    const fetchMock = routes();
    renderInStore(<OverviewScreen />, testStore({ permissions: [] }));
    expect(screen.getByRole("heading", { name: "You don't have access to the overview" })).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps Run analysis visible but read-only for the public demo", async () => {
    routes();
    renderInStore(<OverviewScreen />, testStore({ permissions: VIEWER, isDemo: true, role: "VIEWER" }));
    const button = await screen.findByRole("button", { name: /Run analysis/ });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button).toHaveAccessibleDescription("The public demo is read-only.");
  });

  it("runs an analysis, reusing the Idempotency-Key when the same attempt is retried", async () => {
    const success = vi.spyOn(toast, "success");
    const failure = vi.spyOn(toast, "error");
    let posts = 0;
    const fetchMock = routes({
      "/evaluations": () =>
        ++posts === 1
          ? errorResponse(503, "UNAVAILABLE", "Down.")
          : jsonResponse(
              { id: "run-2", status: "SUCCEEDED", counts: { created: 2, refreshed: 5, resolved: 1, reopened: 0 } },
              { status: 201 },
            ),
    });
    renderInStore(<OverviewScreen />, testStore({ permissions: MANAGER }));
    const user = userEvent.setup();
    const button = await screen.findByRole("button", { name: /Run analysis/ });

    await user.click(button);
    await waitFor(() => expect(failure).toHaveBeenCalledWith("The service is temporarily unavailable.", expect.anything()));
    await user.click(screen.getByRole("button", { name: /Run analysis/ }));
    await waitFor(() => expect(success).toHaveBeenCalledWith("Analysis complete: 2 new, 5 refreshed, 1 resolved, 0 reopened"));

    const keys = fetchMock.mock.calls
      .filter(([url]) => String(url).endsWith("/evaluations"))
      .map(([, init]) => (init?.headers as Record<string, string>)["Idempotency-Key"]);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBeTruthy();
    expect(keys[1]).toBe(keys[0]);
  });
});

describe("overview helpers", () => {
  it("detects a store with no data", () => {
    expect(hasNoData(dashboardFixture())).toBe(false);
    const empty = dashboardFixture();
    empty.inventory = { ...empty.inventory, active_products: 0 };
    empty.active_exceptions = { ...empty.active_exceptions, total: 0 };
    expect(hasNoData(empty)).toBe(true);
  });

  it("words the analysis result and stale data", () => {
    expect(completionMessage({ created: 2, refreshed: 5, resolved: 1 })).toBe(
      "Analysis complete: 2 new, 5 refreshed, 1 resolved, 0 reopened",
    );
    expect(staleAge(30)).toBe("30 hours ago");
    expect(staleAge(50)).toBe("50 hours ago");
    expect(staleAge(80)).toBe("3 days ago");
  });

  it("summarises the shipments chart for its accessible name", () => {
    const points = shipmentPoints(trendsFixture([{ date: "2026-10-02", on: 18, late: 2 }, { date: "2026-10-31", on: 9, late: 0 }]));
    expect(points[0]).toMatchObject({ label: "Oct 2", onTime: 18, late: 2 });
    expect(shipmentSummary(points)).toBe("Shipments per day, Oct 2 to Oct 31: 27 on time, 2 late");
  });
});
