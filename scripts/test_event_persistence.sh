#!/bin/bash
set -e

TENANT_ID="demo-tenant"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

echo "====== A. EVENT PERSISTENCE TEST ======"
echo ""

# Start services if not already running
echo "[1/6] Checking services..."
docker compose -f docker/docker-compose.yml ps | grep -E "postgres|redis" | wc -l > /dev/null || docker compose -f docker/docker-compose.yml up -d
sleep 2

# Start API
echo "[2/6] Starting API..."
pkill -9 -f "uvicorn src.main" 2>/dev/null || true
sleep 1
source .venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &
API_PID=$!
sleep 3

# Start worker
echo "[3/6] Starting worker..."
pkill -9 -f "src.workers" 2>/dev/null || true
rm -f /tmp/worker.log
python -m src.workers > /tmp/worker.log 2>&1 &
WORKER_PID=$!
sleep 3

# Create workflow
echo "[4/6] Creating workflow..."
WF_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/workflows \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: $TENANT_ID" \
  -d '{"user_id": "demo-user", "tenant_id": "'$TENANT_ID'", "config": {}}')

WORKFLOW_ID=$(echo "$WF_RESPONSE" | jq -r '.id')
echo "Created workflow: $WORKFLOW_ID"
echo "Response: $WF_RESPONSE" | jq .

# Wait for worker to process
echo "[5/6] Waiting for worker to process..."
sleep 12

# Query database
echo "[6/6] Querying Postgres for events..."
EVENTS=$(PGPASSWORD="canva_password_dev" psql -h 127.0.0.1 -p 55432 -U canva_user -d canva_notebooklm_db -t -c \
  "SELECT id, workflow_id, event_type, payload->>'new_status' as new_status FROM workflow_events WHERE workflow_id = '$WORKFLOW_ID' ORDER BY id;" 2>&1)

echo "Events found:"
echo "$EVENTS"

# Count events
EVENT_COUNT=$(echo "$EVENTS" | wc -l)
echo ""
echo "====== RESULT ======"
echo "Workflow ID: $WORKFLOW_ID"
echo "Event rows: $EVENT_COUNT"

if [ "$EVENT_COUNT" -gt 0 ]; then
  echo "✓ Events persisted to Postgres"
else
  echo "✗ NO events found in Postgres"
fi

# Cleanup
echo ""
echo "Cleaning up..."
kill $API_PID 2>/dev/null || true
kill $WORKER_PID 2>/dev/null || true
wait 2>/dev/null || true

echo ""
echo "====== NEXT STEP ======"
echo "Run: curl -N -H 'X-Tenant-ID: $TENANT_ID' 'http://localhost:8000/api/v1/workflows/$WORKFLOW_ID/stream?last_event_id=0' | head -30"
echo ""
