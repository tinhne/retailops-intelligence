# API Conventions

> **Status:** v1 (T-022), 2026-10-31. Binding for every endpoint in `apps/api`. The resource map in
> [§12](#12-resource-map) is the planned surface; FastAPI's generated OpenAPI schema becomes the source
> of truth for exact shapes once endpoints exist (ADR-0013).

Related: [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) · [`SECURITY_ARCHITECTURE.md`](SECURITY_ARCHITECTURE.md) ·
[`DATA_FLOW.md`](DATA_FLOW.md) · [`STATE_MACHINES.md`](../domain/STATE_MACHINES.md)

## 1. Principles

- **One client, one origin.** The only client in v1 is the web app, which calls `/api/v1` on its own
  origin through the Next.js rewrite. There is no CORS configuration (ADR-0004).
- **The API is the authority.** Permissions, tenancy, validation and every business number are
  decided by the API. The UI never recomputes them.
- **State changes are explicit commands.** Lifecycle transitions are `POST` commands named after the
  transition, never a generic `PATCH {"status": ...}` ([§10](#10-commands-for-state-transitions)).
- **Predictable shapes.** One list envelope, one error envelope, snake_case, typed values.

## 2. Base path and documentation

| Item | Value |
|---|---|
| Base path | `/api/v1` |
| Store-scoped resources | `/api/v1/stores/{store_id}/...` |
| Organization-scoped resources | `/api/v1/organizations/{organization_id}/...` (members, audit log) |
| OpenAPI schema | `/api/v1/openapi.json` |
| Interactive docs | `/api/docs` (both can be disabled with `API_DOCS_ENABLED=false`) |

Versioning policy is in [§14](#14-versioning-and-deprecation).

## 3. Authentication and CSRF

| Mechanism | Detail |
|---|---|
| Session | `ro_session` cookie (opaque, `HttpOnly`, `Secure` in production, `SameSite=Lax`). No `Authorization` header and no bearer tokens |
| CSRF | `X-CSRF-Token` header equal to the `ro_csrf` cookie on POST, PUT, PATCH and DELETE. Before login, get the cookie from `GET /api/v1/auth/csrf`; after login it is bound to the session (SECURITY_ARCHITECTURE §5) |
| Public routes | `health/live`, `health/ready`, `meta`, `auth/csrf`, `auth/options` (whether the sign-in page may offer the demo), `auth/login`, `auth/demo` (demo mode only), and the OpenAPI documents. Everything else requires a session |
| Order of checks | 401 authentication → 403 CSRF → 404 tenancy → 403 permission → 422 validation → 409 state → 403 actor rules |

## 4. Request and response format

| Aspect | Convention |
|---|---|
| Media type | `application/json; charset=utf-8`, except uploads (`multipart/form-data`) and CSV downloads (`text/csv`) |
| Field names | snake_case, in bodies, query parameters and responses |
| Identifiers | UUID strings |
| Timestamps | ISO-8601 / RFC 3339 with offset. Responses are always UTC with `Z` (`2026-10-31T14:05:00Z`). Request timestamps without an offset are rejected with 422 (CSV imports follow BR-502 instead). The UI converts to the store time zone (BR-501) |
| Dates | `YYYY-MM-DD`, interpreted in the store time zone (analytics ranges) |
| Money | Decimal **string** with two decimals (`"1249.90"`), never a JSON number (BR-503). The currency is the store's currency, also returned on orders |
| Quantities | Integers |
| Enumerations | UPPER_SNAKE strings, exactly as in the domain docs (`IN_PROGRESS`, `INVENTORY_OVERSOLD`) |
| Nulls | Optional response fields are present with `null`, never omitted |
| Estimates | Values that are estimates (BR-152) are grouped under an `estimates` object, for example `"estimates": {"avg_daily_units": "1.75", "days_of_cover": 6}`, so a client cannot mistake them for facts |
| Single resource | The resource object itself, without a wrapper |
| Unknown request fields | Rejected with 422 (`extra="forbid"`) |
| Response headers | `X-Request-ID` on every response; `Cache-Control: no-store` on authenticated responses |

## 5. Pagination, sorting and filtering

**List envelope**

```json
{"items": [], "page": 1, "page_size": 25, "total": 123}
```

| Parameter | Rule |
|---|---|
| `page` | Integer ≥ 1, default 1. A page past the end returns `items: []` with the real `total` |
| `page_size` | 1 to 100, default 25. Larger values are rejected with 422, not silently clamped |
| `sort` | `sort=field` ascending, `sort=-field` descending, comma-separated for several keys (`sort=-priority_score,due_at`). Only fields listed for the endpoint are accepted (422 otherwise). The API appends `id` as a final tie-breaker so pages are stable |
| Exact filters | `status=OPEN`. Repeat the parameter for several values: `status=OPEN&status=REOPENED` |
| Ranges | `{field}_from` (inclusive) and `{field}_to` (exclusive), for example `placed_from`, `placed_to` |
| Text search | `q`, a case-insensitive match on the fields documented per endpoint (for example SKU and name) |
| Booleans | `true` / `false` |
| Special values | `assignee_id=me` and `assignee_id=unassigned` on the exception list |

`total` is an exact count. At the target data volumes this is cheap (**Needs validation** with the
benchmark in T-053); a cursor-based list is the fallback if it is not.

## 6. Errors

**Envelope**

```json
{
  "error": {
    "code": "EXCEPTION_TRANSITION_NOT_ALLOWED",
    "message": "An exception in status RESOLVED cannot be acknowledged.",
    "details": [{"field": null, "code": "CURRENT_STATUS", "message": "RESOLVED"}],
    "request_id": "6f1c2b8e-1d4a-4e0b-9a51-0d2f3c7a9b10"
  }
}
```

- `code` is stable and machine-readable; `message` is for people and may change.
- `details` is always an array. For validation errors, each item has `field` (a dotted path such as
  `body.resolution_note` or `query.page_size`), `code` and `message`. For conflicts it carries the
  facts needed to recover (for example the current `version`).
- Errors never contain stack traces, SQL, or internal identifiers of other tenants.

**Status codes**

| Status | Meaning |
|---|---|
| 400 | Malformed request: invalid JSON, wrong content type, malformed multipart |
| 401 | Not authenticated, or the session is invalid or expired |
| 403 | Authenticated but not allowed: missing permission, CSRF failure, or an actor rule |
| 404 | Not found **or belongs to another tenant**. Existence is never revealed |
| 409 | Conflict: invalid state transition, stale version, resource busy, import not applicable |
| 422 | Well-formed request that fails validation |
| 429 | Rate limited; `Retry-After` header in seconds |
| 500 | Unexpected error; details only in logs, `request_id` in the body |
| 503 | `health/ready` only: the database is unreachable |

**Error codes** (initial catalogue; new codes are added here first)

| Code | Status | When |
|---|---|---|
| `MALFORMED_REQUEST` | 400 | Body cannot be parsed |
| `AUTH_REQUIRED` | 401 | No valid session |
| `INVALID_CREDENTIALS` | 401 | Login failed, whatever the cause |
| `CSRF_FAILED` | 403 | Missing or mismatched CSRF token |
| `PERMISSION_DENIED` | 403 | Role lacks the permission, or an actor rule fails (for example resolving someone else's exception without `exceptions.manage`) |
| `NOT_FOUND` | 404 | Missing or other tenant |
| `VALIDATION_ERROR` | 422 | Body, query or path validation failed |
| `RATE_LIMITED` | 429 | Any rate limit |
| `STALE_VERSION` | 409 | `expected_version` differs from the stored version |
| `EXCEPTION_TRANSITION_NOT_ALLOWED` | 409 | Transition not allowed from the current status (STATE_MACHINES §3.2) |
| `EXCEPTION_NEWER_OCCURRENCE_EXISTS` | 409 | Proposed: manual reopen of an occurrence when a newer active exception exists for the same dedup key |
| (none) | 200 | A manual trigger while another run holds the store lock returns that request's run with status `SKIPPED`; it is not an error |
| `IMPORT_NOT_APPLICABLE` | 409 | Apply, discard or revalidate called in a status that does not allow it |
| `IMPORT_CONTENT_MISSING` | 409 | Revalidate (or apply) when the file bytes are no longer stored: a `FAILED` import keeps them only until its preview expiry |
| `IMPORT_PREVIEW_EXPIRED` | 409 | Apply after the 24 h preview window |
| `IMPORT_HAS_ERRORS` | 409 | Strict-mode apply of an import with error rows |
| `IMPORT_PREVIEW_STALE` | 409 | Re-validation inside apply produced different error rows than the user confirmed |
| `IMPORT_SKIPPED_ROWS_NOT_CONFIRMED` | 422 | Valid-rows-only apply without the matching skipped-row count |
| `IDEMPOTENCY_KEY_REUSED` | 422 | Key already used for a different resource or with a different body |
| `IDEMPOTENT_REQUEST_IN_PROGRESS` | 409 | The first request with this key is still running |
| `LAST_OWNER` | 409 | Demoting or deactivating the last active OWNER |
| `MEMBER_EXISTS` | 409 | Adding a member whose email is already a member of the organization |
| `EMAIL_IN_USE` | 409 | Adding a member whose email has an account in another organization (attaching existing accounts is open question O-35) |
| `MEMBER_IN_OTHER_ORGANIZATION` | 409 | Deactivating or reactivating an account that also belongs to another organization (`is_active` is per account) |
| `OWN_MEMBERSHIP` | 403 | Changing your own role or status (ROLE_AND_PERMISSION_WORKFLOW §8.2) |
| `CONVERSATION_FULL` | 409 | A copilot conversation reached `AI_MAX_MESSAGES_PER_CONVERSATION`; start a new one |
| `INTERNAL_ERROR` | 500 | Unexpected error |

CSV row-level issue codes (`UNKNOWN_SKU`, `ORDER_TRANSITION_NOT_ALLOWED`, …) are **data**, returned in
import issue lists, not HTTP errors.

## 7. Optimistic concurrency

- Exception resources include `version` (integer). Every exception command accepts an optional
  `expected_version` in the body.
- If it is present and differs from the stored value, the command fails with
  `409 STALE_VERSION` and `details` carries the current version. The client refetches and lets the
  person decide again.
- If it is absent, the command is validated against the current state under a row lock. The UI
  always sends it; scripts may omit it.
- `version` increases only when an exception event is written (status, assignment, severity, due
  date, material evidence change). Routine refreshes by the scheduled evaluation do not change it
  (SYSTEM_ARCHITECTURE §9).

## 8. Idempotency

Two endpoints accept an `Idempotency-Key` header: **import apply** and the **manual evaluation
trigger**. Both are expensive, user-initiated, and likely to be retried after a timeout or a double
click.

| Rule | Detail |
|---|---|
| Format | 8 to 128 characters from `[A-Za-z0-9_-]`. The web app generates a UUID when the confirmation dialog opens and reuses it for retries of that action |
| Scope | Per store and endpoint. The key is stored on the resource it produced: `data_import.apply_idempotency_key` and `evaluation_run.idempotency_key` (both proposed, unique per store) |
| First request | Processed normally. Apply returns 200 with the import (and its evaluation run summary); the trigger returns 201 with the run |
| Replay after completion | Returns 200 with the current representation of the same resource and the header `Idempotent-Replayed: true`. Nothing is re-applied or re-run |
| Replay while the first is running | `409 IDEMPOTENT_REQUEST_IN_PROGRESS` with `Retry-After` |
| Same key, different resource or body | `422 IDEMPOTENCY_KEY_REUSED` (for apply, the body is compared by `mode` and `confirm_skipped_rows`) |
| First request failed before creating anything | For example a validation error. No row holds the key, so a retry with the same key runs normally |
| Retention | As long as the import or run row exists |
| Without a key | Apply is still protected by its state machine: a second apply gets `409 IMPORT_NOT_APPLICABLE`. A second manual trigger without a key starts another run once the lock is free |

All other mutations are either naturally idempotent (acknowledging an already acknowledged
exception is rejected as an invalid transition, not duplicated) or protected by `expected_version`.

## 9. Rate limits

| Scope | Limit | Key | Notes |
|---|---|---|---|
| `POST /auth/login` | 5 per minute | client IP + normalized email | Throttles credential stuffing without locking accounts |
| `POST /auth/demo` | 10 per minute (proposed) | client IP | Only when demo mode is on |
| Other unauthenticated routes (except health) | 300 per minute (proposed) | client IP | |
| Authenticated requests | 300 per minute | principal | |
| Copilot (`messages`, `exception-summaries`, `note-drafts`) | 20 per minute | principal | Counted in addition to the general limit. Protects the shared free-tier LLM quota (ADR-0010) |

- Exceeding a limit returns `429 RATE_LIMITED` with `Retry-After`.
- The limiter is an in-process sliding window. **Limitation:** limits are per API process and reset
  on restart; v1 runs one API process. Scaling out needs a shared store such as Redis.
- The client IP comes from `X-Forwarded-For` only with `TRUST_PROXY_HEADERS=true`, which is safe
  only behind an edge proxy that appends the client address (SECURITY.md §5).
- "Principal" is the user id. For demo visitors it depends on the demo identity decision in
  ADR-0011 (per-visitor identity recommended, otherwise the session id).
- A 429 **from the LLM provider** is not an API error: the copilot falls back to the deterministic
  provider and says so in the answer.

## 10. Commands for state transitions

Lifecycle changes use `POST /…/{resource_id}/{command}`:

- Each command maps to one transition (or one assignment change) in STATE_MACHINES, with its own
  permission, required inputs, event type and audit action. A generic `PATCH` of `status` would hide
  those differences and invite bypassing the transition functions.
- The response is the updated resource (200), including the new `version`.
- `PATCH` is used only for plain attribute updates with no lifecycle meaning: store settings and
  membership role or activation.

## 11. Files

| Direction | Convention |
|---|---|
| Upload | `POST /stores/{store_id}/imports` with `multipart/form-data` fields `import_type` and `file`. Limits from BR-602 (`.csv`, UTF-8, ≤ 5 MB, ≤ 20,000 rows). A file-level failure still returns 201 with an import in status `REJECTED` and its issue, because the attempt belongs in the import history |
| Download | `text/csv; charset=utf-8`, `Content-Disposition: attachment` with a server-generated filename. Exported cells are formula-injection-safe (SECURITY_ARCHITECTURE §9) |
| Templates | Static CSV headers with fictional example rows per import type |

## 12. Resource map

Paths below are relative to `/api/v1`. "Member" means any role with a membership in the store's
organization. All mutating routes require the CSRF header.

### 12.1 Platform and identity

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/health/live` | public | Process is up; no I/O |
| GET | `/health/ready` | public | Database reachable; 503 otherwise |
| GET | `/meta` | public | API version, `demo_mode_enabled`, `copilot_mode` (`llm` or `deterministic`) |
| GET | `/auth/csrf` | public | Issue the pre-login `ro_csrf` cookie (204) |
| POST | `/auth/login` | public | Email and password; sets `ro_session` and a session-bound `ro_csrf` |
| POST | `/auth/demo` | public, demo mode only | Start a read-only VIEWER session in the demo organization |
| POST | `/auth/logout` | authenticated | Revoke the current session, clear cookies |
| GET | `/auth/me` | authenticated | User, memberships with role, effective permissions, accessible stores |
| POST | `/auth/password` | authenticated | Change own password (current and new); revokes the other sessions |
| GET | `/stores` | authenticated | Stores the user can access |
| GET | `/stores/{store_id}` | member | Store name, code, currency, time zone, demo flag |
| GET | `/stores/{store_id}/settings` | `settings.read` | Store settings (BUSINESS_RULES §7) |
| PATCH | `/stores/{store_id}/settings` | `settings.manage` | Update thresholds, weights, evaluation interval; validated and audited |
| GET | `/organizations/{organization_id}/members` | `users.read` | Members with email, role, `status` (`ACTIVE`, `DEACTIVATED`), `joined_at`, `last_login_at`; `{items}` sorted by name, no paging |
| POST | `/organizations/{organization_id}/members` | `users.manage` | Body `email`, `full_name`, `role`. Creates the account (no email delivery, ROLE_AND_PERMISSION_WORKFLOW §8.1) and returns 201 `{member, temporary_password}`, the password shown once; `409 MEMBER_EXISTS` / `EMAIL_IN_USE`. Audited as `user.create` |
| PATCH | `/organizations/{organization_id}/members/{membership_id}` | `users.manage` | Body `role` and/or `status`. Last-OWNER guard; not your own membership (403 `OWN_MEMBERSHIP`); deactivation revokes every session. Audited as `user.role_change`, `user.deactivate` (+ `auth.session_revoked`), `user.reactivate` |

### 12.2 Catalog

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/stores/{store_id}/products` | `catalog.read` | Filters `q` (SKU, name), `status`, `category`, `supplier_id`; sort `sku`, `name`, `-updated_at` |
| GET | `/stores/{store_id}/products/{product_id}` | `catalog.read` | Product with supplier |
| GET | `/stores/{store_id}/suppliers` | `catalog.read` | Suppliers with lead times |

### 12.3 Orders

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/stores/{store_id}/orders` | `orders.read` | Filters `q` (order number), `status`, `payment_status`, `fulfillment_status`, `channel`, `placed_from`, `placed_to`, `overdue`; default sort `-placed_at` |
| GET | `/stores/{store_id}/orders/{order_id}` | `orders.read` | Order with three status axes, lines and ship-by source |
| GET | `/stores/{store_id}/orders/{order_id}/events` | `orders.read` | Status history with source and skipped states |

Exceptions linked to an order use the exception list filter `order_id`.

### 12.4 Inventory

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/stores/{store_id}/inventory/positions` | `inventory.read` | `on_hand`, `reserved`, `available`, `incoming`, `incoming_eta`, `health`, and `estimates` (`avg_daily_units`, `days_of_cover`); filters `health`, `category`, `q` |
| GET | `/stores/{store_id}/inventory/positions/{product_id}` | `inventory.read` | One position with the last cycle count |
| GET | `/stores/{store_id}/inventory/movements` | `inventory.read` | Ledger; filters `product_id`, `movement_type`, `occurred_from`, `occurred_to`, `import_id` |
| GET | `/stores/{store_id}/inventory/reconciliation` | `inventory.read` | P1. Read-only BR-104 check: drift between balances and the ledger and reservations |

### 12.5 Imports

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/stores/{store_id}/imports` | `imports.read` | Import history; filters `import_type`, `status` (repeatable). Items carry `can_revalidate` |
| POST | `/stores/{store_id}/imports` | `imports.run` | Upload and validate (multipart); returns the import in `VALIDATED` or `REJECTED` |
| GET | `/stores/{store_id}/imports/{import_id}` | `imports.read` | Preview summary: new, updated, unchanged, error and warning counts, duplicate-file flag, expiry |
| GET | `/stores/{store_id}/imports/{import_id}/issues` | `imports.read` | Row issues; filters `severity`, `code`, `row_number`; sort `row_number` |
| GET | `/stores/{store_id}/imports/{import_id}/issues/export` | `imports.read` | Formula-safe CSV of the issues |
| POST | `/stores/{store_id}/imports/{import_id}/apply` | `imports.run` | Body `mode`, `confirm_skipped_rows`; `Idempotency-Key`; runs the import-triggered evaluation afterwards |
| POST | `/stores/{store_id}/imports/{import_id}/discard` | `imports.run` | `VALIDATED → DISCARDED` |
| POST | `/stores/{store_id}/imports/{import_id}/revalidate` | `imports.run` | `FAILED → VALIDATING → VALIDATED \| REJECTED` using the stored bytes, synchronous like the upload. A failed apply keeps the bytes until the preview's expiry; afterwards `409 IMPORT_CONTENT_MISSING` |
| GET | `/stores/{store_id}/import-templates/{import_type}` | `imports.read` | CSV template |

### 12.6 Exceptions and evaluations

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/stores/{store_id}/exceptions` | `exceptions.read` | Filters `status`, `active`, `exception_type`, `category`, `severity`, `priority_band`, `assignee_id` (uuid, `me`, `unassigned`), `product_id`, `order_id`, `evaluation_run_id` (exceptions that run detected), `due_to`; default sort `-priority_score`, also `due_at`, `-first_detected_at`, `severity` |
| GET | `/stores/{store_id}/exceptions/{exception_id}` | `exceptions.read` | Evidence, calculation, priority breakdown, links, `version` |
| GET | `/stores/{store_id}/exceptions/{exception_id}/events` | `exceptions.read` | Immutable history |
| GET | `/stores/{store_id}/exceptions/{exception_id}/notes` | `exceptions.read` | Notes with source |
| POST | `/stores/{store_id}/exceptions/{exception_id}/notes` | `exceptions.work` | Add a note; `source` is `USER` or `AI_DRAFT_ACCEPTED` |
| POST | `/stores/{store_id}/exceptions/{exception_id}/acknowledge` | `exceptions.work` | `OPEN → ACKNOWLEDGED` |
| POST | `/stores/{store_id}/exceptions/{exception_id}/claim` | `exceptions.work` | Assign an unassigned exception to oneself |
| POST | `/stores/{store_id}/exceptions/{exception_id}/start` | `exceptions.work` | `→ IN_PROGRESS`; auto-assigns the actor if unassigned |
| POST | `/stores/{store_id}/exceptions/{exception_id}/resolve` | `exceptions.work` + actor rule | `resolution_code`, `resolution_note` (≥ 10 characters); the assignee or a holder of `exceptions.manage` |
| POST | `/stores/{store_id}/exceptions/{exception_id}/dismiss` | `exceptions.manage` | `reason` (stored as `dismissed_reason`), `note` (≥ 10 chars) |
| POST | `/stores/{store_id}/exceptions/{exception_id}/reopen` | `exceptions.manage` | `reason`; only the latest occurrence for its dedup key |
| POST | `/stores/{store_id}/exceptions/{exception_id}/assign` | `exceptions.assign` | `assignee_id` (an active member with `exceptions.work`) |
| POST | `/stores/{store_id}/exceptions/{exception_id}/unassign` | `exceptions.assign` | Clear the assignee |
| POST | `/stores/{store_id}/exceptions/{exception_id}/set-due-date` | `exceptions.assign` | Override `due_at` with a reason; audited |
| POST | `/stores/{store_id}/evaluations` | `evaluations.run` | "Run analysis": synchronous run, 201 with the run; `Idempotency-Key`; 409 if one is running |
| GET | `/stores/{store_id}/evaluations` | `exceptions.read` | Run history with trigger, status and counts |
| GET | `/stores/{store_id}/evaluations/{run_id}` | `exceptions.read` | One run |

Every exception command accepts `expected_version` ([§7](#7-optimistic-concurrency)).

### 12.7 Analytics

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/stores/{store_id}/dashboard/summary` | `dashboard.read` | Attention list (top active exceptions by priority), counts by band and severity, overdue orders, exposure at risk (labelled as gross order-line value, BR-404), inventory health counts |
| GET | `/stores/{store_id}/analytics/trends` | `analytics.read` | `metric`, `date_from`, `date_to`, `granularity` (`day`, `week`) |
| GET | `/stores/{store_id}/analytics/exceptions` | `analytics.read` | Breakdown by type, category, severity and status; time to resolve |
| GET | `/stores/{store_id}/analytics/fulfillment` | `analytics.read` | On-time shipment rate against `ship_by`, paid-to-shipped hours |

### 12.8 Copilot

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/stores/{store_id}/copilot/conversations` | `copilot.use` | The caller's own conversations |
| POST | `/stores/{store_id}/copilot/conversations` | `copilot.use` | Start one; optional `context_type` `EXCEPTION` and `context_id` |
| GET | `/stores/{store_id}/copilot/conversations/{conversation_id}` | `copilot.use` | Messages with structured answers; 404 for other users' conversations |
| POST | `/stores/{store_id}/copilot/conversations/{conversation_id}/messages` | `copilot.use` | Ask a question; returns the structured answer with `generated_by`. `409 CONVERSATION_FULL` at the message cap |
| POST | `/stores/{store_id}/copilot/exception-summaries` | `copilot.use` + `exceptions.read` | `exception_id`, optional `refresh`; cached investigation summary |
| POST | `/stores/{store_id}/copilot/note-drafts` | `copilot.use` + `exceptions.work` | Draft a note for an exception (optional `user_hint`); returns the draft only, nothing is saved. Saving goes through the notes endpoint with `source = AI_DRAFT_ACCEPTED` |

Conversations of the shared demo viewer are private to the browser session (ADR-0011). Response
shapes are in the generated OpenAPI schema (`docs/ai/AI_ARCHITECTURE.md §5` explains the
structured answer).

### 12.9 Audit

| Method | Path | Permission | Description |
|---|---|---|---|
| GET | `/organizations/{organization_id}/audit-log` | `audit.read` | Filters `store_id`, `action`, `actor_user_id`, `target_type`, `target_id`, `occurred_from`, `occurred_to`; default sort `-occurred_at` |

## 13. OpenAPI and generated contracts

The TypeScript types in `packages/contracts` are generated, never written by hand (ADR-0013).

1. FastAPI produces the OpenAPI document from the Pydantic schemas and route declarations.
2. A script exports it without starting a server: `python -m app.core.openapi_export` writes
   `packages/contracts/openapi.json` (planned name).
3. `openapi-typescript` generates the type file in `packages/contracts` from that document.
4. Both files are committed. CI regenerates them and fails on any diff, so a backend change that
   alters the contract cannot merge without the regenerated types (AGENTS.md §10).
5. The web app imports `paths` and `components` types from `packages/contracts` through its typed
   wrapper in `apps/web/lib/api`.

Rules that keep the generated types useful:

- Every route declares its response model and its error responses (the error envelope schema for
  4xx).
- `operationId` is stable and readable (`{module}_{action}`, such as `exceptions_resolve`), set
  through FastAPI's unique-id function, so generated names do not change when paths change.
- One tag per module.
- Enumerations are Python `Enum` or `Literal` types, so they become string unions.
- Money fields are serialized as strings and typed as strings in TypeScript; the web app formats them
  without converting to floating point for arithmetic.

## 14. Versioning and deprecation

- The major version is in the path (`/api/v1`).
- Additive changes are allowed within v1: new endpoints, new optional request fields, new response
  fields, new filter parameters, new enumeration values. Clients must tolerate unknown fields and
  render unknown enumeration values generically.
- Breaking changes (removing or renaming a field, changing a type, tightening validation, changing
  semantics) are allowed in v1 only as a coordinated release of `api`, regenerated contracts and
  `web` in one change, because the web app is the only client and is deployed together with the API.
- Once a client outside this repository exists, breaking changes need `/api/v2`, with the old
  version marked deprecated and announced with a `Sunset` header (RFC 8594) for a published period.
