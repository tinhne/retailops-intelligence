# PROJECT_STATE

> Canonical current state. Update after every meaningful milestone. Verified facts only.

| Field | Value |
|---|---|
| Project | RetailOps Intelligence: E-commerce Operations & Decision Intelligence Platform |
| Owner | Lê Văn Trung Tính (GitHub `tinhne`) |
| Current milestone | **M8 quality and M10 release docs done locally (T-081, T-083, T-100).** Remaining: deployment and the public demo (T-093/T-094), which wait on the owner's hosting choice |
| Current phase | v1.0 feature-complete and verified locally, end to end; deployment remains |
| Overall completion | All P0/P1 product tasks are implemented and tested except T-093/T-094 deployment (blocked on hosting choice). T-095 (P2) not started |
| Last verified commit | `ea205ec` (pushed 2026-11-01): GitHub Actions run 41277118318 green on all 5 jobs incl. the first E2E job; locally backend 865, web 265, Playwright 19/19, copilot eval 65/65 |
| Remote | https://github.com/tinhne/retailops-intelligence (public). The first CI run passed |
| Architecture version | v1 (modular monolith; `docs/domain/*`, ADR-0001..0013) |
| Last update | 2026-11-01 (UTC+7) |

## Implemented (verified)

- **Docs:** product discovery, workflows, domain contracts, architecture, ADRs, design system and
  screens, AI architecture, test strategy. Tags `discovery-complete`, `workflow-v1`, `architecture-v1`.
- **Identity and security:** argon2id, server-side sessions, session-bound CSRF, role matrix
  (`GET /api/v1/roles`), cross-tenant 404, rate limits, audit log (no IP addresses exposed), demo viewer login.
- **Data model:** migrations 0001–0002 (all modules). `alembic check` shows no drift.
- **Orders and inventory:** order FSM (three axes, reachability), ledger with count-as-of semantics,
  reservations, shipment cutoff, reconciliation.
- **Imports:** 4 CSV types, preview, atomic apply (strict or valid-rows-only), idempotency, issue CSV, templates.
- **Exceptions:** 9 deterministic rules, reconciliation (dedup, refresh, auto-resolve, verify with
  grace, reopen, recurrence, supersede), priority and due dates, lifecycle API, evaluations API.
- **Read side:** products, orders, inventory positions and movements, dashboard, trends, exception
  breakdown, store settings, members.
- **Worker:** `python -m app.workers.scheduler` evaluates each store on its interval under the
  engine's advisory lock (T-055). Not yet in the compose stack.
- **Demo dataset:** `make seed` generates the fictional "Kestrel Home & Kitchen" store (114 products,
  1,549 orders, 8 suppliers, 60 days). The engine produces 18 exceptions across all 9 types.
- **Contracts:** OpenAPI → TypeScript. Identity schemas expose the `Role` and `Permission` enums.
- **Web foundation (T-060):** tokens and Tailwind theme, restyled shadcn/ui primitives, API client
  (CSRF header, `ApiError`), QueryClient policy (retries; 401 → sign-in), `/api` rewrite to FastAPI,
  `proxy.ts` optimistic sign-in redirect, S-01 sign-in and `/demo`, session gate, store resolution,
  app shell (demo banner, sidebar with rail and drawer, account menu, offline notice).
- **Overview (T-061):** S-02 with freshness strip, six KPIs, Needs attention, value at risk per
  category (never totalled, BR-404), stock health, shipments chart with a table view, recent imports,
  and Run analysis (idempotent, gated for the demo). Dashboard API gained `exposure_by_category`.
  Links stay plain text until their target pages exist.
- **Exceptions (T-062):** S-03 inbox (views, URL-state filters, search, sort, pagination, stacked
  mobile rows) and S-04 investigation (priority breakdown, calculation, evidence, affected orders,
  lifecycle banner, activity with notes). Every lifecycle command from the UI, laid out from the API's
  `available_actions`/`blocked_actions`, with stale-version handling. API gained a `due_to` filter and
  closing fields on list items.
