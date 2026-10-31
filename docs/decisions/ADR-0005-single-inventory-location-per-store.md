# ADR-0005: Single inventory location per store

| Field | Value |
|---|---|
| Decision ID | ADR-0005 |
| Title | Single inventory location per store |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

Inventory exceptions depend on `available = on_hand − reserved` (BR-101). With several locations,
"available" becomes a question of allocation: which warehouse ships which order line, whether stock can
be transferred, and whether an oversell is per location or network-wide. Each answer changes the
oversell calculation and the affected-order allocation (BR-402).

The **MVP assumption** is that target stores fulfil from one location. This is **Needs validation**
with real operators.

## Alternatives considered

### A. Multi-location from the start (location table; balances, movements and reservations per location)

- **Pros:** fits larger merchants and stores using a third-party logistics provider plus their own
  stock.
- **Cons:** needs routing rules, transfers and per-location reservations before any exception can be
  computed correctly; the import contracts grow a location column; every rule and test doubles in
  complexity before the core workflow is validated.

### B. A location column with a single default location ("schema-ready")

- **Pros:** a later migration looks easier.
- **Cons:** dead complexity in every query, index and test, and a false impression that multi-location
  works. The hard part of multi-location is allocation logic, not the column.

## Decision

Each store has exactly one implicit fulfillment location (BR-005). Inventory is keyed by
`(store_id, product_id)` in `inventory_balance`; movements and reservations carry no location.

## Consequences

### Positive

- The inventory formulas, health classification and oversell allocation stay simple, exact and fully
  testable.
- Import contracts stay small.

### Negative

- Merchants with several warehouses cannot be represented correctly. Splitting them into several
  stores is not a real workaround, because orders and SKUs would split too.
- Adding locations later requires a location key on balances, movements and reservations, a
  redefinition of `available`, allocation rules for oversell, and a data migration.

## Related documents

- [`BUSINESS_RULES.md`](../domain/BUSINESS_RULES.md) (BR-005, BR-101, BR-402)
- [`DOMAIN_MODEL.md`](../domain/DOMAIN_MODEL.md) §3 (InventoryLocation excluded)
- [`ENTITY_RELATIONSHIPS.md`](../domain/ENTITY_RELATIONSHIPS.md)
