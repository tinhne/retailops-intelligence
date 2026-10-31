# ADR-0006: Three order status axes and reachability-based import sync

| Field | Value |
|---|---|
| Decision ID | ADR-0006 |
| Title | Three order status axes and reachability-based import sync |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

Orders arrive as snapshots in CSV exports. Two facts shape the model:

1. **A single status loses information.** A cancelled order whose payment is still captured means the
   store owes a refund (`ORDER_REFUND_PENDING`). A refunded order whose goods were delivered means the
   customer kept the goods. Both facts disappear if lifecycle, payment and fulfillment are one field.
2. **Exports skip states.** An order exported as `PAID` yesterday can appear as `SHIPPED` today with
   no record of `PROCESSING` or `READY_TO_SHIP` in between.

Reservations and shipment movements are driven by order status (STATE_MACHINES §1.5), so an invalid
status change corrupts inventory as well as order history.

## Alternatives considered

### A. One status field

- **Pros:** simplest model and UI.
- **Cons:** cannot express "cancelled but still paid" or "refunded after delivery"; refund-pending
  detection becomes guesswork.

### B. Three axes, but imports must follow single-step transitions

- **Pros:** every transition is explicitly observed.
- **Cons:** rejects most real exports, which skip intermediate states; users would have to fabricate
  intermediate files.

### C. Accept whatever status the import says (the source system is the truth)

- **Pros:** never rejects a row.
- **Cons:** accepts regressions such as `DELIVERED → PAID` or `CANCELLED → SHIPPED`, which would
  re-reserve or double-ship stock and make the order history meaningless.

## Decision

- Orders carry three fields: `status`, `payment_status`, `fulfillment_status`, which must satisfy the
  axis compatibility matrix (STATE_MACHINES §1.3); `fulfillment_status` is derived when omitted.
- An import may move an existing order to any state **reachable** from its current state through the
  lifecycle graph (STATE_MACHINES §1.2). The `order_event` records `source = IMPORT` and the skipped
  states. Unreachable targets are row errors (`ORDER_TRANSITION_NOT_ALLOWED`); invalid axis
  combinations are `ORDER_INVALID_STATUS_COMBINATION`.
- Reservation and shipment effects follow the resulting status, through the idempotent
  `reservations.sync_for_orders` (BR-123).

## Consequences

### Positive

- Business facts survive in terminal states, and refund-pending detection is exact.
- Imports tolerate the granularity of real exports.
- Order history is honest about inferred steps (`skipped_statuses`).
- Inventory effects cannot be triggered by impossible transitions.

### Negative

- Users meet more validation errors (axis combinations, unreachable moves) and need clear messages
  and documentation.
- A reachable but wrong jump (an export error that moves `PAID` straight to `DELIVERED`) is accepted.
- A legitimate backward correction in the source system (for example a mistaken `SHIPPED` corrected to
  `PROCESSING`) is rejected, and v1 has no manual correction path. Open question for the product
  owner.
- The compatibility matrix and reachability check add work to every order import row (computed from a
  small static graph, so the cost is negligible).

## Related documents

- [`STATE_MACHINES.md`](../domain/STATE_MACHINES.md) §1
- [`BUSINESS_RULES.md`](../domain/BUSINESS_RULES.md) (BR-120..123, BR-206, BR-608)
- [`EXCEPTION_CATALOG.md`](../domain/EXCEPTION_CATALOG.md) (`ORDER_REFUND_PENDING`)
- ADR-0012
