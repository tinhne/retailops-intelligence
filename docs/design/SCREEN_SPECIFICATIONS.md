# Screen Specifications

> **Status:** v1 design specification (task T-030, milestone M3).
> Read with `INFORMATION_ARCHITECTURE.md` (routes, permissions), `DESIGN_SYSTEM.md` (tokens,
> formatting) and `COMPONENT_INVENTORY.md` (components). Field names come from
> `docs/domain/DOMAIN_MODEL.md`. Computed values cite their rule (BR-xxx).

Example values describe the shape of the seeded demo store, **Kestrel Home & Kitchen** (USD,
America/New_York). They are illustrations for engineers, not product data, and are never
hard-coded (AGENTS.md §11).

## Screen index

| ID | Screen | Route | P | Wireframe |
|---|---|---|---|---|
| S-00 | App shell and global states | all `/s/{storeId}/…` | P0 | §0.2 |
| S-01 | Login and demo entry | `/login`, `/demo` | P0 | |
| S-02 | Overview | `/overview` | P0 | **yes** |
| S-03 | Exceptions inbox | `/exceptions` | P0 | **yes** |
| S-04 | Exception detail / investigation | `/exceptions/{id}` | P0 | **yes** |
| S-05 | Orders list | `/orders` | P0 | |
| S-06 | Order detail | `/orders/{id}` | P0 | |
| S-07 | Products list | `/products` | P0 | |
| S-08 | Product detail | `/products/{id}` | P0 | |
| S-09 | Inventory positions | `/inventory` | P0 | |
| S-10 | Movements ledger | `/inventory/movements` | P0 | |
| S-11 | Imports list | `/imports` | P0 | |
| S-12 | New import wizard (upload → preview → apply → summary) | `/imports/new` → `/imports/{id}` | P0 | **yes** |
| S-13 | Import detail with issues | `/imports/{id}` | P0 | |
| S-14 | Copilot | `/copilot`, `/copilot/{id}` | P0 | |
| S-15 | Audit log | `/admin/audit-log` | P0 | |
| S-16 | Settings | `/admin/settings` | P0 | |
| S-17 | Users & roles | `/admin/users` | P0 | |
| S-20 | Analytics | `/analytics` | P1 | |
| S-21 | Evaluation runs | `/evaluation-runs` | P1 | |
| S-22 | Data quality | `/data-quality` | P1 | |

---

## 0. Conventions that apply to every screen

### 0.1 How to read a screen spec

Each screen lists: **Purpose**, **Primary persona**, **Layout** (regions, top to bottom),
**Data** (field → source), **Actions** (with permission and disabled reason), **Filters / sort /
search**, **Pagination**, and **States**. A state marked *Standard* behaves exactly as described
in §0.3. Only screen-specific copy and deviations are written out.

Data source notation: `entity.field` is a stored field from DOMAIN_MODEL.md (`operational_exception.priority_score`).
`computed:` marks a value the API computes on read (`computed: available` per BR-101). The UI
never computes business values itself. It formats what the API returns.

### 0.2 App shell (S-00)

```text
+--------------------------------------------------------------------------------------------+
| [DEMO DATA] Fictional store, generated records, read-only viewer.  Take the tour  Leave demo |
+------------------+-------------------------------------------------------------------------+
| RetailOps        | Exceptions / EXC-9B1C4E2A           [Search…  Ctrl K]  [Copilot]  (DV)  |
| Kestrel Home &   +-------------------------------------------------------------------------+
|   Kitchen        |                                                                         |
| USD · Times in ET|   PageHeader: title, subtitle, primary actions                          |
|                  |   ------------------------------------------------------------------    |
|   Overview       |   Page content (max 1440 px, gutter 16/24/32 px)                        |
| OPERATIONS       |                                                                         |
| > Exceptions   5 |                                                                         |
| COMMERCE         |                                                                         |
|   Orders         |                                                                         |
|   Products       |                                                                         |
|   Inventory      |                                                                         |
|   Movements      |                                                                         |
| INTELLIGENCE     |                                                                         |
|   Copilot        |                                                                         |
| DATA             |                                                                         |
|   Imports        |                                                                         |
| ADMINISTRATION   |                                                                         |
|   Settings       |                                                                         |
|   Audit log      |                                                                         |
| [<< Collapse]    |                                                                         |
+------------------+-------------------------------------------------------------------------+
```

- The demo banner renders only when `organization.is_demo`. The store label has no dropdown
  chevron when the user has exactly one store (IA §7).
- Below 768 px: the banner shows one line ("Demo data · read-only" + **Tour**). The top bar holds
  the menu button, store name, search icon and avatar. The sidebar becomes a drawer.
- "Skip to content" link first in tab order. `<main id="content">` wraps page content.

**Global states (shell level)**

| State | Trigger | Behaviour |
|---|---|---|
| Session expired | Any request returns 401 | Clear the query cache, then redirect to `/login?next={current path}&reason=expired`. Unsaved form input is not preserved (stated in the login alert). |
| Store not accessible | `storeId` not in `/me` memberships, or the API returns 404 for the store | Full-page NotFound: "This store doesn't exist or you don't have access to it." Button: "Go to my stores" (`/`). |
| Route permission missing | Route permission not in `permissions` | `PermissionDenied` inside the shell (§0.3). |
| Record not found | Detail endpoint returns 404 | `NotFoundState` inside the shell: "This {exception/order/product/import} doesn't exist or belongs to another store." Link back to the list. |
| Offline | `navigator.onLine === false` | Neutral banner below the top bar: "You're offline. Data shown may be out of date." Mutations are `aria-disabled` with "You're offline." |
| Unhandled render error | React error boundary (`error.tsx`) | `ErrorState` (full page): "Something went wrong displaying this page." **Reload page**, plus the `request_id` of the last failed request if any. |
| Server unavailable | 502/503/504 | Treated as an API error with retry (§0.3). The message is "The service is temporarily unavailable." |

### 0.3 Standard states

| State | Standard behaviour |
|---|---|
| **Initial loading** | Shown only when there is no cached data. The PageHeader title renders immediately (static text). Data regions render skeletons that match the final layout: table skeleton with 8 rows at the table's density, KPI skeleton blocks, detail section skeletons (title bar + 3 text lines). `aria-busy="true"` on the region. A visually hidden live region announces "Loading {page}". Each independent region loads and fails independently. |
| **Background refetch** | Data stays visible. No skeleton. Lists use `keepPreviousData` while paging (rows at 60% opacity). |
| **Empty** | No records exist and no filter or search is applied. `EmptyState`: 24 px icon in a 40 px muted circle, a title (what is missing), one sentence (why and what fills it), and at most one primary action, shown only if the user has the permission for it. |
| **Populated** | The normal view. |
| **Search results** | `q` is set. The result count reads "14 results for "KHK-104"". The matching substring in the primary cell is wrapped in `<mark>` (bg `--surface-selected`, no colour change). A clear (×) button sits in the input. |
| **Filtered / no results** | Filters or search return 0 rows. `EmptyState` variant `no-results`: "No {items} match these filters", the active filters listed as chips, and **Clear filters**. The table header stays visible. |
| **Validation error** | Forms: field errors plus a form-level alert (DESIGN_SYSTEM §14). Invalid URL parameters (an unknown enum in `?severity=`) are dropped, the URL is normalised with `router.replace`, and an info toast reads "Some filters in the link weren't recognised and were removed." |
| **API error with retry** | `ErrorState` in the failed region: title "Couldn't load {items}", the message from `error.message` (for 5xx: "Something went wrong on our side."), `request_id` in mono with a copy button, and **Try again** (refetch). Queries retry automatically twice (1 s, 3 s) for network and 5xx errors only, never for 4xx. |
| **Rate limited (429)** | Inline warning with a countdown from `Retry-After`: "Too many requests. Try again in 34 s." The triggering control is `aria-disabled` until the countdown ends. |
| **Conflict (409)** | For mutations: the dialog or form stays open with input kept. A warning alert shows the API message (for example `EXCEPTION_TRANSITION_NOT_ALLOWED`: "This exception is already Resolved.") or the stale-version message: "This exception changed while you were working. Review the latest details, then try again." Button **Reload latest** refetches the record and closes the alert. |
| **Permission denied** | `PermissionDenied`: `lock` icon, "You don't have access to {page}", "This page requires the {Permission label} permission. Your role: {Role}." For demo orgs: "This area isn't part of the read-only demo." No retry button. A 403 from a mutation shows an error toast with the same text. |
| **Success toast** | Sonner, bottom-right (bottom-centre below 640 px), 5 s, `role="status"`. Pattern: "{Object} {past-tense verb}" plus an optional single action ("Exception resolved" · **Next in queue**). Errors that need action are inline, not toasts. Toasts only confirm. |
| **Pending action** | The triggering button shows its pending state (spinner, present participle, locked width, `aria-busy`). Other actions on the same record are `aria-disabled` ("Another action is in progress."). Long operations (analysis, import validation and apply) show a status line with elapsed time instead. |
| **Confirmation dialog** | `ConfirmDialog` (Radix AlertDialog). Required for actions that end tracking, change many records or change configuration (listed per screen). The title names the action and object. The body states the consequence. The confirm button repeats the verb. Initial focus goes to **Cancel**. Escape cancels. |
| **Disabled action** | `aria-disabled="true"`, a tooltip and an `aria-describedby` reason (copy in IA §5). Never hidden when the user can see the object. Hidden only when the whole area is unavailable (navigation). |
| **Responsive** | Per DESIGN_SYSTEM §8 and §11.5. Screen-specific notes are listed per screen. |

### 0.4 Data contract assumptions (proposed)

The API reference is owned by the architect (T-022) and the backend (T-04x/T-05x). The UI needs
the following resources. Names follow the brief's conventions (`/api/v1`, store-scoped paths,
list envelope `{items, page, page_size, total}`, `sort=±field`). Shapes marked **proposed** must
be confirmed when `packages/contracts` is generated.

