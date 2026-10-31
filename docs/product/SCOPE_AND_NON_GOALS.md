# Scope and Non-Goals

> **Status:** Draft v1 (M0, T-001) · **Owner:** Product/BA · **Last updated:** 2026-10-31
> Related: [FEATURE_CATALOG](FEATURE_CATALOG.md) · `docs/domain/DOMAIN_MODEL.md §3` ·
> `docs/domain/BUSINESS_RULES.md` · ADR-0005, ADR-0010, ADR-0011

Labels: **Industry practice**, **MVP assumption**, **Needs validation** (see
[PRODUCT_VISION](PRODUCT_VISION.md)).

## 1. Summary

v1 is a single-store-per-tenant operations layer. It ingests four CSV types, keeps a correct stock
ledger and order state, detects nine exception types with deterministic rules, and supports the full
exception lifecycle (triage, assignment, investigation, resolution, verification) with an audit
trail. An optional copilot explains the data through allowlisted tools. v1 observes and tracks. It
never acts in the source systems.

## 2. In scope for v1

| Capability | Included in v1 | Feature | Canonical source |
|---|---|---|---|
| Authentication and roles | Email and password, server-side sessions, CSRF protection, five fixed roles, store scoping | F-001 | ADR-0004, ADR-0007, BR-001..003 |
| Data ingestion | `products`, `orders`, `order_items`, `inventory_adjustments` CSVs with validation preview, strict and valid-rows-only modes, error CSV, templates, duplicate-file detection | F-002 | `STATE_MACHINES.md §4`, BR-601..608 |
| Inventory | Positions (on hand, reserved, available, incoming), stock health, velocity and days-of-cover estimates, append-only ledger, reservations, cycle-count cutoff | F-003, F-004 | BR-101..152, ADR-0012 |
| Orders | Three status axes, reachability-based import sync, event timeline, ship-by derivation | F-005 | `STATE_MACHINES.md §1`, BR-201..206 |
| Exception detection | 9 rules, precedence, dedup, refresh, auto-resolve, verification, reopen, supersede, priority, due date. Triggers: after import and manual "Run analysis" | F-006 | `EXCEPTION_CATALOG.md`, `PRIORITY_MODEL.md` |
| Exception work | Inbox, lifecycle actions, assignment and claim, notes, investigation view | F-007, F-008, F-009 | `STATE_MACHINES.md §3` |
| Overview | Dashboard with KPIs, attention list, inventory health, data freshness, trends | F-010 | Analytics module |
| Copilot | Q&A, exception explanation, note drafts accepted by a person; works without an LLM key | F-011 | ADR-0010 |
| Audit | Append-only audit log of security-relevant and business-changing actions, read API | F-012 | `DOMAIN_MODEL.md` (audit) |
| Demo | Seeded fictional store, read-only `VIEWER` access via "Explore the demo", demo labelling, reset | F-013 | ADR-0011 |
| P1 within v1 | Scheduled evaluation worker, store settings, user management, audit viewer, exception performance analytics, hosted public demo, copilot evaluation harness, data quality overview | F-014..F-021 | TASKS.md |

## 3. Explicit non-goals

