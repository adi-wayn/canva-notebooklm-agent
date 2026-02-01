# AI Agent Core Architecture

## Overview

This document defines the architecture, responsibilities, and event contract for the AI Agent Core layer that orchestrates NotebookLM and Canva.

---

## Component Diagram

```
User → API → Queue → Worker → DesignAgent → Adapters
                         ↓
                    Agent Events (agent_step)
                         ↓
                    DB (source of truth) → SSE Stream → UI
```

### Data Flow

1. **User submits prompt** via UI
2. **API creates workflow** and enqueues task
3. **Worker polls queue** and loads workflow from DB
4. **Worker creates emit_agent_event closure** (DB + SSE)
5. **Worker calls handler** with AgentContext
6. **Handler instantiates DesignAgent** (thin wrapper)
7. **DesignAgent orchestrates**:
   - Calls NotebookLM adapter
   - Validates canonical output
   - Saves canonical output as artifact
   - Builds Canva design plan
   - Calls Canva adapter
   - Emits semantic events at each step
8. **Events persisted to DB first**, then broadcast via SSE
9. **UI receives events** and displays semantic messages
10. **UI hydrates artifacts** from DB on terminal state

---

## Responsibility Boundaries

### DesignAgent (`src/agent/design_agent.py`)

**Owns**: All business logic for orchestrating NotebookLM → Canva

**Responsibilities**:
- Analyze user prompts
- Extract structured insights from NotebookLM
- Validate against canonical schema
- Save canonical output as artifact
- Build Canva-specific design plan
- Execute Canva design creation
- Emit semantic events at each step
- Handle partial failures gracefully

**Does NOT**:
- Manage database persistence (uses engine)
- Manage SSE broadcasting (uses emit_event closure)
- Handle infrastructure concerns (queue, state machine)

### Workflow Handler (`src/workflows/handlers.py`)

**Owns**: Thin wrapper for agent instantiation

**Responsibilities**:
- Validate inputs (prompt, adapters)
- Create AgentContext
- Instantiate DesignAgent
- Call `agent.execute()`
- Return result

**Does NOT**:
- Contain business logic
- Call adapters directly
- Emit events directly

### Workflow Worker (`src/workers/workflow_worker.py`)

**Owns**: Infrastructure for queue polling and event emission

**Responsibilities**:
- Poll Redis queue for tasks
- Load workflow from DB
- Create `emit_agent_event` closure (DB + SSE)
- Pass closure to handler
- Manage adapter lifecycle
- Update workflow state machine

**Does NOT**:
- Contain business logic
- Know about agent internals

### Event Emitter (`src/workers/event_emitter.py`)

**Owns**: Single source of truth for agent event emission

**Responsibilities**:
- Persist events to DB (source of truth)
- Broadcast events via SSE (best-effort)
- Generate monotonic sequence numbers
- Handle broadcast failures gracefully

**Guarantees**:
- DB persistence happens FIRST
- SSE broadcast happens AFTER
- Sequence numbers are monotonic per workflow
- No alternative emission code paths

---

## Event Emission Contract

### Event Structure

All agent events use the `agent_step` event type with semantic payloads:

```json
{
  "event_type": "agent_step",
  "payload": {
    "event_name": "notebooklm_extraction_completed",
    "message": "Extracted insights from NotebookLM",
    "progress_pct": 30,
    "metadata": {
      "title": "AI in Healthcare",
      "sections_count": 5,
      "first_headings": ["Introduction", "Current State"]
    },
    "event_version": 1,
    "seq": 3,
    "timestamp": "2026-02-02T00:30:00Z"
  }
}
```

### Semantic Event Names

1. **`agent_thinking`** (5%) - Analyzing user prompt
2. **`notebooklm_extraction_started`** (10%) - Starting NotebookLM extraction
3. **`notebooklm_extraction_completed`** (30%) - Extraction complete, summary in metadata
4. **`design_plan_created`** (50%) - Design plan built
5. **`canva_design_started`** (60%) - Creating Canva design
6. **`canva_design_created`** (90%) - Canva design created successfully
7. **`canva_content_partial_warning`** (90%) - Optional warning if content addition failed

### Event Ordering

