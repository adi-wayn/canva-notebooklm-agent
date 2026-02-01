# Step 2 Validation: Canva OAuth + Design Creation

## Quick Start (10 minutes)

```bash
# Step 1: Start the smoke test
make smoke-canva

# Step 2: Complete OAuth (in browser)
# - Open URL printed in terminal
# - Click "Connect Canva"
# - Authorize in Canva OAuth screen
# - Wait for script to detect connection (checks database)

# Step 3: Test design creation (after OAuth)
make smoke-canva-design

# Step 4: Verify in UI
# - Open http://localhost:5173 (frontend)
# - See artifact card with design
# - Click "🎨 Open in Canva"
# - Should open real design in Canva editor
```

---

## What Gets Tested

### Test 1: Database & Migrations ✓
- PostgreSQL running
- `user_connections` table exists
- Alembic migration applied successfully
- **How to verify**: `SELECT COUNT(*) FROM user_connections;`

### Test 2: OAuth Endpoints ✓
- GET `/api/v1/auth/canva/authorize` - generates state token
- GET `/api/v1/auth/canva/status` - returns connection status
- **How to verify**: curl commands in script output

### Test 3: OAuth Flow (Manual) ✓
- Click authorize → redirected to Canva OAuth
- Canva OAuth → code generated → token stored
- Row inserted into `user_connections` table
- **How to verify**: Check script detection message

### Test 4: Design Creation ✓
- Real Canva API called: `POST /v1/designs`
- Design ID returned and stored
- Artifact created with `canva_design` type
- URL format: `https://www.canva.com/design/{id}/edit`
- **How to verify**: Click "Open in Canva" button

---

## Step-by-Step Instructions

### 1. Run Smoke Test
```bash
make smoke-canva
```

**Expected Output:**
```
=== Starting services (PostgreSQL + Redis) ===
[INFO] Running: make up
[✓] Services started

=== Running Alembic migrations ===
[INFO] Command: .venv/bin/alembic upgrade head
[✓] Migrations applied successfully

=== Starting API server ===
[✓] API is ready on http://localhost:8000

=== Verifying OAuth endpoints ===
[✓] OAuth authorize endpoint is available
[✓] OAuth status endpoint is available

=== OAuth Setup (Manual Step) ===

IMPORTANT: Complete OAuth flow manually

1. Open your browser:
   http://localhost:8000/api/v1/auth/canva/authorize?redirect_uri=http://localhost:5173/callback

2. Authorize with your Canva account
3. You'll be redirected - check that:
   - Browser shows: connected: true
   - Database has new row: SELECT * FROM user_connections WHERE provider='canva'
```

### 2. Complete OAuth in Browser

1. **Copy the OAuth URL** from script output
2. **Open in browser** (or click the link)
3. **Sign in to Canva** (if not already logged in)
4. **Authorize the application**:
   - Permission: "Create designs in your Canva account"
   - Click "Allow"
5. **Wait for redirect**
   - You should see a success message
   - Or redirect to http://localhost:5173/callback

### 3. Verify Database Connection

Run in terminal:
```bash
docker exec canva-notebooklm-postgres psql -U canva_user -d canva_notebooklm_db \
  -c "SELECT id, user_id, provider, account_email FROM user_connections WHERE provider='canva';"
```

**Expected Output:**
```
 id | user_id | provider | account_email
----+---------+----------+---------------
  1 | test    | canva    | user@example.com
```

If you see a row, OAuth worked! ✅

### 4. Test Design Creation

Once OAuth connection is confirmed:

```bash
make smoke-canva-design
```

**Expected Output:**
```
=== Triggering workflow to create Canva design ===
[INFO] Submitting workflow...
[✓] Workflow created: abc-def-123
[✓] ✓ Real Canva design was created
```

### 5. Verify in Frontend UI

1. **Open frontend**: http://localhost:5173
2. **Look for artifact card**:
   - Should show a design card
   - Icon: 🎨
   - Title: "Design: ..." (the title from your workflow input)
3. **Click "Open in Canva"**:
   - Should open in new tab
   - URL: `https://www.canva.com/design/{design_id}/edit`
   - Should show Canva editor
4. **Edit the design**:
   - Add text, images, etc.
   - Save in Canva
   - ✅ PROOF: Real design in Canva!

---

## Troubleshooting

