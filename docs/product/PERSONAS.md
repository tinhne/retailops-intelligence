# Personas

> **Status:** Draft v1 (M0, T-001) · **Owner:** Product/BA · **Last updated:** 2026-10-31
> Related: [PRODUCT_VISION](PRODUCT_VISION.md) · [JOBS_TO_BE_DONE](JOBS_TO_BE_DONE.md) ·
> [FEATURE_CATALOG](FEATURE_CATALOG.md) · Permission matrix: ADR-0007 and
> `docs/workflows/ROLE_AND_PERMISSION_WORKFLOW.md` (T-010)

## About these personas

These are **proto-personas**. They are built from assumptions about how small and mid-sized e-commerce
operations teams typically work. They are **not** derived from user research, and no conversations
with operators have taken place for this project. Each persona lists the assumptions that most need
checking. Until that research happens, treat every routine, pain, and frequency below as
**Needs validation** unless it is labelled otherwise.

**Assumed context (MVP assumption).** A single-brand online store that sells physical goods through
its own storefront and one or more marketplaces. It ships from one stock location (BR-005) and uses
one currency and one time zone (BR-004). The operations team is small, so one person often holds
more than one of the roles below. In the product, each person has exactly one role per organization
(BR-002). In a very small store the owner usually holds `OWNER` and does the manager's work too.

**Names are roles.** The personas are named by role, not given invented names, so they are not
mistaken for real people. The demo store's fictional accounts (`owner@kestrel.example`,
`manager@…`, `staff@…`, `analyst@…`) map to these roles.

---

## Permission summary

The role matrix is code-defined (ADR-0007) and enforced in the backend.

