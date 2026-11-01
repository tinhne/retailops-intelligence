# Runbook: the container stack

> **Status:** implemented and verified locally (T-090, 2026-11-01) with Docker 29.1.3 and Compose
> v5.0.1. There is no hosted deployment yet (T-093). Related: [DEMO_RESET.md](DEMO_RESET.md),
> [`SECURITY.md`](../../SECURITY.md), [CONTAINER_DIAGRAM.md](../architecture/CONTAINER_DIAGRAM.md).

## 1. Services

| Service | Image | Runs | Host port | Health check | User |
|---|---|---|---|---|---|
| `db` | `postgres:16-alpine` | PostgreSQL; `infra/docker/postgres-init` creates the `retailops_test` database on a new volume | `POSTGRES_HOST_PORT` (54329), all interfaces | `pg_isready` | `postgres` |
| `api` | `retailops-api:local` from `infra/docker/api.Dockerfile` | `alembic upgrade head`, then uvicorn on :8000 | `API_HOST_PORT` (8000), 127.0.0.1 only | `GET /api/v1/health/ready` (database reachable) | `app` (uid 999) |
| `demo-seed` | same image as `api` | `python -m app.demo --if-missing`, then exits | none | exit status 0 | `app` |
| `worker` | same image as `api` | `python -m app.workers.scheduler --heartbeat /tmp/worker-heartbeat` | none | heartbeat file younger than 180 s | `app` |
| `web` | `retailops-web:local` from `infra/docker/web.Dockerfile` | Next.js standalone server (`node apps/web/server.js`) on :3000 | `WEB_HOST_PORT` (3000), 127.0.0.1 only | `GET /login` | `node` (uid 1000) |

Start order: `db` healthy → `api` healthy (migrations applied) → `demo-seed` completes → `worker` and
`web` start. The browser only talks to `web`; `web` proxies `/api/*` to `http://api:8000`
(ADR-0004).

## 2. Start the stack

```bash
docker compose up --build            # foreground, with logs
make stack-up                        # the same, detached, waits for health checks
```

Then open <http://localhost:3000> and choose **Explore the demo**. API docs are on
<http://localhost:8000/api/docs> (and through the web origin at `/api/docs`).

On the first start `demo-seed` builds the demo organization (about ten seconds). On later starts it
sees the existing organization and exits without changing anything. Data lives in the named volume
`retailops_pgdata`, shared with the local development workflow (`make db-up`, `make api-dev`).

The database alone, for local development with hot reload: `make db-up` (only `db` starts).

## 2a. Customer installation (no demo organization)

A customer instance starts without `demo-seed`, so no fictional organization exists, and the
sign-in page offers no demo (`GET /api/v1/auth/options` answers `demo_available: false`).

```bash
# .env: APP_ENV=production, SESSION_SECRET=$(openssl rand -hex 32), COOKIE_SECURE=true (HTTPS),
#       DEMO_MODE_ENABLED=false, a strong POSTGRES_PASSWORD; leave DEMO_STAFF_PASSWORD empty
make stack-up-customer
make stack-provision ARGS="--org-name 'Lotus Home' --store-name 'Lotus Home Online' \
  --currency VND --timezone Asia/Ho_Chi_Minh \
  --owner-email owner@lotushome.vn --owner-name 'Nguyen Van An' --exposure-cap 100000000"
```

`stack-provision` creates the organization, its store with default settings and the owner account,
writes the audit entry `organization.provision`, and prints the owner's temporary password once.
Hand it over through a secure channel. The owner then signs in, adds the team under **Users &
roles** (each new member also gets a one-time temporary password), reviews **Settings**, and imports
the four CSV files in the order products → inventory adjustments → orders → order items.
Outside the containers the same command is `make provision ARGS="..."`.

`exposure_cap` is in store currency: the default 5000 suits USD; for VND use a value such as
100000000. It can be changed later under Settings.

## 3. Configuration

Compose reads variables from the shell or from `.env` in the repository root (see `.env.example`,
variable reference in `ENVIRONMENT_STATUS.md`). The services get an explicit list; `DATABASE_URL`
is always built from `POSTGRES_*` and points at `db`, so a local `.env` written for `make api-dev`
does not break the containers.

| Variable | Default in compose | Notes |
|---|---|---|
| `POSTGRES_HOST_PORT` / `API_HOST_PORT` / `WEB_HOST_PORT` | 54329 / 8000 / 3000 | Change them to run a second copy of the stack |
| `SESSION_SECRET` | a local-only placeholder | `APP_ENV=production` refuses it; use `openssl rand -hex 32` |
| `COOKIE_SECURE` | `false` | `true` behind HTTPS |
| `TRUST_PROXY_HEADERS` | `false` | Read `SECURITY.md` §5 before changing it |
| `DEMO_STAFF_PASSWORD` | empty | Empty: the seeded staff accounts cannot sign in. Refused in production |
| `LLM_PROVIDER` and keys | `deterministic` | Free-tier providers only (ADR-0010) |

