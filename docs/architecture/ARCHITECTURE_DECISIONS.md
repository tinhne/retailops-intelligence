# Architecture Decisions: Summary

> **Status:** v1, 2026-10-31. A reading guide to the ADRs. The index with statuses is
> [`DECISIONS.md`](../../DECISIONS.md); each ADR in [`docs/decisions/`](../decisions/) is authoritative.

## 1. Decisions by theme

### Shape of the system

| ADR | Decision | Main trade-off accepted |
|---|---|---|
| [ADR-0001](../decisions/ADR-0001-modular-monolith.md) | One FastAPI application with nine modules that own their tables and talk through services | Boundaries enforced by tests, not by process isolation; the app scales as one unit |
| [ADR-0002](../decisions/ADR-0002-technology-stack.md) | Python 3.12 / FastAPI / SQLAlchemy 2 (sync) / PostgreSQL 16; Next.js / TypeScript; no pgvector | Two languages and toolchains; sync endpoints hold threads during slow calls |
| [ADR-0013](../decisions/ADR-0013-openapi-generated-typescript-contracts.md) | TypeScript types generated from FastAPI's OpenAPI schema, checked in CI | Types only, no runtime validation of responses in the browser |

### Correctness of operational facts

| ADR | Decision | Main trade-off accepted |
|---|---|---|
| [ADR-0003](../decisions/ADR-0003-deterministic-rule-engine-separate-from-ai.md) | Pure, versioned rule functions decide exceptions, severity and priority; AI only reads and explains | New rules need code and a deploy; rules do not learn |
| [ADR-0005](../decisions/ADR-0005-single-inventory-location-per-store.md) | One implicit stock location per store | Multi-warehouse merchants are not supported |
| [ADR-0006](../decisions/ADR-0006-order-status-axes-and-reachability-import-sync.md) | Three order status axes; imports may jump to any reachable state, recording skipped states | Legitimate backward corrections are rejected; reachable-but-wrong jumps are accepted |
| [ADR-0012](../decisions/ADR-0012-cycle-count-cutoff-for-shipment-movements.md) | Shipment movements only for shipments after the latest cycle count | Depends on accurate source timestamps; back-dated counts are an open question |

### Exception workflow

| ADR | Decision | Main trade-off accepted |
|---|---|---|
| [ADR-0008](../decisions/ADR-0008-exception-deduplication-verification-reopen.md) | One active exception per dedup key; manual resolutions verified at the next run; recurrence window for reopen | Premature resolutions reopen; reconciliation is the most intricate logic |
| [ADR-0009](../decisions/ADR-0009-evaluation-execution-model.md) | Import-triggered, manual and scheduled runs; per-store advisory lock; one REPEATABLE READ transaction per run | Up to one interval of latency for time-based conditions; apply requests include evaluation time |

### Security and access

| ADR | Decision | Main trade-off accepted |
|---|---|---|
| [ADR-0004](../decisions/ADR-0004-server-side-sessions-same-origin-proxy-csrf.md) | Opaque hashed sessions in `HttpOnly` cookies, same-origin proxy, signed double-submit CSRF | A lookup per request; web and API must share one origin |
| [ADR-0007](../decisions/ADR-0007-code-defined-role-permission-matrix.md) | Five fixed roles; the permission matrix is a code constant | No custom roles; matrix changes need a deploy |
| [ADR-0011](../decisions/ADR-0011-public-demo-read-only-viewer.md) | Public visitors explore as read-only VIEWER; sandbox later | Visitors cannot try lifecycle actions yet |

### AI

| ADR | Decision | Main trade-off accepted |
|---|---|---|
| [ADR-0010](../decisions/ADR-0010-ai-provider-abstraction-and-allowlisted-tools.md) | Free-tier providers only (`gemini`, `openai_compatible`) behind `LLMProvider`, plus a `deterministic` fallback; eleven allowlisted read-only tools; no raw SQL | Shared free-tier quotas mean more deterministic answers under load; free-tier data-use terms need checking |

## 2. How the decisions fit together

- **ADR-0003 + ADR-0010** separate *deciding* from *explaining*. Every number the copilot cites comes
  from a rule or service the AI cannot change, which is why the copilot can be optional and why a
  free-tier model is acceptable.
- **ADR-0001 + ADR-0009** keep consistency inside one database: the import apply is one transaction,
  and the evaluation reads one snapshot, without a broker or distributed coordination.
- **ADR-0008 + ADR-0009** make the lifecycle trustworthy: deduplication needs non-overlapping runs per
  store, and verification needs runs that happen even without new data.
- **ADR-0006 + ADR-0012** together decide how imported order snapshots move stock: reachability guards
  the status change, the cutoff guards the ledger.
- **ADR-0004 + ADR-0007 + ADR-0011** give the public demo its safety: a session-based VIEWER whose
  permissions contain no mutation, enforced in the API.

## 3. Open questions raised by the ADRs

| Question | Raised in | Needs |
|---|---|---|
| Demo visitor identity (shared VIEWER user or per-visitor ephemeral user) | ADR-0011 | Orchestrator decision; domain model change if per-visitor |
| VIEWER's `audit.read` exposes IP addresses to public visitors | ADR-0007, ADR-0011 | Redaction or matrix change |
| Manual reopen of an older occurrence while a newer one is active | ADR-0008 | Rule in STATE_MACHINES §3.2 |
| Recurrence of a condition whose exception was resolved as `SUPERSEDED` | ADR-0008 | Rule in STATE_MACHINES §3.3 |
| Back-dated cycle counts | ADR-0012 | Business rule decision |
| Imported references using the reserved `order_item:` prefix | ADR-0012 | New import row error |
| Backward order corrections from source systems | ADR-0006 | Product decision |
| Proposed columns (`version`, idempotency keys, `file_content`, `cache_key`, run statuses) | ADR-0008, ADR-0009, ADR-0010 | Approval and update of DOMAIN_MODEL |

## 4. Changing a decision

Decisions are never edited to say something new. A new ADR supersedes the old one; the procedure is
in [`DECISIONS.md`](../../DECISIONS.md#superseding-an-adr).
