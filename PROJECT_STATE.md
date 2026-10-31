# PROJECT_STATE

> Canonical current state. Update after every meaningful milestone. Verified facts only.

| Field | Value |
|---|---|
| Project | RetailOps Intelligence: E-commerce Operations & Decision Intelligence Platform |
| Owner | Lê Văn Trung Tính (GitHub `tinhne`) |
| Current milestone | **M6 frontend: foundation, Overview, exceptions and orders done (T-060..T-063).** Next: T-064, T-065, then M7 AI |
| Current phase | Backend core complete. Web sign-in, shell, Overview, exceptions and orders built and verified. Products, inventory and imports screens not built |
| Overall completion | M0–M3 documented and tagged. Backend M4–M5 implemented and tested. Web shell, sign-in, Overview, the full exception workflow and orders done. Products, inventory and imports screens, copilot and deployment not done |
| Last verified commit | `main` after merging `feat/orders-ui`: backend `make check` green (629 tests), web lint, typecheck, 134 tests and build green |
| Remote | https://github.com/tinhne/retailops-intelligence (public). The first CI run passed |
| Architecture version | v1 (modular monolith; `docs/domain/*`, ADR-0001..0013) |
| Last update | 2026-11-01 (UTC+7) |

## Implemented (verified)

- **Docs:** product discovery, workflows, domain contracts, architecture, ADRs, design system and
  screens, AI architecture, test strategy. Tags `discovery-complete`, `workflow-v1`, `architecture-v1`.
- **Identity and security:** argon2id, server-side sessions, session-bound CSRF, role matrix
  (`GET /api/v1/roles`), cross-tenant 404, rate limits, audit log (no IP addresses exposed), demo viewer login.
- **Data model:** migrations 0001–0002 (all modules). `alembic check` shows no drift.
- **Orders and inventory:** order FSM (three axes, reachability), ledger with count-as-of semantics,
  reservations, shipment cutoff, reconciliation.
- **Imports:** 4 CSV types, preview, atomic apply (strict or valid-rows-only), idempotency, issue CSV, templates.
- **Exceptions:** 9 deterministic rules, reconciliation (dedup, refresh, auto-resolve, verify with
  grace, reopen, recurrence, supersede), priority and due dates, lifecycle API, evaluations API.
- **Read side:** products, orders, inventory positions and movements, dashboard, trends, exception
  breakdown, store settings, members.
- **Worker:** `python -m app.workers.scheduler` evaluates each store on its interval under the
  engine's advisory lock (T-055). Not yet in the compose stack.
- **Demo dataset:** `make seed` generates the fictional "Kestrel Home & Kitchen" store (114 products,
  1,549 orders, 8 suppliers, 60 days). The engine produces 18 exceptions across all 9 types.
- **Contracts:** OpenAPI → TypeScript. Identity schemas expose the `Role` and `Permission` enums.
- **Web foundation (T-060):** tokens and Tailwind theme, restyled shadcn/ui primitives, API client
  (CSRF header, `ApiError`), QueryClient policy (retries; 401 → sign-in), `/api` rewrite to FastAPI,
  `proxy.ts` optimistic sign-in redirect, S-01 sign-in and `/demo`, session gate, store resolution,
  app shell (demo banner, sidebar with rail and drawer, account menu, offline notice).
- **Overview (T-061):** S-02 with freshness strip, six KPIs, Needs attention, value at risk per
  category (never totalled, BR-404), stock health, shipments chart with a table view, recent imports,
  and Run analysis (idempotent, gated for the demo). Dashboard API gained `exposure_by_category`.
  Links stay plain text until their target pages exist.
- **Exceptions (T-062):** S-03 inbox (views, URL-state filters, search, sort, pagination, stacked
  mobile rows) and S-04 investigation (priority breakdown, calculation, evidence, affected orders,
  lifecycle banner, activity with notes). Every lifecycle command from the UI, laid out from the API's
  `available_actions`/`blocked_actions`, with stale-version handling. API gained a `due_to` filter and
  closing fields on list items.
- **Orders (T-063):** S-05 list (filters incl. store-local placed presets and overdue) and S-06 detail
  (three status axes with callouts, dates, lines with reservation and stock health, totals with the
  BR-205 mismatch, linked exceptions, history). Read-only, as orders change through imports.
- **Delivery:** API Dockerfile (non-root, builds), CI workflow (passed on GitHub), OpenAPI → TS contracts.

## In progress / next

