# AI Tool Catalog

> **Status:** Design (v1), task T-070. Implemented in `apps/api/app/domains/ai/tools/` (T-071).
> Every tool here is read-only. The list is a closed allowlist: a tool name not in this document
> does not exist for the copilot. Related: [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md), ADR-0010.
>
> All examples use the fictional demo store "Kestrel Home & Kitchen". The ids, SKUs, and numbers
> are illustrative values made up for this document, not output from the system.

## 1. Rules that apply to every tool

| Guardrail | Rule |
|---|---|
| Allowlist | Exactly the 11 tools below. An unknown tool name is rejected (`UNKNOWN_TOOL`) and recorded |
| Argument validation | A Pydantic v2 model per tool, `extra="forbid"` (`additionalProperties: false`). Invalid arguments return `INVALID_ARGUMENTS` with the field errors. The tool does not run |
| Server-injected scope | `store_id`, `as_of`, and the acting user are **never** tool arguments. The registry injects them from the authenticated request and the turn. The model cannot widen the scope by choosing ids |
| Permission | `copilot.use` admits the request. Each tool then checks its own read permission (below) with the same `require_permission` logic the REST API uses. Denials return `PERMISSION_DENIED`, are recorded, and are written to `audit_log` as `ai.tool_denied` |
| Store scoping | Every query goes through the owning module's service and repository with the `store_id` predicate (BR-003). An id that exists in another store returns `NOT_FOUND` with the same message as an id that does not exist, so existence is never revealed |
| Read-only execution | Each call runs in its own `READ ONLY` transaction with `SET LOCAL statement_timeout` = `AI_TOOL_TIMEOUT_SECONDS` (default 5 s). A bug that attempted a write would fail at the database |
| Size caps | Rows ≤ the per-tool cap (never more than 50). Serialized envelope ≤ 16 KB: long strings are truncated first, then trailing rows are dropped. `truncated` and `total_available` say so |
| Untrusted text | Free text that came from imported files or from people (product, supplier and category names, exception titles built from them, notes, file names, references, raw import values, carrier names) is listed in `untrusted_fields`, sanitised, and length-limited (`PROMPT_DESIGN.md §4`) |
| Data minimisation | Fields no supported question needs are not returned: `customer_ref`, `tracking_number`, `unit_cost`, supplier `contact_ref`, user emails, IP addresses |
| Logging | One `ai_tool_call` row per call, whatever its outcome (`AI_ARCHITECTURE.md §9`) |
| Errors | Errors carry a code and a safe message. Never a stack trace, SQL, or internal identifiers beyond the requested id |

### 1.1 Common input conventions

- Ids are UUID strings. SKUs and order numbers are strings ≤ 64 characters, trimmed, compared
  case-sensitively (BR-506).
- Datetimes are ISO-8601 **with an offset**. Lower bounds (`*_since`) must lie within
  `[as_of − 90 days, as_of]`. `due_before` may lie up to 30 days after `as_of`.
- `limit` is an integer from 1 to the tool's cap.
- Enum values are exactly the domain names (`STATE_MACHINES.md`, `EXCEPTION_CATALOG.md`).

### 1.2 Result envelope

Every tool returns the same envelope. Single-record tools return a one-element `records` list, so
the evidence ledger treats all tools alike.

```json
{
  "tool": "get_inventory_position",
  "status": "SUCCESS",
  "as_of": "2026-10-31T18:42:10Z",
  "data_window": { "from": null, "to": "2026-10-31T18:42:10Z" },
  "row_count": 1,
  "total_available": 1,
  "truncated": false,
  "untrusted_fields": ["records[].name"],
  "notes": ["available = on_hand − reserved (BR-101)."],
  "records": [{ "ref": { "type": "product", "id": "…", "label": "KHK-CI-SKL10 · Cast Iron Skillet 10 in" }, "…": "…" }]
}
```

Failure envelope:

```json
{
  "tool": "get_exception",
  "status": "NOT_FOUND",
  "error": { "code": "NOT_FOUND", "message": "No exception with this id in the current store." }
}
```

