# ADR-0009: Evaluation execution model

| Field | Value |
|---|---|
| Decision ID | ADR-0009 |
| Title | Evaluation execution model: import-triggered, manual, and scheduled worker with advisory locks |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

Exceptions must be current in three situations:

1. **After new data arrives** (an import is applied).
2. **On demand**, when a manager wants a fresh analysis.
3. **As time passes, with no new data.** Several rules are time-based: an order becomes overdue when
   the clock passes `ship_by` (BR-202), stalled after `stall_threshold_hours` (BR-203), and a refund
   overdue after `refund_overdue_hours` (BR-206). Without periodic evaluation these exceptions would
   never appear between imports.

Runs for the same store must not overlap: two concurrent reconciliations could both create an
exception for the same key (one would fail on the partial unique index) or interleave auto-resolve
and refresh decisions. The solution must not add infrastructure beyond the agreed stack.

## Alternatives considered

### A. Evaluate synchronously on every write (database triggers or service hooks)

- **Pros:** always fresh after a change.
- **Cons:** time-based rules never fire without writes; triggers hide business logic in the database
  and break the pure-rule design (ADR-0003).

### B. Task queue with a broker and a periodic scheduler (for example Celery or RQ with Redis)

- **Pros:** retries, distribution, mature tooling.
- **Cons:** adds a broker to run, secure and monitor for a single job type; more moving parts than the
  problem needs.

### C. Scheduler thread inside the API process

- **Pros:** no extra container.
- **Cons:** runs once per API replica; couples background work to web request capacity and deploys;
  harder to reason about during restarts.

### D. Database or host cron calling an internal endpoint

- **Pros:** no long-running worker.
- **Cons:** database-side schedulers are not available on every managed provider (**Needs
  validation** per provider); host cron ties the design to the platform; an HTTP trigger needs
  machine authentication.

## Decision

Three triggers, each recorded as an `evaluation_run` with its trigger, `as_of`, rule versions,
status, timings and counts:

| Trigger | Where it runs | Lock behaviour |
|---|---|---|
| `IMPORT` | In the apply request, after the apply transaction commits, through the `ImportAppliedHandler` binding | Waits up to `EVALUATION_LOCK_WAIT_SECONDS` (default 10); on timeout the run is recorded `SKIPPED` and the next scheduled run covers it |
| `MANUAL` | `POST /stores/{store_id}/evaluations` (`evaluations.run`), synchronous | Busy → `409 EVALUATION_IN_PROGRESS` |
| `SCHEDULED` | The `worker` process (`python -m app.workers.scheduler`), per store every `evaluation_interval_minutes` (default 15) | Busy → skip and log |

- **Locking:** a session-level PostgreSQL advisory lock per store, `pg_try_advisory_lock(EVALUATION,
  key(store_id))`, taken on a dedicated connection *before* the run's transaction and released in a
  `finally` block. The worker re-checks that the store is still due after acquiring the lock.
- **Snapshot:** each run is one REPEATABLE READ transaction that commits once. Serialization failures
  are retried up to three times.
- **Scope:** v1 runs all nine rules every time; the reconciliation already supports partial runs.
- There are no other background jobs.

## Consequences

### Positive

- No broker or scheduler service; the worker is the same image as the API.
- Runs for one store never overlap, and several workers are safe.
- Time-based exceptions appear within one interval of becoming true.
- Every run is observable and explains why exceptions appeared or closed.

### Negative

- Time-based detection latency is up to the interval plus one scheduler tick.
- The apply request includes evaluation time (**Needs validation** with a 20,000-row benchmark).
- Session-level advisory locks require real database sessions; a transaction-pooling proxy would
  force a redesign.
- Each run re-evaluates the whole store, which is fine at target scale but will need incremental
  evaluation for much larger stores.
- If the worker is down, only import-triggered and manual runs happen; its health check (heartbeat)
  and the run history make that visible.
- Housekeeping (expired sessions, stale previews) gets no scheduled job and is handled lazily.

## Related documents

- [`SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md) §8, §9, §11
- [`DATA_FLOW.md`](../architecture/DATA_FLOW.md) flows 2 and 3
- [`STATE_MACHINES.md`](../domain/STATE_MACHINES.md) §3.3, §4
- ADR-0003, ADR-0008
