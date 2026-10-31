# AGENTS.md: Instructions for every engineer and coding agent

Read this file completely before editing anything in this repository. Then follow the
[Resume protocol](#resume-protocol).

## 1. Product purpose

**RetailOps Intelligence** is an e-commerce operations and decision-intelligence platform for small
and mid-sized online stores. It ingests products, orders, and inventory data. Deterministic rules
detect operational exceptions such as oversold SKUs, overdue fulfillment, pending refunds, and data
inconsistencies. The team then prioritises, assigns, investigates, and resolves those exceptions,
with an AI copilot that explains the evidence and suggests next steps.

The product principle that overrides everything else: **business-critical facts and calculations
are deterministic and testable. AI explains and recommends. It never invents facts or bypasses
business rules.**

Owner: Lê Văn Trung Tính (independent portfolio project). Never invent customers, metrics,
deployments, or usage figures. Public documentation never mentions development tools or coding assistants.

## 2. Source-of-truth documents

| Topic | File |
|---|---|
| Current state, next actions | `PROJECT_STATE.md`, `HANDOFF.md` |
| Backlog | `TASKS.md` |
| History (append-only) | `PROGRESS.md` |
| Architecture decisions | `DECISIONS.md` → `docs/decisions/ADR-*.md` |
| Module map | `ARCHITECTURE_MAP.md` |
| State machines | `docs/domain/STATE_MACHINES.md` |
| Business rules (BR-xxx) | `docs/domain/BUSINESS_RULES.md` |
| Exception rules | `docs/domain/EXCEPTION_CATALOG.md` |
| Priority formula | `docs/domain/PRIORITY_MODEL.md` |
| Entities | `docs/domain/DOMAIN_MODEL.md` |

If code and these documents disagree, **do not silently pick one**. Verify the actual behavior,
then either fix the code or update the document with an ADR explaining the change.

## 3. Architecture (summary)

- Monorepo. `apps/api` (Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16),
  `apps/web` (Next.js App Router, TypeScript, Tailwind, shadcn/ui, TanStack Query),
  `packages/contracts` (TypeScript types generated from the API's OpenAPI schema).
- Backend is a **modular monolith**: `apps/api/app/domains/<module>/` each with `models.py`,
  `schemas.py`, `service.py`, `router.py`, `repository.py` as needed. Modules: identity, catalog,
  orders, inventory, imports, exceptions, audit, ai, analytics.
- A module writes only its own tables. Cross-module calls go through the other module's `service.py`.
- The browser talks only to the Next.js origin. `/api/*` is proxied to FastAPI, so session cookies
  stay first-party (ADR-0004).

## 4. Coding standards

**Python**
- Type hints everywhere. `ruff` (lint + format) and `mypy --strict` on `app/` must pass.
- Pydantic v2 schemas for all API input/output. Never return ORM objects from routers.
- Money is `Decimal` / `NUMERIC(12,2)`, never float (BR-503). Time is timezone-aware UTC.
- Rule functions are pure. They receive `as_of` explicitly and never call `datetime.now()` (BR-504).
- Status fields change only through domain transition functions that validate and record events.
- Every store-scoped query is filtered by `store_id` through the repository helpers.

**TypeScript**
- `strict` mode. No `any` without a justification comment.
- API types come from `packages/contracts`. Do not hand-write duplicate response types.
- Use design tokens (`apps/web/styles/tokens.css` / Tailwind theme). No arbitrary hex values in components.
- Every data view implements the loading, empty, error, and permission-denied states.
- No fake controls: a button that does nothing must not exist.

## 5. Business rules you must not break

1. `available = on_hand − reserved` (BR-101). Never subtract committed demand twice.
2. Inventory movements are append-only (BR-110). Corrections are compensating movements.
3. Order transitions follow `STATE_MACHINES.md`. Imports may only move orders to **reachable** states.
4. One active exception per dedup key. Manual resolution is verified by the next evaluation.
5. Exposure is "gross order-line value at risk", never "loss" (BR-404).
6. Imports never silently skip rows. Apply is atomic.
7. AI tools are allowlisted, permission-checked, store-scoped, and size-limited. There is no raw SQL tool.

## 6. Security requirements

- Passwords are hashed with argon2id. Session tokens are opaque and stored hashed. Cookies are
  `HttpOnly`, `Secure` in production, and `SameSite=Lax`, and mutating requests need the CSRF
  double-submit header.
- Authorization is enforced in the backend (`require_permission`). Hiding something in the
  frontend is never enough.
- Never commit secrets. `.env` is gitignored, and `.env.example` lists variable **names** with
  safe placeholder values only.
- Error responses never leak stack traces or SQL. Use the standard error envelope.
- Cross-tenant tests must exist for every new store-scoped endpoint.

## 7. Testing requirements

- Backend: `pytest` with unit tests for rules, transitions, and priority, plus API integration
  tests against a real PostgreSQL instance (Docker), including permission and tenancy tests.
- Frontend: `vitest` with Testing Library for components, and Playwright for the critical journeys.
- A change to a business rule must change or add a test that references the rule ID.
- Never weaken, skip, or delete a test to make CI pass. Record known failures in `PROJECT_STATE.md`.

## 8. Git conventions

- `main` is stable. Do substantial work on `feat/*`, `fix/*`, `docs/*`, or `chore/*` branches and merge only when checks pass.
- Commit messages use Conventional Commits (`feat(api): …`, `docs(domain): …`, `test(exceptions): …`).
- Make small, meaningful commits. Never force-push, never rewrite published history, never commit secrets.
- Tag verified milestones only (`discovery-complete`, `workflow-v1`, `architecture-v1`, …).

## 9. File ownership (multi-agent work)

| Area | Owner role | Others may |
|---|---|---|
| `docs/product`, `docs/workflows` | Product/BA | read |
| `docs/operations` | QA (test strategy) / DevOps (deployment, runbooks) | read |
| `docs/domain`, `docs/architecture`, `docs/decisions`, `packages/contracts` | Architect (orchestrator approves) | read |
| `apps/api` | Backend | read |
| `apps/web` | Frontend | read |
| `apps/api/app/domains/ai`, `docs/ai` | AI engineer | read |
| `infra`, `.github`, `docker-compose.yml`, `Makefile` | DevOps | read |
| `PROJECT_STATE.md`, `HANDOFF.md`, `TASKS.md`, `DECISIONS.md`, `ARCHITECTURE_MAP.md` | Orchestrator (architect drafts) | append to `PROGRESS.md` |
| `packages/contracts/src/schema.ts` | Generated, never hand-edited | regenerate with `pnpm contracts:generate` after changing an endpoint |

Two agents never edit the same file at the same time. Shared contracts change first, in their own commit.

## 10. Required documentation updates

| When you… | Update |
|---|---|
| finish any task | `PROGRESS.md` (append), `TASKS.md` status (with evidence) |
| change a business rule | `docs/domain/*`, tests, and add an ADR if it reverses a decision |
| add or change an endpoint | OpenAPI is generated automatically. Regenerate `packages/contracts` |
| add an environment variable | `.env.example`, `ENVIRONMENT_STATUS.md` (name only) |
| change module boundaries | `ARCHITECTURE_MAP.md`, ADR |
| end a session | `PROJECT_STATE.md`, `HANDOFF.md` |

## 11. Prohibited shortcuts

- Marking a task DONE without running its verification.
- Hard-coding demo data in UI components or presenting seeded data as live production data.
- Using `float` for money, or naive datetimes.
- Letting the AI layer write to business tables, execute SQL, or change statuses without a human action.
- Catching and ignoring exceptions to make a test pass.
- Adding a dependency or service just to look impressive.

## Resume protocol

1. Read `AGENTS.md` (this file), `PROJECT_STATE.md`, `HANDOFF.md`, `TASKS.md`, and the latest entries of `PROGRESS.md` and `DECISIONS.md`.
2. Run `git status` and `git log --oneline -15`.
3. Run the test suites (`make test`) and note the results.
4. Compare the documented state with the code. If they disagree, trust verified command output and fix the documents.
5. Pick the highest-priority `READY` task in `TASKS.md`.
6. Before ending the session, update `PROJECT_STATE.md`, `PROGRESS.md`, `TASKS.md`, and `HANDOFF.md`.
