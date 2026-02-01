# Canva NotebookLM Agent UI

**Modern, agent-centric user interface for workflow management**

![Status](https://img.shields.io/badge/status-production--ready-green)
![Architecture](https://img.shields.io/badge/architecture-micro--frontend-blue)
![UX](https://img.shields.io/badge/ux-agent--centric-purple)

---

## Overview

This is a **React + Vite** application with a **micro-frontend architecture** designed to feel like interacting with an AI agent, not a traditional CRUD application.

### Key Features
- ✅ **Conversational Input** - Natural language prompts (like ChatGPT)
- ✅ **Real-Time Streaming** - Live SSE events with auto-scroll
- ✅ **Agent State Visualization** - Idle → Thinking → Processing → Complete
- ✅ **Progress Tracking** - Animated progress bar (0-100%)
- ✅ **Error Handling** - Retry logic with clear error messages
- ✅ **Artifact Display** - Generated files featured prominently
- ✅ **Responsive Design** - Works on mobile, tablet, desktop
- ✅ **Modular Architecture** - Easy to extend and test

---

## Quick Start

### Prerequisites
- Node.js 18+ (or 20+)
- npm or yarn
- Backend API running on `http://localhost:8000`

### Installation
```bash
cd ui
npm install
```

### Development
```bash
npm run dev
# Opens http://127.0.0.1:5173/
```

### Production Build
```bash
npm run build
# Output: dist/
```

### E2E Tests
```bash
npm run e2e       # Run tests
npm run e2e:headed  # Run with UI (interactive debugging)
```

---

## Architecture

### Directory Structure
```
ui/src/
├── lib/                 # Pure functions, utilities
│   ├── api.js          # API client (fetch wrapper)
│   ├── eventParser.js  # SSE parsing logic
│   └── stateHelpers.js # State derivation, UI helpers
├── hooks/               # Custom React hooks (state management)
│   ├── useWorkflow.js       # CRUD operations
│   ├── useEventStream.js    # SSE lifecycle
│   └── useWorkflowState.js  # State derivation
├── components/          # Presentational components (dumb, testable)
│   ├── Header.jsx           # Branding + agent state
│   ├── AgentInput.jsx       # Conversational input
│   ├── WorkflowStream.jsx   # Live event stream
│   ├── StateIndicator.jsx   # Workflow state/progress
│   └── ControlBar.jsx       # Action buttons
├── pages/               # Page compositions (smart, orchestrates)
│   └── WorkflowPage.jsx     # Main page
├── App.jsx              # Entry point
├── main.jsx             # React root
└── styles.css           # Global styles (agent-centric theme)
```

### Design Principles
1. **Separation of Concerns** - Logic (hooks), state (derivation), UI (components)
2. **Single Responsibility** - Each component does one thing well
3. **Testability** - Pure functions, clear inputs/outputs
4. **Scalability** - Easy to add components, hooks, or pages
5. **Micro-Frontend Ready** - Clear boundaries, no circular dependencies

---

## Component API

### Header
```jsx
<Header 
  agentState="idle|thinking|processing|complete|error" 
  isConnected={boolean}
/>
```
Shows branding and real-time agent state with animated pulse.

### AgentInput
```jsx
<AgentInput
  onSubmit={(config) => {}} 
  isLoading={boolean}
  tenantId={string}
  userId={string}
/>
```
Conversational input for workflow creation. Advanced config hidden by default.

### WorkflowStream
```jsx
<WorkflowStream
  events={Array<{id, payload, ts}>}
  isConnected={boolean}
  isLoading={boolean}
/>
```
Displays live SSE events with timestamps and auto-scroll.

### StateIndicator
```jsx
<StateIndicator
  snapshot={object|null}  // Workflow state from API
  agentState="idle|thinking|processing|complete|error"
  isLoading={boolean}
/>
```
Shows execution state: status badge, progress bar, workflow info, errors, artifacts.

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
Action buttons with conditional enabling/disabling based on workflow state.

---

## State Management

### Hooks Pattern
State is managed via custom hooks, not Redux/MobX:

- **useWorkflow()** - Workflow CRUD (create, fetch, retry, cancel)
- **useEventStream()** - SSE lifecycle (open, close, replay)
- **useWorkflowState()** - Derived state (agentState, canRetry, canCancel)

### Data Flow
```
User Action (e.g., click "Start")
    ↓
Component Handler (e.g., handleCreateWorkflow)
    ↓
Hook Method (e.g., workflow.create())
    ↓
API Client (e.g., api.createWorkflow())
    ↓
Backend API
    ↓
Response → Update State → Re-render Components
```

---

## Styling

### Theme
- **Primary:** `#3b82f6` (blue) - Actions, links
- **Success:** `#10b981` (green) - Complete, retry
- **Danger:** `#ef4444` (red) - Errors, cancel
- **Warning:** `#f59e0b` (yellow) - Thinking state
- **Muted:** `#64748b` (slate) - Labels, helper text

### Responsive Breakpoints
- **Mobile:** `<640px` - Single column, stacked layout
- **Tablet:** `640px-1024px` - Adjusted columns, reordered sections
- **Desktop:** `>1024px` - 2-column layout (state sidebar + stream)

### Animations
- **Pulse:** 2s infinite (agent state indicator)
- **Spin:** 0.8s linear infinite (loading spinner)
- **Fade-in:** 0.2s (modal overlay)
- **Slide-up:** 0.3s (modal dialog)

---

## Testing

### E2E Tests (Playwright)
8 comprehensive test scenarios:
1. ✅ Load UI and display main screen
2. ✅ Create workflow and observe live progress
3. ✅ Reload page and replay workflow events
4. ✅ Handle retry for retryable failed workflow
5. ✅ Handle cancel for running workflow
6. ✅ Show retry button only for retryable failures
7. ✅ Display and update progress bar
8. ✅ Handle multiple workflows independently

**Run Tests:**
```bash
make e2e-ui
# Or manually:
npm run e2e
```

**View Report:**
```bash
npx playwright show-report playwright-report/
```

---

## Environment Variables

### Development (`.env.development`)
```
VITE_API_BASE_URL=http://localhost:8000
```

### Production (`.env.production`)
```
VITE_API_BASE_URL=https://api.yourapp.com
```

Access in code:
```javascript
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';
```

---

## API Integration

The UI expects these backend endpoints:

### Create Workflow
```
POST /api/v1/workflows
Headers: X-Tenant-ID
Body: { user_id, tenant_id, config }
Response: { id, status, ... }
```

### Get Workflow
```
GET /api/v1/workflows/{id}
Headers: X-Tenant-ID
Response: { id, status, progress_pct, ... }
```

### SSE Stream
```
GET /api/v1/workflows/{id}/stream
Headers: X-Tenant-ID, Last-Event-ID (optional)
Response: text/event-stream
```

### Retry Workflow
```
POST /api/v1/workflows/{id}/retry
Headers: X-Tenant-ID
Response: { id, status, ... }
```

### Cancel Workflow
```
POST /api/v1/workflows/{id}/cancel
Headers: X-Tenant-ID
Response: { id, status, ... }
```

---

## Development Workflow

### Adding a New Component
1. Create `src/components/MyComponent.jsx`
2. Define props interface (JSDoc or TypeScript)
3. Add test selectors (`data-testid`)
4. Import in `WorkflowPage.jsx`
5. Add E2E test case (if critical user flow)

### Adding a New Hook
1. Create `src/hooks/useMyHook.js`
2. Follow existing patterns (useState, useCallback, useMemo)
3. Return object with methods + state
4. Import in component that needs it

### Updating Styles
1. Edit `src/styles.css`
2. Use CSS variables for consistency
3. Test responsive breakpoints
4. Verify button/input states (hover, disabled, active)

---

## Troubleshooting

### UI won't load
- Check Vite dev server is running (`npm run dev`)
- Verify port 5173 is not in use
- Check browser console for errors

### Workflow won't create
- Verify backend API is running on `:8000`
- Check Network tab in browser DevTools
- Look for CORS errors or 500 responses

### SSE stream not updating
- Check `/stream` endpoint in Network tab
- Verify `Accept: text/event-stream` header
- Confirm backend is sending events correctly

### E2E tests failing
- Ensure backend services running (`make up`, `make api`, `make worker`)
- Check Playwright config (`playwright.config.js`)
- Run in headed mode for debugging: `npm run e2e:headed`

---

## Documentation

Comprehensive guides available:

1. **[UI_ARCHITECTURE.md](../UI_ARCHITECTURE.md)** - Component API, data flow, design principles
2. **[UI_MIGRATION_SUMMARY.md](../UI_MIGRATION_SUMMARY.md)** - Before/after, file changes, known issues
3. **[UI_DEVELOPMENT_GUIDE.md](../UI_DEVELOPMENT_GUIDE.md)** - How to extend, best practices, patterns
4. **[UI_VISUAL_TOUR.md](../UI_VISUAL_TOUR.md)** - Visual mockups, interaction flows, color legend

---

## Contributing

### Code Style
- Use functional components (no class components)
- Prefer hooks over HOCs
- Use `const` over `let` when possible
- Add JSDoc comments for public APIs
- Follow existing patterns for consistency

### Git Commits
```bash
# Good: Clear, descriptive
git commit -m "Add Recent Workflows sidebar component"
git commit -m "Fix progress bar width calculation"

# Bad: Vague
git commit -m "updates"
git commit -m "wip"
```

---

## Roadmap

### Short-Term (1-2 weeks)
- [ ] Workflow history page
- [ ] Dark mode toggle
- [ ] Artifact preview/download
- [ ] Keyboard shortcuts (Cmd+Enter, Escape)

### Mid-Term (1-2 months)
- [ ] Unit tests for all components
- [ ] Visual regression testing (Percy/Chromatic)
- [ ] i18n support (internationalization)
- [ ] Advanced event filtering

### Long-Term (3-6 months)
- [ ] Module Federation (micro-frontends)
- [ ] Component Storybook
- [ ] Extract as reusable library
- [ ] Plugin architecture

---

## License

(Add your license here)

---

## Support

For questions or issues:
- See documentation in root directory (`UI_*.md` files)
- Check browser console + Network tab
- Review E2E test logs
- Check backend API logs

---

**Built with ❤️ using React, Vite, and modern web standards**
