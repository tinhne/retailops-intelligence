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
| RetailOps        | Exceptions / EXC-1042               [Search…  Ctrl K]  [Copilot]  (DV)  |
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
| **Conflict (409)** | **`STALE_VERSION`** (exception commands send `expected_version` = the `version` on screen): a warning toast "Someone else updated EXC-1042. The latest details are now shown. Review them and try again." The exception, its events and notes are refetched automatically. An open dialog stays open with its input, and the next submit sends the new version. If the new status no longer allows the action, the dialog closes and the toast says "EXC-1042 is now {status label}. No change was made." **Other 409 codes** (`EXCEPTION_TRANSITION_NOT_ALLOWED`, `LAST_OWNER`, `IMPORT_HAS_ERRORS`, `IMPORT_PREVIEW_EXPIRED`, `IMPORT_PREVIEW_STALE`, `IDEMPOTENT_REQUEST_IN_PROGRESS`): an alert inside the dialog or form with the API message, input kept, then a refetch. |
| **Permission denied** | `PermissionDenied`: `lock` icon, "You don't have access to {page}", "This page requires the {Permission label} permission. Your role: {Role}." For demo orgs: "This area isn't part of the read-only demo." No retry button. A 403 from a mutation shows an error toast with the same text. |
| **Success toast** | Sonner, bottom-right (bottom-centre below 640 px), 5 s, `role="status"`. Pattern: "{Object} {past-tense verb}" plus an optional single action ("Exception resolved" · **Next in queue**). Errors that need action are inline, not toasts. Toasts only confirm. |
| **Pending action** | The triggering button shows its pending state (spinner, present participle, locked width, `aria-busy`). Other actions on the same record are `aria-disabled` ("Another action is in progress."). Long operations (analysis, import validation and apply) show a status line with elapsed time instead. |
| **Confirmation dialog** | `ConfirmDialog` (Radix AlertDialog). Required for actions that end tracking, change many records or change configuration (listed per screen). The title names the action and object. The body states the consequence. The confirm button repeats the verb. Initial focus goes to **Cancel**. Escape cancels. |
| **Disabled action** | `aria-disabled="true"`, a tooltip and an `aria-describedby` reason (copy in IA §5). Never hidden when the user can see the object. Hidden only when the whole area is unavailable (navigation). |
| **Responsive** | Per DESIGN_SYSTEM §8 and §11.5. Screen-specific notes are listed per screen. |

### 0.4 Data contract

Paths are relative to `/api/v1` and follow `docs/architecture/API_CONVENTIONS.md` (list envelope
`{items, page, page_size, total}`, `sort=±field`, multi-value filters by repeating the parameter,
ranges as `{field}_from` / `{field}_to`, error envelope with `code` and `request_id`). **Status:**
"implemented" means the route exists in `apps/api` today. "API_CONVENTIONS" means it is specified
there but not implemented yet. The generated `packages/contracts` types are authoritative once they
exist.

