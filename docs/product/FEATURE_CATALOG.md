# Feature Catalog

> **Status:** Draft v1 (M0, T-002) · **Owner:** Product/BA · **Last updated:** 2026-10-31
> Related: [PERSONAS](PERSONAS.md) · [JOBS_TO_BE_DONE](JOBS_TO_BE_DONE.md) ·
> [SCOPE_AND_NON_GOALS](SCOPE_AND_NON_GOALS.md) · [SUCCESS_METRICS](SUCCESS_METRICS.md) ·
> `docs/domain/*` (canonical) · `TASKS.md`

## 1. How to read this catalog

### 1.1 Priorities

| Priority | Meaning | Spec depth |
|---|---|---|
| **P0** | Required for the v1 release. The product does not work end to end without it | Full spec: problem, story, preconditions, main and alternative workflows, business rules, errors, acceptance criteria, permissions, audit |
| **P1** | Part of v1, but the core loop works without it, so it can follow the P0 set | Problem, story, acceptance criteria, permissions |
| **P2** | Next after v1. A clear need exists, but it depends on infrastructure or validation | One line plus rationale |
| **P3** | Roadmap. Needs data or integrations that v1 deliberately excludes | One line plus rationale |

Every P0 feature maps to a task in `TASKS.md` and to a workflow document written in M1 (T-010).
The planned workflow paths are listed in §7.

### 1.2 Conventions used in the specs

- **Business rules** are cited by their canonical IDs (`BR-xxx`) or by section of
  `STATE_MACHINES.md`, `EXCEPTION_CATALOG.md`, and `PRIORITY_MODEL.md`. This catalog does not
  restate formulas that are already canonical. It references them.
- **Errors** use the standard envelope
  `{"error": {"code", "message", "details", "request_id"}}` and the status codes from the API
  conventions (400, 401, 403, 404, 409, 422, 429). `EXCEPTION_TRANSITION_NOT_ALLOWED` and the import
  issue codes are canonical. Other error codes in this catalog are **proposed names**; the final list
  belongs to the API conventions document (T-022).
- **Audit actions** follow the `<area>.<verb>` pattern used in `DOMAIN_MODEL.md` (`exception.resolve`,
  `import.apply`, `auth.login_failed`). Action names not listed there are **proposed**; the audit
  catalogue is finalised in T-043. Audit metadata never contains passwords, tokens, or other secrets.
- **Domain history versus audit.** Order and exception status changes are recorded as
  `order_event` and `exception_event` rows. The `audit_log` additionally records who performed a
  user-initiated action, with the request ID. System-initiated changes are traced through
  `evaluation_run` and events with `actor_type = SYSTEM`.
- **Examples** use fictional data from the demo store "Kestrel Home & Kitchen" (USD,
  America/New_York). They illustrate rules. They are not measurements.

### 1.3 Role reference (ADR-0007)

| Role | Permissions |
|---|---|
| `OWNER` | All |
| `MANAGER` | All except `users.manage` |
| `STAFF` | `dashboard.read`, `catalog.read`, `orders.read`, `inventory.read`, `exceptions.read`, `exceptions.work`, `imports.read`, `analytics.read`, `copilot.use`, `settings.read` |
| `ANALYST` | `dashboard.read`, `catalog.read`, `orders.read`, `inventory.read`, `exceptions.read`, `imports.read`, `analytics.read`, `copilot.use`, `audit.read`, `settings.read` |
| `VIEWER` | Same as `ANALYST`. Can never mutate shared data |

---

## 2. Catalog overview

| ID | Feature | Pri | Primary personas | Tasks | Workflow doc (T-010) |
|---|---|---|---|---|---|
| F-001 | Authentication, sessions, and role-based access | P0 | All | T-042, T-060 | ROLE_AND_PERMISSION_WORKFLOW |
| F-002 | Data import pipeline | P0 | Ops Manager, Analyst | T-052, T-065 | IMPORT_PIPELINE |
| F-003 | Inventory positions and stock health | P0 | Ops Manager, Staff | T-051, T-064 | INVENTORY_WORKFLOW |
| F-004 | Inventory movement ledger and reservations | P0 | Ops Manager, Analyst | T-051, T-064 | INVENTORY_WORKFLOW |
| F-005 | Orders list and detail | P0 | Staff, Ops Manager | T-050, T-063 | ORDER_WORKFLOW |
| F-006 | Exception detection engine and evaluation runs | P0 | System; Ops Manager | T-053 | EXCEPTION_WORKFLOW |
| F-007 | Exception inbox | P0 | Ops Manager, Staff | T-054, T-062 | EXCEPTION_WORKFLOW |
| F-008 | Exception lifecycle and assignment | P0 | Ops Manager, Staff | T-054, T-062 | EXCEPTION_WORKFLOW |
| F-009 | Exception investigation view | P0 | Staff, Ops Manager, Analyst | T-062 | EXCEPTION_WORKFLOW, AI_INVESTIGATION_WORKFLOW |
| F-010 | Operations overview dashboard | P0 | Owner, Ops Manager | T-057, T-061 | EXCEPTION_WORKFLOW |
| F-011 | Operations copilot with deterministic fallback | P0 | All | T-071, T-072, T-073 | AI_INVESTIGATION_WORKFLOW |
| F-012 | Audit log (recording and read API) | P0 | Owner, Analyst | T-043 | ROLE_AND_PERMISSION_WORKFLOW |
| F-013 | Read-only demo access and demo dataset | P0 | Demo visitor | T-056, T-042 (VIEWER) | ROLE_AND_PERMISSION_WORKFLOW |
| F-014 | Scheduled evaluation worker | P1 | System | T-055 | EXCEPTION_WORKFLOW |
| F-015 | Store settings: thresholds and priority weights | P1 | Ops Manager, Owner | T-066 | EXCEPTION_WORKFLOW |
| F-016 | User and membership management | P1 | Owner | T-066 | ROLE_AND_PERMISSION_WORKFLOW |
| F-017 | Audit log viewer | P1 | Owner, Analyst | T-066 | ROLE_AND_PERMISSION_WORKFLOW |
| F-018 | Exception performance analytics | P1 | Analyst, Ops Manager | T-057 (extension) | EXCEPTION_WORKFLOW |
| F-019 | Hosted public demo with scheduled reset | P1 | Demo visitor | T-093, T-094 | ROLE_AND_PERMISSION_WORKFLOW |
| F-020 | Copilot evaluation harness | P1 | Internal (quality) | T-074 | AI_INVESTIGATION_WORKFLOW |
| F-021 | Data quality overview | P1 | Analyst | T-065 (extension) | IMPORT_PIPELINE |
| F-022 | Per-visitor demo sandbox | P2 | Demo visitor | T-095 | none |
| F-023 | Notification digests | P2 | Owner, Ops Manager | none | none |
| F-024 | Business-hour SLA calendars and carrier cut-offs | P2 | Ops Manager | none | none |
| F-025 | Storefront and marketplace read connectors | P2 | Ops Manager | none | none |
| F-026 | Saved inbox views and CSV export of lists | P2 | Ops Manager, Analyst | none | none |
| F-027 | Bulk exception actions | P2 | Ops Manager | none | none |
| F-028 | `PRODUCT_PRICE_ANOMALY` rule | P2 | Ops Manager, Analyst | none | none |
| F-029 | In-app stock adjustment form | P2 | Staff, Ops Manager | none | none |
| F-038 | Follow-up date for exceptions waiting on an external party | P2 | Staff, Ops Manager | none | none |
| F-030 | Custom roles | P3 | Owner | none | none |
| F-031 | Multi-location inventory | P3 | Ops Manager | none | none |
| F-032 | Purchase orders and supplier performance (`SUPPLIER_LATE_RECEIPT`) | P3 | Ops Manager, Analyst | none | none |
| F-033 | Carrier tracking events (`ORDER_DELIVERY_DELAYED`) | P3 | Staff | none | none |
| F-034 | Returns with reasons (`RETURN_RATE_SPIKE`) | P3 | Ops Manager, Analyst | none | none |
| F-035 | Payment entity: partial captures, split tenders, processor reconciliation | P3 | Owner, Analyst | none | none |
| F-036 | Split shipments and per-line fulfillment | P3 | Staff | none | none |
| F-037 | Per-store role scoping | P3 | Owner | none | none |

---

## 3. P0 feature specifications

### F-001 Authentication, sessions, and role-based access

**Priority** P0 · **Personas** all · **Tasks** T-042, T-060 · **Workflow** `ROLE_AND_PERMISSION_WORKFLOW.md` ·
**Modules** identity · **Decisions** ADR-0004, ADR-0007

**User problem.** Operations data includes order values, stock positions, and decisions with money
attached. When a team shares one admin login, nobody can tell who dismissed an alert or applied an
import, and a read-only visitor must never be able to change anything.

**User stories.**
- As a team member, I want to sign in with my own email and password, so that my actions are
  attributed to me.
- As an Owner, I want each person's role to decide what they can see and do, enforced by the
  server, so that hiding a button is never the only protection.

**Preconditions.** The user exists with `is_active = true` and has a membership with one role in the
organization (seeded, or created through F-016). The organization has at least one store.

**Main workflow.**
1. The user opens the sign-in page and submits email and password.
2. The server lower-cases the email, looks up the user, and verifies the argon2id hash.
3. On success the server creates an opaque random session token, stores only its SHA-256 hash in
   `user_session` with `expires_at`, sets `ro_session` (`HttpOnly`, `SameSite=Lax`, `Secure` in
   production) and the readable `ro_csrf` cookie, and updates `last_login_at`.
4. The client loads the current user: profile, organization, role, permission list, and stores.
5. Navigation and actions render according to the permission list. Every API request is still
   checked by `require_permission(...)` and by store scoping in the repositories.
6. Every `POST`/`PUT`/`PATCH`/`DELETE` carries `X-CSRF-Token` equal to `ro_csrf`.
7. Activity extends the session (12 h sliding) up to the 7-day absolute limit.
8. Sign-out sets `revoked_at` on the session and clears both cookies.

**Alternative workflows.**
- **A1 Session expired or revoked.** Any request returns 401. The UI returns to sign-in with the
  original path preserved and never resubmits a mutation automatically.
- **A2 Several stores in one organization.** A store switcher lists every store in the organization
  (BR-002). Store-scoped URLs use `/api/v1/stores/{store_id}/...`.
- **A3 User deactivated** (F-016). All of that user's sessions are revoked. The next request
  returns 401.
- **A4 Demo visitor.** "Explore the demo" follows F-013.

**Business rules.** BR-001, BR-002, BR-003; ADR-0004 (opaque server-side sessions, same-origin proxy,
CSRF double-submit); ADR-0007 (code-defined role matrix). Rate limits: login 5 per minute per IP and
email; general 300 per minute per user.

**Error conditions.**

| Condition | Response | User-facing behaviour |
|---|---|---|
| Unknown email, wrong password, or inactive user | 401 `INVALID_CREDENTIALS` (proposed) | One generic message for all three cases, so the response never reveals whether an account exists |
| More than 5 login attempts per minute for one IP and email | 429 `RATE_LIMITED` with `Retry-After` | "Too many attempts. Try again in N seconds" |
| Missing, expired, or revoked session | 401 `UNAUTHENTICATED` (proposed) | Redirect to sign-in |
| Missing or mismatched CSRF token on a mutation | 403 `CSRF_INVALID` (proposed) | "Your session needs refreshing"; the page reloads the token |
| Authenticated but lacking the permission | 403 `FORBIDDEN` (proposed) | Permission-denied state naming the missing permission |
| Resource belongs to another organization or store | 404 `NOT_FOUND` (proposed) | Not-found state. Existence is never revealed |

