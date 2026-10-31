# Business Rules

> **Status:** Canonical (v1). Every rule has an identifier (`BR-xxx`). Tests reference these IDs
> in their names or docstrings so a rule can be traced to its verification.
> Related: `STATE_MACHINES.md`, `EXCEPTION_CATALOG.md`, `PRIORITY_MODEL.md`.

Legend for the "Basis" column:
- **Industry**: an established practice in e-commerce operations.
- **MVP**: a simplifying assumption made for this version. It is documented so it can be revisited.
- **Validate**: a decision that should be checked with real operators before it is relied on.

---

## 1. Tenancy and scope

| ID | Rule | Basis |
|---|---|---|
| BR-001 | All business data belongs to exactly one **store**, and each store belongs to exactly one **organization**. | Industry |
| BR-002 | A user accesses data through an organization **membership** that carries one role. In the MVP a membership grants access to every store in that organization. | MVP |
| BR-003 | Every read and write of store-scoped data is filtered by `store_id` at the repository layer. Filtering only in the UI is never sufficient. | Industry |
| BR-004 | A store has exactly one currency and one IANA time zone. Monetary values in imports must match the store currency; rows with a different currency are rejected. | MVP |
| BR-005 | A store has a single fulfillment location in the MVP. Multi-location inventory is out of scope (ADR-0005). | MVP |

## 2. Inventory

### 2.1 Quantities

Inventory is tracked per `(store, product)` in `inventory_balance`. Each quantity is defined below.

| Quantity | Definition | Source of truth |
|---|---|---|
| `on_hand` | Physical units in the fulfillment location | Sum of `on_hand_delta` across `inventory_movement` rows (the ledger) |
| `reserved` | Units held for **committed** orders that have not shipped yet | Sum of `ACTIVE` `stock_reservation.quantity` |
| `available` | Units that can still be promised to new orders | **`available = on_hand − reserved`** |
| `incoming` | Units expected from suppliers but not yet received | Sum of `incoming_delta` across ledger rows |
| `pending_demand` | Units on orders in `CREATED` / `PAYMENT_PENDING` (not reserved) | Computed from order lines |

| ID | Rule | Basis |
|---|---|---|
| BR-101 | `available = on_hand − reserved`. Pending demand is **not** subtracted from `available`. It is compared against `available` only in the oversell-risk rule (BR-403). Committed demand is already represented by `reserved` and must never be subtracted a second time. | Industry |
| BR-102 | `available` can be negative. A negative value means committed demand exceeds physical stock (oversold). It is reported, never clamped. | Industry |
| BR-103 | `incoming` never counts toward `available`. It appears as context in evidence ("40 units expected on 2026-11-04"). | Industry |
| BR-104 | `inventory_balance` is a cached projection of the ledger and reservations. The reconciliation check (`inventory.reconcile`, exposed at `GET /inventory/reconciliation` and on the Data quality page) recomputes it and reports any drift as a defect. It never silently fixes drift. | MVP |

### 2.2 Inventory movement ledger

| ID | Rule | Basis |
|---|---|---|
| BR-110 | Every change to `on_hand` or `incoming` is an append-only `inventory_movement` row with `movement_type`, `on_hand_delta`, `incoming_delta`, `occurred_at`, `source` (`IMPORT`, `ORDER`, `SYSTEM`), `reference`, and `created_by`. Rows are never updated or deleted. Mistakes are corrected with a compensating `CORRECTION` movement. | Industry |
| BR-111 | Movement types: `CYCLE_COUNT` (absolute count; delta = counted − current on_hand), `RECEIPT` (+on_hand, −incoming down to 0), `INCOMING_EXPECTED` (+incoming), `INCOMING_CANCELLED` (−incoming), `DAMAGE` (−), `SHRINKAGE` (−), `RETURN_RESTOCK` (+), `CORRECTION` (±), `SHIPMENT` (−, system-generated from orders). | Industry |
| BR-112 | Imported adjustments carry an external `reference` that is unique per store. Re-importing a row with a reference that has already been applied is reported as `ALREADY_APPLIED` and has no effect. This makes adjustment imports idempotent. | MVP |
| BR-113 | A `CYCLE_COUNT` sets on-hand **as of its `occurred_at`**: `delta = counted − (on_hand − Σ on_hand_delta of movements with occurred_at > count time)`. A count imported late therefore does not erase receipts or shipments recorded after it was taken. A count older than the product's latest count is rejected (`STALE_CYCLE_COUNT`). | MVP |

### 2.3 Reservations

| ID | Rule | Basis |
|---|---|---|
| BR-120 | An order line is reserved when its order enters committed demand (`PAID`, `PROCESSING`, `READY_TO_SHIP`). See `STATE_MACHINES.md §1.5`. | Industry (reserve on payment) |
| BR-121 | A reservation is `RELEASED` when the order is cancelled or refunded before shipping. (Payment failure happens before reservation in the v1 graph. `RELEASED → ACTIVE` is kept for idempotent re-sync, but the v1 graph cannot reach it.) If a committed line's SKU changes, the reservation moves to the new product and both products' `reserved` are recomputed. | Industry |
| BR-122 | A reservation is `CONSUMED` when the order ships. | Industry |
| BR-123 | Reservations are synchronised by one idempotent function (`reservations.sync_for_orders`). Running it twice gives the same result. | MVP |

