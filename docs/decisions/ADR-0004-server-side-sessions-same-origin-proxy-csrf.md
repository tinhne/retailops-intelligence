# ADR-0004: Server-side opaque sessions, same-origin API proxy, CSRF double-submit

| Field | Value |
|---|---|
| Decision ID | ADR-0004 |
| Title | Server-side opaque sessions, same-origin API proxy, CSRF double-submit |
| Date | 2026-10-31 |
| Status | Accepted |

## Context

The web app (Next.js) and the API (FastAPI) are separate servers. Users sign in with email and
password. Requirements:

- Sessions must be revocable immediately (logout, deactivation, password change).
- A successful XSS should not be able to steal a long-lived credential.
- Cookies must stay first-party: browsers increasingly restrict third-party cookies.
- Cross-site request forgery must be prevented.
- The setup must stay simple enough to test end to end.

## Alternatives considered

### A. JWT access token in browser storage, sent as a bearer header

- **Pros:** stateless; immune to CSRF.
- **Cons:** any XSS can read and exfiltrate the token; revocation needs a denylist (state again) or
  short lifetimes plus refresh-token machinery.

### B. Stateless signed token (JWT) in an `HttpOnly` cookie

- **Pros:** no database lookup per request.
- **Cons:** revocation is still hard; CSRF protection is still required; key rotation and token size
  to manage. Saves one indexed lookup the database handles easily.

### C. API on its own origin, CORS with credentials, `SameSite=None` cookies

- **Pros:** API and web deploy independently on different hosts.
- **Cons:** third-party cookie restrictions break sessions in some browsers; CORS misconfiguration is
  a common vulnerability; a wider CSRF surface.

### D. Hosted identity provider

- **Pros:** MFA and SSO without building them.
- **Cons:** an external dependency and possible cost outside the agreed stack; the public demo flow
  becomes more complex.

## Decision

- **Passwords:** argon2id.
- **Sessions:** an opaque 256-bit random token in cookie `ro_session` (`HttpOnly`, `Secure` in
  production, `SameSite=Lax`, host-only). The server stores only its SHA-256 hash in `user_session`.
  Lifetime 12 h sliding and 7 days absolute. Revocation sets `revoked_at`.
- **Same origin:** the browser talks only to the Next.js origin; Next.js rewrites `/api/*` to
  FastAPI. No CORS policy exists.
- **CSRF:** double-submit. A readable `ro_csrf` cookie and an `X-CSRF-Token` header must match on
  POST, PUT, PATCH and DELETE. Before login the token is random (from `GET /auth/csrf`, which also
  protects the login form); after login it is `HMAC(SECRET_KEY, session id)` so a token injected from a
  sibling subdomain cannot be used with another session.
- **Authorization** is always decided by the API (`require_permission` and store scoping). The
  Next.js server is not a security component.

## Consequences

### Positive

- Logout, deactivation and password change take effect on the next request.
- JavaScript cannot read the session token, and a database leak exposes only hashes of
  high-entropy tokens.
- No CORS configuration to get wrong; cookies are first-party.
- Easy to test: the API sees ordinary cookie-authenticated requests.

### Negative

- One indexed database lookup per request (cheap at target scale; a cache is possible later).
- `web` and `api` must stay behind one public origin.
- The proxy hop must forward the client IP correctly (`FORWARDED_ALLOW_IPS`) and pass 5 MB uploads
  (**Needs validation** in T-060). *Resolved by Amendment 1: the setting is `TRUST_PROXY_HEADERS`,
  and uploads were validated.*
- The frontend fetch wrapper must send the CSRF header on every unsafe request.
- An XSS can still act as the user while the page is open; the cookie protects the token, not its
  use. CSP and React's escaping are the mitigation.
- No MFA or SSO in v1.

## Amendment 1 (2026-11-01, security review T-082)

The decision stands. The review closed three gaps between this record and the code.

1. **Pre-login CSRF token implemented as decided.** `GET /api/v1/auth/csrf` did not exist, and
   `POST /auth/login` and `POST /auth/demo` had no CSRF check (they were protected only because
   they accept JSON bodies alone, which a cross-site form cannot send without a preflight). The
   endpoint now sets a random `ro_csrf` cookie and returns the same value; both sign-in endpoints
   require `X-CSRF-Token` to equal the cookie, and the web sign-in fetches a fresh token before
   every attempt. When a live session calls the endpoint, it returns the session-bound token
   instead, so a stray call never invalidates a signed-in tab. Implementing it was small and keeps
   one rule for every state-changing request, so amending the record to drop the token was not
   chosen.
2. **Client address: `TRUST_PROXY_HEADERS`, not `FORWARDED_ALLOW_IPS`.** The code has a boolean
   `TRUST_PROXY_HEADERS`: when true, the API uses the right-most `X-Forwarded-For` entry. Testing the
   compose stack showed that the Next.js rewrite proxy forwards the browser's `X-Forwarded-For`
   unchanged and appends nothing. A list of trusted peers (uvicorn's `FORWARDED_ALLOW_IPS`) would not
   help: the peer is always the `web` container, which never adds the client address. So the setting
   stays `false` when `web` faces the internet directly (every request then shares the `web`
   address), and is `true` only behind an edge proxy that appends the client address, with the API
   unreachable from outside. The API image runs uvicorn with `--no-proxy-headers` so that this is the
   only switch. A custom Next.js server that appends the header was rejected: it replaces the
   standalone server for a problem the hosting edge already solves. Details: `SECURITY.md` §5.
3. **5 MB uploads through the proxy validated.** On the compose stack a 5.1 MB CSV reached the API
   and was recorded as `REJECTED` (`FILE_TOO_LARGE`); a 7 MB request was refused by the API's new
   6 MB body limit with 413.

## Related documents

- [`SECURITY.md`](../../SECURITY.md) §3, §5, §6
- [`SECURITY_ARCHITECTURE.md`](../architecture/SECURITY_ARCHITECTURE.md) §5
- [`DATA_FLOW.md`](../architecture/DATA_FLOW.md) flow 1
- [`API_CONVENTIONS.md`](../architecture/API_CONVENTIONS.md) §3
- ADR-0007, ADR-0011
