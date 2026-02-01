# UI/UX Architecture & Component Guide

## Overview

The new UI has been rebuilt with a **micro-frontend, modular architecture** that separates concerns into independent, composable components. The design philosophy is **agent-centric**: the interface feels like interacting with an AI assistant, not a backend system.

---

## Architecture Layers

### 1. **Presentational Components** (`src/components/`)
Pure, dumb components that accept props and render. No API calls, no side effects.

- **Header.jsx** - Branding + connection state indicator
- **AgentInput.jsx** - Conversational prompt input with optional config
- **WorkflowStream.jsx** - Live event stream display with auto-scroll
- **StateIndicator.jsx** - Workflow execution state, progress, errors, artifacts
- **ControlBar.jsx** - Action buttons (retry, cancel, refresh, load)

### 2. **Custom Hooks** (`src/hooks/`)
State management & lifecycle orchestration. Each hook encapsulates a domain:

- **useWorkflow()** - CRUD operations (create, fetch, retry, cancel)
- **useEventStream()** - SSE lifecycle, event parsing, stream management
- **useWorkflowState()** - State derivation, UI state flags, snapshot mutations

### 3. **Utilities** (`src/lib/`)
Pure functions for API, parsing, and UI logic:

- **api.js** - Centralized API client
- **eventParser.js** - SSE chunk parsing + snapshot updates
- **stateHelpers.js** - Status → agent state mapping, action guards, CSS class generation

### 4. **Page Composition** (`src/pages/`)
Orchestrates components + hooks into a cohesive user experience:

- **WorkflowPage.jsx** - Main layout: Header → AgentInput → WorkflowView → ControlBar → Modals

---

## Component API Reference

### Header
```jsx
<Header 
  agentState="idle|thinking|processing|complete|error" 
  isConnected={boolean}
/>
```

Displays branding and real-time connection status with animated pulse.

### AgentInput
```jsx
<AgentInput
  onSubmit={(config) => {}} 
  isLoading={boolean}
  tenantId={string}
  userId={string}
/>
```

Conversational input for workflow creation. Shows advanced config toggle.

**Selectors:**
- `[data-testid="agent-input-form"]` - Form container
- `[data-testid="prompt-input"]` - Main textarea
- `[data-testid="config-input"]` - JSON config textarea
- `[data-testid="submit-workflow-btn"]` - Submit button

### WorkflowStream
```jsx
<WorkflowStream
  events={Array}  // {id, payload, ts, parseError?}
  isConnected={boolean}
  isLoading={boolean}
/>
```

Displays live SSE events with timestamps and auto-scroll.

**Selectors:**
- `[data-testid="event-stream"]` - Container
- `[data-testid="event-entry"]` - Individual event (repeated)

### StateIndicator
```jsx
<StateIndicator
  snapshot={object|null}  // Workflow state from API
  agentState="idle|thinking|processing|complete|error"
  isLoading={boolean}
/>
```

Shows execution state: status badge, progress bar, workflow info, errors, artifacts.

**Selectors:**
- `[data-testid="workflow-status"]` - Status badge
- `[data-testid="progress-bar"]` - Progress fill
- `[data-testid="progress-percent"]` - Percentage text
- `[data-testid="workflow-id"]` - Workflow ID (code)
- `[data-testid="workflow-error"]` - Error container
- `[data-testid="error-retryable"]` - Retryable flag
- `[data-testid="workflow-artifacts"]` - Artifacts list

### ControlBar
```jsx
<ControlBar
  canRetry={boolean}
  canCancel={boolean}
  onRetry={() => {}}
  onCancel={() => {}}
  onRefresh={() => {}}
  onLoadWorkflow={() => {}}
  isRetrying={boolean}
  isCancelling={boolean}
  activeWorkflowId={string|null}
/>
```

Action buttons: Refresh, Retry, Cancel, Load Workflow.

**Selectors:**
- `[data-testid="retry-btn"]` - Retry button
- `[data-testid="cancel-btn"]` - Cancel button

### WorkflowPage
Orchestrates all components. Manages:
- Workflow creation/loading
- Event stream lifecycle
- State updates from events
- Modal dialogs (Load Workflow)
- Error handling

**Key Selectors:**
- `[data-testid="agent-state"]` - Header state pill
- `[data-testid="workflow-id-input"]` - Load workflow ID input
- `[data-testid="load-workflow-btn"]` - Load workflow button

---

## Data Flow

### Creating a Workflow (Happy Path)

```
User Input
    ↓
AgentInput.onSubmit(config)
    ↓
WorkflowPage.handleCreateWorkflow()
    ↓
workflow.create(tenantId, userId, config)
    ↓
api.createWorkflow()
    ↓
API returns: {id, status, ...}
    ↓
workflowState.setSnapshot()
    ↓
eventStream.openStream()
    ↓
SSE reader loop begins
    ↓
Event arrives → parseEventChunk() → updateFromEvent()
    ↓
StateIndicator re-renders with latest status/progress
```

### Updating Workflow State

```
SSE Event (e.g., status change)
    ↓
eventStream.events updated
    ↓
WorkflowPage useEffect detects new events
    ↓
workflowState.updateFromEvent(latestEvent)
    ↓
workflowState.snapshot updated
    ↓
StateIndicator re-renders with new progress/status
```

