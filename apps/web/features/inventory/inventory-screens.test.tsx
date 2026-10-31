import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Permission } from "@/lib/api/auth";
import { listItemFixture } from "@/test/exception-fixtures";
import { jsonResponse, routeFetch } from "@/test/fetch";
import { dashboardFixture } from "@/test/fixtures";
import { movementFixture, positionFixture, productDetailFixture, productListItemFixture } from "@/test/inventory-fixtures";
import { renderInStore, testStore } from "@/test/render";

import { MovementsScreen } from "./movements-screen";
import { PositionsScreen } from "./positions-screen";
import { ProductScreen } from "./product-screen";
import { ProductsScreen } from "./products-screen";

const replace = vi.fn();
let search = new URLSearchParams();
let pathname = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn() }),
  usePathname: () => pathname,
  useSearchParams: () => search,
  useParams: () => ({ productId: "p1" }),
}));

const STORE = "/s/f0da0f22-b9e0-4483-b144-e9f0f8703d13";
const VIEWER: Permission[] = ["dashboard.read", "exceptions.read", "orders.read", "catalog.read", "inventory.read"];
const page = <T,>(items: T[]) => ({ items, page: 1, page_size: 25, total: items.length });

beforeEach(() => {
  replace.mockReset();
  search = new URLSearchParams();
});

describe("ProductsScreen (S-07)", () => {
  beforeEach(() => {
    pathname = `${STORE}/products`;
  });
  const routes = (items = [productListItemFixture()]) =>
    routeFetch({
      "/products": jsonResponse(page(items)),
      "/categories": jsonResponse({ items: ["Kitchen", "Bath"] }),
      "/suppliers": jsonResponse(page([{ id: "sup-1", name: "Evergreen Woodworks" }])),
    });

  it("lists products with stock health and flags cost above price", async () => {
    routes([productListItemFixture({ unit_cost: "40.00" })]);
    renderInStore(<ProductsScreen />, testStore({ permissions: VIEWER }));
    const table = (await screen.findAllByRole("table"))[0];
    expect(await within(table).findByRole("link", { name: "KHK-BW-012" })).toHaveAttribute("href", `${STORE}/products/p1`);
    expect(within(table).getByText("Approaching reorder point")).toBeInTheDocument();
    expect(within(table).getByRole("button", { name: "Unit cost is higher than unit price." })).toBeInTheDocument();
  });

  it("hides stock columns without inventory access", async () => {
    routes();
    renderInStore(<ProductsScreen />, testStore({ permissions: ["catalog.read"] }));
    const table = (await screen.findAllByRole("table"))[0];
    await within(table).findByRole("link", { name: "KHK-BW-012" });
    expect(screen.queryByRole("columnheader", { name: "Stock" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Stock/ })).not.toBeInTheDocument();
  });

  it("shows the import empty state for a store with no products", async () => {
    routes([]);
    renderInStore(<ProductsScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByText("No products yet")).toBeInTheDocument();
  });

  it("shows permission denied without catalog access", () => {
    renderInStore(<ProductsScreen />, testStore({ permissions: ["inventory.read"] }));
    expect(screen.getByRole("heading", { name: "You don't have access to products" })).toBeInTheDocument();
  });
});

describe("ProductScreen (S-08)", () => {
  const routes = (product = productDetailFixture(), active = [] as ReturnType<typeof listItemFixture>[]) =>
    routeFetch({
      "/products/p1": jsonResponse(product),
      "/exceptions": (() => {
        let call = 0;
        return () => jsonResponse(page(call++ === 0 ? active : []));
      })(),
      "/inventory/movements": jsonResponse(page([movementFixture()])),
    });

  it("shows the stock arithmetic and links the full ledger", async () => {
    routes();
    renderInStore(<ProductScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByRole("heading", { level: 1, name: "Bamboo cutting board, large" })).toBeInTheDocument();
    expect(screen.getByText(/available = on_hand − reserved = 18 − 3 = 15 \(BR-101\)/)).toBeInTheDocument();
    expect(screen.getByText(/Healthy: available is above 12, the approaching threshold for reorder point 10/)).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "View all movements" })).toHaveAttribute(
      "href",
      `${STORE}/inventory/movements?product_id=p1`,
    );
  });

  it("calls negative on-hand a data issue, not oversold (BR-402a)", async () => {
    routes(
      productDetailFixture({ health: "OVERSOLD", stock: { on_hand: -4, reserved: 0, available: -4, incoming: 0, incoming_eta: null, last_cycle_count_at: null } }),
      [listItemFixture({ id: "e9", reference: "EXC-1042", exception_type: "DATA_NEGATIVE_ON_HAND" })],
    );
    renderInStore(<ProductScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByText(/which is physically impossible/)).toBeInTheDocument();
    expect(screen.queryByText("Oversold")).not.toBeInTheDocument();
    expect(screen.getAllByText("Data issue").length).toBeGreaterThan(0);
    // Available and days of cover both rest on the impossible on-hand figure.
    expect(screen.getAllByText("not reliable")).toHaveLength(2);
    expect(await screen.findAllByRole("link", { name: "EXC-1042" })).not.toHaveLength(0);
  });
});

