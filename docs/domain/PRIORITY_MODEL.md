# Priority Model

> **Status:** Canonical (v1). Implemented in `apps/api/app/domains/exceptions/priority.py`.

## Purpose

Severity describes **how bad the condition is**. Priority describes **what to work on first**.
Priority mixes severity with breadth (how many orders are affected), exposure, deadline, and how
long the exception has gone unresolved. The score is a ranking aid. It is **not** a measure of money
lost or of business impact, and the UI shows how it was calculated for every exception.

## Formula

```
priority_score = min(100, S + A + E + D + T)
```

| Component | Definition | Default weight / cap |
|---|---|---|
| **S**: severity | `CRITICAL` 50 · `HIGH` 35 · `MEDIUM` 20 · `LOW` 8 | 50 max |
| **A**: affected orders | `min(cap_A, 3 × n)` where `n` = distinct affected orders | cap 15 |
| **E**: exposure | `0` if `v ≤ 0`, else `round(cap_E × log10(1 + v) / log10(1 + exposure_cap))`, clamped to `cap_E`. `v` is the gross order-line value at risk, in store currency | cap 15, `exposure_cap` = 5000 |
| **D**: deadline | passed (`deadline_at ≤ as_of`) → 12 · `0 < deadline_at − as_of ≤ 24 h` → 8 · `≤ 72 h` → 4 · otherwise or none → 0 | 12 max |
| **T**: time unresolved | `min(cap_T, 2 × whole days since first_detected_at)` | cap 8 |

The maximum is 50 + 15 + 15 + 12 + 8 = **100**.

Exposure is logarithmic so one very large order does not drown out everything else, while larger
values still rank higher.

## Priority bands

| Band | Score | Expected response (guideline, configurable) |
|---|---|---|
| **P1** | ≥ 70 | same working day |
| **P2** | 50–69 | within 1 day |
| **P3** | 30–49 | within 3 days |
| **P4** | < 30 | within 7 days |

## Exception due date

`due_at = first_detected_at + response_hours(severity)`, where `CRITICAL` = 4 h, `HIGH` = 24 h,
`MEDIUM` = 72 h, `LOW` = 168 h. When the finding has a business `deadline_at` that is in the future
and earlier than that, `due_at = deadline_at`. The due date is set at creation and recalculated
when severity changes, unless a user overrode it. A user with `exceptions.assign` can override it
(`due_at_overridden = true`, audited), and automatic recalculation never replaces an override.

## Worked examples

| Exception | S | A | E | D | T | Score | Band |
|---|---|---|---|---|---|---|---|
| Oversold SKU, 4 committed orders, 600.00 at risk, nearest ship-by in 10 h, new | 50 | 12 | 11 | 8 | 0 | **81** | P1 |
| Order overdue by 30 h, total 120.00, detected when it became overdue (1 whole day open) | 35 | 3 | 8 | 12 | 2 | **60** | P2 |
| Below reorder point, medium severity, no orders, 3 days open | 20 | 0 | 0 | 0 | 6 | **26** | P4 |
| Refund pending on 89.90 order, 26 h after cancellation | 35 | 3 | 8 | 12 | 0 | **58** | P2 |

(E for 600.00: `15 × log10(601) / log10(5001) = 15 × 2.779 / 3.699 = 11.27 → 11`.)

## Configuration

Weights and caps live in `store_settings.priority_weights`; `exposure_cap` is its own `store_settings` column. They are validated
(non-negative integers that sum to at most 100 at the maximum). When weights change, priorities are
recalculated at the next evaluation, and the change is written to the audit log.

## Limitations (stated in the UI tooltip and in the AI copilot's answers)

- The score is a heuristic. The weights are reasonable defaults that have not been validated with
  real operators, and each team should tune them.
- Exposure counts the gross value of order lines that are at risk. It does not account for margin,
  whether customers would accept a delay, or how likely the risk is to materialise.
- Severity thresholds use calendar hours, not business hours (BR-204).
- Customer impact (repeat customer, VIP, complaint history) is not modelled, because the MVP stores
  no customer profile data (BR-505).
