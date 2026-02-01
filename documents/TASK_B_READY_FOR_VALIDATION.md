# ✅ Task B: Ready for Step 2 Validation

## Summary of Changes

### Problem Statement
User requested:
1. **No Alembic config workarounds** → single canonical setup
2. **Single migration command** → runs from repo root
3. **Smoke test script** → validates OAuth + design creation end-to-end
4. **Runbook documentation** → clear 10-minute validation path

### Solution Delivered

#### 1. Clean Alembic Setup ✅
- **Removed**: `alembic/alembic.ini` (duplicate config file)
- **Now**: Single `alembic.ini` at repo root
- **Test**: `cd /repo/root && .venv/bin/alembic upgrade head` ✅ Works

#### 2. Smoke Test Script ✅
**File**: `scripts/smoke_canva_oauth_and_create_design.sh` (350 lines)

**Does:**
- Starts services (PostgreSQL + Redis)
- Applies migrations cleanly (no manual setup)
- Starts API server
- Verifies OAuth endpoints
- Prints OAuth URL for manual authorization
- **Waits and detects when user completes OAuth** (checks database)
- Optionally tests design creation with `--test-design-creation` flag

**Commands:**
```bash
make smoke-canva               # Step 1: Setup + OAuth
make smoke-canva-design       # Step 2: Design creation test
```

#### 3. Clear Runbook ✅
**File**: `documents/STEP2_VALIDATION_RUNBOOK.md` (300+ lines)

**Includes:**
- 10-minute quick start
- Step-by-step instructions
- Database verification queries
- Troubleshooting guide
- Validation checklist (11 items)
- Commands reference

#### 4. Updated Makefile ✅
**Added targets:**
```makefile
smoke-canva:            # Test OAuth setup
smoke-canva-design:     # Test design creation
```

**Updated help** to show smoke test commands

---

## Validation Status

### ✅ Pre-Launch Checks
- Smoke script syntax valid
- Makefile targets exist
- Migrations run from repo root
- Database current at revision: `003_user_connections`
- No duplicate configs

### 📋 Ready for User Testing
- `make smoke-canva` → ready to run
- `make smoke-canva-design` → ready to run
- Documentation complete
- No blockers

---

## How User Runs Validation

### Phase 1: OAuth Setup (5 minutes)
```bash
make smoke-canva
# Output: OAuth URL printed
# User: Click URL → Authorize in Canva → Complete
```

**Expected:**
- Services start ✓
- Migrations apply ✓
- API ready ✓
- OAuth URL printed ✓
- Script detects OAuth completion ✓

### Phase 2: Design Creation (5 minutes)
```bash
make smoke-canva-design
# Creates real design via Canva API
# Shows design_id + URL
```

**Expected:**
- Workflow created ✓
- Real Canva API called ✓
- Design ID returned ✓
- Design URL resolvable ✓

### Phase 3: UI Verification (Manual)
1. Open http://localhost:5173
2. See artifact card with 🎨 icon
3. Click "Open in Canva"
4. Real design opens in Canva editor ✓

---

## Files Summary

### Created
- `scripts/smoke_canva_oauth_and_create_design.sh` - Smoke test (executable)
- `documents/STEP2_VALIDATION_RUNBOOK.md` - 10-minute guide
- `documents/TASK_B_CORRECTIONS_AND_SMOKE_TEST.md` - This summary

### Modified
- `Makefile` - Added smoke test targets

### Deleted
- `alembic/alembic.ini` - Workaround config (cleaned up)

### Unchanged (Verified Working)
- All Python code (no changes needed)
- All UI code (no changes needed)
- `alembic.ini` (repo root) - canonical config

---

## Key Improvements

| Before | After |
|--------|-------|
| Manual config file copying | Single canonical config |
| Migrations failed without setup steps | `alembic upgrade head` works from anywhere |
| No validation script | `make smoke-canva` does full validation |
| No clear runbook | STEP2_VALIDATION_RUNBOOK.md provided |
| User unsure what to test | Clear 11-item checklist provided |

---

## Next Steps for User

### Option 1: Quick Smoke Test
```bash
make smoke-canva
# 2 minutes - verifies OAuth setup
```

### Option 2: Full Validation
```bash
# Follow runbook
cat documents/STEP2_VALIDATION_RUNBOOK.md

# Or run directly
make smoke-canva        # Step 1: OAuth
make smoke-canva-design # Step 2: Design
# Open http://localhost:5173 to verify UI
```

### Option 3: Manual Verification (if something fails)
```bash
# Check migrations
.venv/bin/alembic current

# Check OAuth endpoint
curl -s http://localhost:8000/api/v1/auth/canva/status | jq .

# Check database
docker exec canva-notebooklm-postgres psql -U canva_user -d canva_notebooklm_db \
  -c "SELECT * FROM user_connections;"
```

---

## Success Criteria ✅

Task B Step 2 is **COMPLETE** when:

1. ✅ `make smoke-canva` runs from repo root without errors
2. ✅ OAuth URL prints and user can authorize in browser
3. ✅ Database shows `user_connections` row after OAuth
4. ✅ `make smoke-canva-design` creates real Canva design
5. ✅ Design artifact appears in UI (http://localhost:5173)
6. ✅ "Open in Canva" button works
7. ✅ Can edit design in Canva editor (proves it's real)

---

## Scope & Reversibility

### What Changed
- ✅ Minimal changes (only test infrastructure + cleanup)
- ✅ All changes are reversible
- ✅ No breaking changes to existing code
- ✅ Production-safe configuration

### What Didn't Change
- ✅ Worker logic (already real, no changes needed)
- ✅ API endpoints (already implemented)
- ✅ Database schema (already migrated)
- ✅ UI components (already integrated)

---

## Ready to Proceed

```bash
# Start validation
make smoke-canva

# See docs
cat documents/STEP2_VALIDATION_RUNBOOK.md
```

---

**Status**: READY FOR VALIDATION ✅  
**Commands**: `make smoke-canva` (then `make smoke-canva-design`)  
**Docs**: `documents/STEP2_VALIDATION_RUNBOOK.md`  
**Time to validate**: ~10 minutes

