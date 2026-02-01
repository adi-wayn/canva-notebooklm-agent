# T2.8 Demo Debugging & Troubleshooting Guide

## Pre-Flight Checklist

Before starting the demo, verify:

```bash
# 1. Venv activated
python --version  # Should show Python 3.10+

# 2. Docker running
docker ps  # Should list containers or be empty

# 3. All required ports free
lsof -i :5432  # PostgreSQL (should be empty)
lsof -i :6379  # Redis (should be empty)
lsof -i :8000  # API (should be empty)
lsof -i :5173  # UI (should be empty)
```

---

## Common Issues & Fixes

### Issue: `make dev` fails with "ValidationError"

**Symptoms:**
```
pydantic.v1.error_wrappers.ValidationError: ... field required ...
```

**Cause**: Config fields are still trying to load required values but defaults are not working.

**Fix**:
1. Verify your edits to `src/config.py` are saved:
   ```bash
   grep "default=\"dev_client_id\"" src/config.py
   # Should return a line
   ```
2. If missing, re-apply the fix:
   ```bash
   # Replace client_id: SecretStr = Field(...)
   # With: client_id: SecretStr = Field(default="dev_client_id", ...)
   ```
3. Restart the API:
   ```bash
   make dev
   ```

---

### Issue: `make worker` fails with "No module named..."

**Symptoms:**
```
ModuleNotFoundError: No module named 'src.queue.worker'
```

**Cause**: Makefile still points to old non-existent module.

**Fix**:
1. Verify Makefile has correct worker target:
   ```bash
   grep -A 2 "^worker:" Makefile
   # Should show: $(PYTHON) -c "import asyncio; from src.workers.workflow_worker..."
   ```
2. If old, update Makefile:
   ```makefile
   worker:
       $(PYTHON) -c "import asyncio; from src.workers.workflow_worker import run_worker_loop; asyncio.run(run_worker_loop())"
   ```
3. Restart worker:
   ```bash
   make worker
   ```

---

### Issue: PostgreSQL container won't start

**Symptoms:**
```
docker-compose up -d
# postgres service fails to start or exits with error
```

**Cause**: Port already in use, or previous container interfering.

**Fix**:
1. Check if port is free:
   ```bash
   lsof -i :5432
   ```
2. If in use, kill the process or use different port:
   ```bash
   docker-compose down -v  # Remove all containers + volumes
   make up                  # Restart fresh
   ```
3. Verify service is running:
   ```bash
   docker ps | grep postgres
   # Should show canva-notebooklm-postgres running
   ```

---

### Issue: Redis connection fails

**Symptoms:**
```
redis.asyncio.ConnectionError: Error 111 connecting to localhost:6379
```

**Cause**: Redis container not running or port not exposed.

**Fix**:
1. Verify Redis is running:
   ```bash
   docker ps | grep redis
   # Should show canva-notebooklm-redis running
   ```
2. If not running:
   ```bash
   make down
   make up
   sleep 5  # Wait for services to be ready
   ```
3. Test Redis manually:
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

---

### Issue: API starts but returns 500 on workflow creation

**Symptoms:**
```
POST /api/v1/workflows → 500 Internal Server Error
```

**Cause**: Usually database connection or worker not running.

**Fix**:
1. Check API logs for detailed error:
   ```bash
   # Look at make dev terminal output
   # Should see: "INFO:     Uvicorn running on http://0.0.0.0:8000"
   ```
2. Ensure worker is running in another terminal:
   ```bash
   make worker
   # Should see: "[worker-1] Worker started"
   ```
3. Test database connection:
   ```bash
   python -c "from src.storage.database import database; print('DB OK')"
   ```

---

### Issue: UI fails to load (blank page, no error)

**Symptoms:**
- Page loads but is blank (white screen)
- Console shows network errors
- UI dev server shows errors

**Cause**: Vite proxy not working or API not responding.

**Fix**:
1. Verify API is running on port 8000:
   ```bash
   curl http://localhost:8000/health
   # Should return: {"status": "healthy", ...}
   ```
2. Verify UI is on port 5173:
   ```bash
   curl http://localhost:5173/
   # Should return HTML
   ```
3. Check browser console (F12 → Console) for errors (e.g., CORS, fetch failures)
4. Restart UI dev server:
   ```bash
   # In the UI terminal, Ctrl+C
   make ui
   ```

---

### Issue: SSE stream not connecting / "Unable to open event stream"

**Symptoms:**
```
UI message: "Unable to open event stream."
Workflow stuck in SUBMITTED state.
```

**Cause**: Worker not processing tasks or database not persisting events.

**Fix**:
1. Verify worker is running and consuming tasks:
   ```bash
   # Check worker terminal output
   # Should see: "[worker-1] Processing workflow wf_..."
   ```
