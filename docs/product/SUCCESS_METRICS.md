# Success Metrics

> **Status:** Draft v1 (M0, T-001) · **Owner:** Product/BA · **Last updated:** 2026-10-31
> Related: [PRODUCT_VISION](PRODUCT_VISION.md) · [JOBS_TO_BE_DONE](JOBS_TO_BE_DONE.md) ·
> `docs/domain/DOMAIN_MODEL.md` · `docs/domain/STATE_MACHINES.md` · `docs/domain/PRIORITY_MODEL.md`

## 1. Ground rules

1. **No baselines exist.** RetailOps Intelligence has no production usage. Every metric below has the
   target status **"To be baselined (no production usage exists)"**. No number in this document is
   a measurement.
2. **Measured from domain data.** Every metric is computed from the tables and events in
   `DOMAIN_MODEL.md`. v1 has no separate product-analytics or click telemetry. Metrics that would
   need it are listed as gaps (§12).
3. **Demo data is excluded.** Rows that belong to an organization with `organization.is_demo = true`
   are excluded from every product metric. The seeded dataset is synthetic and must never be used
   to set targets.
4. **Reproducible.** Each metric has a formula that can be written as a SQL query over the listed
   tables, scoped by `store_id`. Durations are reported as median and p90, not means. Period
   boundaries use the store time zone (BR-501).
5. **Exposure is not loss.** Metrics that use `exposure_amount` measure gross order-line value at
   risk over time (BR-404). They are never reported as money lost or saved.

**Notation.** `ex` = `operational_exception`, `ev` = `exception_event`, `run` = `evaluation_run`,
`imp` = `data_import`, `iss` = `import_row_issue`, `so` = `sales_order`. "Manual resolution codes"
are `STOCK_REPLENISHED`, `ORDER_FULFILLED`, `REFUND_ISSUED`, `DATA_CORRECTED`,
`CUSTOMER_CONTACTED`, `FIXED_IN_SOURCE_SYSTEM`, `OTHER` (`STATE_MACHINES.md §3.2`).

---

## 2. North-star metric

**NS-1 First-time verified on-time resolution rate (CRITICAL and HIGH exceptions).**

| Field | Value |
|---|---|
| Question it answers | Are the most serious problems fixed before their due date, and do the fixes hold? (Value questions 6 and 7) |
| Population | `ex` with `first_detected_at` in the period, that reached severity `CRITICAL` or `HIGH` at any time (initial severity or any `SEVERITY_CHANGED` event), excluding `resolution_code = SUPERSEDED` (the work continues in the superseding exception) and excluding `DISMISSED` (tracked by M-16) |
| Numerator | Population members with `status = RESOLVED`, `resolved_at ≤ due_at`, `reopen_count = 0`, and either `resolution_code = CONDITION_CLEARED` or `verified_at IS NOT NULL` |
| Formula | `numerator / population` |
| Source | `operational_exception` (severity, status, resolved_at, due_at, reopen_count, resolution_code, verified_at), `exception_event` (`SEVERITY_CHANGED`) |
| Good direction | Higher |
| Guardrails | M-13 reopen rate, M-16 dismissal rate, count of `DUE_DATE_CHANGED` events (a due date pushed out to meet the target is visible) |
| Target status | To be baselined (no production usage exists) |

A cohort is complete only once every member is inactive or past its `due_at`. The default response
windows for `CRITICAL` and `HIGH` are 4 h and 24 h (`PRIORITY_MODEL.md`), but due dates can be
overridden, so completeness is checked per cohort rather than assumed from the defaults.

---

## 3. Detection and data freshness

