# ADR-0002: Technology stack

| Field | Value |
|---|---|
| Decision ID | ADR-0002 |
| Title | Technology stack |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

The stack must support:

- Exact decimal money (BR-503) and timezone-aware timestamps (BR-501).
- Relational integrity features the domain relies on: partial unique indexes (one active exception
  per dedup key), composite keys, advisory locks, REPEATABLE READ snapshots.
- A typed API whose schema can generate client types (ADR-0013).
- Unit tests for pure rules and integration tests against a real database.
- A modern, accessible, responsive UI with good table, form and chart support.
- Free and open-source components, maintainable by one engineer.

## Alternatives considered

### A. Django + Django REST Framework

- **Pros:** batteries included (ORM, migrations, admin, auth); mature ecosystem.
- **Cons:** OpenAPI generation needs add-ons and is less precise than schemas declared with Pydantic;
  the built-in admin makes it easy to change status fields without going through domain transitions;
  heavier conventions than this API needs.

### B. TypeScript end to end (Node.js API with a TypeScript ORM, or Next.js route handlers)

- **Pros:** one language; types shared without generation.
- **Cons:** JavaScript numbers are floats, so money needs a decimal library everywhere; ORM support for
  partial indexes, advisory locks and isolation levels generally means raw SQL; Python is a better fit
  for the rule engine, data generation and the copilot evaluation tooling.

### C. The chosen stack, but with async SQLAlchemy

- **Pros:** better I/O concurrency, especially while waiting for LLM responses.
- **Cons:** async sessions forbid implicit lazy loading and complicate tests and transaction handling;
  the workload is short database-bound requests at modest concurrency, where sync endpoints in
  FastAPI's threadpool are sufficient.

### D. Database alternatives (MySQL, SQLite)

- **Cons:** MySQL lacks partial indexes; SQLite lacks concurrent writers and advisory locks. Neither
  matches the integrity features above as directly as PostgreSQL.

## Decision

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 with the **sync** engine and psycopg 3, Alembic |
| Database | PostgreSQL 16. **No pgvector in v1**: there is no document corpus that justifies semantic search; the copilot uses structured tools over relational data (ADR-0010) |
| Frontend | Next.js (App Router), TypeScript strict, Tailwind CSS, shadcn/ui (Radix), TanStack Query, React Hook Form + Zod, Recharts |
| Monorepo | pnpm workspace; `packages/contracts` generated from OpenAPI with openapi-typescript |
| Tests | pytest (unit and API integration against real PostgreSQL), vitest + Testing Library, Playwright |
| Infrastructure | Multi-stage Dockerfiles; docker compose services `db`, `api`, `worker`, `web`; GitHub Actions CI |
| Operations | Structured JSON logs with `request_id`; `/api/v1/health/live` and `/api/v1/health/ready` |

## Consequences

### Positive

- `Decimal`, timezone-aware datetimes and Pydantic validation make the money and time rules natural.
- PostgreSQL provides every integrity feature the domain needs without extra infrastructure.
- FastAPI's OpenAPI output drives generated TypeScript contracts.
- Sync SQLAlchemy keeps transactions, tests and lazy-loading behaviour simple.
- Every component is open source and runs locally in docker compose.

### Negative

- Two languages and two toolchains (Python and pnpm) in one repository and CI pipeline.
- Sync endpoints occupy a threadpool thread for their whole duration. A slow LLM call holds a thread,
  so concurrent copilot requests are bounded by the threadpool and the database pool; the copilot
  rate limit and timeouts keep this acceptable at the target scale (**Needs validation** under load).
- Next.js App Router plus a separate API means two servers to run and an extra proxy hop (ADR-0004).

## Related documents

- [`SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md)
- [`CONTAINER_DIAGRAM.md`](../architecture/CONTAINER_DIAGRAM.md)
- ADR-0001, ADR-0004, ADR-0010, ADR-0013
