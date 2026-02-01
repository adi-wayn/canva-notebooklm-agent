# E2E Testing Guide for Workflow Demo UI

## Overview

This guide covers end-to-end (E2E) testing of the Workflow Demo UI using Playwright. These tests validate the complete user flow from browser interaction through the API, worker, database, and SSE stream back to the UI.

## Test Coverage

The E2E test suite (`ui/tests/e2e/workflow.spec.js`) validates:

1. **Basic UI Load**: Main screen displays all components
2. **Workflow Creation**: Create workflow → observe live progress → reach terminal state
3. **SSE Event Streaming**: Live events appear in UI during workflow execution
4. **State Persistence & Replay**: Reload page → load by ID → events replay from database
5. **Retry Flow**: Failed retryable workflow → retry button enabled → retry succeeds
6. **Cancel Flow**: Running workflow → cancel → transitions to FAILED with USER error
7. **Non-Retryable Failures**: Permanent failures → retry button disabled
8. **Progress Bar**: Visual progress updates during workflow execution
9. **Multiple Workflows**: Create/load multiple workflows independently

## Prerequisites

### System Requirements

- Node.js 16+ with npm
- Python 3.10+ with dependencies installed
- Docker and docker-compose
- Playwright browsers (installed via `make e2e-install`)

### Running Services

Before running E2E tests, ensure all backend services are running:

```bash
# Terminal 1: Start data services
make up

# Terminal 2: Start API (non-reload mode for tests)
make api

# Terminal 3: Start worker
make worker
```

**Important**: Use `make api` (not `make dev`) for tests. The `api` target runs uvicorn without `--reload`, which is more stable for automated testing.

## Installation

### First-Time Setup

```bash
# Install UI dependencies and Playwright browsers
make e2e-install
```

This command:
- Runs `npm install` in the `ui/` directory
- Installs Playwright with Chromium and system dependencies
- Takes ~2-5 minutes depending on network speed

### Manual Installation (if needed)

```bash
cd ui
npm install
npx playwright install --with-deps
```

## Running Tests

### Headless Mode (CI/Automated)

```bash
# Run all E2E tests in headless mode
make e2e
```

**Output:**
```
Running 8 tests using 1 worker

  ✓ should load UI and display main screen (2s)
  ✓ should create workflow and observe live progress to completion (28s)
  ✓ should reload page and replay workflow events (35s)
  ✓ should handle retry for retryable failed workflow (32s)
  ✓ should handle cancel for running workflow (18s)
  ✓ should show retry button only for retryable failures (30s)
  ✓ should display and update progress bar (12s)
  ✓ should handle multiple workflows independently (45s)

  8 passed (202s)
```

### Headed Mode (Visual/Interactive)

```bash
# Run tests with visible browser windows
make e2e-headed
```

This opens Chromium windows so you can watch the tests execute in real time. Useful for:
- Understanding test flow
- Debugging test failures
- Demoing the system behavior

### Playwright UI Mode (Best for Development)

```bash
# Open Playwright's interactive test runner
make e2e-ui
```

**Features:**
- Visual test timeline
- Step-by-step execution
- Live DOM snapshots
- Network activity viewer
- Ability to debug individual tests

### Running Specific Tests

```bash
cd ui

# Run a single test by name
npm run e2e -- --grep "should create workflow"

# Run tests in a specific file
npm run e2e -- workflow.spec.js

# Run with debug mode (stops at breakpoints)
npm run e2e:debug
```

## Test Architecture

### Data Flow

```
┌─────────────┐
│  Playwright │
│  (Browser)  │
└──────┬──────┘
       │ http://127.0.0.1:5173
       ▼
┌─────────────┐       ┌──────────────┐
│  Vite Dev   │ proxy │  FastAPI     │
│  Server     │──────▶│  :8000       │
│  :5173      │       └──────┬───────┘
└──────┬──────┘              │
       │                     │
       │ SSE Stream          │ enqueue
       │                     ▼
       │              ┌──────────────┐
       │              │  Redis Queue │
       │              └──────┬───────┘
       │                     │ dequeue
       │                     ▼
       │              ┌──────────────┐       ┌────────────┐
       └──────────────│  Worker      │◄─────▶│  Postgres  │
                      └──────────────┘       └────────────┘
```

### Test Selectors

Tests use `data-testid` attributes for stable element selection:

| Selector | Element |
|----------|---------|
| `tenant-input` | Tenant ID input field |
| `user-input` | User ID input field |
| `config-input` | Config JSON textarea |
| `create-workflow-btn` | Create Workflow button |
| `workflow-id-input` | Load workflow ID input |
| `load-workflow-btn` | Load & Stream button |
| `workflow-status` | Status pill (SUBMITTED, COMPLETED, etc.) |
| `workflow-id` | Workflow ID display text |
| `workflow-step` | Current step and progress % |
| `workflow-error` | Error message box |
| `error-retryable` | Retryable flag display |
| `retry-btn` | Retry button |
| `cancel-btn` | Cancel button |
| `event-log` | Event log container |
| `event-entry` | Individual event log entry |
| `workflow-artifacts` | Artifacts list |
| `progress-bar` | Progress bar fill |

### Timeouts

- **Test timeout**: 60 seconds per test
- **Assertion timeout**: 10 seconds per expect()
- **Workflow completion**: 30 seconds max wait for terminal state
- **SSE connection**: 10 seconds max wait for first event

