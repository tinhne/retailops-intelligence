import type { LinkedException, OrderDetail, OrderListItem } from "@/lib/api/orders-api";

export function orderListItemFixture(overrides: Partial<OrderListItem> = {}): OrderListItem {
  return {
    id: "o1",
    order_number: "KHK-12023",
    channel: "WEB",
    currency: "USD",
    customer_ref: "CUST-1",
    status: "READY_TO_SHIP",
    payment_status: "PAID",
    fulfillment_status: "IN_PROGRESS",
    placed_at: "2026-10-25T23:47:00Z",
    paid_at: "2026-10-25T23:55:00Z",
    ship_by: "2026-10-27T23:55:00Z",
    ship_by_source: "STORE_SLA",
    shipped_at: null,
    total: "54.42",
    line_count: 1,
    is_overdue: true,
    ...overrides,
  };
}

export function linkedExceptionFixture(overrides: Partial<LinkedException> = {}): LinkedException {
  return {
    id: "e1",
    reference: "EXC-1015",
    title: "Refund pending for cancelled order KHK-12027",
    exception_type: "ORDER_REFUND_PENDING",
    severity: "CRITICAL",
    status: "OPEN",
    priority_band: "P1",
    link_role: "PRIMARY",
    is_active: true,
    resolution_code: null,
    verified_at: null,
    ...overrides,
  };
}

export function orderDetailFixture(overrides: Partial<OrderDetail> = {}): OrderDetail {
  return {
    id: "o1",
    order_number: "KHK-12027",
    channel: "WEB",
    customer_ref: "CUST-23245",
    status: "CANCELLED",
    payment_status: "PAID",
    fulfillment_status: "UNFULFILLED",
    placed_at: "2026-10-27T13:47:00Z",
    paid_at: "2026-10-27T13:55:00Z",
    ship_by: "2026-10-29T13:55:00Z",
    ship_by_source: "STORE_SLA",
    shipped_at: null,
    delivered_at: null,
    cancelled_at: "2026-10-28T09:47:00Z",
    carrier: null,
    tracking_number: null,
    hours_overdue: null,
    is_overdue: false,
    last_import_id: null,
    created_at: "2026-10-31T17:47:00Z",
    updated_at: "2026-10-31T17:47:00Z",
    lines: [
      {
        id: "l1",
        line_number: 1,
        product_id: "p1",
        sku: "KHK-BW-012",
        product_sku: "KHK-BW-012",
        product_name: "Acacia Salad Servers",
        quantity: 1,
        unit_price: "33.95",
        line_discount: "0.00",
        line_total: "33.95",
        reservation: { status: "RELEASED", quantity: 1 },
      },
    ],
    amounts: {
      currency: "USD",
      subtotal: "33.95",
      discount_total: "0.00",
      shipping_total: "6.95",
      tax_total: "2.72",
      total: "43.62",
      lines_total: "33.95",
      expected_total: "43.62",
      difference: "0.00",
      has_total_mismatch: false,
    },
    events: [
      { id: "ev1", from_status: null, to_status: "PAID", skipped_statuses: [], source: "IMPORT", import_id: null, actor_user_id: null, payment_status: "PAID", fulfillment_status: "UNFULFILLED", occurred_at: "2026-10-27T13:55:00Z" },
      { id: "ev2", from_status: "PAID", to_status: "CANCELLED", skipped_statuses: ["PROCESSING"], source: "IMPORT", import_id: null, actor_user_id: null, payment_status: "PAID", fulfillment_status: "UNFULFILLED", occurred_at: "2026-10-28T09:47:00Z" },
    ],
    exceptions: [linkedExceptionFixture()],
    ...overrides,
  };
}
