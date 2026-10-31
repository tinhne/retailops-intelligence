# Decisions

Index of Architecture Decision Records (ADRs). Each ADR is a file in [`docs/decisions/`](docs/decisions/).
A thematic reading guide is in
[`docs/architecture/ARCHITECTURE_DECISIONS.md`](docs/architecture/ARCHITECTURE_DECISIONS.md).

Statuses: `Proposed` · `Accepted` · `Superseded by ADR-xxxx` · `Deprecated`.

| ID | Title | Status | Date | Link |
|---|---|---|---|---|
| ADR-0001 | Modular monolith | Accepted | 2026-10-31 | [ADR-0001](docs/decisions/ADR-0001-modular-monolith.md) |
| ADR-0002 | Technology stack | Accepted | 2026-10-31 | [ADR-0002](docs/decisions/ADR-0002-technology-stack.md) |
| ADR-0003 | Deterministic rule engine separated from the AI layer | Accepted | 2026-10-31 | [ADR-0003](docs/decisions/ADR-0003-deterministic-rule-engine-separate-from-ai.md) |
| ADR-0004 | Server-side opaque sessions, same-origin API proxy, CSRF double-submit | Accepted | 2026-10-31 | [ADR-0004](docs/decisions/ADR-0004-server-side-sessions-same-origin-proxy-csrf.md) |
| ADR-0005 | Single inventory location per store | Accepted | 2026-10-31 | [ADR-0005](docs/decisions/ADR-0005-single-inventory-location-per-store.md) |
| ADR-0006 | Three order status axes and reachability-based import sync | Accepted | 2026-10-31 | [ADR-0006](docs/decisions/ADR-0006-order-status-axes-and-reachability-import-sync.md) |
| ADR-0007 | Code-defined role and permission matrix | Accepted | 2026-10-31 | [ADR-0007](docs/decisions/ADR-0007-code-defined-role-permission-matrix.md) |
| ADR-0008 | Exception deduplication, verification and reopen semantics | Accepted | 2026-10-31 | [ADR-0008](docs/decisions/ADR-0008-exception-deduplication-verification-reopen.md) |
| ADR-0009 | Evaluation execution model: import-triggered, manual, and scheduled worker with advisory locks | Accepted | 2026-10-31 | [ADR-0009](docs/decisions/ADR-0009-evaluation-execution-model.md) |
| ADR-0010 | AI provider abstraction, free-tier providers, allowlisted tools, deterministic fallback, no raw SQL | Accepted | 2026-10-31 | [ADR-0010](docs/decisions/ADR-0010-ai-provider-abstraction-and-allowlisted-tools.md) |
| ADR-0011 | Public demo: read-only viewer now, sandbox later | Accepted | 2026-10-31 | [ADR-0011](docs/decisions/ADR-0011-public-demo-read-only-viewer.md) |
| ADR-0012 | Cycle-count cutoff for shipment movements | Accepted | 2026-10-31 | [ADR-0012](docs/decisions/ADR-0012-cycle-count-cutoff-for-shipment-movements.md) |
| ADR-0013 | OpenAPI-generated TypeScript contracts | Accepted | 2026-10-31 | [ADR-0013](docs/decisions/ADR-0013-openapi-generated-typescript-contracts.md) |

## Writing a new ADR

1. Copy the structure of an existing ADR: a header table (Decision ID, Title, Date, Status), then
   Context, Alternatives considered (at least two, each with pros and cons), Decision, Consequences
   (positive and negative), Related documents.
2. Use the next free number and a kebab-case file name: `docs/decisions/ADR-0014-short-title.md`.
3. Start it as `Proposed`. It becomes `Accepted` when the orchestrator approves it.
4. Add a row to the table above in the same commit.
5. If it changes module boundaries, update `ARCHITECTURE_MAP.md`; if it changes a business rule,
   update `docs/domain/*` and the tests that reference the rule (AGENTS.md §10).

## Superseding an ADR

Accepted ADRs are immutable records of what was decided and why. To change a decision:

1. Write a new ADR that explains what changed in the context, which alternatives were reconsidered,
   and the new decision. Its Context section names the ADR it replaces.
2. In the **old** ADR, change only the Status field to `Superseded by ADR-xxxx` and add a one-line note
   under the header table linking to the new ADR. Do not rewrite its body.
3. Update the Status column of both rows in the table above.
4. Update every document that cites the old decision (search the repository for its ID) so it points
   to the new ADR.
5. If the old decision is simply no longer relevant, without a replacement, set its status to
   `Deprecated` with a one-line reason instead.

Small clarifications that do not change the decision (typos, broken links, a missing related
document) may be edited in place.