**Acceptance criteria.**
- **AC-001-1** *Given* an active user with correct credentials, *when* they sign in, *then* the
  response sets `ro_session` as `HttpOnly` and `SameSite=Lax` (and `Secure` in production), the
  database holds only the SHA-256 hash of the token, and an `auth.login` audit entry is written.
- **AC-001-2** *Given* a wrong password, *when* sign-in is attempted, *then* the response is 401
  with exactly the same message as for an unknown email, and `auth.login_failed` is recorded
  without the password.
- **AC-001-3** *Given* five failed attempts in one minute for the same IP and email, *when* a sixth
  is made, *then* the response is 429.
- **AC-001-4** *Given* a signed-in `STAFF` user, *when* they call an endpoint that requires
  `exceptions.assign`, *then* the response is 403 and no data changes.
- **AC-001-5** *Given* a user of organization A, *when* they request an order that belongs to
  organization B, *then* the response is 404.
- **AC-001-6** *Given* a `POST` without an `X-CSRF-Token` that matches `ro_csrf`, *then* the
  response is 403 and nothing changes.
- **AC-001-7** *Given* a session idle for more than 12 hours, or created more than 7 days ago,
  *when* any request is made, *then* the response is 401.
- **AC-001-8** *Given* a user has signed out, *when* the old token is replayed, *then* the response
  is 401.

**Permissions.**

| Action | Permission | Roles |
|---|---|---|
| Sign in, sign out, read own profile and permissions | authenticated (any active user) | all |
| Every other endpoint | as stated per feature | per §1.3 |

**Audit requirements.**

| Action | Audit `action` | Metadata |
|---|---|---|
| Successful sign-in | `auth.login` | user ID, IP, user agent, request ID |
| Failed sign-in | `auth.login_failed` | normalised email, reason category, IP. Never the password |
| Sign-out | `auth.logout` | session ID |
| Session revoked by deactivation | `auth.session_revoked` (proposed) | revoked session count, actor |

---

### F-002 Data import pipeline

**Priority** P0 · **Personas** Ops Manager (runs), Analyst and Staff (read) · **Tasks** T-052, T-065 ·
**Workflow** `IMPORT_PIPELINE.md` · **Modules** imports, catalog, orders, inventory ·
**Canonical** `STATE_MACHINES.md §4`, BR-601..608

**User problem.** Data reaches the product as CSV exports from storefronts, marketplaces, and stock
counts. Manual imports into other tools can drop or alter rows without saying so, and a bad file can
corrupt order and stock data (PROBLEM_ANALYSIS P-02).

**User stories.**
- As an Operations Manager, I want to upload an export, see exactly what would change and which rows
  fail and why, and apply it only when I am satisfied, so that I never corrupt data or lose rows
  without knowing.
- As an Analyst, I want the import history and a downloadable file of failed rows, so that I can fix
  the export mapping at the source.

**Preconditions.** The user holds `imports.run`. For `orders.csv`, the store currency is set
(BR-004). For `order_items.csv`, the referenced orders and SKUs exist (BR-605). Recommended order:
`products` → `orders` → `order_items` → `inventory_adjustments`.

**Main workflow.**
1. The user chooses an import type and, if needed, downloads its template (BR-601).
2. The user uploads a `.csv` file. An import is created in `UPLOADED` with `original_filename`,
   `file_sha256`, and `size_bytes`.
3. `VALIDATING`, file level: `FILE_EMPTY`, `FILE_TOO_LARGE` (> 5 MB), `FILE_TYPE`, `FILE_ENCODING`
   (UTF-8, BOM accepted), `TOO_MANY_ROWS` (> 20,000), `MISSING_COLUMNS`. Any failure → `REJECTED`
   (BR-602, BR-603).
4. `VALIDATING`, row level: every row is parsed with the csv module (never evaluated) and checked
   against the column contract. Issues are stored as `import_row_issue` rows with row number,
   column, code, severity, message, and raw value. Checks include duplicates in the file (BR-604),
   references (BR-605), the order axis matrix, required timestamps and their sequence, reachability
   of status moves, locked lines, and currency (`STATE_MACHINES.md §1.2–1.4`).
5. `VALIDATED`. The preview shows counts (new, updated, unchanged, error, warning), the issues
   table, a `DUPLICATE_FILE` warning when the SHA-256 matches a completed import of the same type
   (BR-607), and the expiry time (24 hours after validation).
6. The user chooses a mode. **Strict** (default) is available only when there are no `ERROR` rows.
   **Valid-rows-only** requires the user to confirm the exact number of rows that will be skipped
   (BR-606).
7. The user applies (`Idempotency-Key` header). `APPLYING` runs in one database transaction and ends
   in `COMPLETED` or `COMPLETED_WITH_ERRORS`.
8. Effects by type: products are upserted by `sku`, creating suppliers when new; orders are upserted
   by `order_number`, with status moves made through the domain transition function (an
   `order_event` with `source = IMPORT`, `import_id`, and any skipped states); reservations are
   synchronised (BR-123) and shipment movements written (BR-130); order lines are upserted by
   `(order_number, line_number)`; adjustments become ledger movements, idempotent by `reference`
   (BR-112).
9. An evaluation run with `trigger = IMPORT` starts automatically and is linked through
   `evaluation_run_id`. The import page shows its outcome counts (created, refreshed, resolved,
   reopened, superseded).
10. Issues can be downloaded at any time as an error CSV in which cells starting with `=`, `+`, `-`,
    or `@` are prefixed with an apostrophe.

**Alternative workflows.**
- **A1 File rejected.** Status `REJECTED` with the file-level code. The user fixes the file and
  uploads it as a new import.
- **A2 Row errors in strict mode.** Apply is disabled with the reason "N rows have errors". The
  user downloads the error CSV, fixes the export, and uploads again.
- **A3 Valid-rows-only.** The confirmation reads "Apply N rows and skip M rows". The status becomes
  `COMPLETED_WITH_ERRORS`, and the skipped rows stay downloadable.
- **A4 Discard.** The user discards the preview → `DISCARDED`.
- **A5 Preview expired.** After 24 hours the import becomes `DISCARDED`. Applying is refused.
- **A6 Apply fails.** The transaction rolls back and the status becomes `FAILED`. No business data
  changed. Retry moves the import back to `VALIDATING`, so it is checked against current data.
- **A7 Duplicate file.** The warning is shown. The user may still apply; upserts produce mostly
  `unchanged` rows, and adjustments already applied report `ALREADY_APPLIED`.
- **A8 Repeated apply request.** A second request with the same `Idempotency-Key` returns the first
  result and applies nothing.
- **A9 History.** Imports are listed with type, status, mode, counts, user, and a link to their
  evaluation run.

**Business rules.** BR-004, BR-112, BR-123, BR-130, BR-131, BR-502, BR-503, BR-506, BR-601..608;
`STATE_MACHINES.md §1.2` (reachability), §1.3 (axis matrix), §1.4 (timestamps), §4 (import
lifecycle).

**Error conditions.**

| Condition | Response | Behaviour |
|---|---|---|
| File-level failure | Import `REJECTED` with `FILE_EMPTY`, `FILE_TOO_LARGE`, `FILE_TYPE`, `FILE_ENCODING`, `TOO_MANY_ROWS`, or `MISSING_COLUMNS` | Shown on the import record. No rows validated |
| Row error | `import_row_issue` with severity `ERROR`: `REQUIRED`, `VALUE_TOO_LONG`, `INVALID_ENUM`, `INVALID_NUMBER`, `INVALID_INTEGER`, `NEGATIVE_VALUE`, `INVALID_DATETIME`, `DUPLICATE_KEY_IN_FILE`, `UNKNOWN_SKU`, `UNKNOWN_ORDER`, `CURRENCY_MISMATCH`, `ORDER_INVALID_STATUS_COMBINATION`, `ORDER_MISSING_TIMESTAMP`, `ORDER_TIMESTAMP_SEQUENCE`, `ORDER_TRANSITION_NOT_ALLOWED`, `ORDER_LINE_LOCKED`, `LINE_DISCOUNT_EXCEEDS_LINE` | Row listed in the preview and the error CSV |
| Row warning | `UNKNOWN_COLUMN`, `TIMEZONE_ASSUMED`, `PRICE_ZERO`, `NEGATIVE_MARGIN`, `ALREADY_APPLIED`, `DUPLICATE_FILE` | Row applied; warning shown |
| Strict apply with error rows | 409 `IMPORT_HAS_ERRORS` (proposed) | Apply disabled with reason |
| Confirmed skip count differs from the actual count | 422 `VALIDATION_ERROR` | "The preview changed. Review the skipped rows again" |
| Apply on an import not in `VALIDATED`, or preview expired | 409 `IMPORT_NOT_APPLICABLE` (proposed) | Shows the current status |
| Apply transaction fails | Import `FAILED`; 409 or 500 envelope with `request_id` | "Nothing was changed. Retry or contact the owner" |
| Upload or apply without `imports.run` | 403 `FORBIDDEN` | Upload controls hidden; history still visible with `imports.read` |

**Acceptance criteria.**
- **AC-002-1** *Given* a `products.csv` without the `reorder_point` column, *when* it is uploaded,
  *then* the import is `REJECTED` with `MISSING_COLUMNS` and no row issues are created.
- **AC-002-2** *Given* a file with 20,001 data rows, *then* it is `REJECTED` with `TOO_MANY_ROWS`.
- **AC-002-3** *Given* an `orders.csv` in which `K-2001` appears on rows 4 and 9, *then* row 9 has a
  `DUPLICATE_KEY_IN_FILE` error and row 4 is validated normally (BR-604).
- **AC-002-4** *Given* order `K-0950` is `DELIVERED` in the database and an import row sets it to
  `PAID`, *then* the row has `ORDER_TRANSITION_NOT_ALLOWED`. *Given* an order that is `PAID` and a row
  that sets `SHIPPED` with valid `shipped_at`, *then* on apply one `order_event` records
  `PAID → SHIPPED` with skipped statuses `PROCESSING`, `READY_TO_SHIP` and `source = IMPORT`.
- **AC-002-5** *Given* a row with `status = CANCELLED`, `payment_status = PAID`, and no
  `cancelled_at`, *then* the row has `ORDER_MISSING_TIMESTAMP`.
- **AC-002-6** *Given* `placed_at = 2026-10-12T08:00:00` with no offset, *then* the row is valid
  with a `TIMEZONE_ASSUMED` warning, and the value is stored as 12:00 UTC for a store in
  America/New_York (BR-502).
- **AC-002-7** *Given* a validated import with 3 error rows in strict mode, *when* the user tries to
  apply, *then* the request is refused and nothing changes. *When* the user switches to
  valid-rows-only and confirms "skip 3 rows", *then* the valid rows are applied, the status is
  `COMPLETED_WITH_ERRORS`, and the 3 rows remain downloadable.
- **AC-002-8** *Given* an apply that fails part-way, *then* no business table contains any change
  from that import and its status is `FAILED`.
- **AC-002-9** *Given* an `inventory_adjustments` row whose `reference` was applied before, *then* the
  row shows `ALREADY_APPLIED` and no movement is written (BR-112).
- **AC-002-10** *Given* an issue whose raw value is `=HYPERLINK("x")`, *when* the error CSV is
  downloaded, *then* the cell reads `'=HYPERLINK("x")`.
- **AC-002-11** *Given* an import reaches `COMPLETED`, *then* an evaluation run with
  `trigger = IMPORT` exists and is linked to the import.
- **AC-002-12** *Given* a file whose SHA-256 equals a completed import of the same type and store,
  *then* the preview shows `DUPLICATE_FILE` and apply is still possible.
- **AC-002-13** *Given* a preview validated more than 24 hours ago, *when* apply is requested,
  *then* it is refused and the import is `DISCARDED`.
