#!/usr/bin/env bash
# One-command local walkthrough (`make demo`): build and start the Docker Compose stack, regenerate
# the fictional demo store so its data is current, enable the staff sign-ins, and print where to go.
# Local only: the demo CLI refuses DEMO_STAFF_PASSWORD when APP_ENV=production.
set -euo pipefail
cd "$(dirname "$0")/../.."

ENV_FILE=.env

# A value from the environment, else from .env (the file Docker Compose reads), without quotes.
setting() {
  local value="${!1:-}"
  if [ -z "$value" ] && [ -f "$ENV_FILE" ]; then
    value="$(grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e "s/^[\"']//" -e "s/[\"']\$//")"
  fi
  printf '%s' "$value"
}

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Start Docker Desktop, then run 'make demo' again." >&2
  exit 1
fi

# Staff sign-ins need DEMO_STAFF_PASSWORD. Generate one on the first run and keep it in the
# git-ignored .env, so the password stays the same from one walkthrough to the next.
password="$(setting DEMO_STAFF_PASSWORD)"
if [ -z "$password" ]; then
  password="demo-$(openssl rand -hex 8)"
  if [ -f "$ENV_FILE" ]; then
    # Rewrite in place (keeps the file's permissions) without an empty DEMO_STAFF_PASSWORD= line.
    kept="$(grep -v -E '^DEMO_STAFF_PASSWORD=' "$ENV_FILE" || true)"
    printf '%s\n' "$kept" >"$ENV_FILE"
  else
    (umask 077 && : >"$ENV_FILE")
  fi
  printf '# Staff sign-in password for the local walkthrough (make demo)\nDEMO_STAFF_PASSWORD=%s\n' \
    "$password" >>"$ENV_FILE"
fi
export DEMO_STAFF_PASSWORD="$password"

echo "==> Building and starting the database and API (the first build takes a few minutes)"
docker compose up --build -d --wait db api

echo "==> Generating fresh demo data"
docker compose run --rm --no-deps demo-seed python -m app.demo

echo "==> Starting the worker and the web app"
docker compose up --build -d --wait worker web

web_port="$(setting WEB_HOST_PORT)"
api_port="$(setting API_HOST_PORT)"
cat <<EOF

RetailOps Intelligence is running, with demo data generated just now (all of it fictional).

  Open       http://127.0.0.1:${web_port:-3000}
  Viewer     "Explore the demo" on the sign-in page: read-only, no password
  Staff      manager@kestrel.example (also owner@, staff@, sofia@, analyst@kestrel.example)
  Password   ${password}   (kept in .env, the same next time)
  API docs   http://127.0.0.1:${api_port:-8000}/api/docs

  Stop: make down   Fresh data: make demo   Delete all local data: make reset
EOF
