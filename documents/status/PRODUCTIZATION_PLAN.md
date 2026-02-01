# Productization Phase Plan

**Goal**: Transform the validated architecture into a client-ready product with real integrations.

**Date Started**: 2026-01-18  
**Target**: Demo-ready in ~4-6 hours of focused work

---

## Phase Overview

### 1. Design System Enhancement ⏳
**Current**: Basic CSS with some variables  
**Target**: Professional, cohesive design system

- [ ] Enhance CSS variables (expanded color palette, spacing scale, typography system)
- [ ] Create reusable component classes
- [ ] Add transitions and micro-interactions
- [ ] Ensure accessibility (focus states, contrast ratios)

### 2. Chat/Agent-Style UI 🎯
**Current**: Form-based interaction  
**Target**: Conversational agent experience

- [ ] Message bubble components (user vs. agent)
- [ ] Streaming "thinking" indicators
- [ ] Progress visualization (percentage + descriptive steps)
- [ ] Artifact presentation as primary content

### 3. Artifact Renderer System 🎨
**Current**: Generic event display  
**Target**: Typed artifacts with rich renderers

- [ ] Define artifact types (text, link, canva_design, notebook)
- [ ] Create renderer per type
- [ ] Add actions: Copy, Download, Open in Canva
- [ ] Result summary section

### 4. History/Session View 📋
**Current**: Single workflow view  
**Target**: Multi-workflow session management

- [ ] List recent workflows per tenant
- [ ] Filter by status (all/completed/failed)
- [ ] Click to load workflow
- [ ] Display timestamps and quick status

### 5. Canva Integration (Real) 🎨
**Current**: Mocked  
**Target**: OAuth + real API

- [ ] Implement OAuth2 flow (authorization code grant)
- [ ] Store refresh tokens securely (backend + DB)
- [ ] Add "Connect Canva" button in UI
- [ ] Show connection status indicator
- [ ] Call real Canva API to create designs
- [ ] Return design URLs to UI

### 6. NotebookLM Integration (Real) 📚
**Current**: Mocked  
**Target**: Real workflow

- [ ] Research NotebookLM API availability
- [ ] If API exists: implement OAuth + API calls
- [ ] If no API: document alternative (manual upload + link)
- [ ] Generate client-consumable artifact (summary, audio link, etc.)

### 7. Empty/Error/Loading States 🎭
**Current**: Basic  
**Target**: Polished, helpful

- [ ] Empty state for no workflows (with CTA)
- [ ] Loading skeletons for workflows
- [ ] Error boundaries with retry actions
- [ ] Friendly error messages

### 8. Demo Flow Documentation 📖
**Current**: None  
**Target**: <2 minute path for non-technical users

- [ ] Write step-by-step guide
- [ ] Create sample workflow config
- [ ] Record expected outputs
- [ ] Document prerequisites (accounts needed)

---

## Technical Approach

### Frontend Changes
- Keep React + Vite setup
- Add new components in `ui/src/components/`
- Enhance hooks for connection status
- Use existing SSE streaming (validated)

### Backend Changes
- Add OAuth endpoints for Canva (`/api/v1/auth/canva/*`)
- Store tokens in new `user_connections` table
- Add real API adapter logic in `src/adapters/canva_adapter.py`
- Keep Postgres as source of truth (no new infra)

### Database Schema
```sql
CREATE TABLE user_connections (
  id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  tenant_id TEXT NOT NULL,
  provider TEXT NOT NULL,  -- 'canva' or 'notebooklm'
  access_token TEXT,
  refresh_token TEXT,
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(user_id, tenant_id, provider)
);
```

---

## Success Criteria (Definition of Done)

✅ **UI feels professional**: Clean layout, smooth interactions, no developer jargon  
✅ **Real Canva connection works**: OAuth flow → token storage → design creation → link in UI  
✅ **Artifacts are actionable**: Copy/Download/Open buttons functional  
✅ **History view usable**: Can see past workflows and click to load  
✅ **Demo flow <2 minutes**: Non-technical user can complete successfully  
✅ **No regressions**: Backend validation (Steps A/B) still passing  

---

## Implementation Order (Incremental)

### Sprint 1: UI/UX Foundation (2-3 hours)
1. Enhanced design system (CSS variables, tokens)
2. Chat-style message components
3. Artifact renderer framework
4. History view skeleton

### Sprint 2: Canva Integration (1-2 hours)
1. OAuth flow backend
2. Token storage (DB migration)
3. Connection UI indicator
4. Real API call for design creation

### Sprint 3: Polish & NotebookLM (1-2 hours)
1. NotebookLM approach (API or alternative)
2. Empty/error states refinement
3. Demo flow testing & documentation
4. Final E2E validation

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| NotebookLM has no API | Use manual link approach; document clearly |
| OAuth flow complex | Use well-tested library (authlib for Python) |
| UI rework breaks E2E tests | Keep data-testid attributes intact |
| Real API rate limits | Add retry logic + clear error messages |

---

## Files to Modify

### Frontend
- `ui/src/styles.css` (design system expansion)
- `ui/src/components/ArtifactRenderer.jsx` (NEW)
- `ui/src/components/MessageBubble.jsx` (NEW)
- `ui/src/components/WorkflowHistory.jsx` (NEW)
- `ui/src/components/ConnectionStatus.jsx` (NEW)
- `ui/src/pages/WorkflowPage.jsx` (enhance layout)

### Backend
- `src/api/routes/auth.py` (NEW - Canva OAuth)
- `src/adapters/canva_adapter.py` (replace mock with real)
- `src/adapters/notebooklm_adapter.py` (implement real workflow)
- `src/storage/repository.py` (add UserConnectionRepository)
- `alembic/versions/002_user_connections.py` (NEW migration)

---

## Next Actions

Starting with Sprint 1: UI/UX Foundation
1. Enhance design system
2. Create chat-style components
3. Build artifact renderers
4. Add history view

Then proceed to Canva integration (Sprint 2) and final polish (Sprint 3).