## Troubleshooting

### Tests Hang or Timeout

**Symptom**: Tests wait forever and eventually timeout.

**Causes & Fixes**:

1. **Backend not running**:
   ```bash
   # Verify all services are up
   curl http://localhost:8000/health  # Should return JSON
   curl http://localhost:5173/        # Should return HTML
   redis-cli ping                      # Should return PONG
   docker ps | grep postgres           # Should show running container
   ```

2. **Worker not processing**:
   ```bash
   # Check worker terminal for errors
   # Should see: "[worker-1] Worker started"
   
   # Restart worker if needed
   # Ctrl+C in worker terminal, then:
   make worker
   ```

3. **Port conflicts**:
   ```bash
   lsof -i :8000  # API port
   lsof -i :5173  # UI port
   lsof -i :5432  # Postgres
   lsof -i :6379  # Redis
   ```

### Test Failures

**Symptom**: Tests fail with assertion errors.

**Debug steps**:

1. **Run in headed mode** to see what's happening:
   ```bash
   make e2e-headed
   ```

2. **Check screenshots and traces**:
   ```bash
   cd ui
   npx playwright show-report
   ```
   This opens an HTML report with screenshots, traces, and network logs.

3. **Run with debug mode**:
   ```bash
   cd ui
   npm run e2e:debug -- --grep "failing test name"
   ```
   This opens Playwright Inspector for step-by-step debugging.

### Specific Test Issues

#### "should create workflow" fails

- **Check**: API is running (`curl http://localhost:8000/health`)
- **Check**: Worker is consuming queue (see worker terminal output)
- **Check**: Database is accessible (worker logs should not show DB errors)

#### "should reload page and replay" fails

- **Check**: Events are persisted to database (not just in-memory)
- **Check**: SSE replay logic is working (check API logs for `Last-Event-ID` header)

#### "should handle retry" fails

- **Check**: Worker recognizes `simulate_failure` config flag
- **Check**: Retry endpoint enqueues action correctly
- **Check**: Worker processes retry actions (see worker logs)

#### "should handle cancel" fails

- **Check**: Cancel endpoint is working (`POST /api/v1/workflows/{id}/cancel`)
- **Check**: Worker handles cancel action (marks as FAILED with USER error)

### Browser Issues

**Symptom**: Playwright can't launch browser.

**Fix**:
```bash
cd ui
npx playwright install --with-deps
```

This reinstalls browser binaries and system dependencies.

### Network Issues

**Symptom**: Tests can't connect to API or UI.

**Fix**:
1. Verify Vite proxy is configured correctly in `ui/vite.config.js`:
   ```js
   proxy: {
     '/api': {
       target: 'http://localhost:8000',
       changeOrigin: true,
     },
   }
   ```

2. Ensure API is bound to `0.0.0.0` (not `127.0.0.1` only):
   ```bash
   make api  # Should bind to 0.0.0.0:8000
   ```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Setup Node
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: |
          pip install -r src/requirements.txt
          make ui-install
          make e2e-install
      
      - name: Start services
        run: |
          make up
          make api &
          make worker &
          sleep 10  # Wait for services to be ready
      
      - name: Run E2E tests
        run: make e2e
      
      - name: Upload test artifacts
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: ui/playwright-report/
```

## Writing New E2E Tests

### Test Template

```javascript
test('should do something useful', async ({ page }) => {
  await page.goto('/');
  
  // Arrange: Set up initial state
  await page.getByTestId('config-input').fill(JSON.stringify({
    custom_config: "value"
  }));
  
  // Act: Perform user action
  await page.getByTestId('create-workflow-btn').click();
  
  // Assert: Verify expected outcome
  await expect(page.getByTestId('workflow-status')).toHaveText('SUBMITTED', { timeout: 10000 });
});
```

### Best Practices

1. **Use data-testid over CSS selectors**: More stable across UI changes
2. **Set explicit timeouts**: Don't rely on defaults for async operations
3. **Verify intermediate states**: Not just final outcomes
4. **Clean up after tests**: Each test should be independent
5. **Test real user flows**: Not just API responses

### Adding New Selectors

If you need to test a new UI element:

1. Add `data-testid` attribute in `ui/src/App.jsx`:
   ```jsx
   <button data-testid="my-new-button">Click Me</button>
   ```

2. Use in test:
   ```javascript
   await page.getByTestId('my-new-button').click();
   ```

## Performance Considerations

- **Sequential execution**: Tests run one at a time (`workers: 1`) to avoid race conditions on shared backend
- **No retries**: `retries: 0` ensures tests are deterministic
- **Trace on failure**: Captures full context only when tests fail
- **Video on failure**: Records video only for failing tests to save space

## Next Steps

- Add visual regression tests (screenshots comparison)
- Add accessibility tests (a11y audits)
- Add performance tests (page load times, SSE latency)
- Add mobile viewport tests
- Add cross-browser tests (Firefox, WebKit)

---

**For questions or issues, check**:
- `ui/playwright.config.js` — Test configuration
- `ui/tests/e2e/workflow.spec.js` — Test implementations
- `documents/UI_DEMO.md` — Manual testing guide
- `documents/TROUBLESHOOTING_T28.md` — Backend troubleshooting
