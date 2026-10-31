import type { Dashboard, Trends } from "@/lib/api/store-api";

const window = (days: number) => ({
  start: "2026-10-02T04:00:00Z",
  end: "2026-10-31T18:00:00Z",
  days,
  timezone: "America/New_York",
});

/** A dashboard shaped like the API's (`DashboardOut`), with values chosen for the tests. */
export function dashboardFixture(overrides: Partial<Dashboard> = {}): Dashboard {
  return {
    as_of: "2026-10-31T18:00:00Z",
    timezone: "America/New_York",
    currency: "USD",
    active_exceptions: {
      total: 18,
      by_severity: { CRITICAL: 4, HIGH: 7, MEDIUM: 6, LOW: 1 },
      by_band: { P1: 2, P2: 6, P3: 6, P4: 4 },
      by_category: { INVENTORY: 7, FULFILLMENT: 6, PAYMENT: 2, DATA_QUALITY: 3 },
      exposure_by_category: { INVENTORY: "345.70", FULFILLMENT: "336.24", PAYMENT: "86.16", DATA_QUALITY: "0.00" },
      unassigned: 18,
      past_due: 1,
      reopened: 0,
    },
    attention: [
      {
        id: "e1",
        reference: "EXC-1010",
        title: "Order KHK-12023 is past its ship-by deadline",
        exception_type: "ORDER_FULFILLMENT_OVERDUE",
        category: "FULFILLMENT",
        severity: "CRITICAL",
        status: "OPEN",
        priority_band: "P1",
        priority_score: 72,
        due_at: "2099-01-01T00:00:00Z",
        is_past_due: false,
        assignee_id: null,
        assignee_name: null,
      },
      {
        id: "e2",
        reference: "EXC-1002",
        title: "Oversold: KHK-KT-012 short by 3 units",
        exception_type: "INVENTORY_OVERSOLD",
        category: "INVENTORY",
        severity: "HIGH",
        status: "IN_PROGRESS",
        priority_band: "P2",
        priority_score: 63,
        due_at: "2020-01-01T00:00:00Z",
        is_past_due: true,
        assignee_id: "u2",
        assignee_name: "Marcus Lee",
      },
    ],
    orders: { overdue_count: 3, overdue_value: "176.22", awaiting_shipment: 28 },
    inventory: {
      active_products: 107,
      oversold: 3,
      out_of_stock: 1,
      below_reorder_point: 4,
      approaching_reorder_point: 0,
      healthy: 99,
    },
    sales_today: { window: window(1), orders_placed: 15, paid_orders: 12, gmv: "1188.03" },
    sales_last_7_days: { window: window(7), orders_placed: 120, paid_orders: 100, gmv: "9000.00" },
    on_time_shipment_30_days: {
      window: window(30),
      shipped_with_deadline: 438,
      on_time: 412,
      late: 26,
      shipped_without_deadline: 0,
      on_time_rate_pct: "94.1",
    },
    data_freshness: {
      imports: [
        { import_type: "products", import_id: null, status: null, applied_at: null },
        { import_type: "orders", import_id: null, status: null, applied_at: null },
        { import_type: "order_items", import_id: null, status: null, applied_at: null },
        { import_type: "inventory_adjustments", import_id: null, status: null, applied_at: null },
      ],
      last_evaluation_run: {
        id: "run-1",
        trigger: "SCHEDULED",
        status: "SUCCEEDED",
        as_of: "2026-10-31T17:47:00Z",
        started_at: "2026-10-31T17:47:00Z",
        finished_at: "2026-10-31T17:47:01Z",
      },
    },
    ...overrides,
  };
}

export function trendsFixture(days: Array<{ date: string; on: number; late: number }>): Trends {
  const zero = { orders_placed: 0, units: 0, gmv: "0.00", exceptions_detected: 0, exceptions_resolved: 0 };
  return {
    as_of: "2026-10-31T18:15:00Z",
    window: window(days.length),
    currency: "USD",
    partial_last_day: true,
    days: days.map((day) => ({ ...zero, date: day.date, shipped_on_time: day.on, shipped_late: day.late })),
    totals: { ...zero, shipped_on_time: 0, shipped_late: 0 },
  };
}
