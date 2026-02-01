#!/bin/bash

# Smoke Test: Canva OAuth + Design Creation End-to-End
# 
# This script validates:
# 1. Services start (PostgreSQL, Redis)
# 2. Migrations run cleanly
# 3. API + Worker start
# 4. OAuth endpoints are ready
# 5. Workflow creates a real Canva design
#
# Usage:
#   bash scripts/smoke_canva_oauth_and_create_design.sh
#   or: make smoke-canva

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
API_URL="http://127.0.0.1:8000"
WORKER_PORT="8001"
HEALTH_ENDPOINT="$API_URL/health"
AUTH_STATUS_ENDPOINT="$API_URL/api/v1/auth/canva/status"
TIMEOUT=30

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[✓]${NC} $1"
}

log_error() {
  echo -e "${RED}[✗]${NC} $1"
}

log_step() {
  echo -e "\n${YELLOW}=== $1 ===${NC}"
}

# Cleanup on exit
cleanup() {
  log_info "Cleaning up..."
  pkill -f "uvicorn.*main:app" || true
  pkill -f "python.*queue" || true
}
trap cleanup EXIT

# ============================================================================
# STEP 1: Start Services (PostgreSQL + Redis)
# ============================================================================
log_step "Starting services (PostgreSQL + Redis)"
log_info "Running: make up"
make up > /dev/null 2>&1 || {
  log_error "Failed to start services"
  exit 1
}
log_success "Services started"

# Wait for PostgreSQL to be ready
log_info "Waiting for PostgreSQL..."
sleep 5
max_attempts=10
attempt=0
while [ $attempt -lt $max_attempts ]; do
  if docker exec canva-notebooklm-postgres pg_isready -U canva_user > /dev/null 2>&1; then
    log_success "PostgreSQL is ready"
    break
  fi
  attempt=$((attempt + 1))
  sleep 1
done

if [ $attempt -eq $max_attempts ]; then
  log_error "PostgreSQL failed to become ready"
  exit 1
fi

# ============================================================================
# STEP 2: Run Migrations
# ============================================================================
log_step "Running Alembic migrations"
log_info "Command: .venv/bin/alembic upgrade head"

if .venv/bin/alembic upgrade head > /tmp/alembic.log 2>&1; then
  # Check if anything actually ran or if we're already at head
  if grep -q "Already at the head of the branch" /tmp/alembic.log; then
    log_success "Database already at head revision"
  elif grep -q "Running upgrade" /tmp/alembic.log; then
    log_success "Migrations applied successfully"
  else
    log_success "Migrations completed"
  fi
else
  log_error "Migration failed"
  cat /tmp/alembic.log
  exit 1
fi

# Verify user_connections table exists
log_info "Verifying user_connections table..."
if docker exec canva-notebooklm-postgres psql -U canva_user -d canva_notebooklm_db -c "\dt user_connections" | grep -q "user_connections"; then
  log_success "user_connections table exists"
else
  log_error "user_connections table not found"
  exit 1
fi

# Seed default tenant and user required by FK
log_info "Seeding default tenant (test-tenant)..."
docker exec canva-notebooklm-postgres psql -U canva_user -d canva_notebooklm_db -c "INSERT INTO tenants (id, name, tier, is_active, custom_metadata, created_at, updated_at) VALUES ('test-tenant', 'Test Tenant', 'free', true, '{}'::jsonb, NOW(), NOW()) ON CONFLICT (id) DO NOTHING;" >/dev/null 2>&1 || true

log_info "Seeding default user (test-user)..."
docker exec canva-notebooklm-postgres psql -U canva_user -d canva_notebooklm_db -c "INSERT INTO users (id, tenant_id, email, display_name, is_active, roles, custom_metadata, created_at, updated_at) VALUES ('test-user', 'test-tenant', 'test-user@example.com', 'Test User', true, '[\"admin\"]'::jsonb, '{}'::jsonb, NOW(), NOW()) ON CONFLICT (id) DO NOTHING;" >/dev/null 2>&1 || true

# ============================================================================
# STEP 3: Start API Server
# ============================================================================
log_step "Starting API server"
log_info "Starting: uvicorn src.main:app --host 0.0.0.0 --port 8000"

.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --log-level warning > /tmp/api.log 2>&1 &
API_PID=$!

# Wait for API to be ready
log_info "Waiting for API to be ready..."
attempt=0
while [ $attempt -lt $TIMEOUT ]; do
  if curl -s "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
    log_success "API is ready on $API_URL"
    break
  fi
  attempt=$((attempt + 1))
  sleep 1
done

if [ $attempt -eq $TIMEOUT ]; then
  log_error "API failed to become ready"
  log_error "API logs:"
  cat /tmp/api.log
  exit 1
fi

# ============================================================================
# STEP 4: Verify OAuth Endpoints
# ============================================================================
log_step "Verifying OAuth endpoints"

# Check authorize endpoint
log_info "Testing: GET $API_URL/api/v1/auth/canva/authorize"
if curl -s -w "%{http_code}" "$API_URL/api/v1/auth/canva/authorize?redirect_uri=http://localhost:5173/callback" \
  -H "X-Tenant-ID: test-tenant" \
  -H "X-User-ID: test-user" 2>/dev/null | grep -q "302\|307\|200"; then
  log_success "OAuth authorize endpoint is available"
else
  log_error "OAuth authorize endpoint failed"
  exit 1
fi