| Resource | Endpoint (proposed) | Used by |
|---|---|---|
| Current user | `GET /api/v1/me` → `{user{id,email,full_name}, memberships[{organization{id,name,slug,is_demo}, role, permissions[], stores[{id,name,code,currency,timezone}]}]}` | Shell, guards |
| Auth | `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `POST /api/v1/auth/demo` | S-01 |
| Dashboard summary | `GET /stores/{id}/analytics/summary` (**proposed shape** in S-02 Data) | S-02, sidebar badge |
| Fulfilment series | `GET /stores/{id}/analytics/fulfillment?from&to&granularity=day` | S-02, S-20 |
| Trends | `GET /stores/{id}/analytics/trends?metric&from&to&granularity` | S-20 |
| Exceptions | `GET /stores/{id}/exceptions`, `GET …/exceptions/{eid}`, `GET …/{eid}/events`, `GET\|POST …/{eid}/notes` | S-02, S-03, S-04 |
| Exception commands | `POST …/{eid}/acknowledge \| start \| claim \| resolve \| dismiss \| reopen`, `PUT …/{eid}/assignee`, `PUT …/{eid}/due-date`. All accept `expected_version`. | S-04 |
| Assignable users | `GET /stores/{id}/assignable-users` → members whose role has `exceptions.work` (`id`, `full_name`, `role`). Readable with `exceptions.read`, because the assignee filter needs it. | S-03, S-04 |
| Evaluation runs | `GET\|POST /stores/{id}/evaluation-runs`, `GET …/evaluation-runs/{rid}` (POST accepts `Idempotency-Key`) | S-02, S-03, S-21 |
| Orders | `GET /stores/{id}/orders`, `GET …/orders/{oid}` (includes `items[]`, `events[]`, `computed: expected_total`, `computed: is_overdue`, `computed: hours_overdue`) | S-05, S-06 |
| Products | `GET /stores/{id}/products`, `GET …/products/{pid}`, `GET /stores/{id}/products/categories`, `GET /stores/{id}/suppliers` | S-07, S-08 |
| Inventory | `GET /stores/{id}/inventory/positions`, `GET …/inventory/positions/{pid}`, `GET …/inventory/movements`, `GET …/inventory/reservations?product_id&status=ACTIVE` | S-08, S-09, S-10 |
| Imports | `POST /stores/{id}/imports` (multipart `import_type`, `file`), `GET …/imports`, `GET …/imports/{iid}`, `GET …/{iid}/issues`, `GET …/{iid}/issues.csv`, `POST …/{iid}/apply {mode, confirm_skipped_rows}` (`Idempotency-Key`), `POST …/{iid}/discard`, `POST …/{iid}/retry`, `GET /stores/{id}/import-templates/{import_type}.csv` | S-11, S-12, S-13 |
| Copilot | `GET\|POST /stores/{id}/ai/conversations`, `GET …/ai/conversations/{cid}`, `POST …/{cid}/messages`, `POST /stores/{id}/exceptions/{eid}/ai/investigation`, `POST …/exceptions/{eid}/ai/note-draft` | S-04, S-14 |
| Settings | `GET\|PUT /stores/{id}/settings` | S-16 |
| Members | `GET /organizations/{org_id}/members`, `PATCH /organizations/{org_id}/members/{membership_id} {role}` | S-17 |
| Role matrix | `GET /api/v1/roles` → `[{role, permissions[]}]` plus permission labels and descriptions, served from the code-defined matrix (ADR-0007), so the UI never duplicates it | S-17, `PermissionGate` copy |
| Audit | `GET /organizations/{org_id}/audit-logs?store_id&action&actor_id&target_type&from&to` | S-15 |

**Proposed JSON shapes the investigation UI depends on** (stored as JSONB on
`operational_exception`; the UI renders them generically, so every rule uses one renderer):

```ts
// operational_exception.priority_breakdown
type PriorityBreakdown = {
  components: Array<{ key: "S" | "A" | "E" | "D" | "T"; label: string; input: string; points: number; max: number }>;
  total: number; band: "P1" | "P2" | "P3" | "P4";
  due: { due_at: string; basis: "SEVERITY_RESPONSE" | "BUSINESS_DEADLINE" | "MANUAL_OVERRIDE"; response_hours?: number };
};
// operational_exception.calculation
type Calculation = {
  rule_id: string; as_of: string;
  condition: { expression: string; result: boolean };          // "available < 0"
  steps: Array<{ label: string; expression: string; substituted: string;
                 result: string; result_type: "quantity" | "money" | "hours" | "ratio" | "text" }>;
};
// operational_exception.evidence[]
type EvidenceItem = {
  key: string; label: string; value: string;
  value_type: "quantity" | "money" | "datetime" | "hours" | "text";
  is_estimate?: boolean;                                         // BR-152
  source: { type: "inventory_balance" | "product" | "order" | "inventory_movement" | "data_import" | "calculated";
            id?: string; label: string };
};
```

---

## S-01 Login and demo entry

**Purpose.** Authenticate workspace users, and give public visitors a one-click read-only demo
that is clearly labelled as such. **Persona.** All users. Public visitor for `/demo`.

**Layout (`/login`).** Centred column, max 400 px, on `--background`.
1. Wordmark "RetailOps Intelligence" (`text-title-lg`) and tagline "Turn operational chaos into
   clear decisions." (`--muted-foreground`).
2. Card **Sign in**: Email (`type=email`, `autocomplete=username`), Password
   (`autocomplete=current-password`, with a show/hide toggle button using `aria-pressed`), and a
   full-width primary **Sign in** button.
3. Divider "or".
4. Card **Explore the demo**: "See a fictional store with generated data. Read-only, no sign-up."
   Full-width secondary button **Explore the demo**.
5. Footer (`text-xs`, muted): "An independent portfolio project by Lê Văn Trung Tính ·
   trungtinh.site".

No "Forgot password" and no "Sign up": neither exists in v1 (IA-5).

**Layout (`/demo`).** Same column. Title "Explore the RetailOps Intelligence demo". A definition
list: Store "Kestrel Home & Kitchen (fictional)", Data "About 120 products, about 1,500 orders over
the last 60 days, 8 suppliers, every exception type", Access "Read-only viewer: you can explore
and ask the copilot, but not change data", Freshness "Generated relative to today and reset
periodically". Primary **Start the demo**. Link "Sign in with a workspace account".

**Data.** `POST /auth/login {email, password}` then `GET /me`. `POST /auth/demo` creates a
`VIEWER` session in the demo organization. Redirect: `next` (same-origin paths only, otherwise
`/`). For demo: `/s/{demoStoreId}/overview?tour=1`.

**Actions.** Sign in (public). Explore / Start the demo (public).

| State | Behaviour |
|---|---|
| Initial loading | If a session cookie exists, `GET /me` runs first. While pending, only the wordmark shows (no form flash). Success redirects to `/`. |
| Empty / populated / search / filtered | N/A (form page). |
| Validation error | Email: required, valid format ("Enter an email address like name@company.com"). Password: required. No password-policy hints on login. |
| API error with retry | 401 → danger alert above the form: "Email or password is incorrect." (never says which). 5xx → "Sign-in is unavailable right now. Try again in a moment." plus `request_id`. The form keeps the email and clears the password. |
| Rate limited | 429 → "Too many sign-in attempts. Try again in 60 s." (from `Retry-After`). The Sign in button is `aria-disabled` with a countdown. |
| Session expired | `?reason=expired` → info alert: "Your session expired. Sign in again to continue. Unsaved changes were not kept." |
| Signed out | `?reason=signed_out` → info alert "You've signed out." |
| Demo unavailable | `/auth/demo` fails → danger alert in the demo card: "The demo is temporarily unavailable. Try again in a few minutes." |
| Pending action | "Signing in…" / "Starting demo…". Both buttons are disabled while either request is in flight. |
| Permission denied | N/A. A deactivated account receives the same generic 401 message unless the API returns a distinct code. |
| Success toast | None. The redirect is the success. |
| Confirmation dialog / disabled | N/A. |
| Responsive | At 360 px: cards are full width with a 16 px gutter. Inputs use 16 px text. |

---

## S-02 Overview

**Purpose.** Answer three questions on one screen: what needs attention now, is someone on it,
and is the data current? **Personas.** Store Owner (primary), Operations Manager.

### Wireframe (≥ 1280 px, content area)

```text
Overview                                                                    [Run analysis]
Last evaluation 9:45 AM EDT · Scheduled · 2 new · 5 refreshed · 1 resolved · 0 reopened
Last imports: Orders Oct 31, 8:02 AM EDT · Inventory adjustments Oct 30, 6:15 PM EDT

+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+
| Active      | | Unassigned  | | Overdue     | | Value at    | | Refunds     | | On-time     |
| exceptions  | | P1–P2       | | orders      | | risk (gross)| | pending     | | ships, 7 d  |
| 23          | | 3           | | 7           | | $4,812.40   | | 3           | | 91.4%       |
| 5 P1 · 9 P2 | |             | | oldest 3d 4h| | 11 exc.     | | $412.60 owed| | ↓ 2.1 pp    |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+

+------------------------------------------------------------+ +----------------------------+
| Needs attention                       Open triage queue (7) | | Active by category         |
|------------------------------------------------------------| | Inventory        9  ▇▇▇▇▇▇ |
| ▮▮▮▮ P1 81 [■ Critical] Oversold: Enamel Dutch Oven 5.5 qt… | | Fulfillment      8  ▇▇▇▇▇  |
|            KHK-DO55-SGE · 4 orders · Due in 3h 55m · Unassg | | Payment          3  ▇▇     |
| ▮▮▮▮ P1 79 [■ Critical] Fulfillment overdue: KHK-10391      | | Data quality     3  ▇▇     |
|            Order 3d 4h past ship-by · Dana Whitfield        | +----------------------------+
| ▮▮▮▯ P2 60 [▲ High]     Fulfillment overdue: KHK-10482      | | Stock health (active SKUs) |
|            Order 30h past ship-by · Sam Ortiz               | | Oversold                 2 |
| …  8 rows                                                  | | Out of stock             4 |
|                                       View all active (23) | | Below reorder point     11 |
+------------------------------------------------------------+ | Approaching reorder pt.  7 |
                                                               | Healthy                 96 |
                                                               +----------------------------+
