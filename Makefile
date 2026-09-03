.PHONY: help dev dev-d stop clean test test-unit test-integration lint typecheck format migrate migrate-create seed docker-build logs logs-api setup gen-docs seed-local api-local web-dev

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

dev: ## Start all services in development mode
	docker compose up --build

dev-d: ## Start all services in detached mode
	docker compose up --build -d

stop: ## Stop all services
	docker compose down

clean: ## Stop and remove all volumes
	docker compose down -v

test: ## Run all tests
	cd services/api && ../../.venv/bin/python -m pytest tests/ -v

test-unit: ## Run unit tests
	cd services/api && ../../.venv/bin/python -m pytest tests/unit/ -v

test-integration: ## Run integration tests
	cd services/api && ../../.venv/bin/python -m pytest tests/integration/ -v

lint: ## Run linter
	cd services/api && ../../.venv/bin/ruff check .

typecheck: ## Run type checking
	cd services/api && ../../.venv/bin/mypy app/

format: ## Format code
	cd services/api && ../../.venv/bin/ruff format .

migrate: ## Run database migrations
	cd services/api && alembic upgrade head

migrate-create: ## Create a new migration
	cd services/api && alembic revision --autogenerate -m "$(msg)"

seed: ## Seed synthetic data
	cd services/api && python -m app.core.seed

docker-build: ## Build Docker images
	docker compose build

logs: ## View logs
	docker compose logs -f

logs-api: ## View API logs
	docker compose logs -f api

setup: ## Initial project setup
	cp -n .env.example .env || true
	docker compose build
	docker compose up -d postgres redis minio
	sleep 5
	cd services/api && pip install -r requirements.txt
	cd services/api && alembic upgrade head
	@echo "Setup complete. Run 'make dev' to start."

gen-docs: ## Generate synthetic demo documents into data/synthetic
	python scripts/synthetic_documents.py

# --- Standalone (no Docker) mode ------------------------------------------
# The API can run entirely against a local SQLite file. Document upload /
# full verification still require MinIO; case, registry, audit, auth flows
# work fully.

seed-local: ## Seed a local SQLite database (standalone mode)
	cd services/api && DATABASE_URL=sqlite+aiosqlite:///./veridex.db python -m app.core.seed

api-local: ## Run the API standalone against SQLite (no Docker)
	cd services/api && DATABASE_URL=sqlite+aiosqlite:///./veridex.db python -m uvicorn app.main:app --reload --port 8000

web-dev: ## Run the Next.js dashboard in dev mode
	cd apps/web && npm run dev
