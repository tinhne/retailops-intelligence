# Architecture Map

A one-page map from architecture to code: modules, key files, API boundaries, table ownership,
dependencies, data flows and owners. Details live in
[`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md).

**Last updated:** 2026-10-31 (architecture v1, before any code exists).

## How to update this file

- Change the **Status** cell when code lands: `planned` → `scaffolded` (files exist, not
  feature-complete) → `implemented (<commit>)` → `verified (<test or CI evidence>)`.
- Add a row to **Key files** when a new file becomes an entry point or a boundary.
- A change to module boundaries, table ownership or allowed dependencies also needs an ADR
  ([`DECISIONS.md`](DECISIONS.md)) and an update to SYSTEM_ARCHITECTURE §4–§5 (AGENTS.md §10).
- Update the **Last updated** line.

## 1. Application modules

| Module | Backend path | Frontend feature | API prefix (under `/api/v1`) | Owner | Status |
|---|---|---|---|---|---|
| identity | `apps/api/app/domains/identity/` | `apps/web/features/admin/`, login | `/auth/*`, `/meta`, `/stores`, `/stores/{id}`, `/stores/{id}/settings`, `/organizations/{id}/members` | BE | planned |
| catalog | `apps/api/app/domains/catalog/` | `apps/web/features/inventory/` (products) | `/stores/{id}/products`, `/stores/{id}/suppliers` | BE | planned |
| orders | `apps/api/app/domains/orders/` | `apps/web/features/orders/` | `/stores/{id}/orders` | BE | planned |
| inventory | `apps/api/app/domains/inventory/` | `apps/web/features/inventory/` | `/stores/{id}/inventory/*` | BE | planned |
| imports | `apps/api/app/domains/imports/` | `apps/web/features/imports/` | `/stores/{id}/imports`, `/stores/{id}/import-templates/*` | BE | planned |
| exceptions | `apps/api/app/domains/exceptions/` | `apps/web/features/exceptions/` | `/stores/{id}/exceptions`, `/stores/{id}/evaluations` | BE | planned |
| audit | `apps/api/app/domains/audit/` | `apps/web/features/admin/` (audit viewer) | `/organizations/{id}/audit-log` | BE | planned |
| ai | `apps/api/app/domains/ai/` | `apps/web/features/copilot/` | `/stores/{id}/copilot/*` | AI (backend), FE (UI) | planned |
| analytics | `apps/api/app/domains/analytics/` | `apps/web/features/overview/` | `/stores/{id}/dashboard/*`, `/stores/{id}/analytics/*` | BE | planned |
| worker | `apps/api/app/workers/scheduler.py` | none | none | BE | planned |
| demo | `apps/api/app/demo/` | demo labelling in the shell | `/auth/demo` (via identity) | BE | planned |

## 2. Key files

| Path | Purpose | Task | Status |
|---|---|---|---|
| `apps/api/app/main.py` | App factory, middleware, routers, composition root (binds `ImportAppliedHandler`) | T-040 | planned |
| `apps/api/app/core/config.py` | Typed settings from environment variables | T-040 | planned |
| `apps/api/app/core/logging.py` | JSON logs, `request_id` context | T-040 | planned |
| `apps/api/app/core/errors.py` | Domain errors and the error envelope | T-040 | planned |
| `apps/api/app/core/security.py` | argon2id, session tokens, CSRF HMAC | T-042 | planned |
| `apps/api/app/core/rate_limit.py` | In-process rate limiter | T-042, T-082 | planned |
| `apps/api/app/core/pagination.py` | List envelope, `page`, `page_size`, `sort` | T-040 | planned |
| `apps/api/app/db/base.py`, `session.py` | Declarative base with constraint naming, engine, sessions | T-041 | planned |
| `apps/api/app/db/repository.py` | `StoreScopedRepository` (mandatory `store_id`) | T-041 | planned |
| `apps/api/app/db/locks.py` | Advisory lock namespaces and key derivation | T-053, T-055 | planned |
| `apps/api/migrations/` | Alembic environment and versions | T-041 | planned |
| `apps/api/app/domains/identity/permissions.py` | Role → permission matrix (ADR-0007) | T-042 | planned |
| `apps/api/app/domains/identity/deps.py` | `current_principal`, `csrf_protect`, `store_scope`, `require_permission` | T-042 | planned |
| `apps/api/app/domains/orders/state.py` | Order transitions, reachability, axis matrix | T-050 | planned |
| `apps/api/app/domains/inventory/calculations.py` | Health, velocity, cycle-count cutoff | T-051 | planned |
| `apps/api/app/domains/imports/parsing.py` | CSV parsing within limits | T-052 | planned |
| `apps/api/app/domains/exceptions/rules/` | Nine pure rule functions | T-053 | planned |
| `apps/api/app/domains/exceptions/evaluator.py`, `reconciliation.py`, `priority.py` | Run orchestration, STATE_MACHINES §3.3, PRIORITY_MODEL | T-053 | planned |
| `apps/api/app/workers/scheduler.py` | Scheduled evaluations with advisory locks | T-055 | planned |
| `apps/api/app/demo/generator.py`, `reset.py` | Demo dataset and reset command | T-056 | planned |
| `apps/api/app/domains/analytics/queries.py` | The only cross-module read-only SQL | T-057 | planned |
| `apps/api/app/domains/ai/tools/` | Allowlisted tool registry | T-071 | planned |
| `apps/api/app/domains/ai/providers/` | `gemini`, `openai_compatible`, `deterministic` adapters | T-072 | planned |
| `apps/api/evals/` | Copilot evaluation dataset and runner | T-074 | planned |
| `apps/api/tests/unit/`, `apps/api/tests/integration/` | Rule, transition and priority tests; API, permission and tenancy tests | T-040 onwards | planned |
| `packages/contracts/` | Generated OpenAPI document and TypeScript types (ADR-0013) | T-060 | planned |
| `apps/web/lib/api/` | Typed fetch wrapper, CSRF header, error envelope | T-060 | planned |
| `apps/web/app/(app)/` | Authenticated routes | T-060 to T-066 | planned |
| `apps/web/styles/tokens.css` | Design tokens | T-060 | planned |
| `apps/web/tests/e2e/` | Playwright critical journey | T-081 | planned |
| `docker-compose.yml`, `infra/docker/` | `db`, `api`, `worker`, `web` | T-090 | planned |
| `.github/workflows/ci.yml` | Lint, types, tests, builds, contract diff, dependency audit | T-091 | planned |

## 3. API boundaries

- The browser calls only the Next.js origin; `/api/*` is rewritten to the `api` container (ADR-0004).
- Store data: `/api/v1/stores/{store_id}/...`; organization data: `/api/v1/organizations/{organization_id}/...`.
- Lifecycle changes are `POST` commands (`/exceptions/{id}/resolve`), never `PATCH status`.
- Full resource map: [`API_CONVENTIONS.md` §12](docs/architecture/API_CONVENTIONS.md#12-resource-map).

## 4. Database ownership

Only the owning module writes a table. Readers outside the owner go through its service, except
`analytics` (read-only SQL, SYSTEM_ARCHITECTURE §10.1) and the demo reset (§10.2).

| Table | Owner | Read directly by |
|---|---|---|
| organization, store, store_settings, app_user, membership, user_session | identity | none |
| supplier, product | catalog | analytics |
| sales_order, order_item, order_event | orders | analytics |
| inventory_balance, inventory_movement, stock_reservation | inventory | analytics |
| data_import, import_row_issue | imports | analytics |
| evaluation_run, operational_exception, exception_entity_link, exception_event, exception_assignment, exception_note | exceptions | analytics |
| audit_log | audit | none |
| ai_conversation, ai_message, ai_tool_call | ai | none |

ER diagram: [`docs/domain/ENTITY_RELATIONSHIPS.md`](docs/domain/ENTITY_RELATIONSHIPS.md).

## 5. Allowed dependencies (service level)

| Module | May call |
|---|---|
| audit | none |
| identity | audit |
| catalog | none |
| orders | catalog |
| inventory | orders, catalog |
| imports | identity, catalog, orders, inventory, audit; exceptions only through the `ImportAppliedHandler` binding |
| exceptions | identity, catalog, orders, inventory, imports, audit |
| analytics | identity; read-only SQL over catalog, orders, inventory, imports, exceptions tables |
| ai | identity, catalog, orders, inventory, imports, exceptions, analytics |
| workers.scheduler | exceptions, identity |
| demo | identity, imports (and the services it uses), exceptions |

Every router may use `identity/deps.py`. Graph and reasons: SYSTEM_ARCHITECTURE §5.

## 6. Data flows (short)

| Flow | Path | Detail |
|---|---|---|
| Login | browser → web → api (identity) → db | [DATA_FLOW §1](docs/architecture/DATA_FLOW.md#1-login-and-an-authenticated-request) |
| Import | upload and validate → preview → apply (one transaction across catalog, orders, inventory) → import-triggered evaluation | [DATA_FLOW §2](docs/architecture/DATA_FLOW.md#2-csv-import-validate-preview-apply-evaluate) |
| Scheduled evaluation | worker → per-store advisory lock → snapshot → pure rules → reconciliation → exceptions and events | [DATA_FLOW §3](docs/architecture/DATA_FLOW.md#3-scheduled-evaluation) |
| Exception action | browser → exceptions command → row lock + version check → event + audit in one commit | [DATA_FLOW §4](docs/architecture/DATA_FLOW.md#4-exception-transition-with-optimistic-concurrency) |
| Copilot | browser → ai → provider (free-tier LLM or deterministic) → allowlisted tools → services → structured answer | [DATA_FLOW §5](docs/architecture/DATA_FLOW.md#5-copilot-question) |

## 7. Agent ownership

Consistent with AGENTS.md §9. Two agents never edit the same file at the same time.

| Area | Owner role | Others |
|---|---|---|
| `docs/product/`, `docs/workflows/` | Product/BA | read |
| `docs/domain/`, `docs/architecture/`, `docs/decisions/`, `packages/contracts/` (generation setup) | Architect, orchestrator approves | read |
| `apps/api/` (except `app/domains/ai/`) | Backend | read |
| `apps/api/app/domains/ai/`, `docs/ai/` | AI engineer | read |
| `apps/web/` | Frontend | read |
| `infra/`, `.github/`, `docker-compose.yml`, `Makefile` | DevOps | read |
| `PROJECT_STATE.md`, `HANDOFF.md`, `TASKS.md`, `DECISIONS.md`, `ARCHITECTURE_MAP.md` | Orchestrator | append to `PROGRESS.md` |

Notes:

- `ARCHITECTURE_MAP.md` is not listed in AGENTS.md §9; it is shown here under the orchestrator, who
  updates it as code lands.
- `packages/contracts/` files are generated. The backend change that alters the API regenerates them
  in the same commit (AGENTS.md §10); nobody edits them by hand (ADR-0013).
- `docs/architecture/SECURITY_ARCHITECTURE.md` is extended by QA during the security review (T-082).