+------------------------------------------------------------------------------------------+
| Shipments per day, on time vs late, last 30 days (ET)                     [Chart | Table] |
|   ▇ On time  ▇ Late                                                                       |
|   (stacked columns, one per store-local day)                                              |
+------------------------------------------------------------------------------------------+
+------------------------------------------------------------------------------------------+
| Recent imports                                                          View all imports |
| orders_2026-10-31.csv          Orders                [✓ Completed]  1,240 rows  8:02 AM   |
| adjustments_2026-10-30.csv     Inventory adjustments [✓ Completed]     86 rows  Oct 30    |
+------------------------------------------------------------------------------------------+
```

### Layout
1. **PageHeader**: "Overview". Subtitle: today's date in the store zone ("Saturday, Oct 31, 2026").
   Action: **Run analysis**.
2. **Freshness strip** (`text-sm`, muted, two lines): last evaluation run (time, trigger, counts)
   and the latest completed import per type. If the last run failed: a warning tone line, "The last
   evaluation failed at 9:45 AM EDT. Exceptions may be out of date.", with a link to the run (P1)
   or the request ID (P0). If the latest orders import is more than 24 h old: "Order data was last
   imported 2 days ago. Figures may be out of date." (warning tone, text and icon).
3. **KPI row**: 6 `KpiCard`s. Grid: 6 columns ≥ 1280, 3 columns 768–1279, 2 columns < 768. Each
   card is a link to the filtered list behind it.
4. **Main grid** (≥ 1280: 2/3 + 1/3. Below: stacked). Left: **Needs attention**. Right: **Active
   by category**, **Stock health**.
5. **Shipments per day** chart (full width).
6. **Recent imports** (last 3).

### Data

| UI element | Source |
|---|---|
| Freshness: last evaluation | `summary.last_evaluation_run` → `evaluation_run.{trigger, as_of, finished_at, status, counts}` |
| Freshness: last imports | `summary.last_import_by_type[]` → `data_import.{import_type, applied_at, status}` |
| Active exceptions | `summary.active_exceptions_total`, `summary.active_by_band.{P1,P2}` |
| Unassigned P1–P2 | `summary.unassigned_by_band.{P1,P2}` (summed) |
| Overdue orders | `summary.overdue_orders_count`, `summary.oldest_overdue_hours` (BR-202) |
| Value at risk (gross) | `summary.value_at_risk_total` = Σ `operational_exception.exposure_amount` over active exceptions, `summary.value_at_risk_exception_count`. Tooltip: "Gross order-line value at risk across active exceptions. An order can count under more than one exception. This is not a measure of loss (BR-404)." |
| Refunds pending | `summary.refunds_pending_count`, `summary.refunds_pending_amount` (active `ORDER_REFUND_PENDING`, BR-206) |
| On-time shipments, 7 d | `summary.on_time_ship_rate_7d`, `summary.on_time_ship_rate_prev_7d`. Definition: orders with `shipped_at` in the window and `shipped_at ≤ ship_by`, divided by all orders with `shipped_at` in the window. Delta in pp. |
| Needs attention | `GET exceptions?status=OPEN,ACKNOWLEDGED,IN_PROGRESS,REOPENED&sort=-priority_score,due_at&page_size=8` → `priority_band, priority_score, severity, title, primary_entity.label, affected_order_count, due_at, assignee.full_name, status` |
| Triage count | `GET exceptions?status=OPEN,REOPENED&page_size=1` → `total` |
| Active by category | `summary.active_by_category.{INVENTORY, FULFILLMENT, PAYMENT, DATA_QUALITY}` |
| Stock health | `summary.stock_health_counts.{OVERSOLD, OUT_OF_STOCK, BELOW_REORDER_POINT, APPROACHING_REORDER_POINT, HEALTHY}` (ACTIVE products, BR-141) |
| Shipments chart | `GET analytics/fulfillment?from={today−29d}&to={today}&granularity=day` → `[{date, shipped_on_time, shipped_late}]` (store-local days) |
| Recent imports | `GET imports?sort=-created_at&page_size=3` |

### Actions

| Action | Permission | Disabled reason |
|---|---|---|
| Run analysis | `evaluations.run` | Missing: "You need the Run analysis permission. Ask an owner or manager." Demo: "The public demo is read-only." While a run is in progress: "An analysis is already running." |
| KPI card links, list rows, category rows, health rows | the target route's permission | Without it, the card renders as plain text (not a link) |

**KPI links:** Active → `/exceptions?view=active`. Unassigned → `/exceptions?view=unassigned&priority_band=P1,P2`.
Overdue → `/orders?overdue=true&sort=ship_by`. Value at risk → `/exceptions?view=active&sort=-exposure_amount`.
Refunds → `/exceptions?view=active&exception_type=ORDER_REFUND_PENDING`. On-time → `/orders?overdue=true`.
Category row → `/exceptions?view=active&category={CATEGORY}`. Health row → `/inventory?health={HEALTH}`.

**Filters / sort / search / pagination.** None on this page (fixed windows). Global search is in
the top bar.

| State | Behaviour |
|---|---|
| Initial loading | Standard. 6 KPI skeletons, 8-row list skeleton, 2 side-card skeletons, a chart block (240 px). |
| Empty (no data ever imported) | KPI row and grid are replaced by one `EmptyState`: "No data yet". "Import products, orders and inventory adjustments to start detecting exceptions." Action **Start an import** (`imports.run`). Otherwise: "Ask an owner or manager to import data." Secondary link: **Download CSV templates**. |
| Empty (data, no active exceptions) | Needs attention shows a success-tone EmptyState: "Nothing needs attention", "The last evaluation at 9:45 AM EDT found no active exceptions." |
| Populated | As wireframed. |
| Search / filtered | N/A. |
| Validation error | N/A. |
| API error with retry | Per region. The KPI row fails as one unit (single summary call). |
| Permission denied | Standard (all roles hold `dashboard.read`). Regions whose permission is missing (for example `imports.read` for Recent imports) are omitted. |
| Pending action | **Run analysis** → "Running analysis…". `POST evaluation-runs` with an `Idempotency-Key`. While `status = RUNNING`, poll `GET evaluation-runs/{rid}` every 2 s. The freshness strip shows "Analysis running · started 9:52 AM EDT". |
| Success toast | "Analysis complete: 2 new, 5 refreshed, 1 resolved, 0 reopened" · **View exceptions**. Then refetch summary and lists. |
| Run conflict | 409 → info toast "An analysis is already running for this store. Results will appear when it finishes." The UI polls the running run. |
| Run failure | Run `status = FAILED` → error toast "Analysis failed. No exceptions were changed." with `request_id`. The freshness strip shows the warning line. |
| Confirmation dialog | None (manual evaluation is idempotent and changes no business data). |
| Disabled action | Run analysis per the table above. |
| Responsive | < 768: KPIs in 2 columns. Needs attention uses stacked rows. Side cards stack below. The chart is 200 px high with 7-day labels. |

---

## S-03 Exceptions inbox

**Purpose.** The work queue: see, filter and pick the next exception to handle, in priority
order. **Personas.** Operations Manager (triage), Operations Staff ("Assigned to me").

### Wireframe (≥ 1280 px, content area)

```text
Exceptions                                     Last evaluation 9:45 AM EDT (5m ago)  [Run analysis]
[All active 23]  [Triage 7]  [Assigned to me 2]  [Unassigned]  [Closed]
+------------------------------------------------------------------------------------------------+
| [Q Search title or EXC-…      ] [Severity ▾] [Priority ▾] [Status ▾] [Category ▾] [Type ▾]     |
| [Assignee ▾] [Due ▾]                                 Sort [Priority ▾]  Density [≡]  23 results |
| Severity: Critical, High  ×    Clear all                                                        |
|------------------------------------------------------------------------------------------------|
| Priority    Exception                                Severity     Status       At risk  Assignee   Due          |
|------------------------------------------------------------------------------------------------|
| ▮▮▮▮ P1 81  Oversold: Enamel Dutch Oven 5.5 qt, Sage  [■ Critical] [○ Open]     $600.00 Unassigned Due in 3h 55m |
|             Oversold · KHK-DO55-SGE · 4 orders · EXC-9B1C4E2A                                   |
| ▮▮▮▮ P1 79  Fulfillment overdue: KHK-10391            [■ Critical] [◉ In progress] $96.00 Dana W.  Overdue 3d |
|             Fulfillment overdue · KHK-10391 · 1 order · EXC-31D07B55                            |
| ▮▮▮▯ P2 60  Fulfillment overdue: KHK-10482            [▲ High]     [◎ Acknowl.] $120.00 Sam O.    Overdue 6h |
| ▮▮▯▯ P3 41  Below reorder point: Linen Tea Towel, Grey [▲ High]    [↺ Reopened]   —      Sam O.    Overdue 2d |
| …                                                                                              |
|------------------------------------------------------------------------------------------------|
| 1–25 of 23                                       Rows per page [25 ▾]   ‹ Previous  Page 1 of 1  Next › |
+------------------------------------------------------------------------------------------------+
```

### Layout
1. **PageHeader**: "Exceptions". Meta: "Last evaluation 9:45 AM EDT (5m ago)". Action: **Run analysis**.
2. **View tabs** (links, `?view=`): All active · Triage · Assigned to me · Unassigned · Closed.
   Counts are shown on Triage and Assigned to me only (actionable).
3. **Card with FilterBar + DataTable + Pagination.**

**Views**

| View (`view=`) | Filter | Default sort | Shown to | Default for |
|---|---|---|---|---|
| `active` | status ∈ OPEN, ACKNOWLEDGED, IN_PROGRESS, REOPENED | `-priority_score`, then `due_at` | all | OWNER, MANAGER, ANALYST, VIEWER |
| `triage` | status ∈ OPEN, REOPENED | `-priority_score` | all | |
| `mine` | active and `assignee_id = me` | `-priority_score` | users with `exceptions.work` | STAFF |
| `unassigned` | active and `assignee_id IS NULL` | `-priority_score` | all | |
| `closed` | status ∈ RESOLVED, DISMISSED | `-updated_at` | all | |

### Data (table columns)

| Column | Source | Align | Hide below |
|---|---|---|---|
| Priority | `priority_band`, `priority_score` → `PriorityIndicator` | left | never |
| Exception | `title` (primary link to S-04, max 2 lines). Second line, muted: type label (from `exception_type`) · `primary_entity.label` · `affected_order_count` orders · `formatExceptionRef(id)` | left | never |
| Severity | `severity` → `SeverityBadge` | left | never (icon-only pill < 1024 with the label in tooltip and accessible name) |
| Status | `status` → `ExceptionStatusPill` | left | never |
| At risk | `exposure_amount` → `Money` ("—" when 0, i.e. no order value at risk) | right | lg |
| Assignee | `assignee.full_name` (avatar initials 20 px + name) or "Unassigned" (muted) | left | md |
| Due | `due_at` → `formatDue` (overdue in `--overdue-fg` with `alarm-clock`) | left | never |
| Last detected | `last_detected_at` → `RelativeTime` | left | xl (column hidden by default, toggle in Density menu) |

In the **Closed** view, Due is replaced by **Closed** (`resolved_at` or the dismissal event time),
and the status pill shows the resolution: "Resolved · Stock replenished", "Resolved · Condition
cleared (auto)", "Dismissed · False positive".

### Actions

| Action | Permission | Notes |
|---|---|---|
| Open exception | `exceptions.read` | Whole row (stretched link). |
| Run analysis | `evaluations.run` | Same as S-02. |
| Row actions | none in v1 | Lifecycle actions live on S-04 only. This keeps every transition next to its evidence (deterministic first). Bulk actions are out of scope (no bulk API). |

### Filters / sort / search

| Control | Param | Options |
|---|---|---|
| Search | `q` | Title contains (case-insensitive). `EXC-xxxxxxxx` or a full UUID matches by ID. 300 ms debounce. `/` focuses the field. |
| Severity | `severity` | Critical, High, Medium, Low (multi) |
| Priority | `priority_band` | P1, P2, P3, P4 (multi) |
| Status | `status` | Statuses allowed by the current view (multi) |
| Category | `category` | Inventory, Fulfillment, Payment, Data quality |
| Type | `exception_type` | The 9 catalog types, grouped by category, with labels: Oversold, Oversell risk, Out of stock, Below reorder point, Fulfillment overdue, Stalled after payment, Refund pending, Order total mismatch, Negative on-hand |
| Assignee | `assignee` | Me, Unassigned, then members from `assignable-users` (searchable combobox) |
| Due | `due` | Overdue (`due_at < now`), Due within 24 h, Any |
| Detected in run (hidden) | `evaluation_run_id` | Set by links from S-13/S-21. Shown as a removable chip "From evaluation run Oct 31, 8:05 AM EDT". |
| Related entity (hidden) | `order_id`, `product_id` | Set by links from S-06/S-08. Shown as a chip "Order KHK-10482". |
| Sort | `sort` | Priority (`-priority_score`), Due soonest (`due_at`), Newest (`-first_detected_at`), Last detected (`-last_detected_at`), Value at risk (`-exposure_amount`), Severity (`-severity`) |

**Pagination.** Server-side, 25 per page (25/50/100). **Refresh.** Refetch on window focus and
every 60 s while the tab is visible. Keyboard focus stays on the same exception ID across refetches.

| State | Behaviour |
|---|---|
| Initial loading | Standard. The tabs render immediately, without counts. |
| Empty (no exception ever, no evaluation run) | "No exceptions detected yet". "Exceptions appear after an analysis runs on imported data." Action **Run analysis** (`evaluations.run`), or link **Go to Imports**. |
| Empty view | Triage: success tone, "Triage queue is clear", "No open or reopened exceptions.", link **View all active**. Mine: "Nothing is assigned to you", "Claim an unassigned exception or check with your manager.", link **View unassigned**. Unassigned: "Every active exception has an owner." Closed: "No resolved or dismissed exceptions yet." |
| Populated | As wireframed. |
| Search results | Standard. An exact `EXC-` reference match with a single result shows a hint row: "Press Enter to open EXC-9B1C4E2A." |
| Filtered / no results | Standard: "No exceptions match these filters". |
| Validation error | Standard URL-param handling. |
| API error with retry | Standard, inside the card. Tabs and filters stay usable. |
| Permission denied | Standard (`exceptions.read`). The `mine` view for users without `exceptions.work` falls back to `active` with an info toast: "Assigned to me is available to roles that work on exceptions." |
| Success toast | Run analysis only (see S-02). |
| Pending action | Run analysis only. |
| Confirmation dialog | N/A. |
| Disabled action | Run analysis per permission. |
| Responsive | < 768: stacked rows (DESIGN_SYSTEM §11.5). Tabs scroll horizontally with fade edges. Filters collapse into "Filters (n)", which opens a bottom sheet with **Apply** and **Reset**. Sort is a select. 768–1279: Assignee and At risk hidden per the column table. |

---

## S-04 Exception detail / investigation

**Purpose.** Everything needed to understand, decide on and move one exception through its
lifecycle: what was detected, why it ranks where it does, the evidence and its sources, who is
affected, what happened so far, and (separately labelled) what the copilot makes of it.
**Personas.** Operations Staff and Manager (act). Owner, Analyst and demo viewer (read).

### Wireframe (≥ 1280 px, content area)

```text
Exceptions / EXC-9B1C4E2A                                          [‹ Previous] [Next in queue ›]
Oversold: Enamel Dutch Oven 5.5 qt, Sage
Oversold · Inventory · Product KHK-DO55-SGE ↗ · EXC-9B1C4E2A [⧉] · Rule INV-OVERSOLD@1
[■ Critical]  ▮▮▮▮ P1 · 81   [○ Open]   Assignee: Unassigned [Assign ▾]   Due in 3h 55m [✎]
First detected Oct 31, 9:45 AM EDT · Last detected 9:45 AM EDT · Detected 1 time
                                       [Acknowledge]  [Start work]  [Claim]  [More ▾]