- **AC-002-14** *Given* a `STAFF` user, *then* upload returns 403 and the import history is visible.

**Permissions.**

| Action | Permission | Roles |
|---|---|---|
| View history, preview, issues; download templates and error CSV | `imports.read` | all |
| Upload, choose mode, apply, discard, retry | `imports.run` | OWNER, MANAGER |

**Audit requirements.**

| Action | Audit `action` | Metadata |
|---|---|---|
| Upload | `import.create` (proposed) | type, filename, size, SHA-256, row count, resulting status (`VALIDATED` or `REJECTED`) |
| Apply | `import.apply` | mode, counts, skipped-row count, idempotency key, evaluation run ID |
| Discard | `import.discard` (proposed) | reason (`USER` or `EXPIRED`) |
| Retry after failure | `import.retry` (proposed) | previous error |

Domain records: `data_import`, `import_row_issue`, `order_event` (with `import_id`),
`inventory_movement` (with `import_id`), `evaluation_run` (`trigger = IMPORT`, `triggered_by`).

---

### F-003 Inventory positions and stock health

**Priority** P0 · **Personas** Ops Manager, Staff, Analyst · **Tasks** T-051, T-064 ·
**Workflow** `INVENTORY_LIFECYCLE.md` · **Modules** inventory, catalog · **Canonical** BR-101..104,
BR-140..152, `BUSINESS_RULES.md §2.5`

**User problem.** People compute "available stock" differently. Stock already promised to paid orders
is invisible on the shelf, and low stock is noticed only when the SKU sells out (P-03, P-07).

**User story.** As an Operations Manager, I want each SKU's on-hand, reserved, available, and incoming
quantities with a health badge and a days-of-cover estimate, so that I can see which products need
action and why.

**Preconditions.** The user holds `inventory.read` and `catalog.read`. Products have been imported.

**Main workflow.**
1. The inventory list shows per product: SKU, name, category, product status, `on_hand`,
   `reserved`, `available`, `incoming` with ETA, reorder point, health badge, average daily units
   (estimate), days of cover (estimate), supplier and lead time, and a link to any active inventory
   exception.
2. The user filters by health, category, supplier, product status, or "has active exception", and
   sorts by available, days of cover, or SKU.
3. The product detail shows the position with its formula (`available = on_hand − reserved`),
   pending demand, last cycle count time, recent movements (F-004), active reservations, and linked
   exceptions.

**Alternative workflows.**
- **A1 Product not `ACTIVE`.** Health shows "Not classified (DRAFT/ARCHIVED)". Only
  `DATA_NEGATIVE_ON_HAND` can still apply.
- **A2 No sales in the velocity window.** Days of cover shows "Not enough sales history" (BR-151).
- **A3 `reorder_point = 0`.** The product is never `BELOW_REORDER_POINT` or
  `APPROACHING_REORDER_POINT` (BR-140).
- **A4 Negative available.** Shown as a negative number with the `OVERSOLD` badge, never clamped
  (BR-102).

**Business rules.** BR-005, BR-101, BR-102, BR-103, BR-104, BR-140, BR-141, BR-150, BR-151, BR-152,
BR-506; health classification in `BUSINESS_RULES.md §2.5` (top-down, first match wins, default
`approaching_reorder_factor = 1.25`).

**Error conditions.**

| Condition | Response |
|---|---|
| Product not found, or in another store | 404 `NOT_FOUND` |
| Missing `inventory.read` | 403 `FORBIDDEN` |
| Invalid filter value or `page_size > 100` | 422 `VALIDATION_ERROR` |

**Acceptance criteria.**
- **AC-003-1** *Given* `on_hand = 6` and active reservations totalling 10, *then* available shows
  `−4` and the badge is `OVERSOLD`.
- **AC-003-2** *Given* reorder point 10: available 0 → `OUT_OF_STOCK`; 8 → `BELOW_REORDER_POINT`;
  12 → `APPROACHING_REORDER_POINT` (12 ≤ ceil(10 × 1.25) = 13); 14 → `HEALTHY`.
- **AC-003-3** *Given* `reorder_point = 0` and available 1, *then* the badge is `HEALTHY`.
- **AC-003-4** *Given* 40 units incoming with an ETA, *then* available excludes them and the UI shows
  "40 expected on {date}" (BR-103).
- **AC-003-5** *Given* 3 units on `PAYMENT_PENDING` orders, *then* available is not reduced by them
  and pending demand shows 3 (BR-101).
- **AC-003-6** *Given* average daily units of 0, *then* days of cover reads "Not enough sales
  history". Wherever velocity or cover appears, it is labelled as an estimate (BR-152).
- **AC-003-7** *Given* any product, *then* the badge in the UI equals the backend classification
  (T-064 verification).

**Permissions.** `inventory.read` and `catalog.read` (all roles). The feature has no mutations.

**Audit requirements.** Read-only. No audit entries. Changes to the underlying data are audited in
F-002 and recorded in the ledger (F-004).

---

### F-004 Inventory movement ledger and reservations

**Priority** P0 · **Personas** Ops Manager, Analyst, Staff · **Tasks** T-051, T-064 ·
**Workflow** `INVENTORY_LIFECYCLE.md` · **Modules** inventory, orders · **Canonical** BR-110..132,
`STATE_MACHINES.md §1.5, §2`, ADR-0012

**User problem.** Stock figures cannot be explained after the fact. Corrections overwrite history,
and counts that already include shipped orders get decremented a second time (P-06).

**User story.** As an Analyst, I want every change to on-hand and incoming stock recorded as an
append-only movement with its source and reference, so that I can explain any stock figure and
correct mistakes without rewriting history.

**Preconditions.** The user holds `inventory.read`. Movements are created only by imports (F-002)
and by the system when orders ship.

**Main workflow.**
1. An `inventory_adjustments` import is applied. Each row becomes one `inventory_movement` with
   `on_hand_delta` and `incoming_delta` per BR-111: `CYCLE_COUNT` sets the delta to counted minus
   current; `RECEIPT` adds to on-hand and reduces incoming, not below 0; `INCOMING_EXPECTED` and
   `INCOMING_CANCELLED` change incoming; `DAMAGE`, `SHRINKAGE` reduce on-hand; `RETURN_RESTOCK`
   increases it; `CORRECTION` applies a signed delta.
2. When an order enters committed demand (`PAID`, `PROCESSING`, `READY_TO_SHIP`), one `ACTIVE`
   reservation exists per order line (BR-120). Cancellation, payment failure, or a refund before
   shipping releases it (BR-121).
3. When an order reaches `SHIPPED` or later, its reservations become `CONSUMED` (BR-122). A
   `SHIPMENT` movement (`−quantity`, reference `order_item:{id}`) is written only if `shipped_at` is
   later than the product's latest `CYCLE_COUNT.occurred_at` (BR-130), and at most once per line
   (BR-131).
4. The balance projection is updated. The ledger view per product lists `occurred_at`, type, deltas,
   running on-hand, source (`IMPORT`, `ORDER`, `SYSTEM`), reference, import link, note, and creator.
5. The reservation view lists order, line, quantity, status, `activated_at`, and `closed_at`.

**Alternative workflows.**
- **A1 Correcting a mistake.** The user imports a `CORRECTION` with a new reference. The original
  movement stays (BR-110).
- **A2 Re-imported reference.** `ALREADY_APPLIED`, no movement (BR-112).
- **A3 Shipped before the latest count.** The reservation is consumed and no movement is written,
  because the count already reflects the shipment (BR-130).
- **A4 Order returned.** No automatic restock. A `RETURN_RESTOCK` adjustment records it after
  inspection (BR-132).
- **A5 Payment retried and paid.** A `RELEASED` reservation becomes `ACTIVE` again
  (`STATE_MACHINES.md §2`).
- **A6 Drift.** The reconciliation check (`inventory.reconcile`) recomputes the balance and reports
  drift as a defect without fixing it (BR-104). Where drift is shown is open question Q-08 in
  SCOPE_AND_NON_GOALS.

**Business rules.** BR-104, BR-110, BR-111, BR-112, BR-120, BR-121, BR-122, BR-123, BR-130, BR-131,
BR-132; invariants 1–2 in `DOMAIN_MODEL.md §4`.

**Error conditions.**

| Condition | Response |
|---|---|
| Invalid adjustment row (unknown SKU, invalid type, negative count, zero `CORRECTION`, missing reference) | Row `ERROR` in the import preview (codes per the import contract) |
| Attempt to update or delete a movement | No endpoint exists. Not reachable through the API |
| Product in another store | 404 `NOT_FOUND` |
| Missing `inventory.read` | 403 `FORBIDDEN` |

**Acceptance criteria.**
- **AC-004-1** *Given* `on_hand = 10` and a `CYCLE_COUNT` of 7, *then* one movement with
  `on_hand_delta = −3` is written and `on_hand` becomes 7.
- **AC-004-2** *Given* incoming 40 and a `RECEIPT` of 25, *then* on-hand rises by 25 and incoming
  falls by 25. *Given* incoming 40 and a `RECEIPT` of 50, *then* incoming becomes 0 and on-hand rises
  by 50.
- **AC-004-3** *Given* a cycle count at 10:00 and an order line shipped at 09:30 that is imported
  later, *then* the reservation is `CONSUMED` and no `SHIPMENT` movement exists. *Given* the line
  shipped at 10:30, *then* exactly one `SHIPMENT` movement exists for it, even after re-importing the
  order.
- **AC-004-4** *Given* an order moves from `PAID` to `CANCELLED`, *then* its reservations are
  `RELEASED` and `reserved` falls by their quantity.
- **AC-004-5** *Given* `reservations.sync_for_orders` runs twice on the same data, *then* the result
  is identical (BR-123).
- **AC-004-6** *Given* any completed import, *then* for every product `on_hand = Σ on_hand_delta` and
  `reserved = Σ ACTIVE reservation quantity` (invariants I-1, I-2 in SUCCESS_METRICS).
- **AC-004-7** *Given* an order reaches `RETURNED`, *then* on-hand does not change until a
  `RETURN_RESTOCK` adjustment is imported.

**Permissions.**

| Action | Permission | Roles |
|---|---|---|
| View movements and reservations | `inventory.read` | all |
| Create adjustments | `imports.run` (through F-002) | OWNER, MANAGER |
| `SHIPMENT` movements, reservation changes | system | n/a |

**Audit requirements.** The ledger is the domain record: every movement carries `source`,
`reference`, `import_id`, and `created_by`. The user action is audited as `import.apply` (F-002).
Detected drift is recorded as `inventory.drift_detected` (proposed, actor `SYSTEM`) with the product
and the expected and actual values.

---

### F-005 Orders list and detail

**Priority** P0 · **Personas** Staff, Ops Manager, Owner · **Tasks** T-050, T-063 ·
**Workflow** `ORDER_LIFECYCLE.md` · **Modules** orders · **Canonical** `STATE_MACHINES.md §1`,
BR-201..206

**User problem.** An order's lifecycle, payment, and fulfillment state live in different systems.
Skipped states are invisible, and nobody can see which problems touch a given order (P-01, P-04,
P-05).

**User story.** As Operations Staff, I want an order's three status axes, its timeline, lines,
ship-by deadline, and linked exceptions on one page, so that I can see what the order needs next.

**Preconditions.** The user holds `orders.read`. Orders have been imported.

**Main workflow.**
1. The orders list (server-side pagination, at most 100 per page) shows order number, channel,
   `placed_at`, `status`, `payment_status`, `fulfillment_status`, total, `ship_by` with its source,
   an overdue flag, and the count of active exceptions.
2. Filters: each status axis, channel, `placed_at` range, overdue, has active exception, exact
   `customer_ref`. Sorting: `placed_at`, `ship_by`, total.
