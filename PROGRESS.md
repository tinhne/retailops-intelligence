# PROGRESS

Append-only implementation log. Newest entries at the bottom. Never rewrite earlier entries;
add a correction entry instead.

---

## 2026-10-31 21:45 (UTC+7): Orchestrator: environment assessment and repository bootstrap

- **Task:** Directive §23 steps 1–3 and 5–6.
- **Findings:** Working folder contained only an unrelated saved web page (left untouched). The repo
  was created in the subfolder `retailops-intelligence/`. Docker 29.1.3 / Compose v5, Node 24.14,
  pnpm 10.33, git 2.50 are available. The system Python is 3.9, so Python 3.12 was installed via `uv` (Homebrew).
  GitHub SSH auth as `tinhne` works. `tinhne/retailops-intelligence` does not exist (API 404, SSH
  "repository not found"). The `gh` CLI is not installed, so the remote can't be created without
  the owner (T-092 BLOCKED).
- **Files created:** `.gitignore`, `LICENSE` (MIT, Lê Văn Trung Tính), `AGENTS.md`, `TASKS.md`,
  `ENVIRONMENT_STATUS.md`, `RELEASE_NOTES.md`, `PROGRESS.md`.
- **Tests:** n/a.

## 2026-10-31 22:00 (UTC+7): Orchestrator: canonical domain contracts (T-020)

- **Files created:** `docs/domain/STATE_MACHINES.md`, `BUSINESS_RULES.md`, `EXCEPTION_CATALOG.md`,
  `PRIORITY_MODEL.md`, `DOMAIN_MODEL.md`.
- **Key decisions:** three order status axes with a compatibility matrix; import sync by
  reachability; reservations on payment; `available = on_hand − reserved`; cycle-count cutoff for
  shipment movements; 9 exception rules with per-product inventory precedence; dedup /
  auto-resolve / verification / reopen / supersede reconciliation table; transparent 0–100
  priority score with P1–P4 bands; excluded entities and their rationale (Payment, Shipment, Variant, Location).
- **Tests:** n/a (documentation). Rule IDs (BR-xxx) will be referenced by tests.

## 2026-10-31 22:30 (UTC+7): Orchestrator (Backend role): backend foundation (T-040, T-041, T-042 partial, T-043 partial)

- **Files created:** `apps/api/**` (FastAPI app factory, settings, JSON logging, request-ID middleware,
  error envelope, pagination, rate limiter, SQLAlchemy base/session, identity models, argon2
  hashing, opaque sessions, session-bound CSRF, role/permission matrix, `require_permission`,
  store-scoped access with 404 for other tenants, auth router (login/demo/logout/me), audit log
  model, service, and router, health live/ready), Alembic migration `0001` (identity + audit),
  `docker-compose.yml` (postgres:16 with a test DB init script), `Makefile`, `.env.example`.
- **Tests executed:** `make check` → ruff clean, `mypy --strict` clean (32 files), **pytest 28 passed**
  (unit: permissions matrix, password/CSRF/token primitives, rate limiter, error envelope, request
  ID, production settings guard; integration against PostgreSQL 16: login and cookies, generic
  invalid-credential errors plus audit, login rate limit (429 on the 6th attempt), CSRF rejection, logout
  revocation, idle expiry, 403 with the missing permission, cross-tenant 404, audit isolation, demo
  viewer login, demo misconfiguration guard, readiness). `alembic check` reports no drift.
- **Remaining:** user management endpoints (T-066/P1), store settings API, OpenAPI contract generation.

## 2026-11-01 (UTC+7): Orchestrator: documentation milestones M0–M3 (T-001, T-002, T-010, T-021..T-023, T-030, T-070, T-080)

- **Agents:** PM (product discovery), BA (workflows), Architect (architecture, ER, ADR-0001..0013),
  Design (IA, flows, design system, screens, components), AI/QA (AI docs, test strategy).
- **Orchestrator review:** resolved about 30 cross-document inconsistencies in the canonical docs:
  BR-113 cycle count as of occurred_at, BR-402a negative on-hand precedence, BR-609 line lock, the
  verification grace rule, run statuses, due-date override and reopen, deadline boundaries,
  refund clocks, DST ambiguity, BR-150 refunded-before-shipping exclusion, and reserved shipment
  references. Owner decision applied: the AI copilot uses free-tier LLM providers only.
