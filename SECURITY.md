# Security

RetailOps Intelligence is an independent portfolio project. It has no production deployment and no
real customer data; the public demo uses a fictional store. This file summarises the threat model,
the controls that exist in the code (with the tests that verify them), the limitations, and what a
deployment must get right. The full design is in
[`docs/architecture/SECURITY_ARCHITECTURE.md`](docs/architecture/SECURITY_ARCHITECTURE.md).

Last review: 2026-11-01 (task T-082).

## 1. Reporting a vulnerability

Please report suspected vulnerabilities privately to the owner, Lê Văn Trung Tính
([GitHub @tinhne](https://github.com/tinhne)), rather than in a public issue. Include the affected
endpoint or file, the steps to reproduce, and the impact you expect. There is no bug bounty.

## 2. Threat model in brief

| What we protect | Main threats | Primary controls |
|---|---|---|
| Tenant isolation (one organization never sees another's data) | Guessing ids (IDOR), missing filters | Store scoping on every route (404 for foreign stores), store-scoped repositories, cross-tenant tests |
| Integrity of orders, the stock ledger, exception history and the audit log | Forged requests, over-posting, privilege escalation | Server-side permission matrix, CSRF tokens, validated state transitions, append-only tables |
| Credentials and sessions | Brute force, session theft, login CSRF | argon2id, opaque hashed session tokens in `HttpOnly` cookies, sign-in rate limits, double-submit CSRF before and after sign-in |
| Availability of a small single-instance deployment | Oversized uploads, request floods, pathological CSV files | Request body cap, CSV limits, rate limits, pagination caps |
| The shared public demo | Vandalism, confusing the next visitor | Read-only viewer role, a scheduled reset job |
| Store data sent to an LLM provider | Data leaving the platform, prompt injection | No write tools for the AI, allowlisted tools, deterministic fallback (ADR-0010) |

Trust boundaries: browser → `web` (Next.js, no secrets, not a security component) → `api` (FastAPI:
authentication, authorization, tenancy) → PostgreSQL. CSV content and LLM output are untrusted data.

## 3. Controls and how they are verified

| Control | Implementation | Verified by |
|---|---|---|
| Password hashing | argon2id (`identity/security.py`); equal timing for unknown emails | `tests/unit/test_security_primitives.py` |
| Sessions | 256-bit opaque token in `ro_session` (`HttpOnly`, `SameSite=Lax`, `Secure` when `COOKIE_SECURE=true`); only its SHA-256 is stored; 12 h idle and 7 day absolute expiry; logout revokes | `tests/integration/test_auth_and_access.py` |
| CSRF after sign-in | Every POST, PUT, PATCH and DELETE needs `X-CSRF-Token` equal to `HMAC(SESSION_SECRET, session)` | `test_mutating_request_without_csrf_header_is_rejected` |
| CSRF before sign-in (login CSRF) | `GET /api/v1/auth/csrf` sets a random `ro_csrf` cookie and returns it; `POST /auth/login` and `POST /auth/demo` require the header to equal the cookie. The web sign-in fetches a fresh token per attempt | `test_sign_in_requires_the_pre_session_csrf_token`, `login-screen.test.tsx` |
| Authorization | Code-defined role matrix (ADR-0007); `require_permission` on every store route; actor rules in the exception lifecycle | `tests/unit/test_permissions.py`, `tests/unit/test_exception_lifecycle.py`, route tests |
| Tenancy | `store_context` resolves membership; other tenants get 404; natural keys unique per store | cross-tenant tests in every `tests/integration/test_api_*.py` |
| Read-only public demo | "Explore the demo" signs in the demo VIEWER only; every mutating route answers 403 to it | `tests/integration/test_demo_read_only.py` walks every mutating OpenAPI operation against the real demo build and checks that no shared row changed |
| Rate limits | Sign-in 5 per minute per IP and email; demo sign-in 5 per minute per IP; 300 requests per minute per signed-in user; refused sign-ins (bad CSRF) do not count | `test_login_is_rate_limited_per_ip_and_email`, `test_rejected_sign_ins_do_not_consume_the_rate_limit` |
| Request size | Bodies above 6 MB (5 MB file plus multipart overhead) get 413 `PAYLOAD_TOO_LARGE` before parsing; a chunked body is cut off at the limit | `tests/unit/test_app_basics.py`; through the Next.js proxy in the compose stack |
| CSV uploads | `imports.run` and CSRF required; `.csv` only; strict UTF-8; at most 5 MB (larger files are recorded as `REJECTED`), 20,000 rows and 100 columns; parsed by the `csv` module and never evaluated; bytes kept only in PostgreSQL until apply, discard or 24 h expiry; filenames are metadata only | `tests/unit/test_import_parsing.py`, `tests/integration/test_imports_*.py` |
| CSV formula injection | Exported issue cells starting with `=`, `+`, `-`, `@`, tab or CR are prefixed with `'` | import export tests |
| Error handling | Standard error envelope with `request_id`; no stack traces or SQL in responses | `tests/unit/test_app_basics.py` |
| API response headers | `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` | `test_api_responses_carry_security_headers` |
| Web response headers | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, CSP `frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'` | checked on the compose stack (RUNBOOK §8) |
| Secrets and configuration | Environment variables only; `.env` is gitignored; `APP_ENV=production` refuses the development secret, any `SESSION_SECRET` shorter than 32 characters and `COOKIE_SECURE=false` | `test_production_requires_secret_and_secure_cookies` |
| Demo accounts | Seeded staff accounts get random passwords unless `DEMO_STAFF_PASSWORD` is set; the seed command refuses that variable when `APP_ENV=production`; the reset refuses to delete an organization that is not flagged as demo | `tests/integration/test_demo_seed.py` |
| Containers | Multi-stage images, non-root users (`app`, `node`), health checks, api and web published on 127.0.0.1 only in compose | RUNBOOK §8 |
| Supply chain | Committed lockfiles; CI runs `pip-audit` and `pnpm audit --prod` | `.github/workflows/ci.yml` |

## 4. Deployment checklist

1. Terminate TLS at the edge and send HSTS. Set `APP_ENV=production`, `COOKIE_SECURE=true` and a
   random `SESSION_SECRET` of at least 32 characters (`openssl rand -hex 32`).
2. Expose only the `web` origin. The `api` must be reachable from `web` alone (private network).
3. Decide `TRUST_PROXY_HEADERS` with §5.
4. Leave `DEMO_STAFF_PASSWORD` unset. Schedule the demo reset ([`docs/operations/DEMO_RESET.md`](docs/operations/DEMO_RESET.md)).
5. Use a database role that owns the schema for migrations and, ideally, a non-owner role for the
   application.
6. Configure LLM keys only in the `api` environment, and only after checking the provider's
   free-tier data terms (ADR-0010).

## 5. Client addresses behind the Next.js proxy (`TRUST_PROXY_HEADERS`)

The API uses the client address for sign-in rate limits and for audit rows. Behind the `web`
container, the TCP peer is always `web`. `TRUST_PROXY_HEADERS=true` makes the API use the right-most
entry of `X-Forwarded-For` instead.

**What the Next.js rewrite proxy does (verified on the compose stack, Next.js 16.4):** it forwards
the browser's `X-Forwarded-For` header unchanged and does **not** append the address it received
the request from. So:

| Deployment | Setting | Result |
|---|---|---|
| `web` faces the internet directly (no edge proxy), or the local compose stack | `false` (default) | Every request appears to come from the `web` container. Sign-in limits per IP become limits shared by all users of that `web` instance (the demo sign-in limit becomes 5 per minute in total). Safe, but coarse |
| Same, with `true` | **never** | Any client chooses its own address by sending `X-Forwarded-For`: it can bypass the per-IP sign-in limits and write arbitrary addresses into the audit log. Verified: a request with `X-Forwarded-For: 203.0.113.77` was audited with that address |
| An edge proxy or platform router in front of `web` that **appends** the client address to `X-Forwarded-For` (most load balancers and PaaS routers do), and `api` is not reachable from outside | `true` | The right-most entry is the address the edge saw: correct per-client limits and audit addresses |

Check the edge's documentation before enabling it: an edge that passes the client's header through
without appending puts the deployment back in the "never" row. The API image runs uvicorn with
`--no-proxy-headers`, so this setting is the only switch.

## 6. Review findings (T-082, 2026-11-01)

| ID | Finding | Severity | Status |
|---|---|---|---|
| F1 | ADR-0004 describes a pre-login `GET /auth/csrf`, but it did not exist and `POST /auth/login` and `POST /auth/demo` had no CSRF check. Login CSRF was blocked only because the endpoints accept JSON alone | Medium | **Fixed**: endpoint, check on both sign-in routes, web sign-in uses it, tests |
| F2 | An `X-CSRF-Token` header with non-ASCII characters raised `TypeError` in `hmac.compare_digest`, answered as 500 | Low | **Fixed**: byte comparison, tests |
| F3 | No request body limit. Starlette spools multipart files above 1 MB to a temporary file, so a holder of `imports.run` could send an arbitrarily large upload (disk and CPU) before the 5 MB check ran | Medium | **Fixed**: 6 MB body cap with 413, streamed check for chunked bodies, tests; verified through the proxy |
| F4 | CSV header checks were quadratic in the number of columns (a 20,000-column header took 7 s; a 5 MB header of about 700,000 names would take hours) and created one warning row per unknown column | Medium | **Fixed**: 100-column cap (`TOO_MANY_COLUMNS`) and a linear duplicate check, test |
| F5 | With `TRUST_PROXY_HEADERS=true`, clients behind the Next.js proxy can spoof their address (§5). The architecture documents referred to `FORWARDED_ALLOW_IPS`, which the code never had | Medium (configuration) | **Documented** (§5, ADR-0004 amendment); compose keeps it `false`; uvicorn proxy headers disabled |
| F6 | Production accepted placeholder secrets such as `change-me` | Medium (configuration) | **Fixed**: at least 32 characters required, test |
| F7 | The demo seed could purge a non-demo organization that used the demo slug, and `DEMO_STAFF_PASSWORD` worked in production | Low | **Fixed**: both refused, tests |
| F8 | No security headers on API responses or web pages | Low | **Fixed** (baseline set above). A nonce-based script CSP is still open |
| F9 | Demo sign-in shares the sign-in limiter (5 per minute per IP; the design proposed 10) and, without a trusted edge, the limit is global | Low (availability) | **Documented**; tune with the deployment (T-093) |
| F10 | Sign-in is limited per IP *and email*, so one address can try one password against many accounts (password spraying) | Low | **Documented** (limitation L3) |
| F11 | Audit rows store IP addresses and user agents; demo viewers hold `audit.read` | n/a | **Verified**: the audit API never returns `ip` or `user_agent` |
| F12 | `SECURITY_ARCHITECTURE.md` listed a database `statement_timeout`, which is not configured | Low | **Documented** as not implemented |

## 7. Known limitations

| ID | Limitation | Consequence | Path forward |
|---|---|---|---|
| L1 | No MFA, no SSO, no self-service password reset | A stolen password is enough | TOTP MFA |
| L2 | Rate limits live in process memory | They multiply with instances and reset on restart | A shared store when scaling out |
| L3 | No per-IP limit across emails, no account lockout (deliberate) | Password spraying from one address is only slowed per account | Per-IP sign-in budget once client addresses are trustworthy (§5) |
| L4 | Tenancy and append-only rules are enforced by application code and tests, not by the database | A missed filter would be a real bug; a database administrator can alter history | Row-level security; `REVOKE UPDATE, DELETE` for the application role |
| L5 | No script CSP with nonces | XSS defence relies on React's escaping and the absence of raw HTML rendering | Nonce-based CSP in the web app |
| L6 | No statement timeout or WAF | A slow query or a flood is limited only by the host | `statement_timeout` per role; platform protections (T-093) |
| L7 | Shared public demo | Visitors see the same data and cannot try lifecycle actions | Per-visitor sandbox (T-095) |
| L8 | LLM output can be wrong or influenced by imported text | Labelled and validated, not eliminated | Evaluation set with injection cases (T-074) |