| ID | Metric | Definition and formula | Source | Direction | Target status |
|---|---|---|---|---|---|
| M-01 | Detection latency (time-based rules) | Time from the moment a condition became true to its first detection. `ORDER_FULFILLMENT_OVERDUE`: `ex.first_detected_at − ex.deadline_at` (= `ship_by`). `ORDER_REFUND_PENDING`: `ex.first_detected_at − ex.deadline_at` (= `cancelled_at + refund_overdue_hours`). `ORDER_STALLED_AFTER_PAYMENT`: `ex.first_detected_at − (paid_at + stall_threshold_hours)`, with both inputs read from `ex.calculation`. Median and p90 per type | `operational_exception` (first_detected_at, deadline_at, calculation) | Lower | To be baselined (no production usage exists) |
| M-02 | Import-to-detection latency | For runs with `run.trigger = IMPORT`: `run.finished_at − imp.applied_at`, joined by `imp.evaluation_run_id = run.id`. Median and p95 | `data_import`, `evaluation_run` | Lower | To be baselined (no production usage exists) |
| M-03 | Evaluation run failure rate | `count(run with a failed status) / count(run)` per trigger (`MANUAL`, `IMPORT`, `SCHEDULED`) | `evaluation_run` (status, error) | Lower | To be baselined (no production usage exists) |
| M-04 | Scheduled evaluation gap | Per store, the interval between consecutive `SCHEDULED` runs' `started_at`. Report the p95 gap divided by `store_settings.evaluation_interval_minutes` (design intent ≈ 1; this is a specification, not a baseline) | `evaluation_run`, `store_settings` | Closer to 1 | To be baselined (no production usage exists) |
| M-05 | Data freshness by import type | Per store and `import_type`: `as_of − max(imp.applied_at)` over imports with `status ∈ {COMPLETED, COMPLETED_WITH_ERRORS}`. Measures how recently data was imported, not how recently it was exported from the source | `data_import` | Lower | To be baselined (no production usage exists) |

M-01 measures the product's latency once data is present. If an order arrives in an import that is
already late, the lag is split between M-01 and M-05. Inventory and data-quality rules have no
derivable onset time, so they are measured by M-02 instead.

## 4. Response and ownership

| ID | Metric | Definition and formula | Source | Direction | Target status |
|---|---|---|---|---|---|
| M-06 | Time to acknowledge | `min(ev.occurred_at) − ex.first_detected_at` over `ev` with `event_type = STATUS_CHANGED`, `actor_type = USER`, `from_status = OPEN`. Population: exceptions with such an event. Always reported together with M-15 so that auto-cleared exceptions are not hidden | `exception_event`, `operational_exception` | Lower | To be baselined (no production usage exists) |
| M-07 | Time to assign | `min(exception_assignment.assigned_at) − ex.first_detected_at` (includes self-claims) | `exception_assignment`, `operational_exception` | Lower | To be baselined (no production usage exists) |
| M-08 | Unowned active exceptions | Snapshot at `as_of`: count and p90 age (`as_of − first_detected_at`) of `ex` with `status ∈ {OPEN, ACKNOWLEDGED, IN_PROGRESS, REOPENED}` and `assignee_id IS NULL`, by `priority_band` | `operational_exception` | Lower | To be baselined (no production usage exists) |
| M-09 | Due-date adherence | `count(ex resolved with resolved_at ≤ due_at) / count(ex resolved)`, excluding `SUPERSEDED`. Snapshot companion: count of active `ex` with `due_at < as_of`. Guardrail: `count(ev where event_type = DUE_DATE_CHANGED and actor_type = USER)` | `operational_exception`, `exception_event` | Higher; overrides watched | To be baselined (no production usage exists) |

## 5. Resolution quality and verification