- **`seq` field**: Monotonic integer per workflow (1, 2, 3, ...)
- **Purpose**: Deterministic ordering even with SSE transport jitter
- **Reset**: Sequence counter resets to 0 at workflow start

### Persistence Strategy

1. **DB First**: Event persisted to `workflow_events` table
2. **SSE Second**: Event broadcast via SSE (best-effort)
3. **Source of Truth**: DB is canonical, UI hydrates from DB on terminal state
4. **Failure Handling**: SSE broadcast failure is non-fatal (logged as warning)

---

## Canonical Artifact Storage

### Artifact Structure

```json
{
  "name": "NotebookLM Extraction (v1.0)",
  "content_type": "application/json",
  "data": {
    "version": "1.0",
    "source": "notebooklm",
    "extraction_metadata": {...},
    "content": {...},
    "validation": {...}
  }
}
```

### Storage Strategy

- **Full JSON in DB**: Canonical output saved as first-class artifact
- **Summary in SSE**: Only title, section count, headings in event metadata
- **Rationale**: Prevents large payloads in SSE stream
- **Access**: UI fetches full artifact from DB on terminal state

---

## AgentContext Design

### Purpose

Bundle all dependencies for agent execution without coupling to raw dicts.

### Structure

```python
@dataclass
class AgentContext:
    workflow_id: str
    tenant_id: str
    notebooklm: Any  # NotebookLMAdapter
    canva: Any  # CanvaAdapter
    emit_event: Callable  # async (event_name, message, progress_pct, metadata) -> None
    logger: logging.Logger
```

### Benefits

- **Type Safety**: Clear dependency injection
- **Testability**: Easy to mock in unit tests
- **Decoupling**: Agent doesn't know about worker internals
- **Clarity**: Explicit dependencies vs implicit dict keys

---

## Backwards Compatibility

### UI Event Handling

- **Agent events**: Mapped to semantic messages ("AI Agent is...")
- **Legacy events**: Still supported (`progress_changed`, `status_changed`)
- **Fallback**: Unknown events display generic "Processing..."

### Workflow Engine

- **No changes**: Agent events are regular `workflow_events` with semantic payloads
- **Infrastructure events**: Still used (`SUBMITTED`, `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`)
- **Decoupling**: Product UX semantics separate from infrastructure state machine

---

## Hard Constraints

### 1. No Mocks in Golden Path

- **ADAPTERS_MOCK_MODE=false** must remain mandatory for demo flow
- Mocks only for CI/tests
- Real NotebookLM and Canva adapters in production

### 2. Single Event Code Path

- All `agent_step` events go through `emit_agent_event()`
- No alternative emitters
- DB persistence first, then SSE broadcast

### 3. Canonical Output as Artifact

- Full JSON stored in DB as artifact
- SSE events only get summary (title/sections/headings)
- Prevents large payloads in event stream

### 4. Strict Ordering

- `seq` field in all agent events
- Monotonic int for deterministic ordering
- UI can sort by seq even with transport jitter

### 5. UI Hydration

- On COMPLETED/FAILED, UI fetches `/workflows/{id}`
- Renders artifacts without requiring refresh
- DB is source of truth, SSE is best-effort

---

## Verification

### Acceptance Criteria

1. ✅ Submit workflow → See semantic steps live → Reach COMPLETED → Canva link appears
2. ✅ Canonical output stored as artifact in DB
3. ✅ All agent events persisted to `workflow_events` table
4. ✅ SSE stream shows events in real-time
5. ✅ Page reload reconstructs state from DB
6. ✅ All three documentation files complete

### Testing Strategy

- **Unit Tests**: Agent emits events in correct order, validates canonical output
- **Integration Tests**: E2E workflow with semantic events, SSE stream verification
- **Browser Tests**: Real UI flow with ADAPTERS_MOCK_MODE=false

---

## Future Evolution

### Schema Versioning

- Current: `version: "1.0"`
- Future: `version: "1.1"` for backwards-compatible changes
- Breaking changes: `version: "2.0"`

### New Event Types

- Add new `event_name` values without modifying infrastructure
- UI can gracefully handle unknown events (fallback to message)

### Agent Variants

- `DesignAgent` for presentations
- `SummaryAgent` for NotebookLM-only workflows
- `AnalyticsAgent` for data visualization

All agents share the same event emission contract and AgentContext pattern.
