# PROJECT_STATE

> Canonical current state. Update after every meaningful milestone. Verified facts only.

| Field | Value |
|---|---|
| Project | RetailOps Intelligence: E-commerce Operations & Decision Intelligence Platform |
| Owner | Lê Văn Trung Tính (GitHub `tinhne`) |
| Current milestone | **M6 frontend: foundation done (T-060).** Next: T-061 Overview, then T-062..T-065, M7 AI |
| Current phase | Backend core complete. Web foundation, sign-in and app shell built and verified. Data screens not built |
| Overall completion | M0–M3 documented and tagged. Backend M4–M5 implemented and tested. Web shell and sign-in done. No data screens, no copilot, not deployed |
| Last verified commit | `main` after merging `feat/web-foundation`: backend `make check` green (627 tests), web lint, typecheck, 57 tests and build green |
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
  app shell (demo banner, sidebar with rail and drawer, account menu, offline notice). The Overview
  route shows only its header until T-061.
- **Delivery:** API Dockerfile (non-root, builds), CI workflow (passed on GitHub), OpenAPI → TS contracts.

## In progress / next

| Task | Notes |
|---|---|
| T-061 Overview dashboard | READY. Replace the header-only page with S-02 (KPIs, attention list, trends) |
| T-062..T-065 Frontend screens | READY. Flip `ready: true` in `components/shell/nav-config.ts` as each page lands |
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
- **Doc/code gap (for T-062):** SCREEN_SPECIFICATIONS §0.4 lists `/claim`, `/unassign` and
  `/set-due-date` exception commands. The API has `/assign`, `/start` and `/due-date`, and no claim or unassign.
- The demo banner and `/demo` page omit the spec's "periodically reset" wording until the reset job exists (T-094).
- Behind the Next.js proxy, the API sees the proxy's IP unless `TRUST_PROXY_HEADERS=true`, so the demo
  sign-in limiter would be shared by all visitors. Set it in the deployed configuration (T-090, T-093).

## Latest test results

- `make check` (2026-11-01, after the contracts change): ruff OK, ruff format OK, mypy --strict OK, pytest **627 passed**.
- Web (2026-11-01): `pnpm --filter @retailops/web lint`, `typecheck`, `build` green; vitest **57 passed**.
  `pnpm audit --prod --audit-level high`: no known vulnerabilities.
- Browser check against the seeded local API: password and demo sign-in, `next` redirect, invalid
  credentials, session expiry, sign-out, unknown store, and the 375, 768 and 1280 px layouts.
- GitHub Actions run 41227323682 (5e24711, first run with the web foundation): success. API, web,
  dependency audit and Docker image jobs all passed.

## Owner decisions log

- 2026-10-31: The AI copilot uses **free-tier LLM APIs only** (Gemini by default, OpenAI-compatible
  free tiers as an alternative) with a deterministic fallback.
- 2026-11-01: The owner created the GitHub repository. Pushes go over SSH.

## Next three highest-priority actions

1. Overview dashboard (T-061), then the exception inbox and investigation (T-062), built from
   `docs/design/*` against `packages/contracts`.
2. Orders, products and inventory, and imports screens (T-063..T-065).
3. Compose stack with the web image (T-090) and demo exception history (T-056), then the AI copilot
   (T-071..T-073).
