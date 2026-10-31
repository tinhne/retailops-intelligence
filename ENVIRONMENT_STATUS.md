# ENVIRONMENT_STATUS

> Names only. **Never write secret values in this file.** Last updated: 2026-11-01.

## Local development requirements

| Tool | Version verified | Notes |
|---|---|---|
| Docker Desktop / Engine | 29.1.3 (Compose v5.0.1) | Runs PostgreSQL and the full stack (`docker compose up --build`, verified 2026-11-01; see `docs/operations/RUNBOOK.md`) |
| Python | 3.12 (via `uv`) | Backend. The system Python 3.9 is too old and is not used |
| uv | 0.13.6 | Python env and dependency manager for `apps/api` |
| Node.js | 24.14.1 | Frontend |
| pnpm | 10.33.0 | Frontend workspace |
| git | 2.50.1 | |

## Environment variables (names only)

| Variable | Used by | Required | Purpose |
|---|---|---|---|
| `APP_ENV` | api, worker | yes | `local` \| `test` \| `production` |
| `DATABASE_URL` | api, worker | yes | PostgreSQL connection string (psycopg 3 driver) |
| `SESSION_SECRET` | api | yes (prod) | HMAC key for CSRF token derivation. `APP_ENV=production` requires at least 32 characters |
| `COOKIE_SECURE` | api | no | `true` in production (HTTPS) |
| `TRUST_PROXY_HEADERS` | api | no | Default `false`. `true` makes the API take the client address (rate limits, audit) from the right-most `X-Forwarded-For` entry. Only safe behind an edge proxy that appends the client address, with the API unreachable from outside: the Next.js proxy alone forwards whatever the browser sends (`SECURITY.md` §5) |
| `LOG_LEVEL` | api, worker | no | default `INFO` |
| `DEMO_MODE_ENABLED` | api | no | Enables the "Explore the demo" read-only sign-in |
| `DEMO_STAFF_PASSWORD` | `python -m app.demo` (`make seed`, compose `demo-seed`) | no | Password for the seeded staff accounts (`owner@`, `manager@`, `staff@`, `sofia@`, `analyst@kestrel.example`). Unset means a random password, so those accounts cannot sign in. Local and test use only: refused when `APP_ENV=production` |
| `LLM_PROVIDER` | api | no | `deterministic` (default, no key) \| `gemini` \| `openai_compatible`. Free-tier providers only (ADR-0010) |
| `GEMINI_API_KEY` | api | no | Free key from Google AI Studio. Server-side only, never exposed to the frontend |
| `LLM_MODEL` | api | no | Model identifier (defaults to a Flash-class Gemini model) |
| `LLM_BASE_URL` / `LLM_API_KEY` | api | no | `openai_compatible` only (e.g. Groq, OpenRouter free models) |
| `LLM_TIMEOUT_SECONDS` | api | no | Live-provider timeout before falling back to deterministic (default 20) |
| `COPILOT_RATE_LIMIT_PER_MINUTE` | api | no | Per-user copilot limit to protect the free quota (default 20) |
| `API_INTERNAL_URL` | web (build) | yes (deploy) | Where the Next.js server proxies `/api/*` (e.g. `http://api:8000`). Read when the web app is built, because rewrites are compiled: a build argument of `infra/docker/web.Dockerfile` (compose passes `http://api:8000`). Defaults to `http://localhost:8000` for local development |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | db (compose) | yes (local) | Local database container only. Compose builds the containers' `DATABASE_URL` from them |
| `POSTGRES_HOST_PORT` | compose | no | Host port of `db` (default 54329) |
| `API_HOST_PORT` / `WEB_HOST_PORT` | compose | no | Host ports of `api` and `web` (defaults 8000 and 3000, bound to 127.0.0.1) |

## External dependencies and connected services

| Service | Status | Notes |
|---|---|---|
| GitHub repository `tinhne/retailops-intelligence` | **Created (public), `main` pushed 2026-11-01** | Remote `origin` = `git@github.com:tinhne/retailops-intelligence.git` (SSH). `gh` is installed but not signed in, so CI status is read through the public API |
| Hosting provider | **Not chosen** | Evaluation pending (T-093). No paid resources without approval |
| Managed PostgreSQL | **Not provisioned** | Local Docker Postgres only |
| LLM provider | **No key configured** | Free-tier only (owner decision, 2026-10-31): Google Gemini (AI Studio key) by default, any OpenAI-compatible free tier as an alternative. The product runs on the deterministic provider until a key is added |

## Missing credentials / manual setup steps

1. ~~Create the GitHub repository~~ Done by the owner on 2026-11-01.
2. (Later) Choose a hosting provider and add deployment secrets to GitHub Actions.
3. (Optional) Create a free Gemini API key in Google AI Studio and set `LLM_PROVIDER=gemini` and
   `GEMINI_API_KEY` in `.env` (local) or in the host's secret store (deployment).
