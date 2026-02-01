# UI/UX & API Contract Specification — T2.4

## Objective
Define the customer-facing workflow model and API contract that enables a real client (web UI, mobile app, CLI) to interact with the workflow engine.

---

## PART 1: UX FLOWS

### Flow 1: Create & Monitor Workflow

```
USER ACTION                          SYSTEM STATE
┌────────────────────────────────┐
│ 1. User submits workflow       │
│    (Web: click "Create Design" │
│     Input: source_id, title)   │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ POST /api/v1/workflows         │
│ Returns: { id, status: "QUEUED"│
│            progress_pct: 0% }   │
│                                │
│ Response: 201 Created          │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ 2. User sees workflow card     │
│    Status: QUEUED              │
│    Progress: 0%                │
│    Action: [Cancel] [Refresh]  │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ 3. User subscribes to updates  │
│    (Web: SSE stream, Mobile:   │
│     polling GET /workflows/{id}│
│     CLI: watch output)         │
│                                │
│ GET /workflows/{id}/events     │
│ or GET /workflows/{id}/stream  │
│ (preferred: SSE)               │
│                                │
│ Events: status_changed,        │
│         step_progressed,       │
│         artifact_created,      │
│         failed                 │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ 4. Status updates in real time │
│    SUBMITTED → QUEUED          │
│    QUEUED → PROCESSING         │
│    Progress: 5% → 100%         │
│    Steps: analyzing_content    │
│            generating_layout   │
│            creating_design ... │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ 5. Final state: COMPLETED      │
│    Progress: 100%              │
│    Artifacts: [design.pdf,     │
│                layout.json]    │
│    Status: ✓ COMPLETE          │
│    Actions: [Download] [Share] │
│              [Refine] [New]    │
└────────────────────────────────┘
```

### Flow 2: Retry on Transient Error

```
┌────────────────────────────────┐
│ Processing encounters timeout  │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ Workflow fails                 │
│ Status: FAILED                 │
│ Step: "analyzing_content"      │
│ Progress: 20%                  │
│ Error: {                       │
│   type: "TRANSIENT",          │
│   message: "Request timeout... │
│   retryable: true             │
│ }                             │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ User sees failure card         │
│ Status: ⚠ FAILED              │
│ Message: "Request timeout.     │
│           Please try again."   │
│ Actions:                       │
│   [Retry] [Cancel] [Details]   │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ User clicks [Retry]            │
│ POST /api/v1/workflows/{id}    │
│           /retry               │
│                                │
│ Returns: workflow with status  │
│ QUEUED (requeued)              │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ Workflow restarts from same    │
│ step (or from beginning)       │
│ Progress: 20% → continues      │
│ Status: PROCESSING → COMPLETED │
└────────────────────────────────┘
```

### Flow 3: Permanent Error (No Retry)

```
┌────────────────────────────────┐
│ Processing encounters invalid  │
│ response (JSON parse error)    │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ Workflow fails                 │
│ Status: FAILED                 │
│ Error: {                       │
│   type: "PERMANENT",          │
│   message: "Invalid JSON...",  │
│   retryable: false            │
│ }                             │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ User sees error card           │
│ Status: ✗ FAILED              │
│ Message: "Invalid input.       │
│           This error cannot    │
│           be retried. Please   │
│           contact support."    │
│ Actions:                       │
│   [Cancel] [Details] [Support] │
│ (NO [Retry] button)            │
└────────────────────────────────┘
```

### Flow 4: Refine Results (Advanced)

```
┌────────────────────────────────┐
│ Workflow completed with        │
│ design output                  │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ User clicks [Refine]           │
│ Input: additional instructions │
│ (e.g., "Add more color",       │
│  "Change layout to columns")   │
│                                │
│ POST /api/v1/workflows/{id}    │
│           /refine              │
│ { "instructions": "..." }      │
│                                │
│ Returns: new workflow in QUEUED│
│ (linked to parent)             │
└────────────┬────────────────────┘
             │
             ▼
┌────────────────────────────────┐
│ New iteration starts           │
│ Status: QUEUED → PROCESSING    │
│ Steps: generating_layout       │
│        (skips content analysis)│
│        creating_design ...     │
└────────────────────────────────┘
```