| ID | Metric | Definition and formula | Source | Direction | Target status |
|---|---|---|---|---|---|
| M-10 | Time to resolve | `ex.resolved_at − ex.first_detected_at` for `status = RESOLVED`, split into **manual** (manual resolution codes) and **automatic** (`CONDITION_CLEARED`). `SUPERSEDED` is excluded. For reopened exceptions this uses the latest `resolved_at`, so it measures total elapsed time. Median and p90 per `exception_type` and severity | `operational_exception` | Lower | To be baselined (no production usage exists) |
| M-11 | Time to verified resolution | Manual: `ex.verified_at − ex.first_detected_at`. Automatic: `ex.resolved_at − ex.first_detected_at`. Combined distribution per type | `operational_exception` | Lower | To be baselined (no production usage exists) |
| M-12 | Verification pass rate | Of manual resolutions that have been checked: `count(ev VERIFIED) / (count(ev VERIFIED) + count(ev REOPENED with reason VERIFICATION_FAILED))` in the period | `exception_event` (event_type, payload reason) | Higher | To be baselined (no production usage exists) |
| M-13 | Reopen rate | `count(distinct ex with ≥1 REOPENED event in period) / count(distinct ex with an event where to_status = RESOLVED in period)`, split by reopen reason: `VERIFICATION_FAILED`, `RECURRED_WITHIN_WINDOW`, manual (actor_type = USER) | `exception_event`, `operational_exception.reopen_count` | Lower, but read by reason | To be baselined (no production usage exists) |
| M-14 | Recurrence after window | `count(ex created with previous_occurrence_id IS NOT NULL) / count(ex created)` per `rule_id`. Also lists the products and orders that recur most | `operational_exception` (previous_occurrence_id, rule_id) | Lower | To be baselined (no production usage exists) |
| M-15 | Auto-cleared before human action | `count(ex resolved with CONDITION_CLEARED and no ev with actor_type = USER) / count(ex resolved)`. High values can mean self-healing conditions or thresholds that are too sensitive. Interpret per rule | `operational_exception`, `exception_event` | Interpret per rule | To be baselined (no production usage exists) |
| M-16 | Dismissal rate by reason and rule | `count(ex DISMISSED with dismissed_reason = r) / count(ex created)` per `rule_id` and reason (`FALSE_POSITIVE`, `ACCEPTED_RISK`, `DUPLICATE`, `NOT_ACTIONABLE`). `FALSE_POSITIVE` is the main proxy for rule precision | `operational_exception` (dismissed_reason, rule_id) | Lower for `FALSE_POSITIVE` | To be baselined (no production usage exists) |

## 6. Operational outcome proxies

These metrics describe the operation, not the product. The product aims to improve them, but without
a pre-adoption baseline no causal claim can be made.

| ID | Metric | Definition and formula | Source | Direction | Target status |
|---|---|---|---|---|---|
| M-17 | Value-at-risk hours | Per category: `Σ ex.exposure_amount × hours(resolved_at − first_detected_at)` for exceptions resolved in the period. Never summed across categories, because one order can appear in an inventory and a fulfillment exception at the same time. Labelled "gross order-line value at risk × hours", never loss (BR-404) | `operational_exception` | Lower | To be baselined (no production usage exists) |
| M-18 | Overdue order rate | Orders with `so.paid_at` in the period that have an `ORDER_FULFILLMENT_OVERDUE` exception (via `exception_entity_link`, role `PRIMARY`) ÷ orders with `paid_at` in the period. Only cohorts whose `ship_by` has passed are reported | `sales_order`, `exception_entity_link`, `operational_exception` | Lower | To be baselined (no production usage exists) |
| M-19 | On-time ship rate | Among orders with `shipped_at` in the period: `count(shipped_at ≤ ship_by) / count(*)`, split by `ship_by_source` (`IMPORTED`, `STORE_SLA`) | `sales_order` | Higher | To be baselined (no production usage exists) |
| M-20 | Refund-pending age at resolution | For resolved `ORDER_REFUND_PENDING`: `ex.resolved_at − so.cancelled_at`. Also the share that reached `CRITICAL` (a `SEVERITY_CHANGED` event to `CRITICAL`) | `operational_exception`, `sales_order`, `exception_event` | Lower | To be baselined (no production usage exists) |

## 7. Data quality and imports

