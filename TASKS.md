# TASKS

Statuses: `BACKLOG` · `READY` · `IN_PROGRESS` · `BLOCKED` · `REVIEW` · `DONE`.
A task moves to `DONE` only with evidence: a commit hash, test output, or a file that was verified.
Agent roles: **ORCH** orchestrator · **PM** product/BA · **ARCH** architect · **BE** backend ·
**FE** frontend · **AI** AI engineer · **QA** QA/security · **OPS** DevOps.

---

## M0: Product discovery

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-001 | P0 | Product vision, personas, JTBD, problem analysis, success metrics, scope and non-goals | none | PM | DONE | Six docs exist. Industry practice, MVP assumptions, and items to validate are labelled separately. No fabricated interviews or metrics | `docs/product/*.md` | Reviewed 2026-11-01, tag discovery-complete |
| T-002 | P0 | Prioritised feature catalogue (P0–P3), each with problem, story, preconditions, flows, rules, errors, acceptance criteria, permissions, audit | T-001 | PM | DONE | Every P0 feature fully specified | `docs/product/FEATURE_CATALOG.md` | Reviewed 2026-11-01 |

## M1: Business workflows

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-010 | P0 | Six workflow docs with Mermaid diagrams: order, inventory, exception, import (incl. data contracts), AI investigation, roles and permissions | T-020 | PM | DONE | Consistent with `docs/domain/*`. Edge cases and failure paths are documented | `docs/workflows/*.md` | Reviewed, tag workflow-v1 |

## M2: Domain and architecture

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-020 | P0 | Canonical domain contracts: state machines, business rules, exception catalog, priority model, domain model | none | ORCH | DONE | Docs exist and are internally consistent | `docs/domain/{STATE_MACHINES,BUSINESS_RULES,EXCEPTION_CATALOG,PRIORITY_MODEL,DOMAIN_MODEL}.md` | Written 2026-10-31. See PROGRESS |
| T-021 | P0 | ER diagram (Mermaid) matching `DOMAIN_MODEL.md` | T-020 | ARCH | DONE | Every v1 entity and relationship present | `docs/domain/ENTITY_RELATIONSHIPS.md` | docs/domain/ENTITY_RELATIONSHIPS.md |
| T-022 | P0 | Architecture docs: system, context, container, data flow, security, API conventions | T-020 | ARCH | DONE | C4-style Mermaid diagrams. API conventions define envelope, pagination, errors, auth, idempotency, rate limits | `docs/architecture/*.md` | Reviewed, tag architecture-v1 |
| T-023 | P0 | ADRs 0001–0013 plus the `DECISIONS.md` index | T-020 | ARCH | DONE | One file per decision in the standard format | `docs/decisions/ADR-*.md` | DECISIONS.md index |

