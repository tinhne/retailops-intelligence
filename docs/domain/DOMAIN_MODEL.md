# Domain Model

> **Status:** Canonical (v1). The SQLAlchemy models in `apps/api/app/domains/*/models.py` implement
> this document. The ER diagram is in `ENTITY_RELATIONSHIPS.md`.

## 1. Bounded contexts (modules)

The backend is a modular monolith (ADR-0001). Each module owns its tables, and only that module's
code writes to them. Other modules read through the module's service interface, never by importing
its models directly. The exceptions to that rule are read-only analytics queries, which are listed
in `docs/architecture/SYSTEM_ARCHITECTURE.md`.

| Module | Owns | Responsibility |
|---|---|---|
| `identity` | organization, store, store_settings, app_user, membership, user_session | Authentication, tenancy, roles, permissions |
| `catalog` | supplier, product | Product master data |
| `orders` | sales_order, order_item, order_event | Order lifecycle and status axes |
| `inventory` | inventory_balance, inventory_movement, stock_reservation | Stock ledger, reservations, health |
| `imports` | data_import, import_row_issue | CSV ingestion pipeline |
| `exceptions` | evaluation_run, operational_exception, exception_entity_link, exception_event, exception_assignment, exception_note | Rule engine, deduplication, lifecycle |
| `audit` | audit_log | Immutable record of security-relevant and business-changing actions |
| `ai` | ai_conversation, ai_message, ai_tool_call | Copilot conversations and tool execution metadata |
| `analytics` | *(no tables)* | Read-only aggregate queries over the other modules |

## 2. Entities

Conventions: every table has a UUID primary key `id` (except where noted), `created_at`, and
`updated_at` (UTC). Store-scoped tables have a non-null `store_id`, indexed and included in every
query (BR-003).

### identity

| Entity | Key fields | Notes |
|---|---|---|
| **Organization** | name, slug (unique), is_demo | Tenant boundary |
| **Store** | organization_id, name, code, currency (ISO-4217), timezone (IANA) | Unit of data isolation (BR-001) |
| **StoreSettings** | store_id (PK), fulfillment_sla_hours, stall_threshold_hours, refund_overdue_hours, approaching_reorder_factor, velocity_window_days, reopen_window_hours, exposure_cap, priority_weights (JSONB), evaluation_interval_minutes | Defaults in `BUSINESS_RULES.md §7` |
| **User** (`app_user`) | email (unique, lower-cased), full_name, password_hash (argon2id), is_active, last_login_at | Never stores plaintext passwords |
| **Membership** | user_id, organization_id, role (`OWNER`, `MANAGER`, `STAFF`, `ANALYST`, `VIEWER`) | Unique (user, organization) |
| **UserSession** | user_id, token_hash (SHA-256 of the opaque token), expires_at, revoked_at, ip, user_agent | Server-side sessions allow revocation (ADR-0004) |

**Role and Permission are code, not tables.** Roles are a fixed enum, and the role → permission
matrix is a constant in `identity/permissions.py` (see `ROLE_AND_PERMISSION_WORKFLOW.md`). Custom
roles are a P3 roadmap item. Keeping the matrix in code means it is reviewed and tested like any
other code, and an administrator cannot widen access by editing database rows.

### catalog

| Entity | Key fields | Notes |
|---|---|---|
| **Supplier** | store_id, name (unique per store), lead_time_days, contact_ref | Supports lead-time-aware low-stock severity |
| **Product** | store_id, sku (unique per store), name, category, status (`ACTIVE`, `DRAFT`, `ARCHIVED`), unit_price, unit_cost, reorder_point, reorder_quantity, supplier_id | One row per sellable SKU |

### orders

| Entity | Key fields | Notes |
|---|---|---|
| **Order** (`sales_order`) | store_id, order_number (unique per store), channel, customer_ref, status, payment_status, fulfillment_status, placed_at, paid_at, ship_by, ship_by_source (`IMPORTED`/`STORE_SLA`), shipped_at, delivered_at, cancelled_at, currency, subtotal, discount_total, shipping_total, tax_total, total, carrier, tracking_number | Three status axes (`STATE_MACHINES.md §1`) |
| **OrderItem** | order_id, product_id, sku (as imported), line_number, quantity (>0), unit_price, line_discount | Unique (order, line_number) |
| **OrderEvent** | order_id, from_status, to_status, skipped_statuses, source (`IMPORT`, `USER`, `SYSTEM`), import_id, occurred_at | Immutable status history |

### inventory

| Entity | Key fields | Notes |
|---|---|---|
| **InventoryBalance** | store_id + product_id (PK), on_hand, reserved, incoming, incoming_eta, last_cycle_count_at, version | Cached projection (BR-104); `available` is computed |
| **InventoryMovement** | store_id, product_id, movement_type, on_hand_delta, incoming_delta, occurred_at, source, reference (unique per store when not null), import_id, note, created_by | Append-only ledger (BR-110) |
| **StockReservation** | store_id, product_id, order_item_id (unique), quantity, status (`ACTIVE`, `CONSUMED`, `RELEASED`), activated_at, closed_at | One per order line (BR-120..123) |

### imports

| Entity | Key fields | Notes |
|---|---|---|
| **DataImport** | store_id, import_type, status, mode (`STRICT`, `VALID_ROWS_ONLY`), original_filename, file_sha256, size_bytes, row_count, summary (JSONB: new/updated/unchanged/error/warning counts), validated_at, applied_at, expires_at, created_by, evaluation_run_id | File bytes are stored for the validation-to-apply window, then purged |
| **ImportRowIssue** | import_id, row_number, column, code, severity (`ERROR`, `WARNING`), message, raw_value | Covers both blocking errors and warnings. Downloadable as CSV |