| ID | Metric | Definition and formula | Source | Direction | Target status |
|---|---|---|---|---|---|
| M-21 | Import row error rate | For imports that reached `VALIDATED`: `count(distinct (iss.import_id, iss.row_number) with severity = ERROR) / Σ imp.row_count`, per `import_type`. Breakdown by issue `code` (top 5) | `data_import`, `import_row_issue` | Lower | To be baselined (no production usage exists) |
| M-22 | File rejection and apply failure rate | `count(imp with status = REJECTED) / count(imp)` by file-level code (`FILE_EMPTY`, `FILE_TOO_LARGE`, `FILE_TYPE`, `FILE_ENCODING`, `TOO_MANY_ROWS`, `MISSING_COLUMNS`), and `count(status = FAILED) / count(imp that reached APPLYING)` | `data_import`, `import_row_issue` | Lower | To be baselined (no production usage exists) |
| M-23 | Valid-rows-only skip rate | Share of applied imports with `mode = VALID_ROWS_ONLY`, and `Σ skipped rows / Σ row_count` within them (skipped rows from `imp.summary` error count) | `data_import` (mode, summary, row_count) | Lower | To be baselined (no production usage exists) |
| M-24 | Data-quality exception rate | `count(ex with category = DATA_QUALITY created in period)` per 1,000 orders with `so.created_at` in the period, split by `DATA_ORDER_TOTAL_MISMATCH` and `DATA_NEGATIVE_ON_HAND` | `operational_exception`, `sales_order` | Lower | To be baselined (no production usage exists) |

## 8. Copilot

| ID | Metric | Definition and formula | Source | Direction | Target status |
|---|---|---|---|---|---|
| M-25 | Answer groundedness | Share of assistant messages in which **every** item in `facts[]` and `metrics[]` has at least one ref, and every ref resolves to a record in the user's store that a tool call for that message returned. `count(grounded messages) / count(assistant messages)`, split by `generated_by` | `ai_message.content`, `ai_tool_call` (see gap G-2) | Higher | To be baselined (no production usage exists) |
| M-26 | Reference coverage | Item level: `count(facts and metrics items with ≥1 ref) / count(facts and metrics items)` | `ai_message.content` | Higher | To be baselined (no production usage exists) |
| M-27 | Unsupported-answer rate (offline) | On the copilot evaluation dataset (T-074): share of answers that contain a claim not supported by tool results, as scored by the evaluation runner. Stored with date and provider | Evaluation results (`apps/api/evals/`), not a production table | Lower | To be baselined (no production usage exists) |
| M-28 | Tool error and denial rate | `count(ai_tool_call with an unsuccessful status) / count(ai_tool_call)`, by `tool_name` and by cause (validation error, permission denied, execution error) | `ai_tool_call` (status, error) | Lower | To be baselined (no production usage exists) |
| M-29 | Deterministic answer share | `count(ai_message where provider = deterministic) / count(assistant ai_message)` | `ai_message` (provider, model) | Descriptive | To be baselined (no production usage exists) |
| M-30 | Copilot latency | p50 and p95 of `ai_message.latency_ms` per provider; p95 of `ai_tool_call.duration_ms` per tool | `ai_message`, `ai_tool_call` | Lower | To be baselined (no production usage exists) |
| M-31 | AI note draft acceptance rate | `count(exception_note with source = AI_DRAFT_ACCEPTED) / count(drafts offered)` | `exception_note`; the denominator needs instrumentation (gap G-1) | Descriptive | To be baselined (no production usage exists) |

## 9. Engagement (from domain events only)

| ID | Metric | Definition and formula | Source | Direction | Target status |
|---|---|---|---|---|---|
| M-32 | Weekly active operators | Per store and ISO week: distinct `ev.actor_id` with `actor_type = USER`, plus distinct `ai_conversation.user_id` with a user message that week, reported separately | `exception_event`, `ai_conversation`, `ai_message` | Higher | To be baselined (no production usage exists) |

---

## 10. Guardrail invariants (requirements, not success metrics)