---

## PART 2: SCREEN LIST & UI STATES

### Screen 1: Workflow Creation

**States:**
- `initial`: Empty form
- `submitting`: Loading indicator during POST
- `submitted`: Confirmation + workflow ID + redirect

**Fields:**
- Source ID (dropdown, pre-populated from available NotebookLM sources)
- Title (text input, optional)
- Advanced options (collapsible):
  - Template preference (grid, timeline, minimal, etc.)
  - Branding colors (color picker)
  - Language (for generated text)

**Error states:**
- Missing required field → red highlight + tooltip
- API error (400, 401, 429) → inline error message with action

---

### Screen 2: Workflow Progress

**States:**
- `queued`: "Your design is queued. Estimated wait: 2-5 min"
- `processing`: Progress bar, live step name, current % complete
- `completed`: All artifacts displayed, download links, action buttons
- `failed`: Error message (retryable=true shows [Retry]; retryable=false shows support link)

**Live Updates (via SSE or polling):**
- Real-time progress bar (0-100%)
- Step name updates (e.g., "Analyzing content... (20%)" → "Generating layout... (50%)")
- Artifacts appear as they're created (downloads become available immediately)

**Header:**
- Workflow ID (copy button)
- Status badge (color-coded: QUEUED=gray, PROCESSING=blue, COMPLETED=green, FAILED=red)
- Created timestamp + elapsed time

---

### Screen 3: Results View

**Sections:**
1. **Status Summary**
   - Status badge + message
   - Completion time + elapsed duration

2. **Artifacts**
   - For each artifact:
     - Name (human-readable)
     - Type (PDF, JSON, PNG, etc.)
     - Size (if applicable)
     - **Action buttons**: [Download] [Preview] [Copy link] [Share]
   - Combined download (ZIP all artifacts)

3. **Metadata**
   - Request ID (for support)
   - Step name where it completed
   - Tenant ID (if applicable)

4. **Actions**
   - [Refine] (if completed) → opens refinement dialog
   - [Retry] (if failed + retryable)
   - [Cancel] → mark as archived
   - [New Workflow] → reset form

---

### Screen 4: Error Details

**For Transient Errors:**
```
⚠ Request Timed Out

Your workflow encountered a temporary issue while processing.
This can happen when our services are busy or experiencing
temporary latency.

Please try again. If the problem persists, contact support.

[Retry] [View Details] [Cancel]
```

**For Permanent Errors:**
```
✗ Invalid Input

The workflow failed due to an error in your input or the
content you provided. This error cannot be retried.

Please check your source content and try a new workflow,
or contact support for assistance.

Request ID: wf_abc123def456 (for support tickets)

[Copy Request ID] [Contact Support] [New Workflow]
```

---

## PART 3: ERROR MESSAGE GUIDELINES

### Retryable Error Copy (Transient)

**Pattern:**
```
[Icon] [Friendly name]

[One-sentence explanation of what went wrong]
This is usually temporary.

[Action buttons: Retry, Cancel, Details]
```

**Examples:**
- "Request Timed Out" — "The API took too long to respond. This is usually temporary."
- "Rate Limited" — "We received too many requests. Please wait a moment and try again."
- "Service Temporarily Unavailable" — "The service is temporarily unavailable. This usually resolves within minutes."

### Non-Retryable Error Copy (Permanent)

**Pattern:**
```
[Icon] [Friendly name]

[Explanation of the problem]
This error cannot be retried.

[What to do next: check input, contact support, try again with different settings]

[Action buttons: Cancel, Support, Details]
```

**Examples:**
- "Invalid Input" — "The content you provided is invalid. Please check your source and try again."
- "Quota Exceeded" — "You have reached your workflow quota for this period. Upgrade your plan or try again later."
- "Authentication Failed" — "Your API key expired or is invalid. Please update your credentials."

---

## PART 4: API CONTRACT

### Endpoint 1: Create Workflow