| # | Non-goal | Why | What v1 does instead | Revisit when |
|---|---|---|---|---|
| NG-01 | **Storefront, checkout, or listing management** | Stores already have one. Competing with it is not the problem being solved | Imports storefront exports | Never (out of product scope) |
| NG-02 | **Payment processing, executing refunds, processor reconciliation, dispute handling** | Requires PCI-scope integrations and is the payment processor's job. `Payment` entity excluded (`DOMAIN_MODEL.md §3`) | Order-level `payment_status` and `paid_at`. `ORDER_REFUND_PENDING` tells a person to refund in the payment system | Partial captures or split tenders become a real need (F-035, P3) |
| NG-03 | **Carrier integrations**: label purchase, rate shopping, tracking events | Separate tooling category. `Shipment` entity excluded | Order-level `shipped_at`, `delivered_at`, `carrier`, `tracking_number` from imports | `ORDER_DELIVERY_DELAYED` is prioritised (F-033, P3) |
| NG-04 | **Multi-location inventory**: transfers, per-location allocation, 3PL split stock | Changes the oversell calculation and needs real routing rules (ADR-0005, BR-005) | One fulfillment location per store | Target users run more than one stock location (F-031, P3) |
| NG-05 | **Customer personal data**: names, addresses, emails, phone numbers | Data minimisation. No workflow in scope needs it (BR-505) | Opaque `customer_ref` such as `CUST-10492` | Never stored in v1 |
| NG-06 | **Customer communication** (emails, messages to buyers) | Needs PII (NG-05) and messaging infrastructure | Recommended actions tell the operator to contact the customer in their own tools | Not planned |
| NG-07 | **Writing back to source systems** or two-way sync | The product observes and tracks. Acting in a source system needs credentials and per-platform logic, and creates a second writer | People act in the source system; the next import verifies the result | After read connectors exist (F-025) and there is clear demand |
| NG-08 | **Live API connectors and webhooks** | CSV keeps v1 independent of any one platform and makes data contracts explicit | Four CSV contracts with templates | F-025 (P2) |
| NG-09 | **Purchase orders and supplier management** | `PurchaseOrder` excluded. Incoming quantity is enough for low-stock context | `INCOMING_EXPECTED`, `RECEIPT`, `INCOMING_CANCELLED` movements; supplier lead time | Supplier performance tracking (F-032, P3) |
| NG-10 | **Product variants and parent/child grouping** | Every rule in scope works at SKU level. `ProductVariant` excluded | Product = SKU | Catalog display needs it |
| NG-11 | **Split shipments and per-line fulfillment** | `Shipment` excluded; one shipment per order assumed | Order-level fulfillment status | F-036 (P3) |
| NG-12 | **Partial refunds and partial payments** | `payment_status` is one value per order | `REFUNDED` means fully refunded | With F-035 |
| NG-13 | **More than one currency per store, FX conversion** | BR-004 | Rows in another currency are rejected (`CURRENCY_MISMATCH`) | Multi-currency stores in the target segment |
| NG-14 | **Business-hour SLA calendars, carrier cut-off times** | BR-204 | Calendar hours | F-024 (P2) |
| NG-15 | **Demand forecasting and seasonality** | Velocity is a simple moving average, labelled as an estimate (BR-150..152) | Days of cover as an estimate | Not planned for v1 |
| NG-16 | **Autonomous AI actions** (status changes, data edits, sending messages) | Principle 1: AI explains, people act (ADR-0010) | AI drafts notes that a person accepts | Not planned |
| NG-17 | **Semantic search over documents** | No document corpus justifies it. No pgvector in v1 | Structured tools over relational data | A document corpus appears (for example SOPs) |
| NG-18 | **Notifications** (email, SMS, chat) and background jobs other than scheduled evaluation and demo reset | Needs delivery infrastructure; v1 is pull-based | Inbox, dashboard, due dates | F-023 (P2) |
| NG-19 | **Custom roles and per-store role scoping** | Code-defined matrix (ADR-0007). A membership grants access to every store in the organization (BR-002) | Five fixed roles | F-030, F-037 (P3) |
| NG-20 | **Returns management** (RMA, inspection workflow, return reasons) | Needs data v1 does not collect | `RETURNED` does not restock automatically; a `RETURN_RESTOCK` adjustment records it (BR-132) | `RETURN_RATE_SPIKE` (F-034, P3) |
| NG-21 | **Accounting, tax calculation, financial reporting** | Exposure is value at risk, not loss (BR-404). The product is not a ledger of money | BR-205 total reconciliation as a data-quality check | Not planned |
| NG-22 | **Self-service sign-up and billing** | Independent portfolio project | Accounts are created by an Owner (P1, F-016); visitors use the read-only demo | Not planned |
| NG-23 | **In-app editing of orders, products, or stock** | Data changes arrive through imports so that the source system stays authoritative | CSV imports | In-app stock adjustment form (F-029, P2) |
| NG-24 | **Native mobile apps, localisation** | Responsive web covers the use case; English UI only | Responsive web at 375 px and up | Demand from staff on the floor |

## 4. Assumptions

| ID | Assumption | Label | How it would be validated |
|---|---|---|---|
| A-01 | Target stores ship from a single stock location | MVP assumption | Ask about stock locations and 3PL use |
| A-02 | Operators can export orders, lines, products, and stock adjustments to CSV and map them to the four contracts without engineering help | Needs validation | Time a mapping exercise with real exports |
| A-03 | One payment state and one shipment per order are enough for the rules in scope | MVP assumption | Count orders with partial payments or split shipments in real exports |
| A-04 | Reserving stock at payment (not at order placement) matches how operators think about committed stock | Industry practice (BR-120); platform behaviour varies (Needs validation) | Compare with the platform's committed figure |
| A-05 | Calendar-hour SLAs are accurate enough for prioritisation | MVP assumption | Compare overdue flags with operators' own judgement |
| A-06 | Data is imported at least daily | Needs validation | Observe import frequency (M-05) |
| A-07 | File limits (5 MB, 20,000 rows) cover a daily export for the target segment | MVP assumption | Check real export sizes |
| A-08 | An opaque `customer_ref` is enough for operational work inside the product | MVP assumption | Ask what operators look up per customer |
| A-09 | Teams are small enough that per-instance rate limiting is acceptable | MVP assumption (documented limitation) | Revisit when running more than one API instance |
| A-10 | Rule-authored recommended actions are specific enough to act on | Needs validation | Ask operators to rate each action text |