3. The order detail shows the three axes; timestamps (placed, paid, ship-by and its source, shipped,
   delivered, cancelled) in the store time zone; lines with SKU links, quantity, unit price,
   discount, and reservation status; the totals check (`expected_total` and difference, BR-205);
   the timeline from `order_event` with skipped states and source; and linked exceptions through
   `exception_entity_link` (roles `PRIMARY` and `AFFECTED`).

**Alternative workflows.**
- **A1 Cancelled with payment still captured.** A banner reads "Refund pending since
  {cancelled_at}" from the moment of cancellation (BR-206), even before the
  `ORDER_REFUND_PENDING` exception exists (after 24 hours).
- **A2 No lines imported yet.** "No lines imported"; the totals check is not evaluated.
- **A3 `REFUNDED` with `fulfillment_status = DELIVERED`.** The detail states that the goods were
  delivered and the payment refunded (`STATE_MACHINES.md §1.1`).
- **A4 Derived ship-by.** With `ship_by_source = STORE_SLA`, the UI shows
  "paid_at + {fulfillment_sla_hours} h".

**Business rules.** `STATE_MACHINES.md §1.1–1.5`; BR-201, BR-202, BR-203, BR-205, BR-206, BR-501,
BR-503, BR-505.

**Error conditions.** 404 for an unknown order or one in another store; 403 without `orders.read`;
422 for invalid filters.

**Acceptance criteria.**
- **AC-005-1** *Given* an order paid at 2026-10-12 08:00 EDT with no imported ship-by, *then*
  ship-by shows 2026-10-14 08:00 EDT with source `STORE_SLA` (BR-201).
- **AC-005-2** *Given* `as_of` equal to `ship_by`, *then* the order is not overdue; one second later
  it is (BR-202).
- **AC-005-3** *Given* an order imported as `PAID` and later as `SHIPPED`, *then* the timeline shows
  one `PAID → SHIPPED` event with skipped `PROCESSING`, `READY_TO_SHIP`, source `IMPORT`, and a link
  to the import.
- **AC-005-4** *Given* lines summing to 120.00, no order discount, shipping 10.00, tax 0.00, and a
  recorded total of 125.00, *then* the detail shows expected 130.00, difference −5.00, and the linked
  `DATA_ORDER_TOTAL_MISMATCH` exception.
- **AC-005-5** *Given* any order, *then* the only customer field shown is the opaque
  `customer_ref` (BR-505).
- **AC-005-6** *Given* an order listed as affected by an `INVENTORY_OVERSOLD` exception, *then* the
  order detail links that exception.
- **AC-005-7** *Given* any role, *then* the order pages contain no control that changes order data.

**Permissions.** `orders.read` (all roles). No mutations in v1. Order changes arrive only through
imports (F-002).

**Audit requirements.** Read-only. Status history is the `order_event` table, written by imports.

---

### F-006 Exception detection engine and evaluation runs

**Priority** P0 · **Personas** system; Ops Manager (manual trigger) · **Tasks** T-053 ·
**Workflow** `EXCEPTION_MANAGEMENT.md` · **Modules** exceptions (reads catalog, orders, inventory
through their services) · **Canonical** `EXCEPTION_CATALOG.md`, `STATE_MACHINES.md §3.3–3.4`,
`PRIORITY_MODEL.md`, ADR-0003, ADR-0008, ADR-0009

**User problem.** Problems are discovered by their consequences, not their conditions, and nothing
checks whether a fix worked (P-08).

**User stories.**
- As an Operations Manager, I want every rule evaluated after each import and on demand, with one
  exception per condition, so that I never compare exports by hand.
- As an Owner, I want a problem someone marked resolved to be checked against the data, so that
  "done" means done.

**Preconditions.** Data has been imported for the store. A manual trigger requires
`evaluations.run`. No other run for the store holds its advisory lock.

**Main workflow.**
1. A trigger occurs: an import completes (`IMPORT`) or a user clicks "Run analysis" (`MANUAL`).
   Scheduled runs (`SCHEDULED`) are F-014.
2. An `evaluation_run` is created with `trigger`, `as_of` (fixed for the whole run), the list of
   rules (all nine by default), and `triggered_by`.
3. The run takes the store's Postgres advisory lock, so runs for one store never overlap.
4. A snapshot is loaded: products, balances, reservations, orders and lines, settings.
5. Each rule runs as a pure function `(snapshot, settings, as_of) → findings`. Rules never read the
   clock (BR-504).
6. Precedence is applied: one inventory exception per product, most severe first (BR-401);
   `ORDER_FULFILLMENT_OVERDUE` supersedes `ORDER_STALLED_AFTER_PAYMENT`.
7. Each finding is reconciled with the latest exception for its dedup key according to the table in
   `STATE_MACHINES.md §3.3`: create, refresh, auto-resolve (`CONDITION_CLEARED`), verify
   (`verified_at`), reopen (`VERIFICATION_FAILED` or `RECURRED_WITHIN_WINDOW`), new occurrence
   (`previous_occurrence_id`), dismissed handling, and supersede (`SUPERSEDED`, assignee carried
   over).
8. Priority (`S + A + E + D + T`, capped at 100), band, and breakdown are computed. `due_at` is set
   on creation and recalculated when severity changes (`PRIORITY_MODEL.md`).
9. `exception_event` rows are written with `actor_type = SYSTEM` and the run ID: `DETECTED`,
   `EVIDENCE_UPDATED` (only when the evidence changed materially), `SEVERITY_CHANGED`,
   `AUTO_RESOLVED`, `VERIFIED`, `REOPENED`, `SUPERSEDED`. `exception_entity_link` rows connect each
   exception to its primary and affected entities.
10. The run records counts (created, refreshed, resolved, reopened, superseded), `finished_at`, and
    its status, then releases the lock.

**Alternative workflows.**
- **A1 Partial rule set.** Only the rules that ran can auto-resolve or verify. A run limited to
  inventory rules never resolves order exceptions.
- **A2 Manual trigger while a run is active.** Rejected with 409 and the active run's ID (proposed,
  open question Q-03).
- **A3 Run fails.** The run is recorded with a failure status and an error. No exception changes
  from that run persist (proposed: one transaction per run, to be confirmed in ADR-0009).
- **A4 Priority weights changed** (F-015). Scores are recalculated at the next run.
- **A5 Dismissed exception, condition still present.** Only `last_detected_at` is updated. No event.
- **A6 Same request repeated.** A manual trigger with a repeated `Idempotency-Key` returns the same
  run.

**Business rules.** BR-140, BR-150..152, BR-201..206, BR-401..404, BR-504; health classification
`BUSINESS_RULES.md §2.5`; all nine rule definitions in `EXCEPTION_CATALOG.md`; reconciliation and
verification `STATE_MACHINES.md §3.3–3.4`; scoring and due date `PRIORITY_MODEL.md`. Defaults:
`stall_threshold_hours = 12`, `fulfillment_sla_hours = 48`, `refund_overdue_hours = 24`,
`reopen_window_hours = 72`, `exposure_cap = 5000`.

**Error conditions.**

| Condition | Response |
|---|---|
| Manual trigger without `evaluations.run` | 403 `FORBIDDEN` |
| Manual trigger while the store's lock is held | 409 `EVALUATION_IN_PROGRESS` (proposed) with the running run's ID |
| Rule or persistence failure | Run recorded as failed with `error`; no partial exception changes (proposed) |
| Invalid run parameters (unknown rule ID) | 422 `VALIDATION_ERROR` |

**Acceptance criteria.**
- **AC-006-1 Oversold.** *Given* SKU `KHK-DO-55` with `on_hand = 6` and paid orders K-1001 (2),
  K-1002 (3), K-1003 (2), K-1004 (3) in that `paid_at` order, all lines at 89.00, and the earliest
  affected ship-by 20 hours after `as_of`, *when* a run executes, *then* exactly one
  `INVENTORY_OVERSOLD` exception exists with severity `CRITICAL`, affected orders K-1003 (1 uncovered)
  and K-1004 (3 uncovered), exposure 356.00, priority `50 + 6 + 10 + 8 + 0 = 74` (band P1), and
  `due_at = first_detected_at + 4 h`.
- **AC-006-2 Precedence.** *Given* an active product with `available = 0` and pending demand of 2,
  *then* only `INVENTORY_OVERSELL_RISK` is raised for it, not `INVENTORY_OUT_OF_STOCK`.
- **AC-006-3 Supersede.** *Given* an active `INVENTORY_BELOW_REORDER_POINT` assigned to a staff
  member, *when* the product becomes oversold, *then* the old exception is `RESOLVED` with
  `SUPERSEDED` and `superseded_by_id`, and the new `INVENTORY_OVERSOLD` exception has the same
  assignee.
- **AC-006-4 Refresh.** *Given* an active exception for a dedup key, *when* the condition is found
  again, *then* no second exception is created, `last_detected_at` and `detection_count` are
  updated, and `EVIDENCE_UPDATED` is written only if the evidence changed materially.
- **AC-006-5 Auto-resolve.** *Given* an active `ORDER_REFUND_PENDING`, *when* an import sets the
  order's `payment_status` to `REFUNDED` and the run executes, *then* the exception is `RESOLVED`
  with `CONDITION_CLEARED`.
- **AC-006-6 Verification fails.** *Given* a user resolved an `INVENTORY_OVERSOLD` exception, *when*
  the next run still finds `available < 0`, *then* the exception is `REOPENED` with reason
  `VERIFICATION_FAILED` and `reopen_count` increases by 1.
- **AC-006-7 Verification passes.** *Given* a user resolved an exception, *when* the next run that
  executes its rule finds no condition, *then* `verified_at` is set and a `VERIFIED` event is written.
- **AC-006-8 Recurrence.** *Given* an exception resolved at time T whose condition cleared, *when*
  it is detected again at T + 48 h, *then* it is `REOPENED` with `RECURRED_WITHIN_WINDOW`. *When*
  instead it is detected at T + 80 h, *then* a new `OPEN` exception is created with
  `previous_occurrence_id` pointing to the old one.
- **AC-006-9 Dismissed.** *Given* a dismissed exception whose condition persists, *then* it stays
  `DISMISSED` and only `last_detected_at` changes. *When* the condition clears, *then*
  `condition_cleared_at` is set. *When* it returns, *then* a new `OPEN` exception linked by
  `previous_occurrence_id` is created.
- **AC-006-10 Partial run.** *Given* a run limited to inventory rules, *then* no order exception
  changes status.
- **AC-006-11 Stalled and overdue boundaries.** *Given* order K-1187 paid at 2026-10-12 08:00 EDT
  with derived ship-by 2026-10-14 08:00 EDT and still `PAID`: at `as_of` 2026-10-12 20:00 no
  exception exists; at 20:01 `ORDER_STALLED_AFTER_PAYMENT` is `MEDIUM`; at 2026-10-13 20:00 it is
  `HIGH`; at 2026-10-14 08:00 it is still stalled (not overdue, BR-202); at 08:01
  `ORDER_FULFILLMENT_OVERDUE` is `MEDIUM` and the stalled exception is `SUPERSEDED`; after
  2026-10-15 08:00 it is `HIGH`; after 2026-10-17 08:00 it is `CRITICAL`.
- **AC-006-12 Refund severity.** *Given* order K-1240 cancelled at 2026-10-12 10:00 EDT with payment
  captured, *then* no exception exists at 2026-10-13 10:00, an `ORDER_REFUND_PENDING` exception is
  `HIGH` after that, and it becomes `CRITICAL` after 2026-10-15 10:00.
- **AC-006-13 Determinism.** *Given* the same snapshot and `as_of`, *then* two runs produce identical
  findings.
- **AC-006-14 Import trigger.** *Given* an import completes, *then* a run with `trigger = IMPORT`
  exists and is linked to it.