```
POST /api/v1/workflows

Request:
{
  "workflow_type": "content_to_presentation",  // or other types (T.B.D)
  "source_id": "notebooklm_src_123",
  "title": "Q4 Strategy",
  "input_data": {
    "template_preference": "grid",
    "branding": { "primary_color": "#3b82f6" }
  }
}

Response: 201 Created
{
  "id": "wf_abc123",
  "tenant_id": "tenant_1",
  "user_id": "user_1",
  "status": "SUBMITTED",
  "step": "submitted",
  "progress_pct": 0,
  "artifacts": [],
  "error": null,
  "created_at": "2026-01-17T10:30:00Z",
  "updated_at": "2026-01-17T10:30:00Z",
  "request_id": "req_xyz789"
}
```

---

### Endpoint 2: Get Workflow Status

```
GET /api/v1/workflows/{workflow_id}

Response: 200 OK
{
  "id": "wf_abc123",
  "tenant_id": "tenant_1",
  "user_id": "user_1",
  "status": "PROCESSING",
  "step": "generating_layout",
  "progress_pct": 45,
  "artifacts": [
    {
      "name": "content_analysis",
      "content_type": "application/json",
      "url": "https://storage.example.com/artifacts/wf_abc123/analysis.json",
      "created_at": "2026-01-17T10:31:00Z"
    }
  ],
  "error": null,
  "created_at": "2026-01-17T10:30:00Z",
  "updated_at": "2026-01-17T10:31:30Z",
  "request_id": "req_xyz789"
}
```

---

### Endpoint 3: Stream Workflow Events (SSE)

```
GET /api/v1/workflows/{workflow_id}/stream

Response: 200 OK (text/event-stream)

Server sends events (newline-delimited JSON):

event: status_changed
data: {
  "workflow_id": "wf_abc123",
  "tenant_id": "tenant_1",
  "request_id": "req_xyz789",
  "event_type": "status_changed",
  "old_status": "SUBMITTED",
  "new_status": "QUEUED",
  "step": "queued",
  "progress_pct": 5,
  "timestamp": "2026-01-17T10:30:01Z"
}

event: step_progressed
data: {
  "workflow_id": "wf_abc123",
  "tenant_id": "tenant_1",
  "request_id": "req_xyz789",
  "event_type": "step_progressed",
  "step": "analyzing_content",
  "progress_pct": 20,
  "timestamp": "2026-01-17T10:30:30Z"
}

event: artifact_created
data: {
  "workflow_id": "wf_abc123",
  "tenant_id": "tenant_1",
  "request_id": "req_xyz789",
  "event_type": "artifact_created",
  "step": "analyzing_content",
  "progress_pct": 25,
  "timestamp": "2026-01-17T10:30:35Z"
}

event: failed
data: {
  "workflow_id": "wf_abc123",
  "tenant_id": "tenant_1",
  "request_id": "req_xyz789",
  "event_type": "failed",
  "old_status": "PROCESSING",
  "new_status": "FAILED",
  "step": "generating_layout",
  "error": {
    "type": "TRANSIENT",
    "message": "Request timeout after 30s",
    "retryable": true
  },
  "timestamp": "2026-01-17T10:31:30Z"
}
```

**Alternative (Polling):**
```
GET /api/v1/workflows/{workflow_id}/events
?since_timestamp=2026-01-17T10:30:00Z
&limit=100

Response: 200 OK
{
  "events": [
    { event_type: "status_changed", ... },
    { event_type: "step_progressed", ... },
    { event_type: "artifact_created", ... },
    ...
  ],
  "has_more": false
}
```

---

### Endpoint 4: Retry Workflow

```
POST /api/v1/workflows/{workflow_id}/retry

Request: {} (or optional refinement data)

Response: 200 OK or 201 Created
{
  "id": "wf_abc123",
  "status": "QUEUED",
  "step": "queued",
  "progress_pct": 5,
  "artifacts": [],  // Cleared from previous run
  "error": null,
  "updated_at": "2026-01-17T10:32:00Z"
}
```

---

### Endpoint 5: Cancel Workflow

```
POST /api/v1/workflows/{workflow_id}/cancel

Response: 200 OK
{
  "id": "wf_abc123",
  "status": "FAILED",
  "error": {
    "type": "USER",
    "message": "Workflow cancelled by user",
    "retryable": false
  }
}
```