- **Tags:** `discovery-complete`, `workflow-v1`, `architecture-v1` (verified docs; schema implemented).

## 2026-11-01 (UTC+7): Orchestrator: demo dataset, infrastructure, GitHub (T-056 partial, T-090 partial, T-091, T-092)

- Demo generator `app/demo` (`make seed`): 114 products, ~1,540 orders, ~2,600 ledger movements,
  zero reconciliation drift. Every exception scenario is engineered. 2 integration tests.
- API multi-stage non-root Dockerfile (builds). GitHub Actions CI (API, web, audits, Docker).
  Next.js 16 web scaffold. OpenAPI → TypeScript contracts generator.
- GitHub repo created by the owner. `main` and the tags pushed over SSH. **The first CI run passed** (run
  41216596429 on 4f38073).

## 2026-11-01 (UTC+7): Backend agents, integrated by the orchestrator (T-050, T-051, T-052, T-053, T-054, T-057)

- **Imports (T-052):** 4 CSV types, preview, strict and valid-rows-only atomic apply, re-validation
  guard, idempotency, issue CSV export, templates and sample data. 150 tests. Verified alone on clean main (241 passed).
- **Read APIs and analytics (T-050/T-051 read side, T-057, settings):** 18 endpoints. 116 tests.
  The orchestrator fixed BR-150 velocity via the shared `orders.sql.counts_as_sale` and updated 3 tests.
  Verified alone on clean main (357 passed).
- **Exception engine and lifecycle (T-053, T-054):** 9 rules, reconciliation per STATE_MACHINES §3.3,
  priority and due dates, lifecycle API with concurrency, evaluations API. 267 tests. The orchestrator added:
  negative on-hand supersedes inventory exceptions, with 1 test.
- **Integrated result:** `make check` → ruff OK, mypy --strict OK, **625 passed**. `make seed` plus
  engine run → 18 exceptions covering all 9 types. Contracts regenerated: 43 paths, 47 operations, 126 schemas.

## 2026-11-01 (UTC+7): Orchestrator: scheduled worker (T-055); session paused on usage limit

- `app/workers/scheduler.py`: evaluates each store once per `evaluation_interval_minutes` (any
  trigger resets the clock) under the engine's advisory lock. Supports `--once` and graceful
  SIGTERM. 2 integration tests pass. ruff and mypy are clean.
- The frontend and AI copilot agents were stopped mid-task on a usage limit. Their work is uncommitted
  and unverified in the working tree (see HANDOFF.md §3).

## 2026-11-01 (UTC+7): Orchestrator: session resume and web foundation (T-060)

- **Resume check:** `git status` was clean on `main` at 932df62. The "uncommitted partial work"
  in `apps/web` and `apps/api/app/domains/ai` that HANDOFF.md described was **not present**: the web
  app was still the unmodified scaffold and the AI domain held only `models.py`. Docs corrected.
  Baseline `make check`: ruff, format and mypy OK, pytest **627 passed** (625 plus 2 worker tests).
- **Contracts (747441b):** `MembershipOut`, `RolePermissionsOut` and `MemberOut` type `role` and
  `permissions` with the `Role` and `Permission` enums, so `packages/contracts` exports the exact
  unions. The JSON is unchanged. Contracts regenerated.
- **Web foundation (T-060):** design tokens (`styles/tokens.css`, light plus ready dark values),
  Tailwind v4 theme mapping, Inter, shadcn/ui primitives restyled to the tokens (button with
  pending state and `aria-disabled`, input, label, card, alert tones, skeleton, tooltip, dropdown,
  sheet, avatar, toaster). API client with the CSRF double-submit header and `ApiError` from the
  error envelope. QueryClient defaults (2 retries for network and 5xx only, 1 s/3 s; any 401 clears
  the cache and goes to sign-in, with `reason=expired` for `SESSION_EXPIRED`). `/api/*` rewrite to
  FastAPI, `proxy.ts` optimistic redirect, `/s/{id}` redirect. S-01 sign-in and `/demo` entry.
  Session gate, store resolution (unknown store = not found), app shell (skip link, demo banner,
  sidebar with persisted collapse, icon rail at 768–1023 px, mobile drawer, top bar, account menu
  with sign-out, offline notice), permission gates and state components. The sidebar shows only
  built pages, so it currently lists Overview, whose dashboard content is T-061.
