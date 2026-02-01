# T2.8 Demo UI (MVP) — End-to-End Local Run

## Overview

This UI lets you create a workflow, watch live progress via SSE, refresh to replay state, and trigger retry/cancel.

**No real Canva/NotebookLM/LLM credentials required.** The backend starts with safe dev defaults and mocks external integrations. The demo focuses on the workflow engine, persistence, and UI interaction.

## Prerequisites

- Python 3.10+ with `uv` package manager
- Node 16+ and `npm`
- Docker and `docker-compose`
- Terminal access to the workspace

## Quick Start (4 Steps)

### Step 1: Start data services (PostgreSQL + Redis)

```bash
make up
```

**Output:**
```
✓ Services started (postgres, redis)
  PostgreSQL: localhost:5432
  Redis: localhost:6379
```

### Step 2: Start the API server (fastAPI)

In a second terminal:
```bash
make dev
```

**Output (after startup):**
```
INFO:     Application startup complete [uvicorn]
Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Start the worker (consumes Redis queue)

In a third terminal:
```bash
make worker
```

**Output (blocks):**
```
INFO: [worker-1] Worker started
```

### Step 4: Install UI deps and run Vite dev server

In a fourth terminal (first time only):
```bash
make ui-install
```

Then:
```bash
make ui
```

**Output:**
```
  VITE v5.1.0  ready in 234 ms

  ➜  local:   http://localhost:5173/
  ➜  press h to show help
```

**Open your browser to http://localhost:5173 and proceed to "Using the UI" below.**

---

## Using the UI

### Create a Workflow

1. Refresh the UI page if needed (it opens to create form by default).
2. Leave default values or customize:
   - **Tenant ID**: `demo-tenant` (or any string)
   - **User ID**: `demo-user` (or any string)
   - **Config (JSON)**: defaults to `{"prompt":"Generate artifacts","source_id":"demo-source"}`
3. Click **Create Workflow**.

**Expected outcome:**
- Workflow ID appears (e.g., `wf_a1b2c3d4e5f6`)
- UI auto-loads that workflow and opens a live event stream
- Status shows `SUBMITTED` → `QUEUED` → `PROCESSING` → `COMPLETED`
- Progress bar increments from 0 to 100
- Events appear in the live event log (JSON formatted)

### Refresh & Reload Persisted State

1. After a workflow completes, note its ID.
2. Refresh the browser (`Cmd+R` or `Ctrl+R`).
3. In the "Load Existing Workflow" card, paste the workflow ID into the **Workflow ID** field.
4. Click **Load & Stream**.

**Expected outcome:**
- UI fetches the workflow's final state from the API
- Event log replays all previously saved events (SSE replay from database)
- Final status (COMPLETED or FAILED) is displayed
- Artifacts (if any) are listed

### Retry a Failed Workflow

To force a failure (for testing):

1. In the create form, modify **Config** to:
   ```json
   {"simulate_failure": "transient_once"}
   ```
2. Click **Create Workflow**.
3. Wait for the workflow to reach FAILED status.
4. If the error shows `"retryable": true`, the **Retry** button appears enabled.
5. Click **Retry**.

**Expected outcome:**
- Retry command is enqueued
- Worker processes the retry, resets the workflow to SUBMITTED
- Workflow re-runs and (likely) completes successfully
- New events appear in the log

### Cancel a Running Workflow

1. Create a new workflow (any config).
2. While it's in PROCESSING state, click **Cancel**.

**Expected outcome:**
- Cancel command is enqueued
- Worker marks the workflow FAILED with `error.type="USER"` and `message="Workflow cancelled by user"`
- New FAILED event appears in the log
- Status pill changes to red (FAILED)
- **Retry** button is disabled (USER errors are not retryable)

### Refresh State Without Stopping Stream

Click **Refresh state** to fetch the latest workflow state from the API without closing the SSE stream.

---

## Architecture & Data Flow

```
┌─────────────────────────┐
│   Vite Dev Server       │
│   http://localhost:5173 │
│   (React UI)            │
└───────────┬─────────────┘
            │ http (proxied via Vite)
            ▼
┌─────────────────────────┐       ┌──────────────────┐
│   FastAPI (port 8000)   │◄────► │  PostgreSQL 12   │
│   (/api/v1/workflows)   │       │  localhost:5432  │
│   - GET /workflows/{id} │       └──────────────────┘
│   - POST /workflows     │
│   - POST /retry         │       ┌──────────────────┐
│   - POST /cancel        │◄────► │  Redis Streams   │
│   - GET /stream (SSE)   │       │  localhost:6379  │
└───────────▲─────────────┘       └──────────────────┘
            │
            │ enqueue/dequeue
            │
