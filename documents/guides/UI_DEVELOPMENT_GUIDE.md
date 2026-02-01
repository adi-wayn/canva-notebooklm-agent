# UI Development Guide: How to Iterate

This guide shows you how to continue developing the UI with best practices for the new modular architecture.

---

## Quick Start: Making Changes

### Adding a New Visual Feature

**Example: Add a "Copy Workflow ID" button**

1. **Update Component** (`src/components/StateIndicator.jsx`):
```jsx
<div className="info-item">
  <span className="info-label">Workflow ID</span>
  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
    <code data-testid="workflow-id">{snapshot.id}</code>
    <button 
      className="btn-small" 
      onClick={() => navigator.clipboard.writeText(snapshot.id)}
      title="Copy to clipboard"
    >
      📋
    </button>
  </div>
</div>
```

2. **Add Styles** (`src/styles.css`):
```css
.btn-small {
  padding: 4px 8px;
  font-size: 12px;
  background: transparent;
  border: none;
  cursor: pointer;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.btn-small:hover {
  opacity: 1;
}
```

3. **Test Manually**:
```bash
cd ui && npm run dev
# Open http://127.0.0.1:5173/
# Create workflow → Click copy button → Paste in terminal
```

4. **Add E2E Test** (optional):
```javascript
test('should copy workflow ID to clipboard', async ({ page }) => {
  await page.goto('/');
  await page.getByTestId('prompt-input').fill('Test copy');
  await page.getByTestId('submit-workflow-btn').click();
  await expect(page.getByTestId('workflow-id')).toBeVisible();
  
  // Click copy button
  await page.locator('button[title="Copy to clipboard"]').click();
  
  // Verify copied (browser API limitation in Playwright)
  // Best tested manually or with browser extension
});
```

---

## Common Patterns

### 1. **Adding a New Hook**

**Use Case:** Need to manage WebSocket connection

**File:** `src/hooks/useWebSocket.js`

```javascript
import { useState, useEffect, useRef } from 'react';

export function useWebSocket(url) {
  const [isConnected, setIsConnected] = useState(false);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);

  useEffect(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);
    ws.onerror = (e) => setError(e.message);
    ws.onmessage = (e) => {
      setMessages((prev) => [...prev, JSON.parse(e.data)]);
    };

    return () => {
      ws.close();
    };
  }, [url]);

  const send = (data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  };

  return { isConnected, messages, error, send };
}
```

**Usage in Component:**
```javascript
import { useWebSocket } from '../hooks/useWebSocket';

function MyComponent() {
  const { isConnected, messages, send } = useWebSocket('ws://localhost:8000/ws');
  
  return (
    <div>
      <p>Connected: {isConnected ? 'Yes' : 'No'}</p>
      <button onClick={() => send({ type: 'ping' })}>Send Ping</button>
      {messages.map((msg) => <p key={msg.id}>{msg.content}</p>)}
    </div>
  );
}
```

---

### 2. **Adding a New Component**

**Use Case:** Need a "Recent Workflows" sidebar

**File:** `src/components/RecentWorkflows.jsx`

```javascript
import React from 'react';

export function RecentWorkflows({ workflows, onSelect, activeId }) {
  if (!workflows || workflows.length === 0) {
    return (
      <div className="recent-workflows empty">
        <p className="muted">No recent workflows</p>
      </div>
    );
  }

  return (
    <div className="recent-workflows">
      <h3>Recent Workflows</h3>
      <ul className="workflow-list">
        {workflows.map((wf) => (
          <li 
            key={wf.id} 
            className={`workflow-item ${wf.id === activeId ? 'active' : ''}`}
            onClick={() => onSelect(wf.id)}
          >
            <div className="workflow-title">{wf.config?.prompt || 'Untitled'}</div>
            <div className="workflow-meta">
              <span className={`status-badge status-${wf.status}`}>{wf.status}</span>
              <span className="workflow-time">{formatTime(wf.created_at)}</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatTime(isoString) {
  const date = new Date(isoString);
  return date.toLocaleDateString();
}
```

**Add to WorkflowPage:**
```javascript
import { RecentWorkflows } from '../components/RecentWorkflows';

// In WorkflowPage.jsx:
const [recentWorkflows, setRecentWorkflows] = useState([]);

// Fetch recent workflows on mount
useEffect(() => {
  async function fetchRecent() {
    const wfs = await api.getRecentWorkflows(tenantId);
    setRecentWorkflows(wfs);
  }
  fetchRecent();
}, [tenantId]);

// Add to render:
<aside className="sidebar-right">
  <RecentWorkflows 
    workflows={recentWorkflows} 
    onSelect={handleLoadWorkflowById}
    activeId={activeWorkflowId}
  />
</aside>
```

