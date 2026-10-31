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
