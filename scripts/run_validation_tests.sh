#!/bin/bash
# Quick Reference: How to Run the Validated Tests

## Prerequisites
# - Docker running (for postgres + redis)
# - Python 3.10+ with dependencies installed

## Test Execution Steps

### 1. START SERVICES
echo "Starting Docker services..."
cd "$(dirname "$0")"
make up
sleep 5

### 2. START API (Terminal 1)
echo "Starting API..."
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload > /tmp/api.log 2>&1 &
sleep 3

### 3. START WORKER (Terminal 2)  
echo "Starting worker..."
python -m src.workers > /tmp/worker.log 2>&1 &
WORKER_PID=$!
sleep 2

### 4. RUN STEP A - EVENT PERSISTENCE
echo ""
echo "========================================"
echo "STEP A: Event Persistence"
echo "========================================"

# Create workflow
WF_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/workflows \
  -H 'X-Tenant-ID: demo-tenant' \
  -H 'Content-Type: application/json' \
  -d '{"design_id": "test-design-abc", "source_id": "test-source-xyz"}')

WF_ID=$(echo "$WF_RESPONSE" | jq -r '.id')
echo "Created workflow: $WF_ID"

# Wait for processing
echo "Waiting 12 seconds for workflow completion..."
sleep 12

# Query Postgres
echo ""
echo "Querying Postgres for events..."
python check_step_a.py "$WF_ID"

### 5. RUN STEP B - SSE REPLAY
echo ""
echo "========================================"
echo "STEP B: SSE Replay from Postgres"
echo "========================================"
echo "Streaming events from SSE endpoint..."
echo ""

timeout 3 curl -s -N -H 'X-Tenant-ID: demo-tenant' \
  "http://localhost:8000/api/v1/workflows/$WF_ID/stream?last_event_id=0" 2>/dev/null | \
  head -30 || true

### 6. CLEANUP
echo ""
echo "========================================"
echo "Cleaning up..."
echo "========================================"
kill $WORKER_PID 2>/dev/null || true
pkill -f "uvicorn" || true
sleep 1
echo "✅ Tests complete!"
echo ""
echo "Expected Results:"
echo "  Step A: 8 events in Postgres with terminal status COMPLETED"
echo "  Step B: 8 SSE frames with matching event IDs 2574-2581"
echo ""
echo "If both pass → Architecture is validated ✅"
echo "If both pass but UI still fails → Frontend issue (Step C debug)"
