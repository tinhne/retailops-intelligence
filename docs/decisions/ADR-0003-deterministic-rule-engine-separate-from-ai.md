# ADR-0003: Deterministic rule engine separated from the AI layer

| Field | Value |
|---|---|
| Decision ID | ADR-0003 |
| Title | Deterministic rule engine separated from the AI layer |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

The product principle in AGENTS.md §1: business-critical facts and calculations are deterministic and
testable; AI explains and recommends, and never invents facts or bypasses business rules.

Operational exceptions drive real work (expediting stock, contacting customers, issuing refunds). A
team must be able to ask "why was this raised?" and get the same answer tomorrow. LLM output is
non-deterministic, can be wrong with high confidence, and may be unavailable (no key, quota exhausted).

## Alternatives considered

### A. LLM-based detection (send data to a model and ask it to find problems)

- **Pros:** flexible; could surface patterns no rule anticipates.
- **Cons:** non-reproducible results; impossible to unit test; no stable dedup key, so no reliable
  lifecycle; per-evaluation cost and quota use every 15 minutes; hallucinated issues; sends all
  operational data to a third party.

### B. Hybrid: rules detect, the LLM sets severity, priority or the recommended action

- **Pros:** richer, more contextual text.
- **Cons:** severity and priority drive the inbox order and due dates, so they would become
  non-reproducible; the recommended action would no longer be reviewable rule text.

### C. Configurable rule DSL stored in the database

- **Pros:** users could define rules without a deploy.
- **Cons:** a DSL, its validation, versioning and test tooling are a product of their own;
  premature before the nine v1 rules are validated with operators.

## Decision

- Each rule in EXCEPTION_CATALOG is a pure Python function
  `(snapshot, settings, as_of) → list[Finding]` with no I/O and an explicit `as_of` (BR-504), and a
  versioned id (`INV-OVERSOLD@1`).
- Severity, priority (PRIORITY_MODEL), due date, title, evidence, calculation and recommended action
  are all computed deterministically and stored with the exception.
- The AI layer only **reads** stored exceptions and service outputs through allowlisted tools
  (ADR-0010). Its output is labelled (facts, metrics, estimates, recommendations, limitations) and is
  never persisted as a business fact. The only AI-originated data saved in business tables is a note a
  person explicitly accepted (`source = AI_DRAFT_ACCEPTED`).

## Consequences

### Positive

- Every number on screen is traceable to a formula, its inputs and a rule version.
- Rules are unit-tested with fixed `as_of` values, and each test references its BR id.
- Detection works identically with or without an LLM.
- Changing a rule is a reviewed code change with a new version id, so history stays interpretable.

### Negative

- New rules need code and a deploy; operators cannot define their own in v1.
- Rules do not learn; thresholds are heuristics until validated with real operators
  (**Needs validation**, PRIORITY_MODEL limitations).
- The copilot's usefulness is bounded by rule coverage: it can explain only what rules and tools
  expose.

## Related documents

- [`EXCEPTION_CATALOG.md`](../domain/EXCEPTION_CATALOG.md)
- [`PRIORITY_MODEL.md`](../domain/PRIORITY_MODEL.md)
- [`BUSINESS_RULES.md`](../domain/BUSINESS_RULES.md) (BR-504)
- ADR-0008, ADR-0009, ADR-0010