---

### Endpoint 6: Refine Workflow (New Iteration)

```
POST /api/v1/workflows/{workflow_id}/refine

Request:
{
  "instructions": "Add more colors. Make the layout 3 columns.",
  "template_preference": "minimal"  // Optional: override template
}

Response: 201 Created
{
  "id": "wf_def456",  // New workflow ID
  "parent_workflow_id": "wf_abc123",  // Reference to original
  "status": "QUEUED",
  "step": "queued",
  "progress_pct": 5,
  "input_data": {
    "refinement_instructions": "Add more colors...",
    "original_source_id": "notebooklm_src_123"
  },
  "artifacts": [],
  "error": null,
  "created_at": "2026-01-17T10:33:00Z"
}
```

---

### Endpoint 7: List Workflows

```
GET /api/v1/workflows?status=COMPLETED&limit=10&offset=0

Response: 200 OK
{
  "workflows": [
    {
      "id": "wf_abc123",
      "status": "COMPLETED",
      "step": "completed",
      "progress_pct": 100,
      "created_at": "2026-01-17T10:30:00Z",
      "updated_at": "2026-01-17T10:35:00Z"
    },
    ...
  ],
  "total": 42,
  "limit": 10,
  "offset": 0
}
```

---

## PART 5: WORKFLOW MODEL FIELDS (API PERSPECTIVE)

**Core Workflow Object:**

```json
{
  "id": "wf_abc123",                    // Unique workflow ID
  "tenant_id": "tenant_1",               // Multi-tenant context
  "user_id": "user_1",                   // User identifier
  "status": "PROCESSING",                // SUBMITTED|QUEUED|PROCESSING|COMPLETED|FAILED
  "step": "generating_layout",           // Current step name
  "progress_pct": 45,                    // 0-100
  "artifacts": [                         // List of outputs
    {
      "name": "design_export",           // Human-readable name
      "content_type": "application/pdf", // MIME type
      "url": "https://...",              // Download URL (nullable)
      "created_at": "2026-01-17T10:31:00Z"
    }
  ],
  "error": {                             // Null if no error
    "type": "TRANSIENT",                 // TRANSIENT|PERMANENT|USER
    "message": "Request timeout...",     // User-friendly message
    "retryable": true                    // Can user retry?
  },
  "created_at": "2026-01-17T10:30:00Z",  // Workflow submission time
  "updated_at": "2026-01-17T10:31:30Z",  // Last status change
  "request_id": "req_xyz789"             // For tracing & support
}
```

---

## PART 6: IMPLEMENTATION NOTES

### T2.4 Scope (Backend Only)

✅ Implemented:
- Workflow model with all fields above
- State machine (SUBMITTED → QUEUED → PROCESSING → COMPLETED|FAILED)
- Event emitter (async generator / callback interface)
- Error classification (Transient/Permanent/User)

⏸️ Not Yet Implemented (documented for future):
- FastAPI SSE endpoint (/stream)
- Real workflow retention (DB persistence)
- Real artifact storage (S3/GCS)
- Polling alternative (/events)
- List workflows pagination
- Retry/cancel/refine endpoints (just the engine)

### T2.5+ Roadmap

- T2.5: API Gateway + Redis Streams (expose endpoints above, with queuing)
- T2.6: Persistence & Recovery (PostgreSQL for workflows, S3 for artifacts)
- T2.7: Client Implementation (Web UI with SSE, mobile app with polling, CLI)

---

## PART 7: TESTING STRATEGY

**Unit Tests (T2.4):**
- Event emission order ✓
- Error classification (transient/permanent) ✓
- State transitions ✓
- Serialization to JSON ✓

**Integration Tests (T2.4):**
- Happy path (SUBMITTED → COMPLETED) ✓
- Failure + retry flow ✓
- Progress tracking ✓
- Event stream (async generator) ✓

**E2E Tests (T2.5+):**
- Full HTTP API workflow (create, stream, complete, download)
- Real adapter integration (mocked externals)
- Error handling across boundaries (API → engine → adapters)
