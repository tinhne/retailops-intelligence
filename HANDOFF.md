# HANDOFF

Concise continuation guide for the next engineer or agent. Read `AGENTS.md` first.

## 1. What this project is
RetailOps Intelligence detects, prioritises, and tracks the resolution of e-commerce operational
exceptions (oversold SKUs, overdue fulfillment, pending refunds, data inconsistencies) from imported
CSV data. A free-tier LLM copilot explains the evidence and suggests next steps. Business logic is
deterministic, and AI is advisory only.

## 2. Completed
Backend foundation (auth, sessions, CSRF, permissions, tenancy, audit), full database schema
(migrations 0001–0002), order state machine, and inventory ledger and reservations, all with tests.
Canonical domain docs are in `docs/domain/`. See `PROJECT_STATE.md` for the verified list.

## 3. Currently being implemented
Imports pipeline, exception engine and lifecycle API, read APIs and analytics (backend), and the
M0–M3 documentation set. See `PROJECT_STATE.md → In progress`.

## 4. Broken or blocked
GitHub remote not created (owner action), and no hosting chosen. Nothing known broken.

## 5. Files that matter
`docs/domain/*` (contracts) · `apps/api/app/domains/orders/state.py` (order FSM) ·
`apps/api/app/domains/inventory/service.py` (ledger and reservations) ·
`apps/api/app/domains/exceptions/engine.py` (evaluation entry point) · `apps/api/app/api/deps.py`
(auth/permission dependencies) · `apps/api/migrations/versions/`.

## 6. Decisions that must be preserved
Modular monolith · three order status axes and reachability import sync · `available = on_hand −
reserved` · append-only ledger · cycle-count-as-of semantics · one active exception per dedup key with
verification of manual resolutions · code-defined permission matrix · server-side sessions with
same-origin proxy · free-tier LLM only, with a deterministic fallback · no raw SQL tool for AI.

## 7. Start the application
```bash
make setup      # backend deps (uv, Python 3.12)
make migrate    # starts Postgres (docker) and applies migrations
make api-dev    # http://localhost:8000/api/docs
```

## 8. Run tests
```bash
make check      # ruff, format check, mypy --strict, pytest (needs docker Postgres)
```

## 9. What to do next
Follow "Next three highest-priority actions" in `PROJECT_STATE.md`.

## 10. Must not be changed without an ADR
The state machines, business rules, permission matrix, the error envelope and API conventions, and the
database schema (add migrations, never edit applied ones).
