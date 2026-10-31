# ADR-0007: Code-defined role and permission matrix

| Field | Value |
|---|---|
| Decision ID | ADR-0007 |
| Title | Code-defined role and permission matrix |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

Five roles (OWNER, MANAGER, STAFF, ANALYST, VIEWER) need fine-grained permissions such as the split
between working, assigning and managing exceptions. Some rules depend on data, not only on role: staff
may resolve only exceptions assigned to them, and may start only unassigned or own exceptions
(STATE_MACHINES §3.2). The public demo VIEWER must never be able to change shared data.

## Alternatives considered

### A. Role and permission tables with an admin UI

- **Pros:** organizations could define custom roles.
- **Cons:** an administrator (or a compromised admin session) can widen access by editing rows; the
  space of possible configurations is impossible to test exhaustively; seed data and migrations for
  permissions; an admin UI to build. Custom roles are a P3 roadmap item, not a v1 need.

### B. A policy engine (attribute-based access control)

- **Pros:** expressive rules ("assignee may resolve") in one place.
- **Cons:** a new dependency and policy language for a small rule set; harder to read in code review
  than a typed constant and a few explicit guards.

### C. Ad hoc role checks in handlers (`if role == "MANAGER"`)

- **Pros:** no up-front design.
- **Cons:** checks scatter, drift and are easy to forget on a new endpoint; nothing to test centrally.

## Decision

- Roles are an enum; permissions are a fixed set of strings (`exceptions.work`, `imports.run`, …).
- The role → permission matrix is a constant in `identity/permissions.py`. OWNER has all permissions;
  MANAGER all except `users.manage`; STAFF read access plus `exceptions.work`; ANALYST read access plus
  `analytics.read`, `audit.read`, `copilot.use`; VIEWER the same as ANALYST.
- Every non-public route declares `require_permission(...)`. A route inventory test fails if one does
  not.
- Data-dependent rules (assignee, last OWNER) live in service guards next to the transition they
  protect.
- `/auth/me` returns the effective permission set so the UI can hide or disable actions with a reason.
  The API remains the enforcement point.

## Consequences

### Positive

- Access rules are reviewed as code diffs and tested exhaustively (every role × permission).
- No privilege escalation by editing data.
- The demo VIEWER is read-only by construction.

### Negative

- Changing the matrix needs a code change and a deploy.
- No custom roles; organizations whose responsibilities do not match the five roles must pick the
  closest one.
- Roles are per organization (BR-002); a user cannot have different roles in different stores of the
  same organization.
- VIEWER inherits `audit.read` from ANALYST, which exposes audit metadata to public visitors (open
  question in SECURITY_ARCHITECTURE §16).

## Related documents

- [`SECURITY_ARCHITECTURE.md`](../architecture/SECURITY_ARCHITECTURE.md) §6
- [`STATE_MACHINES.md`](../domain/STATE_MACHINES.md) §3.2
- [`DOMAIN_MODEL.md`](../domain/DOMAIN_MODEL.md) (identity)
- ADR-0004, ADR-0011
