#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_LOG="$ROOT_DIR/.logs/api-e2e.log"
WORKER_LOG="$ROOT_DIR/.logs/worker-e2e.log"
mkdir -p "$ROOT_DIR/.logs"

cd "$ROOT_DIR"

echo "[e2e-ui] Starting docker services (postgres, redis)..."
docker compose -f docker/docker-compose.yml up -d

cleanup() {
  echo "[e2e-ui] Stopping API/worker..."
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
  [[ -n "${WORKER_PID:-}" ]] && kill "$WORKER_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Start API
echo "[e2e-ui] Starting API..."
./.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 >"$API_LOG" 2>&1 &
API_PID=$!
sleep 3

# Start worker
echo "[e2e-ui] Starting worker..."
./.venv/bin/python -m src.workers >"$WORKER_LOG" 2>&1 &
WORKER_PID=$!
sleep 3

# Health check API
if ! curl -sf http://127.0.0.1:8000/health >/dev/null; then
  echo "[e2e-ui] API failed to start. See $API_LOG" >&2
  exit 1
fi

# Seed default tenant/user for tests
SEED_SQL=$(cat <<'SQL'
INSERT INTO tenants (id, name, tier, is_active, custom_metadata, created_at, updated_at)
VALUES ('demo-tenant', 'Demo Tenant', 'pro', true, '{}', NOW(), NOW())
ON CONFLICT (name) DO NOTHING;

INSERT INTO users (id, tenant_id, email, display_name, is_active, roles, custom_metadata, created_at, updated_at)
VALUES ('demo-user', 'demo-tenant', 'demo-user@example.com', 'Demo User', true, '["user"]', '{}', NOW(), NOW())
ON CONFLICT (email) DO NOTHING;
SQL
)

docker exec canva-notebooklm-postgres psql -U canva_user -d canva_notebooklm_db -c "$SEED_SQL" >/tmp/seed.log 2>&1 || true

echo "[e2e-ui] Running Playwright UI E2E tests..."
cd "$ROOT_DIR/ui"
# Ensure deps and browsers
npm install
npx playwright install --with-deps

# Run tests with artifact outputs
npx playwright test \
  --output=test-results/e2e \
  --reporter=html

echo "[e2e-ui] Tests finished. Artifacts in ui/test-results/e2e and ui/playwright-report"