describe("PositionsScreen (S-09)", () => {
  beforeEach(() => {
    pathname = `${STORE}/inventory`;
  });
  const routes = (items = [positionFixture()]) =>
    routeFetch({
      "/inventory/positions": jsonResponse(page(items)),
      "/analytics/dashboard": jsonResponse(dashboardFixture()),
      "/categories": jsonResponse({ items: ["Kitchen"] }),
    });

  it("counts each health bucket and toggles it as a filter", async () => {
    routes();
    renderInStore(<PositionsScreen />, testStore({ permissions: VIEWER }));
    const oversold = await screen.findByRole("button", { name: /Oversold\s*3/ });
    expect(oversold).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(oversold);
    expect(replace).toHaveBeenCalledWith(`${STORE}/inventory?health=OVERSOLD`, { scroll: false });
    expect(screen.getByText(/never counted as available \(BR-101, BR-103\)/)).toBeInTheDocument();
  });

  it("treats an empty oversold filter as good news", async () => {
    search = new URLSearchParams("health=OVERSOLD");
    const fetchMock = routes([]);
    renderInStore(<PositionsScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByText("No oversold products")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Oversold\s*3/ })).toHaveAttribute("aria-pressed", "true");
    const positionsCall = fetchMock.mock.calls.map((call) => String(call[0])).find((url) => url.includes("/inventory/positions"));
    expect(positionsCall).toContain("health=OVERSOLD");
    expect(positionsCall).toContain("page_size=50");
  });

  it("offers only the page sizes its URL state accepts", async () => {
    routes([positionFixture()]);
    renderInStore(<PositionsScreen />, testStore({ permissions: VIEWER }));
    const sizes = await screen.findByLabelText("Rows per page");
    expect(within(sizes).getAllByRole("option").map((option) => option.textContent)).toEqual(["50", "100"]);
  });

  it("shows a negative on-hand row as a data issue without days of cover", async () => {
    routes([positionFixture({ on_hand: -4, available: -4, health: "OVERSOLD", days_of_cover: null })]);
    renderInStore(<PositionsScreen />, testStore({ permissions: VIEWER }));
    const table = (await screen.findAllByRole("table"))[0];
    expect(await within(table).findByText("Data issue")).toBeInTheDocument();
    expect(within(table).queryByText("Oversold")).not.toBeInTheDocument();
  });
});

describe("MovementsScreen (S-10)", () => {
  beforeEach(() => {
    pathname = `${STORE}/inventory/movements`;
  });

  it("shows signed deltas and links shipments to their order", async () => {
    routeFetch({
      "/inventory/movements": jsonResponse(
        page([
          movementFixture(),
          movementFixture({
            id: "m2",
            movement_type: "SHIPMENT",
            on_hand_delta: -2,
            on_hand_after: 56,
            incoming_delta: 0,
            source: "ORDER",
            reference: "order_item:9b1",
            note: "Order KHK-12023",
            created_by: null,
          }),
          movementFixture({ id: "m3", movement_type: "CORRECTION", on_hand_delta: 1, created_by: "u2", reference: null }),
          movementFixture({ id: "m4", movement_type: "DAMAGE", on_hand_delta: -1, created_by: "u-gone", reference: null }),
        ]),
      ),
      "/members": jsonResponse({ items: [{ id: "u2", full_name: "Marcus Lee", role: "STAFF", can_work_exceptions: true }] }),
    });
    renderInStore(<MovementsScreen />, testStore({ permissions: VIEWER }));
    const table = await screen.findByRole("table");
    expect(await within(table).findByText("+40")).toBeInTheDocument();
    expect(within(table).getByText("−2")).toBeInTheDocument();
    expect(within(table).getByText("Shipment")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "Order KHK-12023" })).toHaveAttribute("href", `${STORE}/orders?q=KHK-12023`);
    expect(within(table).getAllByText("Order KHK-12023")).toHaveLength(1);
    expect(within(table).getByText("PO-2291")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Occurred (ET)" })).toBeInTheDocument();
    expect(await within(table).findByText("Marcus Lee")).toBeInTheDocument();
    expect(within(table).getByText("Former member")).toBeInTheDocument();
    expect(within(table).getAllByText("System")).toHaveLength(2);
  });

  it("filters by product from a link and names it in a chip", async () => {
    const productId = "0b9c3f1e-2a4d-4c6b-8e7f-1a2b3c4d5e6f";
    search = new URLSearchParams(`product_id=${productId}&occurred=7d`);
    const fetchMock = routeFetch({
      "/inventory/movements": jsonResponse(page([])),
      [`/products/${productId}`]: jsonResponse(productDetailFixture({ id: productId })),
      "/members": jsonResponse({ items: [] }),
    });
    renderInStore(<MovementsScreen />, testStore({ permissions: VIEWER }));
    expect(await screen.findByText("Product: KHK-BW-012")).toBeInTheDocument();
    expect(screen.getByText("No movements match these filters")).toBeInTheDocument();
    const url = fetchMock.mock.calls.map((call) => String(call[0])).find((u) => u.includes("/inventory/movements")) ?? "";
    expect(url).toContain(`product_id=${productId}`);
    expect(url).toMatch(/from=\d{4}-\d{2}-\d{2}T/);
    expect(url).toContain("sort=-occurred_at");
  });

  it("drops an unknown movement type from a shared link", async () => {
    search = new URLSearchParams("movement_type=TELEPORT");
    routeFetch({ "/inventory/movements": jsonResponse(page([])), "/members": jsonResponse({ items: [] }) });
    renderInStore(<MovementsScreen />, testStore({ permissions: VIEWER }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith(`${STORE}/inventory/movements`, { scroll: false }));
  });
});