- **Copy honesty:** the spec's "periodically reset" was left out of the demo banner and `/demo`
  page because the reset job does not exist yet (T-094).
- **Dev validation:** Cache Components' instant-navigation check cannot render pages behind the
  client-side session gate, so `experimental.instantInsights.validationLevel` is `manual-warning`
  (segments opt in with `export const instant`).
- **Docs synced:** ARCHITECTURE_MAP paths and statuses now match the code (several backend paths
  had moved, e.g. `identity/security.py`, `api/deps.py`, `exceptions/engine.py`, `demo/seed.py`).
  ENVIRONMENT_STATUS: added `TRUST_PROXY_HEADERS` and `DEMO_STAFF_PASSWORD`, removed the
  unimplemented `CORS_ALLOWED_ORIGINS`, and the web uses the documented `API_INTERNAL_URL`.
- **Tests:** web lint, typecheck and `next build` green. vitest **57 passed** (API client, retry and
  401 policy, safe `next` redirects, nav and permission gating, class merging, login screen states,
  ErrorState). `pnpm audit --prod --audit-level high`: no known vulnerabilities. Browser check
  against the seeded API: password and demo sign-in, `next` redirect, invalid credentials, session
  expiry, sign-out, unknown store, and the 375, 768 and 1280 px layouts.

## 2026-11-01 (UTC+7): Orchestrator: Overview dashboard (T-061)

- **API (5a108e5):** `ActiveExceptionSummary.exposure_by_category`, the sum of `exposure_amount` of
  active exceptions per category (gross value at risk, BR-404). Per category only, never totalled.
  Integration test updated (closed exceptions with exposure are excluded). Contracts regenerated.
- **Web:** S-02 Overview. Formatters (`lib/format`: money from decimal strings with U+2212, store-zone
  date and time with per-instant EDT/EST, deadlines, durations), `status-maps.ts` (labels, tones and
  icons for severity, status including the four RESOLVED forms, health, import status), status atoms
  (StatusPill, SeverityBadge, ExceptionStatusPill, PriorityIndicator, ImportStatusPill), Money,
  DateTime and DueLabel on one shared minute ticker, KpiCard, ChartFrame with a Chart/Table toggle,
  EmptyState, ActionButton (disabled with a focusable reason) and RunAnalysisButton (Idempotency-Key
  reused on retry; SUCCEEDED, SKIPPED, FAILED and RUNNING outcomes).
- **Overview regions:** freshness strip, six KPIs, Needs attention (top 8), active exceptions and value
  at risk per category, stock health, shipments per day (stacked, store-local days, partial day
  marked), recent imports. States: loading skeletons, no data (with CSV template links), nothing needs
  attention, dashboard error with retry, independent chart and imports errors, permission denied.
- **Links:** KPI cards and rows link only to built pages the role may open (`sectionHref`), so they are
  plain text until T-062..T-065 land.
- **Found:** the demo store has no CSV imports (the seed writes rows directly), so "no data" is
  detected from products, active exceptions and imports together. Products with negative on-hand
  count as Oversold in stock health; BR-402a wants a separate data-issue row. Recorded as T-058.
- **Spec synced:** S-02 data table now matches the API (`days=30` trends, `assignee=unassigned`,
  `exposure_by_category`).
- **Tests:** web lint, typecheck and build green; vitest **90 passed**. Mutation checks: breaking the
  key reuse or the data-quality "—" rule fails the suite. Browser check against the seeded API as the
  demo viewer (Run analysis read-only) and as a manager (Run analysis completes, freshness updates),
  at 1440 and 375 px.

## 2026-11-01 (UTC+7): Orchestrator: exceptions inbox and investigation (T-062)

- **API (2d58630):** `due_to` filter on the exception list (due at or before an instant, time zone
  required). Backs the inbox Due filter and the Overview's past-due link. 1 integration test.
