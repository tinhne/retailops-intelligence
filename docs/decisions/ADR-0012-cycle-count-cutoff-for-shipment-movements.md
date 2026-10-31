# ADR-0012: Cycle-count cutoff for shipment movements

| Field | Value |
|---|---|
| Decision ID | ADR-0012 |
| Title | Cycle-count cutoff for shipment movements |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

`on_hand` is the sum of ledger deltas (BR-110). Stock decreases from two sources:

- **Shipments**, which the platform learns about from order imports (`shipped_at`).
- **Cycle counts** imported from the source system (`CYCLE_COUNT`, an absolute count; delta = counted −
  current `on_hand`, BR-111).

A count taken in the warehouse already reflects every order that shipped before it. If the platform
also wrote a shipment movement for those orders, stock would be decremented twice. Imports arrive in
any order: a count may be imported before or after the orders it already reflects.

## Alternatives considered

### A. Always write a shipment movement when an order ships

- **Pros:** simple and uniform.
- **Cons:** double-decrements every shipment that a later-imported count already reflects; on_hand
  drifts low and creates false out-of-stock or oversold exceptions.

### B. Never write shipment movements (counts are the only source of decreases)

- **Pros:** no double counting.
- **Cons:** `on_hand` stays stale between counts, so oversold detection lags by days.

### C. Treat counts as deltas

- **Pros:** composes with shipment movements.
- **Cons:** source systems export absolute counts; the delta they imply is unknowable without the
  source's own ledger.

### D. Full as-of ledger replay (compute the count's delta against the ledger as of the count time)

- **Pros:** correct for back-dated counts too.
- **Cons:** more complex and more expensive to explain and test; depends on precise timestamps
  everywhere.

## Decision

BR-130 and BR-131:

- When an order line becomes fulfilled, write one `SHIPMENT` movement (`on_hand_delta = −quantity`,
  `reference = order_item:{id}`) **only if** `shipped_at` is later than the product's most recent
  `CYCLE_COUNT.occurred_at`. Otherwise the count already reflects it; the reservation is consumed and no
  movement is written.
- At most one `SHIPMENT` movement per order line, guaranteed by the unique `(store_id, reference)`
  constraint.
- `RETURNED` does not restock automatically (BR-132).

## Consequences

### Positive

- No double counting in the common case (a count imported after the shipments it reflects).
- Shipment handling is idempotent and safe to retry.
- Each decision is explainable from two timestamps shown in the evidence.

### Negative

- Correctness depends on accurate `occurred_at` and `shipped_at` values from source systems. Clock skew
  or a count taken before picking but stamped later can overstate `on_hand`, and reconciliation
  (BR-104) cannot detect it because the ledger is internally consistent.
- **Back-dated counts (resolved, BR-113).** The cutoff is combined with option D for counts: a
  `CYCLE_COUNT` delta is computed against on-hand **as of its `occurred_at`**
  (`counted − (on_hand − Σ deltas recorded after the count time)`). A count imported after
  later-dated movements therefore keeps them instead of overstating `on_hand`. A count older than
  the product's latest count is rejected (`STALE_CYCLE_COUNT`). Implemented in
  `inventory/service.py::record_movement` and covered by
  `test_late_imported_count_keeps_movements_recorded_after_it`.
- **Reserved references (resolved).** Imported references starting with `order_item:` are rejected
  as a row error (`RESERVED_REFERENCE`), because that prefix belongs to system shipment movements.
- **Needs validation** with real exports: how source systems timestamp counts and shipments.

## Related documents

- [`BUSINESS_RULES.md`](../domain/BUSINESS_RULES.md) §2.2, §2.4
- [`STATE_MACHINES.md`](../domain/STATE_MACHINES.md) §1.5, §2
- [`ENTITY_RELATIONSHIPS.md`](../domain/ENTITY_RELATIONSHIPS.md) §4.1
- ADR-0006
