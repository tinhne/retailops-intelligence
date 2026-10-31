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
