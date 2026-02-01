# Task B Step 2: Real Canva Design Creation (In Progress)

**Status**: 🔄 IMPLEMENTATION STARTED

## What This Step Accomplishes

Transform from mock designs to real, working Canva designs that users can edit:
1. Check for Canva OAuth connection (require authorization)
2. Call real Canva design creation API
3. Store design_id + resolvable design URL
4. Display with "Open in Canva" button
5. Block workflow if Canva not connected

## Implementation Details

### 1. Workflow Worker Updates

**File**: `src/workers/workflow_worker.py`

**Changes Made**:
- ✅ Import UserConnectionRepository for checking OAuth status
- ✅ Import create_canva_adapter_from_db() factory function
- ✅ Replaced mock artifact code with real Canva integration

**New Logic**:
```python
# Check if user has Canva connection
async with database.session() as session:
    conn_repo = UserConnectionRepository(
        session, 
        user_id=engine_workflow.user_id,
        tenant_id=engine_workflow.tenant_id
    )
    has_canva = await conn_repo.has_connection("canva")

if has_canva:
    # Get adapter from database tokens
    adapter = await create_canva_adapter_from_db(
        user_id=engine_workflow.user_id,
        tenant_id=engine_workflow.tenant_id
    )
    
    if adapter:
        # Create real design
        design = await adapter.create_presentation(title=title)
        
        # Store with resolvable Canva URL
        design_url = f"https://www.canva.com/design/{design.design_id}/edit"
        self.engine.add_artifact(
            engine_workflow,
            name=f"Design: {title}",
            content_type="canva_design",
            url=design_url,
            data={
                "design_id": design.design_id,
                "title": design.title,
                "created_at": design.created_at.isoformat(),
            }
        )
else:
    # Not connected - show helpful message
    self.engine.add_artifact(
        engine_workflow,
        name="Connect Canva to create designs",
        content_type="text",
        data={"message": "Click 'Connect Canva' in the app to authorize"}
    )
```

**Error Handling**:
- Token expiration (adapter returns None) → show "token expired" message
- Design creation failure → catch exception, add error artifact
- Canva not connected → add helpful "Connect Canva" message

### 2. UI Integration (Already Ready)

**File**: `ui/src/components/ArtifactRenderer.jsx`

**Canva Design Artifact Support**:
```javascript
case 'canva_design':
  return (
    <div className="artifact-preview">
      {artifact.thumbnail ? (
        <img src={artifact.thumbnail} alt="Design preview" />
      ) : (
        <div className="artifact-placeholder">🎨 Canva Design</div>
      )}
    </div>
  );
```

**Action Buttons**:
- 📋 Copy (copies design URL)
- ⬇️ Download (if content available)
- 🎨 **Open in Canva** (new button for canva_design type)
  - Opens design in Canva editor
  - User can immediately edit design
  - Real-time collaboration ready

### 3. Design URL Pattern

**Format**: `https://www.canva.com/design/{design_id}/edit`

**Example**: 
```
https://www.canva.com/design/DAGc_pZ1234/edit
```

**Behavior**:
- Clicking "Open in Canva" opens in new tab
- User sees design in Canva editor
- Can edit, add content, export, etc.
- Full Canva feature access

## Data Flow

```
User clicks "Create Design"
    ↓
WorkflowPage sends POST /workflows with description
    ↓
API creates workflow, queues task
    ↓
WorkflowWorker polls queue
    ↓
Check: Does user have Canva connection?
    ├─ NO: Add artifact with "Connect Canva" message
    └─ YES: ↓
        Retrieve tokens from user_connections table
            ↓
        Create CanvaAdapter with stored tokens
            ↓
        Call adapter.create_presentation(title)
            ↓
        Real Canva API creates design (POST /v1/designs)
            ↓
        Get design_id from response
            ↓
        Build design URL: https://www.canva.com/design/{id}/edit
            ↓
        Store artifact with:
          - name: "Design: {title}"
          - content_type: "canva_design"
          - url: design_url
          - data: {design_id, title, created_at}
            ↓
        Emit event to frontend
            ↓
ArtifactRenderer displays card with:
  - 🎨 Icon
  - Design name
  - "Canva Design" label
  - 📋 Copy (URL)
  - 🎨 Open in Canva button (opens design_url in new tab)
```

## Testing Checklist

### Pre-Testing Setup
- ✅ Database migration (user_connections table ready)
- ✅ OAuth endpoints created
- ✅ UI ConnectionStatus component ready
- ✅ Real Canva design creation code in worker
- ✅ ArtifactRenderer supports canva_design type
- ⚠️ Need: Canva Developer Account with OAuth credentials set in .env

