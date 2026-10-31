# PROJECT_STATE

> Canonical current state. Update after every meaningful milestone. Verified facts only.

| Field | Value |
|---|---|
| Project | RetailOps Intelligence: E-commerce Operations & Decision Intelligence Platform |
| Owner | Lê Văn Trung Tính (GitHub `tinhne`) |
| Current milestone | **M5: Core operational workflows** (in progress). M0–M3 documentation is in review |
| Current phase | Backend core implementation in parallel (imports, exception engine, read APIs and analytics) |
| Overall completion | Foundation stage. Backend foundation and domain core merged. No UI yet. Not deployed |
| Last verified commit | `28e6fbf` (main): `make check` green, 87 tests |
| Working branch | `main` (feature work merged via `--no-ff` merges) |
| Architecture version | v1 (modular monolith, see `docs/domain/*`, ADR-0001..0013) |
| Last update | 2026-10-31 23:30 (UTC+7) |

## Implemented (verified)

- Repository skeleton, agent guide, backlog, persistent state files.
- Canonical domain contracts: state machines, business rules BR-xxx, exception catalog (9 rules),
  priority model, domain model.
- Backend foundation: FastAPI app factory, settings with production guards, JSON logs with request
  IDs, error envelope, pagination, rate limiting, health live/ready.
- Identity and security: argon2id, opaque server-side sessions, session-bound CSRF, role → permission
  matrix, store-scoped access (cross-tenant → 404), demo viewer login, audit log and API.
- Database: Alembic migrations 0001 (identity, audit) and 0002 (catalog, orders, inventory,
  imports, exceptions, AI). `alembic check` shows no drift.
- Order lifecycle: transitions, reachability for import sync, axis matrix, timestamp rules, demand
  classes, upsert with immutable events, line lock (BR-609).
- Inventory: ledger with cycle-count-as-of semantics (BR-113), reservations sync (BR-120..123),
  shipment cutoff (BR-130/131), reconciliation (BR-104), health and velocity math.

## In progress

| Task | Owner role | Notes |
|---|---|---|
| T-001/T-002 product discovery docs | PM agent | `docs/product/*` |
| T-010 workflow docs | BA agent | `docs/workflows/*` |
| T-021..T-023 architecture docs, ADRs, ER diagram | Architect agent | Updating ADR-0010 for free-tier LLMs |
| T-030 design docs | Design agent | `docs/design/*` |
| T-070/T-080 AI docs and test strategy | AI/QA agent | Updating for free-tier LLMs |
| T-052 CSV import pipeline | Backend agent | `domains/imports`, `catalog/service.py`, `sample-data/` |
| T-053/T-054 exception engine and lifecycle API | Backend agent | `domains/exceptions` (except models) |
| T-050/T-051 read APIs, T-057 analytics, store settings | Backend agent | catalog/orders/inventory routers, `domains/analytics`, store router |

## Blocked

| Task | Blocker | Needed from owner |
|---|---|---|
| T-092 GitHub remote | The repo `tinhne/retailops-intelligence` does not exist and `gh` is not installed | Create the empty repo on GitHub, or run `gh auth login` |
| T-093 Deployment | No hosting provider or credentials | Choose a provider (free tier acceptable) |

## Known bugs

None recorded.

## Latest test results

`make check` on `28e6fbf`: ruff OK, ruff format OK, mypy --strict OK (57 files), pytest **87 passed**.

## Deployment status

Not deployed. Local stack: PostgreSQL via `docker compose up -d db`. The API runs with `make api-dev`.

## Owner decisions log

- 2026-10-31: The AI copilot must use **free-tier LLM APIs only** (Gemini via an AI Studio key by default,
  or an OpenAI-compatible free tier such as Groq or OpenRouter), with the deterministic fallback. Recorded in
  ENVIRONMENT_STATUS.md and ADR-0010.

## Next three highest-priority actions

1. Review and integrate the three backend agents' work (imports, exception engine, read APIs). Run `make check` and merge.
2. Review the M0–M3 documentation, fix inconsistencies, commit, and tag `discovery-complete`, `workflow-v1`, `architecture-v1`.
3. Demo dataset generator (T-056), then the frontend scaffold (T-060) from the design system.