### Issue: "PostgreSQL failed to become ready"
**Solution:**
```bash
# Check if container is running
docker ps | grep postgres

# If not running:
make up

# If stuck:
make clean && make up
```

### Issue: "API failed to become ready"
**Solution:**
```bash
# Check API logs
tail -50 /tmp/api.log

# If env vars missing:
python -c "from src.config import settings; print(settings.database_url)"

# Restart:
pkill -f uvicorn
make smoke-canva
```

### Issue: "Migration failed"
**Solution:**
```bash
# Check migration history
.venv/bin/alembic history

# Check current head
.venv/bin/alembic current

# If stuck at old version:
.venv/bin/alembic upgrade head -v

# Reset database (dev only):
make db-reset
make db-migrate
```

### Issue: "OAuth redirect not working"
**Possible causes:**
1. Frontend not running - start it: `cd ui && npm run dev`
2. Redirect URI mismatch - verify in Canva app settings
3. CSRF state validation failed - check logs: `tail /tmp/api.log`

**Solution:**
```bash
# Manually verify status endpoint
curl -s http://localhost:8000/api/v1/auth/canva/status | jq .

# Expected: {"connected": true, "provider": "canva", "account_email": "user@example.com"}
```

### Issue: "Design creation failed / artifact not appearing"
**Solution:**
```bash
# Check worker logs
tail -50 /tmp/worker.log

# Check database for artifact
docker exec canva-notebooklm-postgres psql -U canva_user -d canva_notebooklm_db \
  -c "SELECT * FROM artifacts WHERE type='canva_design' ORDER BY created_at DESC LIMIT 1;"

# Check Canva API token is fresh
curl -s http://localhost:8000/api/v1/auth/canva/status | jq .token_expires_at
```

---

## Validation Checklist

Use this to verify everything is working:

- [ ] **Services**: `make up` - PostgreSQL + Redis running
- [ ] **Migrations**: `.venv/bin/alembic upgrade head` - completes without errors
- [ ] **API**: `curl http://localhost:8000/health` - returns 200
- [ ] **OAuth endpoints**: `curl http://localhost:8000/api/v1/auth/canva/status` - returns JSON
- [ ] **OAuth flow**: Authorize in browser, see redirect message
- [ ] **Database**: `SELECT * FROM user_connections WHERE provider='canva'` - shows 1 row
- [ ] **Design creation**: `make smoke-canva-design` - creates real design
- [ ] **Frontend**: http://localhost:5173 - loads without errors
- [ ] **Artifact card**: Shows 🎨 icon with design title
- [ ] **Open in Canva**: Click button → opens real Canva editor

---

## Key URLs

| Service | URL | Purpose |
|---------|-----|---------|
| Frontend | http://localhost:5173 | Chat UI with artifacts |
| API Health | http://localhost:8000/health | API status check |
| OAuth Auth | http://localhost:8000/api/v1/auth/canva/authorize | Start OAuth flow |
| OAuth Status | http://localhost:8000/api/v1/auth/canva/status | Check connection |
| Swagger | http://localhost:8000/docs | API documentation |

---

## Definition of Done ✅

**Step 2 is complete when:**

1. ✅ OAuth flow works end-to-end (no mocks)
2. ✅ Token stored in `user_connections` table
3. ✅ Real Canva design created via API
4. ✅ Design URL is resolvable (opens in Canva editor)
5. ✅ Artifact renders in UI with working "Open in Canva" button
6. ✅ Can edit design in Canva (proves it's real)

**Then:** Task B complete → Proceed to Step 3 (NotebookLM)

---

## Commands Reference

```bash
# Start smoke test (Step 1)
make smoke-canva

# Test design creation (Step 2)
make smoke-canva-design

# View API logs
tail -f /tmp/api.log

# View worker logs
tail -f /tmp/worker.log

# Check database connection
make db-check

# View migrations
.venv/bin/alembic history

# Apply migrations
.venv/bin/alembic upgrade head

# Query user_connections
docker exec canva-notebooklm-postgres psql -U canva_user -d canva_notebooklm_db \
  -c "SELECT * FROM user_connections;"

# Restart services
make clean && make up
```

---

**Created**: January 18, 2026  
**Status**: Ready for Step 2 Validation  
**Next**: Run `make smoke-canva` to begin
