# HANDOFF

Concise continuation guide for the next engineer or agent. Read `AGENTS.md` first.

## 1. What this project is
RetailOps Intelligence detects, prioritises, and tracks the resolution of e-commerce operational
exceptions (oversold SKUs, overdue fulfillment, pending refunds, data inconsistencies) from imported
CSV data. A free-tier LLM copilot explains the evidence and suggests next steps. Business logic is
deterministic, and AI is advisory only.

## 2. Completed
Docs M0–M3 (tagged). Backend: auth, sessions, CSRF (including pre-session `GET /auth/csrf`),
permissions, tenancy, audit; schema (migrations 0001–0003); order FSM; inventory ledger and
reservations; CSV import pipeline (with revalidate); exception engine and lifecycle API; read APIs
and analytics; organization member admin; AI copilot (tools, free-tier providers with the
deterministic fallback, conversations, summaries, note drafts, `make ai-eval`); scheduled worker;
demo seed with exception history and imports, demo reset job; compose stack (db, api, worker, web,
demo-seed); `SECURITY.md`. Web: every screen in `docs/design/SCREEN_SPECIFICATIONS.md` S-01..S-17
except the P1 analytics screen, including Copilot (S-14) and admin. `make check` 865 passed;
vitest 265 passed. See `PROJECT_STATE.md` and `PROGRESS.md` (latest entry) for detail.

## 3. Currently being implemented
**Manual test pass complete (2026-11-01)** on the seeded local data, as demo viewer, owner and
manager, with no open findings (details in `PROGRESS.md`). The working tree is clean; `main` is
ahead of `origin/main` and not pushed (the owner approves pushes).

**Exact next step:** ask the owner to push `main`, confirm the GitHub Actions run, then start T-081
(Playwright journey), T-083 (accessibility) and T-100 (README, screenshots, release notes).

**Notes for the next task:**
- Local stack: `make seed` (with `DEMO_STAFF_PASSWORD`), `make api-dev`, `pnpm web:dev`; or the
  compose stack (`make stack-up`, `make stack-demo-reset`). The seed changes the store id, so open
  the app from `/login`.
- Sign-in needs the pre-session CSRF token (`GET /auth/csrf`); backend tests use
  `tests.factories.login()` or `pre_session_csrf(client)`. A new mutating route a demo viewer may
  call must be listed in `VISITOR_PRIVATE` in `tests/integration/test_demo_read_only.py`.
- Security headers include `X-Frame-Options: DENY`, so pages cannot be framed (also not in tests).
- The sidebar lists only built pages; every v1 nav item is now `ready`. `sectionHref` still hides
  links the role may not open.
- Reuse: `lib/list-params.ts` + `useListState` for list URL state, `components/data/*`
  (`DataTable` with `pinned`, `hideBelow` to `2xl`, `renderExpanded`), `components/data/section.tsx`,
  `features/imports/import-actions.tsx` (`newImportHref`, `ImportLink`), `lib/api/download.ts`,
  `features/copilot/copilot-answer.tsx` (`CopilotAnswer`, `ReferenceChip`).
- Any horizontal scroll container must be `relative`, page grids need `grid-cols-1`, and long
  inline labels need truncation, or pages scroll sideways.
- Mutations on exceptions go through `features/exceptions/detail/use-exception-command.ts`.
- Backend tests in parallel need separate databases (`TEST_DATABASE_URL`); the suite drops and
  recreates the schema.

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
