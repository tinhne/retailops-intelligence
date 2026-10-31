# Jobs To Be Done

> **Status:** Draft v1 (M0, T-001) · **Owner:** Product/BA · **Last updated:** 2026-10-31
> Related: [PERSONAS](PERSONAS.md) · [FEATURE_CATALOG](FEATURE_CATALOG.md) ·
> [SUCCESS_METRICS](SUCCESS_METRICS.md) · `docs/domain/EXCEPTION_CATALOG.md`

All jobs below are **hypotheses** derived from the proto-personas. They are not findings from user
research. Each job is mapped to the exception types it depends on, the workflow that serves it, the
features that implement it, and the metric that would show whether it is being done well.

**Format.** *When* [situation], *I want to* [motivation], *so I can* [expected outcome].

**Workflow references.** The workflow documents are written in M1 (T-010). Their planned paths are:

| Code | Workflow document (T-010) | Canonical basis |
|---|---|---|
| WF-ORD | `docs/workflows/ORDER_LIFECYCLE.md` | `STATE_MACHINES.md §1`, BR-201..206 |
| WF-INV | `docs/workflows/INVENTORY_LIFECYCLE.md` | `STATE_MACHINES.md §2`, BR-101..152 |
| WF-EXC | `docs/workflows/EXCEPTION_MANAGEMENT.md` | `STATE_MACHINES.md §3`, `EXCEPTION_CATALOG.md`, `PRIORITY_MODEL.md` |
| WF-IMP | `docs/workflows/IMPORT_PIPELINE.md` | `STATE_MACHINES.md §4`, BR-601..608 |
| WF-AI | `docs/workflows/AI_ASSISTED_INVESTIGATION.md` | ADR-0010, structured answer schema |
| WF-RBAC | `docs/workflows/ROLE_AND_PERMISSION_WORKFLOW.md` | ADR-0007, BR-001..003 |

---

## 1. The core job

> *When* I run a small online store across several sales channels and systems, *I want to* know
> every condition that is breaking, or about to break, a promise to a customer (stock, shipping,
> refund) or the accuracy of our records, *so I can* fix the most important ones first, know who is
> fixing them, and be sure they stay fixed.