| Resource | Endpoint | Status | Used by |
|---|---|---|---|
| Current user | `GET /auth/me` → `{user {id, email, full_name}, memberships[] {organization_id, organization_name, is_demo, role, permissions[], stores[] {id, name, code, currency, timezone}}, csrf_token}` | implemented | Shell, guards |
| Auth | `POST /auth/login`, `POST /auth/demo` (both return the `/auth/me` shape), `POST /auth/logout` | implemented | S-01 |
| Role matrix | `GET /roles` → `[{role, permissions[]}]`, any authenticated user. Labels and descriptions come from `status-maps.ts` | implemented | S-17, `PermissionGate` copy |
| Store | `GET /stores/{id}` → `{store, settings, data_freshness}` | implemented | Shell, S-16 |
| Settings | `GET /stores/{id}/settings`, `PATCH /stores/{id}/settings` (partial update) | implemented | S-16 |
| Store members (assignee picker) | `GET /stores/{id}/members` → `{items[] {id, full_name, role, can_work_exceptions}}`, permission `exceptions.read`, no emails | implemented | S-03 (assignee filter), S-04 (assign) |
| Organization members | `GET /organizations/{org_id}/members` (`users.read`) → `{items[] {id (membership), user_id, full_name, email, role, status: ACTIVE \| DEACTIVATED, joined_at, last_login_at}}`, sorted by name, no paging. `POST …/members {email, full_name, role}` (`users.manage`) → `201 {member, temporary_password}`; `409 MEMBER_EXISTS` (already a member here), `409 EMAIL_IN_USE` (account in another organization, O-35). `PATCH …/members/{membership_id} {role?, status?}` (`users.manage`) → the member; `409 LAST_OWNER`, `409 MEMBER_IN_OTHER_ORGANIZATION` (status of an account shared with another organization), `403 OWN_MEMBERSHIP`. Deactivation revokes every session. Other organizations answer 404 | implemented | S-17 |
| Dashboard | `GET /stores/{id}/analytics/dashboard` → `DashboardOut` (see S-02 Data) | implemented | S-02, sidebar badge |
| Trends | `GET /stores/{id}/analytics/trends?date_from&date_to&granularity` → `days[] {date, orders_placed, units, gmv, exceptions_detected, exceptions_resolved, shipped_on_time, shipped_late}`, `partial_last_day` | implemented | S-02 chart, S-20 |
| Exception breakdown | `GET /stores/{id}/analytics/exceptions-breakdown` → per type: active, detected, resolved, median hours to resolve | implemented | S-20, S-22 |
| Exceptions | `GET /stores/{id}/exceptions` (filters `status` (default: the active statuses), `exception_type`, `category`, `severity`, `priority_band`, `assignee` = uuid \| `me` \| `unassigned`, `product_id`, `order_id`, `evaluation_run_id` (exceptions whose `DETECTED` event that run wrote), `due_to`, `q` = reference or title; items include `resolution_code`, `verified_at`, `dismissed_reason`, `closed_at`), `GET …/exceptions/{eid}` (includes `reference`, `version`), `GET …/{eid}/events`, `GET\|POST …/{eid}/notes` | implemented | S-02, S-03, S-04 |
| Exception commands | `POST …/{eid}/acknowledge`, `/start`, `/resolve {resolution_code, resolution_note}`, `/dismiss {dismissal_reason, note}`, `/reopen {reason}`, `/assign {assignee_id}` (claim = assign yourself, unassign = `assignee_id: null`), `PATCH …/{eid}/due-date {due_at, note?}`. Every body also carries `expected_version`. A mismatch returns `409 STALE_VERSION`. The detail response lists `available_actions` and `blocked_actions {action, code, reason}` for the caller | implemented | S-04 |
| Evaluation runs | `POST /stores/{id}/evaluations` ("Run analysis", synchronous, `Idempotency-Key`, returns the run. Status `SKIPPED` when another run holds the store lock), `GET …/evaluations`, `GET …/evaluations/{rid}`. Statuses `RUNNING`, `SUCCEEDED`, `FAILED`, `SKIPPED` | implemented | S-02, S-03, S-13, S-21 |
| Orders | `GET /stores/{id}/orders` (filters `q` = order number, `status`, `payment_status`, `fulfillment_status`, `channel`, `placed_from`, `placed_to`, `overdue`. Items include `line_count`, `is_overdue`), `GET …/orders/{oid}` (lines with reservation, amounts with `expected_total`, `difference`, `has_total_mismatch`, events with `import_id` and `import_filename`, linked exceptions with `reference`) | implemented | S-05, S-06 |
| Products | `GET /stores/{id}/products` (filters `q` = SKU or name substring, `status`, `category`, `supplier_id`, `health` repeatable. Items include `on_hand`, `reserved`, `available`, `health`; `health` is `DATA_ISSUE` when `on_hand < 0`, any status, BR-402a), `GET …/products/{pid}` (stock snapshot, `health`, `approaching_threshold`, `avg_daily_units` and `days_of_cover` as `Estimate {value, basis, window_days}`, `active_exception_count`), `GET /stores/{id}/suppliers`, `GET /stores/{id}/categories` | implemented | S-07, S-08 |
| Inventory | `GET /stores/{id}/inventory/positions` (filters `health` including `DATA_ISSUE`, `category`, `q`), `GET …/inventory/movements` (filters `product_id`, `movement_type`, `source`, `import_id`, `from`, `to`; rows carry `import_filename` and, for shipments, the `order_id` behind the `order_item:{id}` reference, both derived on read), `GET …/inventory/reconciliation` (P1) | implemented | S-08, S-09, S-10 |
| Imports | `POST /stores/{id}/imports` (multipart `import_type`, `file`. Validates synchronously and returns `201` with the import in `VALIDATED` or `REJECTED`), `GET …/imports` (filters `import_type`, `status` repeatable; items carry `can_revalidate`), `GET …/imports/{iid}` (`ImportDetailOut` with `summary` and `file_issues`), `GET …/{iid}/issues` (filters `severity`, `code`, `row_number`), `GET …/{iid}/issues.csv`, `POST …/{iid}/apply {mode, confirm_skipped_rows}` (`Idempotency-Key`), `POST …/{iid}/discard`, `GET …/imports/templates/{import_type}` | implemented | S-11, S-12, S-13 |
| Import retry | `POST …/imports/{iid}/revalidate` (`FAILED → VALIDATING → VALIDATED \| REJECTED` from the stored bytes, synchronous). A failed apply keeps the bytes until the preview's expiry; afterwards `409 IMPORT_CONTENT_MISSING` and `can_revalidate` is false | implemented | S-13 |
| Copilot | `GET\|POST /stores/{id}/copilot/conversations`, `GET …/conversations/{cid}`, `POST …/conversations/{cid}/messages`, `POST /stores/{id}/copilot/exception-summaries {exception_id, refresh?}`, `POST /stores/{id}/copilot/note-drafts` | API_CONVENTIONS | S-04, S-14 |
| Audit | `GET /stores/{id}/audit-logs` (filters `action` prefix, `actor_user_id`, `from`, `to`; items include `actor_name`, the actor's full name without email, `null` for system actions). Store entries plus organization-level entries (`store_id` null, such as `user.*`) | implemented | S-15 |

**JSON documents the investigation UI renders** (JSONB on `operational_exception`, as produced by
`apps/api/app/domains/exceptions/priority.py` and `rules/base.py`). The UI renders them
generically, so all nine rules share one renderer:

```ts
// operational_exception.priority_breakdown
type PriorityBreakdown = {
  components: Array<{
    key: "severity" | "affected_orders" | "exposure" | "deadline" | "age";
    label: string;                 // "Severity", "Affected orders", "Value at risk", "Deadline", "Time unresolved"
    points: number; max_points: number;
    explanation: string;           // rule-authored sentence, e.g. "Gross order-line value at risk 600.00 on a logarithmic scale…"
  }>;
  total: number; uncapped_total: number; band: "P1" | "P2" | "P3" | "P4";
  formula_version: string; as_of: string;
};
// operational_exception.calculation
type Calculation = {
  formulas: string[];              // "available = on_hand − reserved (BR-101)", …
  inputs: Record<string, string | number | boolean | null>;
  outputs: Record<string, string | number | boolean | null>;
  steps?: Array<Record<string, unknown>>;   // optional, rule-specific rows
};
// operational_exception.evidence
type Evidence = {
  facts: Array<{
    key: string; label: string; value: string | number | boolean | null;   // money and dates as strings
    unit: string | null; estimate: boolean;        // estimate → EstimateLabel (BR-152)
    volatile: boolean;                             // changes with time alone (hours overdue)
    source: { type: string; id: string; label: string } | null;
  }>;
  records: Record<string, Array<Record<string, unknown>>>;   // e.g. affected_orders rows
  notes: string[];
};
```

Due-date basis comes from `operational_exception.due_at_overridden` (PRIORITY_MODEL "Exception due
date"): `false` → calculated from severity response time or the business deadline, `true` →
manual override. On reopen, `due_at` is recomputed from the reopen time and the override is
cleared (orchestrator decision).

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

**Data.** `POST /auth/login {email, password}` (returns the `/auth/me` shape). `POST /auth/demo` creates a
`VIEWER` session in the demo organization. Redirect: `next` (same-origin paths only, otherwise
`/`). For demo: `/s/{demoStoreId}/overview?tour=1`.

**Actions.** Sign in (public). Explore / Start the demo (public).

| State | Behaviour |
|---|---|
| Initial loading | If a session cookie exists, `GET /auth/me` runs first. While pending, only the wordmark shows (no form flash). Success redirects to `/`. |
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
Last evaluation 9:45 AM EDT · Scheduled · Succeeded
Last imports: Orders Oct 31, 8:02 AM EDT · Order items 8:04 AM · Inventory adjustments Oct 30, 6:15 PM

+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+
| Active      | | Unassigned  | | Past due    | | Overdue     | | Awaiting    | | On-time     |
| exceptions  | |             | | exceptions  | | orders      | | shipment    | | ships, 30 d |
| 23          | | 6           | | 4           | | 7           | | 41          | | 94.1%       |
| 5 P1 · 9 P2 | | 2 are P1    | | due passed  | | $1,284.50   | | paid, not   | | 412 of 438  |
|             | |             | |             | | gross value | | shipped     | | on time     |
+-------------+ +-------------+ +-------------+ +-------------+ +-------------+ +-------------+

+------------------------------------------------------------+ +----------------------------+
| Needs attention                       Open triage queue (7) | | Active exceptions by       |
|------------------------------------------------------------| | category                   |
| ▮▮▮▮ P1 81 [■ Critical] Oversold: Enamel Dutch Oven 5.5 qt… | |               Count  Order |
|            EXC-1042 · Due in 3h 55m · Unassigned           | |                      value |
| ▮▮▮▮ P1 79 [■ Critical] Fulfillment overdue: KHK-10391      | |                     at risk|
|            EXC-1037 · Overdue 3d · Dana Whitfield          | | Inventory        9  $612.00|
| ▮▮▮▯ P2 60 [▲ High]     Fulfillment overdue: KHK-10482      | | Fulfillment      8 $1,284.50|
|            EXC-1029 · Overdue 6h · Sam Ortiz               | | Payment          3  $412.60|
| …  8 rows                                                  | | Data quality     3        — |
|                                       View all active (23) | | Order value at risk (gross,|
+------------------------------------------------------------+ | per category). An order can|
                                                               | count in several categories|
                                                               +----------------------------+
                                                               | Stock health (active SKUs) |
                                                               | Oversold                 2 |
                                                               | Out of stock             4 |
                                                               | Below reorder point     11 |
                                                               | Approaching reorder pt.  7 |
                                                               | Healthy                 96 |
                                                               | Data issue               1 |
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
2. **Freshness strip** (`text-sm`, muted, two lines): the most recently started evaluation run
   (time, trigger, status) and the latest applied import per type. Status variants: `RUNNING` →
   "Analysis running · started 9:52 AM EDT". `FAILED` → warning tone "The last evaluation failed at
   9:45 AM EDT. No exceptions were changed by it." `SKIPPED` → muted "The last scheduled run was
   skipped because another analysis was running." If the latest orders import is more than 24 h
   old: warning tone "Order data was last imported 2 days ago. Figures may be out of date."
   (text and icon).
3. **KPI row**: 6 `KpiCard`s. Grid: 6 columns ≥ 1280, 3 columns 768–1279, 2 columns < 768. Each
   card links to the list behind it.
4. **Main grid** (≥ 1280: 2/3 + 1/3. Below: stacked). Left: **Needs attention**. Right: **Active
   exceptions by category** (count and order value at risk per category), **Stock health**.
5. **Shipments per day** chart (full width).
6. **Recent imports** (last 3).

**Exposure is never totalled.** One order can appear in several exceptions (for example an
oversold line and the same order's overdue fulfilment), so a grand total would double-count. The
category card shows value at risk **per category only**, captioned "Order value at risk (gross,
per category). An order can count in more than one category. Not a measure of loss (BR-404)."
There is no total row and no value-at-risk KPI. Data-quality exceptions carry no exposure, so
their cell shows "—".

### Data (`GET /stores/{id}/analytics/dashboard` → `DashboardOut`, unless noted)

| UI element | Source |
|---|---|
| Freshness: last evaluation | `data_freshness.last_evaluation_run.{trigger, status, as_of, started_at, finished_at}` |
| Freshness: last imports | `data_freshness.imports[].{import_type, status, applied_at}` |
| Active exceptions | `active_exceptions.total`, `active_exceptions.by_band.{P1, P2}` |
| Unassigned | `active_exceptions.unassigned` (secondary "2 are P1" from a `page_size=1` count query `assignee=unassigned&priority_band=P1`; the list returns active statuses when `status` is omitted) |
| Past due exceptions | `active_exceptions.past_due` (active with `due_at < as_of`) |
| Overdue orders | `orders.overdue_count` (BR-202), secondary `orders.overdue_value` labelled "gross value" |
| Awaiting shipment | `orders.awaiting_shipment` (PAID, PROCESSING, READY_TO_SHIP) |
| On-time shipments, 30 d | `on_time_shipment_30_days.{on_time_rate_pct, on_time, shipped_with_deadline}`. Null rate → "—" with "No shipments with a deadline in the last 30 days". The tooltip states the definition: "Shipped in the window with a ship-by date. On time means shipped_at ≤ ship_by." |
| Needs attention | `attention[]` (top 8) → `reference, title, severity, status, priority_band, priority_score, due_at, is_past_due, assignee_name` |
| Triage count | `GET /stores/{id}/exceptions?status=OPEN&status=REOPENED&page_size=1` → `total` |
| Active by category: count | `active_exceptions.by_category.{INVENTORY, FULFILLMENT, PAYMENT, DATA_QUALITY}` |
| Active by category: order value at risk | `active_exceptions.exposure_by_category.{…}` = Σ `exposure_amount` of active exceptions per category (implemented 2026-11-01). Never summed client-side. `DATA_QUALITY` shows "—" because data-quality findings claim no exposure (EXCEPTION_CATALOG). |
| Stock health | `inventory.{oversold, out_of_stock, below_reorder_point, approaching_reorder_point, healthy, data_issue}` (ACTIVE products; the six counts add up to `active_products`). `data_issue` counts products with `on_hand < 0`, which are in none of the availability classes (BR-402a). It is the sixth row, "Data issue" (attention tone, `database` icon), after Healthy, and links to `/inventory?health=DATA_ISSUE`. |
| Shipments chart | `GET /stores/{id}/analytics/trends?days=30` (daily, store-local days, the last one partial) → `days[].{date, shipped_on_time, shipped_late}`, `partial_last_day` |
| Recent imports | `GET /stores/{id}/imports?page_size=3` |

### Actions

| Action | Permission | Disabled reason |
|---|---|---|
| Run analysis | `evaluations.run` | Missing: "You need the Run analysis permission. Ask an owner or manager." Demo: "The public demo is read-only." While a run is in progress: "An analysis is already running." |
| KPI card links, list rows, category rows, health rows | the target route's permission | Without it, the card renders as plain text (not a link) |

**KPI links** (rendered only once the target page exists and the role may open it; until then the card is plain text):
Active → `/exceptions?view=active`. Unassigned → `/exceptions?view=unassigned`.
Past due → `/exceptions?view=active&due=overdue&sort=due_at`. Overdue orders →
`/orders?overdue=true&sort=ship_by`. Awaiting shipment → `/orders?status=PAID&status=PROCESSING&status=READY_TO_SHIP`.
On-time → `/analytics` (P1) or no link in P0. Category row → `/exceptions?view=active&category={CATEGORY}`.
Health row → `/inventory?health={HEALTH}`.

**Filters / sort / search / pagination.** None on this page (fixed windows). Global search is in
the top bar.

| State | Behaviour |
|---|---|
| Initial loading | Standard. 6 KPI skeletons, 8-row list skeleton, 2 side-card skeletons, a chart block (240 px). |
| Empty (no data ever imported) | KPI row and grid are replaced by one `EmptyState`: "No data yet". "Import products first, then inventory adjustments, orders and order items, to start detecting exceptions." Action **Start an import** (`imports.run`). Otherwise: "Ask an owner or manager to import data." Secondary link: **Download CSV templates**. |
| Empty (data, no active exceptions) | Needs attention shows a success-tone EmptyState: "Nothing needs attention", "The last evaluation at 9:45 AM EDT found no active exceptions." |
| Populated | As wireframed. |
| Search / filtered | N/A. |
| Validation error | N/A. |
| API error with retry | Per region. The KPI row, attention list, category and health cards fail as one unit (single dashboard call). The chart and recent imports fail independently. |
| Permission denied | Standard (all roles hold `dashboard.read`). Regions whose permission is missing (for example `imports.read` for Recent imports) are omitted. |
| Pending action | **Run analysis** → "Running analysis…". `POST /stores/{id}/evaluations` with an `Idempotency-Key` (generated when clicked, reused on retry). The request is synchronous and returns the run. |
| Success toast | Run `SUCCEEDED` → "Analysis complete: 2 new, 5 refreshed, 1 resolved, 0 reopened" (from the run's `counts`) · **View exceptions**. Then refetch the dashboard and lists. |
| Run skipped | Returned run has `status = SKIPPED` (another run held the store lock) → info toast "An analysis is already running. Results will appear when it finishes." The dashboard refetches once after 15 s. |
| Run failure | Run `status = FAILED` → error toast "Analysis failed. No exceptions were changed." with `request_id`. The freshness strip shows the failure line. |
| Confirmation dialog | None (a manual evaluation is idempotent and changes no business data). |
| Disabled action | Run analysis per the table above. |
| Responsive | < 768: KPIs in 2 columns. Needs attention uses stacked rows. Side cards stack below. The category card becomes a 3-column table (category, count, value at risk). The chart is 200 px high with 7-day labels. |

---

## S-03 Exceptions inbox

**Purpose.** The work queue: see, filter and pick the next exception to handle, in priority
order. **Personas.** Operations Manager (triage), Operations Staff ("Assigned to me").

### Wireframe (≥ 1280 px, content area)

```text
Exceptions                                     Last evaluation 9:45 AM EDT (5m ago)  [Run analysis]
[All active 23]  [Triage 7]  [Assigned to me 2]  [Unassigned]  [Closed]
+------------------------------------------------------------------------------------------------+
| [Q Search reference or title ] [Severity ▾] [Priority ▾] [Status ▾] [Category ▾] [Type ▾]     |
| [Assignee ▾] [Due ▾]                                 Sort [Priority ▾]  Density [≡]  23 results |
| Severity: Critical, High  ×    Clear all                                                        |
|------------------------------------------------------------------------------------------------|
| Priority    Exception                                Severity     Status       At risk  Assignee   Due          |
|------------------------------------------------------------------------------------------------|
| ▮▮▮▮ P1 81  Oversold: Enamel Dutch Oven 5.5 qt, Sage  [■ Critical] [○ Open]     $600.00 Unassigned Due in 3h 55m |
|             EXC-1042 · Oversold · KHK-DO55-SGE · 4 orders                                       |
| ▮▮▮▮ P1 79  Fulfillment overdue: KHK-10391            [■ Critical] [◉ In progress] $96.00 Dana W.  Overdue 3d |
|             EXC-1037 · Fulfillment overdue · KHK-10391 · 1 order                                |
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
| `active` | `active=true` (OPEN, ACKNOWLEDGED, IN_PROGRESS, REOPENED) | `-priority_score,due_at` | all | OWNER, MANAGER, ANALYST, VIEWER |
| `triage` | `status=OPEN&status=REOPENED` | `-priority_score` | all | |
| `mine` | `active=true&assignee_id=me` | `-priority_score` | users with `exceptions.work` | STAFF |
| `unassigned` | `active=true&assignee_id=unassigned` | `-priority_score` | all | |
| `closed` | `status=RESOLVED&status=DISMISSED` | `-first_detected_at` | all | |

### Data (table columns)

| Column | Source | Align | Hide below |
|---|---|---|---|
| Priority | `priority_band`, `priority_score` → `PriorityIndicator` | left | never |
| Exception | `title` (primary link to S-04, max 2 lines). Second line, muted: `reference` (Inter 500, e.g. `EXC-1042`) · type label (from `exception_type`) · `primary_entity.label` · `affected_order_count` orders | left | never |
| Severity | `severity` → `SeverityBadge` | left | never (icon-only pill < 1024 with the label in tooltip and accessible name) |
| Status | `status` → `ExceptionStatusPill` | left | never |
| At risk | `exposure_amount` → `Money` ("—" when 0, i.e. no order value at risk) | right | lg |
| Assignee | `assignee.full_name` (avatar initials 20 px + name) or "Unassigned" (muted) | left | md |
| Due | `due_at` → `formatDue` (overdue in `--overdue-fg` with `alarm-clock`) | left | never |
| Last detected | `last_detected_at` → `RelativeTime` (full date in the tooltip) | left | xl (column hidden by default, toggle in Density menu) |

**Density.** A **Density** menu next to Sort (≥ 768 px; stacked rows below have no density)
offers Comfortable (44 px rows, default) and Compact (36 px rows), plus a **Last detected
(wide screens)** column toggle. Both choices are per-viewer preferences kept in `localStorage`
(`ro.exceptions.compact`, `ro.exceptions.lastDetectedColumn`), not in the URL.

In the **Closed** view, Due is replaced by **Closed** (`resolved_at`, or the dismissal event time),
and the status pill uses the RESOLVED forms from DESIGN_SYSTEM §3.5: "Resolved — awaiting
verification" (manual, `verified_at` null), "Verified", "Resolved · condition cleared",
"Superseded", or "Dismissed" (with the `dismissed_reason` label in the tooltip). The resolution
code label ("Stock replenished") is shown in the muted second line. Rows awaiting verification
are intentionally not shown as successes.

### Actions

| Action | Permission | Notes |
|---|---|---|
| Open exception | `exceptions.read` | Whole row (stretched link). |
| Run analysis | `evaluations.run` | Same as S-02. |
| Row actions | none in v1 | Lifecycle actions live on S-04 only. This keeps every transition next to its evidence (deterministic first). Bulk actions are out of scope (no bulk API). |

### Filters / sort / search

| Control | Param | Options |
|---|---|---|
| Search | `q` | Matches the exception `reference` (`EXC-1042`, or just `1042`) and the title (contains, case-insensitive), server-side. 300 ms debounce. `/` focuses the field. |
| Severity | `severity` | Critical, High, Medium, Low (multi) |
| Priority | `priority_band` | P1, P2, P3, P4 (multi) |
| Status | `status` | Statuses allowed by the current view (multi) |
| Category | `category` | Inventory, Fulfillment, Payment, Data quality |
| Type | `exception_type` | The 9 catalog types, grouped by category, with labels: Oversold, Oversell risk, Out of stock, Below reorder point, Fulfillment overdue, Stalled after payment, Refund pending, Order total mismatch, Negative on-hand |
| Assignee | `assignee_id` | `me`, `unassigned`, then members from `GET /stores/{id}/members` with `can_work_exceptions = true` (searchable combobox, name and role, no emails) |
| Due | `due` (UI) → `due_to` (API) | Overdue → `due_to={now}`. Due within 24 h → `due_to={now + 24 h}`. Any → omitted. The UI keeps the relative choice in the URL and computes `due_to` at request time. |
| Detected in run (hidden) | `evaluation_run_id` | Set by "View new exceptions" on S-13 (and S-21 later). The API returns the exceptions whose `DETECTED` event that run wrote, within the view's statuses. Shown as a removable chip "From evaluation run Oct 31, 8:05 AM EDT" (the run's `started_at`; "From an evaluation run" until it loads). Clear all and the view tabs remove it. |
| Related entity (hidden) | `order_id`, `product_id` | Set by links from S-06/S-08. Shown as a chip "Order KHK-10482". |
| Sort | `sort` | The sorts the API accepts (API_CONVENTIONS §12.6): Priority (`-priority_score`), Due soonest (`due_at`), Newest (`-first_detected_at`), Severity (`severity`) |

**Pagination.** Server-side, 25 per page (25/50/100). **Refresh.** Refetch on window focus and
every 60 s while the tab is visible. Keyboard focus stays on the same exception ID across refetches.
**Queue.** The rows on screen (IDs and references, in order) and the list URL are kept per tab in
`sessionStorage`; S-04 steps through them with Previous / Next in queue.

| State | Behaviour |
|---|---|
| Initial loading | Standard. The tabs render immediately, without counts. |
| Empty (no exception ever, no evaluation run) | "No exceptions detected yet". "Exceptions appear after an analysis runs on imported data." Action **Run analysis** (`evaluations.run`), or link **Go to Imports**. |
| Empty view | Triage: success tone, "Triage queue is clear", "No open or reopened exceptions.", link **View all active**. Mine: "Nothing is assigned to you", "Claim an unassigned exception or check with your manager.", link **View unassigned**. Unassigned: "Every active exception has an owner." Closed: "No resolved or dismissed exceptions yet." |
| Populated | As wireframed. |
| Search results | Standard. When `q` exactly equals a reference (`EXC-1042` or `1042`) and one row matches, a hint row says "Press Enter to open EXC-1042". |
| Filtered / no results | Standard: "No exceptions match these filters". |
| Validation error | Standard URL-param handling. |
| API error with retry | Standard, inside the card. Tabs and filters stay usable. |
| Permission denied | Standard (`exceptions.read`). The `mine` view for users without `exceptions.work` falls back to `active` with an info toast: "Assigned to me is available to roles that work on exceptions." |
| Success toast | Run analysis only (see S-02). |
| Pending action | Run analysis only. |
| Confirmation dialog | N/A. |
| Disabled action | Run analysis per permission. |
| Responsive | < 768: stacked rows (DESIGN_SYSTEM §11.5). Tabs scroll horizontally. Search stays inline; the other filters collapse into "Filters (n)" (n = filters in use), which opens a bottom sheet of checkbox groups (Severity, Priority, Status, Category, Type) and selects (Assignee, Due) editing a draft: **Apply** writes the draft to the URL and closes the sheet, **Reset** clears the draft only. Sort is a select next to it. No Density menu. 768–1279: Assignee and At risk hidden per the column table. |

---

## S-04 Exception detail / investigation

**Purpose.** Everything needed to understand, decide on and move one exception through its
lifecycle: what was detected, why it ranks where it does, the evidence and its sources, who is
affected, what happened so far, and (separately labelled) what the copilot makes of it.
**Personas.** Operations Staff and Manager (act). Owner, Analyst and demo viewer (read).

### Wireframe (≥ 1280 px, content area)

```text
Exceptions / EXC-1042                                          [‹ Previous] [Next in queue ›]
Oversold: Enamel Dutch Oven 5.5 qt, Sage
EXC-1042 [⧉] · Oversold · Inventory · Product KHK-DO55-SGE ↗ · Rule INV-OVERSOLD@1
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
| How this was detected                     As of 9:45 AM EDT  | | [Regenerate] [Ask follow-up]|
| available = on_hand − reserved (BR-101)                      | +-----------------------------+
| shortage = −available                                        | | Details                     |
| exposure = Σ uncovered_quantity × unit_price (BR-404)        | | Entity    KHK-DO55-SGE ↗    |
| Inputs   on_hand 18 · reserved 22 · committed_lines 19       | | Category  Inventory         |
| Outputs  available −4 · shortage 4 · exposure $600.00        | | Detected  Scheduled run     |
+--------------------------------------------------------------+ | Detections 1 · Reopens 0    |
| Evidence                                                     | | ▸ Technical details         |
| Fact               Value                  Source             | +-----------------------------+
| On hand            18                     Inventory balance ↗|
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
  navigation on the same row ("2 of 25", **Previous** / **Next in queue**: neighbours on the
  remembered list page, kept per tab by S-03; not rendered when the person arrived without a list
  or the exception is not on that page; at either end of the page the missing direction stays
  visible but `aria-disabled` with "This is the first/last exception on that page of the list."),
  title (`h1`, `operational_exception.title`), meta line, status row, detection line, then the
  **ExceptionActionBar** (wraps under the status row), with **How resolution works** (C-63) next to
  it for VIEWER only.
- **Lifecycle banner** (conditional, directly under the header):

| Condition | Tone | Copy |
|---|---|---|
| `RESOLVED`, manual, `verified_at` null | info | Status pill "Resolved — awaiting verification". Banner: "Resolved by {name} at {time} ({resolution label}). Awaiting verification: RetailOps re-checks the condition after the next import completes, or after 24 h, whichever comes first. If it is still present then, this exception reopens." |
| `RESOLVED`, manual, `verified_at` set | success | Status pill "Verified". Banner: "Verified at {time}. The condition was no longer detected after {name} resolved it." |
| `RESOLVED`, `CONDITION_CLEARED` | success | "Resolved automatically at {time}. The condition cleared during an evaluation." |
| `RESOLVED`, `SUPERSEDED` | neutral | "Superseded at {time} by {reference} ({type label}). Work continues there." + link |
| `REOPENED`, `VERIFICATION_FAILED` | warning | "Reopened at {time}: verification failed. The condition was still present after the data was refreshed (or 24 h after {name} resolved it). The due date was recalculated from the reopen time." |
| `REOPENED`, `RECURRED_WITHIN_WINDOW` | warning | "Reopened at {time}. The condition came back within {reopen_window_hours} h of being resolved. The due date was recalculated from the reopen time." |
| `REOPENED`, manual | warning | "Reopened by {name} at {time}: {reason}. The due date was recalculated from the reopen time, and any manual due date was cleared." |
| `DISMISSED` | muted | "Dismissed by {name} at {time} · {`dismissed_reason` label}: {note}" |
| `previous_occurrence_id` set | neutral (secondary line) | "This condition occurred before: {reference}, resolved {date}." + link |

- **Main column** (≥ 1280: fluid, aside 360 px. Below: single column), sections in this order:
  1. **Recommended action**: callout (neutral tone, `list-checks` icon), label "Recommended action ·
     rule {rule_id}", text `recommended_action` in `text-prose`. Labelled as rule-authored. It is
     never mixed with AI output.
  2. **Why this priority**: `PriorityBreakdown` (all five components, points / max, meters, total
     and band threshold, due-date basis line, limitation note with a popover listing the
     PRIORITY_MODEL limitations).
  3. **How this was detected**: `CalculationBlock`: the rule's `formulas` (mono, in order), then
     `inputs` and `outputs` as labelled values formatted by type, then any rule-specific `steps`
     rows. The header shows the rule ID and the evaluation's `as_of`.
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
     at, verified at), dismissed reason. Collapsible **Technical details**: `dedup_key`, full
     `id` (copy), `evaluation_run_id`, `version`.
- **Below 1280 px:** single column in this order: header → banner → Recommended action → Why this
  priority → How this was detected → Evidence → Affected orders → **AI investigation** → Activity
  → Details. Deterministic sections always come first. An "On this page" select (768–1279) or
  menu (< 768), placed under the lifecycle banner, jumps to the sections the page rendered
  (`#priority`, `#calculation`, `#evidence`, `#affected` when shown, `#activity`, `#details`;
  `#ai` joins once the AI panel exists): it scrolls the section into view and moves focus to its
  heading.

### Data

| UI element | Source |
|---|---|
| Title, type, category, rule | `operational_exception.{title, exception_type, category, rule_id}` |
| Reference | `operational_exception.reference` (`EXC-1042`), shown verbatim |
| Primary entity | `exception_entity_link (role=PRIMARY)` → `{entity_type, entity_id, label}` |
| Severity, priority | `severity`, `priority_score`, `priority_band`, `priority_breakdown.components[] {key, label, points, max_points, explanation}` (§0.4) |
| Status, assignee, due | `status` (+ `resolution_code`, `verified_at` for the RESOLVED label), `assignee_id` → member name, `due_at`, `due_at_overridden` ("Due date set manually" note) |
| Detection line | `first_detected_at`, `last_detected_at`, `detection_count` |
| Recommended action | `recommended_action` (deterministic, rule-authored) |
| Calculation | `calculation.{formulas[], inputs{}, outputs{}, steps[]?}` (§0.4) |
| Evidence | `evidence.facts[] {key, label, value, unit, estimate, volatile, source}` (§0.4). `estimate` facts get `EstimateLabel`. `evidence.notes[]` render as a bullet list under the table. The Source cell links by `source.type`: `product` and `inventory_balance` → S-08 `/products/{id}`, `order` → S-06, `data_import` → S-13, each only with the page's permission; `supplier` and other types stay text; no source reads "Calculated". |
| Affected orders | `evidence.records.affected_orders[]` (order, paid at, ship by, uncovered quantity, value at risk; BR-402). The order number links to S-06 through the row's `order_id` (with `orders.read`). Other `evidence.records` groups render as titled sub-tables with the same component, plus a Source column (same links) when their rows carry a `source` and no order number. |
| Lifecycle banner | `status`, `resolution_code`, `resolution_note`, `resolved_by`, `resolved_at`, `verified_at`, `dismissed_reason`, `superseded_by_id`, `previous_occurrence_id`, the latest `REOPENED` event payload `reason` |
| Timeline | `GET …/events` → `exception_event.{event_type, actor_type, actor_id, from_status, to_status, payload, occurred_at, evaluation_run_id}`. `GET …/notes` → `exception_note.{author_id, body, source, created_at}` |
| AI panel | Latest `ai_conversation` with `context_type=EXCEPTION, context_id={id}` for the current user, plus its last `ai_message.content` (structured answer) |
| Version | `operational_exception.version`. Sent as `expected_version` with every command. A mismatch returns `409 STALE_VERSION` (§0.3 Conflict). |

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
| `VERIFIED` | "Verified: the condition was no longer detected" |
| `REOPENED` | "Reopened: {reason label}. Due date recalculated to {new due}" |
| `SUPERSEDED` | "Superseded by {reference}" |

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
| Dismiss… | `POST /dismiss {reason, note, expected_version}` (stored as `dismissed_reason`) | `exceptions.manage` | "Dismissing requires the Manage exceptions permission." |
| Reopen… | `POST /reopen {reason, expected_version}` | `exceptions.manage`, status `RESOLVED` or `DISMISSED` | "Reopening requires the Manage exceptions permission." |
| Assign / reassign / unassign | `POST /assign {assignee_id, expected_version}`, `POST /unassign {expected_version}` | `exceptions.assign`. The assignee must be a member with `can_work_exceptions` | Field renders read-only text, with the reason on focus |
| Change due date | `POST /set-due-date {due_at, reason, expected_version}` | `exceptions.assign` (sets `due_at_overridden`, audited) | Edit button `aria-disabled` |
| Add note | `POST /notes {body, source:"USER"}` | `exceptions.work` | The composer is replaced by "Notes can be added by people who work on exceptions." (demo: read-only copy) |
| Draft with copilot | `POST /stores/{id}/copilot/note-drafts {exception_id}` | `copilot.use` (saving still needs `exceptions.work`) | "Saving notes requires the Work on exceptions permission." on **Save note** |
| Generate investigation / Regenerate | `POST /stores/{id}/copilot/exception-summaries {exception_id, refresh}` | `copilot.use` | Panel shows a permission message |

**Dialogs**

| Dialog | Fields (Zod) | Copy |
|---|---|---|
| **Resolve exception** | `resolution_code`: select, required, one of STOCK_REPLENISHED "Stock replenished", ORDER_FULFILLED "Order fulfilled", REFUND_ISSUED "Refund issued", DATA_CORRECTED "Data corrected", CUSTOMER_CONTACTED "Customer contacted", FIXED_IN_SOURCE_SYSTEM "Fixed in source system", OTHER "Other". `resolution_note`: textarea, required, trimmed length 10–4,000 ("6 / 10 minimum") | Info callout: "After you resolve, this exception shows Resolved — awaiting verification. RetailOps re-checks the condition after the next import completes, or after 24 h. If the condition is still present then, the exception reopens (verification failed). For long-running work, such as waiting for a delivery, keep it In progress. It resolves automatically when the condition clears." Submit: **Resolve exception** |
| **Dismiss exception** | `reason` (stored as `dismissed_reason`): radio group, required: FALSE_POSITIVE "False positive: the condition isn't real", ACCEPTED_RISK "Accepted risk: we know and accept it", DUPLICATE "Duplicate: tracked elsewhere", NOT_ACTIONABLE "Not actionable: nothing we can do". `note`: required, trimmed length 10–4,000 ("6 / 10 minimum") | "Dismissed exceptions stop being tracked. If the condition clears and comes back later, a new exception is created." Submit: **Dismiss exception** |
| **Reopen exception** | `reason`: textarea, required, trimmed length ≥ 1, ≤ 4,000 | "The exception returns to Reopened and appears in the triage queue." Submit: **Reopen exception** |
| **Change due date** (popover) | `due_at`: date + time in the store zone, required, must be in the future. `reason`: required, trimmed length ≥ 1 | Shows "Calculated: Oct 31, 1:45 PM EDT (Critical, 4 h response)" and, under the reason field, "A manual due date is kept until the exception is reopened." Submit: **Update due date** |
| **Assign** (popover combobox) | Searchable list: "Assign to me" (first, if the user can work), then `GET /stores/{id}/members` entries with `can_work_exceptions = true` (name + role, no emails), then "Remove assignee" | Selecting submits immediately. The field shows a pending spinner. |

The Resolve, Dismiss and Reopen dialogs are the confirmation for those actions. No second dialog
follows.

### Filters / sort / search / pagination
Timeline filter: All / Notes (client-side over the loaded events). Events load 50 at a time with
**Show earlier activity**. Affected orders: up to 50 rows, sorted by `paid_at` (FIFO, as allocated). If
the evidence lists more, a muted line says "Showing 50 of {n} affected orders".

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
| Conflict (409) | `STALE_VERSION`: standard (§0.3). Warning toast "Someone else updated EXC-1042. The latest details are now shown. Review them and try again.", automatic refetch, open dialog kept with its input. `EXCEPTION_TRANSITION_NOT_ALLOWED` (for example someone already resolved it): the toast names the new status and the action bar re-renders from the refetched state. |
| Changed by others | Refetch on focus and every 60 s. When `status` or `assignee` changed since the last render and the user has no dialog open: info toast "Updated by {actor}: status is now In progress". |
| Success toast | Acknowledge → "Exception acknowledged". Start → "Work started. Assigned to you." Claim → "Assigned to you". Resolve → "EXC-1042 resolved. Awaiting verification after the next import, or within 24 h." · **Next in queue**. Dismiss → "Exception dismissed" · **Next in queue** (the action appears only when the queue has a next exception). Reopen → "Exception reopened". Assign → "Assigned to {name}". Due → "Due date updated". Note → no toast (the note appears in the timeline, which is announced via a polite live region). |
| Pending action | Standard. The whole action bar is `aria-disabled` while one transition is in flight. |
| Confirmation dialog | Resolve, Dismiss, Reopen (the form dialogs above). |
| Disabled action | Per the action table. In demo orgs, every mutating control shows "The public demo is read-only." In addition, **How resolution works** (C-63, a popover with the lifecycle explainer and live examples fetched when it opens) is shown next to the action bar for VIEWER only. |
| Responsive | < 768: the action bar becomes a bar fixed to the bottom of the screen (`--z-sticky-bar`, 64 px, `--card` with a top border; the page keeps 80 px of bottom padding for it) holding the primary action (large, fills the row) and **More** (a bottom sheet titled "Actions" listing the secondary and More-menu actions; refused ones stay listed, `aria-disabled`, with their reason under the label). Choosing a dialog action closes the sheet and opens the dialog. Status pills wrap to two lines. Evidence and affected-orders tables scroll horizontally with the first column pinned. The PriorityBreakdown meter column is hidden below 400 px (points stay). |

---

## S-05 Orders list

**Purpose.** Find orders and see their three status axes and deadlines. Linked exceptions are on S-06.
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
| Lines | `line_count` | right | xl |
| Total | `total` → Money | right | never |

**Actions.** Open order (`orders.read`). No create, edit or delete (IA-5).

**Filters / sort / search.** Search `q`: order number or customer reference (customer references are
opaque IDs per BR-505, and are searchable here only, never in global search, IA §8). Status (multi, repeated `status`, grouped by status group). Payment status. Fulfillment
status. Channel. Placed (`placed`: presets Today, Last 7 days, Last 30 days, Last 60 days, and
Custom range. A custom range keeps store-local days in the URL, `placed=custom&placed_from=YYYY-MM-DD&placed_to=YYYY-MM-DD`,
either end optional, edited with two date inputs under the filter row; the API receives the start
day's store midnight as `placed_from` and the midnight after the end day as `placed_to`, which is
exclusive. The chip reads "Placed: Oct 1 – Oct 31", "From Oct 1" or "Until Oct 31").
**Overdue only** toggle (`overdue=true`). Sort:
the sorts `OrderSort` accepts, default Placed newest (`-placed_at`), also Placed oldest, Ship by
soonest (`ship_by`), Total highest (`-total`) and Order number.
**Pagination:** 25 (25/50/100).

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | "No orders yet". "Orders come from CSV imports (orders.csv, then order_items.csv)." Action **Import orders** (`imports.run`). |
| Populated / search results / filtered | Standard. The Overdue-only empty result uses a success tone: "No overdue orders". |
| Validation error | Custom date range: "End date must be on or after start date." under the inputs (`role="alert"`, the end input `aria-invalid`); the reversed range is not applied, so the list keeps its last valid range. A reversed or malformed range in a shared link is dropped like any unknown filter (§0.3). |
| API error / permission denied | Standard (`orders.read`). |
| Success toast / pending / confirmation / disabled | N/A (read-only screen). |
| Responsive | < 768: stacked rows. Line 1: order number + Status pill + total. Line 2: placed · payment · fulfillment. Line 3: ship by with the overdue flag. |

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
   (recorded)**, plus "Lines total" (`amounts.lines_total`). When `amounts.has_total_mismatch` is
   true (BR-205): extra rows "Expected total {amounts.expected_total}" and "Difference
   {amounts.difference}" in `--tone-danger-fg`, plus a link to the `DATA_ORDER_TOTAL_MISMATCH`
   exception by its reference.
6. **Exceptions** (`exceptions.read`): compact list of linked exceptions (active first, then the
   last 5 closed): reference (`EXC-1042`), severity, title, status (with the RESOLVED forms from
   DESIGN_SYSTEM §3.5), and role ("About this order" for PRIMARY, "Affects this order" for
   AFFECTED).
7. **Status history** (`OrderTimeline`): each `order_event` as "Paid → Shipped, via Processing,
   Ready to ship" (`skipped_statuses`), source tag Import / User / System, time, and for imports
   the file name (`import_filename`, mono) linking to S-13 with `imports.read`, plain text
   otherwise.

**Data.** `GET /stores/{id}/orders/{oid}` (`OrderDetail`): order fields with `ship_by_source`,
`lines[] {line_number, product_id, sku, product_sku, product_name, quantity, unit_price,
line_discount, line_total, reservation {status, quantity}}`, `amounts {subtotal, discount_total,
shipping_total, tax_total, total, lines_total, expected_total, difference, has_total_mismatch}`,
events `{from_status, to_status, skipped_statuses, source, import_id, import_filename, occurred_at}`, linked
exceptions `{id, reference, exception_type, severity, status, …}`, `is_overdue`. Product health
for the Stock column comes from `GET /stores/{id}/inventory/positions?q={sku}` only when
`inventory.read` is held. Otherwise the column is omitted.

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
| Supplier | `supplier.name` | left | xl |
| Reorder point / qty | `reorder_point` / `reorder_quantity` | right | lg |
| Available | `available` (BR-101) | right | md |
| Stock | `health` → `HealthBadge` ("Data issue" for `DATA_ISSUE`, i.e. `on_hand < 0`, BR-402a; `on_hand` only adds the figure to its tooltip) | left | never |

**Actions.** Open product. No catalog editing in v1 (CSV import only).
**Filters / sort / search.** `q`: substring of SKU or name. Status (default: Active). Category
(from `GET /stores/{id}/categories`). Supplier (`supplier_id`). Stock health (`health`,
repeatable, the five availability classes then Data issue). Sort: SKU (default), Name, Recently updated (`-updated_at`), Available.
**Pagination:** 25 (25/50/100).

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
   status tag, `HealthBadge` (md; "Data issue" when `health` is `DATA_ISSUE`).
2. **Stock position** (`inventory.read`): a row of `StatTile`s: On hand, Reserved, **Available**
   (danger text when negative, with the minus sign), Incoming (+ ETA), Avg daily
   units (est.), Days of cover (est.). Under the tiles, one formula line in `text-mono`:
   "available = on_hand − reserved = 18 − 22 = −4 (BR-101). Incoming is not counted (BR-103)."
   Health explanation: "Oversold: available is below 0." For the reorder-point classes:
   "Reorder point 10. Approaching from 11 to 13 (reorder point × 1.25, rounded up)." (from
   `approaching_threshold`). When `health` is `DATA_ISSUE` (`on_hand < 0`, any product status): an
   attention-tone callout replaces the health explanation: "Data issue: on hand is −3, which is physically impossible. Stock health and
   inventory exceptions are suspended for this product until a cycle count corrects it (BR-402a).
   See EXC-1051 (Negative on-hand)." The Available tile shows the value with "not reliable" in
   muted text. Days of cover shows "—" with "not reliable", since it is derived from the same
   impossible figure.
3. **Product** (DescriptionList): price, cost, reorder point, reorder quantity, supplier (name,
   lead time), last cycle count.
4. **Exceptions** (`exceptions.read`): `active_exception_count` in the heading, then the list from
   `GET /stores/{id}/exceptions?product_id={id}` (active first, then the last 5 closed; same
   compact list as S-06).
5. **Active reservations** (P1, `inventory.read`): Order (link) · Line · Qty · Paid (ET) · Ship by
   (ET), sorted by `paid_at` (the FIFO order used by BR-402). No v1 endpoint returns reservations
   per product, so the section is not rendered until one exists (IA-5).
6. **Recent movements** (`inventory.read`): last 10 ledger rows (compact) + **View all
   movements** → `/inventory/movements?product_id={id}`.

**Data.** `GET /stores/{id}/products/{pid}` (`ProductDetail`): product fields, `supplier {name,
lead_time_days}`, `stock` snapshot (on hand, reserved, available, incoming, ETA, last cycle count),
`health`, `approaching_threshold`, `avg_daily_units` and `days_of_cover` as `Estimate {value, basis,
window_days, note}` (rendered with `EstimateLabel`, basis in the tooltip), `active_exception_count`.
Movements: `GET …/inventory/movements?product_id={id}&page_size=10`. Exceptions:
`GET …/exceptions?product_id={id}`.

**Actions.** Links only.

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty sub-sections | No reservations: "No units are reserved for paid orders." No movements: "No ledger entries yet. Stock arrives through inventory adjustment imports." Days of cover null: "Not enough sales history" (BR-151). Non-ACTIVE product with valid stock (health null): "Not tracked" with "Stock health is computed for active products only." A non-ACTIVE product with `on_hand < 0` is still `DATA_ISSUE` and gets the callout. |
| Not found | Standard. |
| API error / permission denied | Standard. Sections omitted per permission. |
| Search / filtered / validation / toast / pending / confirmation / disabled | N/A. |
| Responsive | < 768: tiles in 2 columns. The formula line wraps. Tables scroll with the first column pinned. |

---

## S-09 Inventory positions

**Purpose.** See stock risk across all SKUs at once, ranked by health. **Personas.** Manager,
Staff.

**Layout.** PageHeader "Inventory" → **Health summary bar**: six toggle buttons with counts
("Oversold 2", "Out of stock 4", "Below reorder point 11", "Approaching 7", "Healthy 96", then,
after a divider, "Data issue 1"), from the dashboard's `inventory` counts. Each is a real `button`
with `aria-pressed` and sets the `health` filter. The API classifies products with `on_hand < 0` as
`DATA_ISSUE` instead of by `available`, because their inventory rules are suppressed (BR-402a), so
they are counted and filtered as "Data issue", never as Oversold. The divider marks that it is not
an availability class. Then a caption: "Available = on
hand − reserved. Incoming stock is shown separately and never counted as available (BR-101,
BR-103)." → FilterBar → DataTable (compact default) → Pagination.

| Column | Source | Align | Hide below |
|---|---|---|---|
| SKU | `product.sku` (link to S-08) | left | never |
| Product | `product.name` | left | md |
| Health | `health` → `HealthBadge` ("Data issue" for `DATA_ISSUE`) | left | never |
| On hand | `inventory_balance.on_hand` | right | md |
| Reserved | `reserved` | right | md |
| Available | `available` (BR-101, danger text if < 0) | right | never |
| Incoming | `incoming` + "ETA Nov 4" (`incoming_eta`) | right | lg |
| Reorder point | `product.reorder_point` | right | lg |
| Avg daily units (est.) | `avg_daily_units` (1 dp) | right | 2xl (1536 px; at 1280–1535 px the eleven columns squeeze the product name. The value stays on S-08) |
| Days of cover (est.) | `days_of_cover` (1 dp, or "—" with a tooltip "Not enough sales history"). Hidden for "Data issue" rows | right | lg |
| Last count (ET) | `last_cycle_count_at` | left | xl |

**Filters / sort / search.** `q`: substring of SKU or name. Health (multi, repeated `health`,
including `DATA_ISSUE`). Category. **Include inactive products** toggle (`include_inactive=true`;
they show "Not tracked", or "Data issue" when on-hand is negative). Sort (`PositionSort`): Available, lowest first (default, which puts oversold and
out-of-stock first), Days of cover (lowest first), SKU. **Pagination:** 50 default (50/100), since
the table is compact.

| State | Behaviour |
|---|---|
| Initial loading | Standard. The summary bar shows skeleton chips. |
| Empty | "No stock positions yet". "Import products, then inventory adjustments (a CYCLE_COUNT sets on-hand)." Action **Import inventory adjustments** (`imports.run`). |
| Populated / search / filtered | Standard. "Oversold" filter with no rows: success tone, "No oversold products". "Data issue" filter with no rows: success tone, "No data issues", "No active product has a negative on-hand figure." |
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
| On hand after | `on_hand_after` (the running balance) | right | md |
| Reference | `reference`. Shipments (`order_item:{id}`) render their note, "Order KHK-10482", as a link to that order (S-06) through the movement's derived `order_id`; if the line no longer resolves, to the Orders list searched for the number. Others as plain text in mono. | left | md |
| Note | `note` (truncated, tooltip). Omitted for shipments, whose note is already the reference | left | xl |
| Import | `import_filename` (mono), linking to S-13 (`/imports/{import_id}`) with `imports.read`, plain text otherwise, "—" for rows no import wrote (shipments, system rows) | left | xl |
| Recorded by | `created_by` → name via `GET /stores/{id}/members`, "Former member" if absent, or "System" | left | xl |
| Recorded (ET) | `recorded_at` | left | 2xl |

**Filters / sort / search.** Product (`product_id`): a combobox that searches SKU and name on the
server (`GET …/inventory/positions?q&include_inactive=true&sort=sku`, 20 results, 300 ms debounce,
arrow keys and Enter, "Any product" to clear); links from S-08 set it too; chip "Product:
KHK-DO55-SGE". Type (multi, repeated `movement_type`). Source (`source`). Occurred (`occurred`:
store-local presets Today, Last 7, 30 and 90 days, sent as `from`; or Custom range,
`occurred=custom&occurred_from&occurred_to` in store days, sent as `from` (inclusive) and `to`
(exclusive midnight after the end day), validated as S-05). Import (`import_id`, set by
**View ledger entries** on S-13 for applied inventory adjustment imports; chip "Import: {file
name}"). Sort (`MovementSort`): Occurred newest (default), Occurred oldest, Recorded newest
(`-recorded_at`). There is no free-text search on this endpoint. **Pagination:** 50 (50/100).

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
**Personas.** Manager (runs), Staff and Analyst (read). The workflow, data contracts and issue
codes are canonical in `docs/workflows/IMPORT_PIPELINE.md`. This screen and S-12/S-13 render them.

**Layout.** PageHeader "Imports". Actions: **Download template ▾** (menu in the recommended order:
products.csv, inventory_adjustments.csv, orders.csv, order_items.csv → `GET
/stores/{id}/imports/templates/{import_type}`) and **New import** (primary). An info line under the
header: "Recommended order: products → inventory adjustments → orders → order items. Each file
references the ones before it (IMPORT_PIPELINE §10)." FilterBar → DataTable → Pagination.

| Column | Source (`ImportOut`) | Align | Hide below |
|---|---|---|---|
| File | `original_filename` (link to S-12/S-13) | left | never |
| Type | `import_type` → Products / Orders / Order items / Inventory adjustments | left | md |
| Status | `status` → `ImportStatusPill` | left | never |
| Mode | `mode` → Strict / Valid rows only / "—" before apply | left | 2xl (1536 px; at 1280–1535 px ten columns overflow. S-13 shows it) |
| Rows | `summary.rows_total` | right | md |
| Create · Update | `summary.creates`, `summary.updates` (after apply: `summary.applied.creates`, `.updates`) | right | lg |
| Rows with errors | `summary.rows_with_errors`, danger text when > 0 | right | md |
| Rows with warnings | `summary.rows_with_warnings` | right | 2xl (as Mode) |
| Uploaded by | `created_by` → name via `GET /stores/{id}/members` ("Former member" if absent) | left | lg |
| Uploaded (ET) | `created_at` | left | never |

**Actions**

| Action | Permission | Disabled reason |
|---|---|---|
| New import | `imports.run` | Permission copy / "The public demo is read-only." |
| Download template | `imports.read` | none |
| Open import | `imports.read` | none |

**Filters / sort / search.** Type (`import_type`), Status (`status`, multi, repeated; chip
"Status: Failed, Rejected"). The endpoint has no text search, so there is no search box. Sort: newest first. **Pagination:** 25. **Live
status:** upload validation and apply run inside their requests, so rows are rarely mid-flight.
If a visible row is `UPLOADED`, `VALIDATING` or `APPLYING`, refetch every 2 s until none are.

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | "No imports yet". "Start with products, then inventory adjustments, orders and order items. Each file type has a template." Actions **New import** (`imports.run`) and **Download template**. |
| Populated / filtered | Standard. |
| Search / validation | N/A. |
| API error / permission denied | Standard (`imports.read`). |
| Template download error | Error toast: "Couldn't download the template. Try again." |
| Success toast / pending / confirmation | N/A on this screen. |
| Disabled action | New import per the table. |
| Responsive | < 768: stacked rows. Line 1: file name + status. Line 2: type · rows · rows with errors. Line 3: uploaded time and person. |

---

## S-12 New import wizard (upload → preview → apply → summary)

**Purpose.** Load a CSV safely: never silently skip rows, show every issue and the expected
changes before anything changes, and make partial application an explicit, counted decision
(BR-606, IMPORT_PIPELINE §1). **Persona.** Operations Manager (`imports.run`).

**Routing.** Step 1 is `/imports/new` (`?type=` preselects a type). `POST /stores/{id}/imports`
uploads **and validates in the same request**, returning `201` with the import in `VALIDATED` or
`REJECTED` (a file-level failure is still recorded in the history). The app then
`router.replace`s to `/imports/{id}`, which renders the stepper while `status ∈ {VALIDATED,
APPLYING}` and the summary or detail once terminal (IA §3 A8). If `UPLOADED` or `VALIDATING` is
ever observed (a reload mid-request), the page polls `GET /imports/{id}` every 2 s.

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
| Rows       | | Create     | | Update     | | Unchanged  | | Rows with  | | Rows with  |
| 1,240      | | 312        | | 914        | | 0          | | errors  14 | | warnings 3 |
+------------+ +------------+ +------------+ +------------+ +------------+ +------------+

[!] 3 timestamps had no UTC offset and were read as store time, America/New_York
    (TIMEZONE_ASSUMED). Export with offsets to remove the ambiguity.

Expected changes (first 50 rows)                                       [Show all actions ▾]
| Row | Key         | Action    | Changed fields                                   |
| 2   | KHK-100611  | Update    | status, fulfillment_status                       |
| 3   | KHK-100612  | Create    | —                                                |
| 4   | KHK-100504  | Unchanged | —                                                |

Issues                         [All 17] [Errors 14] [Warnings 3]       [Download issues CSV]
[Code ▾]  [Q Row number]
| Row | Column       | Code                              | Severity  | Message                       | Value                  |
| 18  | status       | ORDER_INVALID_STATUS_COMBINATION  | [x Error] | SHIPPED needs payment PAID     | SHIPPED / PENDING      |
| 41  | placed_at    | INVALID_DATETIME                  | [x Error] | Not an ISO-8601 timestamp      | 11/05/2026 2:00 PM     |
| 77  | status       | ORDER_TRANSITION_NOT_ALLOWED      | [x Error] | DELIVERED → PAID not reachable | PAID                   |
| 112 | currency     | CURRENCY_MISMATCH                 | [x Error] | Store currency is USD          | EUR                    |
| 203 | paid_at      | TIMEZONE_ASSUMED                  | [! Warn.] | Read as America/New_York       | 2026-10-30T11:20:00    |
| …                                                                                                  |
| 1–25 of 17 issues                                                 ‹ Previous  Page 1 of 1  Next › |

                                                      [Discard import]   [Continue to apply ›]
```

### Step 1: Upload (`/imports/new`)
- **Type** (required): radio cards in a 2 × 2 grid (1 column < 640), in the recommended order:
  Products ("Create or update products by SKU. Creates suppliers"), Inventory adjustments
  ("Counts, receipts, damage and corrections. Each reference applies once"), Orders ("Create or
  update orders by order number. Status changes must be reachable"), Order items ("Lines for
  orders that already exist, by order number and line number"). Each card has a **Template** link.
- **Column reference** (collapsible, closed by default): the selected type's columns from
  IMPORT_PIPELINE §5 (column, required, type and validation), with a link to the template.
- **File**: `ImportDropzone`. Accepts `.csv` only, ≤ 5 MB. Shows the selected file name and size
  with a **Remove** button.
- Dependency hint, per type: Order items → "Order items must reference orders and SKUs that
  already exist. Import those first." Orders → "Products should be imported first, so that order
  items can reference them." Inventory adjustments → "Opening counts come before orders, so that
  orders shipped before the count are not deducted twice (BR-130)."
- Primary: **Upload and validate**. Secondary: **Cancel** (back to S-11).

### Step 2: Preview (`/imports/{id}`, `VALIDATED`)
- Summary tiles from `summary`: Rows (`rows_total`), Create (`creates`), Update (`updates`),
  Unchanged (`unchanged`), Rows with errors (`rows_with_errors`), Rows with warnings
  (`rows_with_warnings`).
- Warning callouts from `summary.issue_counts_by_code` and `file_issues`: `DUPLICATE_FILE` ("This
  file is identical to an import completed on Oct 30, 8:04 AM EDT. Applying it again is safe:
  rows come out unchanged and adjustments as already applied."), `TIMEZONE_ASSUMED` (count),
  `UNKNOWN_COLUMN` (lists the ignored headers), `ALREADY_APPLIED` (count, adjustments only).
- The expiry countdown ("Preview expires in 23h 58m") comes from `expires_at`.
- **Expected changes** table (IMPORT_PIPELINE §3.2 step 7) from `summary.preview[] {row_number,
  key, action, changed_fields}`. The API lists only rows that create, update or have errors (action
  `SKIP`), at most 50, so the title reads "first 50 of N" when more change and a note says unchanged
  rows are not listed. Columns: Row, Key (SKU, order number, order number + line, or reference),
  Action (Create / Update / Unchanged / Error, as text with icon), Changed fields (comma list). A
  filter by action. Rows with errors link to their issues.
- Then the `IssueTable`.
- Actions: **Discard import** (secondary, confirm), **Download issues CSV** (when issues > 0),
  **Continue to apply** (primary).

### Step 3: Apply (`VALIDATED`)

```text
Apply mode
(•) Strict  (default)
    Apply only if every row is valid. Nothing is skipped.
    ⚠ Blocked: 14 rows have errors. Fix them in the source and upload again,
      or choose "Valid rows only".
( ) Valid rows only
    Apply the 1,226 valid rows and skip the 14 rows with errors. Skipped rows are kept
    as import issues and can be downloaded.
    [ ] I understand that 14 rows will be skipped.

What will change: 312 orders created, 914 updated, 0 unchanged.
Applying runs in one transaction. If anything fails, nothing changes.

                                               [‹ Back]   [Apply 1,226 rows, skip 14]
```

- Mode radio (`STRICT` default). With 0 errors, only Strict is shown and the button reads
  **Apply 1,240 rows**.
- Valid rows only requires the consent checkbox. The button label always states the counts. The
  request sends `{mode: "VALID_ROWS_ONLY", confirm_skipped_rows: 14}`. The server checks that the
  confirmed count equals the rows it would skip (BR-606).
- Cascade hint for Orders and Products in valid-rows-only mode: "Lines of skipped orders will fail
  with UNKNOWN_ORDER when you import order items" / "Adjustments and lines for skipped products will
  fail with UNKNOWN_SKU" (IMPORT_PIPELINE §7).
- `Idempotency-Key`: generated when step 3 opens, reused on retries of the same mode, and
  regenerated if the mode changes (`422 IDEMPOTENCY_KEY_REUSED` otherwise).
- Button disabled reasons: strict with errors → "Strict mode blocks apply while 14 rows have
  errors."; consent not ticked → "Confirm that 14 rows will be skipped."; no permission → standard.
- Apply runs inside the request. The pending state shows "Applying 1,226 rows… This runs in one
  transaction. If anything fails, no data changes." with the `motion-essential` spinner.

**Apply errors** (409/422 from `POST /apply`; the import stays `VALIDATED` unless noted). After
any 409 or 422 the page refetches the import and renders what the server now holds. Where the API
sends a different code than this table's name, both are handled (API code in brackets):

| Code | UI |
|---|---|
| `IMPORT_HAS_ERRORS` | Inline: "Strict mode can't apply a file with row errors. Choose Valid rows only, or fix the file." |
| `IMPORT_SKIPPED_ROWS_NOT_CONFIRMED` (`SKIPPED_ROWS_NOT_CONFIRMED`, 422) | Inline: "The number of rows to skip changed. Review the issues and confirm again." The checkbox is cleared. |
| `IMPORT_PREVIEW_EXPIRED` (`IMPORT_EXPIRED`) | The page refetches (status `DISCARDED`) and shows the expired state. |
| `IMPORT_PREVIEW_STALE` (`IMPORT_DATA_CHANGED`) | The apply is recorded as `FAILED` (nothing applied), so the refetch shows the S-13 `FAILED` callout with `failure_reason` and **Validate again**, which re-checks the stored file against current data and restarts at the preview. |
| `IDEMPOTENT_REQUEST_IN_PROGRESS` | Info: "This apply is already running." The page polls the import. |
| `IMPORT_NOT_APPLICABLE` | The page refetches and renders the current status. |

### Step 4: Summary (`COMPLETED` / `COMPLETED_WITH_ERRORS`)
- Banner: success "Import completed. 1,240 rows applied." or warning "Import completed. 1,226 rows
  applied, 14 skipped with your confirmation."
- Tiles from `summary.applied {mode, creates, updates, unchanged, skipped}`.
- **Evaluation run** panel (`evaluation_run_id` → `GET /stores/{id}/evaluations/{rid}`):
  `SUCCEEDED` → "3 new exceptions · 6 refreshed · 1 resolved · 0 reopened" with **View new
  exceptions** when the run created any: the inbox's All active view filtered by
  `evaluation_run_id` (S-03), so it lists the new exceptions still active. Shown with
  `exceptions.read`, which reads evaluation runs. Applied **inventory adjustment** imports also
  offer **View ledger entries** (S-10 with `import_id`). `SKIPPED` → info "Another analysis was running, so this import's
  analysis was skipped. The next scheduled run, within 15 minutes, will evaluate the new data."
  `FAILED`, or `summary.evaluation_error` set → warning "The import is complete, but its analysis
  failed. No exceptions were changed by it, and the next scheduled run will catch up." A missing
  `evaluation_run_id` shows the same SKIPPED copy.
- Onboarding note after a **products** import that created products: info "New active products
  have no stock yet, so they appear as Out of stock until you import inventory adjustments
  (IMPORT_PIPELINE §10)."
- Issues section (skipped rows and warnings) with the issues CSV download.
- Actions: **Import another file** (`/imports/new?type={next type in the recommended order}`),
  **Back to imports**.

**Data.** `ImportDetailOut`: `id, import_type, status, mode, original_filename, file_sha256,
size_bytes, row_count, summary {rows_total, rows_valid, rows_with_errors, rows_with_warnings,
creates, updates, unchanged, issue_counts_by_code, preview[], applied, evaluation_error},
created_at, validated_at, applied_at, expires_at, created_by, applied_by, evaluation_run_id,
failure_reason, can_revalidate, file_issues[]`. Issues: `GET …/issues` → `{row_number, column,
code, severity, message, raw_value}`.

**Actions**

| Action | Permission | Notes |
|---|---|---|
| Upload and validate | `imports.run` | `POST /stores/{id}/imports` (multipart `import_type`, `file`) |
| Discard import | `imports.run` | `POST …/discard`. Confirm dialog: "Discard this import? The file is deleted and no data changes. The issue list stays available for reference." Button **Discard import** |
| Apply | `imports.run` | `POST …/apply`. Step 3 is the confirmation. No extra dialog. |
| Download issues CSV | `imports.read` | `GET …/issues.csv`: the original columns plus `row_number`, `code`, `column`, `message`, formula-injection safe |
| Download template | `imports.read` | `GET …/imports/templates/{import_type}` |

| State | Behaviour |
|---|---|
| Initial loading | `/imports/{id}`: header skeleton + stepper + tiles skeleton. |
| Empty | Step 1 has no data state. Preview with 0 issues: "No issues found. All 1,240 rows are valid." (success tone). |
| Populated | As above. |
| Search results / filtered | Issue table: filter by severity tabs, code (single, from `issue_counts_by_code`; the API takes one), and a **Row number** box (digits only, 300 ms debounce, `row_number` exact match; file-level issues have no row and drop out). No match: "No issues match these filters". Expected-changes table: filter by action. |
| Validation error (client) | No type: "Choose what you're importing." No file: "Choose a CSV file." Wrong extension: "Only .csv files can be imported." Too large: "This file is 7.2 MB. The limit is 5 MB. Split it into smaller files." |
| Validation error (file-level, server) | `REJECTED`: a danger alert per `file_issues[]` item showing the code, the API `message` (for `MISSING_COLUMNS` it lists the missing headers and may say "this looks like an orders file") and the "How to fix" text from IMPORT_PIPELINE §6. **Upload a corrected file** → `/imports/new?type={type}`. |
| API error with retry | Upload network failure: "Upload failed. Check your connection and try again." (the file stays selected). Apply 5xx: an inline error in step 3 with **Try again** (same Idempotency-Key). |
| Apply failed | `FAILED`: danger "Apply failed and was rolled back. No data was changed." + `failure_reason` + **Validate again** while `can_revalidate` (S-13). |
| Preview expired | `DISCARDED` by expiry: muted "This preview expired after 24 hours, because store data may have changed since validation. Upload the file again." + **Upload again**. |
| Permission denied | `/imports/new` without `imports.run`: standard PermissionDenied. On a record, actions are disabled per the table. |
| Success toast | Discard → "Import discarded". Apply completes → none (the summary step is the confirmation). |
| Pending action | Upload: the request goes through `XMLHttpRequest` for upload progress. While the bytes are sent, the button reads "Uploading 42%…" and a determinate progress bar ("Upload progress", `aria-valuenow`) shows the percentage ("Uploading…" when the size is unknown); once sent, the same request validates the file, so the button reads "Validating…" and the bar turns indeterminate ("Validating the file"). Only the phase change is announced (`role="status"`), not every percent. Apply: "Applying 1,226 rows…". |
| Confirmation dialog | Discard. Apply uses the inline step 3 confirmation. |
| Disabled action | Per the step 3 reasons. |
| Responsive | < 768: tiles in 2 columns. The stepper shows "Step 2 of 4 · Preview". The issue and expected-changes tables scroll horizontally with Row pinned. Step 3 buttons are full width and stacked. |

**Issue codes and fix text.** The UI does not keep its own copy of issue codes. The code list,
level (FILE / ERROR / WARNING), meaning and "How to fix" text come from IMPORT_PIPELINE §6, mirrored
into `status-maps.ts` (`importIssueMeta`). Codes the UI must handle: FILE `FILE_EMPTY`,
`FILE_TOO_LARGE`, `FILE_TYPE`, `FILE_ENCODING`, `TOO_MANY_ROWS`, `MISSING_COLUMNS`. ERROR
`REQUIRED`, `VALUE_TOO_LONG`, `INVALID_ENUM`, `INVALID_NUMBER`, `INVALID_INTEGER`,
`NEGATIVE_VALUE`, `INVALID_DATETIME`, `DUPLICATE_KEY_IN_FILE`, `UNKNOWN_SKU`, `UNKNOWN_ORDER`,
`CURRENCY_MISMATCH`, `ORDER_INVALID_STATUS_COMBINATION`, `ORDER_MISSING_TIMESTAMP`,
`ORDER_TIMESTAMP_SEQUENCE`, `ORDER_TRANSITION_NOT_ALLOWED`, `ORDER_LINE_LOCKED`,
`LINE_DISCOUNT_EXCEEDS_LINE`, `STALE_CYCLE_COUNT`. WARNING `UNKNOWN_COLUMN`, `TIMEZONE_ASSUMED`,
`PRICE_ZERO`, `NEGATIVE_MARGIN`, `ALREADY_APPLIED`, `DUPLICATE_FILE`. An unknown code falls back to
the API `message` with no hint, and never breaks the table.

---

## S-13 Import detail with issues

**Purpose.** The permanent record of one import: what was uploaded, what happened, every issue,
and what the import triggered. **Personas.** Manager, Staff, Analyst.

**Layout.** For `VALIDATED` and `APPLYING` this route renders S-12. For other statuses:
1. PageHeader: breadcrumb "Imports / {file}". Title = file name. `ImportStatusPill` (md). Type tag.
2. **Status callout** (by status):
   - `COMPLETED`: none (the summary tiles suffice).
   - `COMPLETED_WITH_ERRORS`: warning "14 rows were skipped with your confirmation. They are listed below and in the issues CSV."
   - `REJECTED`: danger, one block per `file_issues[]` item (code, message, fix text) + **Upload a corrected file**.
   - `FAILED`: danger "Apply failed and was rolled back. No data was changed." + `failure_reason`. While `can_revalidate` (the failed apply keeps the file bytes until the preview's original expiry): "Validate the same file again against the current store data. Nothing changes until you apply." + **Validate again** (`POST …/revalidate`, `imports.run`, pending "Validating…"). A `VALIDATED` result brings back the stepper at Preview with a new 24 h expiry; a `REJECTED` result shows the rejection callout. A 409 (bytes purged meanwhile, or the status changed) shows the API message and refetches. Once the bytes are gone: "The file is no longer stored. Upload it again to validate it from the start." + **Upload a corrected file**.
   - `DISCARDED`: muted "Discarded on {date}" (the API records no discarding user, so no name) or the expiry copy. The UI treats a record whose `updated_at` is at or after `expires_at` as expired.
3. **Details** (DescriptionList): Type, Mode, Uploaded by / at, Validated at, Applied by / at, Size,
   Rows, SHA-256 (first 12 characters, mono, copy full).
4. **Summary tiles**: as S-12 step 4 for applied imports, as step 2 otherwise.
5. **Evaluation run** (applied imports): as S-12 step 4 (SUCCEEDED / SKIPPED / FAILED copy).
6. **Expected changes** (for `REJECTED` and `DISCARDED`, hidden) and **Issues**: `IssueTable` with
   severity tabs, code filter and row search, plus **Download issues CSV**. Server pagination at 25.

**Data.** As S-12.

**Actions.** Upload a corrected file (`imports.run`), Validate again (`imports.run`, `FAILED` with
`can_revalidate`; visible but `aria-disabled` with the permission copy for people without
`imports.run`), Download issues CSV (`imports.read`), View new exceptions (`exceptions.read`),
View ledger entries (`inventory.read`, applied inventory adjustment imports).

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | Issues: "No issues. Every row was valid." (success tone). |
| Populated / search / filtered | Issue table as S-12. |
| Validation | N/A. |
| API error | Standard. Issues CSV download failure → error toast with **Try again**. |
| Not found / permission denied | Standard (`imports.read`). |
| Success toast | Validate again with a `VALIDATED` result → "Validated again. Review the preview before applying." (the stepper takes over). Validation runs inside the request, like the upload. |
| Pending action | Validate again pending state. |
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
  EXC-1042" when `context_type = EXCEPTION`) and the updated relative time. Right: the thread.
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

**Data.** `GET|POST /stores/{id}/copilot/conversations` and `GET …/conversations/{cid}`:
`ai_conversation.{id, title, context_type, context_id, updated_at}`, `ai_message.{role, content,
provider, model, latency_ms, created_at}`, `ai_tool_call.{tool_name, status, row_count,
duration_ms, error}`. Ask: `POST …/conversations/{cid}/messages`. References to exceptions carry
the exception `reference` as their label (`EXC-1042`).

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

**Purpose.** An immutable record of security-relevant and business-changing actions for the
current store. **Personas.** Owner, Manager, Analyst.

**Layout.** PageHeader "Audit log". Subtitle "Kestrel Home & Kitchen · append-only".
Data: `GET /stores/{id}/audit-logs`.
FilterBar → DataTable (compact) → Pagination. Rows expand inline (disclosure button in the first
column) to show metadata.

| Column | Source | Align | Hide below |
|---|---|---|---|
| Time (ET) | `audit_log.occurred_at`, with the row's disclosure button. Pinned while the table scrolls sideways | left | never |
| Actor | `actor_name` from the audit response (no emails). "System" when `actor_user_id` is null. "Former member" when the API returns an ID without a name. | left | never |
| Action | `action` → label + code in mono (e.g. "Resolved exception" `exception.resolve`) | left | never |
| Target | `target_type` + `target_id` → label, linked when the record belongs to this store and its page is open to the person: exception reference (`details.reference`, `EXC-1042`) → exception detail, import (`details.import_type`, "Orders import") → import detail, the store → "Store settings", a member → `details.full_name`. Otherwise the type plus a short ID. | left | md |
| Request ID | `request_id` (mono, copy button) | left | lg |
| Expanded row | Action code, target and request ID (so narrow screens see the hidden columns), then `details` as a key–value list (mono values). A `before` / `after` pair (settings) is shown per key as "48 → 36". Secrets are never present (server guarantee). `AuditLogOut` has no IP field, so no IP is shown (IA Q-IA-2). | | |

**Action labels** (prefix groups for the filter). The labels cover the actions the API records today:
Sign-in and sessions (`auth.login`, `auth.demo_login`, `auth.logout`, `auth.login_failed`,
`auth.session_revoked`), Users (`user.create`, `user.role_change`, `user.deactivate`,
`user.reactivate`), Settings (`settings.update`), Exceptions (`exception.acknowledge`, `.start`,
`.resolve`, `.dismiss`, `.reopen`, `.assign` (shown as "Claimed exception" when `details.claimed`,
"Unassigned exception" when `details.to_assignee_id` is null), `.note`, `.due_date`), Imports
(`import.applied`, `import.failed`, `import.discarded`), Analysis runs (`evaluation.run`). Unknown
actions fall back to the raw code. `auth.login_failed` rows have no organization, so they never
appear in a store's log. **Deviation (T-066):** the names follow the implemented API, not the
proposal in ROLE_AND_PERMISSION_WORKFLOW §11 (`authz.denied` is not recorded, so it has no filter
group). The labels live in `features/admin/audit-actions.ts`.

**Filters / sort / search.** Period (`period` in the URL: Last 24 hours / Last 7 days (default) /
Last 30 days / Last 90 days / All time / Custom range). Presets count store-local calendar days
including today; Last 24 hours is rolling. Custom range: From and To date inputs (`from`, `to` as
`YYYY-MM-DD`) covering whole store-local days, either end optional; an inverted range shows "The
start date must be on or before the end date." and is not applied. Action group (single select,
sent as the `action` prefix, e.g. `exception.`). Actor (select of the store's active members from
`GET /stores/{id}/members`, `actor_user_id`). No free-text search on this endpoint. Sort: newest
first only (append-only log). **Pagination:** 50 (50/100).

**Actions.** Expand row, copy request ID. No export (IA-5).

| State | Behaviour |
|---|---|
| Initial loading | Standard. |
| Empty | "No audit events in this period". "Nothing was recorded in the last 7 days. Widen the date range to see older events." **Show all time**. |
| Populated / search / filtered | Standard. |
| Validation | Custom range: "The start date must be on or before the end date." under the date inputs; the inverted range is not applied. Unknown values in a shared link are dropped with the standard toast. |
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

| Section | Field (`store_settings.*`) | Default | Validation (mirrors `StoreSettingsUpdate`) | Helper text |
|---|---|---|---|---|
| Store profile (read-only) | `store.name`, `store.code`, `store.currency`, `store.timezone`, organization | — | — | "Currency and time zone are fixed after the store is created." |
| Fulfillment | `fulfillment_sla_hours` | 48 | integer 1–8,760 | "Ship-by deadline when the import has none: paid at + this many hours (BR-201)." |
| | `stall_threshold_hours` | 12 | integer 1–8,760 | "A paid order not yet processing after this many hours is 'stalled' (BR-203)." |
| | `refund_overdue_hours` | 24 | integer 1–8,760 | "A cancelled, still-paid order becomes 'refund pending' after this many hours (BR-206)." |
| Inventory | `approaching_reorder_factor` | 1.25 | decimal 1.00–3.00, 2 dp | "Approaching reorder point up to reorder point × this factor (BR §2.5)." |
| | `velocity_window_days` | 28 | integer 7–90 | "Days of sales used for average daily units and days of cover (BR-150)." |
| Exceptions | `reopen_window_hours` | 72 | integer 1–8,760 | "A resolved exception that recurs within this window is reopened instead of recreated." |
| | `evaluation_interval_minutes` | 15 | integer 5–1,440 | "How often scheduled analysis runs." |
| Priority model | `exposure_cap` | 5,000.00 | decimal > 0, 2 dp, ≤ 9,999,999,999.99 (store currency) | "Value at risk at which the exposure component reaches its maximum." |
| | `priority_weights.severity.{CRITICAL, HIGH, MEDIUM, LOW}` | 50 / 35 / 20 / 8 | integers 0–100 | "Points for each severity." |
| | `priority_weights.affected_orders_per_order`, `.affected_orders_cap` | 3 / 15 | integers 0–100 | "Points per affected order, up to the cap." |
| | `priority_weights.exposure_cap_points` | 15 | integer 0–100 | "Points when value at risk reaches the exposure cap (logarithmic below it)." |
| | `priority_weights.deadline.{overdue, within_24h, within_72h}` | 12 / 8 / 4 | integers 0–100 | "Points by how close the business deadline is." |
| | `priority_weights.age_points_per_day`, `.age_cap` | 2 / 8 | integers 0–100 | "Points per whole day unresolved, up to the cap." |

**Priority model guard.** Live line under the section: "Maximum possible score: 100 of 100"
(= highest severity weight + `affected_orders_cap` + `exposure_cap_points` + highest deadline
weight + `age_cap`, the same sum as `PriorityWeights.max_possible_score`). If it is above 100:
section-level error "The maximum possible score is 108. It must be 100 or less." (mirrors the
backend validator). **Reset section to defaults** (a ghost button per section) fills the defaults
into the form and still requires Save.

**Actions**

| Action | Permission | Notes |
|---|---|---|
| Save changes | `settings.manage` | Confirm dialog "Save 2 changes?" listing each change as old → new ("Fulfillment SLA: 48 h → 36 h"), with "Changes apply from the next evaluation. Existing exceptions are re-ranked then. The change is recorded in the audit log." Button **Save changes**. `PATCH /stores/{id}/settings` with only the changed fields. |
| Discard | `settings.manage` | Resets the form to the server values. No dialog. |
| Reset section to defaults | `settings.manage` | Form-only. |

| State | Behaviour |
|---|---|
| Initial loading | Section skeletons. |
| Empty | N/A (settings always exist, with defaults). |
| Populated | Form (editors) or definition list (readers). |
| Search / filtered | N/A. |
| Validation error | Field and form-level per DESIGN_SYSTEM §14. Messages: "Enter a whole number from 1 to 8,760." (and the other integer ranges), "Enter a number with at most 2 decimal places.", "Enter a value from 1.00 to 3.00.", "Enter an amount above 0.00 and at most 9,999,999,999.99.". Server 422 details (`loc` `body.priority_weights…`) map to fields. The UI adds no cross-field rules that the backend does not enforce. |
| API error with retry | Load failure: standard. Save failure: alert in the save bar area with `request_id`. Values are kept. |
| Conflict | The API has no settings version, so there is no 409. **Implemented instead (T-066):** the form keeps the values it was opened with. **Save changes** refetches first, and a background refetch also compares: when the saved values differ (someone else saved), "Settings were changed by someone else. Reload to see the latest values. Your edits will be lost." (the last sentence only when there are edits) with **Reload**, and nothing is sent. The PATCH carries only the changed fields, so a race inside that window is last-write-wins per field. |
| Permission denied | Standard (`settings.read`, which all roles hold). |
| Success toast | "Settings saved. They apply from the next evaluation." |
| Pending action | **Save changes** → "Checking…" (the refetch), then "Saving…" in the dialog. |
| Confirmation dialog | Save (above). Navigation guard: `beforeunload` while there are unsaved changes. **Deferred (T-066):** an in-app "Discard unsaved changes?" dialog for sidebar links (the App Router has no route-change event to intercept). |
| Disabled action | Readers see no form, so there are no disabled inputs. In demo orgs the read-only note reads "The public demo is read-only." |
| Responsive | Single column at all widths. The save bar is full width with buttons stacked below 400 px. |

Implementation notes (T-066): the store profile comes from the session's store context. The
priority weights are grouped (Severity, Affected orders, Value at risk, Deadline, Time unresolved)
with each group's helper text, and the confirm dialog names a weight as "Severity · Critical". Any
weight change sends the whole `priority_weights` object, as the API requires. Integers are sent as
JSON numbers, decimals as strings (BR-503). The defaults shown as hints mirror
`DEFAULT_PRIORITY_WEIGHTS` and BUSINESS_RULES §7 in `features/admin/settings-fields.ts`; the API
does not return them.

---

## S-17 Users & roles

**Purpose.** See who has access to the organization and what each role can do. Owners add
members, change roles, and deactivate or reactivate members. **Personas.** Owner, Manager (read).
**Changed in T-066 (orchestrator decision):** add member, deactivation and reactivation are in the
UI, using the simplest variant of ROLE_AND_PERMISSION_WORKFLOW §8: the owner creates the account
and hands over a temporary password shown once. There is still no invite email and no
password-reset or own-password UI.

**Layout.** PageHeader "Users & roles" with **Add member** (`users.manage`). Subtitle
"Kestrel Commerce · organization-wide". Tabs (Radix): **Members** · **Roles and permissions**
(tab state is local, not in the URL).

**Members tab** (`GET /organizations/{org_id}/members`, `users.read`). DataTable (comfortable):
Name (avatar initials) · Email · Role (plain text) · Status (Active / Deactivated, neutral and
muted tags) · Last sign-in ("Never" when null, hidden below lg) · row menu (`users.manage`):
**Change role…**, **Deactivate…** or **Reactivate…**. A "You" tag appears next to the current user.

**Add member dialog.** Full name, Email, Role (the five roles with their descriptions, no
default). Validation mirrors `MemberCreate`: "Enter the member's full name.", "Enter an email
address.", "Enter an email address such as name@example.com.", "Choose a role.". An info alert
says RetailOps doesn't send email. `409 MEMBER_EXISTS` / `EMAIL_IN_USE` show the API message on the
email field (an existing account is never attached, open question O-35). Success: toast "Member
added: Jordan Lee", then the **Member added** dialog with the sign-in email and the temporary
password (mono, copy button), "It is shown only once and can't be recovered later." It does not
close on an outside click; **Done** closes it.

**Deactivate / Reactivate dialog.** Confirmation. Deactivate: "They are signed out everywhere at
once and can't sign in until reactivated. Their notes, history and audit entries keep their name.
Exceptions assigned to them stay assigned until a manager reassigns them." (O-27 proposal to
unassign is not implemented.) **Deactivate member** (destructive), toast "Sam Ortiz deactivated.
Their sessions were ended." Reactivate: "They can sign in again with their existing password",
**Reactivate member**, toast "Sam Ortiz reactivated". `409 LAST_OWNER`,
`409 MEMBER_IN_OTHER_ORGANIZATION` and `403 OWN_MEMBERSHIP` show as an alert in the dialog.

**Change role dialog.** A radio group of the 5 roles (current role preselected), each with a one-line description: Owner ("Full
access, including users"), Manager ("Runs operations. Everything except managing users"), Staff
("Works on exceptions. Reads operational data"), Analyst ("Read-only, plus copilot and audit
log"), Viewer ("Read-only demo access"). Below the select, a "What changes" list compares the
current role with the new one (permissions gained and lost, from the code-defined matrix).
Submit **Change role**. Confirmation is the dialog itself.

**Roles and permissions tab** (P0). A read-only matrix table from `GET /api/v1/roles`
(`[{role, permissions[]}]`, any authenticated user). Rows are the 18 permissions (label and
one-line description from `permissionLabels` / `permissionDescriptions` in `lib/permissions.ts`,
code in mono). Columns are OWNER, MANAGER, STAFF,
ANALYST, VIEWER. Cells
show a check icon with the visually hidden text "Granted", or "—" with "Not granted". Caption:
"Roles are defined in code (ADR-0007) and can't be edited here."

**Actions**

| Action | Permission | Disabled reason |
|---|---|---|
| Add member | `users.manage` (OWNER only) | Managers: "Only owners can add members, change roles or deactivate members." Demo: "The public demo is read-only." |
| Change role | `users.manage` (OWNER only) | Own row: "You can't change your own role." Last active owner: "At least one owner is required." The UI pre-checks the active owner count, and the server enforces it with `409 LAST_OWNER`. |
| Deactivate / Reactivate | `users.manage` (OWNER only) | Own row: "You can't deactivate your own account." Last active owner: "At least one owner is required." |

Disabled menu items show their reason under the label (as in the exception "More" menu).

**Filters / sort / search.** Client-side over the member list (organizations are small), kept in
the URL (`q`, `role`, `status`): name or email contains, role filter, status filter, sorted by
name. No pagination.

| State | Behaviour |
|---|---|
| Initial loading | Standard. Roles tab: row skeletons. |
| Empty | Not reachable (the current user is a member). Search with no match: standard no-results. |
| Populated / search / filtered | Standard. |
| Validation error | Same role selected: "Choose a different role." Add member: field messages above. |
| API error / conflict | Standard, with the request ID in dialog alerts. `409 LAST_OWNER` shows "At least one owner is required. Make another member an owner first." in the dialog and refreshes the list. |
| Permission denied | Standard (`users.read`). Hidden from STAFF, ANALYST and VIEWER navigation. |
| Success toast | "Role changed: Sam Ortiz is now Manager." "Member added: Jordan Lee". "Sam Ortiz deactivated. Their sessions were ended." "Sam Ortiz reactivated". |
| Pending action | "Changing role…", "Adding…", "Deactivating…", "Reactivating…". |
| Confirmation dialog | The Change role dialog (with the "What changes" list) and the Deactivate / Reactivate dialog. |
| Disabled action | Per the table. Managers see the matrix and list without the row menu, and **Add member** disabled with its reason. |
| Responsive | < 768: stacked rows (name, email, role · status · last sign-in, row menu). The matrix scrolls horizontally with the permission column pinned. |

Password resets, own-password change and forcing a new password at first sign-in are not in v1
(open question O-28). Existing accounts cannot be added to a second organization (O-35).

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
which opens S-14 with `?q=` and the window. **Data.** `analytics/trends` (daily metrics),
`analytics/exceptions-breakdown`, `analytics/dashboard`. **States.** Standard per chart (independent loading and error). Empty window: "No data
in this period."

### S-21 Evaluation runs
**Purpose.** Observability of detection: when it ran, why and what changed. **Columns.** Started
(ET), Trigger (Scheduled / Manual / Import, linking to the import), As of, Status, Duration, Rules,
Created / Refreshed / Resolved / Reopened / Superseded counts, Triggered by. Status pill:
`RUNNING` (info, "Running"), `SUCCEEDED` (success, "Succeeded"), `FAILED` (danger, "Failed. No
changes committed"), `SKIPPED` (muted, "Skipped: another run held the store lock"). Row → the
inbox filtered by `evaluation_run_id` (IA Q-IA-6). **Data.** `GET /stores/{id}/evaluations`.
**Action.** Run analysis (`evaluations.run`). **States.** Standard. A failed run shows its `error`
in an expandable row.

### S-22 Data quality
**Purpose.** One place for data problems that are not operational exceptions. **Layout.** Two
sections: **Data-quality exceptions** (active `DATA_ORDER_TOTAL_MISMATCH` and
`DATA_NEGATIVE_ON_HAND`, as a compact inbox table linking to S-04) and **Imports with rejected or
skipped rows** (the last 30 days of `REJECTED` and `COMPLETED_WITH_ERRORS` imports, with
error-code counts linking to S-13). **Permission.** `imports.read` + `exceptions.read`.
**States.** Standard. Empty: success tone, "No data-quality problems found."