---

## Design Principles

### 1. **Agent-Centric**
- Input feels conversational (large textarea, minimal form)
- States are clear: thinking → processing → complete
- Errors are actionable (retry option visible)
- Artifacts are featured, not buried

### 2. **Modular**
- Components have single responsibility
- Props are well-defined and documented
- No circular dependencies
- Easy to swap/upgrade individual modules

### 3. **Micro-Frontend Ready**
- Components can be isolated and tested independently
- Each component has its own CSS scope (no conflicts)
- State is managed at the page level, passed down
- Easy to extract into separate bundles/packages later

### 4. **Performance**
- Hooks memoize derived state
- Event log limited to 200 items (prevents memory leak)
- Streaming updates animate smoothly
- No unnecessary re-renders due to well-scoped state

---

## Styling Philosophy

All styles in `src/styles.css` follow these rules:

- **CSS Variables** for theming (primary, danger, success, etc.)
- **Semantic Color Usage** (blue for primary, red for danger, green for success)
- **Minimal Shadows & Depth** for modern, clean look
- **Responsive Grid** that adapts to mobile/tablet/desktop
- **Animations** for feedback (pulse, spin, slide, fade)
- **Accessibility** (no color-only status indication)

### Color Scheme

| Purpose | Color | Usage |
|---------|-------|-------|
| Primary | #3b82f6 (blue) | Buttons, links, active states |
| Success | #10b981 (green) | Retry, complete states |
| Danger | #ef4444 (red) | Cancel, error states |
| Muted | #64748b (slate) | Labels, helper text |
| Background | #ffffff | Cards, modals |
| Border | #e2e8f0 (light gray) | Dividers, outlines |

### State Pills (Agent State)

- **Idle** - Gray (ready, waiting)
- **Thinking** - Yellow (submitted/queued)
- **Processing** - Blue (active work, animated pulse)
- **Complete** - Green (success or failure)
- **Error** - Red (unexpected issue)

---

## Testing Strategy

### Unit Tests (Future)
Test individual components with Jest + React Testing Library:
```javascript
test('AgentInput submits config', () => {
  // Render with props
  // User interaction
  // Assert onSubmit called with correct payload
});
```

### E2E Tests (Current)
Playwright tests validate full workflows:
```javascript
test('Create workflow and observe progress', async ({ page }) => {
  await page.fill('[data-testid="prompt-input"]', 'Generate summary');
  await page.click('[data-testid="submit-workflow-btn"]');
  await expect(page.locator('[data-testid="workflow-status"]')).toContainText('COMPLETED');
});
```

### Visual Regression (Future)
Screenshots of each state to detect unintended style changes.

---

## Future Enhancements

### Phase 2 (Mid-term)
- [ ] Workflow history/favorites
- [ ] Dark mode toggle
- [ ] Advanced filtering/search in event log
- [ ] Artifact preview (inline images, rich content)
- [ ] Keyboard shortcuts (Cmd+Enter to submit, etc.)

### Phase 3 (Long-term, Micro-Frontend Federation)
- [ ] Extract components as separate npm packages
- [ ] Module Federation for independent deployment
- [ ] Shared component library
- [ ] Plugin architecture for custom components
- [ ] Multi-tenant theming

### Accessibility
- [ ] ARIA labels on all interactive elements
- [ ] Keyboard navigation (Tab order, Enter/Escape)
- [ ] Color contrast validation (WCAG AA)
- [ ] Screen reader testing

---

## Development Workflow

### Running Locally

```bash
cd ui
npm install
npm run dev
# Opens http://127.0.0.1:5173/
```

### Building for Production

```bash
cd ui
npm run build
# Output: dist/
```

### Running E2E Tests

```bash
make e2e-ui
# Runs full orchestration + Playwright tests
# Results: ui/playwright-report/
```

### Adding a New Component

1. **Create** `src/components/MyComponent.jsx` (presentational)
2. **Define** props interface + data types
3. **Add** test selectors (data-testid)
4. **Export** from `src/components/index.js` (future)
5. **Import** in `WorkflowPage.jsx`
6. **Add** E2E test case

### Updating Styles

- Edit `src/styles.css` directly
- Use CSS variables for consistency
- Test responsive breakpoints (640px, 1024px)
- Verify button/input states (hover, disabled, active)

---

## Known Limitations & TODO

**Current (v0.1)**
- ❌ Worker queue blocking (backend issue, not UI)
- ❌ No workflow history page
- ❌ No artifact preview/download
- ❌ No dark mode
- ❌ No offline mode

**Fixed Recently**
- ✅ Conversational input layout
- ✅ Real-time progress indicator
- ✅ Live event streaming with auto-scroll
- ✅ State machine visualization (idle → thinking → processing → complete)
- ✅ Error handling with retry guidance
- ✅ Responsive design (mobile/tablet/desktop)
- ✅ Modal for loading workflows
- ✅ Modular component architecture

---

## Questions?

For component-specific questions, refer to the JSDoc comments in each file.
For styling, check `src/styles.css` CSS variables section.
For state management, see `src/hooks/` documentation.