- **API (574cec1):** list items (and so the detail) carry `resolution_code`, `verified_at`,
  `dismissed_reason` and `closed_at`, so the Closed view shows the four RESOLVED forms without
  calling an unverified manual resolution a success, and when each exception closed. Dismissal time
  comes from the latest DISMISSED event, batch-loaded per page. 1 integration test.
- **Web, inbox (S-03):** views as link tabs with counts, URL state validated and normalised (unknown
  values dropped with a toast), search with debounce and `/`, multi-select filters with chips, assignee
  and due selects, sort, server pagination, stacked rows below 768 px, per-view empty states,
  60 s refresh, and the list URL remembered for the detail breadcrumb.
- **Web, investigation (S-04):** header with status row, assignee control (assign, reassign, claim,
  unassign) and due-date override in the store zone; lifecycle banner per resolution form and reopen
  reason; recommended action; priority breakdown with the PRIORITY_MODEL limitations; calculation;
  evidence; affected orders; activity timeline (events and notes merged, newest first) with notes;
  details with technical identifiers.
- **Actions:** laid out from the API's `available_actions` and `blocked_actions` per the S-04 status
  table, with IA §5 reasons (demo: read-only). Resolve, Dismiss and Reopen dialogs validate like the
  API (closing notes need 10 non-whitespace characters). Every command sends `expected_version`;
  `STALE_VERSION` keeps the dialog and its input, warns, and refetches. Changes made by others are
  announced on refetch.
- **Nav:** Exceptions is live, so the Overview's KPI cards, category rows and attention rows link to it.
- **Spec synced:** SCREEN_SPECIFICATIONS §0.4 exception endpoints now match the API.
- **Deferred to T-067:** sticky mobile action bar and filter sheet, queue Previous/Next, jump menu,
  density toggle, VIEWER lifecycle explainer, evidence source links. AI panel and AI note drafts stay
  with T-073.
- **Tests:** web lint, typecheck and build green; vitest **120 passed**. Browser check against the seeded
  API: acknowledge, start, resolve (with validation), the Closed view, and reopen as a manager; the
  read-only demo viewer; 1440 and 375 px.

## 2026-11-01 (UTC+7): Orchestrator: orders list and detail (T-063)

- **API (1f7e1d5):** an order's linked exceptions carry `title`, `resolution_code` and `verified_at`, so
  the order page names them and shows the RESOLVED forms honestly. Order detail test extended.
- **Web, list (S-05):** read-only list with search (order number or customer reference), status
  (grouped), payment, fulfillment, channel, placed presets in store-local days (Today, 7, 30, 60 days),
  overdue-only toggle, sort, pagination, stacked rows below 768 px, and the success-toned empty
  overdue result. URL state validated like the inbox.
- **Web, detail (S-06):** status card with the cancelled-but-paid and refunded-without-return
  callouts, key dates (ship-by source with the store SLA hours), line items with reservation and
  stock health (negative on-hand shown as a data issue, BR-402a), totals with the BR-205 mismatch
  rows, linked exceptions (active first, last 5 closed), status history with skipped statuses.
- **Fix found in the browser:** at 375 px the page could scroll sideways. Screen-reader-only labels
  inside table cells escaped their scroll container because it was not positioned, and the page grids
  had no shrinkable column. Both fixed for every table and page grid.
- **Spec synced:** S-05 search matches IA §8 and the API (customer references searchable in the Orders
  list only). Orders and its links (Overview KPIs) are live in the nav.
- **Deferred to T-067:** custom placed range, import file links in order history, Ask the copilot.
- **Tests:** web lint, typecheck and build green; vitest **134 passed**.

## 2026-11-01 (UTC+7): Orchestrator: commit attribution and history rewrite (owner-approved)

- **Decision (owner):** commits, tags and pull requests credit the owner only, with no tool co-author
  lines. 39 of the 43 commits on GitHub carried a co-author trailer.
- **Action:** a one-time history rewrite removed those trailer lines from every commit message on all
  branches and tags, then `main` and the tags `discovery-complete`, `workflow-v1` and `architecture-v1`
  were force-pushed with leases on the old remote IDs. This is an explicit, owner-approved exception to
  AGENTS.md §8 ("never rewrite published history"); the rule otherwise stands.