Every persona job below is a slice of this core job. The seven value questions in
[PRODUCT_VISION §4](PRODUCT_VISION.md#4-value-proposition-the-seven-questions) are the steps of the
job: see, understand, prioritise, act, own, verify.

---

## 2. Store Owner

| ID | Job statement | Exception types | Workflow | Features | Measured by |
|---|---|---|---|---|---|
| JTBD-O1 | *When* I check in on the business, *I want to* see in one place which problems are putting customer orders or customer money at risk and whether someone owns each one, *so I can* decide whether to step in or trust the team | All nine types, grouped by category | WF-EXC | F-010, F-007 | M-08, NS-1 |
| JTBD-O2 | *When* an order has been cancelled but the customer's payment is still captured, *I want to* know before the customer has to chase us or dispute the charge, *so I can* get the refund issued and avoid paying for the same mistake twice | `ORDER_REFUND_PENDING` | WF-ORD, WF-EXC | F-006, F-007, F-009 | M-20, M-01 |
| JTBD-O3 | *When* a SKU is oversold, *I want to* see exactly which paid orders cannot be covered and their combined value at risk, *so I can* decide between expediting stock, contacting customers about a delay, or cancelling and refunding | `INVENTORY_OVERSOLD` | WF-INV, WF-EXC | F-009 | M-17 |
| JTBD-O4 | *When* I see a monetary figure in the product, *I want to* know exactly what it counts and what it does not, *so I can* avoid making a financial decision on a misread number | All types with exposure (BR-404) | WF-EXC | F-009 (priority breakdown), F-011 | M-25 |
| JTBD-O5 | *When* people join or leave the team, *I want to* grant or remove access at the right level, *so I can* keep business data and actions limited to the people who need them | none | WF-RBAC | F-001, F-016 (P1) | none (security control) |
| JTBD-O6 | *When* a decision looks wrong in hindsight (a dismissal, a reopen, an import applied with skipped rows), *I want to* see who did what and when, *so I can* fix the process rather than argue about memory | none | WF-RBAC | F-012, F-008 history | none |

**Emotional and social dimension (Needs validation).** Feel in control without micro-managing.
Avoid being surprised by a customer complaint or a marketplace warning about something the team
should have caught.

## 3. Operations Manager

| ID | Job statement | Exception types | Workflow | Features | Measured by |
|---|---|---|---|---|---|
| JTBD-M1 | *When* fresh data has been imported, *I want to* get one ranked list of what needs attention across inventory, fulfillment, payment, and data quality, *so I can* assign the most urgent work first instead of building the list by hand | All nine types | WF-IMP → WF-EXC | F-002, F-006, F-007 | M-02, M-06 |
| JTBD-M2 | *When* paid orders for a SKU exceed physical stock, *I want to* know which orders are short and in what order they were paid, *so I can* decide whom to fulfil first and whom to contact | `INVENTORY_OVERSOLD` (FIFO allocation by `paid_at`, BR-402) | WF-INV | F-009, F-005 | M-17 |
| JTBD-M3 | *When* unpaid orders for a SKU add up to more than the stock still available, *I want to* be warned before those orders are paid, *so I can* pause the listing or confirm incoming stock in time | `INVENTORY_OVERSELL_RISK` (BR-403) | WF-INV | F-006, F-009 | M-02, M-15 |
| JTBD-M4 | *When* a paid order has not moved into processing, *I want to* see it before its ship-by deadline passes, *so I can* get it picked and avoid a late shipment | `ORDER_STALLED_AFTER_PAYMENT`, then `ORDER_FULFILLMENT_OVERDUE` (BR-201..203) | WF-ORD, WF-EXC | F-006, F-007 | M-01, M-18, M-19 |
| JTBD-M5 | *When* stock for a SKU drops low, *I want to* know whether it will likely run out before a replenishment can arrive, *so I can* reorder in time and with the right quantity | `INVENTORY_BELOW_REORDER_POINT` (severity uses days of cover vs lead time), `INVENTORY_OUT_OF_STOCK` | WF-INV | F-003, F-009 | M-10 |
| JTBD-M6 | *When* someone on my team marks a problem resolved, *I want to* have the system confirm from the data that the condition is gone, *so I can* trust the closed list without re-checking it myself | All types (verification, `STATE_MACHINES.md §3.4`) | WF-EXC | F-006, F-008 | M-12, M-13 |
| JTBD-M7 | *When* an alert describes a condition we have consciously accepted (a known data quirk, a pre-order SKU), *I want to* dismiss it with a reason and not see it again until the condition changes, *so I can* keep the queue meaningful | Any type. Dismissed exceptions stay dismissed until the condition clears and returns (`STATE_MACHINES.md §3.3`) | WF-EXC | F-008 | M-16 |
| JTBD-M8 | *When* I import an export from the storefront or a stock count, *I want to* see every row that would fail and why, before anything changes, *so I can* fix the export instead of corrupting our data | none (import issues are not exceptions, `EXCEPTION_CATALOG.md`) | WF-IMP | F-002 | M-21, M-22, M-23 |
| JTBD-M9 | *When* a threshold does not match how we operate (we promise 24 h handling, not 48 h), *I want to* change it once for the store, *so I can* make detection match our actual promises | `ORDER_FULFILLMENT_OVERDUE`, `ORDER_STALLED_AFTER_PAYMENT`, `ORDER_REFUND_PENDING` (BR §7 settings) | WF-EXC | F-015 (P1) | M-16 |
| JTBD-M10 | *When* one person is overloaded or away, *I want to* see who owns what and reassign it, *so I can* keep deadlines from slipping | All types | WF-EXC | F-007, F-008 | M-07, M-09 |

**Emotional and social dimension (Needs validation).** Be seen by the Owner as running a tight
operation. Avoid the "who was supposed to check that?" conversation.

## 4. Operations Staff

| ID | Job statement | Exception types | Workflow | Features | Measured by |
|---|---|---|---|---|---|
| JTBD-S1 | *When* I start a shift, *I want to* see what is assigned to me and what unassigned work I can pick up, in priority order, *so I can* work without waiting for instructions | All types | WF-EXC | F-007, F-008 (claim) | M-06, M-08 |
| JTBD-S2 | *When* I open a problem, *I want to* have the evidence, the affected orders, and a concrete next step on one screen, *so I can* act without opening three other systems | All types (`recommended_action` per rule) | WF-EXC, WF-AI | F-009 | M-10 |
| JTBD-S3 | *When* a paid order is stuck, *I want to* know which status it is stuck in and what that status needs, *so I can* unblock it (start picking, clear the packing queue, hand over to the carrier) | `ORDER_STALLED_AFTER_PAYMENT`, `ORDER_FULFILLMENT_OVERDUE` (action depends on `PAID` / `PROCESSING` / `READY_TO_SHIP`) | WF-ORD | F-009, F-005 | M-19 |
| JTBD-S4 | *When* I have fixed something in the source system, *I want to* record what I did and why, *so I can* give the next person and the verification step the context they need | All types (resolution code plus a note of at least 10 characters) | WF-EXC | F-008 | M-13 |
| JTBD-S5 | *When* I am waiting on something outside my control (a supplier delivery, a carrier pickup), *I want to* keep the item open with a note rather than mark it resolved, *so I can* avoid it being reopened as a failed resolution | `INVENTORY_OUT_OF_STOCK`, `INVENTORY_BELOW_REORDER_POINT`, `INVENTORY_OVERSOLD` (`STATE_MACHINES.md §3.4`) | WF-EXC | F-008 | M-13 |
| JTBD-S6 | *When* physical stock does not match what the system says, *I want to* get a cycle count recorded so the ledger is corrected traceably, *so I can* trust the stock figure again | `DATA_NEGATIVE_ON_HAND`, `INVENTORY_OVERSOLD` | WF-INV, WF-IMP | F-004, F-002 (the import itself needs `imports.run`, held by the Manager) | M-24 |
| JTBD-S7 | *When* I do not understand a number, *I want to* ask in plain language and get an answer that cites the records, *so I can* explain the situation to my manager or a customer | All types | WF-AI | F-011 | M-25, M-27 |

**Emotional and social dimension (Needs validation).** Have finished work stay finished. Have a
record showing what they did when an issue comes back.

## 5. Analyst

| ID | Job statement | Exception types | Workflow | Features | Measured by |
|---|---|---|---|---|---|
| JTBD-A1 | *When* reviewing the week, *I want to* see trends by exception type, severity, and resolution time, *so I can* find recurring causes such as one supplier, one channel, or one export | All types | WF-EXC | F-010, F-018 (P1) | M-10, M-14 |
| JTBD-A2 | *When* order totals do not reconcile, *I want to* find which orders and which import rows are responsible, *so I can* fix the export mapping at the source | `DATA_ORDER_TOTAL_MISMATCH` (BR-205; evidence notes rejected import rows for the order) | WF-IMP, WF-ORD | F-002, F-009 | M-21, M-24 |
| JTBD-A3 | *When* a rule seems noisy, *I want to* see dismissal reasons and reopen rates for that rule, *so I can* recommend a threshold change with evidence | All types, per `rule_id` | WF-EXC | F-018 (P1) | M-13, M-16 |
| JTBD-A4 | *When* someone asks "why was this flagged?", *I want to* see the rule version, the `as_of` time, and the exact inputs, *so I can* give an answer anyone can reproduce | All types (`calculation`, `rule_id@version`, BR-504) | WF-EXC | F-009 | none |
| JTBD-A5 | *When* something looks wrong in the data or the queue, *I want to* read the audit trail, *so I can* tell a data problem from a process problem | none | WF-RBAC | F-012 | none |

## 6. Demo visitor (access mode)

| ID | Job statement | Features |
|---|---|---|
| JTBD-V1 | *When* I am evaluating the product, *I want to* explore a realistic store that contains every exception type and ask the copilot about it, without registering, *so I can* judge the product quickly, knowing I cannot break anything | F-013, F-011 |

---

## 7. Exception type to job map

This table links each canonical exception type to the jobs it serves, the person who usually acts, the
action that happens **outside** the product, and the signal the system uses to verify the outcome.

| Exception type | Category | Jobs | Usual actor | Action in the source system | Verified when (auto-resolve condition) |
|---|---|---|---|---|---|
| `INVENTORY_OVERSOLD` | INVENTORY | O3, M2, S5, S6 | Manager decides, Staff executes | Cycle count; expedite incoming stock; contact affected customers; cancel and refund if needed | `available ≥ 0` |
| `INVENTORY_OVERSELL_RISK` | INVENTORY | M3 | Manager | Pause or limit the listing; confirm incoming stock | `pending_demand ≤ available` or superseded |
| `INVENTORY_OUT_OF_STOCK` | INVENTORY | M5, S5 | Manager | Reorder from supplier; hide the listing | `available > 0` |
| `INVENTORY_BELOW_REORDER_POINT` | INVENTORY | M5, S5 | Manager | Place a replenishment order | `available > reorder_point` |
| `ORDER_FULFILLMENT_OVERDUE` | FULFILLMENT | M4, S3 | Staff | Pick, pack, hand over to the carrier; contact the customer about the delay | order leaves `PAID` / `PROCESSING` / `READY_TO_SHIP` |
| `ORDER_STALLED_AFTER_PAYMENT` | FULFILLMENT | M4, S3 | Staff | Move the order into processing | status ≠ `PAID` (or superseded by overdue) |
| `ORDER_REFUND_PENDING` | PAYMENT | O2 | Owner or Manager approves, Staff executes | Issue the refund in the payment system, then re-import the order | `payment_status = REFUNDED` |
| `DATA_ORDER_TOTAL_MISMATCH` | DATA_QUALITY | A2 | Analyst finds, Manager fixes | Compare with the source system; re-import missing or rejected lines | totals reconcile (BR-205) |
| `DATA_NEGATIVE_ON_HAND` | DATA_QUALITY | S6 | Staff counts, Manager imports | Physical count imported as a `CYCLE_COUNT` adjustment | `on_hand ≥ 0` |

**Implication for workflow design.** Every verification signal depends on fresh data reaching the
product. A fix made in the source system is only visible after the next import. The resolve flow in
F-008 must make this visible to the person resolving (see the risk on stale-data reopens in
[SCOPE_AND_NON_GOALS](SCOPE_AND_NON_GOALS.md)).

## 8. Jobs deliberately not served in v1

| Job | Why not now | Where it is tracked |
|---|---|---|
| "Ship this order for me" / "issue this refund for me" | The product does not write to source systems or process payments | Non-goal, [SCOPE_AND_NON_GOALS](SCOPE_AND_NON_GOALS.md) |
| "Tell me when a parcel is late in transit" | Needs carrier tracking events | `ORDER_DELIVERY_DELAYED` roadmap rule, F-033 (P3) |
| "Tell me which supplier is always late" | Needs purchase orders | `SUPPLIER_LATE_RECEIPT`, F-032 (P3) |
| "Forecast demand for the holiday season" | Velocity is a simple moving average that ignores seasonality (BR-150..152) | Non-goal |
| "Contact the affected customers for me" | The product stores no customer contact data (BR-505) | Non-goal |
