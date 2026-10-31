# PROJECT_STATE

> Canonical current state. Update after every meaningful milestone. Verified facts only.

| Field | Value |
|---|---|
| Project | RetailOps Intelligence: E-commerce Operations & Decision Intelligence Platform |
| Owner | Lê Văn Trung Tính (GitHub `tinhne`) |
| Current milestone | **M5 core operational workflows: backend complete.** Next: M6 frontend, M7 AI |
| Current phase | Backend core integrated and verified. Frontend scaffold exists, screens not built |
| Overall completion | M0–M3 documented and tagged. Backend M4–M5 implemented and tested. No UI screens, no copilot, not deployed |
| Last verified commit | `main` after merging `feat/exception-engine` plus contracts: `make check` green, 625 tests |
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
- **Demo dataset:** `make seed` generates the fictional "Kestrel Home & Kitchen" store. The engine
  produces 18 exceptions across all 9 types.
- **Delivery:** API Dockerfile (non-root, builds), CI workflow (passed on GitHub), OpenAPI → TS contracts.

## In progress / next

| Task | Notes |
|---|---|
| T-060..T-066 Frontend | Next.js 16 scaffold and libraries installed. Screens are specified in `docs/design/*` |
| T-071..T-073 AI copilot | Docs complete. Needs migration 0003 (session-scoped demo conversations, tool-call result refs, cache key) |
| T-055 Scheduled evaluation worker | **Done**: `app/workers/scheduler.py` with 2 tests. Not yet in the compose stack |
| T-056 Demo seed history | Add exception history (assigned, in progress, resolved and verified, reopened, dismissed) via the lifecycle service |
| T-090 Compose stack | Add `api`, `worker`, `web` services and the web Dockerfile |

## Uncommitted partial work (2026-11-01)

The frontend (apps/web) and AI copilot (apps/api/app/domains/ai) agents were stopped mid-task on a usage
limit. Their files are in the working tree, uncommitted and unverified. See HANDOFF.md §3.

## Blocked

| Task | Blocker | Needed from owner |
|---|---|---|
| T-093 Deployment | No hosting provider or credentials | Choose a provider (free tier preferred) |

## Known bugs / limitations

- The evaluation engine uses a transaction-scoped advisory lock under READ COMMITTED with row locks.
  SYSTEM_ARCHITECTURE §8–9 describes REPEATABLE READ plus retry (documented deviation, acceptable at MVP scale).
- Evaluation and import idempotency keys are stored in audit details or import summary JSON (no dedicated column yet).
- Import validation and apply run row by row. A 20,000-row performance check has not been run.

## Latest test results

`make check` (2026-11-01): ruff OK, ruff format OK, mypy --strict OK, pytest **625 passed** (~73 s).
GitHub Actions run 41216596429: success.

## Owner decisions log

- 2026-10-31: The AI copilot uses **free-tier LLM APIs only** (Gemini by default, OpenAI-compatible
  free tiers as an alternative) with a deterministic fallback.
- 2026-11-01: The owner created the GitHub repository. Pushes go over SSH.

## Next three highest-priority actions

1. Frontend core (T-060..T-065): app shell, login and demo entry, overview, exception inbox and
   investigation, orders, inventory, imports, built from `docs/design/*` against `packages/contracts`.
2. Scheduled evaluation worker (T-055) and the full compose stack with the web image (T-090), plus
   demo exception history (T-056).
3. AI copilot (T-071..T-073): migration 0003, tool registry, Gemini / OpenAI-compatible /
   deterministic providers with fallback, copilot UI.