| Permission | Owner | Ops Manager | Ops Staff | Analyst | Viewer (demo) |
|---|:-:|:-:|:-:|:-:|:-:|
| `dashboard.read`, `catalog.read`, `orders.read`, `inventory.read`, `exceptions.read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `imports.read`, `analytics.read`, `copilot.use`, `settings.read` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `exceptions.work` (acknowledge, claim unassigned, start, resolve own, notes) | ✓ | ✓ | ✓ | | |
| `exceptions.assign` (assign/reassign, change due date) | ✓ | ✓ | | | |
| `exceptions.manage` (dismiss, reopen, resolve any) | ✓ | ✓ | | | |
| `evaluations.run` | ✓ | ✓ | | | |
| `imports.run` | ✓ | ✓ | | | |
| `audit.read` | ✓ | ✓ | | ✓ | ✓ |
| `settings.manage`, `users.read` | ✓ | ✓ | | | |
| `users.manage` | ✓ | | | | |

### Who does what in the exception lifecycle

| Step | System | Owner | Ops Manager | Ops Staff | Analyst | Viewer |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Detect, refresh, auto-resolve, verify, supersede | ✓ | | | | | |
| Trigger "Run analysis" | | ✓ | ✓ | | | |
| Acknowledge, claim an unassigned exception | | ✓ | ✓ | ✓ | | |
| Assign / reassign, override due date | | ✓ | ✓ | | | |
| Start work, add notes | | ✓ | ✓ | ✓ (own or unassigned) | | |
| Resolve | | ✓ (any) | ✓ (any) | ✓ (own) | | |
| Dismiss, manually reopen | | ✓ | ✓ | | | |
| Read evidence, history, copilot explanations | | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## 1. Store Owner

**Snapshot.** Founded or bought the store and still makes the money decisions. Splits time between
merchandising, suppliers, marketing, and finance. Checks operations in short bursts. In a very small
store, the Owner is also the Operations Manager.

| Aspect | Description |
|---|---|
| **Goals** | Keep customer promises (ship on time, refund on time) without reading every report. Avoid paying twice for one mistake (refund plus dispute fee). Know that the team is working on the right things. Keep access to business data limited to the right people |
| **Responsibilities** | Supplier relationships and buying decisions. Pricing. Final say on refunds, customer remediation, and accepted risk. Hiring, and granting or revoking system access |
| **Daily routine** | Morning check of yesterday's orders and anything flagged as urgent (about 10 minutes). Answers escalations from the manager during the day |
| **Weekly routine** | Reviews sales and stock levels. Approves replenishment orders. Reviews refunds and cancellations. Asks "why did this happen again?" about recurring problems |
| **Pains today** | Learns about problems from customer complaints or marketplace warnings rather than from the team. Cannot tell if a "done" from the team means it is fixed. Receives monetary figures with no stated basis. Gives everyone the same storefront admin login, or has no easy way to restrict access |
| **Decisions owned** | Whether to cancel and refund or delay and contact customers for an oversold SKU. Whether to accept a risk (dismiss with `ACCEPTED_RISK`). Reorder budgets. Who gets which role. Store thresholds such as the fulfillment SLA |
| **Needs from the product** | A one-screen answer to "what is at risk right now and is someone on it?" (F-010). Exposure shown as gross value at risk, never as loss (BR-404). An immutable record of who did what (F-012). User and role management (F-016) |
| **Role in permission model** | `OWNER`: all permissions. The only role with `users.manage` |
| **Success looks like** | No CRITICAL exception without an owner. Refund-pending exceptions resolved before they become CRITICAL. Recurring problems visible in trends |
| **Key assumptions to validate** | That owners will open a separate tool daily, or would rather get a digest (F-023 is P2). That owners want to see the priority score at all, rather than only the band |

## 2. Operations Manager

**Snapshot.** Runs day-to-day operations: fulfillment, stock, returns, and the team doing them. Decides
what gets done first. The heaviest user of the product.

| Aspect | Description |
|---|---|
| **Goals** | Ship every paid order by its ship-by deadline. Never sell stock the store does not have. Keep data accurate enough to trust. Distribute work fairly and see what is stuck |
| **Responsibilities** | Triage and assignment. Replenishment triggers. Importing exports from the storefront, marketplaces, and stock counts. Tuning thresholds. Coaching staff. Escalating money decisions to the Owner |
| **Daily routine** | Start of day: pull fresh exports and import them, then triage new and reopened exceptions, assign P1/P2 work, and check overdue orders. Midday: re-run analysis after a stock count or a carrier pickup. End of day: confirm nothing CRITICAL is unowned |
| **Weekly routine** | Reviews reopen and dismissal patterns, recurring SKUs and suppliers, and import error trends. Adjusts thresholds or reorder points. Holds a short review with the Owner |
| **Pains today** | Builds the "what's wrong" list by hand from several exports. Finds oversold SKUs only when picking fails. Cannot see which paid orders are about to miss their ship-by date. Problems fixed by staff come back. CSV imports into other tools drop rows without saying which |
| **Decisions owned** | Priority order of the day. Who owns each exception and by when. Whether a finding is a false positive, a duplicate, or not actionable (dismiss). Whether to reopen. Whether to apply an import with skipped rows (valid-rows-only mode). Threshold and priority-weight settings |
| **Needs from the product** | A single queue ranked by a score whose working is visible (F-007, `PRIORITY_MODEL.md`). Fast triage: acknowledge, assign, and set the due date without leaving the queue (F-008; bulk actions are P2, F-027). An import preview that shows every error before anything changes (F-002). Verification that fixes held (F-006). Settings to tune detection (F-015) |
| **Role in permission model** | `MANAGER`: all permissions except `users.manage`. Holds `exceptions.assign`, `exceptions.manage`, `evaluations.run`, `imports.run`, `settings.manage`, `audit.read` |
| **Success looks like** | Time to acknowledge and time to resolve go down. The reopen rate is understood per rule. No import applied with unknown skipped rows |
| **Key assumptions to validate** | That managers can produce CSV exports in the required shape without engineering help. That the default SLA (48 h) and stall threshold (12 h) match their handling-time promises. That they prefer one queue over per-category tabs |

## 3. Operations Staff

**Snapshot.** Picks, packs, counts stock, processes returns, and fixes records in the storefront or
payment system. Works from a queue during a shift. Has limited time for reading reports.

| Aspect | Description |
|---|---|
| **Goals** | Know exactly what to do next and why. Finish items without going back and forth with the manager. Have their work recognised and not undone |
| **Responsibilities** | Working assigned exceptions. Physical cycle counts. Moving stuck orders into processing. Contacting carriers. Recording what was done |
| **Daily routine** | Opens "My work" at shift start. Claims unassigned items when idle. Investigates each item (evidence, affected orders), acts in the source system, and resolves it with a code and note, or keeps it `IN_PROGRESS` with a note while waiting on something external |
| **Weekly routine** | Scheduled cycle counts for fast-moving SKUs. Hands count results to the manager for import |
| **Pains today** | Instructions arrive as chat messages without context. Has to open three systems to understand one problem. Cannot tell whether a SKU's stock figure includes stock already promised to orders. Gets blamed when an issue recurs, with no record of what was done |
| **Decisions owned** | What to do inside an assigned exception (within policy). Which resolution code applies. When to escalate (add a note, leave it for the manager) |
| **Needs from the product** | A personal queue plus unassigned items (F-007). One investigation screen with evidence, calculation, affected orders, and the recommended action (F-009). A clear resolve form with codes and a required note (F-008). Plain-language explanations that cite records (F-011) |
| **Role in permission model** | `STAFF`: read permissions plus `exceptions.work` and `copilot.use`. Can acknowledge, claim **unassigned** exceptions, start work on exceptions that are unassigned or assigned to them, resolve **their own** exceptions, and add notes. Cannot assign others, dismiss, reopen, run evaluations, or import data |
| **Success looks like** | Few of their resolutions reopen with `VERIFICATION_FAILED`. Little time between claiming and resolving. Notes that the next person can act on |
| **Key assumptions to validate** | That staff use a desktop or tablet during shifts (a phone-width layout is still required, T-083). That staff do not need `imports.run` for cycle counts. Today the manager imports them; this is listed as a decision to validate in [SCOPE_AND_NON_GOALS](SCOPE_AND_NON_GOALS.md) |

## 4. Analyst

**Snapshot.** Part-time or shared role (sometimes the Owner wearing another hat, sometimes a
finance or growth person). Looks for patterns and root causes, and prepares numbers for decisions.
Does not work the queue.

| Aspect | Description |
|---|---|
| **Goals** | Explain why problems recur and what they cost in time and value at risk. Produce numbers that others can reproduce. Recommend threshold and process changes based on evidence |
| **Responsibilities** | Weekly and monthly operations reporting. Data quality investigations (totals that do not reconcile, import errors). Reviewing whether rules produce useful signals |
| **Daily routine** | Light. Checks the dashboard and data freshness. Answers ad-hoc questions ("how many orders shipped late last week?") |
| **Weekly routine** | Trends by exception type and severity. Time-to-resolve and reopen rates per rule. Top import issue codes. SKUs and suppliers that recur in inventory exceptions. Audit review when something looks wrong |
| **Pains today** | Numbers in spreadsheets cannot be traced to their inputs. Different people compute "available stock" differently. Cannot tell which rows of an import were dropped. No history of when a problem started and how long it lasted |
| **Decisions owned** | None operationally. Recommends thresholds, reorder points, and priority weights to the Manager and Owner |
| **Needs from the product** | Reproducible calculations (rule ID with version, `as_of`, inputs) (F-009). Trends and resolution metrics (F-010, F-018). Import issue history (F-002). Audit log read access (F-012). A copilot that cites the records behind every number (F-011) |
| **Role in permission model** | `ANALYST`: all read permissions plus `analytics.read`, `copilot.use`, and `audit.read`. No write permission of any kind |
| **Success looks like** | Can answer "why did this happen?" from the product alone, with references |
| **Key assumptions to validate** | That a read-only analyst role is useful in stores this size, or whether its users would rather export to their own tools (CSV export of lists is P2, F-026) |

---

## 5. Demo visitor (Viewer): an access mode, not a persona

The `VIEWER` role exists for the public demo. It is not a target user of the product, and the product
is not designed around visitors' operational goals.

| Aspect | Description |
|---|---|
| **Who** | Anyone evaluating the project: a prospective user, a reviewer, a hiring team |
| **Entry** | "Explore the demo" on the sign-in page. It signs the visitor in as a read-only `VIEWER` of the fictional organization "Kestrel Commerce" (store "Kestrel Home & Kitchen"). No registration needed (F-013) |
| **Can do** | Everything an Analyst can do: read the dashboard, inbox, investigation views, orders, inventory, imports, analytics, settings, and audit log, and use the copilot |
| **Cannot do** | Any mutation of shared data. Every write endpoint returns 403 for `VIEWER`, and the UI hides or disables actions with the reason "Read-only demo" |
| **Constraints** | All seeded data is labelled as demo data. The dataset is regenerated relative to the current time and reset by a demo reset job. Copilot requests are rate-limited (20 per minute per user) |
| **Future** | A per-visitor sandbox where visitors can run the full workflow without affecting others is a P2 roadmap item (F-022, T-095) |

Open questions about the shared viewer account (conversation privacy, shared rate limits, audit
visibility) are listed in [SCOPE_AND_NON_GOALS](SCOPE_AND_NON_GOALS.md) §5 and F-013.

---

## 6. Persona to feature map

| Feature (P0 unless noted) | Owner | Ops Manager | Ops Staff | Analyst |
|---|:-:|:-:|:-:|:-:|
| F-010 Operations overview dashboard | ●● | ●● | ● | ●● |
| F-007 Exception inbox | ● | ●●● | ●●● | ● |
| F-008 Exception lifecycle and assignment | ● | ●●● | ●●● | |
| F-009 Investigation view | ● | ●● | ●●● | ●● |
| F-002 Data imports | | ●●● | (read) | ●● |
| F-003/F-004 Inventory positions and ledger | ● | ●● | ●● | ●● |
| F-005 Orders | ● | ●● | ●● | ● |
| F-011 Copilot | ● | ●● | ●● | ●● |
| F-012 Audit log | ●● | ● | | ●● |
| F-015 Store settings (P1) | ● | ●●● | | (read) |
| F-016 User management (P1) | ●●● | (read) | | |
| F-018 Exception performance analytics (P1) | ● | ●● | | ●●● |

●●● primary daily tool · ●● regular use · ● occasional use

## 7. Validation plan for these personas

| Question | Method (planned, not yet done) |
|---|---|
| Do the four roles exist as separate people in target stores, or collapse into one or two? | Short structured conversations with operators of small online stores. Record team size and role split |
| What are the actual handling-time promises and refund practices? | Compare against each store's published shipping and refund policies and marketplace settings |
| How do teams find out about oversold SKUs and stuck orders today? | Ask for the last three occurrences and how each was discovered |
| Who imports data and how often? | Observe one week of export and import activity |
| Would staff need to import cycle counts themselves? | Ask managers who performs and records counts today |