## M3: Design system and UX

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-030 | P0 | Information architecture, user flows, design system (tokens), screen specs incl. all states, component inventory | T-010 | FE | DONE | Every P0 screen has its loading/empty/error/permission states specified | `docs/design/*.md` | docs/design/* aligned with API |

## M4: Backend foundation

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-040 | P0 | FastAPI scaffold: settings, structured JSON logging, request IDs, error envelope, `/health/live`, `/health/ready` | T-022 | BE | DONE | App boots. Health endpoints respond. ruff and mypy clean | `apps/api/app/core/*`, `main.py` | make check green |
| T-041 | P0 | DB layer: SQLAlchemy 2 base, session, Alembic, identity tables | T-040 | BE | DONE | `alembic upgrade head` on empty Postgres works | `apps/api/app/db/*`, `migrations/` | migrations 0001-0002, alembic check clean |
| T-042 | P0 | Auth and permissions: argon2 login, opaque sessions, CSRF, role matrix, `require_permission`, store scoping | T-041 | BE | DONE | Login/logout/me work. 401/403 behavior is tested. Cross-tenant access is denied | `domains/identity/*` | tests/integration/test_auth_and_access.py |
| T-043 | P0 | Audit log service and read API | T-042 | BE | DONE | Business actions write audit rows. `audit.read` is enforced | `domains/audit/*` | audit API + tests |

## M5: Core operational workflows

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-050 | P0 | Catalog and orders: models, order state machine (transitions, reachability, axis matrix), read APIs with filters/pagination | T-042 | BE | DONE | Every transition in `STATE_MACHINES.md §1` is tested | `domains/catalog`, `domains/orders` | test_order_state.py, test_api_orders.py |
| T-051 | P0 | Inventory: ledger, balances, reservation sync, cycle-count cutoff, health, velocity, reconciliation | T-050 | BE | DONE | BR-101..152 covered by tests | `domains/inventory` | test_inventory_*.py, test_api_inventory.py |
| T-052 | P0 | Import pipeline: 4 types, validation, preview, strict/valid-rows-only apply, error CSV export, templates, duplicate-file detection | T-051 | BE | DONE | BR-601..608 tested, including failure cases (headers, encoding, empty, duplicates, FKs, negatives, dates) | `domains/imports`, `sample-data/` | 150 tests, verified on clean main |
| T-053 | P0 | Exception engine: 9 rules, evaluator, precedence, dedup/refresh/auto-resolve/verify/reopen/supersede, priority, EvaluationRun | T-051 | BE | DONE | Every catalog rule has unit tests. Reconciliation table in `STATE_MACHINES.md §3.3` fully tested | `domains/exceptions` | rule and reconciliation tests |
| T-054 | P0 | Exception lifecycle API: list/filter/sort, detail, events, ack, assign/claim, start, resolve, dismiss, reopen, notes | T-053 | BE | DONE | Permission matrix per transition is tested. Events and audit are written | `domains/exceptions/router.py` | test_exception_api.py |
| T-055 | P0 | Scheduled evaluation worker with Postgres advisory lock per store | T-053 | BE | DONE | No concurrent runs per store. Each run is recorded | `app/workers/` | pytest plus a manual run |
| T-056 | P0 | Demo dataset generator (relative to now, internally consistent) plus `make seed` / demo reset | T-053 | BE | IN_PROGRESS | Seed produces each exception type at least once. Rerunning is deterministic for a fixed seed | `scripts/`, `app/demo/` | pytest snapshot of counts |
| T-057 | P0 | Analytics: dashboard summary, trends, exceptions by type/severity, fulfillment performance | T-053 | BE | DONE | Numbers reconcile with the underlying tables in tests | `domains/analytics` | test_api_analytics.py |
| T-058 | P1 | Stock health: classify `on_hand < 0` as a data issue instead of an availability class, and expose a data-issue count in `InventoryHealthSummary` (BR-402a). Today such products count as Oversold on the dashboard and in health filters | T-051, T-057 | BE | READY | Health classes exclude negative on-hand everywhere (positions, products, dashboard). Tests reference BR-402a | `domains/inventory/queries.py`, `domains/analytics` | pytest |

## M6: Frontend product

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-060 | P0 | Web scaffold: Next.js, Tailwind tokens, shadcn/ui, app shell and navigation, login, `/api` proxy, generated contracts, query client | T-030, T-042 | FE | DONE | Login works against the API. The shell is responsive. Lint, typecheck, and build pass | `apps/web/*`, `packages/contracts` | 2026-11-01: lint, typecheck, `next build` green; vitest 57 passed; browser check of password and demo sign-in, `next` redirect, session expiry, sign-out, unknown store, 375/768/1280 px layouts |
| T-061 | P0 | Overview dashboard (prioritised attention list, KPIs from real data) | T-057, T-060 | FE | DONE | All states. No hard-coded numbers | `apps/web/features/overview/` | 2026-11-01: vitest 90 passed (screen states, BR-404 per-category exposure, idempotent Run analysis); browser check as demo viewer and manager at 1440 and 375 px |
| T-062 | P0 | Exception inbox and investigation detail (evidence, calculation, priority breakdown, history, notes, actions) | T-054, T-060 | FE | DONE | Full lifecycle from the UI. Actions are hidden or disabled per permission, with a reason | `features/exceptions` | 2026-11-01: vitest 120 passed; browser check of acknowledge → start → resolve (validation) → closed view → reopen as manager, read-only demo viewer, 1440 and 375 px. Playwright journey stays with T-081 |
| T-063 | P0 | Orders list and detail (axes, timeline, linked exceptions) | T-050, T-060 | FE | DONE | Server-side filters and pagination | `features/orders` | 2026-11-01: vitest 134 passed; browser check of the list (overdue filter, search), a cancelled-but-paid order, a total mismatch, and 375 px |
| T-064 | P0 | Products, inventory positions (health), movement ledger | T-051, T-060 | FE | READY | Health badges match the backend | `features/inventory` | vitest |
| T-065 | P0 | Imports: upload, preview, issues table, apply with consent, history, error CSV, templates | T-052, T-060 | FE | READY | Every failure path is visible | `features/imports` | Playwright |
| T-066 | P1 | Admin: users and roles, store settings (thresholds, weights), audit log viewer | T-043, T-060 | FE | BACKLOG | Settings validation. Audit is filterable | `features/admin` | vitest |
| T-067 | P1 | List and detail UI follow-ups. Exceptions: sticky bottom action bar and filter sheet below 768 px, Previous / Next in queue, "On this page" jump menu, density toggle, lifecycle explainer for VIEWER (C-63), evidence source links once S-08 exists. Orders: custom placed date range, import file name links in the status history (needs S-13 and the file name on order events), "Ask the copilot" (with T-073) | T-062, T-063 | FE | BACKLOG | Per S-03..S-06 specs | `features/exceptions`, `features/orders` | vitest plus manual |

## M7: AI intelligence

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-070 | P0 | AI docs: architecture, tool catalog, prompt design, evaluation strategy, safety and limitations | T-022 | AI | DONE | Grounding contract defined (facts / metrics / estimates / recommendations / references) | `docs/ai/*.md` | docs/ai/* |
| T-071 | P0 | Tool registry (allowlisted, validated, permission-checked, store-scoped, size-limited, logged) | T-054, T-057 | AI | READY | Each tool has a permission test and a scope test | `domains/ai/tools/` | pytest |
| T-072 | P0 | Provider abstraction with **free-tier providers only**: `gemini` (default live), `openai_compatible` (Groq/OpenRouter free models), and `deterministic` (no key). Automatic fallback to deterministic on 429/timeout/outage with a visible notice. Summary cache per exception evidence version | T-071 | AI | BACKLOG | The product works with no API key. A quota-exhausted provider never breaks the copilot | `domains/ai/providers/` | pytest with a mocked 429 |
| T-073 | P0 | Copilot API and UI, exception investigation summary, note drafting (human accepts before save) | T-072, T-062 | AI/FE | BACKLOG | Answers show labelled sections and record references | `domains/ai`, `features/copilot` | Playwright |
| T-074 | P1 | Evaluation dataset and runner (tool selection, factual correctness, attribution, unsupported-answer rate, permission enforcement, latency) | T-072 | AI | BACKLOG | Results stored with date and provider, never fabricated | `apps/api/evals/` | `make ai-eval` |

## M8: Quality and security

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-080 | P0 | Test strategy document | T-022 | QA | DONE | Pyramid, tooling, data strategy, gates | `docs/operations/TEST_STRATEGY.md` | docs/operations/TEST_STRATEGY.md |
| T-081 | P0 | Playwright E2E: 12-step critical journey from the directive §12 | T-062..T-065, T-073 | QA | BACKLOG | Passes in CI against docker compose | `apps/web/tests/e2e/` | CI |
| T-082 | P0 | Security review plus `SECURITY.md` (threat model, controls, limitations), rate limiting, upload hardening | T-052, T-054 | QA | BACKLOG | Findings fixed or documented | `SECURITY.md`, `docs/architecture/SECURITY_ARCHITECTURE.md` | Checklist plus tests |
| T-083 | P1 | Accessibility and responsive review (keyboard, contrast, 375 px) | T-061..T-066 | QA/FE | BACKLOG | Critical issues fixed | none | axe checks plus manual |

## M9: Infrastructure and deployment

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-090 | P0 | Multi-stage Dockerfiles (api, web), compose (db, api, worker, web), health checks, non-root users, migrations on start | T-041, T-060 | OPS | IN_PROGRESS | `docker compose up --build` gives a working app with seeded demo data | `infra/docker/*`, `docker-compose.yml` | Manual plus CI docker build |
| T-091 | P0 | GitHub Actions CI: lint, types, tests (with a Postgres service), builds, docker build, dependency audit | T-090 | OPS | DONE | Green on main | `.github/workflows/ci.yml` | GitHub Actions run 41216596429 passed |
| T-092 | P0 | Create the GitHub repository `tinhne/retailops-intelligence` and push | none | OPS | DONE | Remote exists and main is pushed | none | `git ls-remote origin` showed main at 4f38073 plus 3 tags (2026-11-01; that commit is 78a31bf after the history rewrite) |
| T-093 | P1 | Hosting evaluation plus deploy pipeline (CD after CI) | T-091 | OPS | BACKLOG | Provider chosen with documented trade-offs. Deploy verified | `docs/operations/DEPLOYMENT.md` | Health check of the live URL |
| T-094 | P1 | Public read-only demo, demo reset job | T-056, T-093 | OPS/BE | BACKLOG | Anonymous visitors cannot mutate shared data | none | E2E against the deployment |
| T-095 | P2 | Per-visitor demo sandbox (an ephemeral org cloned from the seed, rate-limited, auto-expiring) | T-094 | BE | BACKLOG | Visitors can run the full workflow without affecting others | none | E2E |

## M10: Final release

| ID | Pri | Description | Deps | Agent | Status | Acceptance criteria | Files | Verification |
|---|---|---|---|---|---|---|---|---|
| T-100 | P0 | README (21 sections), real screenshots, demo guide, release notes, final handoff | all | ORCH | BACKLOG | Everything described is implemented | `README.md`, `docs/` | Manual review |

## Blockers needing the product owner

| ID | Needed from owner | Why |
|---|---|---|
| T-093 | Choose a hosting provider and supply credentials or a token (no paid resources without approval) | Deployment |
| T-072 | (Optional) A free Gemini API key from Google AI Studio | The live LLM provider (free tier). The deterministic fallback works without it |