`API_INTERNAL_URL` is a **build argument** of the web image, not a run-time variable: Next.js
compiles the `/api/*` rewrite into its build output. Compose passes `http://api:8000`. For another
API address, build another image:
`docker build -f infra/docker/web.Dockerfile --build-arg API_INTERNAL_URL=http://other:8000 .`

## 4. Demo data

| Task | Command |
|---|---|
| Seed if missing (automatic on start) | `docker compose run --rm --no-deps demo-seed` |
| Reset to the seeded story | `make stack-demo-reset` or `docker compose run --rm --no-deps demo-seed python -m app.demo` |
| Make staff accounts usable locally | set `DEMO_STAFF_PASSWORD` in `.env`, then reset |

What the reset does, its exit codes and the recommended schedule: [DEMO_RESET.md](DEMO_RESET.md).

## 5. Health, logs, status

```bash
docker compose ps                                  # state and health of every service
docker compose logs -f api worker                  # JSON log lines with request_id
curl -s http://localhost:3000/api/v1/health/ready  # {"status":"ok","database":"ok"} via the web origin
```

The worker logs `scheduled_evaluation` for every store it evaluates. A store is evaluated when its
latest run is older than its interval (15 minutes by default), so right after a seed or reset the
worker is quiet for a while: that is expected.

## 6. Run a second copy next to an existing one

The project name separates containers, networks and volumes. Use other host ports and tear down only
that project. This is how the stack was verified without touching the shared development database:

```bash
POSTGRES_HOST_PORT=55432 API_HOST_PORT=8300 WEB_HOST_PORT=3300 \
  docker compose -p retailops-verify up --build -d
docker compose -p retailops-verify ps
curl -s http://127.0.0.1:3300/api/v1/health/ready
docker compose -p retailops-verify down -v          # removes only retailops-verify_* resources
```

## 7. Stop and clean up

| Command | Effect |
|---|---|
| `docker compose stop` | Stops the containers, keeps everything |
| `make down` (`docker compose down`) | Removes containers and network, **keeps** the database volume |
| `make reset` (`docker compose down -v`) | Also **deletes the database volume**: all local data is gone |

## 8. Verification record (2026-11-01)

Run with the commands in §6, after removing earlier local builds of the images:

- All five services reached their expected state: `db`, `api`, `worker`, `web` healthy; `demo-seed`
  exited 0 after logging `demo_seeded` (114 products, 1,551 orders, 2,615 movements, 2 imports, 18
  exceptions).
- `GET /login` on the web origin: 200, with `X-Frame-Options: DENY`, `X-Content-Type-Options:
  nosniff`, `Referrer-Policy` and the partial CSP.
- `GET /api/v1/health/ready` through the web origin: 200 `{"status":"ok","database":"ok"}`, with
  `Cache-Control: no-store`.
- Demo sign-in through the web origin (`GET /auth/csrf`, then `POST /auth/demo`): VIEWER of "Kestrel
  Home & Kitchen"; without the token: 403 `CSRF_FAILED`. Exceptions by status: 12 open, 1
  acknowledged, 1 in progress, 2 resolved, 1 reopened, 1 dismissed. A lifecycle command as the
  viewer: 403 `PERMISSION_DENIED`. In a browser, "Explore the demo" opened the Overview with no
  console errors.
- `id` in the containers: `app` (uid 999) for api and worker, `node` (uid 1000) for web. The worker
  heartbeat file was written after its first pass.
- The reset command inside the stack (`docker compose run --rm --no-deps demo-seed python -m app.demo`)
  exited 0 and signed out the existing demo session (401 on `/auth/me`).
- Uploads through the Next.js proxy as the demo manager: a 5.1 MB CSV was stored as a `REJECTED`
  import with `FILE_TOO_LARGE`; a 7 MB CSV was refused with 413 `PAYLOAD_TOO_LARGE`.
- Client address seen by the API through the proxy: see `SECURITY.md` §5.

## 9. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `web` never starts | It waits for `api` to be healthy and `demo-seed` to finish. `docker compose logs api demo-seed` |
| `api` restarts or is unhealthy | Migrations failed or the database is unreachable: `docker compose logs api` |
| `demo-seed` exits 1 | Read its JSON log. `Organization 'kestrel-commerce' exists but is not a demo organization` means the reset refused to delete real data |
| `demo-seed` exits 3 | Another reset was running; nothing changed |
| Port already in use | Set `API_HOST_PORT`, `WEB_HOST_PORT` or `POSTGRES_HOST_PORT` |
| Browser shows an old API address | `API_INTERNAL_URL` is compiled into the web image; rebuild with `--build` |
| Sign-in answers 403 `CSRF_FAILED` | The client did not call `GET /api/v1/auth/csrf` first, or cookies are blocked |