## 5. Open questions

These are product questions found while writing the M0 documents. They need a decision from the
architect or orchestrator. They do not change any canonical document.

| ID | Question | Why it matters | Proposed answer |
|---|---|---|---|
| Q-01 | Is the demo `VIEWER` one shared account or one ephemeral account per visitor? | `ai_conversation` is keyed by `user_id`, so a shared account would let visitors read each other's copilot conversations. Per-user rate limits (copilot 20 per minute) would also be shared | Ephemeral per-visitor `VIEWER` user, or conversations scoped to the session |
| Q-02 | `VIEWER` holds `audit.read`, and audit entries record `ip` and request metadata | In the shared demo organization, visitors could read other visitors' IP addresses from login entries | Redact `ip` and user agent for `VIEWER` reads, or do not record visitor IPs in demo organizations |
| Q-03 | What happens when "Run analysis" is requested while a run for the store holds the advisory lock? | Users need a predictable response | Return 409 with the running run's ID; the UI shows "Analysis already running" |
| Q-04 | Does a manual due-date override survive the automatic recalculation when severity changes? | `PRIORITY_MODEL.md` says due dates are recalculated on severity change and can be overridden, but not which wins | A manual override persists until a user changes it; the recalculated value is shown alongside |
| Q-05 | When a user with `exceptions.assign` starts work on an exception assigned to someone else, does the assignee change? | `STATE_MACHINES.md §3.2` only covers the unassigned case | The assignee is unchanged unless the user reassigns explicitly |
| Q-06 | Must an assignee hold `exceptions.work`? | Assigning to an `ANALYST` creates an exception nobody assigned can work | Yes; reject with 422 otherwise |
| Q-07 | Should verification wait for fresh data? | A scheduled run that follows a manual resolution, but precedes the import that contains the fix, reopens the exception as `VERIFICATION_FAILED` even though the fix was made | Keep the canonical rule for v1, and show in the resolve dialog when the relevant data was last imported. Revisit with M-13 data |
| Q-08 | Where is ledger drift from the reconciliation check (BR-104) shown? | Drift is a defect that must be visible, not silently fixed | Show it on the evaluation run record and as a dashboard banner for Owner and Manager |
| Q-09 | When `on_hand < 0`, both `DATA_NEGATIVE_ON_HAND` and `INVENTORY_OVERSOLD` fire (because `available = on_hand − reserved < 0`), and an oversold finding with `reserved = 0` has no affected orders | One root cause produces two exceptions, including a `CRITICAL` with zero exposure | Suppress `INVENTORY_OVERSOLD` when `reserved = 0`, or link the two exceptions |
| Q-10 | Can lines be inserted for an order first imported in `SHIPPED` or a later status? | `ORDER_LINE_LOCKED` blocks line changes on shipped orders. If that includes inserts, such an order can never get its lines | Allow inserting lines for an order that has none; block changes to existing lines |
| Q-11 | How should the dashboard total exposure across exceptions? | One order can be counted in an oversold exception and an overdue exception at once | Show exposure per category with no grand total, plus a count of distinct orders at risk |
| Q-12 | Should the scheduled evaluation worker (T-055, P1) be P0? | Without it, stalled, overdue, and refund-pending exceptions only appear when someone imports or runs analysis | Promote to P0, or make the dashboard show "last evaluation" prominently |
| Q-13 | If the LLM provider fails or times out, does that answer fall back to the deterministic adapter? | The product must stay usable without an LLM | Yes, with `generated_by: "deterministic"` and a limitation line |

## 6. Decisions that need validation with real users

