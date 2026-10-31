# ADR-0011: Public demo: read-only viewer now, sandbox later

| Field | Value |
|---|---|
| Decision ID | ADR-0011 |
| Title | Public demo: read-only viewer now, sandbox later |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

RetailOps Intelligence is a portfolio project. Visitors should be able to explore it in seconds,
without registering. The demo shows a fictional store, "Kestrel Home & Kitchen" (organization
"Kestrel Commerce"), with a seeded dataset generated relative to the current time that contains every
exception type. Shared demo data must not be vandalized, and one visitor's actions must not confuse the
next. The copilot runs on free-tier providers only (ADR-0010).

## Alternatives considered

### A. Open self-registration (every visitor creates an organization)

- **Pros:** full hands-on experience.
- **Cons:** registration friction; new organizations start empty; abuse and spam accounts; email
  verification would need email delivery, which is not in the stack.

### B. A shared demo login with write access and a periodic reset

- **Pros:** visitors can try the whole lifecycle.
- **Cons:** visitors overwrite each other's work between resets; data can be vandalized; the published
  credentials are effectively public.

### C. A per-visitor sandbox now (an ephemeral organization cloned from the seed)

- **Pros:** the best experience: full lifecycle without affecting anyone.
- **Cons:** cloning, expiry, clean-up, per-visitor rate limits and storage growth must all be built and
  operated. Valuable, but not before the core product exists.

### D. Screenshots or video only

- **Pros:** zero risk.
- **Cons:** no hands-on exploration; weak evidence that the product works.

## Decision

- "Explore the demo" (`POST /api/v1/auth/demo`, only when `DEMO_MODE_ENABLED=true`) signs the visitor in
  as a **VIEWER** in the demo organization (`is_demo = true`). VIEWER has the ANALYST permissions:
  read access, analytics, audit and the copilot. It holds no mutating permission, so it cannot change
  shared data.
- The UI labels seeded data as demo data at all times and shows lifecycle actions as disabled with a
  reason.
- `python -m app.demo.reset` regenerates the dataset relative to the current time. It is the only code
  path allowed to delete rows from append-only tables, and only for demo organizations. It runs on
  demand or from the host's scheduler, not from the worker.
- Seeded fictional staff accounts (example.com-style addresses) get random, unpublished passwords on
  public deployments.
- The per-visitor sandbox is a P2 roadmap item (T-095).

**Implementation note pending the orchestrator's decision: demo visitor identity.** If every visitor
signs in as the *same* VIEWER user, visitors share copilot conversations (conversations are private
per user), per-user rate limits and audit attribution. **Decided (orchestrator, 2026-10-31):** demo conversations and the per-user copilot rate limit
are scoped by **session** for the shared VIEWER account. Visitors never see each other's conversations
and each session gets its own budget. This needs no new user rows; the session reference is added to
`ai_conversation` in the AI migration (T-073). Per-visitor ephemeral users stay the P2 sandbox option
(T-095).

## Consequences

### Positive

- No registration; a visitor reaches real screens in one click.
- Shared data stays intact by construction (permissions, not UI hiding).
- The demo exercises the same code paths as a real store, including the copilot and the deterministic
  fallback.

### Negative

- Visitors cannot try the core lifecycle actions (acknowledge, assign, resolve) until the sandbox
  exists.
- All visitors share one free-tier LLM quota; under load they get more deterministic answers.
- VIEWER inherits `audit.read`, which would show visitors the IP addresses of other demo users.
  **Decided:** the audit API never returns `ip` or `user_agent` for any role (they stay in the
  database for incident investigation only), so VIEWER keeps `audit.read` without exposing other
  visitors.
- The demo identity question above must be settled before T-094.
- Timestamps in the seed age between resets; the scheduled evaluation keeps exceptions consistent with
  the passing time, but the reset cadence decides how "fresh" the story looks.

## Related documents

- [`SECURITY_ARCHITECTURE.md`](../architecture/SECURITY_ARCHITECTURE.md) §5, §16
- [`SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md) §10.2
- [`API_CONVENTIONS.md`](../architecture/API_CONVENTIONS.md) §9, §12.1
- ADR-0004, ADR-0007, ADR-0010