Statuses: `SUCCESS`, `INVALID_ARGUMENTS`, `PERMISSION_DENIED`, `NOT_FOUND`, `TIMEOUT`,
`REJECTED_LIMIT` (turn's tool-call cap reached), `UNKNOWN_TOOL`, `ERROR`. With the LLM provider, a
failure envelope is returned to the model as an error tool result so it can correct its arguments
or explain the gap. It is never silently dropped.

### 1.3 Summary

| # | Tool | Permission | Row cap (default) | Domain service (planned) |
|---|---|---|---|---|
| 1 | `get_dashboard_summary` | `dashboard.read` | 1 aggregate | `analytics.service.get_dashboard_summary` |
| 2 | `list_exceptions` | `exceptions.read` | 50 (20) | `exceptions.service.list_exceptions` |
| 3 | `get_exception` | `exceptions.read` | 1 | `exceptions.service.get_exception` |
| 4 | `get_exception_history` | `exceptions.read` | 50 events (30) | `exceptions.service.list_events`, `list_notes`, `list_assignments` |
| 5 | `get_related_orders` | `orders.read` (+ `exceptions.read` with `exception_id`) | 50 (20) | `orders.service.list_orders`, `exceptions.service.get_entity_links` |
| 6 | `get_product` | `catalog.read` | 1, or 10 for search | `catalog.service.get_product`, `search_products` |
| 7 | `get_inventory_position` | `inventory.read` | 1 | `inventory.service.get_position` |
| 8 | `get_inventory_movements` | `inventory.read` | 50 (20) | `inventory.service.list_movements` |
| 9 | `get_overdue_orders` | `orders.read` | 50 (20) | `orders.service.list_overdue_orders` |
| 10 | `get_import_errors` | `imports.read` | 50 issues (25), 10 imports | `imports.service.list_imports`, `list_issues` |
| 11 | `get_operational_trends` | `analytics.read` | 1 aggregate (≤ 60 days) | `analytics.service.get_trends` |

Service names are planned. The final names follow the backend implementation. The rule is fixed:
a tool calls the **same** service function as the matching REST endpoint, so the copilot and the UI
can never disagree about a number.

In v1 every role that holds `copilot.use` (all five) also holds all seven read permissions above.
The per-tool permission check is defence in depth. It is exercised in tests with test principals
that lack a permission (`TEST_STRATEGY.md §7`).

---

## 2. Tools

### 2.1 `get_dashboard_summary`

**Purpose.** One-call overview of the store's operational state: the starting point for "what needs
attention today?" and "what should the team prioritise?".

**Input.** No fields (`{}`).

**Output.** One record, `ref = aggregate:<tool_call_id>`.

| Field | Content |
|---|---|
| `active_exceptions` | `total`, `by_severity` {CRITICAL, HIGH, MEDIUM, LOW}, `by_band` {P1..P4}, `by_category` {INVENTORY, FULFILLMENT, PAYMENT, DATA_QUALITY}, `unassigned`, `past_due` (`due_at < as_of`), `reopened` |
| `exposure_by_type` | `[{exception_type, active_count, exposure_sum, currency}]`. Gross order-line value at risk (BR-404). A note states that the sums are **not additive across types**, because one order line can sit in several exceptions (for example an overdue order containing an oversold SKU) |
| `orders` | `overdue_now` (BR-202 evaluated at `as_of`), `awaiting_shipment` (PAID, PROCESSING, READY_TO_SHIP), `placed_today`, `shipped_today` (store-local day) |
| `inventory` | Counts of ACTIVE products by health at `as_of`: `oversold`, `out_of_stock`, `below_reorder_point`, `approaching_reorder_point` |
| `data_freshness` | `last_import` {`ref import:<id>`, type, applied_at}, `last_evaluation_run` {`ref evaluation_run:<id>`, trigger, as_of, status, finished_at} or `null` |

**Scoping.** Aggregates over the injected store only. **Size cap.** One record, about 2 KB.

**Example.**

```json
{ "tool": "get_dashboard_summary", "arguments": {} }
```

```json
{
  "status": "SUCCESS",
  "records": [{
    "ref": { "type": "aggregate", "id": "5a0e9c1d-2f4b-4e7a-9b1c-7d3e8f6a2b10", "label": "Dashboard summary" },
    "active_exceptions": { "total": 23, "by_severity": { "CRITICAL": 2, "HIGH": 9, "MEDIUM": 10, "LOW": 2 },
      "by_band": { "P1": 3, "P2": 7, "P3": 8, "P4": 5 }, "unassigned": 11, "past_due": 4, "reopened": 1 },
    "orders": { "overdue_now": 6, "awaiting_shipment": 41, "placed_today": 19, "shipped_today": 12 },
    "inventory": { "oversold": 2, "out_of_stock": 3, "below_reorder_point": 7, "approaching_reorder_point": 5 },
    "data_freshness": {
      "last_import": { "ref": { "type": "import", "id": "9c4d…", "label": "orders import" }, "applied_at": "2026-10-31T17:55:03Z" },
      "last_evaluation_run": { "ref": { "type": "evaluation_run", "id": "e1b2…", "label": "Evaluation run (IMPORT)" }, "as_of": "2026-10-31T17:55:09Z", "status": "SUCCEEDED" }
    }
  }]
}
```

**Failure modes.** `PERMISSION_DENIED`; `TIMEOUT`; `ERROR`. No evaluation has run yet:
`last_evaluation_run: null` and a note that exception counts may be empty for that reason.

### 2.2 `list_exceptions`

**Purpose.** Find and rank exceptions: highest priority, by type, new since a time, resolved since
a time, assigned to me, linked to a SKU or order.

**Input.**

| Field | Type | Limits / default |
|---|---|---|
| `status` | list of `OPEN`, `ACKNOWLEDGED`, `IN_PROGRESS`, `REOPENED`, `RESOLVED`, `DISMISSED` | default: the four active states |
| `severity` | list of `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` | optional |
| `category` | list of `INVENTORY`, `FULFILLMENT`, `PAYMENT`, `DATA_QUALITY` | optional |
| `exception_type` | list of the 9 types in `EXCEPTION_CATALOG.md` | optional |
| `priority_band` | list of `P1`..`P4` | optional |
| `assignee` | `ME`, `UNASSIGNED`, `ANY` | default `ANY`. There is no lookup by person name (no user directory tool) |
| `entity_sku` | string ≤ 64 | exceptions linked to the product (PRIMARY or AFFECTED) |
| `entity_order_number` | string ≤ 64 | exceptions linked to the order |
| `detected_since` | datetime | `first_detected_at ≥` value |
| `resolved_since` | datetime | `resolved_at ≥` value |
| `due_before` | datetime | `due_at <` value |
| `sort` | `-priority_score`, `due_at`, `deadline_at`, `-first_detected_at`, `-exposure_amount` | default `-priority_score` |
| `limit` | integer | 1–50, default 20 |

**Output.** Records with `ref = exception:<id>` (label = title) and: `exception_type`, `rule_id`,
`category`, `severity`, `status`, `priority_score`, `priority_band`, `title` (untrusted: contains
the product name), `primary_entity` (`ref product:<id>` or `order:<id>`), `exposure_amount`
(decimal string), `currency`, `affected_order_count`, `deadline_at`, `due_at`, `is_past_due`,
`assignee` (`{id, display_name}` or `null`), `first_detected_at`, `last_detected_at`,
`detection_count`, `reopen_count`, `resolved_at`, `resolution_code`, `recommended_action`
(rule-authored). Envelope `notes` carry the priority caveat (`PRIORITY_MODEL.md`, Limitations) and
the BR-404 exposure wording.

**Scoping.** Store predicate plus filters. A SKU or order number from another store simply matches
nothing. **Size cap.** 50 rows.

**Example.**

```json
{ "tool": "list_exceptions",
  "arguments": { "exception_type": ["INVENTORY_OVERSELL_RISK"], "sort": "-priority_score", "limit": 5 } }
```

```json
{
  "status": "SUCCESS", "row_count": 2, "total_available": 2, "truncated": false,
  "records": [{
    "ref": { "type": "exception", "id": "3f6b2d0a-8c41-4b9e-a7d2-1e5f9c0b4a77", "label": "Oversell risk: Bamboo Cutting Board L" },
    "exception_type": "INVENTORY_OVERSELL_RISK", "rule_id": "INV-OVERSELL-RISK@1", "severity": "HIGH",
    "status": "OPEN", "priority_score": 56, "priority_band": "P2",
    "primary_entity": { "ref": { "type": "product", "id": "c2a7…", "label": "KHK-BCB-L · Bamboo Cutting Board L" } },
    "exposure_amount": "149.85", "currency": "USD", "affected_order_count": 4,
    "due_at": "2026-11-01T14:10:00Z", "is_past_due": false, "assignee": null,
    "recommended_action": "Pending orders would exceed available stock if they are paid. Consider pausing the listing or confirming incoming stock."
  }]
}
```

**Failure modes.** `INVALID_ARGUMENTS` (unknown enum value, datetime without offset or out of
range, `limit` > 50); `PERMISSION_DENIED`; `TIMEOUT`. Empty result is `SUCCESS` with 0 rows.

### 2.3 `get_exception`

**Purpose.** Everything needed to explain one exception: evidence, calculation, severity criteria,
and the priority breakdown.

**Input.** `exception_id` (UUID, required).

**Output.** One record with every `list_exceptions` field, plus:

| Field | Content |
|---|---|
| `evidence` | The stored evidence snapshot: typed facts `[{key, label, value, unit, source_ref}]`. Each `source_ref` (product, order, import) enters the evidence ledger |
| `calculation` | Formula inputs and outputs that produced the finding |
| `priority_breakdown` | `{S, A, E, D, T, score, band, inputs: {severity, affected_orders, exposure, deadline_at, days_open}, weights}` per `PRIORITY_MODEL.md` |
| `rule_condition`, `severity_criteria` | Static text for `rule_id` from a code constant that mirrors `EXCEPTION_CATALOG.md` (for example "overdue ≤ 24 h → MEDIUM; > 24 h and ≤ 72 h → HIGH; > 72 h → CRITICAL") |
| `linked_entities` | `[{ref, role: PRIMARY or AFFECTED}]` |
| Lifecycle | `superseded_by_id`, `previous_occurrence_id`, `verified_at`, `dismissed_reason`, `condition_cleared_at`, `resolution_note` (untrusted, ≤ 1,000 characters) |

**Scoping.** Looked up by `(store_id, id)`. **Size cap.** One record. Evidence lists inside it are
capped at 20 entries (for example affected orders), with `truncated` set.

**Example.**

```json
{ "tool": "get_exception", "arguments": { "exception_id": "7d1c9e42-5b3a-4f08-9e6d-2a8b4c1f0e93" } }
```

```json
{
  "status": "SUCCESS",
  "records": [{
    "ref": { "type": "exception", "id": "7d1c9e42-5b3a-4f08-9e6d-2a8b4c1f0e93", "label": "Fulfillment overdue: KH-104812" },
    "exception_type": "ORDER_FULFILLMENT_OVERDUE", "rule_id": "ORD-OVERDUE@1", "severity": "CRITICAL",
    "priority_score": 79, "priority_band": "P1",
    "evidence": [
      { "key": "status", "label": "Order status", "value": "PROCESSING", "source_ref": "order:41e0…" },
      { "key": "ship_by", "label": "Ship-by", "value": "2026-10-28T13:00:00Z", "source_ref": "order:41e0…" },
      { "key": "hours_overdue", "label": "Hours overdue", "value": "77.7", "unit": "hours", "source_ref": "order:41e0…" },
      { "key": "sla_source", "label": "SLA source", "value": "STORE_SLA", "source_ref": "order:41e0…" }
    ],
    "priority_breakdown": { "S": 50, "A": 3, "E": 8, "D": 12, "T": 6, "score": 79, "band": "P1" },
    "severity_criteria": "overdue ≤ 24 h → MEDIUM; > 24 h and ≤ 72 h → HIGH; > 72 h → CRITICAL",
    "recommended_action": "Check the picking/packing queue for blockers."
  }]
}
```

**Failure modes.** `INVALID_ARGUMENTS` (not a UUID); `NOT_FOUND` (missing or another store's id,
same message); `PERMISSION_DENIED`.

### 2.4 `get_exception_history`

**Purpose.** What has happened to an exception: detections, severity changes, assignments, status
changes, verification, reopen reasons, and notes.

**Input.**

| Field | Type | Limits / default |
|---|---|---|
| `exception_id` | UUID | required |
| `event_types` | list of the event types in `DOMAIN_MODEL.md` | optional |
| `include_notes` | boolean | default `true` |
| `limit` | integer | 1–50 events, default 30 (newest first) |

**Output.** One record, `ref = exception:<id>`, with `events[]` (`event_type`, `occurred_at`,
`actor` {`type` USER or SYSTEM, `display_name` or null}, `from_status`, `to_status`,
`evaluation_run_id`, `payload_summary`, for example `{"severity": {"from": "HIGH", "to": "CRITICAL"}}`
or `{"reason": "VERIFICATION_FAILED"}`), `notes[]` (≤ 20: `author_display_name`, `source` USER or
AI_DRAFT_ACCEPTED, `created_at`, `body` untrusted and truncated to 1,000 characters), and
`assignments[]` (≤ 20).

**Scoping.** The exception is resolved by `(store_id, id)` first. Events, notes, and assignments are
read through it. **Size cap.** 50 events, 20 notes, 20 assignments, 16 KB.

**Example.**

```json
{ "tool": "get_exception_history", "arguments": { "exception_id": "7d1c9e42-5b3a-4f08-9e6d-2a8b4c1f0e93", "limit": 5 } }
```

```json
{
  "status": "SUCCESS",
  "untrusted_fields": ["records[].notes[].body"],
  "records": [{
    "ref": { "type": "exception", "id": "7d1c9e42-5b3a-4f08-9e6d-2a8b4c1f0e93", "label": "Fulfillment overdue: KH-104812" },
    "events": [
      { "event_type": "SEVERITY_CHANGED", "occurred_at": "2026-10-31T13:00:04Z", "actor": { "type": "SYSTEM" }, "payload_summary": { "severity": { "from": "HIGH", "to": "CRITICAL" } } },
      { "event_type": "ASSIGNED", "occurred_at": "2026-10-30T15:12:40Z", "actor": { "type": "USER", "display_name": "Morgan P." } }
    ],
    "notes": [{ "author_display_name": "Sam R.", "source": "USER", "created_at": "2026-10-30T16:02:11Z", "body": "Packing station 2 is waiting on boxes." }]
  }]
}
```

**Failure modes.** As `get_exception`.

### 2.5 `get_related_orders`

**Purpose.** Orders behind an exception, orders containing a product, or orders looked up by
number.

**Input.** Exactly one selector, plus optional filters.

| Field | Type | Limits / default |
|---|---|---|
| `exception_id` | UUID | selector. Orders linked via `exception_entity_link`. Also requires `exceptions.read` |
| `product_id` | UUID | selector. Orders with a line for the product |
| `sku` | string ≤ 64 | selector. As `product_id` |
| `order_numbers` | list of strings ≤ 64 | selector. 1–20 entries |
| `status` | list of order statuses (`STATE_MACHINES.md §1.1`) | optional |
| `placed_since` | datetime | optional |
| `include_lines` | boolean | default `true`. At most 20 lines per order |
| `sort` | `-placed_at`, `paid_at` (FIFO), `ship_by` | default `-placed_at`. With `exception_id` the default is the allocation order used by the rule |
| `limit` | integer | 1–50, default 20 |

**Output.** Records with `ref = order:<id>` (label = order number): `order_number`, `channel`,
`status`, `payment_status`, `fulfillment_status`, `placed_at`, `paid_at`, `ship_by`,
`ship_by_source`, `shipped_at`, `delivered_at`, `cancelled_at`, `currency`, `subtotal`,
`discount_total`, `shipping_total`, `tax_total`, `total`, `is_overdue` and `hours_overdue`
(BR-202 at `as_of`), `has_tracking` (boolean, the number itself is not returned), `carrier`
(untrusted), `lines[]` (`line_number`, `sku`, product ref, `quantity`, `unit_price`,
`line_discount`). With `exception_id`: `link_role` (PRIMARY or AFFECTED) and, for
`INVENTORY_OVERSOLD`, `uncovered_quantity` from the evidence. With `order_numbers`: a `not_found`
list of numbers with no match in this store. `active_exception_refs` lists active exceptions linked
to each order. `customer_ref` is never returned.

**Scoping.** Store predicate on orders, and on the exception or product used as the selector.
**Size cap.** 50 orders × 20 lines, 16 KB.

**Example.**

```json
{ "tool": "get_related_orders", "arguments": { "order_numbers": ["KH-104812"] } }
```

```json
{
  "status": "SUCCESS", "row_count": 1, "not_found": [],
  "records": [{
    "ref": { "type": "order", "id": "41e0b7c3-9a2d-4c6f-8e15-0d7a3b9f2c64", "label": "KH-104812" },
    "status": "PROCESSING", "payment_status": "PAID", "fulfillment_status": "IN_PROGRESS",
    "placed_at": "2026-10-26T12:41:00Z", "paid_at": "2026-10-26T13:00:00Z",
    "ship_by": "2026-10-28T13:00:00Z", "ship_by_source": "STORE_SLA",
    "shipping_total": "7.95", "tax_total": "4.20", "total": "71.15", "currency": "USD", "is_overdue": true, "hours_overdue": "77.7", "has_tracking": false,
    "lines": [{ "line_number": 1, "sku": "KHK-CI-SKL10", "quantity": 1, "unit_price": "59.00", "line_discount": "0.00" }],
    "active_exception_refs": ["exception:7d1c9e42-5b3a-4f08-9e6d-2a8b4c1f0e93"]
  }]
}
```

**Failure modes.** `INVALID_ARGUMENTS` (no selector or more than one, more than 20 numbers);
`NOT_FOUND` (exception or product selector not in the store); `PERMISSION_DENIED` (missing
`orders.read`, or `exceptions.read` when `exception_id` is used).

### 2.6 `get_product`

**Purpose.** Product master data and the exceptions currently open on it. Also resolves a product
mentioned by name.

**Input.** Exactly one of:

| Field | Type | Limits |
|---|---|---|
| `product_id` | UUID | |
| `sku` | string ≤ 64 | exact, case-sensitive after trimming (BR-506) |
| `search` | string 2–100 | case-insensitive substring match on SKU or name. Returns at most 10 matches |

**Output.** Records with `ref = product:<id>` (label `SKU · name`): `sku`, `name` (untrusted),
`category` (untrusted), `status` (ACTIVE, DRAFT, ARCHIVED), `unit_price`, `reorder_point`,
`reorder_quantity`, `supplier` (`{name (untrusted), lead_time_days}` or null), `updated_at`,
`active_exception_refs[]` (`{ref, exception_type, severity, priority_band}`). `unit_cost` and the
supplier `contact_ref` are not returned.

**Scoping.** Store predicate. **Size cap.** 1 record, or 10 for `search`.

**Example.**

```json
{ "tool": "get_product", "arguments": { "search": "skillet" } }
```

```json
{
  "status": "SUCCESS", "row_count": 2, "untrusted_fields": ["records[].name", "records[].category", "records[].supplier.name"],
  "records": [
    { "ref": { "type": "product", "id": "a91f…", "label": "KHK-CI-SKL10 · Cast Iron Skillet 10 in" }, "status": "ACTIVE", "unit_price": "59.00", "reorder_point": 12, "supplier": { "name": "Northfield Cookware", "lead_time_days": 14 } },
    { "ref": { "type": "product", "id": "b07c…", "label": "KHK-CI-SKL12 · Cast Iron Skillet 12 in" }, "status": "ACTIVE", "unit_price": "74.00", "reorder_point": 8, "supplier": { "name": "Northfield Cookware", "lead_time_days": 14 } }
  ]
}
```

**Failure modes.** `INVALID_ARGUMENTS` (zero or several selectors, `search` too short);
`NOT_FOUND` (id or SKU); search with no match is `SUCCESS` with 0 rows.

### 2.7 `get_inventory_position`

**Purpose.** The current stock position of one product with the formulas and estimates behind it.

**Input.** Exactly one of `product_id` (UUID) or `sku` (string ≤ 64).

**Output.** One record, `ref = product:<id>`:

| Field | Content |
|---|---|
| `on_hand`, `reserved`, `incoming`, `incoming_eta` | From `inventory_balance` |
| `available` | `on_hand − reserved` (BR-101). May be negative (BR-102). `incoming` is not included (BR-103) |
| `pending_demand` | Units on `CREATED` / `PAYMENT_PENDING` orders |
| `potential_shortage` | `pending_demand − available` when `available ≥ 0` and positive, else 0 (BR-403) |
| `health` | `OVERSOLD`, `OUT_OF_STOCK`, `BELOW_REORDER_POINT`, `APPROACHING_REORDER_POINT`, `HEALTHY`, or `NOT_CLASSIFIED` for non-ACTIVE products (§2.5 of `BUSINESS_RULES.md`), with `reorder_point` and `approaching_threshold` |
| `last_cycle_count_at` | |
| `avg_daily_units` | `{value, is_estimate: true, window_days, basis: "BR-150"}` |
| `days_of_cover` | `{value or null, is_estimate: true, reason}`. `null` with "not enough sales history" when velocity is 0 (BR-151) |
| `supplier_lead_time_days` | When a supplier is set |
| `formulas` | Text of each formula above with its rule ID |

**Scoping.** Store predicate. **Size cap.** One record.

**Example.**

```json
{ "tool": "get_inventory_position", "arguments": { "sku": "KHK-BCB-L" } }
```

```json
{
  "status": "SUCCESS",
  "records": [{
    "ref": { "type": "product", "id": "c2a7…", "label": "KHK-BCB-L · Bamboo Cutting Board L" },
    "on_hand": 9, "reserved": 6, "available": 3, "incoming": 24, "incoming_eta": "2026-11-05T15:00:00Z",
    "pending_demand": 8, "potential_shortage": 5, "health": "BELOW_REORDER_POINT", "reorder_point": 10,
    "avg_daily_units": { "value": "2.43", "is_estimate": true, "window_days": 28, "basis": "BR-150" },
    "days_of_cover": { "value": "1.2", "is_estimate": true },
    "supplier_lead_time_days": 10
  }]
}
```

**Failure modes.** `INVALID_ARGUMENTS`; `NOT_FOUND`; `PERMISSION_DENIED`; `TIMEOUT`.

### 2.8 `get_inventory_movements`

**Purpose.** Recent ledger rows for one product: why stock changed, the last cycle count, missing
receipts.

**Input.**

| Field | Type | Limits / default |
|---|---|---|
| `product_id` / `sku` | UUID / string ≤ 64 | exactly one |
| `since` | datetime | default `as_of − 30 days`, earliest `as_of − 90 days` |
| `movement_types` | list of the 9 types in BR-111 | optional |
| `limit` | integer | 1–50, default 20 (newest first) |

**Output.** One record, `ref = product:<id>`, with `movements[]`: `movement_type`, `on_hand_delta`,
`incoming_delta`, `occurred_at`, `source` (IMPORT, ORDER, SYSTEM), `reference` (untrusted, ≤ 100
characters), import ref (`import:<id>`, enters the ledger) when the movement came from an import,
`note` (untrusted, ≤ 200 characters). `data_window.from = since`.

**Scoping.** Store predicate on product and movements. **Size cap.** 50 movements.

**Example.**

```json
{ "tool": "get_inventory_movements", "arguments": { "sku": "KHK-GLS-TUMB6", "limit": 3 } }
```

```json
{
  "status": "SUCCESS", "untrusted_fields": ["records[].movements[].reference", "records[].movements[].note"],
  "records": [{
    "ref": { "type": "product", "id": "d5e3…", "label": "KHK-GLS-TUMB6 · Glass Tumbler Set of 6" },
    "movements": [
      { "movement_type": "SHIPMENT", "on_hand_delta": -2, "incoming_delta": 0, "occurred_at": "2026-10-30T19:20:00Z", "source": "ORDER", "reference": "order_item:6b1e…" },
      { "movement_type": "DAMAGE", "on_hand_delta": -3, "incoming_delta": 0, "occurred_at": "2026-10-29T14:00:00Z", "source": "IMPORT", "reference": "ADJ-2026-1029-07", "note": "Broken in transit" },
      { "movement_type": "CYCLE_COUNT", "on_hand_delta": -1, "incoming_delta": 0, "occurred_at": "2026-10-27T12:00:00Z", "source": "IMPORT", "reference": "CC-2026-10-27-TUMB6" }
    ]
  }]
}
```

**Failure modes.** `INVALID_ARGUMENTS` (`since` out of range); `NOT_FOUND`; `PERMISSION_DENIED`.

### 2.9 `get_overdue_orders`

**Purpose.** Orders past their ship-by deadline **right now** (BR-202 evaluated at the turn's
`as_of`), including those that became overdue after the last evaluation run.

**Input.**

| Field | Type | Limits / default |
|---|---|---|
| `status` | subset of `PAID`, `PROCESSING`, `READY_TO_SHIP` | default all three |
| `min_hours_overdue` | number | 0–2,160, default 0 |
| `sort` | `-hours_overdue`, `ship_by`, `-total` | default `-hours_overdue` |
| `limit` | integer | 1–50, default 20 |

**Output.** `total_overdue` (count of all matching orders, not only those returned) and records with
`ref = order:<id>`: `order_number`, `status`, `paid_at`, `ship_by`, `ship_by_source`,
`hours_overdue`, `total`, `currency`, `line_count`, `severity_if_detected` (MEDIUM, HIGH or
CRITICAL from the ORD-OVERDUE thresholds, computed by the same function as the rule),
`exception_ref` (the active `ORDER_FULFILLMENT_OVERDUE` exception, or `null` with a note that the
next evaluation will create it).

**Scoping.** Store predicate. The overdue predicate is the shared BR-202 function, not a copy.
**Size cap.** 50 rows.

**Example.**

```json
{ "tool": "get_overdue_orders", "arguments": { "limit": 2 } }
```

```json
{
  "status": "SUCCESS", "total_overdue": 6, "row_count": 2, "truncated": true,
  "records": [
    { "ref": { "type": "order", "id": "41e0…", "label": "KH-104812" }, "status": "PROCESSING", "ship_by": "2026-10-28T13:00:00Z", "hours_overdue": "77.7", "total": "71.15", "severity_if_detected": "CRITICAL", "exception_ref": "exception:7d1c…" },
    { "ref": { "type": "order", "id": "52f1…", "label": "KH-104977" }, "status": "PAID", "ship_by": "2026-10-30T09:30:00Z", "hours_overdue": "33.2", "total": "142.15", "severity_if_detected": "HIGH", "exception_ref": null }
  ]
}
```

**Failure modes.** `INVALID_ARGUMENTS` (status outside the three committed states);
`PERMISSION_DENIED`; `TIMEOUT`.

### 2.10 `get_import_errors`

**Purpose.** Recent imports and their row issues: why an import was rejected or what was skipped.

**Input.**

| Field | Type | Limits / default |
|---|---|---|
| `import_id` | UUID | optional. When given, returns that import's issues |
| `import_type` | `products`, `orders`, `order_items`, `inventory_adjustments` | optional |
| `since` | datetime | optional, within 90 days |
| `severity` | `ERROR`, `WARNING` | optional |
| `codes` | list of issue codes (file-level, row ERROR, WARNING codes of the import contract) | optional |
| `limit` | integer | 1–50 issues, default 25 |

**Output.** `imports[]` (at most 10, newest first; or the one requested): `ref = import:<id>`,
`import_type`, `status` (`STATE_MACHINES.md §4`), `mode`, `original_filename` (untrusted),
`row_count`, `summary` {new, updated, unchanged, error, warning}, `validated_at`, `applied_at`,
`evaluation_run_id`. `code_counts[]` (`{code, severity, count}`). With `import_id`: `issues[]`
(`row_number`, `column`, `code`, `severity`, `message`, `raw_value` untrusted and truncated to 100
characters), ordered by row number.

**Scoping.** Store predicate on imports. **Size cap.** 10 imports, 50 issues, 16 KB.

**Example.**

```json
{ "tool": "get_import_errors", "arguments": { "import_id": "9c4d2e7a-1b3f-4a6c-8d9e-0f1a2b3c4d5e", "severity": "ERROR", "limit": 2 } }
```

```json
{
  "status": "SUCCESS", "untrusted_fields": ["imports[].original_filename", "issues[].raw_value"],
  "imports": [{ "ref": { "type": "import", "id": "9c4d2e7a-1b3f-4a6c-8d9e-0f1a2b3c4d5e", "label": "orders import, 2026-10-31" },
    "import_type": "orders", "status": "COMPLETED_WITH_ERRORS", "mode": "VALID_ROWS_ONLY", "row_count": 212,
    "summary": { "new": 31, "updated": 177, "unchanged": 0, "error": 4, "warning": 2 } }],
  "code_counts": [{ "code": "ORDER_INVALID_STATUS_COMBINATION", "severity": "ERROR", "count": 3 }, { "code": "INVALID_DATETIME", "severity": "ERROR", "count": 1 }],
  "issues": [
    { "row_number": 18, "column": "payment_status", "code": "ORDER_INVALID_STATUS_COMBINATION", "severity": "ERROR", "message": "status SHIPPED requires payment_status PAID", "raw_value": "PENDING" },
    { "row_number": 77, "column": "placed_at", "code": "INVALID_DATETIME", "severity": "ERROR", "message": "Not an ISO-8601 timestamp", "raw_value": "31/10/2026 9am" }
  ]
}
```

**Failure modes.** `INVALID_ARGUMENTS` (unknown code or type); `NOT_FOUND` (`import_id`);
`PERMISSION_DENIED`.

### 2.11 `get_operational_trends`

**Purpose.** Daily counts over a window: "what changed since yesterday?", "how did this week go?".
Counts only. No projections.

**Input.**

| Field | Type | Limits / default |
|---|---|---|
| `window_days` | integer | 1–60, default 14. Days are store-local (America/New_York for the demo store). The last day is partial (today so far) |
| `metrics` | list of the metric names below | default all |

| Metric | Definition (per store-local day) |
|---|---|
| `orders_placed` | Orders with `placed_at` in the day, any status |
| `orders_cancelled` | Orders with `cancelled_at` in the day |
| `orders_shipped` | Orders with `shipped_at` in the day |
| `on_time_shipments` / `late_shipments` | Shipped in the day with `shipped_at ≤ ship_by` / `> ship_by` |
| `units_sold` | Units on lines of orders placed in the day, using the BR-150 status filter |
| `exceptions_detected` | `DETECTED` events |
| `exceptions_auto_resolved` | `AUTO_RESOLVED` events |
| `exceptions_resolved_manually` | Status changes to `RESOLVED` by a user |
| `exceptions_reopened` | `REOPENED` events |
| `exceptions_dismissed` | Status changes to `DISMISSED` |

**Output.** One record, `ref = aggregate:<tool_call_id>`: `timezone`, `days[]` (dates),
`series` {metric: [integers per day]}, `totals` {metric: integer}, `definitions` {metric: text},
`partial_last_day: true`. `data_window.from` = start of the first day, `to` = `as_of`.

**Scoping.** Store predicate on every aggregate. **Size cap.** 60 days × 11 metrics.

**Example.**

```json
{ "tool": "get_operational_trends", "arguments": { "window_days": 2, "metrics": ["orders_placed", "exceptions_detected", "exceptions_auto_resolved"] } }
```

```json
{
  "status": "SUCCESS",
  "data_window": { "from": "2026-10-30T04:00:00Z", "to": "2026-10-31T18:42:10Z" },
  "records": [{
    "ref": { "type": "aggregate", "id": "8b2f…", "label": "Operational trends, 2 days" },
    "timezone": "America/New_York", "days": ["2026-10-30", "2026-10-31"], "partial_last_day": true,
    "series": { "orders_placed": [27, 19], "exceptions_detected": [5, 3], "exceptions_auto_resolved": [4, 2] },
    "totals": { "orders_placed": 46, "exceptions_detected": 8, "exceptions_auto_resolved": 6 }
  }]
}
```

**Failure modes.** `INVALID_ARGUMENTS`; `PERMISSION_DENIED`; `TIMEOUT` (the aggregate queries are
the heaviest in the catalog; covered by the latency measurement in the evaluation).

---

## 3. Tools deliberately not provided

| Not provided | Examples | Why |
|---|---|---|
| Raw SQL or query building | `run_sql`, `query_database`, free-form filter expressions | Bypasses the repository's `store_id` predicate (BR-003) and the permission checks. Opens SQL injection through model output. Unbounded cost and result size. Numbers would be computed ad hoc instead of by tested domain logic (ADR-0010) |
| Any write action | `update_exception_status`, `assign_exception`, `add_note`, `resolve_exception`, `dismiss_exception`, `apply_import`, `trigger_evaluation`, `change_settings`, `adjust_inventory` | The AI never writes business data (`AGENTS.md §11`). Every mutation needs a human actor, CSRF, optimistic concurrency, and an audit entry with that person as actor. Note drafts are returned to the user and saved only through the normal notes endpoint |
| Cross-store or organization-wide queries | `list_stores`, `compare_stores`, organization summary | Tools are bound to the store in the request path. Multi-store comparison would need its own permission design (BR-002 grants per organization, but the copilot works per store) |
| User and personal-data lookup | `get_user`, `list_users`, `find_customer`, `get_customer` | No customer personal data exists (BR-505). The user directory is governed by `users.read` and is not needed to answer operational questions. Excluding it prevents enumeration of staff accounts. Assignee display names appear only inside exception results |
| Audit log | `get_audit_log` | Holds IP addresses and security events. No supported question needs it |
| Settings | `get_settings`, `update_settings` | The thresholds that matter are already in each exception's `calculation`. Updating is a write |
| External access | `web_fetch`, `send_email`, `read_file`, webhooks | No external data sources in scope. Removing every outbound channel removes the main exfiltration path for prompt injection |
| Calculator or code execution | `calculate`, `python` | Business arithmetic belongs to deterministic, tested tools. The validator rejects metrics that no tool returned (`AI_ARCHITECTURE.md §6`) |
| Forecasting | `forecast_sales`, `predict_stockout_date` | No forecasting model in v1. The only forward-looking values are the labelled estimates in `get_inventory_position` (BR-150..152) |

Adding a tool requires: a catalog entry here, a Pydantic schema, a permission test, a cross-store
scope test, a size-cap test (T-071 acceptance), evaluation cases, and a bump of the tools version
in `prompt_version` (`PROMPT_DESIGN.md §8`).
