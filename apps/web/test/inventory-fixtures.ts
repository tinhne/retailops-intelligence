import type { Movement, ProductDetail, ProductListItem } from "@/lib/api/inventory-api";
import type { InventoryPosition } from "@/lib/api/orders-api";

export function productListItemFixture(overrides: Partial<ProductListItem> = {}): ProductListItem {
  return {
    id: "p1",
    sku: "KHK-BW-012",
    name: "Bamboo cutting board, large",
    category: "Kitchen",
    status: "ACTIVE",
    unit_price: "34.00",
    unit_cost: "12.50",
    supplier: { id: "sup-1", name: "Evergreen Woodworks" },
    reorder_point: 10,
    reorder_quantity: 40,
    on_hand: 18,
    reserved: 3,
    available: 15,
    health: "APPROACHING_REORDER_POINT",
    updated_at: "2026-10-25T14:00:00Z",
    ...overrides,
  };
}

const estimate = (value: string | null): ProductDetail["avg_daily_units"] => ({
  value,
  is_estimate: true,
  basis: "units shipped over the window",
  window_days: 28,
  note: null,
});

export function productDetailFixture(overrides: Partial<ProductDetail> = {}): ProductDetail {
  return {
    id: "p1",
    sku: "KHK-BW-012",
    name: "Bamboo cutting board, large",
    category: "Kitchen",
    status: "ACTIVE",
    unit_price: "34.00",
    unit_cost: "12.50",
    supplier: { id: "sup-1", name: "Evergreen Woodworks", lead_time_days: 7 },
    reorder_point: 10,
    reorder_quantity: 40,
    approaching_threshold: 12,
    health: "HEALTHY",
    stock: { on_hand: 18, reserved: 3, available: 15, incoming: 40, incoming_eta: "2026-11-04T16:00:00Z", last_cycle_count_at: "2026-10-20T13:00:00Z" },
    avg_daily_units: estimate("1.43"),
    days_of_cover: estimate("10.5"),
    active_exception_count: 0,
    created_at: "2026-08-01T12:00:00Z",
    updated_at: "2026-10-25T14:00:00Z",
    ...overrides,
  };
}

export function positionFixture(overrides: Partial<InventoryPosition> = {}): InventoryPosition {
  return {
    product_id: "p1",
    sku: "KHK-BW-012",
    name: "Bamboo cutting board, large",
    category: "Kitchen",
    status: "ACTIVE",
    on_hand: 18,
    reserved: 3,
    available: 15,
    incoming: 40,
    incoming_eta: "2026-11-04T16:00:00Z",
    reorder_point: 10,
    health: "HEALTHY",
    avg_daily_units: "1.43",
    days_of_cover: "10.5",
    last_cycle_count_at: "2026-10-20T13:00:00Z",
    ...overrides,
  };
}

export function movementFixture(overrides: Partial<Movement> = {}): Movement {
  return {
    id: "m1",
    product_id: "p1",
    sku: "KHK-BW-012",
    product_name: "Bamboo cutting board, large",
    movement_type: "RECEIPT",
    on_hand_delta: 40,
    on_hand_after: 58,
    incoming_delta: -40,
    incoming_after: 0,
    source: "IMPORT",
    reference: "PO-2291",
    note: null,
    import_id: "imp-1",
    created_by: null,
    occurred_at: "2026-10-28T14:00:00Z",
    recorded_at: "2026-10-28T14:05:00Z",
    ...overrides,
  };
}