+--------------------------------------------------------------+ +-----------------------------+
| ☰ Recommended action · rule INV-OVERSOLD@1                   | | AI investigation            |
| Confirm physical stock with a cycle count. Then expedite     | | Summary                     |
| incoming stock or contact the affected customers about a     | |  4 paid orders cannot be    |
| delay, starting with the most recent orders.                 | |  fully covered by stock…    |
+--------------------------------------------------------------+ | Facts (3)              [▾]  |
| Why this priority                        81 / 100 · P1 (≥ 70) | | Metrics (2)            [▾]  |
| Severity         Critical                   50 / 50  ███████ | | Estimates (1)  est.    [▾]  |
| Affected orders  4 orders × 3               12 / 15  █████▯▯ | | Recommendations (2)    [▾]  |
| Exposure         $600.00 at risk (log)      11 / 15  █████▯▯ | | Limitations (2)        [▾]  |
| Deadline         Nearest ship-by in 10 h     8 / 12  █████▯▯ | | References                  |
| Time unresolved  0 days × 2                  0 / 8   ▯▯▯▯▯▯▯ | | [KHK-DO55-SGE] [KHK-10477]  |
| Due Oct 31, 1:45 PM EDT: Critical response time, 4 h after   | | [KHK-10479] [+2]            |
| first detection.                                             | | Generated 9:51 AM EDT ·     |
| Priority ranks work; it does not measure money lost. [ⓘ]     | | Deterministic engine ·      |
+--------------------------------------------------------------+ | Data Oct 1 – Oct 31         |
| How this was detected                     As of 9:45 AM EDT   | | [Regenerate] [Ask follow-up]|
| Condition   available < 0                          → true     | +-----------------------------+
| Available   on_hand − reserved     18 − 22        = −4        | | Details                     |
| Shortage    −available                            = 4 units   | | Entity    KHK-DO55-SGE ↗    |
| Exposure    Σ uncovered qty × price  4 × $150.00 = $600.00   | | Category  Inventory         |
+--------------------------------------------------------------+ | Detected  Scheduled run     |
| Evidence                                                     | | Detections 1 · Reopens 0    |
| Fact               Value                  Source             | | ▸ Technical details         |
| On hand            18                     Inventory balance ↗| +-----------------------------+
| Reserved           22                     19 reservations ↗  |
| Available          −4                     Calculated         |
| Incoming           40 · ETA Nov 4         Movement PO-2291 ↗ |
| Last cycle count   Oct 28, 6:00 PM EDT    Movement CC-1028 ↗ |
+--------------------------------------------------------------+
| Affected orders (4)                                          |
| Order       Paid (ET)          Ship by (ET)     Uncov.  At risk |
| KHK-10477   Oct 29, 7:45 PM    Oct 31, 7:45 PM  1    $150.00 |
| KHK-10479   Oct 29, 9:02 PM    Oct 31, 9:02 PM  1    $150.00 |
| …                                                            |
+--------------------------------------------------------------+
| Activity                                     [All] [Notes]   |
| [ Add a note…                                             ]  |
|                      [Draft with copilot]       [Add note]   |
| ● Detected by scheduled evaluation · Oct 31, 9:45 AM EDT     |
+--------------------------------------------------------------+
```

### Layout
- **Header block** (full width): breadcrumb (parent link restores the remembered list URL), queue
  navigation (**Previous** / **Next in queue**: neighbours in the remembered list page, hidden when
  the user arrived without a list), title (`h1`, `operational_exception.title`), meta line, status
  row, detection line, then the **ExceptionActionBar** (right-aligned, wraps under the status row
  below 1024 px).
- **Lifecycle banner** (conditional, directly under the header):

| Condition | Tone | Copy |
|---|---|---|
| `RESOLVED`, manual, `verified_at` null | info | "Resolved by {name} at {time} ({resolution label}). The next evaluation will check that the condition has cleared." |
| `RESOLVED`, `verified_at` set | success | "Resolution verified at {time}. The condition was no longer detected." |
| `RESOLVED`, `CONDITION_CLEARED` | success | "Resolved automatically at {time}. The condition cleared during an evaluation." |
| `RESOLVED`, `SUPERSEDED` | neutral | "Superseded at {time} by {EXC-ref} ({type label}). Work continues there." + link |
| `REOPENED`, `VERIFICATION_FAILED` | warning | "Reopened at {time}. The condition was still present at the first evaluation after {name} resolved it." |
| `REOPENED`, `RECURRED_WITHIN_WINDOW` | warning | "Reopened at {time}. The condition came back within {reopen_window_hours} h of being resolved." |
| `REOPENED`, manual | warning | "Reopened by {name} at {time}: {reason}." |
| `DISMISSED` | muted | "Dismissed by {name} at {time} · {dismissal reason label}: {note}" |
| `previous_occurrence_id` set | neutral (secondary line) | "This condition occurred before: {EXC-ref}, resolved {date}." + link |

- **Main column** (≥ 1280: fluid, aside 360 px. Below: single column), sections in this order:
  1. **Recommended action**: callout (neutral tone, `list-checks` icon), label "Recommended action ·
     rule {rule_id}", text `recommended_action` in `text-prose`. Labelled as rule-authored. It is
     never mixed with AI output.
  2. **Why this priority**: `PriorityBreakdown` (all five components, points / max, meters, total
     and band threshold, due-date basis line, limitation note with a popover listing the
     PRIORITY_MODEL limitations).
  3. **How this was detected**: `CalculationBlock` (condition, then each step: label, expression,
     substituted values, result; `as_of` in the header).
  4. **Evidence**: `EvidenceTable`.
  5. **Affected orders** (inventory types with affected orders, and order types via related
     orders) or **Order** summary (order-type exceptions: status axes, total, ship by, lines with
     product health) plus **Related products** (products on the order with an active inventory
     exception).
  6. **Activity**: `NoteComposer` on top, then `Timeline` (newest first, events and notes merged,
     filter All / Notes).
- **Aside** (≥ 1280, 360 px, scrolls with the page):
  1. **AI investigation** (`AIInvestigationPanel`).
  2. **Details**: entity link, category, type, rule ID, "Detected by {trigger} evaluation",
     detection count, reopen count, previous occurrence, superseded by, resolution (code, note, by,
     at, verified at), dismissal reason. Collapsible **Technical details**: `dedup_key`, full
     `id` (copy), `evaluation_run_id`.
- **Below 1280 px:** single column in this order: header → banner → Recommended action → Why this
  priority → How this was detected → Evidence → Affected orders → **AI investigation** → Activity
  → Details. Deterministic sections always come first. An "On this page" select (≥ 768) or
  menu (< 768) jumps to section anchors (`#priority`, `#calculation`, `#evidence`, `#affected`,
  `#ai`, `#activity`).

### Data

| UI element | Source |
|---|---|
| Title, type, category, rule | `operational_exception.{title, exception_type, category, rule_id}` |
| Reference | `formatExceptionRef(operational_exception.id)` |
| Primary entity | `exception_entity_link (role=PRIMARY)` → `{entity_type, entity_id, label}` |
| Severity, priority | `severity`, `priority_score`, `priority_band`, `priority_breakdown` (proposed shape §0.4) |
| Status, assignee, due | `status`, `assignee_id` → member name, `due_at`, `priority_breakdown.due.basis` |
| Detection line | `first_detected_at`, `last_detected_at`, `detection_count` |
| Recommended action | `recommended_action` (deterministic, rule-authored) |
| Calculation | `calculation` (proposed shape §0.4) |
| Evidence | `evidence[]` (proposed shape §0.4). `is_estimate` values get `EstimateLabel`. |
| Affected orders | `exception_entity_link (role=AFFECTED, entity_type=order)` joined with `sales_order.{order_number, paid_at, ship_by, status, total}`. The uncovered quantity and value come from the evidence's affected-order items (BR-402). |
| Lifecycle banner | `status`, `resolution_code`, `resolution_note`, `resolved_by`, `resolved_at`, `verified_at`, `dismissed_reason`, `superseded_by_id`, `previous_occurrence_id`, the latest `REOPENED` event payload `reason` |
| Timeline | `GET …/events` → `exception_event.{event_type, actor_type, actor_id, from_status, to_status, payload, occurred_at, evaluation_run_id}`. `GET …/notes` → `exception_note.{author_id, body, source, created_at}` |
| AI panel | Latest `ai_conversation` with `context_type=EXCEPTION, context_id={id}` for the current user, plus its last `ai_message.content` (structured answer) |
| Version | `operational_exception.version` (needed for `expected_version`; see open question in the final report) |

**Timeline event copy** (actor "System" for `actor_type = SYSTEM`):

| `event_type` | Line |
|---|---|
| `DETECTED` | "Detected by {trigger} evaluation" |
| `EVIDENCE_UPDATED` | "Evidence updated: {changed facts, e.g. Available −2 → −4}" (expandable diff) |
| `SEVERITY_CHANGED` | "Severity changed from High to Critical" |
| `STATUS_CHANGED` | "{Actor} changed status from {from} to {to}" (+ resolution code and note, or dismissal reason and note, when present) |
| `ASSIGNED` / `UNASSIGNED` | "{Actor} assigned {assignee}" / "{Actor} claimed this exception" / "{Actor} removed the assignee" |
| `NOTE_ADDED` | Rendered as the note itself (author, time, body; badge "AI draft, accepted by {author}" when `source = AI_DRAFT_ACCEPTED`) |
| `DUE_DATE_CHANGED` | "{Actor} changed the due date from {old} to {new}" (+ note) |
| `AUTO_RESOLVED` | "Resolved automatically: the condition cleared" |
| `VERIFIED` | "Resolution verified: the condition was no longer detected" |
| `REOPENED` | "Reopened: {reason label}" |
| `SUPERSEDED` | "Superseded by {EXC-ref}" |

### Actions (ExceptionActionBar)

Availability by status. **Primary** is the filled button. Others are outline buttons or sit in
the **More** menu.

| Status | Primary | Secondary | More menu |
|---|---|---|---|
| `OPEN` | Acknowledge | Start work · Claim (if unassigned) | Resolve… · Dismiss… |
| `ACKNOWLEDGED` | Start work | Claim (if unassigned) · Resolve… | Dismiss… |
| `IN_PROGRESS` | Resolve… | none | Dismiss… |
| `REOPENED` | Start work | Acknowledge · Claim (if unassigned) | Resolve… · Dismiss… |
| `RESOLVED` | Reopen… | none | none |
| `DISMISSED` | Reopen… | none | none |

Field-level controls on active statuses: **Assignee** (`AssigneeControl`) and **Due date** edit (✎).

| Action | API | Permission and preconditions | Disabled reason (when visible but not allowed) |
|---|---|---|---|
| Acknowledge | `POST /acknowledge` | `exceptions.work`. From `OPEN` or `REOPENED` | Permission copy (IA §5) / demo copy |
| Start work | `POST /start` | `exceptions.work`. STAFF only if unassigned or assigned to self (auto-assigns self when unassigned). Holders of `exceptions.assign` may start any. | "This exception is assigned to {name}. Ask a manager to reassign it." |
| Claim | `POST /claim` | `exceptions.work`, `assignee_id` null, status active | Hidden when assigned |
| Resolve… | `POST /resolve {resolution_code, resolution_note, expected_version}` | `exceptions.work` **and** (actor is assignee **or** holds `exceptions.manage`) | "Only the assignee or a manager can resolve this exception." |
| Dismiss… | `POST /dismiss {dismissal_reason, note, expected_version}` | `exceptions.manage` | "Dismissing requires the Manage exceptions permission." |
| Reopen… | `POST /reopen {reason, expected_version}` | `exceptions.manage`, status `RESOLVED` or `DISMISSED` | "Reopening requires the Manage exceptions permission." |
| Assign / reassign / unassign | `PUT /assignee {assignee_id \| null}` | `exceptions.assign` | Field renders read-only text, with the reason on focus |
| Change due date | `PUT /due-date {due_at, note?}` | `exceptions.assign` | Edit button `aria-disabled` |
| Add note | `POST /notes {body, source:"USER"}` | `exceptions.work` | The composer is replaced by "Notes can be added by people who work on exceptions." (demo: read-only copy) |
| Draft with copilot | `POST /ai/note-draft` | `copilot.use` (saving still needs `exceptions.work`) | "Saving notes requires the Work on exceptions permission." on **Save note** |
| Generate investigation / Regenerate | `POST /ai/investigation` | `copilot.use` | Panel shows a permission message |

**Dialogs**

| Dialog | Fields (Zod) | Copy |
|---|---|---|
| **Resolve exception** | `resolution_code`: select, required, one of STOCK_REPLENISHED "Stock replenished", ORDER_FULFILLED "Order fulfilled", REFUND_ISSUED "Refund issued", DATA_CORRECTED "Data corrected", CUSTOMER_CONTACTED "Customer contacted", FIXED_IN_SOURCE_SYSTEM "Fixed in source system", OTHER "Other". `resolution_note`: textarea, required, trimmed length 10–4,000 ("6 / 10 minimum") | Info callout: "The next evaluation checks the data in RetailOps. If your change in the source system has not been imported yet, this exception will reopen (verification failed). For long-running work, keep it In progress. It resolves automatically when the condition clears." Submit: **Resolve exception** |
| **Dismiss exception** | `dismissal_reason`: radio group, required: FALSE_POSITIVE "False positive: the condition isn't real", ACCEPTED_RISK "Accepted risk: we know and accept it", DUPLICATE "Duplicate: tracked elsewhere", NOT_ACTIONABLE "Not actionable: nothing we can do". `note`: required, trimmed length ≥ 1, ≤ 4,000 | "Dismissed exceptions stop being tracked. If the condition clears and comes back later, a new exception is created." Submit: **Dismiss exception** |
| **Reopen exception** | `reason`: textarea, required, trimmed length ≥ 1, ≤ 4,000 | "The exception returns to Reopened and appears in the triage queue." Submit: **Reopen exception** |
| **Change due date** (popover) | `due_at`: date + time in the store zone, required, must be in the future. `note`: optional | Shows "Calculated: Oct 31, 1:45 PM EDT (Critical, 4 h response)". Submit: **Update due date** |
| **Assign** (popover combobox) | Searchable list: "Assign to me" (first, if the user can work), members from `assignable-users` (name + role), "Remove assignee" | Selecting submits immediately. The field shows a pending spinner. |

The Resolve, Dismiss and Reopen dialogs are the confirmation for those actions. No second dialog
follows.

### Filters / sort / search / pagination
Timeline filter: All / Notes (client-side over the loaded events). Events load 50 at a time with
**Show earlier activity**. Affected orders: up to 50 rows, sorted by `paid_at` (FIFO, as allocated),
with "View all {n} in Orders" linking to `/orders?exception_id={id}`.