**Add Styles:**
```css
.recent-workflows {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
}

.workflow-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.workflow-item {
  padding: 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.workflow-item:hover {
  background: #f9fafb;
}

.workflow-item.active {
  background: #e0e7ff;
  border: 1px solid var(--primary);
}
```

---

### 3. **Adding a New API Endpoint**

**Use Case:** Need to fetch workflow history

**File:** `src/lib/api.js`

```javascript
export const api = {
  // ... existing methods

  /**
   * Fetch recent workflows for a tenant
   * @param {string} tenantId
   * @param {number} limit - Max number of workflows to fetch
   * @returns {Promise<Array>} Array of workflow objects
   */
  async getRecentWorkflows(tenantId, limit = 10) {
    const resp = await fetch(`${API_BASE}/api/v1/workflows?limit=${limit}`, {
      headers: {
        'X-Tenant-ID': tenantId,
      },
    });

    if (!resp.ok) {
      throw new Error(`Failed to fetch recent workflows: ${resp.statusText}`);
    }

    return resp.json();
  },
};
```

---

### 4. **Adding a State Helper**

**Use Case:** Need to check if workflow is retryable

**File:** `src/lib/stateHelpers.js`

```javascript
/**
 * Check if workflow is in a state where retry is possible
 * @param {object} workflow - Full workflow object
 * @returns {boolean}
 */
export function isRetryable(workflow) {
  return (
    workflow?.status === WorkflowStatus.FAILED &&
    workflow?.error?.retryable === true
  );
}

/**
 * Get human-readable time since workflow created
 * @param {string} createdAt - ISO timestamp
 * @returns {string} "2 minutes ago", "1 hour ago", etc.
 */
export function getTimeSince(createdAt) {
  const now = new Date();
  const created = new Date(createdAt);
  const diffMs = now - created;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins} minute${diffMins > 1 ? 's' : ''} ago`;
  
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
}
```

---

## Testing Workflow

### Manual Testing Checklist

Before committing UI changes:

1. **Visual Inspection**
   - [ ] Component renders correctly
   - [ ] All states visible (idle, loading, error, success)
   - [ ] Animations smooth
   - [ ] No layout shift on data load

2. **Interaction Testing**
   - [ ] Buttons clickable
   - [ ] Forms submittable
   - [ ] Keyboard navigation works
   - [ ] Error messages clear

3. **Responsive Testing**
   - [ ] Desktop (1400px+): Full layout
   - [ ] Tablet (1024px): Adjusted columns
   - [ ] Mobile (640px): Stacked layout

4. **Browser Testing**
   - [ ] Chrome/Edge (Chromium)
   - [ ] Firefox
   - [ ] Safari (if on Mac)

### E2E Testing

When to add E2E tests:
- ✅ Critical user flows (create, retry, cancel)
- ✅ Complex state transitions
- ✅ Multi-step processes
- ❌ Simple visual tweaks
- ❌ CSS-only changes

**Template for New E2E Test:**
```javascript
test('should [describe user action]', async ({ page }) => {
  await page.goto('/');
  
  // Setup: Create necessary preconditions
  await page.getByTestId('prompt-input').fill('Test prompt');
  await page.getByTestId('submit-workflow-btn').click();
  
  // Action: Perform the user action
  await page.getByTestId('my-new-button').click();
  
  // Assert: Verify expected outcome
  await expect(page.getByTestId('expected-result')).toBeVisible();
  await expect(page.getByTestId('expected-result')).toHaveText('Expected text');
});
```

---

## Styling Best Practices

### Use CSS Variables
```css
/* ✅ Good: Uses CSS variable */
.btn-primary {
  background: var(--primary);
}

/* ❌ Bad: Hardcoded color */
.btn-primary {
  background: #3b82f6;
}
```

### Semantic Class Names
```css
/* ✅ Good: Describes purpose */
.workflow-status-badge { }
.event-timestamp { }

/* ❌ Bad: Describes style */
.blue-text { }
.margin-20 { }
```

### Mobile-First Responsive
```css
/* ✅ Good: Mobile default, desktop override */
.container {
  flex-direction: column;
}

@media (min-width: 1024px) {
  .container {
    flex-direction: row;
  }
}

/* ❌ Bad: Desktop default, mobile override */
.container {
  flex-direction: row;
}