- **Orders (T-063):** S-05 list (filters incl. store-local placed presets and overdue) and S-06 detail
  (three status axes with callouts, dates, lines with reservation and stock health, totals with the
  BR-205 mismatch, linked exceptions, history). Read-only, as orders change through imports.
- **Products and inventory (T-064):** S-07 products, S-08 product detail (stock arithmetic, data-issue
  callout, exceptions, recent ledger), S-09 positions with the health summary bar, S-10 movements
  ledger. List URL state now comes from declarative field specs (`lib/list-params.ts`).
- **Imports (T-065):** S-11 history, S-12 upload, preview and apply (strict or valid-rows-only with
  consent, Idempotency-Key), S-13 record views for every terminal status, template and issues CSV
  downloads, and import actions in the other screens' empty states.
- **Stock health data issue (T-058):** `DATA_ISSUE` health class for `on_hand < 0` (any status) and a
  dashboard `data_issue` count; Oversold no longer includes them (BR-402a).
- **Admin (T-066):** organization member API (list, add with a one-time temporary password, role
  change, deactivate/reactivate with last-owner and cross-organization guards), users and roles,
  store settings with validation, filterable audit log with actor names.
- **UI follow-ups (T-067):** exceptions mobile action bar, filter sheet, queue Previous/Next, jump
  menu, density, viewer lifecycle explainer, evidence links; orders custom range and import links;
  ledger product search, custom range, import column, exact order links; imports upload progress,
  multi-status filter, issue row search, Validate again (`POST …/revalidate`), new-exceptions link.
- **AI copilot (T-071..T-074):** migration `0003_ai_copilot`; 11 read-only tools; providers
  `gemini`, `openai_compatible`, `deterministic` with automatic fallback, budgets and a summary
  cache; copilot API (conversations, questions, exception summaries, note drafts); web S-14 page,
  AI investigation panel and "Draft with copilot" (saved only by a person, as `AI_DRAFT_ACCEPTED`);
  `make ai-eval` (deterministic run 65/65).
- **Ops, demo and security (T-056, T-082, T-090, T-094 part):** compose `db`, `api` (migrations on
  start), `worker` (heartbeat), `web` (standalone), `demo-seed`; demo history and imports in the
  seed; `make stack-demo-reset`; pre-session CSRF on sign-in, body and CSV limits, security
  headers; `SECURITY.md`.
- **Delivery:** API Dockerfile (non-root, builds), CI workflow (passed on GitHub), OpenAPI → TS contracts.

## In progress / next

| Task | Notes |
|---|---|
| Manual test pass | Done 2026-11-01 as demo viewer, owner and manager on seeded local data; no open findings |
| T-081 Playwright E2E | DONE 2026-11-01. 19 tests incl. setup pass against the Compose stack, locally and in CI (run 41277118318) |
| T-083 Accessibility review | DONE 2026-11-01. axe WCAG 2.1 A/AA on 11 screens: 3 serious findings and 1 moderate fixed, 0 remaining; keyboard and 375 px in E2E |
| T-100 README and release | DONE 2026-11-01. README with real screenshots, demo guide, release notes v1.0.0 |
| Push | Pushed 2026-11-01 at ea205ec with the owner's approval; CI green |

## Blocked

| Task | Blocker | Needed from owner |
|---|---|---|
| T-093 Deployment | No hosting provider or credentials | Choose a provider (free tier preferred) |

## Known bugs / limitations

- The evaluation engine uses a transaction-scoped advisory lock under READ COMMITTED with row locks.
  SYSTEM_ARCHITECTURE §8–9 describes REPEATABLE READ plus retry (documented deviation, acceptable at MVP scale).
- Evaluation and import idempotency keys are stored in audit details or import summary JSON (no dedicated column yet).
- Import validation and apply run row by row. A 20,000-row performance check has not been run.
- The demo banner and `/demo` page omit the spec's "periodically reset" wording until the reset job exists (T-094).
- Locally, the seeded staff accounts (`make seed` with `DEMO_STAFF_PASSWORD`) belong to the demo
  organization, so the banner says "read-only" even for the manager, who can run imports. Deployed,
  only the demo viewer can sign in there.
