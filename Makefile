# RetailOps Intelligence: developer commands. Run `make help` for the list.
API_DIR := apps/api
UV := uv --directory $(API_DIR)

.DEFAULT_GOAL := help
.PHONY: help setup db-up db-down migrate seed api-dev api-test api-lint api-typecheck check test down reset

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Install backend dependencies (Python 3.12 via uv)
	$(UV) sync

db-up: ## Start PostgreSQL (docker compose) and wait until healthy
	docker compose up -d --wait db

db-down: ## Stop PostgreSQL
	docker compose stop db

migrate: db-up ## Apply database migrations
	$(UV) run alembic upgrade head

seed: migrate ## (Re)generate the demo dataset for "Kestrel Home & Kitchen"
	$(UV) run python -m app.demo

api-dev: migrate ## Run the API with auto-reload on http://localhost:8000
	$(UV) run uvicorn app.main:app --reload --port 8000

api-lint: ## Lint and format-check the backend
	$(UV) run ruff check .
	$(UV) run ruff format --check .

api-typecheck: ## Static type check (mypy --strict)
	$(UV) run mypy

api-test: db-up ## Run backend unit + integration tests
	$(UV) run pytest

check: api-lint api-typecheck api-test ## All backend quality gates

test: api-test ## Run every test suite

down: ## Stop all services
	docker compose down

reset: ## Stop services and DELETE local database volumes
	docker compose down -v
