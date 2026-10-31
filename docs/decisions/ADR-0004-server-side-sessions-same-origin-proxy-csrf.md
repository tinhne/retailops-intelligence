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
  (**Needs validation** in T-060).
- The frontend fetch wrapper must send the CSRF header on every unsafe request.
- An XSS can still act as the user while the page is open; the cookie protects the token, not its
  use. CSP and React's escaping are the mitigation.
- No MFA or SSO in v1.

## Related documents

- [`SECURITY_ARCHITECTURE.md`](../architecture/SECURITY_ARCHITECTURE.md) §5
- [`DATA_FLOW.md`](../architecture/DATA_FLOW.md) flow 1
- [`API_CONVENTIONS.md`](../architecture/API_CONVENTIONS.md) §3
- ADR-0007, ADR-0011