- Behind the Next.js proxy the API sees the proxy's IP. `TRUST_PROXY_HEADERS=true` is safe only behind
  an edge proxy that appends the client address (the Next.js rewrite forwards the browser's header
  unchanged), so the demo sign-in limiter is shared by all visitors until then (SECURITY.md §5, F5, F9).
- Seeded audit entries carry the seed's run time, while exception events and imports are backdated
  over the scripted five hours, so the audit log and the exception timeline disagree on times.
- Copilot exception references use the label "EXC-1042 · title"; the UI shortens chips to the code.
- Open security items (SECURITY.md §6): nonce-based script CSP, `statement_timeout`, per-IP sign-in
  budget across emails, image digests, compose smoke test in CI.
- Admin: no forced password change after a temporary password, no password reset; settings have
  no version (last write wins inside a short window).
- Locally, port 3000 may be taken by another project; the preview then runs the web app on 3001.

## Latest test results

- GitHub Actions run 41277118318 on ea205ec: **success** on all 5 jobs (API, web, dependency audit, Docker images, E2E Playwright against the Compose stack; the Playwright step ran 43 s).
- Resume baseline (2026-11-01, `main` at 44cd6b0): `make check` **865 passed**; web lint, typecheck, vitest **265 passed**.
- Playwright (2026-11-01, `pnpm --filter @retailops/web e2e` against an isolated Compose stack): **19 passed**
  (setup, 12-step journey, public demo ×2, axe ×3, 375 px). Web vitest after the a11y fixes: 265 passed.
- `make ai-eval` deterministic on `main` (bd5c8dd): **65/65**, gates PASS (`apps/api/evals/reports/2026-11-01_deterministic_bd5c8dd.md`).
- `make check` (2026-11-01, merged tree of all five branches): ruff OK, ruff format OK, mypy --strict OK, pytest **865 passed**.
- Web (2026-11-01, at 3c5bf45): `pnpm --filter @retailops/web lint`, `typecheck`, `build` green; vitest **265 passed**.
- `make ai-eval` deterministic (run by the AI branch against its own database): 65/65 cases, gates PASS. No live-LLM run (no key).
  `pnpm audit --prod --audit-level high`: no known vulnerabilities.
- Browser check against the seeded local API: password and demo sign-in, `next` redirect, invalid
  credentials, session expiry, sign-out, unknown store, and the 375, 768 and 1280 px layouts.
  Overview as demo viewer and as manager (Run analysis), at 1440 and 375 px. Exceptions: acknowledge,
  start, resolve, Closed view and reopen as manager; read-only demo viewer; 1440 and 375 px. Orders:
  overdue filter, search, cancelled-but-paid and total-mismatch orders, 375 px with no sideways scroll.
  Products and inventory: product list, the data-issue product KHK-BW-003, positions (health toggles,
  include inactive), the ledger filtered from a product; 1440 and 375 px with no sideways page scroll.
  Imports as manager: upload, preview, strict block, valid-rows-only apply of a no-change test file,
  duplicate-file warning, discard, rejected file; as the demo viewer; 1440 and 375 px.
- GitHub Actions run 41271652506 (all merged work, the copilot UI and the test pass, on 9a1e033):
  success. API, web, dependency audit and Docker image jobs all passed.

## Owner decisions log

- 2026-10-31: The AI copilot uses **free-tier LLM APIs only** (Gemini by default, OpenAI-compatible
  free tiers as an alternative) with a deterministic fallback.
- 2026-11-01: The owner created the GitHub repository. Pushes go over SSH.
- 2026-11-01: Commits credit the owner only, with no tool co-author lines. The owner approved a one-time
  history rewrite to remove them from the 39 earlier commits (force-push of `main` and the 3 tags);
  code was unchanged. AGENTS.md's no-rewrite rule otherwise stands.

## Next three highest-priority actions

1. T-093/T-094: once the owner picks a free host, the deploy pipeline, the public demo and its reset schedule.
2. Open items in `SECURITY.md` §6 and the P1/P2 backlog (e.g. T-095 per-visitor sandbox).
3. Optional: a live free-tier Gemini evaluation (`make ai-eval PROVIDER=gemini`) once the owner provides a key.
