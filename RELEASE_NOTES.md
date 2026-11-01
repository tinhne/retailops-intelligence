# Release notes

Releases follow semantic versioning. Each entry lists features, fixes, breaking changes, known
limitations, and the deployment version.

## v1.0.0 — 2026-11-01

The first complete release: every v1 screen, the rule engine, the import pipeline, the AI copilot
and the container stack, built from the documented specifications and verified by automated and
manual tests. It runs locally; there is no hosted deployment yet.

### Operations

- Overview with KPIs, the attention list by priority, value at risk per category (never totalled),
  stock health including a separate data-issue count, on-time shipments, recent imports and
  on-demand analysis.
- Exceptions inbox (views, filters, search, density, mobile filter sheet) and investigation page
  (priority breakdown, calculation, evidence with source links, affected orders, lifecycle with
  verification and reopen, assignments, due dates, notes, queue navigation).
- Nine deterministic, versioned rules across inventory, fulfillment, payment and data quality, with
  deduplication, transparent 0–100 priority and verified manual resolutions.
- Orders with three status axes, totals checks, linked exceptions and import-linked history.
- Products, inventory positions and the append-only movement ledger with reservations and
  as-of cycle counts.

### Data

- Four CSV contracts with templates; upload with progress; row-level validation with fix hints;
  preview of expected changes; strict or valid-rows-only apply with explicit consent; issues CSV;
  duplicate-file detection; Validate again after an interrupted apply; analysis after each import.

### AI copilot

- Plain-language questions answered in labelled sections with references to records, always with
  limitations and provenance (engine, data window, read-only tools used).
- On-demand exception investigation and note drafts that a person reviews and saves.
- Free-tier providers only (Gemini, OpenAI-compatible) with an automatic deterministic fallback; the
  product works with no key. Evaluation runner (`make ai-eval`).

### Administration and security

- Members and roles (add with a one-time temporary password, change role, deactivate with
  last-owner protection), store settings with validation, filterable audit log.
- Server-side sessions, session-bound and pre-session CSRF, permission checks on every request,
  tenant isolation, rate limits, request and upload limits, security headers, read-only public demo.
  See `SECURITY.md`.

### Delivery

- Docker Compose stack (database, API with migrations on start, scheduled worker, web, demo seed)
  with health checks and non-root images; demo reset command; GitHub Actions CI.
- Playwright end-to-end suite run in CI against the Compose stack: the 12-step operations journey,
  the read-only public demo, a 375 px pass, and axe-core WCAG 2.1 A/AA scans of 11 screens.

### Fixes made while hardening for release

- Stock health classifies negative on-hand as a data issue instead of counting it as oversold.
- Sign-in now requires a pre-session CSRF token; a malformed CSRF header no longer causes a 500.
- Request bodies and CSV headers are size-limited; a quadratic CSV header check was made linear.
- The apply step reports the API's actual error codes and refetches the import after a conflict.
- Copilot reference chips can no longer widen narrow layouts.
- Accessibility (found by the axe scans): the sign-in footer link is underlined instead of
  colour-only, the account menu's name no longer conflicts with its visible initials, and detail
  pages no longer have two landmarks named "Breadcrumb".

### Breaking changes

None (first release).

### Known limitations

- No hosted deployment or scheduled public demo reset yet (waiting on a hosting choice).
- No forced password change after a temporary password and no password reset flow.
- Store settings have no version; concurrent edits are last-write-wins within a short window.
- Open security hardening items are listed in `SECURITY.md` §6.
- The live LLM providers are implemented and tested against mocked HTTP; no live-provider evaluation
  has been run.

### Deployment version

Not deployed. Container images are built locally and in CI (`docker compose up --build`).

## Documentation milestones (before v1.0.0)

- Product discovery, business workflow, domain, architecture and design documentation (M0–M3),
  tagged `discovery-complete`, `workflow-v1` and `architecture-v1`.
- Canonical domain contracts: state machines, business rules, exception catalog, priority model.
