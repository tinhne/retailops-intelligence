# ENVIRONMENT_STATUS

> Names only. **Never write secret values in this file.** Last updated: 2026-11-01.

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
| `TRUST_PROXY_HEADERS` | api | no | `true` when the API sits behind a trusted proxy (the Next.js server or a load balancer), so rate limits and audit use the forwarded client IP. Default `false` |
| `LOG_LEVEL` | api, worker | no | default `INFO` |
| `DEMO_MODE_ENABLED` | api | no | Enables the "Explore the demo" read-only sign-in |
| `DEMO_STAFF_PASSWORD` | `make seed` | no | Password for the seeded staff accounts (`owner@`, `manager@`, `staff@`, `sofia@`, `analyst@kestrel.example`). Unset means a random password, so those accounts cannot sign in. Local and test use only |
| `LLM_PROVIDER` | api | no | `deterministic` \| `gemini` \| `openai_compatible`. Empty: `gemini` when `GEMINI_API_KEY` is set, otherwise `deterministic`. Free-tier providers only (ADR-0010) |
| `GEMINI_API_KEY` | api | no | Free key from Google AI Studio. Server-side only, never exposed to the frontend |
| `LLM_MODEL` | api | no | Model identifier (gemini default: a Flash-class model; required for `openai_compatible`) |
| `LLM_BASE_URL` / `LLM_API_KEY` | api | no | `openai_compatible` only (e.g. Groq, OpenRouter free models) |
| `LLM_TIMEOUT_SECONDS` | api | no | Timeout of one live LLM request before falling back to deterministic (default 20) |
| `COPILOT_RATE_LIMIT_PER_MINUTE` | api | no | Per-principal copilot limit to protect the free quota (default 20; per session for the demo viewer) |
| `LLM_BUDGET_REQUESTS_PER_MINUTE` / `LLM_BUDGET_REQUESTS_PER_DAY` / `LLM_BUDGET_TOKENS_PER_DAY` | api | no | Per-instance live LLM budget below the free-tier quota (defaults 10 / 500 / 1000000); when spent, answers come from the deterministic provider |
| `AI_TURN_DEADLINE_SECONDS`, `AI_MAX_TOOL_ITERATIONS`, `AI_MAX_TOOL_CALLS_PER_TURN`, `AI_TOOL_TIMEOUT_SECONDS`, `AI_TOOL_MAX_ROWS`, `AI_TOOL_MAX_RESULT_BYTES`, `AI_MAX_INPUT_TOKENS_PER_TURN`, `AI_MAX_OUTPUT_TOKENS`, `AI_HISTORY_TURNS`, `AI_MAX_MESSAGES_PER_CONVERSATION`, `AI_SUMMARY_CACHE_TTL_HOURS`, `AI_CIRCUIT_FAILURE_THRESHOLD`, `AI_CIRCUIT_OPEN_SECONDS` | api | no | Copilot limits; defaults in `docs/ai/AI_ARCHITECTURE.md` §10 |
| `EVAL_DATABASE_URL` | `make ai-eval` | no | Evaluation database (default `retailops_eval` on the local container; created if missing and rebuilt on every run). Local/CI only |
| `API_INTERNAL_URL` | web (build) | yes (deploy) | Where the Next.js server proxies `/api/*` (e.g. `http://api:8000`). Read when the web app is built, because rewrites are compiled. Defaults to `http://localhost:8000` for local development |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | db (compose) | yes (local) | Local database container only |

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