2. If worker is idle, manually trigger a process:
   ```bash
   python -c "
   import asyncio
   from src.workers.workflow_worker import WorkflowWorker
   asyncio.run(WorkflowWorker().process_once())
   "
   ```
3. Check worker logs for errors:
   ```bash
   # Look at make worker terminal output
   # Any exceptions or errors?
   ```
4. Verify Redis queue has tasks:
   ```bash
   redis-cli
   > XLEN workflow-queue
   # Should show > 0 if tasks are queued
   ```

---

### Issue: Workflow stuck in PROCESSING state

**Symptoms:**
- Workflow created successfully
- SSE events show progress updates
- But never reaches COMPLETED or FAILED
- Stuck at 95% for a long time

**Cause**: Worker crashed or is hanging on a task.

**Fix**:
1. Check worker terminal for errors or hangs
2. Kill worker (Ctrl+C) and restart:
   ```bash
   make worker
   ```
3. Check if workflow already has events:
   ```bash
   # In UI, click "Refresh state"
   # Does it show any progress updates?
   ```
4. Check database directly:
   ```bash
   psql -h localhost -U canva_user -d canva_notebooklm_db -c "
   SELECT id, status, custom_metadata FROM workflows LIMIT 1;
   "
   ```

---

### Issue: "Workflow is not retryable" or "Workflow is not FAILED"

**Symptoms:**
```
UI shows error but Retry button is disabled
POST /retry returns 400
```

**Cause**: Workflow error is marked `retryable=false` or workflow is not in FAILED state.

**Fix**:
1. Check error status:
   ```bash
   # In UI, check the error box
   # Does it say "Retryable: false"?
   ```
2. To test retry, force a retryable failure:
   ```json
   {
     "simulate_failure": "transient_once"
   }
   ```
3. Create workflow with this config and it will fail with retryable error
4. Then Retry button should appear

---

### Issue: Port conflict

**Symptoms:**
```
make up → "Address already in use"
make dev → "Address already in use :8000"
make ui → "Address already in use :5173"
```

**Cause**: Another service is already using the port.

**Fix**:
1. Find what's using the port:
   ```bash
   lsof -i :8000  # For API
   lsof -i :5173  # For UI
   lsof -i :5432  # For Postgres
   lsof -i :6379  # For Redis
   ```
2. Kill the process:
   ```bash
   kill -9 <PID>
   ```
3. Or use a different port:
   ```bash
   # In Makefile, change port 8000 → 8001, etc.
   # In vite.config.js, change port 5173 → 5174, etc.
   ```

---

## Debug Commands Cheat Sheet

```bash
# 1. Check all services
docker ps

# 2. Check Redis queue
redis-cli XLEN workflow-queue

# 3. Check database
psql -h localhost -U canva_user -d canva_notebooklm_db -c "SELECT COUNT(*) FROM workflows;"

# 4. Check API health
curl -H "X-Tenant-ID: test" http://localhost:8000/health

# 5. Check config loads
python -c "from src.config import settings; print(settings.environment)"

# 6. Check worker imports
python -c "from src.workers.workflow_worker import run_worker_loop; print('OK')"

# 7. Check UI webpack (if Vite has build errors)
cd ui && npm run build

# 8. Full reset (careful: deletes database)
make clean
make setup
```

---

## Logs to Check

### API Logs (make dev terminal)
- Watch for `INFO: Uvicorn running on...`
- Look for stack traces on requests
- Check for database connection errors

### Worker Logs (make worker terminal)
- Watch for `[worker-1] Worker started`
- Check for `Processing workflow wf_...`
- Look for task failures or exceptions

### UI Logs (make ui terminal)
- Check for Vite compilation errors
- Look for `ready in XXX ms`
- Check browser console (F12) for runtime errors

### Docker Logs
```bash
docker logs canva-notebooklm-postgres  # DB logs
docker logs canva-notebooklm-redis     # Redis logs
```

---

## Getting Help

If you're stuck:

1. **Check the docs**:
   - documents/UI_DEMO.md (main guide)
   - documents/LOCAL_DEV_RUN_FIXES.md (what was changed)
   - T28_COMPLETION_CHECKLIST.md (what should be working)

2. **Check logs** in each terminal (API, worker, UI, docker)

3. **Reset and retry**:
   ```bash
   make down        # Stop services
   make clean       # Remove all volumes
   make up          # Start fresh
   make dev         # API
   # (in new terminal) make worker
   # (in new terminal) make ui
   ```

4. **Verify config**:
   ```bash
   python -c "from src.config import settings; print(f'ENV={settings.environment}, CANVA_ID={settings.canva.client_id.get_secret_value()}')"
   ```

---

**Remember**: The demo should work without any real credentials. If you're hitting validation errors on auth or external integrations, it means a default value was not applied correctly. Check `src/config.py` for the fixes.
