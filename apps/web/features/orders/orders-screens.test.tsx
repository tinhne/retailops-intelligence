import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { toast } from "sonner";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Permission } from "@/lib/api/auth";
import { jsonResponse, routeFetch } from "@/test/fetch";
import { linkedExceptionFixture, orderDetailFixture, orderListItemFixture } from "@/test/order-fixtures";
import { renderInStore, testStore } from "@/test/render";

import { OrderScreen, transitionText } from "./order-screen";
import { OrdersScreen } from "./orders-screen";

const replace = vi.fn();
let search = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/orders",
  useSearchParams: () => search,
  useParams: () => ({ orderId: "o1" }),
}));

const VIEWER: Permission[] = ["dashboard.read", "exceptions.read", "orders.read", "catalog.read", "inventory.read"];
const page = <T,>(items: T[]) => ({ items, page: 1, page_size: 25, total: items.length });

beforeEach(() => {
  replace.mockReset();
  search = new URLSearchParams();
});

describe("OrdersScreen (S-05)", () => {
  it("lists orders with their three status axes and the overdue flag", async () => {
    routeFetch({ "/orders": jsonResponse(page([orderListItemFixture()])) });
    renderInStore(<OrdersScreen />, testStore({ permissions: VIEWER }));

    const table = (await screen.findAllByRole("table"))[0];
    await within(table).findByRole("link", { name: "KHK-12023" });
    expect(within(table).getByRole("link", { name: "KHK-12023" })).toHaveAttribute(
      "href",
      "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/orders/o1",
    );
    expect(within(table).getByText("Ready to ship")).toBeInTheDocument();
    expect(within(table).getByText("Payment:", { exact: false })).toBeInTheDocument();
    expect(within(table).getByText(/^Overdue/)).toBeInTheDocument();
    expect(within(table).getByText("$54.42")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Placed (ET)" })).toBeInTheDocument();
  });

  it("calls an empty overdue-only result good news", async () => {
    search = new URLSearchParams("overdue=true");
    const fetchMock = routeFetch({ "/orders": jsonResponse(page([])) });
    renderInStore(<OrdersScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByText("No overdue orders")).toBeInTheDocument();
    expect(String(fetchMock.mock.calls[0][0])).toContain("overdue=true");
  });

  it("filters by a custom placed range in store days and refuses a reversed one", async () => {
    search = new URLSearchParams("placed=custom&placed_from=2026-10-01&placed_to=2026-10-31");
    const fetchMock = routeFetch({ "/orders": jsonResponse(page([orderListItemFixture()])) });
    renderInStore(<OrdersScreen />, testStore({ permissions: VIEWER }));

    await screen.findAllByRole("link", { name: "KHK-12023" });
    const url = String(fetchMock.mock.calls[0][0]);
    expect(url).toContain(`placed_from=${encodeURIComponent("2026-10-01T04:00:00.000Z")}`);
    expect(url).toContain(`placed_to=${encodeURIComponent("2026-11-01T04:00:00.000Z")}`);
    expect(screen.getByText("Placed: Oct 1 – Oct 31")).toBeInTheDocument();

    const to = screen.getByLabelText("Placed to");
    fireEvent.change(to, { target: { value: "2026-09-15" } });
    expect(screen.getByRole("alert")).toHaveTextContent("End date must be on or after start date.");
    expect(to).toHaveAttribute("aria-invalid", "true");
    expect(replace).not.toHaveBeenCalled();

    fireEvent.change(to, { target: { value: "2026-10-15" } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(replace).toHaveBeenLastCalledWith(
      "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/orders?placed=custom&placed_from=2026-10-01&placed_to=2026-10-15",
      { scroll: false },
    );
  });

  it("drops unknown filters from a shared link", async () => {
    search = new URLSearchParams("status=LOST");
    const info = vi.spyOn(toast, "info");
    routeFetch({ "/orders": jsonResponse(page([])) });
    renderInStore(<OrdersScreen />, testStore({ permissions: VIEWER }));
    await waitFor(() => expect(info).toHaveBeenCalled());
    expect(replace).toHaveBeenCalledWith("/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/orders", { scroll: false });
  });
});

describe("OrderScreen (S-06)", () => {
  function routes(order = orderDetailFixture()) {
    return routeFetch({
      "/orders/o1": jsonResponse(order),
      "/stores/f0da0f22-b9e0-4483-b144-e9f0f8703d13": jsonResponse({ settings: { fulfillment_sla_hours: 48 } }),
      "/inventory/positions": jsonResponse(page([{ sku: "KHK-BW-012", health: "HEALTHY", on_hand: 12 }])),
    });
  }

  it("explains a cancelled but paid order and links its refund exception", async () => {
    routes();
    renderInStore(<OrderScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByRole("heading", { level: 1, name: "Order KHK-12027" })).toBeInTheDocument();
    expect(screen.getByText(/Cancelled but still paid: a refund is pending/)).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: "EXC-1015" });
    expect(links[0]).toHaveAttribute("href", "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/exceptions/e1");
    expect(await screen.findByText("(Store SLA: paid + 48 h)")).toBeInTheDocument();
    expect(await screen.findByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("Paid → Cancelled, via Processing")).toBeInTheDocument();
  });

  it("shows the expected total and difference when the total does not add up (BR-205)", async () => {
    const order = orderDetailFixture({
      status: "PROCESSING",
      exceptions: [linkedExceptionFixture({ id: "e2", reference: "EXC-1016", exception_type: "DATA_ORDER_TOTAL_MISMATCH", severity: "MEDIUM" })],
    });
    order.amounts = { ...order.amounts, total: "66.92", expected_total: "54.42", difference: "12.50", has_total_mismatch: true };
    routes(order);
    renderInStore(<OrderScreen />, testStore({ permissions: VIEWER }));
    const totals = await screen.findByRole("region", { name: "Totals" });
    expect(within(totals).getByText("Expected total")).toHaveClass("text-tone-danger-fg");
    expect(within(totals).getByText("$12.50")).toBeInTheDocument();
    expect(within(totals).getByRole("link", { name: "EXC-1016" })).toBeInTheDocument();
  });

  it("does not present an unverified manual resolution as a success", async () => {
    routes(
      orderDetailFixture({
        exceptions: [linkedExceptionFixture({ status: "RESOLVED", is_active: false, resolution_code: "REFUND_ISSUED", verified_at: null })],
      }),
    );
    renderInStore(<OrderScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByText("Resolved — awaiting verification")).toBeInTheDocument();
  });

  it("omits the stock column and exceptions without the permissions", async () => {
    const fetchMock = routes();
    renderInStore(<OrderScreen />, testStore({ permissions: ["orders.read"] }));
    await screen.findByRole("heading", { level: 1, name: "Order KHK-12027" });
    expect(screen.queryByRole("columnheader", { name: "Stock" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Exceptions" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/inventory/positions"))).toBe(false);
  });

  it("links status changes to the import file that made them", async () => {
    const order = orderDetailFixture();
    order.events = order.events.map((event) => ({ ...event, import_id: "imp-9", import_filename: "orders_2026-10-28.csv" }));
    routes(order);
    const { unmount } = renderInStore(<OrderScreen />, testStore({ permissions: [...VIEWER, "imports.read"] }));
    const links = await screen.findAllByRole("link", { name: "Import orders_2026-10-28.csv" });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13/imports/imp-9");
    unmount();

    // Without imports.read the file name stays as text.
    routes(order);
    renderInStore(<OrderScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findAllByText("orders_2026-10-28.csv")).toHaveLength(2);
    expect(screen.queryByRole("link", { name: /orders_2026-10-28\.csv/ })).not.toBeInTheDocument();
  });

  it("words imported status jumps", () => {
    expect(transitionText("PAID", "SHIPPED", ["PROCESSING", "READY_TO_SHIP"])).toBe("Paid → Shipped, via Processing, Ready to ship");
    expect(transitionText(null, "CREATED", [])).toBe("Created");
    expect(transitionText(null, "PAID", [])).toBe("Created: Paid");
  });
});