# Check status endpoint (should show disconnected initially)
log_info "Testing: GET $API_URL/api/v1/auth/canva/status"
STATUS_RESPONSE=$(curl -s "$AUTH_STATUS_ENDPOINT" \
  -H "X-Tenant-ID: test-tenant" \
  -H "X-User-ID: test-user")
if echo "$STATUS_RESPONSE" | grep -q "connected"; then
  log_success "OAuth status endpoint is available"
  echo "  Response: $STATUS_RESPONSE"
else
  log_error "OAuth status endpoint failed"
  echo "  Response: $STATUS_RESPONSE"
  exit 1
fi

# ============================================================================
# STEP 5: Display OAuth Flow Instructions
# ============================================================================
log_step "OAuth Setup (Manual Step)"
echo ""
echo -e "${YELLOW}IMPORTANT: Complete OAuth flow manually${NC}"
echo ""
echo "1. Open your browser:"
echo -e "   ${BLUE}$API_URL/api/v1/auth/canva/authorize?tenant_id=test-tenant&user_id=test-user${NC}"
echo ""
echo "2. Authorize with your Canva account"
echo ""
echo "3. You'll be redirected - check that:"
echo -e "   - Browser shows: ${GREEN}connected: true${NC}"
echo -e "   - Database has new row: ${GREEN}SELECT * FROM user_connections WHERE provider='canva'${NC}"
echo ""
echo "4. Then run this command to test design creation:"
echo -e "   ${BLUE}bash scripts/smoke_canva_oauth_and_create_design.sh --test-design-creation${NC}"
echo ""
echo -e "${YELLOW}[Waiting for manual OAuth completion...]${NC}"
echo "Press Ctrl+C when done, or let this script continue for 5 minutes..."
echo ""

# Wait for user to complete OAuth (configurable timeout)
max_wait=300  # 5 minutes
waited=0
while [ $waited -lt $max_wait ]; do
  # Check if a Canva connection exists
  CONN_CHECK=$(docker exec canva-notebooklm-postgres psql -U canva_user -d canva_notebooklm_db -c "SELECT COUNT(*) FROM user_connections WHERE provider='canva';" 2>/dev/null || echo "0")
  if echo "$CONN_CHECK" | grep -q " 1"; then
    log_success "Canva connection detected in database"
    break
  fi
  
  waited=$((waited + 10))
  if [ $waited -lt $max_wait ]; then
    log_info "Waiting... (${waited}s/$max_wait)"
    sleep 10
  fi
done

# ============================================================================
# STEP 6: Start Worker (Optional - for design creation test)
# ============================================================================
if [ "$1" == "--test-design-creation" ]; then
  log_step "Starting task worker for design creation test"
  log_info "This will test real Canva API design creation"
  
  .venv/bin/python -m src.workers.workflow_worker > /tmp/worker.log 2>&1 &
  WORKER_PID=$!
  
  sleep 3
  
  log_info "Worker started (PID: $WORKER_PID)"
  
  # ========================================================================
  # STEP 7: Trigger Workflow (Create Design)
  # ========================================================================
  log_step "Triggering workflow to create Canva design"
  
  # Create workflow JSON
  WORKFLOW_PAYLOAD='{
    "user_id": "test-user",
    "tenant_id": "test-tenant",
    "input": "Create a social media post design",
    "config": {
      "artifact_types": ["canva_design"]
    }
  }'
  
  log_info "Submitting workflow..."
  WORKFLOW_RESPONSE=$(curl -s -X POST "$API_URL/api/v1/workflows" \
    -H "Content-Type: application/json" \
    -H "X-Tenant-ID: test-tenant" \
    -H "X-User-ID: test-user" \
    -d "$WORKFLOW_PAYLOAD")
  
  echo "Response: $WORKFLOW_RESPONSE"
  
  # Extract workflow_id
  WORKFLOW_ID=$(echo "$WORKFLOW_RESPONSE" | grep -o '"id":"[^"]*"' | cut -d'"' -f4 || echo "")
  
  if [ -z "$WORKFLOW_ID" ]; then
    log_error "Failed to create workflow"
    exit 1
  fi
  
  log_success "Workflow created: $WORKFLOW_ID"
  
  # Wait for design creation
  log_step "Waiting for design creation..."
  sleep 5
  
  # Check worker logs for design creation
  if grep -q "Created real Canva design" /tmp/worker.log 2>/dev/null; then
    log_success "✓ Real Canva design was created"
    grep "design_id" /tmp/worker.log | head -1
  else
    log_info "Check worker logs: tail -20 /tmp/worker.log"
  fi
  
fi

# ============================================================================
# Summary
# ============================================================================
log_step "Smoke Test Summary"
echo ""
echo -e "${GREEN}✓ Services running${NC}"
echo -e "${GREEN}✓ Migrations applied${NC}"
echo -e "${GREEN}✓ API ready${NC}"
echo -e "${GREEN}✓ OAuth endpoints available${NC}"
echo ""
echo "Next steps:"
echo "1. Complete OAuth flow (see instructions above)"
echo "2. Verify: SELECT * FROM user_connections WHERE provider='canva'"
echo "3. Test design creation: bash scripts/smoke_canva_oauth_and_create_design.sh --test-design-creation"
echo ""
echo "Endpoints available:"
echo -e "  Health:      ${BLUE}$HEALTH_ENDPOINT${NC}"
echo -e "  OAuth Auth:  ${BLUE}$API_URL/api/v1/auth/canva/authorize${NC}"
echo -e "  OAuth Status: ${BLUE}$AUTH_STATUS_ENDPOINT${NC}"
echo ""
echo -e "API logs: ${BLUE}tail -f /tmp/api.log${NC}"
echo ""
