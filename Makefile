.PHONY: help setup up down logs clean test lint format install

# Compose configuration (compose file lives under ./docker)
COMPOSE_FILE := docker/docker-compose.yml
DC := docker compose -f $(COMPOSE_FILE)
PYTHON := ./.venv/bin/python

help:
	@echo "Canva-NotebookLM Integration Agent - Development Commands"
	@echo ""
	@echo "Setup & Environment:"
	@echo "  make setup          Initialize project (install deps, setup docker)"
	@echo "  make install        Install Python dependencies"
	@echo ""
	@echo "Docker Management:"
	@echo "  make up             Start PostgreSQL + Redis (docker-compose)"
	@echo "  make down           Stop services"
	@echo "  make logs           View service logs (docker-compose)"
	@echo "  make clean          Stop services and remove volumes (DESTRUCTIVE)"
	@echo ""
	@echo "Development:"
	@echo "  make dev            Run API server in development mode"
	@echo "  make worker         Run task worker"
	@echo ""
	@echo "Testing & Quality:"
	@echo "  make test           Run all tests (unit + integration)"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-int       Run integration tests only"
	@echo "  make test-watch     Run tests in watch mode"
	@echo "  make lint           Run code linters (pylint, flake8)"
	@echo "  make type-check     Run mypy type checker"
	@echo "  make format         Format code with black and isort"
	@echo "  make validate       Run lint + type-check + format (check only)"
	@echo ""
	@echo "Database:"
	@echo "  make db-init        Initialize database schema"
	@echo "  make db-migrate     Run pending migrations"
	@echo "  make db-seed        Seed initial data"
	@echo "  make db-reset       Drop and recreate database (DEV ONLY)"
	@echo "  make db-check       Test database connection"
	@echo ""
	@echo "Smoke Tests:"
	@echo "  make smoke-canva    Test Canva OAuth setup + endpoints"
	@echo "  make smoke-canva-design  Test real design creation (requires OAuth)"
	@echo ""
	@echo "Scripts:"
	@echo "  make validate-creds Check API credential validity"
	@echo ""

# Setup & Installation
setup: install up
	@echo "✓ Project setup complete (install + services)"

install:
	uv pip install --upgrade pip setuptools
	uv pip install -r src/requirements.txt
	uv pip install -r src/requirements-dev.txt
	@echo "✓ Dependencies installed via uv"

# Docker Compose
up:
	$(DC) up -d
	@echo "✓ Services started (postgres, redis)"
	@echo "  PostgreSQL: localhost:55432 -> container 5432"
	@echo "  Redis: localhost:6379"

down:
	$(DC) down
	@echo "✓ Services stopped"

logs:
	$(DC) logs -f

clean:
	$(DC) down -v
	@echo "✓ All services and volumes removed (DESTRUCTIVE)"

# Development
api:
	$(PYTHON) -m uvicorn src.main:app --host 0.0.0.0 --port 8000

dev:
	$(PYTHON) -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

worker:
	$(PYTHON) -m src.workers

ui-install:
	cd ui && npm install
	@echo "✓ UI dependencies installed"

ui:
	cd ui && npm run dev


e2e-install:
	cd ui && npm install && npx playwright install --with-deps
	@echo "✓ Playwright installed with browser dependencies"

e2e:
	cd ui && npm run e2e
	@echo "✓ E2E tests completed"

e2e-ui:
	./scripts/run_e2e_ui.sh

e2e-headed:
	cd ui && npm run e2e:headed

# Testing
test:
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=term-missing

test-unit:
	$(PYTHON) -m pytest tests/unit/ -v --cov=src

test-int:
	$(PYTHON) -m pytest tests/integration/ -v

test-watch:
	$(PYTHON) -m pytest_watch tests/ -v

smoke-test:
	@echo "Running T1.5-T1.7 smoke tests..."
	$(PYTHON) -m pytest tests/unit/test_health.py -q
	$(PYTHON) -m pytest tests/unit/test_cache.py -q
	$(PYTHON) -m pytest tests/unit/test_middleware_request_context.py -q
	$(PYTHON) -m pytest tests/unit/test_integration_t17.py -q
	@echo "✓ All smoke tests passed (T1.5-T1.7 verification complete)"
lint:
	$(PYTHON) -m pylint src/ tests/
	$(PYTHON) -m flake8 src/ tests/ --max-line-length=120

type-check:
	$(PYTHON) -m mypy src/ --strict

format:
	$(PYTHON) -m black src/ tests/ --line-length=120
	$(PYTHON) -m isort src/ tests/ --profile=black

validate: lint type-check
	$(PYTHON) -m black src/ tests/ --line-length=120 --check
	$(PYTHON) -m isort src/ tests/ --profile=black --check
	@echo "✓ All validations passed"

# Database
db-init:
	$(PYTHON) scripts/setup_db.py init
	@echo "✓ Database schema initialized"

db-migrate:
	$(PYTHON) scripts/setup_db.py migrate
	@echo "✓ Migrations applied"

db-seed:
	$(PYTHON) scripts/setup_db.py seed
	@echo "✓ Initial data seeded"

db-reset:
	$(PYTHON) scripts/setup_db.py reset
	@echo "✓ Database reset (DEV ONLY)"

db-check:
	$(PYTHON) scripts/setup_db.py check
	@echo "✓ Database connection verified"

# Testing & Validation
validate-creds:
	$(PYTHON) scripts/validate_credentials.py
	@echo "✓ Credential validation complete"

smoke-canva:
	@bash scripts/smoke_canva_oauth_and_create_design.sh
	@echo ""

smoke-canva-design:
	@bash scripts/smoke_canva_oauth_and_create_design.sh --test-design-creation
	@echo ""

# CI/CD targets (for GitHub Actions)
ci-lint: lint type-check
ci-test: test
ci-all: ci-lint ci-test