- **AC-006-15 No overlap.** *Given* two triggers for the same store at the same moment, *then* their
  runs never execute concurrently.
- **AC-006-16 Inactive products.** *Given* an `ARCHIVED` product with `available = 0`, *then* no
  `INVENTORY_OUT_OF_STOCK` exception is raised (`EXCEPTION_CATALOG.md`, "not exceptions").

**Permissions.**

| Action | Permission | Roles |
|---|---|---|
| Trigger "Run analysis" | `evaluations.run` | OWNER, MANAGER |
| View evaluation runs and their counts | `exceptions.read` | all |
| Detection, reconciliation, verification | system | n/a |

**Audit requirements.**

| Action | Record |
|---|---|
| Manual trigger | `audit_log` action `evaluation.run` (proposed): run ID, rule list, idempotency key |
| Every system change to an exception | `exception_event` with `actor_type = SYSTEM` and `evaluation_run_id` |
| The run itself | `evaluation_run` row with trigger, `as_of`, rules, counts, status, error |

---

### F-007 Exception inbox

**Priority** P0 · **Personas** Ops Manager, Staff · **Tasks** T-054, T-062 ·
**Workflow** `EXCEPTION_MANAGEMENT.md` · **Modules** exceptions · **Canonical** `STATE_MACHINES.md §3.1`,
`PRIORITY_MODEL.md`

**User problem.** Without one ranked list, the manager builds "what's wrong today" by hand and staff
wait for instructions (JTBD-M1, JTBD-S1).

**User stories.**
- As an Operations Manager, I want one list of active exceptions ranked by priority, with filters
  and quick views, so that I can triage and assign the most urgent work first.
- As Operations Staff, I want to see my work and the unassigned work I can claim, so that I can keep
  working without waiting.

**Preconditions.** The user holds `exceptions.read`. At least one evaluation run has completed (an
empty state explains otherwise).

**Main workflow.**
1. The default view lists active exceptions (`OPEN`, `ACKNOWLEDGED`, `IN_PROGRESS`, `REOPENED`)
   sorted by `priority_score` descending, then `due_at` ascending, then `first_detected_at`
   ascending.
2. Each row shows priority score and band, title, type and category, severity, status, assignee,
   `due_at`, business deadline, value at risk, affected-order count, age, detection count, and a
   reopened badge with `reopen_count`.
3. Quick views: *All active* · *My work* (assigned to me) · *Unassigned* · *Past due* (`due_at`
   passed) · *Reopened* · *Resolved, last 7 days* · *Dismissed*.
4. Filters: status, category, exception type, severity, band, assignee, entity (SKU or order
   number), detection date range. Sorting: priority, `due_at`, `first_detected_at`, exposure. The URL
   holds the filter state.
5. Row actions, by permission: Acknowledge, Claim (unassigned only), Assign. They run through F-008.
6. A header line shows the last evaluation (`as_of`, trigger) and links to data freshness (F-010).

**Alternative workflows.**
- **A1 No evaluation has run yet.** The empty state says so, and offers "Run analysis" to users with
  `evaluations.run` or "Import data" to users with `imports.run`.
