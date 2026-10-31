# ENVIRONMENT_STATUS

> Names only. **Never write secret values in this file.** Last updated: 2026-10-31.

## Local development requirements

| Tool | Version verified | Notes |
|---|---|---|
| Docker Desktop / Engine | 29.1.3 (Compose v5.0.1) | Runs PostgreSQL and the full stack |
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
| `SESSION_SECRET` | api | yes (prod) | HMAC key for CSRF token derivation |
| `COOKIE_SECURE` | api | no | `true` in production (HTTPS) |
| `CORS_ALLOWED_ORIGINS` | api | no | Only needed if the API is called cross-origin (not the default setup) |
| `LOG_LEVEL` | api, worker | no | default `INFO` |
| `DEMO_MODE_ENABLED` | api | no | Enables the "Explore the demo" read-only sign-in |
| `LLM_PROVIDER` | api | no | `deterministic` (default, no key) \| `gemini` \| `openai_compatible`. Free-tier providers only (ADR-0010) |
| `GEMINI_API_KEY` | api | no | Free key from Google AI Studio. Server-side only, never exposed to the frontend |
| `LLM_MODEL` | api | no | Model identifier (defaults to a Flash-class Gemini model) |
| `LLM_BASE_URL` / `LLM_API_KEY` | api | no | `openai_compatible` only (e.g. Groq, OpenRouter free models) |
| `LLM_TIMEOUT_SECONDS` | api | no | Live-provider timeout before falling back to deterministic (default 20) |
| `COPILOT_RATE_LIMIT_PER_MINUTE` | api | no | Per-user copilot limit to protect the free quota (default 20) |
| `API_INTERNAL_URL` | web | yes | Where the Next.js server proxies `/api/*` (e.g. `http://api:8000`) |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | db (compose) | yes (local) | Local database container only |

## External dependencies and connected services

| Service | Status | Notes |
|---|---|---|
| GitHub repository `tinhne/retailops-intelligence` | **Not created** | SSH push access as `tinhne` verified. The `gh` CLI is not installed, so the repo can't be created from this machine without a token (T-092) |
| Hosting provider | **Not chosen** | Evaluation pending (T-093). No paid resources without approval |
| Managed PostgreSQL | **Not provisioned** | Local Docker Postgres only |
| LLM provider | **No key configured** | Free-tier only (owner decision, 2026-10-31): Google Gemini (AI Studio key) by default, any OpenAI-compatible free tier as an alternative. The product runs on the deterministic provider until a key is added |

## Missing credentials / manual setup steps

1. Create an empty public repository `tinhne/retailops-intelligence` on GitHub (no README or license,
   to avoid a history conflict), or install `gh` and run `gh auth login`.
2. (Later) Choose a hosting provider and add deployment secrets to GitHub Actions.
3. (Optional) Create a free Gemini API key in Google AI Studio and set `LLM_PROVIDER=gemini` and
   `GEMINI_API_KEY` in `.env` (local) or in the host's secret store (deployment).
