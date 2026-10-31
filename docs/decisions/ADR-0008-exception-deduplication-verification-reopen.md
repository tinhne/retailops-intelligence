# ADR-0008: Exception deduplication, verification and reopen semantics

| Field | Value |
|---|---|
| Decision ID | ADR-0008 |
| Title | Exception deduplication, verification and reopen semantics |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

Rules run after every import, on demand, and every 15 minutes. The same condition (SKU X is oversold)
is therefore detected many times. The team needs one place to work each problem, with its history.

Two further problems:

- People mark issues resolved before the underlying condition has actually changed. Value
  proposition #7, "Was the issue actually resolved?", requires the system to check.
- Conditions recur. A recurrence shortly after resolution usually means the fix did not hold; a
  recurrence weeks later is a new incident.

## Alternatives considered

### A. A new exception for every detection

- **Pros:** trivial to implement.
- **Cons:** the inbox floods with duplicates; assignment and notes fragment across copies.

### B. Deduplicate, but treat resolution as final (any recurrence is a new exception)

- **Pros:** simple lifecycle.
- **Cons:** no verification signal; a premature resolution silently hides a live problem until the next
  recurrence creates an unrelated record.

### C. Deduplicate and trust users completely (the system never reopens)

- **Pros:** the user is always in control.
- **Cons:** "resolved" stops meaning "fixed"; stale resolutions accumulate while conditions persist.

### D. Fingerprint by evidence (a new exception whenever the evidence changes)

- **Pros:** captures every material change.
- **Cons:** far too sensitive: every new order on an oversold SKU would split the incident.

## Decision

- Dedup key `{exception_type}:{entity_type}:{entity_id}`. A partial unique index on
  `(store_id, dedup_key)` for active statuses guarantees at most one active exception per condition.
- Each run reconciles findings against the latest exception per key using the table in
  STATE_MACHINES §3.3: create, refresh, auto-resolve (`CONDITION_CLEARED`), verify (`verified_at`),
  reopen (`VERIFICATION_FAILED`, `RECURRED_WITHIN_WINDOW` within `reopen_window_hours`, default 72),
  create a new occurrence linked by `previous_occurrence_id`, and keep dismissed exceptions dismissed
  until the condition clears.
- Only rules that ran in a given evaluation can auto-resolve.
- Precedence (BR-401; overdue over stalled) resolves the less severe exception as `SUPERSEDED` and
  carries the assignee over.
- `version` on the exception increments exactly when an `exception_event` is written (proposed
  column), so routine refreshes do not invalidate open screens.

## Consequences

### Positive

- One exception per live condition, with complete history, assignment and notes.
- "Resolved" is verified by the system at the next evaluation.
- Recurrences are distinguished from new incidents, and both are linked to earlier occurrences.
- Dismissals are respected while the condition persists, so accepted risks do not come back as noise.

### Negative

- A person who resolves an exception before the source data reflects the fix (for example
  `FIXED_IN_SOURCE_SYSTEM` before the corrected file is imported) sees it reopen at the next
  evaluation. The UI must state that resolutions are verified at the next analysis and that the
  corrected data should be imported first.
- Reconciliation is the most intricate logic in the system; every row of the §3.3 table needs tests
  (T-053).
- Because of the partial unique index, a manual reopen of an older occurrence while a newer one is
  active must be rejected (proposed `409 EXCEPTION_NEWER_OCCURRENCE_EXISTS`). STATE_MACHINES does not
  yet state this rule.
- Behaviour for a key whose latest exception was resolved as `SUPERSEDED` and whose condition
  returns within the window (it would be reopened as a recurrence) is not stated explicitly in
  STATE_MACHINES. Open question.

## Related documents

- [`STATE_MACHINES.md`](../domain/STATE_MACHINES.md) §3
- [`EXCEPTION_CATALOG.md`](../domain/EXCEPTION_CATALOG.md) (dedup keys, precedence)
- [`ENTITY_RELATIONSHIPS.md`](../domain/ENTITY_RELATIONSHIPS.md) §4.1, §5
- [`DATA_FLOW.md`](../architecture/DATA_FLOW.md) flows 3 and 4
- ADR-0003, ADR-0009