### exceptions

| Entity | Key fields | Notes |
|---|---|---|
| **EvaluationRun** | store_id, trigger (`MANUAL`, `IMPORT`, `SCHEDULED`), as_of, rules (list), status (`RUNNING`, `SUCCEEDED`, `FAILED`, `SKIPPED`), started_at, finished_at, counts (JSONB: created/refreshed/resolved/reopened/superseded), triggered_by, error | Makes every detection observable |
| **OperationalException** | store_id, reference (human-friendly `EXC-1001`, from a per-store counter in `exception_sequence`), exception_type, category, rule_id, dedup_key, status, severity, priority_score, priority_band, priority_breakdown (JSONB), title, evidence (JSONB), calculation (JSONB), recommended_action, exposure_amount, affected_order_count, deadline_at, due_at, assignee_id, first_detected_at, last_detected_at, detection_count, resolved_at, resolved_by, resolution_code, resolution_note, verified_at, dismissed_reason, condition_cleared_at, superseded_by_id, previous_occurrence_id, reopen_count, version (optimistic concurrency) | A partial unique index on `(store_id, dedup_key)` where status is active ensures at most one active exception per condition |
| **ExceptionEntityLink** | exception_id, entity_type (`product`, `order`), entity_id, role (`PRIMARY`, `AFFECTED`) | Answers "which exceptions touch this order or product?" |
| **ExceptionEvent** | exception_id, event_type, actor_type (`USER`, `SYSTEM`), actor_id, evaluation_run_id, from_status, to_status, payload (JSONB), occurred_at | Immutable history. No update or delete path exists in code |
| **ExceptionAssignment** | exception_id, assignee_id, assigned_by, assigned_at, unassigned_at | Assignment history |
| **ExceptionNote** | exception_id, author_id, body (≤ 4000 chars), source (`USER`, `AI_DRAFT_ACCEPTED`) | Notes are append-only. An AI-drafted note is saved only after a person accepts it |

Event types: `DETECTED`, `EVIDENCE_UPDATED`, `SEVERITY_CHANGED`, `STATUS_CHANGED`, `ASSIGNED`,
`UNASSIGNED`, `NOTE_ADDED`, `DUE_DATE_CHANGED`, `AUTO_RESOLVED`, `VERIFIED`, `REOPENED`, `SUPERSEDED`.

### audit

| Entity | Key fields | Notes |
|---|---|---|
| **AuditLog** | organization_id, store_id (nullable), actor_user_id (nullable for system), action (e.g. `exception.resolve`, `import.apply`, `auth.login_failed`), target_type, target_id, metadata (JSONB, never secrets), ip, request_id, occurred_at | Append-only. Read requires `audit.read` |

### ai

| Entity | Key fields | Notes |
|---|---|---|
| **AIConversation** | store_id, user_id, title, context_type (`GENERAL`, `EXCEPTION`), context_id | |
| **AIMessage** | conversation_id, role (`user`, `assistant`), content (JSONB structured answer), provider, model, latency_ms, input_tokens, output_tokens | Structured answer separates facts, metrics, estimates, recommendations, and references |
| **AIToolCall** | message_id, tool_name, arguments (JSONB), status, result_summary, row_count, duration_ms, error | Execution metadata for every tool invocation |

## 3. Entities considered and excluded (v1)

| Entity | Decision | Rationale |
|---|---|---|
| **Payment** | Excluded. Order-level `payment_status` and `paid_at` instead | The source exports in scope provide one payment state per order. Partial captures, split tenders, and payment-processor reconciliation are roadmap items. Adding a Payment table now would introduce a 1:N relationship that no workflow uses yet |
| **Shipment** | Excluded. Order-level `fulfillment_status`, `shipped_at`, `delivered_at`, `carrier`, `tracking_number` instead | The MVP assumes one shipment per order. Split shipments need per-line fulfillment tracking (roadmap) |
| **ProductVariant** | Excluded. Product = SKU | Every operational rule in scope works at SKU level. Parent/variant grouping is a catalog-display concern |
| **InventoryLocation** | Excluded (ADR-0005) | Single fulfillment location per store. Multi-location allocation would change the oversell calculation substantially and needs real routing rules |
| **Role / Permission tables** | Excluded. Code-defined matrix | See identity above |
| **ExceptionEvidence table** | Excluded. Evidence is a versioned JSONB document on the exception, and previous versions are kept in `EVIDENCE_UPDATED` events | Evidence is always read and written as a whole snapshot, and every item carries its own source reference |
| **Customer** | Excluded. Opaque `customer_ref` only (BR-505) | Data minimisation. No workflow in scope needs personal data |
| **PurchaseOrder** | Excluded. `incoming` quantity via `INCOMING_EXPECTED` / `RECEIPT` movements | Enough for low-stock context. Supplier performance tracking is P3 |

## 4. Invariants enforced in code and covered by tests

1. `inventory_balance.on_hand = Σ movement.on_hand_delta` (per product).
2. `inventory_balance.reserved = Σ ACTIVE reservation.quantity` (per product).
3. Every order satisfies the axis compatibility matrix (`STATE_MACHINES.md §1.3`).
4. Every status change of an order or exception has a matching event row.
5. At most one active exception per `(store_id, dedup_key)` (partial unique index).
6. No query on store-scoped data runs without a `store_id` predicate (enforced by the repository
   base class, and covered by cross-tenant tests).
