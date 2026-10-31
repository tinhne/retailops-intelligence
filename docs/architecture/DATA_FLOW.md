# Data Flows

> **Status:** v1 (T-022), 2026-10-31. Sequence diagrams for the five flows that carry the most risk.
> Browser calls always go through the Next.js rewrite (`/api/*` → `api`); it is drawn in flow 1 and
> omitted afterwards for readability.

Related: [`SYSTEM_ARCHITECTURE.md`](SYSTEM_ARCHITECTURE.md) (§8 transactions, §9 concurrency) ·
[`API_CONVENTIONS.md`](API_CONVENTIONS.md) · [`SECURITY_ARCHITECTURE.md`](SECURITY_ARCHITECTURE.md) ·
[`STATE_MACHINES.md`](../domain/STATE_MACHINES.md) · [`BUSINESS_RULES.md`](../domain/BUSINESS_RULES.md)

| # | Flow | Key guarantees |
|---|---|---|
| 1 | [Login and an authenticated request](#1-login-and-an-authenticated-request) | Hashed opaque session, CSRF double-submit, 404 before 403 |
| 2 | [CSV import: validate, preview, apply, evaluate](#2-csv-import-validate-preview-apply-evaluate) | Nothing skipped silently, apply is one transaction, evaluation follows |
| 3 | [Scheduled evaluation](#3-scheduled-evaluation) | One run per store at a time, consistent snapshot, dedup reconciliation |
| 4 | [Exception transition](#4-exception-transition-with-optimistic-concurrency) | Valid transitions only, stale writes rejected, event and audit in the same commit |
| 5 | [Copilot question](#5-copilot-question) | Allowlisted, store-scoped tools; deterministic fallback; no writes |

## 1. Login and an authenticated request

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant B as Browser
    participant W as Next.js web
    participant A as FastAPI api
    participant D as PostgreSQL

    U->>B: Open the login page
    B->>W: GET /api/v1/auth/csrf
    W->>A: Rewrite to api, path unchanged
    A-->>B: 204 and Set-Cookie ro_csrf (random, readable by JS, SameSite=Lax)
    U->>B: Submit email and password
    B->>W: POST /api/v1/auth/login with header X-CSRF-Token
    W->>A: Forward cookies, headers and X-Forwarded-For
    A->>A: Rate limit, 5 per minute per IP and email
    A->>A: X-CSRF-Token must equal the ro_csrf cookie
    A->>D: SELECT app_user by lower-cased email
    A->>A: argon2id verify, against a dummy hash when the email is unknown
    alt Unknown email, wrong password or inactive user
        A->>D: INSERT audit_log auth.login_failed in its own transaction
        A-->>B: 401 INVALID_CREDENTIALS, one message for every cause
    else Credentials valid
        A->>D: INSERT user_session with token_hash = SHA-256 of a new 256-bit token
        A->>D: UPDATE last_login_at, INSERT audit_log auth.login, COMMIT
        A-->>B: 200 user, memberships, permissions. Set-Cookie ro_session (HttpOnly, Secure, SameSite=Lax) and a new ro_csrf bound to the session
    end

    Note over B,D: Later, an authenticated mutation
    B->>W: POST /api/v1/stores/S/exceptions/E/acknowledge with cookies and X-CSRF-Token
    W->>A: Forward unchanged
    A->>A: Assign request_id
    A->>D: SELECT user_session JOIN app_user WHERE token_hash = SHA-256 of the cookie
    opt Session missing, revoked, idle over 12 h, older than 7 days, or user inactive
        A-->>B: 401 AUTH_REQUIRED
    end
    A->>A: Header equals cookie and equals HMAC(SECRET_KEY, session id)
    opt CSRF check fails
        A-->>B: 403 CSRF_FAILED
    end
    A->>A: General rate limit per principal
    A->>D: SELECT store S and the principal's membership in its organization
    opt Store missing or in another organization
        A-->>B: 404 NOT_FOUND, existence never revealed
    end
    A->>A: require_permission exceptions.work for the member's role
    opt Role lacks the permission, for example VIEWER
        A-->>B: 403 PERMISSION_DENIED
    end
    A->>A: Service call, see flow 4
    A-->>B: 200 with X-Request-ID, sliding expiry extended at most every 5 minutes
```

Notes:

- The session token never leaves the cookie. JavaScript cannot read it, and the database stores
  only its SHA-256 hash, so a database leak does not yield usable sessions.
- Logout sets `revoked_at` and clears both cookies. Password change and member deactivation revoke
  all of the user's sessions.
- `POST /api/v1/auth/demo` follows the same success path with the demo VIEWER identity and no
  password (ADR-0011). It is available only when `DEMO_MODE_ENABLED=true`.

## 2. CSV import: validate, preview, apply, evaluate

Upload and validation are one request; preview reads are separate; apply is a separate request
with explicit consent. "Domain services" are the `catalog`, `orders` and `inventory` services, which
own the tables the import writes.

```mermaid
sequenceDiagram
    autonumber
    actor U as Manager
    participant B as Browser
    participant I as imports router and service
    participant M as Domain services
    participant X as exceptions service
    participant D as PostgreSQL

    U->>B: Choose type and file
    B->>I: POST /api/v1/stores/S/imports, multipart import_type and file
    I->>I: Session, CSRF, store scope, imports.run
    I->>I: Stream the body and stop past 5 MB. Check .csv name, strict UTF-8 (BOM allowed), required headers, at most 20,000 rows
    alt File-level failure
        I->>D: INSERT data_import REJECTED with one file-level issue, for example FILE_ENCODING or MISSING_COLUMNS
        I-->>B: 201 import with status REJECTED and the issue
    else File accepted
        I->>I: Parse with the csv module. Cell values are data and are never evaluated
        I->>M: Look up SKUs, existing orders and their statuses, adjustment references already applied
        I->>I: Validate rows: types, enums, duplicates in file, references, axis matrix, reachability, timestamps, currency
        I->>D: Look for a completed import of the same type with the same file_sha256
        I->>D: INSERT data_import VALIDATED with summary, file bytes, expires_at in 24 h, and all import_row_issue rows. One commit
        I-->>B: 201 import with status VALIDATED and counts
    end

    B->>I: GET the import and GET its issues, paginated
    I-->>B: Preview of new, updated, unchanged, error and warning counts, plus issues
    U->>B: Confirm apply, strict or valid rows only with the skipped-row count
    B->>I: POST .../imports/I/apply with mode, confirm_skipped_rows and Idempotency-Key K
    I->>D: Read the import
    alt Same key already used for this import
        I-->>B: 200 current import, nothing re-applied
    else Preview expired
        I->>D: Set DISCARDED, purge file bytes
        I-->>B: 409 IMPORT_PREVIEW_EXPIRED
    else Strict mode with error rows
        I-->>B: 409 IMPORT_HAS_ERRORS
    else Valid rows only and the confirmed count differs from the error rows
        I-->>B: 422 IMPORT_SKIPPED_ROWS_NOT_CONFIRMED
    else Preconditions hold
        I->>D: T1. UPDATE status to APPLYING WHERE status is VALIDATED, store key K, COMMIT
        I->>D: T2. BEGIN and take the per-store IMPORT_APPLY advisory lock
        I->>I: Re-parse the stored bytes and re-validate against current data
        alt Error rows differ from what the user confirmed
            I->>D: ROLLBACK T2. T3 sets FAILED with IMPORT_PREVIEW_STALE
            I-->>B: 409 IMPORT_PREVIEW_STALE, revalidate to continue
        else Same result as the preview
            I->>M: Upsert products and ensure balances, or upsert orders with order_event and skipped states, or upsert order lines, or append adjustment movements
            I->>M: Sync reservations. Write a SHIPMENT movement only if shipped_at is after the last cycle count (BR-130)
            I->>D: Set COMPLETED or COMPLETED_WITH_ERRORS, applied_at, purge bytes, INSERT audit_log import.apply, COMMIT T2
            I->>X: ImportAppliedHandler, after the commit
            X->>X: Evaluation with trigger IMPORT as in flow 3, waiting up to 10 s for the store lock
            X-->>I: Run reference, COMPLETED, FAILED or SKIPPED
            I->>D: UPDATE data_import.evaluation_run_id
            I-->>B: 200 import and evaluation run summary
        end
    end
```

Failure paths:

- **Any error inside T2** (constraint violation, bug, lost connection) rolls back every business
  change. A separate transaction marks the import `FAILED` with the error, and the response is the
  standard error envelope. "Retry" re-validates (`FAILED → VALIDATING`), using the bytes kept for
  `FAILED` imports.
- **Evaluation failure or lock timeout** never undoes the import. The run is recorded as `FAILED`
  or `SKIPPED`; the UI says the analysis will run at the next scheduled evaluation, and a user with
  `evaluations.run` can start it manually.
- **Valid-rows-only** applies only rows without errors. Skipped rows stay in `import_row_issue` and
  are downloadable as a formula-safe CSV (`GET .../issues/export`). Nothing is skipped silently
  (BR-606).

## 3. Scheduled evaluation

"Domain services" are the `catalog`, `orders`, `inventory` and `imports` services, which return
read-only snapshot DTOs. Manual and import-triggered runs follow the same path from `run_evaluation`
onwards; only the lock behaviour differs (SYSTEM_ARCHITECTURE §9).

```mermaid
sequenceDiagram
    autonumber
    participant S as worker scheduler
    participant E as exceptions service
    participant M as Domain services
    participant R as pure rules
    participant D as PostgreSQL

    loop Every SCHEDULER_TICK_SECONDS
        S->>D: SELECT stores, evaluation_interval_minutes, last finished run
        loop Each store whose last run is older than its interval
            S->>E: run_evaluation(store, SCHEDULED)
            E->>D: pg_try_advisory_lock(EVALUATION, key of store) on a dedicated connection
            alt Lock held by another run
                E-->>S: Skipped and logged, no run row
            else Lock acquired
                E->>D: Re-check that the store is still due
                E->>D: INSERT evaluation_run RUNNING with as_of = now, autocommit
                E->>D: BEGIN ISOLATION LEVEL REPEATABLE READ
                E->>M: Snapshot DTOs: products, balances, reservations, last counts, recent movements, orders and lines, velocity, rejected import rows
                E->>R: evaluate(snapshot, settings, as_of) for the 9 catalog rules
                R-->>E: Findings with dedup keys, precedence applied (BR-401, overdue over stalled)
                E->>D: SELECT the latest exception per dedup_key for the rules that ran
                E->>E: Reconcile each key with the table in STATE_MACHINES 3.3
                E->>D: Create OPEN exceptions with links and a DETECTED event
                E->>D: Refresh active ones, events only for material evidence or severity changes
                E->>D: Auto-resolve absent findings, verify or reopen manual resolutions, reopen recurrences, supersede less severe ones
                E->>D: Recompute priority and due date, version + 1 only where an event was written
                E->>D: UPDATE evaluation_run COMPLETED with counts and COMMIT
                alt Serialization failure SQLSTATE 40001
                    E->>E: Roll back and retry with a fresh snapshot, at most 3 attempts
                else Any other error
                    E->>D: ROLLBACK, then UPDATE evaluation_run FAILED with the error
                end
                E->>D: pg_advisory_unlock in a finally block
            end
        end
    end
```

Reconciliation outcomes per dedup key (from STATE_MACHINES §3.3):

| Latest exception for the key | Finding present | Finding absent |
|---|---|---|
| none | create `OPEN` | nothing |
| active | refresh evidence, `last_detected_at`, `detection_count`, severity, priority | auto-resolve `CONDITION_CLEARED` |
| `RESOLVED` by a user, first run after the resolution | reopen `VERIFICATION_FAILED` | set `verified_at` |
| `RESOLVED`, re-detected within `reopen_window_hours` | reopen `RECURRED_WITHIN_WINDOW` | nothing |
| `RESOLVED`, re-detected after the window | create new `OPEN` with `previous_occurrence_id` | nothing |
| `DISMISSED`, condition never cleared | update `last_detected_at` only | set `condition_cleared_at` |
| `DISMISSED`, condition had cleared | create new `OPEN` with `previous_occurrence_id` | nothing |

Supersession (BR-401) creates the more severe exception first, then resolves the less severe one with
`SUPERSEDED`, sets `superseded_by_id`, and carries the assignee over (an `ExceptionAssignment` row with
`assigned_by` null). Both keys differ, so the partial unique index is never violated mid-transaction.

## 4. Exception transition with optimistic concurrency

```mermaid
sequenceDiagram
    autonumber
    actor U as Staff member
    participant B as Browser
    participant A as exceptions router
    participant E as exceptions service
    participant AU as audit service
    participant D as PostgreSQL

    U->>B: Resolve with code and note
    B->>A: POST .../exceptions/E/resolve with resolution_code, resolution_note, expected_version 7
    A->>A: Session, CSRF, store scope, exceptions.work, Pydantic checks (note of at least 10 characters)
    A->>E: resolve(store, exception, principal, input)
    E->>D: BEGIN, SELECT operational_exception WHERE id = E AND store_id = S FOR UPDATE
    alt No row for this store
        E-->>B: 404 NOT_FOUND
    else expected_version differs from the stored version
        E-->>B: 409 STALE_VERSION, details carry the current version
    else Status is not OPEN, ACKNOWLEDGED, IN_PROGRESS or REOPENED
        E-->>B: 409 EXCEPTION_TRANSITION_NOT_ALLOWED
    else Actor is not the assignee and lacks exceptions.manage
        E-->>B: 403 PERMISSION_DENIED
    else Allowed
        E->>D: UPDATE status RESOLVED, resolved_at, resolved_by, code, note, version 8
        E->>D: INSERT exception_event STATUS_CHANGED with from and to status
        E->>AU: record exception.resolve with request_id, same transaction
        AU->>D: INSERT audit_log
        E->>D: COMMIT
        E-->>B: 200 exception at version 8
    end

    Note over B,D: A second user who loaded version 7 and acts now waits on the row lock, then gets 409 STALE_VERSION
    Note over E,D: The next evaluation verifies the resolution. Condition gone sets verified_at, condition present reopens with VERIFICATION_FAILED
```

The same pattern applies to every lifecycle command (acknowledge, start, claim, assign, unassign,
set due date, dismiss, reopen). Checks run in this order: tenancy (404), version (409), transition
validity (409), actor rules (403), then the write. `start` without an assignee assigns the actor and
writes both an `ASSIGNED` and a `STATUS_CHANGED` event; both bump `version` once per request.

## 5. Copilot question

```mermaid
sequenceDiagram
    autonumber
    participant B as Browser
    participant A as ai router
    participant C as copilot service
    participant P as provider adapter
    participant L as External LLM provider
    participant T as tool registry
    participant S as domain services
    participant D as PostgreSQL

    B->>A: POST .../copilot/conversations/C/messages with the question
    A->>A: Session, CSRF, store scope, copilot.use, limit 20 per minute per user
    A->>C: ask(store, conversation, question, principal)
    C->>D: Load the conversation WHERE id, store_id and user_id match, plus recent messages
    C->>C: Resolve provider. Skip the live provider during a cool-down after a 429
    alt Live provider, gemini or openai_compatible
        loop At most the configured number of tool iterations
            C->>P: Prompt, history, question, schemas of the tools this user may call
            P->>L: HTTPS request with timeout
            L-->>P: Tool request, name and arguments
            P-->>C: Tool call
            C->>T: Execute with store_id and principal from the session, never from the model
            T->>T: Allowlisted name, Pydantic arguments, permission check
            T->>S: Store-scoped read through the owning service
            S->>D: SELECT with store_id predicate
            T-->>C: JSON result capped at 50 rows, tool call recorded
            C->>D: End the read transaction before the next LLM call
        end
        L-->>P: Final structured answer
        P-->>C: Answer
        C->>C: Validate the answer schema. Every reference must appear in this turn's tool results
        opt 429, timeout, provider outage, or invalid answer
            C->>C: Fall back to the deterministic provider and add a visible limitation notice
        end
    else Deterministic, no key or fallback
        C->>C: Route intent from the question
        C->>T: Execute the mapped tools with the same checks
        C->>C: Fill a template with tool results, generated_by deterministic
    end
    C->>D: INSERT user message, assistant message with provider, model, latency and tokens, and ai_tool_call rows, one commit
    C-->>B: 200 structured answer with summary, facts, metrics, estimates, recommendations, limitations, references
```

Notes:

- **Investigation summaries** (`POST .../copilot/exception-summaries`) first look up a cached
  assistant message by `cache_key` (store, exception id, exception `version`, permission-set hash,
  provider, model, prompt version). A hit returns the stored answer, labelled as cached with its
  generation time, without calling the LLM. A material change to the exception bumps `version`, so a
  stale summary is never served.
- **Note drafts** (`POST .../copilot/note-drafts`) return text only. Saving it is a separate call by
  a person with `exceptions.work` to `POST .../exceptions/E/notes` with `source = AI_DRAFT_ACCEPTED`.
  A VIEWER or ANALYST can draft but cannot save.
- **What leaves the platform.** With a live provider, the question, recent history, tool schemas and
  tool results are sent to the provider over HTTPS. They contain SKUs, product names, order numbers,
  amounts and opaque `customer_ref` values, never customer personal data (BR-505), credentials or
  session data.
