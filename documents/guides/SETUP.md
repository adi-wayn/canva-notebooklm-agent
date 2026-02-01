# Phase 0 Setup Guide

Complete this guide to set up the local development environment.

## Prerequisites

- Python 3.8+ (3.10+ recommended)
- Docker & Docker Compose
- Git
- macOS, Linux, or Windows (WSL2)

## Step 1: Clone & Enter Project

```bash
cd /path/to/canva-notebooklm-agent
```

## Step 2: Create Python Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# OR on Windows:
venv\Scripts\activate
```

## Step 3: Install Dependencies

```bash
make install
```

This uses `uv` (fast Python package installer) to install:
- Core framework: FastAPI, Uvicorn, Pydantic
- Database: SQLAlchemy, asyncpg, Alembic
- Testing: pytest, pytest-asyncio
- Code quality: black, isort, pylint, mypy

All installs go into the active virtual environment.

## Step 4: Configure Environment

Copy `.env.example` to `.env` and fill in required values:

```bash
cp .env.example .env
```

Edit `.env` with:
- `CANVA_CLIENT_ID` — Your Canva OAuth client ID
- `CANVA_CLIENT_SECRET` — Your Canva OAuth secret
- `NOTEBOOKLM_API_KEY` — Your NotebookLM API key
- `LLM_API_KEY` — Your OpenAI or Claude API key
- `AUTH_JWT_SECRET` — Any random 32+ character string

## Step 5: Start Docker Services

```bash
make up
```

This starts:
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`

Verify with:
```bash
docker-compose logs -f
```

## Step 6: Initialize Database

```bash
make db-init
```

This creates PostgreSQL schema and tables.

## Step 7: Validate Credentials

```bash
make validate-creds
```

This tests that all API credentials are valid.

## Step 8: Run Tests

```bash
make test
```

Should see 15+ tests passing from `tests/test_authentication.py`.

## Step 9: Start Development Server

```bash
make dev
```

API will be available at:
- `http://localhost:8000` — API
- `http://localhost:8000/docs` — Interactive API docs (Swagger UI)
- `http://localhost:8001/metrics` — Prometheus metrics

## Verification Checklist

- [ ] Virtual environment activated
- [ ] `.env` file created and filled
- [ ] Docker containers running (`docker ps`)
- [ ] Database initialized (PostgreSQL schema exists)
- [ ] Credential validation passed
- [ ] All tests passing
- [ ] API server starts without errors
- [ ] Swagger UI accessible at `/docs`

## Common Issues

**"PostgreSQL connection refused"**
- Ensure containers are running: `docker-compose ps`
- Check logs: `docker-compose logs postgres`

**"pytest: command not found"**
- Ensure virtual environment is activated
- Reinstall dev dependencies: `pip install -r src/requirements-dev.txt`

**"CANVA_CLIENT_SECRET not found"**
- Check `.env` file exists and is in project root
- Ensure all required keys are present

## Next Steps

Once Phase 0 setup is complete, proceed to Phase 1 implementation.

See [STEP3_DEVELOPMENT_PLAN.md](../STEP3_DEVELOPMENT_PLAN.md) for the full roadmap.

## Useful Commands

```bash
make help              # Show all available commands
make dev              # Start development server (with auto-reload)
make test             # Run all tests
make test-watch       # Run tests and watch for changes
make lint             # Run code linters
make format           # Auto-format code
make validate         # Lint + type-check + format

docker-compose logs   # View container logs
docker-compose down   # Stop containers
make db-reset         # Reset database (DEV ONLY)
```

---

**Status**: ✓ Phase 0 scaffolding complete. Ready for Phase 1 implementation.