- **A2 No active exceptions.** "No active exceptions as of {as_of}" (not the same message as A1).
- **A3 Read-only roles.** Row actions are hidden or disabled with a reason (for example "Requires
  exceptions.work").
- **A4 Row changed by someone else.** The action returns 409, and the row refreshes with the current
  state.

**Business rules.** Active states (`STATE_MACHINES.md §3.1`); priority bands and the due date
(`PRIORITY_MODEL.md`); value at risk is never labelled as loss (BR-404); times in store time zone
(BR-501); store scoping (BR-003).

**Error conditions.** 422 for an invalid filter or `page_size > 100`; 403 without
`exceptions.read`; 401 when the session has ended.

**Acceptance criteria.**
- **AC-007-1** *Given* active exceptions with scores 81, 58, and 26, *then* they are listed in that
  order. *Given* two equal scores, *then* the one with the earlier `due_at` comes first.
- **AC-007-2** *Given* a `STAFF` user, *then* "My work" shows only exceptions assigned to them, and
  "Unassigned" shows active exceptions with no assignee, each with a Claim action.
- **AC-007-3** *Given* an `ANALYST`, *then* no row action is enabled, and each disabled action states
  the missing permission.
- **AC-007-4** *Given* any row with exposure, *then* the column reads "Value at risk" and never
  "Loss".
- **AC-007-5** *Given* `due_at` in the past, *then* the row is marked past due, and times show in the
  store time zone with its abbreviation.
- **AC-007-6** *Given* `page_size = 101`, *then* the response is 422. Valid responses have the shape
  `{items, page, page_size, total}`.
- **AC-007-7** *Given* exceptions in two stores, *then* the inbox for store A never shows store B's
  exceptions.

**Permissions.**

| Action | Permission | Roles |
|---|---|---|
| List, filter, sort | `exceptions.read` | all |
| Row actions | see F-008 | per action |

**Audit requirements.** Listing is not audited. Row actions are audited as in F-008.

---

### F-008 Exception lifecycle and assignment

**Priority** P0 · **Personas** Ops Manager, Staff, Owner · **Tasks** T-054, T-062 ·
**Workflow** `EXCEPTION_MANAGEMENT.md` · **Modules** exceptions · **Canonical** `STATE_MACHINES.md §3.1–3.4`,
`PRIORITY_MODEL.md` (due date)

**User problem.** Problems raised in chat have no owner and no deadline, and "done" is never checked
(P-08; value questions 6 and 7).

**User stories.**
- As an Operations Manager, I want to assign each exception to a person with a due date, so that
  every problem has an owner.
- As Operations Staff, I want to claim, start, and resolve exceptions with a resolution code and a
  note, so that my work is recorded and can be verified.
- As an Operations Manager, I want to dismiss a finding with a reason, or reopen one that was closed
  wrongly, so that the queue reflects reality.

**Preconditions.** The exception belongs to the user's store. The current status allows the
transition (`STATE_MACHINES.md §3.2`). The user holds the permission for the action. The request
may include `expected_version` for optimistic concurrency.

**Actions.**

| Action | From → to | Permission | Required input | Extra rule |
|---|---|---|---|---|
| Acknowledge | `OPEN`, `REOPENED` → `ACKNOWLEDGED` | `exceptions.work` | none | none |
| Claim | assignee empty → me | `exceptions.work` | none | Only when unassigned |
| Assign, reassign, unassign | any active | `exceptions.assign` | assignee ID | Assignee must be an active member whose role has `exceptions.work` (proposed, Q-06) |
| Start | `OPEN`, `ACKNOWLEDGED`, `REOPENED` → `IN_PROGRESS` | `exceptions.work` | none | If unassigned, the actor is assigned. `STAFF` only on exceptions that are unassigned or their own |
| Resolve | any active → `RESOLVED` | `exceptions.work` | `resolution_code` (manual codes) and `resolution_note` of at least 10 characters | Actor is the assignee or holds `exceptions.manage` |
| Dismiss | any active → `DISMISSED` | `exceptions.manage` | dismissal reason (`FALSE_POSITIVE`, `ACCEPTED_RISK`, `DUPLICATE`, `NOT_ACTIONABLE`) and a note | none |
| Reopen | `RESOLVED`, `DISMISSED` → `REOPENED` | `exceptions.manage` | reason note | none |
| Add note | any status | `exceptions.work` | body, 1–4000 characters | Notes are append-only |
| Change due date | any active | `exceptions.assign` | new `due_at` in the future | Interaction with automatic recalculation: Q-04 |

Manual resolution codes: `STOCK_REPLENISHED`, `ORDER_FULFILLED`, `REFUND_ISSUED`, `DATA_CORRECTED`,
`CUSTOMER_CONTACTED`, `FIXED_IN_SOURCE_SYSTEM`, `OTHER`.

**Main workflow.**
1. The manager opens an `OPEN` exception and assigns it to a staff member (`ASSIGNED` event,
   `exception_assignment` row).
2. The staff member acknowledges it (optional) and starts work (`IN_PROGRESS`).
3. The staff member acts in the source system (ships the order, issues the refund, counts stock) and
   adds notes.
4. The staff member resolves it with a code and a note.
5. The next evaluation verifies the resolution (F-006): `verified_at` is set, or the exception
   returns as `REOPENED` with `VERIFICATION_FAILED`.

**Alternative workflows.**
- **A1 Waiting on an external party.** The owner keeps the exception `IN_PROGRESS` with a note, for
  example while waiting for a supplier delivery. When the stock arrives and is imported, the system
  resolves it with `CONDITION_CLEARED` (`STATE_MACHINES.md §3.4`).
- **A2 Two staff claim the same exception.** The first claim wins. The second gets 409 and sees the
  new assignee.
- **A3 Resolving while the condition is still present.** The resolve dialog shows the latest
  evidence and when the relevant data was last imported, and warns that verification will reopen
  the exception unless updated data arrives first (open question Q-07).
- **A4 Manager resolves someone else's exception.** Allowed with `exceptions.manage`.
- **A5 Superseded while in progress.** The more severe exception takes over the assignee (BR-401).
  The old exception keeps its notes and links to its successor.
- **A6 AI-drafted note.** Accepting a copilot draft (F-011) adds a note with
  `source = AI_DRAFT_ACCEPTED` and the accepting user as author.
- **A7 Reopening a dismissed exception whose condition has cleared.** The next run auto-resolves it
  with `CONDITION_CLEARED`.

**Business rules.** `STATE_MACHINES.md §3.1–3.4`; due date rules in `PRIORITY_MODEL.md` (overrides
need `exceptions.assign` and are audited); notes ≤ 4000 characters and append-only
(`DOMAIN_MODEL.md`); `DOMAIN_MODEL.md §4` invariant 4 (every status change has an event).

**Error conditions.**

| Condition | Response |
|---|---|
| Transition not allowed from the current status | 409 `EXCEPTION_TRANSITION_NOT_ALLOWED` |
| `expected_version` is stale | 409 `VERSION_CONFLICT` (proposed) |
| `STAFF` starts or resolves an exception assigned to someone else | 403 `FORBIDDEN` |
| Claim on an exception that already has an assignee | 409 `EXCEPTION_ALREADY_ASSIGNED` (proposed) |
| Missing resolution code, note under 10 characters, unknown dismissal reason, note over 4000 characters, due date in the past, ineligible assignee | 422 `VALIDATION_ERROR` with field details |
| `ANALYST` or `VIEWER` attempts any action | 403 `FORBIDDEN` |
| Exception in another store | 404 `NOT_FOUND` |

**Acceptance criteria.**
- **AC-008-1** *Given* an unassigned exception, *when* a `STAFF` user claims it, *then* they become
  the assignee, an `ASSIGNED` event and an `exception_assignment` row are written, and
  `exception.claim` is audited.
- **AC-008-2** *Given* an exception assigned to another user, *when* a `STAFF` user tries to start
  it, *then* the response is 403 and nothing changes.
- **AC-008-3** *Given* an unassigned `OPEN` exception, *when* a `MANAGER` starts it, *then* the
  manager becomes the assignee and the status is `IN_PROGRESS`.
- **AC-008-4** *Given* an assigned `IN_PROGRESS` exception, *when* the assignee resolves it without a
  code, or with the note "done", *then* the response is 422. *When* they resolve it with
  `ORDER_FULFILLED` and "Shipped with tracking 1Z999, label printed", *then* it is `RESOLVED` with
  `resolved_by`, `resolved_at`, the code, and the note.
- **AC-008-5** *Given* a `STAFF` user, *when* they try to dismiss, *then* the response is 403.
  *Given* a `MANAGER`, *when* they dismiss with `FALSE_POSITIVE` and a note, *then* the exception is
  `DISMISSED`.
- **AC-008-6** *Given* a `RESOLVED` exception, *when* someone tries to move it straight to
  `IN_PROGRESS`, *then* the response is 409 `EXCEPTION_TRANSITION_NOT_ALLOWED`.
- **AC-008-7** *Given* two users loaded the same version, *when* the second submits with the stale
  `expected_version`, *then* the response is 409 and nothing changes.
- **AC-008-8** *Given* a `MANAGER` changes `due_at`, *then* a `DUE_DATE_CHANGED` event and an audit
  entry with the old and new values are written. *Given* a `STAFF` user tries the same, *then* the
  response is 403.
- **AC-008-9** *Given* any successful action, *then* exactly one matching `exception_event` (plus an
  `exception_assignment` row where relevant) and one `audit_log` entry with the request ID exist.
- **AC-008-10** *Given* any note, *then* there is no endpoint to edit or delete it.
- **AC-008-11** *Given* a user without the needed permission, *then* the UI hides or disables the
  action with a reason (T-062).

**Permissions.** As in the actions table. Summary: `exceptions.work` for OWNER, MANAGER, STAFF;
`exceptions.assign` and `exceptions.manage` for OWNER and MANAGER.

**Audit requirements.**

| Action | Audit `action` (proposed unless noted) | Metadata |
|---|---|---|
| Acknowledge | `exception.acknowledge` | exception ID, from and to status |
| Claim | `exception.claim` | exception ID |
| Assign, reassign, unassign | `exception.assign`, `exception.unassign` | previous and new assignee |
| Start | `exception.start` | auto-assigned (yes or no) |
| Resolve | `exception.resolve` (in `DOMAIN_MODEL.md`) | resolution code, note length |
| Dismiss | `exception.dismiss` | dismissal reason |
| Reopen | `exception.reopen` | previous status |
| Add note | `exception.note_add` | note ID, source (`USER` or `AI_DRAFT_ACCEPTED`) |
| Change due date | `exception.due_date_change` | previous and new `due_at` |

The note and resolution text live in `exception_note` and on the exception. The audit entry links to
them rather than copying them.

---

### F-009 Exception investigation view

**Priority** P0 · **Personas** Staff, Ops Manager, Analyst · **Tasks** T-062 ·
**Workflow** `EXCEPTION_MANAGEMENT.md`, `AI_ASSISTED_INVESTIGATION.md` · **Modules** exceptions,
orders, inventory · **Canonical** finding structure in `EXCEPTION_CATALOG.md`, `PRIORITY_MODEL.md`

**User problem.** Answering "why was this flagged, what is affected, and what do I do?" takes three
systems today (JTBD-S2, JTBD-A4).

**User story.** As Operations Staff, I want one page with the evidence, calculation, priority
breakdown, affected orders, related exceptions, history, notes, and recommended action, so that I
can act without opening other systems.

**Preconditions.** The user holds `exceptions.read`. The exception belongs to the user's store.

**Main workflow.** The page shows these sections:
1. **Header.** Title, exception type, `rule_id` with version (for example `INV-OVERSOLD@1`),
   category, severity, status, assignee, `due_at`, business deadline, first and last detection,
   detection count, reopen count, and the `as_of` of the evaluation that last updated it.
2. **Why it matters.** Priority score and band with the breakdown (S, A, E, D, T), the formula, and
   the limitations text from `PRIORITY_MODEL.md`. Value at risk with the tooltip "gross order-line
   value at risk, not loss".
3. **Evidence.** Typed facts, each with its value and a link to its source record (product, order,
   movement, import row).
4. **Calculation.** Formula inputs and outputs (for example `available = on_hand − reserved =
   6 − 10 = −4`).
5. **Affected orders.** For an oversold SKU, the FIFO allocation by `paid_at` with each order's
   uncovered quantity (BR-402). For order exceptions, the order and its lines.
6. **Recommended action.** The rule-authored text, labelled as a rule recommendation, not AI.
7. **Related.** Other active exceptions on the same entities, `superseded_by`, and
   `previous_occurrence`.
8. **History.** All `exception_event` rows in time order with the actor (user name, or "System" with
   a link to the evaluation run).
9. **Notes** and the **actions panel** (F-008), and the **copilot panel** with "Explain this
   exception" (F-011).

**Alternative workflows.**
- **A1 Evidence updated while open.** A banner shows "Evidence updated at {time}" with a reload
  link. Earlier evidence versions are available from `EVIDENCE_UPDATED` events.
- **A2 Superseded.** A banner links the superseding exception.
- **A3 Resolved, verification pending.** "Resolved by {user}; will be verified at the next
  evaluation."
- **A4 Read-only role.** All sections visible; actions hidden or disabled with a reason; copilot
  available.

**Business rules.** Finding structure (`EXCEPTION_CATALOG.md`); BR-402; BR-404; BR-152 (estimates
labelled); BR-501; priority limitations (`PRIORITY_MODEL.md`).

**Error conditions.** 404 for an unknown exception or one in another store; 403 without
`exceptions.read`. Every section has loading, empty, and error states.

**Acceptance criteria.**
- **AC-009-1** *Given* any exception, *then* the breakdown shows S, A, E, D, and T values that add
  up to the displayed score (capped at 100), with the formula and the limitations text.
- **AC-009-2** *Given* the oversold example from AC-006-1, *then* affected orders are listed in
  `paid_at` order with uncovered quantities 1 (K-1003) and 3 (K-1004), each linking to its order.
- **AC-009-3** *Given* any evidence fact, *then* it links to the record it came from.
- **AC-009-4** *Given* an `ORDER_FULFILLMENT_OVERDUE` exception for an order in `READY_TO_SHIP`,
  *then* the recommended action reads "Hand over to the carrier and record tracking." and is
  labelled as a rule recommendation.
- **AC-009-5** *Given* average daily units or days of cover in the evidence, *then* they are
  labelled "estimate".
- **AC-009-6** *Given* any exception, *then* `rule_id` with version and the evaluation `as_of` are
  shown, so the finding can be reproduced (BR-504).
- **AC-009-7** *Given* a history with system and user events, *then* every event shows its actor,
  and system events link to their evaluation run.

**Permissions.** `exceptions.read` to view (all roles); actions per F-008; copilot panel needs
`copilot.use` (all roles).

**Audit requirements.** Viewing is not audited. Actions taken from the page are audited as in F-008.

---

### F-010 Operations overview dashboard

**Priority** P0 · **Personas** Owner, Ops Manager, Analyst · **Tasks** T-057, T-061 ·
**Workflow** `EXCEPTION_MANAGEMENT.md` (triage entry point) · **Modules** analytics (read-only over
other modules)

**User problem.** The Owner and Manager need to know what is happening and what is at risk without
reading every list (value question 1, JTBD-O1).

**User story.** As a Store Owner, I want one overview of what needs attention now, whether someone
owns it, and how fresh the data is, so that I can decide whether to step in.

**Preconditions.** The user holds `dashboard.read` (and `analytics.read` for trends). Data has been
imported.

**Main workflow.** The dashboard shows:
1. **Attention list.** The 10 highest-priority active exceptions, each linking to its investigation
   view.
2. **Exception KPIs.** Active exceptions by band (P1–P4) and by category; unassigned active count;
   past-due count; `CRITICAL` count.
3. **Fulfillment.** Orders awaiting shipment (`PAID`, `PROCESSING`, `READY_TO_SHIP`), overdue and
   stalled counts, on-time ship rate for the last 7 and 30 days (M-19).
4. **Payments.** Orders with a refund pending (cancelled with payment captured), split into "within
   threshold" and "overdue" (BR-206).
5. **Inventory health.** Counts of `ACTIVE` products by health: `OVERSOLD`, `OUT_OF_STOCK`,
   `BELOW_REORDER_POINT`, `APPROACHING_REORDER_POINT`, `HEALTHY`.
6. **Value at risk** per category (inventory, fulfillment, payment) and the number of distinct
   orders at risk. No grand total across categories (open question Q-11).
7. **Trends (30 days).** Exceptions created and resolved per day; exceptions by type and severity;
   fulfillment performance.
8. **Data status.** The last evaluation run (`as_of`, trigger, status, counts) and the time since
   the last completed import of each type (M-05).

**Alternative workflows.**
- **A1 No data yet.** An onboarding empty state links to import templates (with `imports.run`) or
  explains that no data has been imported.
- **A2 Last evaluation failed.** A banner shows the failure and the time of the last successful run.
- **A3 Demo organization.** The demo label is shown (F-013).
- **A4 One widget fails.** That widget shows its error state; the others still render.

**Business rules.** BR-141 (health computed on read), BR-202, BR-206, BR-404, BR-501, BR-503,
`BUSINESS_RULES.md §2.5`. All figures come from queries that reconcile with the underlying tables
(T-057).

**Error conditions.** 403 without `dashboard.read` (permission-denied state); widget-level errors
with `request_id`.

**Acceptance criteria.**
- **AC-010-1** *Given* any dashboard figure, *then* it equals the documented query over the
  underlying tables (T-057 reconciliation tests). No figure is hard-coded.
- **AC-010-2** *Given* active exceptions with exposure in two categories, *then* value at risk is
  shown per category with the tooltip "gross order-line value at risk", and no cross-category total
  appears.
- **AC-010-3** *Given* a KPI is clicked, *then* the matching list opens with the corresponding filter
  applied.
- **AC-010-4** *Given* any state, *then* the last evaluation time and the age of each import type's
  data are visible, in the store time zone.
- **AC-010-5** *Given* each widget, *then* it has loading, empty, and error states.

**Permissions.** `dashboard.read` and `analytics.read` (all roles). No mutations; the "Run analysis"
shortcut is F-006 and needs `evaluations.run`.

**Audit requirements.** Read-only. None.

---

### F-011 Operations copilot with deterministic fallback

**Priority** P0 · **Personas** all · **Tasks** T-071, T-072, T-073 ·
**Workflow** `AI_ASSISTED_INVESTIGATION.md` · **Modules** ai (reads other modules through
allowlisted tools) · **Decisions** ADR-0003, ADR-0010

**User problem.** Staff and owners need plain-language explanations of the data. A general AI over
data can mix computed facts with plausible guesses (JTBD-S7, JTBD-O4).

**User stories.**
- As Operations Staff, I want to ask "why is KHK-DO-55 flagged?" and get an answer whose every fact
  cites a record, so that I can explain it to my manager.
- As an Operations Manager, I want the copilot to draft an investigation note that I edit and accept,
  so that documenting work is quick and still mine.
- As an Owner, I want the copilot to work without any LLM key, so that the product never depends on
  an external provider.

**Preconditions.** The user holds `copilot.use`. The provider is the LLM adapter when a key is
configured on the server, otherwise the deterministic adapter.

**Main workflow (question and answer).**
1. The user opens the copilot (global panel, or from an exception with context type `EXCEPTION`).
2. The user asks a question. Requests are limited to 20 per minute per user.
3. The provider chooses tools from the allowlist: `get_dashboard_summary`, `list_exceptions`,
   `get_exception`, `get_exception_history`, `get_related_orders`, `get_product`,
   `get_inventory_position`, `get_inventory_movements`, `get_overdue_orders`, `get_import_errors`,
   `get_operational_trends`. Each tool validates its arguments, checks the user's permission, scopes
   to the store, caps results (at most 50 rows), and writes an `ai_tool_call` row.
4. The answer follows the structured schema: `summary`, `facts` (with refs), `metrics` (with formula
   and refs), `estimates` (with basis), `recommendations` (with rationale), `limitations`,
   `references`, `data_window`, `generated_by`.
5. The UI renders labelled sections. References link to the records.
6. The message is stored as an `ai_message` with provider, model, latency, and token counts.

**Note drafting.** From the investigation view the user asks for a note draft. The draft appears in
an editable box. Nothing is saved until a user with `exceptions.work` clicks Accept, which creates an
`exception_note` with `source = AI_DRAFT_ACCEPTED`, a `NOTE_ADDED` event, and an audit entry.

**Deterministic mode.** Intent routing maps the question to a supported intent and fills a template
with tool results:

| Intent (example question) | Tools |
|---|---|
| What needs attention today? | `get_dashboard_summary`, `list_exceptions` |
| Explain this exception | `get_exception`, `get_exception_history`, `get_related_orders` |
| Why is SKU X oversold or low? | `get_product`, `get_inventory_position`, `get_inventory_movements` |
| Which orders are overdue? | `get_overdue_orders` |
| What went wrong in the last import? | `get_import_errors` |
| How are we trending? | `get_operational_trends` |

An unrecognised question gets an answer that says it cannot be answered in this mode and lists the
supported questions. It contains no unreferenced facts.

**Alternative workflows.**
- **A1 Tool denied by permission.** The answer states the limitation and contains no data from that
  tool.
- **A2 Result capped.** A limitation line states "showing 50 of N".
- **A3 LLM provider error or timeout.** The answer is produced by the deterministic adapter with
  `generated_by: "deterministic"` and a limitation line (proposed, Q-13).
- **A4 Question outside the store's data.** The copilot declines with a limitation line.
- **A5 Read-only role asks for a draft.** The draft is shown, and Accept is disabled with the reason
  "Requires exceptions.work".

**Business rules.** The AI never writes business data, never runs raw SQL, and never changes a
status (`AGENTS.md §5` rule 7, §11); BR-003 (store scope); BR-152 (estimates labelled); BR-404
(value at risk, never loss); BR-505 (only opaque customer refs); priority score described as a
heuristic (`PRIORITY_MODEL.md`).

**Error conditions.**

| Condition | Response |
|---|---|
| More than 20 requests per minute | 429 `RATE_LIMITED` |
| Missing `copilot.use` | 403 `FORBIDDEN` |
| Empty or over-long question | 422 `VALIDATION_ERROR` (maximum length set in T-073) |
| Tool argument invalid | Tool call recorded as failed; answer states the limitation |
| Accepting a draft without `exceptions.work` | 403 `FORBIDDEN` |

**Acceptance criteria.**
- **AC-011-1** *Given* no LLM key is configured, *when* a user asks "Which orders are overdue?",
  *then* the answer has `generated_by: "deterministic"`, one fact per overdue order with a reference
  to it, and a `data_window`.
- **AC-011-2** *Given* any answer, *then* every fact and metric has at least one reference that
  resolves to a record in the user's store.
- **AC-011-3** *Given* an answer that uses velocity or days of cover, *then* those values appear only
  under estimates, with their basis (for example "28-day moving average").
- **AC-011-4** *Given* an answer about exposure, *then* it uses "value at risk" and never "loss".
- **AC-011-5** *Given* any tool call, *then* an `ai_tool_call` row records tool name, arguments,
  status, row count, and duration, and the result never contains another store's data.
- **AC-011-6** *Given* the tool registry, *then* it contains exactly the allowlisted tools, and none
  accepts SQL text.
- **AC-011-7** *Given* a note draft, *then* no `exception_note` exists until a user accepts it. The
  accepted note has `source = AI_DRAFT_ACCEPTED` and the accepting user as author.
- **AC-011-8** *Given* a user sends 21 requests within a minute, *then* the 21st returns 429.
- **AC-011-9** *Given* an unsupported question in deterministic mode, *then* the answer lists the
  supported questions and contains no facts.

**Permissions.**

| Action | Permission | Roles |
|---|---|---|
| Ask questions, view own conversations | `copilot.use` | all |
| Each tool | the read permission of its data (for example `get_import_errors` → `imports.read`, `get_operational_trends` → `analytics.read`, `list_exceptions` → `exceptions.read`) | per role |
| Accept a note draft | `exceptions.work` | OWNER, MANAGER, STAFF |

**Audit requirements.**

| Action | Record |
|---|---|
| Each question and answer | `ai_conversation`, `ai_message` (provider, model, latency, tokens) |
| Each tool call | `ai_tool_call` (tool, arguments, status, row count, duration, error) |
| Draft accepted | `exception_note` (`AI_DRAFT_ACCEPTED`), `NOTE_ADDED` event, audit `exception.note_add` with the `ai_message` ID |
| Tool denied by permission | `ai_tool_call` with a denied status; audit `copilot.tool_denied` (proposed) |

---

### F-012 Audit log (recording and read API)

**Priority** P0 · **Personas** Owner, Analyst, Ops Manager · **Tasks** T-043 ·
**Workflow** `ROLE_AND_PERMISSION_WORKFLOW.md` · **Modules** audit · **Canonical** `DOMAIN_MODEL.md`
(AuditLog)

**User problem.** With shared logins and chat-based coordination, nobody can reconstruct who
dismissed an alert, applied an import with skipped rows, or changed a threshold (JTBD-O6, JTBD-A5).

**User story.** As a Store Owner, I want every security-relevant and business-changing action
recorded immutably with the actor, target, time, and request ID, so that I can review decisions
after the fact.

**Preconditions.** Recording: always on. Reading: `audit.read`.

**Main workflow.**
1. Each user-initiated business change and each security-relevant event writes one `audit_log` row
   in the same transaction as the change: organization, store (nullable), actor (nullable for
   system), action, target type and ID, metadata, IP, request ID, time.
2. The read API lists entries for the user's organization with filters for action, actor, target
   type and ID, and date range, sorted newest first, paginated.
3. Detailed histories stay in their own tables (`order_event`, `exception_event`,
   `inventory_movement`). The request ID links an audit entry to its log lines.

**Audit catalogue (v1).** `auth.login`, `auth.login_failed`, `auth.logout`, `auth.session_revoked`,
`import.create`, `import.apply`, `import.discard`, `import.retry`, `evaluation.run`,
`exception.acknowledge`, `exception.claim`, `exception.assign`, `exception.unassign`,
`exception.start`, `exception.resolve`, `exception.dismiss`, `exception.reopen`,
`exception.note_add`, `exception.due_date_change`, `settings.update`, `user.create`,
`membership.role_change`, `user.deactivate`, `inventory.drift_detected`, `copilot.tool_denied`,
`auth.demo_login`, `demo.reset`. Only `exception.resolve`, `import.apply`, and `auth.login_failed`
appear in `DOMAIN_MODEL.md`; the rest are proposed for T-043.

**Alternative workflows.**
- **A1 Failed sign-in for an unknown email.** Actor is empty; metadata holds the normalised email.
- **A2 System actions.** Evaluation-driven changes are not copied into the audit log; they are traced
  through `evaluation_run` and `exception_event`.
- **A3 Demo organization.** Visibility of visitor IP addresses to `VIEWER` is open question Q-02.

**Business rules.** Append-only (`DOMAIN_MODEL.md`); BR-003; settings and priority-weight changes are
audited (`BUSINESS_RULES.md §7`, `PRIORITY_MODEL.md`); due-date overrides are audited.

**Error conditions.** 403 without `audit.read`; 422 for invalid filters; entries of another
organization are never returned.

**Acceptance criteria.**
- **AC-012-1** *Given* a user resolves an exception, *then* one `audit_log` row exists with action
  `exception.resolve`, the exception as target, the user as actor, and the request ID from that
  response.
- **AC-012-2** *Given* the audit module, *then* no API endpoint or service method updates or deletes
  audit rows.
- **AC-012-3** *Given* any audit row, *then* its metadata contains no password, session token, CSRF
  token, or API key (a test checks the keys).
- **AC-012-4** *Given* a business change that rolls back, *then* no audit row for it remains.
- **AC-012-5** *Given* a `STAFF` user calls the read API, *then* the response is 403. *Given* an
  `ANALYST`, *then* the response is 200.

**Permissions.**

| Action | Permission | Roles |
|---|---|---|
| Record entries | system | n/a |
| Read and filter entries | `audit.read` | OWNER, MANAGER, ANALYST, VIEWER |

**Audit requirements.** Reading the audit log is not itself audited in v1 (proposed).

---

### F-013 Read-only demo access and demo dataset

**Priority** P0 · **Personas** Demo visitor (access mode) · **Tasks** T-056, T-042 (`VIEWER` role).
Public hosting is F-019 (P1, T-094) · **Workflow** `ROLE_AND_PERMISSION_WORKFLOW.md` ·
**Decisions** ADR-0011

**User problem.** People evaluating the product need to explore a realistic store immediately,
without registering, and without being able to change data that other visitors also see.

**User story.** As a visitor, I want to click "Explore the demo" and land in a realistic store that
contains every exception type, read-only, so that I can judge the product quickly.

**Preconditions.** The demo is enabled in configuration. The fictional organization "Kestrel
Commerce" with store "Kestrel Home & Kitchen" (USD, America/New_York) is seeded with
`is_demo = true` and has a `VIEWER` membership.

**Main workflow.**
1. The visitor clicks "Explore the demo" on the sign-in page.
2. The server starts a `VIEWER` session for the demo organization. The visitor enters no
   credentials. Whether the session belongs to a shared or a per-visitor account is open question
   Q-01.
3. The visitor lands on the overview. A persistent label reads "Demo data: fictional store".
4. The visitor can open every read view and use the copilot. Every mutating control is hidden or
   disabled with the reason "Read-only demo".
5. The seeded dataset (about 120 SKUs, about 1,500 orders over the last 60 days, about 8
   suppliers) is generated relative to the current time and contains every exception type. A reset
   job regenerates it.

**Alternative workflows.**
- **A1 Demo disabled.** The button is not rendered and the endpoint returns 404.
- **A2 Reset during a visit.** Pages show regenerated data on the next request.
- **A3 Rate limits reached.** 429 with a plain-language message.

**Business rules.** BR-001, BR-505 (fictional staff use example domains, customers are opaque refs);
ADR-0011; demo data is always labelled and never presented as live data (`AGENTS.md §11`); product
metrics exclude `is_demo` organizations (SUCCESS_METRICS §1).

**Error conditions.** Any mutation by `VIEWER` → 403 `FORBIDDEN`; copilot over the limit → 429.

**Acceptance criteria.**
- **AC-013-1** *Given* the seed has run, *then* each of the nine exception types has at least one
  exception (T-056).
- **AC-013-2** *Given* a `VIEWER` session, *when* every mutating business endpoint is called, *then*
  each returns 403 and no data changes (the test iterates the route table).
- **AC-013-3** *Given* the active organization has `is_demo = true`, *then* every page shows the
  demo label.
- **AC-013-4** *Given* the generator runs twice with the same seed and reference time, *then* the
  entity and exception counts are identical.
- **AC-013-5** *Given* the generated dataset, *then* every user email uses a reserved example domain
  and no real personal data exists.

**Permissions.** `VIEWER`: the same permissions as `ANALYST`, and no mutation ever succeeds.

**Audit requirements.**

| Action | Audit `action` (proposed) | Metadata |
|---|---|---|
| Demo sign-in | `auth.demo_login` | session ID; IP handling per Q-02 |
| Dataset reset | `demo.reset` | seed, reference time, resulting counts |

---

## 4. P1 feature specifications

### F-014 Scheduled evaluation worker

- **Problem.** Stalled, overdue, and refund-pending conditions depend on the clock. Without
  scheduled runs they only appear when someone imports or runs analysis (risk R-02).
- **Story.** As an Operations Manager, I want evaluations to run automatically every few minutes,
  so that time-based exceptions appear without anyone clicking a button.
- **Acceptance criteria.**
  - *Given* the worker (`python -m app.workers.scheduler`) is running, *then* each store gets a run
    with `trigger = SCHEDULED` every `evaluation_interval_minutes` (default 15).
  - *Given* a run for a store holds its advisory lock, *then* no second run for that store starts.
  - *Given* a run fails for one store, *then* runs for other stores continue and the failure is
    recorded on its run.
  - *Given* the interval setting changes, *then* the next cycle uses the new value.
- **Permissions.** System process. Changing the interval needs `settings.manage` (F-015).

### F-015 Store settings: thresholds and priority weights

- **Problem.** Default thresholds may not match a store's promises (JTBD-M9). Wrong defaults cause
  noise or silence (R-03).
- **Story.** As an Operations Manager, I want to adjust the SLA, stall, refund, reopen-window,
  velocity, and priority settings for my store, so that detection matches how we operate.
- **Acceptance criteria.**
  - *Given* the settings page, *then* every key in `BUSINESS_RULES.md §7` is shown with its current
    value and default.
  - *Given* priority weights that are not non-negative integers or exceed 100 at the maximum, *then*
    saving returns 422 (`PRIORITY_MODEL.md`, Configuration).
  - *Given* a saved change, *then* a `settings.update` audit entry records the old and new values,
    and the change takes effect at the next evaluation.
- **Permissions.** View: `settings.read` (all roles). Change: `settings.manage` (OWNER, MANAGER).

### F-016 User and membership management

- **Problem.** Owners need to give people the right level of access and remove it when they leave
  (JTBD-O5).
- **Story.** As an Owner, I want to add users with a role, change roles, and deactivate users, so
  that access matches responsibilities.
- **Acceptance criteria.**
  - *Given* an Owner adds a user with role `STAFF`, *then* the membership exists and `user.create` is
    audited. How the new user sets a password, with no email delivery in v1, is decided in T-066.
  - *Given* a user is deactivated, *then* all their sessions are revoked and their next request
    returns 401.
  - *Given* an action would leave the organization without an active Owner, *then* it is refused with
    422 (proposed).
  - *Given* a `MANAGER`, *then* the user list is visible and every change returns 403.
- **Permissions.** View: `users.read` (OWNER, MANAGER). Change: `users.manage` (OWNER).

### F-017 Audit log viewer

- **Problem.** The audit API (F-012) needs a usable screen for reviews.
- **Story.** As an Owner or Analyst, I want to filter the audit log by person, action, target, and
  date, so that I can reconstruct what happened.
- **Acceptance criteria.**
  - *Given* filters, *then* results match the API and are paginated, newest first.
  - *Given* an entry, *then* a detail drawer shows its metadata and links to the target.
  - *Given* a user without `audit.read`, *then* the navigation item is hidden and the route shows the
    permission-denied state.
- **Permissions.** `audit.read` (OWNER, MANAGER, ANALYST, VIEWER).

### F-018 Exception performance analytics

- **Problem.** Analysts and managers need to see whether exceptions are handled well and which rules
  are noisy (JTBD-A1, JTBD-A3).
- **Story.** As an Analyst, I want time to acknowledge, time to resolve, verification pass rate,
  reopen rate, and dismissal rate per rule and severity, so that I can recommend changes with
  evidence.
- **Acceptance criteria.**
  - *Given* a period, *then* the page shows M-06, M-07, M-10, M-12, M-13, M-15, and M-16 as defined in
    SUCCESS_METRICS, as medians and p90 where applicable.
  - *Given* any figure, *then* it reconciles with the underlying tables in tests.
  - *Given* a demo organization, *then* the page carries the demo label, and the figures are never
    presented as product results.
- **Permissions.** `analytics.read` (all roles).

### F-019 Hosted public demo with scheduled reset

- **Problem.** The demo (F-013) is useful to evaluators only when it is reachable online.
- **Story.** As a visitor, I want to open a public URL and explore the demo, so that I do not need to
  run anything locally.
- **Acceptance criteria.**
  - *Given* the deployed demo, *then* anonymous visitors cannot change shared data (end-to-end test
    against the deployment, T-094).
  - *Given* the reset schedule, *then* the dataset is regenerated and the demo label stays visible.
  - *Given* no LLM cost approval from the owner, *then* the public demo uses the deterministic provider
    (D-13).
  - No URL is published until the deployment exists and passes its health check.
- **Permissions.** `VIEWER` only.

### F-020 Copilot evaluation harness

- **Problem.** Copilot quality cannot be claimed without measurement (M-27).
- **Story.** As the product owner, I want a fixed set of questions with expected tools and facts,
  run against each provider, so that copilot quality is measured rather than asserted.
- **Acceptance criteria.**
  - *Given* `make ai-eval`, *then* results report tool selection, factual correctness, attribution,
    unsupported-answer rate, permission enforcement, and latency.
  - *Given* a run, *then* results are stored with the date and provider, and never edited by hand.
- **Permissions.** Developer tooling. Not exposed in the product.

### F-021 Data quality overview

- **Problem.** Import issues and data-quality exceptions are spread across individual imports, which
  hides recurring export problems (JTBD-A2). `EXCEPTION_CATALOG.md` already routes invalid CSV rows to
  an "Import errors / Data quality" page.
- **Story.** As an Analyst, I want issue codes over time by import type, together with
  `DATA_ORDER_TOTAL_MISMATCH` and `DATA_NEGATIVE_ON_HAND` exceptions, so that I can fix export
  mappings at the source.
- **Acceptance criteria.**
  - *Given* a period, *then* the page shows M-21 to M-24 and the top issue codes per import type.
  - *Given* an issue code, *then* the user can open the imports and rows that produced it.
- **Permissions.** `imports.read` and `analytics.read` (all roles).

---

## 5. P2 features

| ID | Feature | Rationale |
|---|---|---|
| F-022 | Per-visitor demo sandbox (ephemeral organization cloned from the seed, rate-limited, auto-expiring) | Lets visitors run the full lifecycle without affecting others (T-095). Needs provisioning and cleanup infrastructure that v1 does not have |
| F-023 | Notification digests (for example a daily email of new P1 exceptions and past-due items) | Owners may not open the product daily. Needs a delivery channel and a new background job (NG-18) |
| F-024 | Business-hour SLA calendars and carrier cut-off times | Calendar hours over-flag weekend orders (BR-204). Wait for D-01 and D-02 validation before adding complexity |
| F-025 | Storefront and marketplace read connectors (pull orders, products, stock) | Removes the CSV mapping burden (R-06). Deferred until the CSV contracts prove the domain model (NG-08) |
| F-026 | Saved inbox views and CSV export of lists | Repeated filters and offline analysis for analysts. Export must reuse the formula-injection protection |
| F-027 | Bulk exception actions (acknowledge, assign) | Speeds triage after a large import. Needs per-item permission checks and partial-failure reporting |
| F-028 | `PRODUCT_PRICE_ANOMALY` rule | Catches pricing errors. Needs price history, which v1 does not keep (`EXCEPTION_CATALOG.md`, roadmap) |
| F-029 | In-app stock adjustment form (single cycle count or damage entry) | Lets staff record a count without a CSV. Depends on D-09 (should staff create adjustments at all?) |
| F-038 | Follow-up date for exceptions waiting on an external party | Makes "waiting on supplier" explicit instead of a note, and reduces reopen loops (R-08) |

## 6. P3 features

| ID | Feature | Rationale |
|---|---|---|
| F-030 | Custom roles | The fixed matrix is reviewed as code (ADR-0007). Custom roles are listed as P3 in `DOMAIN_MODEL.md` |
| F-031 | Multi-location inventory | Changes the oversell calculation and needs routing rules (ADR-0005, NG-04) |
| F-032 | Purchase orders and supplier performance, with `SUPPLIER_LATE_RECEIPT` | Needs a `PurchaseOrder` entity, excluded in v1 (NG-09) |
| F-033 | Carrier tracking events, with `ORDER_DELIVERY_DELAYED` | Needs carrier integrations (NG-03) |
| F-034 | Returns with reasons, with `RETURN_RATE_SPIKE` | Needs return reason data (NG-20) |
| F-035 | Payment entity: partial captures, split tenders, processor reconciliation | `Payment` is excluded until a workflow needs a 1:N relation (NG-02, NG-12) |
| F-036 | Split shipments and per-line fulfillment | `Shipment` is excluded; one shipment per order assumed (NG-11) |
| F-037 | Per-store role scoping | In v1 a membership grants every store in the organization (BR-002) |

---

## 7. Cross-cutting requirements (all features)

| ID | Requirement | Source |
|---|---|---|
| CC-01 | Every data view implements loading, empty, error, and permission-denied states | `AGENTS.md §4` |
| CC-02 | No fake controls. Actions the user cannot perform are hidden or disabled with a reason, and the backend enforces the permission regardless | `AGENTS.md §4, §6` |
| CC-03 | Times are stored in UTC and shown in the store time zone with its abbreviation | BR-501 |
| CC-04 | Money uses `Decimal` and the store currency | BR-503 |
| CC-05 | Errors use the standard envelope with `request_id`, and never expose stack traces or SQL | API conventions, `AGENTS.md §6` |
| CC-06 | Lists use server-side pagination (`page_size` ≤ 100), `sort=field` / `sort=-field`, and filters as query parameters | API conventions |
| CC-07 | Rate limits: login 5/min per IP and email; general 300/min per user; copilot 20/min per user. Per-instance limitation documented | Brief, R-12 |
| CC-08 | Keyboard operable, sufficient contrast, usable at 375 px width | T-083 |
| CC-09 | Demo data is always labelled as demo data | ADR-0011, `AGENTS.md §11` |
| CC-10 | Store-scoped resources return 404 for other tenants and are covered by cross-tenant tests | BR-003, `AGENTS.md §6` |

## 8. Traceability: P0 features to workflow documents

Verification for T-002: every P0 feature maps to at least one workflow document (written in T-010).

| Feature | Workflow documents (`docs/workflows/`, T-010) | Tasks | Jobs |
|---|---|---|---|
| F-001 | `ROLE_AND_PERMISSION_WORKFLOW.md` | T-042, T-060 | O5 |
| F-002 | `IMPORT_PIPELINE.md` | T-052, T-065 | M1, M8, A2 |
| F-003 | `INVENTORY_LIFECYCLE.md` | T-051, T-064 | M5 |
| F-004 | `INVENTORY_LIFECYCLE.md`, `IMPORT_PIPELINE.md` | T-051, T-064 | S6 |
| F-005 | `ORDER_LIFECYCLE.md` | T-050, T-063 | S3 |
| F-006 | `EXCEPTION_MANAGEMENT.md` | T-053 | M1, M6 |
| F-007 | `EXCEPTION_MANAGEMENT.md` | T-054, T-062 | M1, S1 |
| F-008 | `EXCEPTION_MANAGEMENT.md` | T-054, T-062 | M6, M7, M10, S4, S5 |
| F-009 | `EXCEPTION_MANAGEMENT.md`, `AI_ASSISTED_INVESTIGATION.md` | T-062 | S2, A4, M2 |
| F-010 | `EXCEPTION_MANAGEMENT.md` | T-057, T-061 | O1 |
| F-011 | `AI_ASSISTED_INVESTIGATION.md` | T-071, T-072, T-073 | S7, O4 |
| F-012 | `ROLE_AND_PERMISSION_WORKFLOW.md` | T-043 | O6, A5 |
| F-013 | `ROLE_AND_PERMISSION_WORKFLOW.md` | T-056, T-042 | V1 |

**Note on priorities versus `TASKS.md`.** The read-only demo is P0 here because the `VIEWER` role
(T-042) and the seeded dataset (T-056) are P0 tasks. Hosting it publicly depends on deployment
(T-093, T-094), which is P1, so the hosted demo is F-019 (P1). The scheduled worker (F-014) follows
T-055 as P1. Promoting it to P0 is proposed in open question Q-12.