### Test Scenario 1: Connected User Creates Design

1. **Setup**:
   - Start backend: `make dev`
   - Start frontend: `cd ui && npm run dev`
   - Open UI: http://localhost:5173

2. **Execute**:
   - Click "Connect Canva" in empty state
   - Authorize in Canva OAuth consent screen
   - Verify DB row created in user_connections table:
     ```sql
     SELECT * FROM user_connections 
     WHERE user_id='demo-user' AND provider='canva';
     ```

3. **Create Design**:
   - Type in input: "Create a social media post for a coffee shop"
   - Click "Send" or "Create Workflow"
   - Watch progress bar move to "finalizing"
   - Verify in backend logs:
     ```
     ✅ Created real Canva design: DAG...
     ```

4. **Verify Artifact**:
   - Design card appears with 🎨 icon
   - Title shows: "Design: Create a social media post..."
   - Label shows: "Canva Design"
   - Has buttons: Copy, Download, Open in Canva

5. **Test "Open in Canva"**:
   - Click 🎨 Open in Canva button
   - New tab opens
   - URL is: https://www.canva.com/design/{design_id}/edit
   - Can edit design in Canva editor
   - ✅ **SUCCESS**: Real design in Canva!

### Test Scenario 2: Disconnected User

1. **Execute**:
   - Without connecting Canva
   - Type in input: "Create a design"
   - Submit workflow

2. **Verify**:
   - Progress bar completes
   - Artifact card appears with message:
     ```
     "Connect Canva to create designs"
     "Click 'Connect Canva' in the app to authorize"
     ```
   - No "Open in Canva" button
   - ✅ Clear UX guidance

### Test Scenario 3: Token Expiration

1. **Setup**:
   - Connect Canva (token stored with 1-hour expiration)
   - Manually set token_expires_at to past time in DB:
     ```sql
     UPDATE user_connections 
     SET token_expires_at = NOW() - INTERVAL 1 HOUR
     WHERE provider='canva';
     ```

2. **Execute**:
   - Create workflow

3. **Verify**:
   - Backend detects expired token
   - create_canva_adapter_from_db() returns None
   - Artifact shows: "Canva token expired"
   - User reconnects Canva
   - ✅ Graceful degradation

## Files Modified

1. ✅ `src/workers/workflow_worker.py`:
   - Added imports: UserConnectionRepository, create_canva_adapter_from_db
   - Replaced mock artifact code with real Canva design creation
   - Added error handling + logging

2. ✅ `ui/src/components/ArtifactRenderer.jsx`:
   - Already supports canva_design type
   - "Open in Canva" button already implemented
   - No changes needed

## Database Schema (Already Created)

```sql
CREATE TABLE user_connections (
  id SERIAL PRIMARY KEY,
  user_id VARCHAR(36) NOT NULL,
  tenant_id VARCHAR(36) NOT NULL,
  provider VARCHAR(50) NOT NULL,
  access_token TEXT NOT NULL,
  refresh_token TEXT,
  token_expires_at TIMESTAMP WITH TIME ZONE,
  account_email VARCHAR(255),
  account_name VARCHAR(255),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(user_id, tenant_id, provider),
  FOREIGN KEY(user_id) REFERENCES users(id),
  FOREIGN KEY(tenant_id) REFERENCES tenants(id)
);
```

## Canva API Integration

**Endpoint Used**: POST /v1/designs (real Canva API)

**Request**:
```json
{
  "title": "User's Design Title"
}
```

**Response**:
```json
{
  "id": "DAGc_pZ1234...",
  "title": "User's Design Title",
  "created_at": "2025-01-18T10:30:00Z",
  "thumbnail_url": "https://...",
  ...
}
```

**Token Management**:
- Tokens stored encrypted in user_connections table
- Auto-refresh on 401 (handled in CanvaAdapter._refresh_token())
- Refresh token persisted to DB after update

## Success Criteria

- ✅ Database migration complete
- ✅ OAuth flow end-to-end working
- ✅ Worker creates real designs (not mocks)
- ✅ Design URL resolvable in Canva
- ✅ "Open in Canva" button works
- ✅ Clear UX when not connected
- ✅ Error handling for token expiration
- ✅ End-to-end test: OAuth → Design → Edit in Canva

## Known Limitations (Phase 2)

- Design is created with title only (no content yet)
- No design customization from prompt
- NotebookLM integration not included
- Design preview/thumbnail not fetched
- Bulk design operations not supported

## Next Steps (Phase 3)

After Step 2 is demoable:
1. Add content to designs (text, images from NotebookLM)
2. Support design customization
3. Add NotebookLM integration
4. Support exporting designs
5. Add design history/listing

