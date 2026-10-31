# HANDOFF

Concise continuation guide for the next engineer or agent. Read `AGENTS.md` first.

## 1. What this project is
RetailOps Intelligence detects, prioritises, and tracks the resolution of e-commerce operational
exceptions (oversold SKUs, overdue fulfillment, pending refunds, data inconsistencies) from imported
CSV data. A free-tier LLM copilot explains the evidence and suggests next steps. Business logic is
deterministic, and AI is advisory only.

## 2. Completed
Docs M0–M3 (tagged). Backend: auth, sessions, CSRF, permissions, tenancy, audit; schema
(migrations 0001–0002); order FSM; inventory ledger and reservations; CSV import pipeline; exception
engine and lifecycle API; read APIs and analytics; demo dataset generator; scheduled evaluation
worker (T-055). `make check` gives 627 tests green. The GitHub repo exists and its first CI run passed.
**Web foundation (T-060, 2026-11-01):** tokens and theme, restyled shadcn/ui primitives, API
client (CSRF header, `ApiError`), QueryClient policy (retries, 401 → sign-in), `/api` rewrite,
`proxy.ts` sign-in redirect, S-01 sign-in and `/demo`, session gate, store resolution and the app
shell. **Overview (T-061):** the S-02 dashboard with formatters, status maps and atoms, KPI cards,
chart frame and Run analysis; the dashboard API gained `exposure_by_category`. **Exceptions (T-062):**
inbox and investigation with every lifecycle action; the list API gained `due_to` and closing fields.
**Orders (T-063):** read-only list and detail. **Products and inventory (T-064):** products list
and detail, inventory positions, movements ledger. **Imports (T-065):** history, upload, preview,
apply with consent, record views. 165 vitest tests. See `PROJECT_STATE.md`.

## 3. Currently being implemented
Nothing is in flight. The working tree is clean. (An earlier handoff described uncommitted
frontend and AI work; it was not in the tree on 2026-11-01, so T-071..T-074 start from scratch.)
Every P0 screen is built. Next up: the AI copilot (T-071, READY). T-058 is also READY; T-067 holds
the deferred list and detail UI details; T-066 (admin, P1) is in the backlog.

**Notes for the next frontend task:**
- The sidebar lists only built pages, and `sectionHref` returns a link only for built pages the role
  may open. Flip `ready: true` in `apps/web/components/shell/nav-config.ts` when a page lands; the
  Overview's KPI cards, category rows and health rows then become links automatically.
- Reuse what T-061 added: `lib/format/*`, `lib/status-maps.ts`, `components/status/status-pill.tsx`,
  `components/data/values.tsx` (Money, DateTime, DueLabel), `components/actions/action-button.tsx`,
  `components/states/empty-state.tsx`, and `test/fetch.ts` `routeFetch` plus `test/render.tsx`
  `renderInStore` for screen tests.
- Every page component calls `useStore()` and renders `PermissionDenied` when its route
  permission is missing (see `features/overview/overview-screen.tsx`). Query keys start with
  `["store", storeId, …]` (IA §7).
- List screens: reuse `components/data/data-table.tsx` (compact density, `pinned` first column,
  `hideBelow` up to `2xl`) and `list-controls.tsx`. For URL state, declare the fields with
  `defineListParams` (`lib/list-params.ts`) and bind them with `useListState`, as the three
  `features/inventory/*-screen.tsx` lists do; store-local date presets use `storeMidnight`. The older
  exceptions and orders param modules work the same way by hand. `HealthBadge` already applies the
  BR-402a data-issue rule.
- Import entry points: `newImportHref(store, type)` and `ImportLink` in
  `features/imports/import-actions.tsx` return nothing for roles without `imports.run`, so empty
  states can offer an import safely. File downloads go through `lib/api/download.ts` (fetch, then a
  toast on failure) rather than plain links.
- `Pagination` takes the list's `pageSizes`; pass `definition.options.pageSizes` when a list accepts
  sizes other than 25/50/100.
- Any horizontal scroll container must be `relative`, and page grids need `grid-cols-1` as a base, or
  phones get sideways page scroll (fixed in T-063).
- Mutations on exceptions go through `features/exceptions/detail/use-exception-command.ts`; follow the
  same shape (expected version, cache update, conflict toasts) for any other versioned resource.
- Local launch: `make api-dev` and `pnpm web:dev` (http://localhost:3000). `make seed` with
  `DEMO_STAFF_PASSWORD` set makes the seeded staff accounts usable for sign-in.

## 4. Broken or blocked
Nothing known broken. Hosting is not chosen (T-093). Open documentation gaps are listed under
"Known bugs / limitations" in `PROJECT_STATE.md`.

## 5. Files that matter
`docs/domain/*` (contracts) · `apps/api/app/domains/orders/state.py` (order FSM) ·
`apps/api/app/domains/inventory/service.py` (ledger and reservations) ·
`apps/api/app/domains/exceptions/engine.py` (evaluation and reconciliation) ·
`apps/api/app/domains/exceptions/rules/` (one pure module per rule) ·
`apps/api/app/domains/imports/service.py` (import apply) · `packages/contracts/src/schema.ts` (generated API types) · `apps/api/app/api/deps.py`
(auth/permission dependencies) · `apps/api/migrations/versions/` · `apps/web/lib/api/client.ts` (fetch
wrapper) · `apps/web/lib/query/query-client.ts` (retry and session-expiry policy) ·
`apps/web/features/session/session-gate.tsx` (session and store guards) · `apps/web/components/shell/`.

## 6. Decisions that must be preserved
Modular monolith · three order status axes and reachability import sync · `available = on_hand −
reserved` · append-only ledger · cycle-count-as-of semantics · one active exception per dedup key with
verification of manual resolutions · code-defined permission matrix · server-side sessions with
same-origin proxy · free-tier LLM only, with a deterministic fallback · no raw SQL tool for AI.

## 7. Start the application
```bash
make setup      # backend deps (uv, Python 3.12)
make migrate    # starts Postgres (docker) and applies migrations
make seed       # demo store "Kestrel Home & Kitchen" plus a first evaluation run
make api-dev    # http://localhost:8000/api/docs
pnpm install && pnpm web:dev   # http://localhost:3000 (proxies /api to :8000)
```

## 8. Run tests
```bash
make check      # ruff, format check, mypy --strict, pytest (needs docker Postgres)
pnpm --filter @retailops/web lint && pnpm --filter @retailops/web typecheck
pnpm --filter @retailops/web test && pnpm --filter @retailops/web build
```

## 9. What to do next
Follow "Next three highest-priority actions" in `PROJECT_STATE.md`.

## 10. Must not be changed without an ADR
The state machines, business rules, permission matrix, the error envelope and API conventions, and the
database schema (add migrations, never edit applied ones).