| ID | v1 decision | Current default | Risk if wrong | How to validate |
|---|---|---|---|---|
| D-01 | Fulfillment SLA when no ship-by is imported | `fulfillment_sla_hours = 48` | Noise (too short) or late warnings (too long) | Compare with published handling times |
| D-02 | Stall threshold after payment | `stall_threshold_hours = 12` | Stalled exceptions for orders that are fine overnight | Observe when orders normally enter processing |
| D-03 | Refund overdue threshold | `refund_overdue_hours = 24` | Too strict for weekend cancellations, or too lax | Compare with stated refund turnaround |
| D-04 | Reopen window for recurrences | `reopen_window_hours = 72` | Recurrences split into new exceptions, or old ones reopened | Look at recurrence patterns (M-13, M-14) |
| D-05 | Priority weights and bands | S 50, A 15, E 15, D 12, T 8; P1 ≥ 70 | Wrong work order | Ask managers to rank a sample, then compare with the score |
| D-06 | Response windows behind `due_at` | CRITICAL 4 h, HIGH 24 h, MEDIUM 72 h, LOW 168 h | Due dates nobody can meet, or that never matter | Compare with how fast teams actually respond |
| D-07 | Oversold allocation order | FIFO by `paid_at` (BR-402) | Teams may fulfil by ship-by or by channel instead | Ask how they choose which orders to short |
| D-08 | Strict import mode as the default | `STRICT` | Friction if most files have a few bad rows | M-23 and feedback |
| D-09 | Staff cannot import (including cycle counts) or run analysis | Not in the `STAFF` role | Staff wait for a manager to import counts | Ask who performs and records counts |
| D-10 | `APPROACHING_REORDER_POINT` is a badge, not an exception | Factor 1.25 | Early warnings missed | Ask whether this should reach the queue |
| D-11 | Dismissed exceptions stay dismissed while the condition persists | `STATE_MACHINES.md §3.3` | A dismissed condition that worsens goes unnoticed | Watch whether managers manually reopen dismissed items |
| D-12 | One queue across all categories | Single inbox sorted by priority | Managers may want category queues | Observe filter use |
| D-13 | Public demo visitors can use the copilot | `VIEWER` has `copilot.use` | Cost and abuse with an LLM key | Use the deterministic provider for the public demo unless the owner approves otherwise |

## 7. Risks

Likelihood and impact are qualitative judgements. All are **Needs validation**.

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-01 | **Stale data.** Detection is only as fresh as the last import, which causes false positives (fixed in the source but not yet imported) and false negatives | High | High: users stop trusting the queue | Data freshness per import type on the dashboard (M-05); "data as of" on every exception; last-import hint in the resolve dialog (Q-07) |
| R-02 | **Time-based rules without the scheduler.** Until F-014 ships, stalled, overdue, and refund-pending exceptions only advance when someone imports or runs analysis | High until F-014 | Medium | Prioritise T-055 (Q-12); show the last evaluation time |
| R-03 | **Alert fatigue** from defaults that do not fit a store | Medium | High | Dedup, precedence, supersede, dismissal semantics; per-rule dismissal metrics (M-16); tunable thresholds (F-015) |
| R-04 | **Exposure read as loss** | Medium | Medium: wrong financial decisions | BR-404 wording everywhere; tooltip; copilot rule; invariant I-8 |
| R-05 | **LLM overstates or invents** | Medium | High | Allowlisted tools, structured answers with refs, deterministic fallback, evaluation dataset (T-074), AI never writes |
| R-06 | **CSV mapping burden** prevents adoption | Medium | High | Templates, precise issue codes, downloadable error CSV; connectors as F-025 (P2) |
| R-07 | **Single-location assumption broken** by stores with a 3PL plus their own stock | Medium | High: wrong oversell figures | Stated as a non-goal (NG-04, ADR-0005) |
| R-08 | **Reopen loops** for conditions that take days to clear (for example an overdue order resolved as `CUSTOMER_CONTACTED`) | Medium | Medium: staff frustration | Guidance to keep work `IN_PROGRESS` with a note (`STATE_MACHINES.md §3.4`); the resolve dialog shows whether the condition is still present; M-13 by reason |
| R-09 | **Overlapping detections** for one root cause (Q-09) | Medium | Low–Medium | Decide Q-09 before T-053 |
| R-10 | **Public demo abuse**: copilot cost, shared rate limits, shared conversations | Medium | Medium | Rate limits; deterministic provider for the public demo (D-13); Q-01 |
| R-11 | **Privacy leak through the audit log** in the shared demo (Q-02) | Medium | Medium | Decide Q-02 before T-094 |
| R-12 | **Rate limits per instance** do not hold when scaled out | Low in v1 | Low | Documented limitation; shared store (for example Redis) when scaling |
| R-13 | **Demo data presented as real results** | Low | High: credibility | Demo label on every screen; metrics exclude `is_demo` organizations; no demo figures in claims |
| R-14 | **Unvalidated priority weights** rank work badly | Medium | Medium | Breakdown shown on every exception; weights tunable; limitations stated (`PRIORITY_MODEL.md`) |
| R-15 | **Time-zone and DST errors** in SLA arithmetic (America/New_York leaves daylight time on 2026-11-01) | Medium | Medium | UTC storage, explicit `as_of` (BR-504), display in store zone (BR-501), tests that cross a DST change |
