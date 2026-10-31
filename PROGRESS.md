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