| State | Behaviour |
|---|---|
| Initial loading | Header skeleton (title bar + 3 pill blocks), then section skeletons. The AI panel and timeline load independently. |
| Empty sub-sections | Affected orders: "No orders are affected. Out-of-stock and below-reorder-point exceptions don't block existing orders (value at risk $0.00)." Evidence: never empty (a rule always emits evidence). If it is empty, show "Evidence unavailable for this exception" plus the `request_id`, as a defect signal. Timeline always has `DETECTED`. AI panel: see `AIInvestigationPanel` empty state. |
| Populated | As wireframed. |
| Search / filtered | Timeline Notes filter with no notes: "No notes yet." |
| Validation error | Dialog field errors per the table. Server 422 is mapped to fields. |
| API error with retry | Per section. A failed exception fetch makes the whole page an `ErrorState`. A failed events, notes or AI request is section-local. |
| Not found | `NotFoundState`: "This exception doesn't exist or belongs to another store." Link **Back to exceptions**. |
| Permission denied | Standard (`exceptions.read`). Action-level per the table. |
| Conflict (409) | Standard conflict state inside the open dialog. Without a dialog (Acknowledge, Start, Claim), an error toast: "This exception changed. The latest details are shown." plus an automatic refetch. |
| Changed by others | Refetch on focus and every 60 s. When `status` or `assignee` changed since the last render and the user has no dialog open: info toast "Updated by {actor}: status is now In progress". |
| Success toast | Acknowledge → "Exception acknowledged". Start → "Work started. Assigned to you." Claim → "Assigned to you". Resolve → "Exception resolved. It will be verified at the next evaluation." · **Next in queue**. Dismiss → "Exception dismissed" · **Next in queue**. Reopen → "Exception reopened". Assign → "Assigned to {name}". Due → "Due date updated". Note → no toast (the note appears in the timeline, which is announced via a polite live region). |
| Pending action | Standard. The whole action bar is `aria-disabled` while one transition is in flight. |
| Confirmation dialog | Resolve, Dismiss, Reopen (the form dialogs above). |
| Disabled action | Per the action table. In demo orgs, every mutating control shows "The public demo is read-only." In addition, **How resolution works** (a popover with the lifecycle explainer) is shown next to the action bar for VIEWER only. |
| Responsive | < 768: the action bar becomes a sticky bottom bar (`--z-sticky-bar`, 64 px, `--card` with a top border) holding the primary action and **More** (a bottom sheet listing the other actions with their disabled reasons). Status pills wrap to two lines. Evidence and affected-orders tables scroll horizontally with the first column pinned. The PriorityBreakdown meter column is hidden below 400 px (points stay). |

---

## S-05 Orders list

**Purpose.** Find orders and see their three status axes, deadlines and linked exceptions.
Orders are read-only in v1 (they change through imports only). **Personas.** Staff and Manager
(investigation), Owner.

**Layout.** PageHeader "Orders" (subtitle "Read-only. Orders are updated by CSV imports.") →
FilterBar → DataTable → Pagination.

| Column | Source | Align | Hide below |
|---|---|---|---|
| Order | `sales_order.order_number` (primary link) | left | never |
| Placed (ET) | `placed_at` → short date-time | left | never |
| Channel | `channel` (Web, Marketplace, POS, Other) | left | lg |
| Status | `status` → `OrderStatusPill` | left | never |
| Payment | `payment_status` (text in the tone colour, with icon) | left | md |
| Fulfillment | `fulfillment_status` (text in the tone colour, with icon) | left | lg |
| Ship by (ET) | `ship_by` → short date-time, plus "Overdue 30h" flag when `computed: is_overdue` (BR-202) | left | md |
| Items | `computed: item_count` | right | xl |
| Total | `total` → Money | right | never |
| Exceptions | `computed: active_exception_count` → neutral count badge with an accessible name ("2 active exceptions"). Empty is "—". | right | lg |

**Actions.** Open order (`orders.read`). No create, edit or delete (IA-5).