- **Verification:** all 43 commits map one-to-one; every rewritten commit has the same tree, author and
  dates as its original; no message or tag mentions the tool; the old state is kept in a git bundle
  outside the repository.
- **Hash map for commits cited earlier in this log** (old → new): 4f38073 → 78a31bf, 932df62 → 6458a58,
  747441b → 0fba20f, 5a108e5 → e942e71, 2d58630 → 82bdb4f, 574cec1 → 8b6f967, 1f7e1d5 → 43239c7,
  5e24711 → f97a8af, 6d534b2 → c5b7e57. CI run IDs recorded earlier still exist on GitHub and refer to
  the old IDs of the same code.

## 2026-11-01 (UTC+7): Orchestrator: products, inventory positions and movements (T-064)

- **Web, shared:** `lib/list-params.ts` describes a list screen's URL state as field specs (text, one,
  many, flag, id) and derives parse, validation, serialisation, "is filtered" and clear-all from them;
  `useListState` binds a definition to the router and drops unknown values from shared links. The
  three new lists use it instead of hand-written param modules. `DataTable` gained a pinned first
  column, a 2xl breakpoint and tighter cell padding in compact density. `EstimateValue` renders
  BR-152 estimates with their basis. `formatDelta` and `storeMidnight` moved into `lib/format`.
- **Products (S-07):** read-only catalog with search, status, category, supplier and stock filters,
  cost-above-price warning, stock columns only with `inventory.read`, stacked rows below 768 px.
- **Product detail (S-08):** stock tiles, the BR-101 formula line, a health explanation from the API's
  `approaching_threshold`, the BR-402a data-issue callout linking its exception (Available and Days
  of cover marked not reliable), product details, exceptions (active and last 5 closed) and the last
  10 ledger rows with a link to the filtered ledger.
- **Inventory positions (S-09):** health summary toggles (`aria-pressed`, counts from the dashboard),
  the BR-101/BR-103 caption, search, health, category, include-inactive, sort, 50/100 page sizes,
  "No oversold products" success state, negative on-hand rows shown as Data issue.
- **Movements (S-10):** ledger with the Occurred column pinned while scrolling sideways, signed deltas,
  running on-hand, type, source, reference (shipments link to the order search), note, recorded by
  (members, "Former member", or System). Filters: product (from S-08 links), type, source, occurred
  presets in store-local days; sorts by occurred or recorded time.
- **Found in the browser:** at 1440 px the positions table overflowed and squeezed product names to
  92 px; fixed with compact padding, two-line names and Avg daily units from 1536 px. Health toggle
  names read "Oversold3" to screen readers; fixed. Days of cover showed "0.0 days" for a data-issue
  product; now "—" with "not reliable".
- **Spec synced:** S-08 days of cover for data issues; S-09 Avg daily units breakpoint; S-10 filter
  names (`from`/`to`, `source`), On hand after and Recorded columns, shipment references, deferred
  Import column and filter. Products, Inventory and Movements are live in the nav, so Overview's
  health rows now link to filtered positions.
- **Deferred to T-067:** ledger product combobox and custom range, Import filter and column, exact
  order-line links, import actions in the empty states (with T-065).
- **Tests:** web lint, typecheck and build green; vitest **151 passed**. Backend unchanged.

## 2026-11-01 (UTC+7): Orchestrator: CSV imports UI (T-065)

- **Imports list (S-11):** history with type and status filters, live refresh while a row is
  validating or applying, uploader names, stacked rows below 768 px, the template menu in the
  recommended order and New import (disabled with the reason for roles without `imports.run`).
- **New import (S-12 step 1):** type cards with template links and dependency hints, the column
  reference from IMPORT_PIPELINE §5, a CSV drop zone with the client checks (type, `.csv`, 5 MB),
  upload-and-validate, then the import's own page.
