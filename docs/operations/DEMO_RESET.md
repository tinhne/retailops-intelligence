# Demo reset job

> **Status:** implemented (T-094, the part that needs no hosting). The command and its safety
> checks are tested; the schedule below is the recommended configuration for a deployment, which
> does not exist yet (T-093). Related: [ADR-0011](../decisions/ADR-0011-public-demo-read-only-viewer.md),
> [RUNBOOK.md](RUNBOOK.md), [`SECURITY.md`](../../SECURITY.md).

## 1. What it does

The public demo shows the fictional organization "Kestrel Commerce" with the store "Kestrel Home &
Kitchen". Visitors sign in as a read-only viewer ("Explore the demo"), so they cannot change it
(ADR-0011, verified by `tests/integration/test_demo_read_only.py`). The data still ages: orders get
older, deadlines pass, and the worker keeps evaluating. The reset job puts the demo back to the
seeded story, relative to the moment it runs:

1. Deletes the demo organization and everything in it (the only code path allowed to delete rows
   of append-only tables). It refuses to run if an organization with the demo slug exists but is
   not flagged `is_demo`.
2. Regenerates the dataset (`app/demo/seed.py`): about 120 products, about 1,500 orders over 60
   days, the stock ledger, and engineered scenarios for every exception type.
3. Runs the first evaluation, in the same transaction as the purge, so visitors never see an
   empty demo and the worker never evaluates the new store halfway through the story.
4. Plays five hours of team activity (`app/demo/history.py`) through the real lifecycle service
   and import pipeline: assignments, an acknowledgement, work in progress with notes, two
   resolutions that the next evaluation verifies, a refund resolution that fresh data proves wrong
   (the engine reopens it), a dismissal, and two small CSV imports.
5. Runs a final scheduled evaluation at the current time.

With the default seed the result is always the same story (18 exceptions: 12 open, 1
acknowledged, 1 in progress, 2 resolved and verified, 1 reopened, 1 dismissed). The pytest snapshot
in `tests/integration/test_demo_seed.py` pins these numbers.

Side effects to know about:

- **Every demo visitor is signed out.** The demo accounts are recreated, so their sessions end.
  The web app sends them back to the sign-in page, where "Explore the demo" works again.
- Everything stored under the demo organization is deleted with it. A new store-scoped table must
  cascade from its store or organization, or be removed in `app/demo/purge.py`, or the purge fails
  on a foreign key (which leaves the old demo in place, because the reset is one transaction).
- Staff accounts (`owner@`, `manager@`, `staff@`, `sofia@`, `analyst@kestrel.example`) get
  `DEMO_STAFF_PASSWORD` locally, or a random password when it is unset. The command refuses
  `DEMO_STAFF_PASSWORD` when `APP_ENV=production`, so public deployments only offer the viewer.
- Record-keeping columns (`created_at`, audit `occurred_at`) carry the time the job ran; business
  timestamps (orders, movements, exception events, imports) follow the generated timeline.

## 2. The command

Run it from the API image or the API's Python environment:

| Context | Command |
|---|---|
| Compose stack | `docker compose run --rm --no-deps demo-seed python -m app.demo` |
| Local development | `make seed` (same as `uv --directory apps/api run python -m app.demo`) |
| Container platform | the API image with the command `python -m app.demo` and the API's `DATABASE_URL` |

Options: `--seed N` builds a different, still deterministic dataset. `--if-missing` seeds only when no
demo organization exists; the compose `demo-seed` service uses it on every start, so restarting the
stack never discards data.

Exit status:

| Code | Meaning | Action |
|---|---|---|
| 0 | Reset done (or nothing to do with `--if-missing`) | none |
| 2 | Refused: `DEMO_STAFF_PASSWORD` is set while `APP_ENV=production` | fix the configuration |
| 3 | Another reset holds the lock (PostgreSQL advisory lock); nothing changed | none; the next run resets |
| 1 | Unexpected failure (for example the seed refused a non-demo organization, or the database is unreachable); the transaction rolled back | read the JSON log line, fix, run again |

A successful run logs one JSON line `demo_seeded` with the counts of products, orders, movements,
imports and every evaluation.

## 3. Schedule

**Recommendation: once a day at 07:00 UTC, and once after each deployment.** 07:00 UTC is about
02:00 to 03:00 in the demo store's time zone (America/New_York), when the fewest visitors are signed
in, and a daily cadence keeps the story fresh while the worker keeps time-based exceptions current
between resets. The job takes about ten seconds.

Host cron (a single VM running the compose stack):

```cron
# m h dom mon dow  command
0 7 * * *  cd /srv/retailops && docker compose run --rm --no-deps demo-seed python -m app.demo >> /var/log/retailops/demo-reset.log 2>&1
```

A hosting platform's scheduled job (for example a cron job service or a scheduled container task)
runs the API image with `python -m app.demo`, the same environment variables as the API, and the
schedule `0 7 * * *`. The job is not part of the worker on purpose (ADR-0011): a reset is rare,
destructive for the demo organization, and easier to reason about as its own process.

Alerting: treat exit status 1 as a failure. Exit status 3 means another reset was running and can
be ignored.

## 4. What visitors can and cannot do

| Action | Demo viewer | Enforced by |
|---|---|---|
| Read every screen of the demo store, use analytics and audit | yes | VIEWER permissions (ADR-0007) |
| Ask the copilot | yes, scoped to the visitor's session (ADR-0011) | `copilot.use` |
| Any lifecycle action, assignment, note, due date | no (403) | `require_permission` on every command route |
| Imports (upload, apply, discard), evaluations, store settings | no (403) | `require_permission` |
| Reach another organization | no (404) | store scoping |
| Become anything but VIEWER through "Explore the demo" | no | the demo sign-in refuses a demo account with any other role (`DEMO_MISCONFIGURED`) |

The test walks every mutating operation in the OpenAPI document, so a route added later is covered
without editing the test. A new route that a visitor may call because it only writes the visitor's
own session data (for example copilot conversations) must be added to `VISITOR_PRIVATE` in the test
with its reason.