**Filters / sort / search.** Search `q`: order-number prefix. Exact `customer_ref` match when the
input starts with `CUST-` (BR-505: never free-text over customer data). Status (multi, grouped by
status group). Payment status. Fulfillment status. Channel. Placed (presets Today, Last 7 days,
Last 30 days, Last 60 days, Custom range in store-local dates). **Overdue only** toggle
(`overdue=true`). **Has active exceptions** toggle. Hidden `exception_id` (chip "Affected by
EXC-9B1C4E2A"). Sort: Placed newest (default), Ship by soonest, Total highest, Order number.
**Pagination:** 25 (25/50/100).

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | "No orders yet". "Orders come from CSV imports (orders.csv, then order_items.csv)." Action **Import orders** (`imports.run`). |
| Populated / search results / filtered | Standard. The Overdue-only empty result uses a success tone: "No overdue orders". |
| Validation error | Custom date range: "End date must be on or after start date." |
| API error / permission denied | Standard (`orders.read`). |
| Success toast / pending / confirmation / disabled | N/A (read-only screen). |
| Responsive | < 768: stacked rows. Line 1: order number + Status pill + total. Line 2: placed · payment · fulfillment. Line 3: ship by with the overdue flag, plus an exceptions count. |

---

## S-06 Order detail

**Purpose.** Show one order's facts across its three status axes, its lines and their stock
reservations, its status history (including skipped states from imports) and every exception
touching it. **Personas.** Staff, Manager.

**Layout.**
1. PageHeader: breadcrumb "Orders / KHK-10482". Title "Order KHK-10482". `OrderStatusPill` (md),
   overdue flag. Meta: "Placed Oct 29, 9:12 AM EDT · Web · Customer CUST-10492 · USD". Action:
   **Ask the copilot** (link, `copilot.use`): opens S-14 prefilled "Summarise order KHK-10482 and
   any open issues."
2. **Status** card, three labelled fields side by side (stacked < 640): Status / Payment /
   Fulfillment, each a pill plus a one-line meaning. Info popover: "Orders track three separate
   facts: lifecycle, money and goods (STATE_MACHINES §1)." Special-combination callouts:
   `CANCELLED` + `PAID` → warning "Cancelled but still paid: a refund is pending." + link to the
   `ORDER_REFUND_PENDING` exception if one exists. `REFUNDED` + `DELIVERED` → info "Refunded
   without a return: the customer kept the goods."
3. **Key dates** (DescriptionList, two columns ≥ 768): Placed, Paid, Ship by (+ source: "Imported"
   or "Store SLA: paid + 48 h", from `ship_by_source` and `store_settings.fulfillment_sla_hours`),
   Shipped, Delivered, Cancelled, Carrier, Tracking number (text plus a copy button, not a link: no
   carrier integration).
4. **Line items** (table, compact): Line · SKU (link to S-08) · Product · Qty · Unit price ·
   Discount · Line total · Reservation (`stock_reservation.status` → "Reserved" / "Shipped" /
   "Released", neutral text) · Stock (`HealthBadge` of the product, when `inventory.read`).
5. **Totals** (right-aligned DescriptionList): Subtotal, Discounts, Shipping, Tax, **Total
   (recorded)**. When `computed: expected_total` differs by more than 0.01 (BR-205): an extra row
   "Expected total {Money}" and "Difference {Money}" in `--tone-danger-fg`, plus a link to the
   `DATA_ORDER_TOTAL_MISMATCH` exception.
6. **Exceptions** (`exceptions.read`): compact list of linked exceptions (active first, then the
   last 5 closed): severity, title, status, priority, and role ("About this order" for PRIMARY,
   "Affects this order" for AFFECTED).
7. **Status history** (`OrderTimeline`): each `order_event` as "Paid → Shipped, via Processing,
   Ready to ship" (`skipped_statuses`), source tag Import / User / System, time, and for imports
   the file name linking to S-13.

**Data.** `sales_order.*`, `order_item.*`, `stock_reservation.{status, quantity}` per item,
`order_event.*`, product `computed: health`, `exception_entity_link` → exceptions,
`computed: expected_total`, `computed: is_overdue`, `computed: hours_overdue`.

**Actions.** Ask the copilot (`copilot.use`). Links only. No mutations.

| State | Behaviour |
|---|---|
| Initial loading | Standard section skeletons. |
| Empty sub-sections | No lines: "This order has no lines yet. Import order_items.csv." (A total-mismatch check needs at least one line, BR-205.) No exceptions: "No exceptions involve this order." No events beyond creation: a single "Created by import" entry. |
| Not found | Standard NotFound. |
| API error / permission denied | Standard. The Exceptions section is omitted without `exceptions.read`. |
| Search / filtered / validation / toast / pending / confirmation / disabled | N/A (read-only). |
| Responsive | < 768: Line items keep the table with the SKU column pinned and horizontal scroll. Status fields stack. |

---

## S-07 Products list

**Purpose.** Catalog hygiene: find SKUs and check status, price, cost, supplier and reorder
settings. **Personas.** Manager, Analyst.

| Column | Source | Align | Hide below |
|---|---|---|---|
| SKU | `product.sku` (primary link to S-08, weight 500) | left | never |
| Name | `name` | left | never |
| Category | `category` | left | lg |
| Status | `status` → tag: Active (neutral), Draft (outline), Archived (muted) | left | md |
| Price | `unit_price` → Money | right | never |
| Cost | `unit_cost` → Money, "—" if null. A `circle-alert` warning icon when cost > price, with tooltip "Unit cost is higher than unit price." | right | lg |
| Supplier | `supplier.name` · `supplier.lead_time_days` d | left | xl |
| Reorder point / qty | `reorder_point` / `reorder_quantity` | right | lg |
| Available | `computed: available` (if `inventory.read`) | right | md |
| Stock | `computed: health` → `HealthBadge` (if `inventory.read`) | left | never |
| Exceptions | `computed: active_exception_count` | right | lg |

**Actions.** Open product. No catalog editing in v1 (CSV import only).
**Filters / sort / search.** `q`: SKU prefix (case-sensitive, BR-506) or name contains. Status
(default: Active). Category (from `products/categories`). Supplier. Stock health. Has active
exceptions. Sort: SKU (default), Name, Price, Available. **Pagination:** 25 (25/50/100).

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | "No products yet". "Import products.csv to create your catalog. SKUs are matched exactly." Action **Import products** (`imports.run`), link **Download template**. |
| Populated / search / filtered | Standard. |
| Validation / toast / pending / confirmation / disabled | N/A. |
| API error / permission denied | Standard (`catalog.read`). Columns needing `inventory.read` are omitted without it. |
| Responsive | < 768: stacked rows. Line 1: SKU + health badge. Line 2: name. Line 3: price · available · supplier. |

---

## S-08 Product detail

**Purpose.** The hub for one SKU: master data, stock position and its arithmetic, reservations,
recent ledger entries and linked exceptions (IA §3 A3). **Personas.** Staff, Manager.

**Layout.**
1. PageHeader: breadcrumb "Products / KHK-DO55-SGE". Title = `product.name`. Meta: SKU, category,
   status tag, `HealthBadge` (md).
2. **Stock position** (`inventory.read`): a row of `StatTile`s: On hand, Reserved, **Available**
   (danger text when negative, with the minus sign), Incoming (+ ETA), Pending demand, Avg daily
   units (est.), Days of cover (est.). Under the tiles, one formula line in `text-mono`:
   "available = on_hand − reserved = 18 − 22 = −4 (BR-101). Incoming is not counted (BR-103)."
   Health explanation: "Oversold: available is below 0." For the reorder-point classes:
   "Reorder point 10. Approaching from 11 to 13 (reorder point × 1.25, rounded up)."
3. **Product** (DescriptionList): price, cost, reorder point, reorder quantity, supplier (name,
   lead time), last cycle count.
4. **Exceptions** (`exceptions.read`): active and the last 5 closed (same compact list as S-06).
5. **Active reservations** (`inventory.read`): Order (link) · Line · Qty · Paid (ET) · Ship by (ET),
   sorted by `paid_at` (the FIFO order used by BR-402). Max 50, then "View in Orders".
6. **Recent movements** (`inventory.read`): last 10 ledger rows (compact) + **View all
   movements** → `/inventory/movements?product_id={id}`.

**Data.** `product.*`, `supplier.{name, lead_time_days}`, inventory position
(`inventory_balance.{on_hand, reserved, incoming, incoming_eta, last_cycle_count_at}` and
`computed: available, pending_demand, avg_daily_units, days_of_cover, health`),
`stock_reservation` (ACTIVE) with order fields, `inventory_movement` (10), exceptions by
`product_id`.

**Actions.** Links only.

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty sub-sections | No reservations: "No units are reserved for paid orders." No movements: "No ledger entries yet. Stock arrives through inventory adjustment imports." Days of cover null: "Not enough sales history" (BR-151). Non-ACTIVE product: health "Not tracked" with "Stock health is computed for active products only." |
| Not found | Standard. |
| API error / permission denied | Standard. Sections omitted per permission. |
| Search / filtered / validation / toast / pending / confirmation / disabled | N/A. |
| Responsive | < 768: tiles in 2 columns. The formula line wraps. Tables scroll with the first column pinned. |

---

## S-09 Inventory positions

**Purpose.** See stock risk across all SKUs at once, ranked by health. **Personas.** Manager,
Staff.

**Layout.** PageHeader "Inventory" → **Health summary bar**: five toggle buttons with counts
("Oversold 2", "Out of stock 4", "Below reorder point 11", "Approaching 7", "Healthy 96"). Each is
a real `button` with `aria-pressed` and sets the `health` filter. Then a caption: "Available = on
hand − reserved. Incoming stock is shown separately and never counted as available (BR-101,
BR-103)." → FilterBar → DataTable (compact default) → Pagination.

| Column | Source | Align | Hide below |
|---|---|---|---|
| SKU | `product.sku` (link to S-08) | left | never |
| Product | `product.name` | left | md |
| Health | `computed: health` → `HealthBadge` | left | never |
| On hand | `inventory_balance.on_hand` | right | md |
| Reserved | `reserved` | right | md |
| Available | `computed: available` (danger text if < 0) | right | never |
| Incoming | `incoming` + "ETA Nov 4" (`incoming_eta`) | right | lg |
| Pending demand | `computed: pending_demand` | right | xl |
| Reorder point | `product.reorder_point` | right | lg |
| Avg daily units (est.) | `computed: avg_daily_units` (1 dp) | right | xl |
| Days of cover (est.) | `computed: days_of_cover` (1 dp, or "—" with a tooltip "Not enough sales history") | right | lg |
| Last count (ET) | `last_cycle_count_at` | left | xl |

**Filters / sort / search.** `q` SKU prefix / name. Health (multi). Category. Supplier. Product
status (default Active. Including inactive shows "Not tracked"). Has incoming. Sort: Health
(default: Oversold → Healthy, then available ascending), Available (asc), Days of cover (asc),
SKU. **Pagination:** 50 default (50/100), since the table is compact.

| State | Behaviour |
|---|---|
| Initial loading | Standard. The summary bar shows skeleton chips. |
| Empty | "No stock positions yet". "Import products, then inventory adjustments (a CYCLE_COUNT sets on-hand)." Action **Import inventory adjustments** (`imports.run`). |
| Populated / search / filtered | Standard. "Oversold" filter with no rows: success tone, "No oversold products". |
| Validation / toast / pending / confirmation / disabled | N/A. |
| API error / permission denied | Standard (`inventory.read`). |
| Responsive | < 768: stacked rows. Line 1: SKU + health. Line 2: name. Line 3: "Available −4 · On hand 18 · Incoming 40 (Nov 4)". The summary bar scrolls horizontally. |

---

## S-10 Movements ledger

**Purpose.** The append-only record of every on-hand and incoming change (BR-110), for tracing
why a balance is what it is. **Personas.** Manager, Staff, Analyst.

**Layout.** PageHeader "Movements" (subtitle "Append-only ledger. Corrections appear as CORRECTION
entries."). FilterBar → DataTable (compact) → Pagination.

| Column | Source | Align | Hide below |
|---|---|---|---|
| Occurred (ET) | `inventory_movement.occurred_at` | left | never |
| SKU | `product.sku` (link) | left | never |
| Type | `movement_type` → label: Cycle count, Receipt, Incoming expected, Incoming cancelled, Damage, Shrinkage, Return restock, Correction, Shipment | left | never |
| On hand Δ | `on_hand_delta` → `formatDelta` | right | never |
| Incoming Δ | `incoming_delta` → `formatDelta` | right | md |
| Source | `source` (Import, Order, System) | left | lg |
| Reference | `reference`: `order_item:{id}` renders as "Order KHK-10482 · line 2" (link to S-06). Others as plain text in mono. | left | md |
| Note | `note` (truncated, tooltip) | left | xl |
| Import | `import_id` → file name (link to S-13) | left | xl |
| Recorded by | `created_by` → name, or "System" | left | xl |

**Filters / sort / search.** Product (combobox, `product_id`; chip "KHK-DO55-SGE"). Type (multi).
Source. Occurred (presets + custom). `q`: reference contains. Sort: Occurred newest (default),
oldest. **Pagination:** 50 (50/100).

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | "No movements yet". "Inventory adjustment imports and shipped orders write ledger entries." Action **Import inventory adjustments** (`imports.run`). |
| Populated / search / filtered | Standard. |
| Validation | Date range as S-05. |
| API error / permission denied | Standard (`inventory.read`). |
| Toast / pending / confirmation / disabled | N/A (append-only and read-only in the UI). |
| Responsive | All widths keep the table (ledger). Horizontal scroll with Occurred pinned. |

---

## S-11 Imports list

**Purpose.** History and live status of CSV imports, and the starting point for new ones.
**Personas.** Manager (runs), Staff and Analyst (read).

**Layout.** PageHeader "Imports". Actions: **Download template ▾** (menu: products.csv,
orders.csv, order_items.csv, inventory_adjustments.csv) and **New import** (primary). An info line
under the header: "Recommended order: products → orders → order items → inventory adjustments."
FilterBar → DataTable → Pagination.

| Column | Source | Align | Hide below |
|---|---|---|---|
| File | `data_import.original_filename` (link to S-12/S-13) | left | never |
| Type | `import_type` → Products / Orders / Order items / Inventory adjustments | left | md |
| Status | `status` → `ImportStatusPill` | left | never |
| Mode | `mode` → Strict / Valid rows only / "—" before apply | left | xl |
| Rows | `row_count` | right | md |
| New · Updated | `summary.new`, `summary.updated` | right | lg |
| Errors | `summary.error` (rows), danger text when > 0 | right | md |
| Warnings | `summary.warning` | right | xl |
| Uploaded by | `created_by` → name | left | lg |
| Uploaded (ET) | `created_at` | left | never |

**Actions**

| Action | Permission | Disabled reason |
|---|---|---|
| New import | `imports.run` | Permission copy / "The public demo is read-only." |
| Download template | `imports.read` | none |
| Open import | `imports.read` | none |

**Filters / sort / search.** `q`: file name contains. Type. Status. Sort: Uploaded newest
(default). **Pagination:** 25. **Live status:** while any visible row is `UPLOADED`, `VALIDATING`
or `APPLYING`, refetch the list every 2 s, and stop when none are.

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | "No imports yet". "Import products first, then orders, order items and inventory adjustments. Each file type has a template." Actions **New import** (`imports.run`) and **Download template**. |
| Populated / search / filtered | Standard. |
| Validation | N/A. |
| API error / permission denied | Standard (`imports.read`). |
| Template download error | Error toast: "Couldn't download the template. Try again." |
| Success toast / pending / confirmation | N/A on this screen. |
| Disabled action | New import per the table. |
| Responsive | < 768: stacked rows. Line 1: file name + status. Line 2: type · rows · errors. Line 3: uploaded time and person. |

---

## S-12 New import wizard (upload → preview → apply → summary)

**Purpose.** Load a CSV safely: never silently skip rows, show every issue before anything
changes, and make partial application an explicit, counted decision (BR-606).
**Persona.** Operations Manager (`imports.run`).

**Routing.** Step 1 is `/imports/new` (`?type=` preselects a type). The upload creates the
`data_import` record, and the app then `router.replace`s to `/imports/{id}`. That route renders
the stepper while `status ∈ {UPLOADED, VALIDATING, VALIDATED, APPLYING}` and the summary/detail
once terminal (IA §3 A8).

**Stepper.** `(1) Upload · (2) Preview · (3) Apply · (4) Summary`. It is an `ol` with
`aria-current="step"`. Completed steps show a check icon and the text "completed". Steps are not
clickable, because the server status drives them.

### Wireframe: step 2 Preview (≥ 1280 px, content area)

```text
Imports / orders_2026-10-31.csv
orders_2026-10-31.csv                                               [▣ Ready to apply]
Orders · 1,240 rows · 412.6 KB · Uploaded by Morgan Lee, Oct 31, 8:00 AM EDT
Preview expires in 23h 58m

  (✓) Upload ─────── (2) Preview ─────── (3) Apply ─────── (4) Summary

+------------+ +------------+ +------------+ +------------+ +------------+ +------------+
| Rows       | | New        | | Updated    | | Unchanged  | | Rows with  | | Warnings   |
| 1,240      | | 312        | | 914        | | 0          | | errors  14 | | 3          |
+------------+ +------------+ +------------+ +------------+ +------------+ +------------+

[!] 3 timestamps had no UTC offset and were read as store time, America/New_York
    (TIMEZONE_ASSUMED). Add an offset to be explicit.

Issues                         [All 17] [Errors 14] [Warnings 3]       [Download issues CSV]
[Code ▾]  [Q Row number]
| Row | Column       | Code                              | Severity  | Message                       | Value                  |
| 18  | status       | ORDER_INVALID_STATUS_COMBINATION  | [x Error] | SHIPPED needs payment PAID     | SHIPPED / PENDING      |
| 41  | placed_at    | INVALID_DATETIME                  | [x Error] | Not an ISO-8601 timestamp      | 10/30/2026 14:05       |
| 77  | status       | ORDER_TRANSITION_NOT_ALLOWED      | [x Error] | DELIVERED → PAID not reachable | PAID                   |
| 112 | currency     | CURRENCY_MISMATCH                 | [x Error] | Store currency is USD          | EUR                    |
| 203 | paid_at      | TIMEZONE_ASSUMED                  | [! Warn.] | Read as America/New_York       | 2026-10-30T11:20:00    |
| …                                                                                                  |
| 1–25 of 17 issues                                                 ‹ Previous  Page 1 of 1  Next › |

                                                      [Discard import]   [Continue to apply ›]
```

### Step 1: Upload (`/imports/new`)
- **Type** (required): radio cards in a 2 × 2 grid (1 column < 640): Products ("Create or update
  products by SKU"), Orders ("Create or update orders by order number"), Order items ("Lines for
  existing orders, by order number and line"), Inventory adjustments ("Counts, receipts, damage and
  corrections. Each reference applies once"). Each card has a **Template** link.
- **Column reference** (collapsible, closed by default): required and optional columns for the
  selected type, from the CSV data contract.
- **File**: `ImportDropzone`. Accepts `.csv` only, ≤ 5 MB. Shows the selected file name and size
  with a **Remove** button.
- Hint for Order items: "Order items must reference orders and SKUs that already exist. Import
  those first."
- Primary: **Upload and validate**. Secondary: **Cancel** (back to S-11).

### Step 2: Preview (`/imports/{id}`, `VALIDATING` → `VALIDATED`)
- `VALIDATING`: a status panel with the `motion-essential` spinner: "Validating 1,240 rows…" plus
  the elapsed time. The app polls every 2 s. Leaving is safe: "You can leave this page. Validation
  continues."
- `VALIDATED`: summary tiles (Rows, New, Updated, Unchanged, Rows with errors, Warnings). Warning
  callouts for `DUPLICATE_FILE` ("This file is identical to an import completed on Oct 30, 8:04 AM
  EDT. Applying it again is safe, because rows are upserted, but may be unnecessary."),
  `TIMEZONE_ASSUMED` (count) and `UNKNOWN_COLUMN` (lists the ignored columns). The expiry countdown
  ("Preview expires in 23h 58m") comes from `expires_at`. Then the `IssueTable`.
- Actions: **Discard import** (secondary, confirm), **Download issues CSV** (when issues > 0),
  **Continue to apply** (primary).

### Step 3: Apply (`VALIDATED`)

```text
Apply mode
(•) Strict  (default)
    Apply only if every row is valid. Nothing is skipped.
    ⚠ Blocked: 14 rows have errors. Fix them in the source file and upload again,
      or choose "Valid rows only".
( ) Valid rows only
    Apply the 1,226 valid rows and skip the 14 rows with errors. Skipped rows are kept
    as import errors and can be downloaded.
    [ ] I understand that 14 rows will be skipped.

What will change: 312 orders created, 914 updated (from the preview).
Applying runs in one transaction. If anything fails, nothing changes.

                                               [‹ Back]   [Apply 1,226 rows, skip 14]
```

- Mode radio (`STRICT` default). With 0 errors, only Strict is shown and the button reads
  **Apply 1,240 rows**.
- Valid rows only requires the consent checkbox. The button label always states the counts.
  The request sends `confirm_skipped_rows = 14`, so the server checks that the consent matches
  the count it skips (BR-606).
- `Idempotency-Key`: generated once per import ID and mode, and reused on retries.
- Button disabled reasons: strict with errors → "Strict mode blocks apply while 14 rows have
  errors."; consent not ticked → "Confirm that 14 rows will be skipped."; no permission → standard.

### Step 3b: Applying (`APPLYING`)
Status panel: "Applying 1,226 rows… This runs in one transaction. If anything fails, no data
changes." Poll every 2 s.

### Step 4: Summary (`COMPLETED` / `COMPLETED_WITH_ERRORS`)
- Banner: success "Import completed. 1,240 rows applied." or warning "Import completed. 1,226 rows
  applied, 14 skipped with your confirmation."
- Summary tiles (applied counts by new/updated/unchanged, skipped).
- **Evaluation run** panel (`data_import.evaluation_run_id`): "Analysis triggered by this import ·
  Running…" (poll), then "3 new exceptions · 6 refreshed · 1 resolved · 0 reopened" with **View
  new exceptions** (`/exceptions?evaluation_run_id={rid}&view=active`).
- Issues section (skipped rows and warnings), with the issues CSV download.
- Actions: **Import another file** (`/imports/new?type={same}`), **Back to imports**.

**Data.** `data_import.{id, import_type, status, mode, original_filename, size_bytes, row_count,
summary, validated_at, applied_at, expires_at, created_by, created_at, file_sha256,
evaluation_run_id}`, `import_row_issue.{row_number, column, code, severity, message, raw_value}`,
`evaluation_run.{status, counts}`.

**Actions**

| Action | Permission | Notes |
|---|---|---|
| Upload and validate | `imports.run` | `POST imports` (multipart) |
| Discard import | `imports.run` | Confirm dialog: "Discard this import? The file is deleted and no data changes. The issue list stays available for reference." Button **Discard import** |
| Apply | `imports.run` | Step 3 is the confirmation. No extra dialog. |
| Retry validation (FAILED) | `imports.run` | `POST /retry` → `VALIDATING` |
| Download issues CSV / template | `imports.read` | Formula-safe export (server) |

| State | Behaviour |
|---|---|
| Initial loading | `/imports/{id}`: header skeleton + stepper + tiles skeleton. |
| Empty | Step 1 has no data state. Preview with 0 issues: "No issues found. All 1,240 rows are valid." (success tone). |
| Populated | As above. |
| Search results / filtered | Issue table: filter by severity tabs, code (multi), row number (exact). No match: "No issues match these filters". |
| Validation error (client) | No type: "Choose what you're importing." No file: "Choose a CSV file." Wrong extension: "Only .csv files can be imported." Too large: "This file is 7.2 MB. The limit is 5 MB. Split it into smaller files." |
| Validation error (file-level, server) | `REJECTED`: danger alert with the code and the fix (table below). **Upload a corrected file** → `/imports/new?type={type}`. |
| API error with retry | Upload network failure: "Upload failed. Check your connection and try again." (the file stays selected). Apply 5xx with the status still `VALIDATED`: an inline error in step 3 with **Try again** (same Idempotency-Key). |
| Apply failed | `FAILED`: danger "Apply failed and was rolled back. No data was changed." + `request_id` + **Retry validation**. |
| Preview expired | `DISCARDED` by expiry: muted "This preview expired after 24 hours, because store data may have changed since validation. Upload the file again." + **Upload again**. |
| Permission denied | `/imports/new` without `imports.run`: standard PermissionDenied. On a record, actions are disabled per the table. |
| Success toast | Discard → "Import discarded". Apply completes → none (the summary step is the confirmation). |
| Pending action | "Uploading… 64%" (upload progress), "Validating…", "Applying…" (status panels). |
| Confirmation dialog | Discard. Apply uses the inline step 3 confirmation. |
| Disabled action | Per the step 3 reasons. |
| Responsive | < 768: tiles in 2 columns. The stepper shows "Step 2 of 4 · Preview". The issue table scrolls horizontally with Row pinned. Step 3 buttons are full width and stacked. |

**File-level codes → fix copy** (`REJECTED`)

| Code | Message shown |
|---|---|
| `FILE_EMPTY` | "The file has no data rows. Check that you exported the right file." |
| `FILE_TOO_LARGE` | "The file is larger than 5 MB. Split it into smaller files." |
| `FILE_TYPE` | "Only .csv files can be imported. Export the sheet as CSV." |
| `FILE_ENCODING` | "The file isn't UTF-8. Export it as "CSV UTF-8" and try again." |
| `TOO_MANY_ROWS` | "The file has more than 20,000 data rows. Split it into parts of 20,000 rows or fewer." |
| `MISSING_COLUMNS` | "Required columns are missing: {list}. Download the template to see the expected headers." |

**Row issue codes → "How to fix" hint** (shown in a tooltip on the code, and in the CSV)

| Code | Hint |
|---|---|
| `REQUIRED` | Fill in the value. This column is required. |
| `VALUE_TOO_LONG` | Shorten the value to the column's maximum length. |
| `INVALID_ENUM` | Use one of the allowed values listed in the template. |
| `INVALID_NUMBER` | Use a plain decimal with a dot, without currency symbols or thousands separators. |
| `INVALID_INTEGER` | Use a whole number. |
| `NEGATIVE_VALUE` | Use 0 or a positive number. |
| `INVALID_DATETIME` | Use ISO-8601, for example 2026-10-31T09:42:00-04:00. |
| `DUPLICATE_KEY_IN_FILE` | Remove the repeated row. The first occurrence is kept. |
| `UNKNOWN_SKU` | Import the product first, or correct the SKU (case-sensitive). |
| `UNKNOWN_ORDER` | Import the order first, or correct the order number. |
| `CURRENCY_MISMATCH` | Use the store currency (USD). |
| `ORDER_INVALID_STATUS_COMBINATION` | Check status, payment_status and fulfillment_status against the allowed combinations. |
| `ORDER_MISSING_TIMESTAMP` | Add the timestamp this status requires (for example paid_at for a paid order). |
| `ORDER_TIMESTAMP_SEQUENCE` | Timestamps must be in order: placed, paid, shipped, delivered. |
| `ORDER_TRANSITION_NOT_ALLOWED` | The order can't move from its current status to this one. Check the source system. |
| `ORDER_LINE_LOCKED` | Lines of orders that have already shipped can't change. |
| `LINE_DISCOUNT_EXCEEDS_LINE` | The line discount can't exceed quantity × unit price. |
| `UNKNOWN_COLUMN` (warning) | Ignored. Remove the column or check its spelling. |
| `TIMEZONE_ASSUMED` (warning) | Read as store time (America/New_York). Add a UTC offset to be explicit. |
| `PRICE_ZERO` (warning) | An active product with price 0. Applied as is. |
| `NEGATIVE_MARGIN` (warning) | Unit cost is higher than unit price. Applied as is. |
| `ALREADY_APPLIED` (warning) | This adjustment reference was already applied. The row has no effect. |
| `DUPLICATE_FILE` (warning) | This file matches a completed import. Applying it again is safe but may be unnecessary. |

---

## S-13 Import detail with issues

**Purpose.** The permanent record of one import: what was uploaded, what happened, every issue,
and what the import triggered. **Personas.** Manager, Staff, Analyst.

**Layout.** For in-progress statuses this route renders S-12. For terminal statuses:
1. PageHeader: breadcrumb "Imports / {file}". Title = file name. `ImportStatusPill` (md). Type tag.
2. **Status callout** (by status):
   - `COMPLETED`: none (the summary tiles suffice).
   - `COMPLETED_WITH_ERRORS`: warning "14 rows were skipped with your confirmation. They are listed below and in the issues CSV."
   - `REJECTED`: danger, with the file-level code and fix (S-12 table) + **Upload a corrected file**.
   - `FAILED`: danger "Apply failed and was rolled back. No data was changed." + `request_id` + **Retry validation**.
   - `DISCARDED`: muted "Discarded on {date} by {name}" or "Discarded automatically: the preview expired after 24 hours."
3. **Details** (DescriptionList): Type, Mode, Uploaded by / at, Validated at, Applied at, Size,
   Rows, SHA-256 (first 12 characters, mono, copy full).
4. **Summary tiles**: New, Updated, Unchanged, Errors, Warnings (from `summary`).
5. **Evaluation run** (applied imports): trigger time, status, counts, and **View new exceptions**.
6. **Issues**: `IssueTable` with severity tabs, code filter and row search, plus **Download issues
   CSV**. Server pagination at 25.

**Data.** As S-12.

**Actions.** Upload a corrected file (`imports.run`), Retry validation (`imports.run`), Download
issues CSV (`imports.read`), View new exceptions (`exceptions.read`).

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | Issues: "No issues. Every row was valid." (success tone). |
| Populated / search / filtered | Issue table as S-12. |
| Validation | N/A. |
| API error | Standard. Issues CSV download failure → error toast with **Try again**. |
| Not found / permission denied | Standard (`imports.read`). |
| Success toast | Retry validation → "Validation restarted" (the stepper takes over). |
| Pending action | Retry validation pending state. |
| Confirmation dialog | N/A. |
| Disabled action | Per permission (standard copy). |
| Responsive | As S-12. |

---

## S-14 Copilot

**Purpose.** Ask questions about the store's operations in plain language and get grounded,
structured answers with references. The copilot never changes data.
**Personas.** Analyst, Manager, Owner, demo viewer.

**Layout.**
- ≥ 1024: a two-pane layout. Left (280 px): **Conversations** list with a **New conversation**
  button, items showing the title (first question, 1 line), a context chip ("Exception
  EXC-9B1C4E2A" when `context_type = EXCEPTION`) and the updated relative time. Right: the thread.
- < 1024: the thread is full width. A **Conversations** button opens the list in a sheet.
- Thread: messages in order. User messages show the label "You" and plain text. Assistant
  messages use `CopilotAnswer` (full variant). Messages are left-aligned with a role label (no
  chat bubbles).
- Composer (sticky bottom): auto-growing textarea (1–6 lines), placeholder "Ask about exceptions,
  orders, stock or imports…", **Send**. Enter sends. Shift+Enter adds a new line. Limit 1,000
  characters (counter after 800). Under it: "The copilot reads this store's data through read-only
  tools. It can't change data. Check references before acting."

**CopilotAnswer sections** (always in this order. Empty sections are omitted, except Limitations):

| Section | Source (`ai_message.content`) | Rendering |
|---|---|---|
| Summary | `summary` | `text-prose`, no heading |
| Facts | `facts[] {text, refs}` | Bulleted. Each fact ends with reference chips. |
| Metrics | `metrics[] {label, value, unit, formula, refs}` | Two-column list: label, value (tabular). A `sigma` button toggles the formula in mono. |
| Estimates | `estimates[] {text, basis}` | Each with an "est." label and its basis in muted text ("Based on the 28-day sales average"). |
| Recommendations | `recommendations[] {text, rationale}` | Numbered. Rationale in muted text. Header note: "Suggestions from the copilot. Rule-based recommended actions are shown on each exception." |
| Limitations | `limitations[]` | Always shown. If empty: "No specific limitations reported." |
| References | `references[] {type, id, label}` | Chips linking to S-04 / S-06 / S-08 (plain text if the user lacks read permission). |
| Provenance | `generated_by`, `data_window {from,to}`, `ai_message.{created_at, latency_ms, provider, model}`, `ai_tool_call[]` | Footer: "Generated by the deterministic engine" or "Generated by LLM provider · {model}" · "Data Oct 1 – Oct 31 (ET)" · time. **Data used: 3 read-only tools** (disclosure listing tool label, row count, duration, and status. A failed tool shows its error.) |

**Suggested questions** (new conversation empty state). Each fills the composer and does not
auto-send:
"What should I work on first today?" · "Which orders are overdue, and why?" · "Which products could
run out before their restock arrives?" · "Summarise the oversold products and the orders they
affect." · "What went wrong in the last import?" · "How has fulfillment performance changed over
the last 30 days?"

**Prefill entry points.** `?q=` (from Analytics, Order detail and Overview links) and
`?context_type=EXCEPTION&context_id=` (from the S-04 "Ask follow-up"). A prefilled question is
editable and is never auto-sent.

**Data.** `ai_conversation.{id, title, context_type, context_id, updated_at}`,
`ai_message.{role, content, provider, model, latency_ms, created_at}`,
`ai_tool_call.{tool_name, status, row_count, duration_ms, error}`.

**Actions.** Send (`copilot.use`). New conversation (`copilot.use`). Reference links (target
permission). No rename or delete in v1.

| State | Behaviour |
|---|---|
| Initial loading | The conversation list shows a 6-item skeleton. The thread shows 2 message skeletons. |
| Empty | New conversation: heading "Ask about your operations", one sentence ("Answers come from this store's data and list their sources."), then the suggested questions. No conversations yet: the list says "No conversations yet." |
| Populated | Thread. Long answers keep the composer visible (sticky). |
| Search / filtered | N/A in v1 (no conversation search). |
| Validation error | Empty message: Send stays enabled but does nothing, and the textarea announces "Type a question first." Over the limit: "Questions are limited to 1,000 characters." |
| API error with retry | The answer slot shows `ErrorState` (compact): "The copilot couldn't answer. Your question was kept." + **Try again** (resends) + `request_id`. Timeout after 60 s: "The copilot took too long to answer. Try again." |
| Rate limited | 429: warning bar above the composer: "Copilot limit reached (20 requests per minute). Try again in 34 s." Send is `aria-disabled` until the countdown ends. |
| Permission denied | Standard (`copilot.use`). Inside an answer, a tool refusal appears as a Limitations item ("Import data wasn't available to your role."). |
| Success toast | None (the answer is the result). |
| Pending action | The user message appears immediately (optimistic, it is just text). The assistant slot shows "Gathering data…", a `motion-essential` spinner and the elapsed time. If the API returns tool calls before the final answer, they are listed as they complete. A polite live region announces "Answer ready" on completion. Send is disabled while pending (one question at a time). |
| Confirmation dialog / disabled | Send disabled while pending or rate limited, with the reason in its tooltip. |
| Responsive | < 768: the composer is full width and Send is icon-only (`aria-label="Send question"`). Reference chips wrap. Metric formulas scroll horizontally. |

---

## S-15 Audit log

**Purpose.** An immutable record of security-relevant and business-changing actions across the
organization. **Personas.** Owner, Manager, Analyst.

**Layout.** PageHeader "Audit log". Subtitle "Kestrel Commerce · organization-wide · append-only".
FilterBar → DataTable (compact) → Pagination. Rows expand inline (disclosure button in the first
column) to show metadata.

| Column | Source | Align | Hide below |
|---|---|---|---|
| Time (ET) | `audit_log.occurred_at` | left | never |
| Actor | `actor_user_id` → name + email (muted). "System" when null. | left | never |
| Action | `action` → label + code in mono (e.g. "Resolved exception" `exception.resolve`) | left | never |
| Target | `target_type` + `target_id` → link label when resolvable (EXC-ref, order number, import file, "Store settings", member name). Otherwise the type plus a short ID. | left | md |
| Store | `store_id` → store name, "—" for org-level events | left | xl |
| IP | `ip`, only if present in the response (see IA Q-IA-2) | left | xl |
| Request ID | `request_id` (mono, copy button) | left | lg |
| Expanded row | `metadata` as a key–value list (mono values). Secrets are never present (server guarantee). | | |

**Action labels** (prefix groups for the filter): Auth (`auth.login`, `auth.login_failed`,
`auth.logout`, `auth.demo_session`), Exceptions (`exception.acknowledge`, `.start`, `.assign`,
`.resolve`, `.dismiss`, `.reopen`, `.due_date_change`, `.note_add`), Evaluations
(`evaluation.run`), Imports (`import.upload`, `.apply`, `.discard`), Settings (`settings.update`),
Members (`member.role_change`). Unknown actions fall back to the raw code.

**Filters / sort / search.** Date range (default last 7 days, presets 24 h / 7 d / 30 d / custom).
Action group (multi). Actor (combobox). Target type. Store. `q`: exact `target_id` or `request_id`.
Sort: newest first only (append-only log). **Pagination:** 50 (50/100).

**Actions.** Expand row, copy request ID. No export (IA-5).

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | "No audit events in this period". Widen the date range. |
| Populated / search / filtered | Standard. |
| Validation | Date range as S-05. |
| API error / permission denied | Standard (`audit.read`). STAFF never sees the nav item. A pasted URL shows PermissionDenied. |
| Toast / pending / confirmation / disabled | N/A (read-only). |
| Responsive | Table kept with Time pinned. The expanded metadata wraps. |

---

## S-16 Settings

**Purpose.** View and (with permission) change the store's operational thresholds and priority
weights, with each setting linked to the rule it drives. **Personas.** Owner, Manager (edit).
Others (read).

**Layout.** PageHeader "Settings" (subtitle "Kestrel Home & Kitchen"). Single column, max 720 px,
sections separated by 32 px with an `h2` each. Editors see a form. Readers see a definition list
of values with defaults (not disabled inputs) and the note "Only owners and managers can change
settings." When dirty, a sticky bottom **Save bar** appears: "2 unsaved changes · **Discard** ·
**Save changes**".

| Section | Field (`store_settings.*`) | Default | Validation (proposed, must mirror backend) | Helper text |
|---|---|---|---|---|
| Store profile (read-only) | `store.name`, `store.code`, `store.currency`, `store.timezone`, organization | — | — | "Currency and time zone are fixed after the store is created." |
| Fulfillment | `fulfillment_sla_hours` | 48 | integer 1–720 | "Ship-by deadline when the import has none: paid at + this many hours (BR-201)." |
| | `stall_threshold_hours` | 12 | integer 1–720, less than `fulfillment_sla_hours` | "A paid order not yet processing after this many hours is 'stalled' (BR-203)." |
| | `refund_overdue_hours` | 24 | integer 1–720 | "A cancelled, still-paid order becomes 'refund pending' after this many hours (BR-206)." |
| Inventory | `approaching_reorder_factor` | 1.25 | decimal 1.00–3.00, 2 dp | "Approaching reorder point up to reorder point × this factor (BR §2.5)." |
| | `velocity_window_days` | 28 | integer 7–90 | "Days of sales used for average daily units and days of cover (BR-150)." |
| Exceptions | `reopen_window_hours` | 72 | integer 1–720 | "A resolved exception that recurs within this window is reopened instead of recreated." |
| | `evaluation_interval_minutes` | 15 | integer 5–1,440 | "How often scheduled analysis runs." |
| Priority model | `exposure_cap` | 5,000.00 | decimal > 0 (store currency) | "Value at risk at which the exposure component reaches its maximum." |
| | `priority_weights.severity.{CRITICAL,HIGH,MEDIUM,LOW}` | 50 / 35 / 20 / 8 | non-negative integers, descending order | "Points for each severity." |
| | `priority_weights.affected_orders.{per_order, cap}` | 3 / 15 | non-negative integers | |
| | `priority_weights.exposure.cap` | 15 | non-negative integer | |
| | `priority_weights.deadline.{passed, within_24h, within_72h}` | 12 / 8 / 4 | non-negative integers, descending | |
| | `priority_weights.time_unresolved.{per_day, cap}` | 2 / 8 | non-negative integers | |

**Priority model guard.** Live line under the section: "Maximum possible score: 100 of 100"
(= severity CRITICAL + affected cap + exposure cap + deadline passed + time cap). If it is above
100: field-level error "The maximum possible score is 108. It must be 100 or less." (mirrors
PRIORITY_MODEL "sum to at most 100"). **Reset section to defaults** (a ghost button per section)
fills the defaults into the form and still requires Save. The `priority_weights` JSON shape above is
proposed (see the final report).

**Actions**

| Action | Permission | Notes |
|---|---|---|
| Save changes | `settings.manage` | Confirm dialog "Save 2 changes?" listing each change as old → new ("Fulfillment SLA: 48 h → 36 h"), with "Changes apply from the next evaluation. Existing exceptions are re-ranked then. The change is recorded in the audit log." Button **Save changes**. `PUT settings`. |
| Discard | `settings.manage` | Resets the form to the server values. No dialog. |
| Reset section to defaults | `settings.manage` | Form-only. |

| State | Behaviour |
|---|---|
| Initial loading | Section skeletons. |
| Empty | N/A (settings always exist, with defaults). |
| Populated | Form (editors) or definition list (readers). |
| Search / filtered | N/A. |
| Validation error | Field and form-level per DESIGN_SYSTEM §14. Cross-field: "Stall threshold must be shorter than the fulfillment SLA (48 h)." |
| API error with retry | Load failure: standard. Save failure: alert in the save bar area with `request_id`. Values are kept. |
| Conflict | 409 (settings changed by someone else): "Settings were changed by someone else. Reload to see the latest values. Your edits will be lost." **Reload**. |
| Permission denied | Standard (`settings.read`, which all roles hold). |
| Success toast | "Settings saved. They apply from the next evaluation." |
| Pending action | **Save changes** → "Saving…". |
| Confirmation dialog | Save (above). Navigation guard: leaving with unsaved changes → "Discard unsaved changes?" with **Discard** / **Keep editing** (and `beforeunload` for tab close). |
| Disabled action | Readers see no form, so there are no disabled inputs. In demo orgs the read-only note reads "The public demo is read-only." |
| Responsive | Single column at all widths. The save bar is full width with buttons stacked below 400 px. |

---

## S-17 Users & roles

**Purpose.** See who has access to the organization and with which role. Owners change roles.
**Personas.** Owner (manage), Manager (read).

**Layout.** PageHeader "Users & roles". Subtitle "Kestrel Commerce · organization-wide". Tabs
(Radix): **Members** · **Roles and permissions**.

**Members tab.** DataTable (comfortable): Name (`app_user.full_name`, avatar initials) · Email ·
Role (`membership.role`, plain text) · Last sign-in (`last_login_at`, relative, "Never" if null) ·
Status (`app_user.is_active` → Active / Deactivated, with neutral and muted tags) · row menu
(`users.manage`): **Change role…**. A "You" tag appears next to the current user.

**Change role dialog.** A select of the 5 roles, each with a one-line description: Owner ("Full
access, including users"), Manager ("Runs operations. Everything except managing users"), Staff
("Works on exceptions. Reads operational data"), Analyst ("Read-only, plus copilot and audit
log"), Viewer ("Read-only demo access"). Below the select, a "What changes" list compares the
current role with the new one (permissions gained and lost, from the code-defined matrix).
Submit **Change role**. Confirmation is the dialog itself.

**Roles and permissions tab.** A read-only matrix table. Rows are the 18 permissions (label +
code in mono + one-line description). Columns are OWNER, MANAGER, STAFF, ANALYST, VIEWER. Cells
show a check icon with the visually hidden text "Granted", or "—" with "Not granted". Caption:
"Roles are defined in code (ADR-0007) and can't be edited here."

**Actions**

| Action | Permission | Disabled reason |
|---|---|---|
| Change role | `users.manage` | Own row: "You can't change your own role." Last owner: "At least one owner is required." (proposed guard, see the final report) |

**Filters / sort / search.** `q` name or email contains. Role filter. Sort: Name (default), Last
sign-in. Pagination: 25 (organizations are small).

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | Not reachable (the current user is a member). Search with no match: standard no-results. |
| Populated / search / filtered | Standard. |
| Validation error | Same role selected: "Choose a different role." |
| API error / conflict | Standard. 409 when the guard trips server-side shows the API message in the dialog. |
| Permission denied | Standard (`users.read`). Hidden from STAFF, ANALYST and VIEWER navigation. |
| Success toast | "Role changed: Sam Ortiz is now Manager." |
| Pending action | "Changing role…". |
| Confirmation dialog | The Change role dialog (with the "What changes" list). |
| Disabled action | Per the table. Managers see the matrix and list without the row menu. |
| Responsive | < 768: stacked rows (name, email, role · last sign-in). The matrix scrolls horizontally with the permission column pinned. |

User provisioning and deactivation are not in the v1 UI (IA Q-IA-4, Q-IA-5).

---

## P1 screens (summary specifications)

These ship after the P0 set. They reuse P0 components and the standard states.

### S-20 Analytics
**Purpose.** Trend exploration for the Analyst, with a bridge to the copilot. **Layout.**
PageHeader "Analytics" + window selector (Last 7 / 30 / 60 days. Data covers about 60 days.) →
`ChartFrame` grid (2 columns ≥ 1280): Orders placed per day (single series), On-time shipment rate
per week (line, %), Exceptions detected per day by category (stacked columns, 4 categorical slots),
Active exceptions by severity (horizontal bars, single colour, Critical in emphasis), Stock health
distribution (horizontal bars, single colour). Each frame has **Ask the copilot about this chart**,
which opens S-14 with `?q=` and the window. **Data.** `analytics/trends`, `analytics/fulfillment`,
summary. **States.** Standard per chart (independent loading and error). Empty window: "No data
in this period."

### S-21 Evaluation runs
**Purpose.** Observability of detection: when it ran, why and what changed. **Columns.** Started
(ET), Trigger (Scheduled / Manual / Import, linking to the import), As of, Status, Duration, Rules,
Created / Refreshed / Resolved / Reopened / Superseded counts, Triggered by. Row → the inbox
filtered by `evaluation_run_id`. **Action.** Run analysis (`evaluations.run`). **States.**
Standard. A failed run shows its `error` in an expandable row.

### S-22 Data quality
**Purpose.** One place for data problems that are not operational exceptions. **Layout.** Two
sections: **Data-quality exceptions** (active `DATA_ORDER_TOTAL_MISMATCH` and
`DATA_NEGATIVE_ON_HAND`, as a compact inbox table linking to S-04) and **Imports with rejected or
skipped rows** (the last 30 days of `REJECTED` and `COMPLETED_WITH_ERRORS` imports, with
error-code counts linking to S-13). **Permission.** `imports.read` + `exceptions.read`.
**States.** Standard. Empty: success tone, "No data-quality problems found."
