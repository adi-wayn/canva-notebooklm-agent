# Quick Reference: Step 2 Validation

## One-Command Start
```bash
make smoke-canva
```

## What Happens
1. ✅ Services start (PostgreSQL + Redis)
2. ✅ Migrations apply (no manual setup)
3. ✅ API starts (http://localhost:8000)
4. ✅ OAuth endpoints verified
5. 📋 OAuth URL printed → Click in browser
6. ⏳ Waits for you to authorize in Canva
7. ✅ Detects when done

## After OAuth Complete
```bash
make smoke-canva-design
```

## What Happens
1. ✅ Real Canva design created
2. ✅ Design ID returned
3. ✅ URL printed: https://www.canva.com/design/{id}/edit
4. ✅ Artifact stored in database

## Verify in UI
```
Open: http://localhost:5173
See: Design artifact card (🎨 icon)
Click: "Open in Canva" button
Result: Opens real design in Canva editor ✅
```

## If Something Fails

### Check Migrations
```bash
.venv/bin/alembic current
# Expected: 003_user_connections (head)
```

### Check OAuth Connection
```bash
docker exec canva-notebooklm-postgres psql -U canva_user -d canva_notebooklm_db \
  -c "SELECT * FROM user_connections WHERE provider='canva';"
# Expected: 1 row with your email
```

### Check API Health
```bash
curl -s http://localhost:8000/health
# Expected: {"status": "ok"}
```

### Check Logs
```bash
tail -50 /tmp/api.log      # API logs
tail -50 /tmp/worker.log   # Worker logs
tail -50 /tmp/alembic.log  # Migration logs
```

## Complete Checklist
- [ ] `make smoke-canva` runs
- [ ] OAuth URL prints
- [ ] You authorize in Canva
- [ ] Script detects authorization
- [ ] `make smoke-canva-design` runs
- [ ] Design created (check logs)
- [ ] Open http://localhost:5173
- [ ] See design artifact
- [ ] Click "Open in Canva"
- [ ] Real Canva editor opens
- [ ] ✅ Task B Complete!

## Full Runbook
See: `documents/STEP2_VALIDATION_RUNBOOK.md`

---

**Time**: ~10 minutes  
**Status**: Ready to run  
**Command**: `make smoke-canva`