┌───────────┴─────────────┐
│  WorkflowWorker         │
│  (consumes queue)       │
│  - Fetch from DB        │
│  - Run WorkflowEngine   │
│  - Persist events/state │
│  - Ack in Redis         │
└─────────────────────────┘
```

---

## Configuration & Environment

### Development Mode (Default)

When you run `make up && make dev && make worker`, the system uses:

- **Database**: PostgreSQL (localhost:5432)  
  - User: `canva_user`  
  - Password: `canva_password_dev`  
  - Database: `canva_notebooklm_db`  
- **Redis**: Redis (localhost:6379)  
- **API Credentials**: Safe dev defaults (no real secrets required)

**No .env file needed for demo mode.** The system has built-in defaults.

### Production Mode (Not for Demo)

To deploy to production or use real integrations, create a `.env` file at the repo root:

```env
ENVIRONMENT=production

# Canva
CANVA_CLIENT_ID=your_real_client_id
CANVA_CLIENT_SECRET=your_real_client_secret

# NotebookLM
NOTEBOOKLM_API_KEY=your_real_api_key

# LLM (OpenAI, Claude, etc.)
LLM_API_KEY=your_real_api_key
LLM_PROVIDER=openai

# Auth
AUTH_JWT_SECRET=your_real_jwt_secret

# Database (if not localhost)
DATABASE_HOST=prod-postgres.example.com
DATABASE_PASSWORD=prod_password

# Redis (if not localhost)
REDIS_HOST=prod-redis.example.com
```

When `ENVIRONMENT=production`, the config loader enforces all secrets. If any are missing, the app will not start.

---

## Verify Everything Works

Run these commands in order from separate terminals:

```bash
# Terminal 1: Start services
make up

# Terminal 2: Start API
make dev

# Terminal 3: Start worker
make worker

# Terminal 4: Start UI
make ui-install  # (first time only)
make ui
```

Then:

1. Open http://localhost:5173
2. Create a workflow and watch it progress
3. Refresh and reload to replay events
4. Test retry and cancel
5. Check logs in each terminal for any errors

**If all three services are running and the UI loads, the demo is ready.**

---

## Troubleshooting

### `make dev` fails with "ValidationError: ... required"

**Cause**: Missing required env vars (even though they should have safe defaults).

**Fix**: Ensure you ran `make up` first (PostgreSQL/Redis must be running). Then restart the API:

```bash
make dev
```

If you get the error, check the backend logs for the exact missing field and provide a default in `src/config.py` if needed.

### `make worker` does not start / "No module named"

**Cause**: Incorrect import path in Makefile.

**Fix**: Verify Makefile has:
```makefile
worker:
    $(PYTHON) -c "import asyncio; from src.workers.workflow_worker import run_worker_loop; asyncio.run(run_worker_loop())"
```

### SSE stream not connecting / "Unable to open event stream"

**Cause**: Worker not running or not processing tasks.

**Fix**:
- Ensure `make worker` is running in another terminal.
- Check the worker terminal for errors (e.g., database connection failures).
- If the worker is stuck, kill it (`Ctrl+C`) and restart.

### UI shows "Stream idle" after creating workflow

**Cause**: Worker didn't process the task in time.

**Fix**: Click **Reconnect Stream** in the UI, or wait a few seconds and refresh the page.

### Database migrations not applied

**Cause**: Alembic migrations haven't run.

**Fix**: The system auto-creates tables on startup via `database.create_tables()` in `src/main.py`. If that fails, manually:

```bash
$(PYTHON) scripts/setup_db.py init
```

---

## Automated E2E Testing

The UI includes comprehensive Playwright E2E tests that validate the complete user flow from browser interaction through API, worker, database, and SSE streaming.

### Quick Test Run

```bash
# First-time setup (installs Playwright browsers)
make e2e-install

# Run all E2E tests (headless)
make e2e

# Run with visual browser (watch tests execute)
make e2e-headed

# Open Playwright UI for interactive debugging
make e2e-ui
```

### Test Coverage

The E2E test suite validates:
- Workflow creation and live progress streaming
- State persistence and SSE event replay after page reload
- Retry flow for failed workflows
- Cancel flow for running workflows
- Progress bar updates
- Multiple independent workflows
- Error handling and UI state transitions

### Prerequisites for E2E Tests

Before running tests, ensure backend services are running:

```bash
# Terminal 1: Data services
make up

# Terminal 2: API (use 'api' target for stable non-reload mode)
make api

# Terminal 3: Worker
make worker
```

**Full E2E Testing Guide**: See [E2E_TESTING_GUIDE.md](E2E_TESTING_GUIDE.md) for:
- Detailed test architecture and data flow
- Troubleshooting test failures
- Writing new E2E tests
- CI/CD integration examples
- Performance considerations

---

## Next Steps (Beyond MVP)

This MVP UI provides a bare minimum demo. In future phases (T2.9+), you can add:

- User authentication and multi-tenant dashboard
- Workflow template library and parameter form builder
- Real-time artifact preview (images, PDFs, etc.)
- Workflow history and bulk operations
- Performance monitoring and analytics dashboard
- Production-ready error handling and retry UI

For now, the demo is sufficient to visualize the end-to-end system working.

