import type { ExceptionDetail, ExceptionEvent, ExceptionListItem } from "@/lib/api/exceptions-api";

/** A list row shaped like the API's `ExceptionListItem`. */
export function listItemFixture(overrides: Partial<ExceptionListItem> = {}): ExceptionListItem {
  return {
    id: "exc-1",
    reference: "EXC-1002",
    exception_type: "INVENTORY_OVERSOLD",
    category: "INVENTORY",
    status: "OPEN",
    severity: "CRITICAL",
    priority_score: 67,
    priority_band: "P2",
    title: "Oversold: KHK-KT-012 short by 3 units across 2 orders",
    primary_entity: { type: "product", id: "p1", label: "KHK-KT-012", name: "Olive Wood Bench Scraper" },
    assignee: null,
    exposure_amount: "56.85",
    affected_order_count: 2,
    deadline_at: null,
    due_at: "2099-01-01T00:00:00Z",
    due_at_overridden: false,
    is_past_due: false,
    first_detected_at: "2026-10-31T17:47:00Z",
    last_detected_at: "2026-10-31T18:16:00Z",
    detection_count: 2,
    age_hours: 0,
    reopen_count: 0,
    version: 3,
    resolution_code: null,
    verified_at: null,
    dismissed_reason: null,
    closed_at: null,
    ...overrides,
  };
}

/** A detail response with evidence, calculation and the actions the API allows. */
export function detailFixture(overrides: Partial<ExceptionDetail> = {}): ExceptionDetail {
  return {
    ...listItemFixture(),
    rule_id: "INV-OVERSOLD@1",
    dedup_key: "INVENTORY_OVERSOLD:product:p1",
    priority_breakdown: {
      total: 67,
      band: "P2",
      as_of: "2026-10-31T18:16:00Z",
      components: [
        { key: "severity", label: "Severity", points: 50, max_points: 50, explanation: "CRITICAL severity scores 50 points." },
        { key: "exposure", label: "Value at risk", points: 7, max_points: 15, explanation: "Gross order-line value at risk 56.85." },
      ],
      due: { basis: "SEVERITY", explanation: "4 h response target for this severity." },
    },
    evidence: {
      facts: [
        { key: "available", label: "Available (on hand − reserved)", value: -3, unit: "units", estimate: false, volatile: false, source: { type: "inventory_balance", id: "p1", label: "Inventory balance of KHK-KT-012" } },
        { key: "exposure_amount", label: "Gross order-line value at risk", value: "56.85", unit: "USD", estimate: false, volatile: false, source: null },
      ],
      records: {
        affected_orders: [
          { order_number: "KHK-12015", paid_at: "2026-10-31T08:55:00Z", ship_by: "2026-11-02T08:55:00Z", uncovered_quantity: 1, value_at_risk: "18.95", order_id: "o1" },
        ],
      },
      notes: [],
    },
    calculation: {
      formulas: ["available = on_hand − reserved (BR-101)"],
      inputs: { on_hand: 5, reserved: 8 },
      outputs: { available: -3, exposure_amount: "56.85" },
    },
    recommended_action: "Confirm physical stock with a cycle count.",
    links: [],
    resolution: null,
    dismissal: null,
    superseded_by: null,
    supersedes: [],
    previous_occurrence: null,
    available_actions: ["acknowledge", "start", "claim", "resolve", "dismiss", "assign", "add_note", "set_due_date"],
    blocked_actions: [],
    created_at: "2026-10-31T17:47:00Z",
    updated_at: "2026-10-31T18:16:00Z",
    ...overrides,
  };
}

export function eventFixture(overrides: Partial<ExceptionEvent>): ExceptionEvent {
  return {
    id: "ev-1",
    event_type: "DETECTED",
    actor_type: "SYSTEM",
    actor: null,
    evaluation_run_id: "run-1",
    from_status: null,
    to_status: "OPEN",
    payload: {},
    occurred_at: "2026-10-31T17:47:00Z",
    ...overrides,
  };
}

export const page = <T,>(items: T[]) => ({ items, page: 1, page_size: 25, total: items.length });
