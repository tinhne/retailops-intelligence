# Exception Catalog

> **Status:** Canonical (v1). Each entry maps one-to-one to a rule class in
> `apps/api/app/domains/exceptions/rules/`. A rule is a pure function
> `(snapshot, settings, as_of) → list[Finding]` with no I/O, so it can be tested on its own.

## Finding structure

Every rule emits structured findings, never just log lines:

| Field | Description |
|---|---|
| `rule_id` | Stable rule identifier with version, e.g. `INV-OVERSOLD@1` |
| `exception_type` | One of the types below |
| `category` | `INVENTORY`, `FULFILLMENT`, `PAYMENT`, `DATA_QUALITY` |
| `dedup_key` | `{exception_type}:{entity_type}:{entity_id}` |
| `primary_entity` | `{type: product\|order, id, label}` |
| `related_entities` | additional products / orders referenced by the evidence |
| `severity` | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| `title` | short human-readable title, built deterministically |
| `evidence` | typed facts (each with a value and the source record it came from) |
| `calculation` | the formula inputs and outputs that produced the finding |
| `affected_order_ids` | orders affected, if any |
| `exposure_amount` | gross order-line value at risk (BR-404), may be 0 |
| `deadline_at` | the business deadline relevant to the finding, if any |
| `recommended_action` | a deterministic, rule-authored next step (not AI-generated) |
| `detected_at` | the evaluation's `as_of` |

## Precedence

`DATA_NEGATIVE_ON_HAND` comes first. A product with `on_hand < 0` gets only that exception, and
its inventory rules are suppressed (BR-402a). Inventory rules are mutually exclusive per product (BR-401). The evaluator computes the inventory
conditions in this order and emits only the first that matches:
`INVENTORY_OVERSOLD` → `INVENTORY_OVERSELL_RISK` → `INVENTORY_OUT_OF_STOCK` → `INVENTORY_BELOW_REORDER_POINT`.

Order rules: `ORDER_FULFILLMENT_OVERDUE` supersedes `ORDER_STALLED_AFTER_PAYMENT` for the same order.

---

## INVENTORY_OVERSOLD (`INV-OVERSOLD@1`)

- **Category:** INVENTORY · **Entity:** product · **Key:** `INVENTORY_OVERSOLD:product:{id}`
- **Condition:** active product with `on_hand ≥ 0` and `available < 0`, so `reserved > on_hand` (committed demand exceeds on-hand stock).
- **Severity:** `CRITICAL`.
- **Affected orders:** allocate `on_hand` to committed order lines in FIFO order of `paid_at`
  (ties broken by `order_number`). Lines not fully covered are affected (BR-402).
- **Exposure:** Σ (uncovered quantity × unit price) across affected lines.
- **Deadline:** earliest `ship_by` among affected orders.
- **Evidence:** on_hand, reserved, available, shortage (= −available), incoming and ETA, last cycle
  count time, affected orders with their uncovered quantity.
- **Recommended action:** "Confirm physical stock with a cycle count. Then expedite incoming
  stock or contact the affected customers about a delay, starting with the most recent orders."
- **Auto-resolves when:** `available ≥ 0`.

## INVENTORY_OVERSELL_RISK (`INV-OVERSELL-RISK@1`)

- **Category:** INVENTORY · **Entity:** product · **Key:** `INVENTORY_OVERSELL_RISK:product:{id}`
- **Condition:** active product, `available ≥ 0`, and `pending_demand > available` (BR-403).
- **Severity:** `HIGH`.
- **Affected orders:** pending orders (`CREATED`, `PAYMENT_PENDING`) containing the SKU, oldest first.
- **Exposure:** potential shortage × the product's current unit price.
- **Evidence:** available, pending demand, potential shortage, pending orders, incoming.
- **Recommended action:** "Pending orders would exceed available stock if they are paid. Consider
  pausing the listing or confirming incoming stock."
- **Auto-resolves when:** `pending_demand ≤ available`, or a more severe condition supersedes it.

## INVENTORY_OUT_OF_STOCK (`INV-OUT-OF-STOCK@1`)

- **Category:** INVENTORY · **Entity:** product · **Key:** `INVENTORY_OUT_OF_STOCK:product:{id}`
- **Condition:** active product with `available = 0`.
- **Severity:** `HIGH` if `avg_daily_units > 0` (the product is selling); otherwise `MEDIUM`.
- **Exposure:** 0, because no order is blocked yet. Lost sales are not estimated.
- **Evidence:** on_hand, reserved, incoming and ETA, avg daily units (estimate), supplier, lead time.
- **Recommended action:** "Reorder from {supplier} (lead time {n} days) or hide the listing until stock arrives." Without a supplier: "Reorder from your supplier …"
- **Auto-resolves when:** `available > 0`.

## INVENTORY_BELOW_REORDER_POINT (`INV-BELOW-ROP@1`)

- **Category:** INVENTORY · **Entity:** product · **Key:** `INVENTORY_BELOW_REORDER_POINT:product:{id}`
- **Condition:** active product, `reorder_point > 0`, `0 < available ≤ reorder_point`.
- **Severity:** `HIGH` if a sales velocity and a supplier lead time both exist and
  `days_of_cover < lead_time_days` (it will likely run out before a new order arrives); otherwise `MEDIUM`.