### 2.4 Shipments and the cycle-count cutoff

The product ingests inventory counts from a source system, and those counts already reflect any
order that shipped before the count was taken. Writing a shipment movement for those orders as
well would decrement stock twice.

| ID | Rule | Basis |
|---|---|---|
| BR-130 | When an order line becomes fulfilled (order reaches `SHIPPED` or later), the system writes one `SHIPMENT` movement (`on_hand_delta = −quantity`, `reference = order_item:{id}`) **only if** `shipped_at` is later than the product's most recent `CYCLE_COUNT.occurred_at`. If the shipment happened before the latest count, the count already reflects it. The reservation is consumed and no movement is written. | MVP |
| BR-131 | A `SHIPMENT` movement is written at most once per order line (unique `reference`). | MVP |
| BR-132 | Status `RETURNED` does **not** restock automatically. Returned goods need inspection, so restocking is recorded explicitly with a `RETURN_RESTOCK` adjustment. | Industry |

### 2.5 Stock health classification

Health is evaluated top-down and the first match wins. `DATA_ISSUE` applies to products of any status,
like `DATA_NEGATIVE_ON_HAND`. The availability classes below it apply only to products with
`status = ACTIVE`; other products are not classified (health `null`).

| Health | Condition | Raises exception? |
|---|---|---|
| `DATA_ISSUE` | `on_hand < 0`, any product status. Not an availability class: the stock figure is invalid input (BR-402a) | yes: `DATA_NEGATIVE_ON_HAND` only; every inventory rule is suppressed |
| `OVERSOLD` | `available < 0` (with `on_hand ≥ 0`, so `reserved > on_hand`) | yes: `INVENTORY_OVERSOLD` |
| `OUT_OF_STOCK` | `available = 0` | yes: `INVENTORY_OUT_OF_STOCK` |
| `BELOW_REORDER_POINT` | `0 < available ≤ reorder_point` | yes: `INVENTORY_BELOW_REORDER_POINT` |
| `APPROACHING_REORDER_POINT` | `reorder_point < available ≤ ceil(reorder_point × approaching_factor)` (default factor 1.25) | no, shown in the inventory view only |
| `HEALTHY` | otherwise | no |

A product with `on_hand < 0` is therefore never counted or filtered as `OVERSOLD` or any other
availability class until a cycle count corrects it. Health filters select it as `DATA_ISSUE`, and
the dashboard's stock health summary counts it separately (`data_issue`, ACTIVE products, so the
six counts add up to the number of active products).

| ID | Rule | Basis |
|---|---|---|
| BR-140 | Products with `reorder_point = 0` never classify as `BELOW_REORDER_POINT` or `APPROACHING_REORDER_POINT`. | MVP |
| BR-141 | Health is computed on read from the current balance. It is never stored as a separate field that could drift. | MVP |

### 2.6 Sales velocity and days of cover (estimates)

| ID | Rule | Basis |
|---|---|---|
| BR-150 | `avg_daily_units = units on order lines placed in the last velocity_window_days (default 28) whose order status is not CANCELLED, PAYMENT_FAILED, CREATED, or PAYMENT_PENDING, and that are not REFUNDED-before-shipping (status REFUNDED with fulfillment UNFULFILLED), divided by velocity_window_days`. | Industry (simple moving average) |
| BR-151 | `days_of_cover = available / avg_daily_units` when `avg_daily_units > 0`; otherwise "not enough sales history". | Industry |
| BR-152 | Velocity and days of cover are **estimates**. The UI and AI must label them that way. They ignore seasonality and promotions. | MVP; Validate |

## 3. Orders and fulfillment

| ID | Rule | Basis |
|---|---|---|
| BR-201 | **Ship-by deadline**: `ship_by` from the import if present; otherwise `paid_at + fulfillment_sla_hours` (default 48). The deadline is stored in UTC. | Industry (handling-time SLA) |
| BR-202 | An order is **overdue** when its status is in `{PAID, PROCESSING, READY_TO_SHIP}` and `as_of > ship_by`. The comparison is strict: exactly at the deadline is not overdue. | MVP |
| BR-203 | An order is **stalled after payment** when `status = PAID`, `as_of − paid_at > stall_threshold_hours` (default 12), and it is not yet overdue. Overdue supersedes stalled. | MVP; Validate thresholds |
| BR-204 | SLAs use calendar hours. Business-hour calendars and carrier cut-off times are out of scope for the MVP. | MVP |
| BR-205 | **Order total reconciliation**: `expected_total = Σ(line quantity × unit_price − line_discount) − order_discount + shipping + tax`. A mismatch exists when `|total − expected_total| > 0.01` and the order has at least one line. | Industry |
| BR-206 | A cancelled order whose `payment_status` is still `PAID` has a **refund pending**. It becomes overdue `refund_overdue_hours` (default 24) after `cancelled_at`. | Industry |

## 4. Exception detection (summary)