These are correctness requirements. They are enforced by code and tests, so they have a fixed
expected value rather than a baseline. A non-zero value is a defect, not a trend.

| ID | Invariant | Expected | Enforced by |
|---|---|---|---|
| I-1 | Ledger drift: `inventory_balance.on_hand ≠ Σ inventory_movement.on_hand_delta` | 0 products | Reconciliation check (BR-104), tests |
| I-2 | Reservation drift: `inventory_balance.reserved ≠ Σ ACTIVE stock_reservation.quantity` | 0 products | `STATE_MACHINES.md §2`, tests |
| I-3 | Skipped import rows without an `import_row_issue` | 0 rows | BR-606, tests |
| I-4 | More than one active exception per `(store_id, dedup_key)` | 0 | Partial unique index |
| I-5 | Cross-tenant reads or writes | 0 | Repository scoping (BR-003), cross-tenant tests |
| I-6 | AI writes to business tables | 0 | Architecture (ADR-0010), tests |
| I-7 | Successful mutations by `VIEWER` | 0 | `require_permission`, tests |
| I-8 | Exposure shown or spoken as "loss" | 0 occurrences | UI copy review, copilot evaluation (BR-404) |

## 11. Metric pairs (avoid gaming)

| If this improves… | …check that this does not get worse | Why |
|---|---|---|
| M-10 Time to resolve | M-13 Reopen rate (`VERIFICATION_FAILED`) | Resolving before the condition clears looks fast but reopens |
| M-09 Due-date adherence | `DUE_DATE_CHANGED` count | Moving due dates out improves adherence without improving work |
| M-16 Dismissal rate (lower) | M-13, M-14 | Not dismissing noisy findings can inflate reopens and recurrences |
| M-06 Time to acknowledge | M-07 Time to assign, M-10 | Acknowledging without owning or acting |
| M-21 Row error rate (lower) | M-23 Valid-rows-only skip rate | Errors can be hidden by skipping rows instead of fixing exports |

## 12. Instrumentation gaps and open questions

| ID | Gap | Affects | Proposed resolution (needs owner decision) |
|---|---|---|---|
| G-1 | The number of AI note drafts offered is not stored. The structured answer schema has no note-draft field | M-31 | AI engineer (T-070) defines where a draft lives, for example a typed section in `ai_message.content` |
| G-2 | `ai_tool_call` stores `result_summary` and `row_count`, not the IDs of returned records, so ref validity cannot be checked after the fact | M-25 | Store returned entity IDs (capped) in `ai_tool_call`, or validate refs at answer time and persist the result |
| G-3 | Priority band history is not stored. `priority_band` holds only the current value | Per-band response metrics | Use severity (whose changes are evented) for cohorts, as NS-1 does, or record band changes in `EVIDENCE_UPDATED` payloads |
| G-4 | Evaluation run status values are not enumerated in `DOMAIN_MODEL.md` | M-03 | Define them in T-053 |
| G-5 | No UI telemetry (page views, filter use, time on page) | Engagement beyond M-32 | Deliberately out of scope for v1 (data minimisation). Revisit with a real pilot |
| G-6 | Inventory and data-quality conditions have no recorded onset time | M-01 for those types | Accept M-02 as the proxy. Do not infer onset from movements |

## 13. Baselining plan

1. Only after a real store uses the product. The demo organization never counts.
2. Collect at least four full weeks of data before proposing any target. **[MVP assumption: the
   period length]**
3. Set targets per exception type and severity, not as one global number.
4. Record each target in this file with the date, the store count, and the data window it came from.

## 14. Deliberately not measured

| Not measured | Reason |
|---|---|
| "Loss prevented", "revenue saved" | The product measures value at risk, not loss (BR-404), and has no counterfactual |
| AI "accuracy %" without a dataset | Accuracy is reported only from the evaluation runner (T-074), with date and provider |
| Customer satisfaction or dispute rate | The product stores no customer data (BR-505) and no dispute data (non-goal) |
