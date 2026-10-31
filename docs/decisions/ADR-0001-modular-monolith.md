# ADR-0001: Modular monolith

| Field | Value |
|---|---|
| Decision ID | ADR-0001 |
| Title | Modular monolith |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

RetailOps Intelligence is built and operated by one engineer and targets small and mid-sized
e-commerce teams. The domain has strong consistency needs across areas:

- Applying one import writes products, orders, order lines, reservations and stock movements, and
  must be atomic (BR-606).
- An evaluation reads catalog, order, inventory and import data and writes exceptions from one
  consistent snapshot.
- Reservations and shipments must agree with order status changes in the same commit.

The code still needs clear internal boundaries so that each area can be understood, tested and, if
ever necessary, extracted.

## Alternatives considered

### A. Microservices (one service per domain)

- **Pros:** independent deployment and scaling; boundaries enforced by the network; failure isolation.
- **Cons:** the atomic import would need a saga or two-phase commit across services; analytics would
  need data replication or cross-service queries; each service needs its own pipeline, configuration,
  health checks and observability; operational cost far beyond what one person and a free-tier host
  can carry. The scaling benefit is irrelevant at the target scale.

### B. Unstructured monolith (code grouped by technical layer only)

- **Pros:** fastest start; no ceremony.
- **Cons:** any code can write any table, so invariants (append-only ledger, transitions only through
  `state.py`) erode quietly; ownership is unclear; rules become hard to test in isolation; extracting a
  module later means untangling everything.

### C. Serverless functions per endpoint

- **Pros:** pay per use; no servers to manage.
- **Cons:** connection management against PostgreSQL is awkward, cold starts hurt interactive use,
  the scheduled worker and advisory locks fit poorly, and local development diverges from production.

## Decision

Build one FastAPI application organized as a **modular monolith**:

- Nine modules under `apps/api/app/domains/`: identity, catalog, orders, inventory, imports,
  exceptions, audit, ai, analytics (DOMAIN_MODEL §1).
- Each module owns its tables. Only that module writes them.
- Cross-module calls go only through the other module's `service.py`, exchanging DTOs, never ORM
  objects. The service dependency graph is acyclic; the one cycle risk (imports ↔ exceptions) is
  broken by an explicit `ImportAppliedHandler` protocol bound at the composition root.
- Within a module: router → service → repository → models.
- Two narrow, documented exceptions: read-only analytics queries, and the demo reset command.
- One PostgreSQL database; one image deployed as two processes (`api`, `worker`).
- Boundaries are enforced by an import-graph test in CI.

## Consequences

### Positive

- Cross-module consistency is a single database transaction; no distributed protocols.
- One build, one image, simple local development with docker compose.
- Module boundaries are explicit and tested, so a module can be extracted later if real load or team
  structure ever requires it.
- Refactoring across modules is an ordinary code change with type checking.

### Negative

- Boundaries are enforced by convention and tests, not by process isolation; a determined shortcut is
  possible and must be caught in review or by the boundary test.
- The whole application scales as one unit, and the database is a shared failure domain.
- A slow query in one module can affect every module (mitigated by statement timeouts and indexes).
- Narrow service interfaces need ongoing discipline; DTO mapping adds some boilerplate.

## Related documents

- [`SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md) §4–§6, §10
- [`DOMAIN_MODEL.md`](../domain/DOMAIN_MODEL.md) §1
- [`ARCHITECTURE_MAP.md`](../../ARCHITECTURE_MAP.md)
- ADR-0002, ADR-0009