- **Exposure:** 0.
- **Evidence:** available, reorder point, incoming and ETA, avg daily units, days of cover (estimate), lead time.
- **Recommended action:** "Place a replenishment order for at least {reorder_quantity or reorder_point × 2 − available − incoming} units."
- **Auto-resolves when:** `available > reorder_point`.

## ORDER_FULFILLMENT_OVERDUE (`ORD-OVERDUE@1`)

- **Category:** FULFILLMENT · **Entity:** order · **Key:** `ORDER_FULFILLMENT_OVERDUE:order:{id}`
- **Condition:** status in `{PAID, PROCESSING, READY_TO_SHIP}` and `as_of > ship_by` (BR-202).
- **Severity:** overdue by ≤ 24 h → `MEDIUM`; > 24 h and ≤ 72 h → `HIGH`; > 72 h → `CRITICAL`.
- **Exposure:** order total.
- **Deadline:** `ship_by` (already passed).
- **Evidence:** status, paid_at, ship_by, hours overdue, SLA source (`IMPORTED` or `STORE_SLA`),
  lines, and any inventory exception currently open on those lines' products.
- **Recommended action:** depends on the status:
  `PAID` → "Start picking: the order has not entered processing."
  `PROCESSING` → "Check the picking/packing queue for blockers."
  `READY_TO_SHIP` → "Hand over to the carrier and record tracking."
  If a line's product is oversold: "Stock shortage blocks this order. See the linked inventory exception."
- **Auto-resolves when:** the order leaves those statuses (shipped, cancelled, etc.).

## ORDER_STALLED_AFTER_PAYMENT (`ORD-STALLED@1`)

- **Category:** FULFILLMENT · **Entity:** order · **Key:** `ORDER_STALLED_AFTER_PAYMENT:order:{id}`
- **Condition:** `status = PAID`, `as_of − paid_at > stall_threshold_hours`, and not overdue (BR-203).
- **Severity:** `HIGH` if `ship_by − as_of ≤ 12 h`; otherwise `MEDIUM`.
- **Exposure:** order total. **Deadline:** `ship_by`.
- **Recommended action:** "Move the order into processing before {ship_by}."
- **Auto-resolves when:** status ≠ `PAID`. If the order becomes overdue instead, this exception
  is resolved as `SUPERSEDED` by `ORDER_FULFILLMENT_OVERDUE`.

## ORDER_REFUND_PENDING (`PAY-REFUND-PENDING@1`)

- **Category:** PAYMENT · **Entity:** order · **Key:** `ORDER_REFUND_PENDING:order:{id}`
- **Condition:** `status = CANCELLED`, `payment_status = PAID`, and `as_of − cancelled_at > refund_overdue_hours` (BR-206).
- **Severity:** `HIGH`; `CRITICAL` when `as_of − cancelled_at > 3 × refund_overdue_hours` (both clocks start at `cancelled_at`).
- **Exposure:** order total (customer money held).
- **Deadline:** `cancelled_at + refund_overdue_hours`.
- **Recommended action:** "Issue the refund in the payment system, then re-import the order or record it."
- **Auto-resolves when:** `payment_status = REFUNDED`.

## DATA_ORDER_TOTAL_MISMATCH (`DQ-ORDER-TOTAL@1`)

- **Category:** DATA_QUALITY · **Entity:** order · **Key:** `DATA_ORDER_TOTAL_MISMATCH:order:{id}`
- **Condition:** BR-205 mismatch on an order with at least one line.
- **Severity:** `MEDIUM`; `LOW` if `|difference| < 1.00`.
- **Exposure:** 0. Data quality findings do not claim financial exposure.
- **Evidence:** recorded total, expected total, difference, line count, plus whether any import
  rows for this order were rejected (missing lines are a common cause).
- **Recommended action:** "Compare the order in the source system. A rejected or missing order line is the most common cause."
- **Auto-resolves when:** totals reconcile.

## DATA_NEGATIVE_ON_HAND (`DQ-NEGATIVE-ON-HAND@1`)

- **Category:** DATA_QUALITY · **Entity:** product · **Key:** `DATA_NEGATIVE_ON_HAND:product:{id}`
- **Condition:** `on_hand < 0` (any product status). Physical stock cannot be negative, so the
  ledger is missing a receipt or count.
- **Severity:** `HIGH`.
- **Evidence:** on_hand, the last 10 movements, the last cycle count.
- **Recommended action:** "Perform a cycle count and import it as a CYCLE_COUNT adjustment."
- **Auto-resolves when:** `on_hand ≥ 0`.

---

## Explicitly not exceptions (by design)

| Condition | Where it is reported instead | Reason |
|---|---|---|
| Invalid CSV rows (bad price, unknown SKU, invalid status combination, duplicate key) | Import errors / Data quality page | The row was never persisted, so there is no live condition to track |
| `APPROACHING_REORDER_POINT` | Inventory health badge | Raising an exception for it would create noise without a clear action |
| Inactive products that are out of stock | not reported | Not sellable |

## Roadmap rules (not in v1)

`ORDER_DELIVERY_DELAYED` (needs carrier tracking events) · `PRODUCT_PRICE_ANOMALY` (needs price
history) · `SUPPLIER_LATE_RECEIPT` (needs purchase orders) · `RETURN_RATE_SPIKE` (needs return reasons).
