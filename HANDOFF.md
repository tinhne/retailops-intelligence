# HANDOFF

Concise continuation guide for the next engineer or agent. Read `AGENTS.md` first.

## 1. What this project is
RetailOps Intelligence detects, prioritises, and tracks the resolution of e-commerce operational
exceptions (oversold SKUs, overdue fulfillment, pending refunds, data inconsistencies) from imported
CSV data. A free-tier LLM copilot explains the evidence and suggests next steps. Business logic is
deterministic, and AI is advisory only.

## 2. Completed
Docs M0–M3 (tagged). Backend: auth, sessions, CSRF, permissions, tenancy, audit; schema
(migrations 0001–0002); order FSM; inventory ledger and reservations; CSV import pipeline; exception
engine and lifecycle API; read APIs and analytics; demo dataset generator. `make check` gives 625 tests
green. The GitHub repo exists and its first CI run passed. See `PROJECT_STATE.md`.

## 3. Currently being implemented
Next up: the frontend (T-060..T-066), the scheduled evaluation worker (T-055), the compose stack
(T-090), and the AI copilot (T-071..T-073).

## 4. Broken or blocked
Nothing known broken. Hosting is not chosen (T-093).

## 5. Files that matter
`docs/domain/*` (contracts) · `apps/api/app/domains/orders/state.py` (order FSM) ·
`apps/api/app/domains/inventory/service.py` (ledger and reservations) ·
`apps/api/app/domains/exceptions/engine.py` (evaluation and reconciliation) ·
`apps/api/app/domains/exceptions/rules/` (one pure module per rule) ·
`apps/api/app/domains/imports/service.py` (import apply) · `packages/contracts/src/schema.ts` (generated API types) · `apps/api/app/api/deps.py`
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
make seed       # demo store "Kestrel Home & Kitchen" plus a first evaluation run
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
