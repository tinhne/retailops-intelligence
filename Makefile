# RetailOps Intelligence: developer commands. Run `make help` for the list.
API_DIR := apps/api
UV := uv --directory $(API_DIR)

.DEFAULT_GOAL := help
.PHONY: stack-up-customer provision stack-provision help setup db-up db-down migrate seed api-dev api-test api-lint api-typecheck ai-eval check test stack-up stack-demo-reset down reset

# Copilot evaluation (docs/ai/EVALUATION_STRATEGY.md §5). PROVIDER: deterministic (no key),
# gemini, openai_compatible, or all. REPEATS=0 means 1 for deterministic and 3 for live providers.
PROVIDER ?= deterministic
REPEATS ?= 0

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

seed: migrate ## (Re)generate the demo organization: dataset, evaluations and team history
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

ai-eval: db-up ## Copilot evaluation into retailops_eval (PROVIDER=deterministic|gemini|openai_compatible|all)
	$(UV) run python -m evals.run --provider $(PROVIDER) --dataset copilot_v1 --repeats $(REPEATS)

check: api-lint api-typecheck api-test ## All backend quality gates

test: api-test ## Run every test suite

stack-up: ## Build and start db, api, worker and web (http://localhost:3000), seeding the demo once
	docker compose up --build -d --wait db api worker web

stack-up-customer: ## Start db, api, worker and web WITHOUT the demo organization (customer install)
	docker compose up --build -d --wait db api
	docker compose up --build -d --no-deps --wait worker web

provision: ## Create a customer organization, store and owner: make provision ARGS='--org-name ...'
	$(UV) run python -m app.provision $(ARGS)

stack-provision: ## The same inside the running compose stack: make stack-provision ARGS='...'
	docker compose run --rm --no-deps api python -m app.provision $(ARGS)

stack-demo-reset: ## Reset the demo organization inside the running compose stack
	docker compose run --rm --no-deps demo-seed python -m app.demo

down: ## Stop all services
	docker compose down

reset: ## Stop services and DELETE local database volumes
	docker compose down -v