@media (max-width: 1024px) {
  .container {
    flex-direction: column;
  }
}
```

---

## Performance Tips

### Memoize Derived State
```javascript
// ✅ Good: Memoized, only recomputes when snapshot changes
const isRetryable = useMemo(() => {
  return snapshot?.status === 'FAILED' && snapshot?.error?.retryable;
}, [snapshot]);

// ❌ Bad: Recomputed on every render
const isRetryable = snapshot?.status === 'FAILED' && snapshot?.error?.retryable;
```

### Avoid Inline Functions in Render
```javascript
// ✅ Good: Function defined outside render
const handleClick = useCallback(() => {
  console.log('clicked');
}, []);

return <button onClick={handleClick}>Click</button>;

// ❌ Bad: New function on every render
return <button onClick={() => console.log('clicked')}>Click</button>;
```

### Lazy Load Heavy Components
```javascript
import { lazy, Suspense } from 'react';

const HeavyChart = lazy(() => import('./HeavyChart'));

function MyComponent() {
  return (
    <Suspense fallback={<div>Loading chart...</div>}>
      <HeavyChart data={data} />
    </Suspense>
  );
}
```

---

## Debugging Tips

### Check Browser Console
```javascript
// Add debug logs in hooks
useEffect(() => {
  console.log('[useWorkflowState] Snapshot updated:', snapshot);
}, [snapshot]);
```

### React DevTools
- Install React DevTools browser extension
- Inspect component props/state
- Track re-renders with "Highlight updates"

### Network Tab
- Check API requests/responses
- Verify SSE connection established
- Look for failed requests (red in Network tab)

### Playwright Debug Mode
```bash
cd ui
PWDEBUG=1 npx playwright test
# Opens inspector, allows step-by-step execution
```

---

## Git Workflow

### Branch Naming
```bash
# Feature branches
git checkout -b feature/add-workflow-history
git checkout -b feature/dark-mode

# Bug fixes
git checkout -b fix/progress-bar-not-updating
git checkout -b fix/modal-overlay-z-index

# UI polish
git checkout -b ui/improve-mobile-layout
git checkout -b ui/add-loading-skeleton
```

### Commit Messages
```bash
# ✅ Good: Clear, descriptive
git commit -m "Add Recent Workflows sidebar component"
git commit -m "Fix progress bar width calculation"
git commit -m "Update E2E tests for new modal UI"

# ❌ Bad: Vague
git commit -m "updates"
git commit -m "fix stuff"
git commit -m "wip"
```

---

## Deployment Checklist

Before deploying UI to production:

1. **Build**
   ```bash
   cd ui
   npm run build
   # Check dist/ size (<5MB ideal)
   ```

2. **Test Production Build**
   ```bash
   npm run preview
   # Opens preview server at http://localhost:4173
   ```

3. **Environment Variables**
   - Set `VITE_API_BASE_URL` for production API
   - Example: `VITE_API_BASE_URL=https://api.myapp.com`

4. **Verify**
   - [ ] All features work
   - [ ] No console errors
   - [ ] API calls succeed
   - [ ] Assets load correctly

---

## FAQ

**Q: Where do I add a new page?**
A: Create `src/pages/MyPage.jsx`, import in `App.jsx`, add routing (future: React Router).

**Q: How do I access the API base URL?**
A: Use `import.meta.env.VITE_API_BASE_URL` or the `api` client from `src/lib/api.js`.

**Q: Can I use a state management library (Redux, Zustand)?**
A: Not needed yet. Custom hooks are sufficient. Add only if state becomes too complex.

**Q: How do I add a loading skeleton?**
A: Create a `LoadingSkeleton.jsx` component, render conditionally while `isLoading` is true.

**Q: Can I extract components as an npm package?**
A: Yes! Once stable, move `src/components/` to a separate repo, publish to npm.

---

## Resources

- **React Docs:** https://react.dev
- **Vite Docs:** https://vitejs.dev
- **Playwright Docs:** https://playwright.dev
- **CSS Variables:** https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties
- **Hooks Guide:** https://react.dev/reference/react

---

## Next Steps

Now that you have the foundation, here's how to continue:

1. **Iterate on UX:** Add visual polish, animations, micro-interactions
2. **Expand Features:** Workflow history, artifact preview, advanced filters
3. **Optimize Performance:** Code splitting, lazy loading, image optimization
4. **Enhance Accessibility:** ARIA labels, keyboard shortcuts, screen reader testing
5. **Scale Architecture:** Module Federation, component library, plugin system

**Happy coding!** 🚀
