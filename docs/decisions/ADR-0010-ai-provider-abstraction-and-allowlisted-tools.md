# ADR-0010: AI provider abstraction, free-tier providers, allowlisted tools, deterministic fallback, no raw SQL

| Field | Value |
|---|---|
| Decision ID | ADR-0010 |
| Title | AI provider abstraction, free-tier providers, allowlisted tools, deterministic fallback, no raw SQL |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

The copilot explains exceptions, answers operational questions and drafts notes. Constraints:

- **AI explains; it never decides or writes** (AGENTS.md §1, ADR-0003).
- **The product must be fully usable without an LLM.**
- **Owner decision (2026-10-31): the copilot uses free-tier LLM APIs only.** The public demo is open to
  anonymous visitors, and nothing paid is used without the owner's approval.
- Answers must be grounded in the store's data, scoped to the user's store and permissions, and
  traceable to the queries that produced them.
- Imported data is untrusted and can contain text aimed at the model (prompt injection).

## Alternatives considered

### A. Paid frontier model API

- **Pros:** strongest answer quality and tool-calling reliability; higher rate limits; contractual
  data-use terms.
- **Cons:** per-token cost driven by anonymous public visitors, which cannot be bounded without strict
  quotas; contradicts the owner's decision. **Rejected: cost for a public demo.**

### B. Self-hosted open-weights model

- **Pros:** data stays on infrastructure the deployer controls; no per-call fees or third-party data
  terms.
- **Cons:** GPU (or large CPU) hosting cost; serving, updating and monitoring a model is an operations
  burden for one person; smaller models are weaker at reliable tool calling. **Rejected: hosting cost
  and operations burden.**

### C. Text-to-SQL (the model writes SQL against a read-only role)

- **Pros:** answers arbitrary questions.
- **Cons:** bypasses repository store scoping and permission checks (would need database row-level
  security to be safe); generated SQL is hard to validate; results cannot be tied to typed references;
  a prompt-injected query could read across tenants. **Rejected.**

### D. Retrieval over embeddings (pgvector)

- **Pros:** standard pattern for document question answering.
- **Cons:** there is no document corpus; the data is relational, changes every evaluation and must be
  exact. Embeddings would be stale and imprecise. **Rejected** (ADR-0002).

### E. Require an LLM (no fallback)

- **Pros:** one answer path to build.
- **Cons:** the product breaks without a key, when a free-tier quota is exhausted, or during an outage.
  **Rejected.**

### F. Call one vendor's SDK directly throughout the code

- **Pros:** least code initially.
- **Cons:** free tiers change and disappear; switching providers would touch every call site; tests
  would need the network. **Rejected.**

## Decision

**Provider abstraction.** An `LLMProvider` interface with three adapters:

| Adapter | When | Configuration |
|---|---|---|
| `gemini` | Default live provider: Google Gemini API with a free key from Google AI Studio | `GEMINI_API_KEY`, `LLM_MODEL` |
| `openai_compatible` | Any OpenAI-compatible free-tier endpoint (for example Groq, or free models on OpenRouter) | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` |
| `deterministic` | No key, or fallback. Intent routing → allowlisted tools → templated, grounded answer | none |

`LLM_PROVIDER` selects `deterministic`, `gemini` or `openai_compatible`. When unset, the API uses
`gemini` if `GEMINI_API_KEY` is set and `deterministic` otherwise. A live provider without its key logs
a startup warning and runs as `deterministic`. Keys are server-side only. A live model must support
tool (function) calling and JSON output; models without them are unsupported.

**Tools.** Eleven allowlisted read-only tools: `get_dashboard_summary`, `list_exceptions`,
`get_exception`, `get_exception_history`, `get_related_orders`, `get_product`,
`get_inventory_position`, `get_inventory_movements`, `get_overdue_orders`, `get_import_errors`,
`get_operational_trends`. Every tool validates its arguments with Pydantic, checks the user's
permission, binds the store and principal from the session (never from model arguments), calls the
owning module's service, caps results (≤ 50 rows), and records an `ai_tool_call` row. **There is no
raw SQL tool and no write tool.**

**Answers.** A structured schema: `summary`, `facts` (with `refs`), `metrics` (with `formula` and
`refs`), `estimates` (with `basis`), `recommendations` (with `rationale`), `limitations`,
`references`, `data_window`, and `generated_by` (`llm:<model>` or `deterministic`). Every reference
must resolve to a row returned by a tool in the same turn. An AI-drafted note is saved only when a
person with `exceptions.work` accepts it.

**Free-tier resilience.**

- Per-user copilot limit: 20 requests per minute.
- Automatic fallback to `deterministic` on provider 429, timeout, outage or invalid output. The answer
  says so in `limitations`, `generated_by` shows `deterministic`, and the UI shows a visible notice.
- After a provider 429, the live provider is skipped for a short cool-down so the quota is not
  hammered.
- Investigation summaries are cached per exception and exception `version` (plus store, permission
  set, provider, model and prompt version), so repeated views do not spend quota.
- Bounded tool iterations and a request timeout per call.

The detailed tool catalog, prompts and evaluation method are owned by the AI engineer in `docs/ai`
(T-070).

## Consequences

### Positive

- No LLM spend; the public demo cannot create a bill.
- The product works fully without a key, and degrades instead of failing when the free tier is
  exhausted.
- Switching providers is a configuration change.
- The copilot is testable offline (deterministic provider and a fake provider).
- The blast radius of a manipulated model is bounded: it can only read through scoped, permission-checked
  tools and produce labelled text.
- Every answer is traceable to its tool calls.

### Negative

- **Free-tier rate limits apply per key and are shared by every user of a deployment,** including
  public visitors. Under load, more answers come from the deterministic provider. The per-user limit
  alone cannot protect the shared quota, hence the cool-down and the summary cache.
- Free-tier model quality, latency and tool-calling reliability vary between models and can change
  without notice (**Needs validation** per model in the evaluation runner, T-074).
- Free tiers can be changed or withdrawn by providers, so the deterministic path must remain a
  first-class product feature, not a stub.
- **Data-use terms of free tiers must be verified.** Some free tiers allow the provider to use
  submitted data. No customer personal data is sent (BR-505), but store operational data is (SKUs,
  product names, order numbers, amounts). The public demo uses fictional data; a deployment with real
  store data must check the provider's current terms or run in `deterministic` mode.
- Two live adapters to maintain and test.
- Deterministic answers cover a narrower set of questions.
- An LLM can still misinterpret correct data; labelled sections and references reduce but do not
  eliminate this.

## Related documents

- [`SECURITY_ARCHITECTURE.md`](../architecture/SECURITY_ARCHITECTURE.md) §10
- [`DATA_FLOW.md`](../architecture/DATA_FLOW.md) flow 5
- [`SYSTEM_ARCHITECTURE.md`](../architecture/SYSTEM_ARCHITECTURE.md) §13 (configuration)
- [`ENTITY_RELATIONSHIPS.md`](../domain/ENTITY_RELATIONSHIPS.md) §5 (`ai_message.cache_key`)
- `docs/ai/` (T-070)
- ADR-0002, ADR-0003, ADR-0011