| Task | Notes |
|---|---|
| T-064, T-065 Frontend screens | READY. Next up: products and inventory (T-064). Flip `ready: true` in `components/shell/nav-config.ts` as each page lands |
| T-067 List and detail UI follow-ups | BACKLOG (P1): exceptions mobile action bar and filter sheet, queue Previous/Next, jump menu, density, VIEWER explainer, evidence links; orders custom date range, import file links, Ask the copilot |
| T-058 Stock health data issue | READY (P1, backend). Negative on-hand products count as Oversold today (BR-402a) |
| T-071..T-073 AI copilot | T-071 READY. Needs migration 0003 (session-scoped demo conversations, tool-call result refs, cache key) |
| T-056 Demo seed history | Add exception history (assigned, in progress, resolved and verified, reopened, dismissed) via the lifecycle service |
| T-090 Compose stack | Add `api`, `worker`, `web` services and the web Dockerfile. The web image needs `API_INTERNAL_URL` at build time |

## Blocked

| Task | Blocker | Needed from owner |
|---|---|---|
| T-093 Deployment | No hosting provider or credentials | Choose a provider (free tier preferred) |

## Known bugs / limitations

- The evaluation engine uses a transaction-scoped advisory lock under READ COMMITTED with row locks.
  SYSTEM_ARCHITECTURE §8–9 describes REPEATABLE READ plus retry (documented deviation, acceptable at MVP scale).
- Evaluation and import idempotency keys are stored in audit details or import summary JSON (no dedicated column yet).
- Import validation and apply run row by row. A 20,000-row performance check has not been run.
- **Doc/code gap (for T-082):** ADR-0004 describes `GET /auth/csrf` issuing a pre-login CSRF token for
  the sign-in form. That endpoint does not exist and `POST /auth/login` is not CSRF-checked. Login CSRF
  is currently mitigated only because the endpoint accepts JSON bodies alone, which a cross-site form
  cannot send without a CORS preflight. Decide in the security review: implement it or amend the ADR.
- Products with `on_hand < 0` are classified by `available` and count as Oversold in stock health
  (dashboard, positions, product filters). BR-402a calls for a separate "Data issue" state (T-058).
- The demo store has no CSV imports (the seed writes rows directly), so the Overview says "No CSV
  imports yet" and the recent imports list is empty for the demo.
- The demo banner and `/demo` page omit the spec's "periodically reset" wording until the reset job exists (T-094).
- Behind the Next.js proxy, the API sees the proxy's IP unless `TRUST_PROXY_HEADERS=true`, so the demo
  sign-in limiter would be shared by all visitors. Set it in the deployed configuration (T-090, T-093).

## Latest test results

- `make check` (2026-11-01, after the exceptions API changes): ruff OK, ruff format OK, mypy --strict OK, pytest **629 passed**.
- Web (2026-11-01, after T-063): `pnpm --filter @retailops/web lint`, `typecheck`, `build` green; vitest **134 passed**.
  `pnpm audit --prod --audit-level high`: no known vulnerabilities.
- Browser check against the seeded local API: password and demo sign-in, `next` redirect, invalid
  credentials, session expiry, sign-out, unknown store, and the 375, 768 and 1280 px layouts.
  Overview as demo viewer and as manager (Run analysis), at 1440 and 375 px. Exceptions: acknowledge,
  start, resolve, Closed view and reopen as manager; read-only demo viewer; 1440 and 375 px. Orders:
  overdue filter, search, cancelled-but-paid and total-mismatch orders, 375 px with no sideways scroll.
- GitHub Actions run 41233590288 (orders, T-063): success. API, web, dependency audit and Docker image
  jobs all passed. It ran on 6d534b2, which is c5b7e57 after the history rewrite (same code).

## Owner decisions log

- 2026-10-31: The AI copilot uses **free-tier LLM APIs only** (Gemini by default, OpenAI-compatible
  free tiers as an alternative) with a deterministic fallback.
- 2026-11-01: The owner created the GitHub repository. Pushes go over SSH.
- 2026-11-01: Commits credit the owner only, with no tool co-author lines. The owner approved a one-time
  history rewrite to remove them from the 39 earlier commits (force-push of `main` and the 3 tags);
  code was unchanged. AGENTS.md's no-rewrite rule otherwise stands.

## Next three highest-priority actions

1. Products, inventory positions and movements (T-064), then imports (T-065), built from
   `docs/design/*` against `packages/contracts`; flip each nav `ready` flag as pages land.
2. Exceptions UI follow-ups (T-067) and the stock-health data-issue fix (T-058).
3. Compose stack with the web image (T-090) and demo exception history (T-056), then the AI copilot
   (T-071..T-073).