The full rule definitions are in `EXCEPTION_CATALOG.md`. Summary:

| ID | Rule |
|---|---|
| BR-401 | One inventory exception at most per product at a time, and it is the most severe: `OVERSOLD` > `OVERSELL_RISK` > `OUT_OF_STOCK` > `BELOW_REORDER_POINT`. When a more severe condition appears, the less severe exception is resolved with `SUPERSEDED` and its assignee carries over. |
| BR-402a | If `on_hand < 0`, the stock figure is invalid input. Only `DATA_NEGATIVE_ON_HAND` is raised for that product, and every inventory rule is suppressed until on-hand is corrected. An active inventory exception for that product is resolved as `SUPERSEDED` by the data-quality exception (not `CONDITION_CLEARED`), and its assignee carries over. `INVENTORY_OVERSOLD` therefore always has `on_hand ≥ 0` and `reserved > on_hand`, so it always has affected orders. |
| BR-402 | Oversold: affected orders are found by allocating `on_hand` to committed order lines in FIFO order of `paid_at`. Lines that cannot be fully covered are affected. |
| BR-403 | Oversell risk: `available ≥ 0` and `pending_demand > available`. Potential shortage = `pending_demand − available`. |
| BR-404 | Exposure figures are **gross order-line value at risk**, not measured financial loss. They must never be labelled as "loss". |

## 5. Time, money, and identifiers

| ID | Rule | Basis |
|---|---|---|
| BR-501 | All timestamps are stored as UTC (`timestamptz`) and displayed in the store time zone with the zone abbreviation. | Industry |
| BR-502 | Import timestamps must be ISO-8601. If a timestamp has no UTC offset, it is interpreted in the store's time zone, and the import preview flags this with a warning. Local times that are ambiguous at a daylight-saving change resolve to the first occurrence (`fold=0`). | MVP |
| BR-503 | Money is stored as `NUMERIC(12,2)` and processed as `Decimal`. Floating point is never used for money. | Industry |
| BR-504 | Each evaluation receives an explicit `as_of` timestamp. Rules never read the wall clock directly, which keeps them deterministic and testable. | MVP |
| BR-505 | Customer references in the product are opaque identifiers (e.g. `CUST-10492`). The MVP stores no customer names, addresses, emails, or phone numbers (data minimisation). | MVP |
| BR-506 | SKUs are unique per store and compared case-sensitively after trimming whitespace. | MVP |

## 6. Imports

The detailed data contracts are in `docs/workflows/IMPORT_PIPELINE.md`. Core rules:

| ID | Rule | Basis |
|---|---|---|
| BR-601 | Supported types: `products`, `orders`, `order_items`, `inventory_adjustments`. Each has a fixed column contract and a downloadable template. | MVP |
| BR-602 | File limits: UTF-8 (a BOM is accepted), `.csv` only, at most 5 MB and 20,000 data rows. Anything else is rejected before row validation. | MVP |
| BR-603 | Unknown columns produce a warning and are ignored. Missing required columns reject the whole file. | Industry |
| BR-604 | Duplicate keys inside one file (e.g. the same SKU twice) are row errors on every occurrence after the first. | Industry |
| BR-605 | Referential integrity: `order_items` must reference an order and a SKU that already exist in the database. Import `orders.csv` first. Otherwise the row errors with `UNKNOWN_ORDER` / `UNKNOWN_SKU`. | Industry |
| BR-606 | Apply is atomic (one transaction). Strict mode is the default. Valid-rows-only mode needs explicit confirmation of the number of skipped rows. | MVP |
| BR-607 | A file whose SHA-256 matches an import already completed for the same store and type is flagged in the preview as `DUPLICATE_FILE`. The user can still apply it, because the semantics are upserts and idempotent references. | MVP |
| BR-608 | Products and orders are upserted by natural key (`sku`, `order_number`). Order status updates obey the reachability rule in `STATE_MACHINES.md §1.2`. | MVP |
| BR-609 | Order lines are upserted by `(order_number, line_number)`. A line that has already been recorded on an order that has shipped (`fulfillment_status ∈ {SHIPPED, DELIVERED, RETURNED}`) cannot change (`ORDER_LINE_LOCKED`). Recording a line for the first time is always allowed, because historical shipped orders arrive in `orders.csv` before their lines arrive in `order_items.csv`. | MVP |

## 7. Configuration defaults

Configuration is stored per store in `store_settings`. Changing it requires `settings.manage`
and writes an audit log entry.

| Key | Default | Used by |
|---|---|---|
| `fulfillment_sla_hours` | 48 | BR-201 |
| `stall_threshold_hours` | 12 | BR-203 |
| `refund_overdue_hours` | 24 | BR-206 |
| `approaching_reorder_factor` | 1.25 | §2.5 |
| `velocity_window_days` | 28 | BR-150 |
| `reopen_window_hours` | 72 | `STATE_MACHINES.md §3.3` |
| `exposure_cap` | 5000 (store currency) | `PRIORITY_MODEL.md` |
| `priority_weights` | see `PRIORITY_MODEL.md` | `PRIORITY_MODEL.md` |
| `evaluation_interval_minutes` | 15 | scheduled evaluation |