- **Preview and apply (S-12 steps 2–4):** stepper, count tiles, warning callouts (duplicate file,
  unknown columns, assumed time zones, already-applied references), expected changes, the issue
  table (severity tabs, code filter, fix text, issues CSV), discard with confirmation, and the apply
  step: strict by default and blocked while rows have errors, valid-rows-only with consent to the
  exact skipped count, an Idempotency-Key per attempt, and copy for each apply error code.
- **Record (S-13):** outcome banners for completed, partly completed, rejected (code, message and
  fix), failed and discarded (expired or manual) imports, applied counts, the analysis the import
  triggered, details with the SHA-256, and Import another file in the recommended order.
- **Elsewhere:** Imports is live in the nav. Empty states on Overview, Orders, Products, Inventory
  and Movements offer the matching import to people who can run one, and Overview's recent imports
  link to their records. `Section` and `StatTile` moved to `components/data/section.tsx`.
- **Fixes found while building:** list pagination offered 25 rows on Inventory and Movements, whose
  URL state accepts only 50 and 100, so choosing it reset the page with an "unrecognised filters"
  toast; `Pagination` now takes the list's page sizes. Page header actions no longer wrap under a
  long subtitle.
- **Found in the browser:** the expected-changes title claimed "first 1 rows" for a 3-row file
  because the API lists only rows that change or fail; the title and a note now say so. Issue codes
  broke mid-word; file names in the list broke mid-word; ten list columns overflowed at 1440 px
  (Mode and Rows with warnings now from 1536 px).
- **Verified as manager** against the local API with a test file copied from two existing products
  plus one invalid row: preview, strict block, valid-rows-only apply (2 unchanged, 1 skipped, so no
  data changed), the duplicate-file warning on a second upload, discard, and a rejected file. As the
  demo viewer: New import disabled with the demo reason. 1440 and 375 px, no console errors.
- **Spec synced:** S-11 single status filter and column breakpoints; S-12 expected-changes scope,
  indeterminate upload progress, single code filter, "View exceptions to triage"; S-13 discard copy
  without a name. Deferred items are in T-067.
- **Tests:** web lint, typecheck and build green; vitest **165 passed**. Backend unchanged.

## 2026-11-01 (UTC+7): Orchestrator: parallel completion of the remaining product work

- **How:** five isolated branches built in parallel, each with its own test database
  (`retailops_test_{ai,stock,admin,ui,ops}`), then merged into `main` one by one:
  `fix/stock-health-data-issue` (T-058), `feat/admin-ui` (T-066), `feat/ops-security` (T-056, T-082,
  T-090, T-094 reset job), `feat/ui-followups` (T-067), `feat/ai-copilot` (T-071..T-074). The
  copilot web UI (T-073) was built on `main` after the AI merge.
- **Merge fixes:** an import conflict in `test_demo_seed.py`; a doc conflict in
  SECURITY_ARCHITECTURE (column cap plus failed-apply byte retention); member tests and the demo
  read-only walk updated for sign-in CSRF and the organization routes; stale docs naming
  `FORWARDED_ALLOW_IPS` / `SECRET_KEY` aligned; `TOO_MANY_COLUMNS` added to the import catalogue.
- **Copilot UI:** S-14 page (conversations, suggested questions, prefill via `?q=` and exception
  context, pending, error, rate limit), `CopilotAnswer` with reference chips, formulas,
  limitations and tool disclosure; AI investigation panel on S-04; "Draft with copilot" saving as
  `AI_DRAFT_ACCEPTED` only on Save note; "Ask the copilot" on order detail.
- **Found in the browser:** copilot reference chips used full exception titles and widened the
  exception page to 1,917 px at 1440; chips now show the code, truncate, and carry the full label as
  a title (3c5bf45).
- **Manual pass (local, seeded data):** demo sign-in via pre-session CSRF; Overview with the
  data-issue row and seeded imports; exception page with AI investigation; copilot questions
  (general and exception context); Inventory data-issue filter; Movements import column and order
  links; Orders and "Ask the copilot"; Imports; Settings read-only; Audit log; owner Users & roles
  with self-action guards. Not yet repeated after the merges: manager lifecycle actions, note
  draft save, import upload and apply.
- **Tests:** backend `make check` 865 passed on the merged tree; web lint, typecheck, build green,
  vitest 265 passed (3c5bf45).
