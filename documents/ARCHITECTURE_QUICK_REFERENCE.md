# Architecture Quick Reference
## Canva-NotebookLM Integration Agent

---

## SYSTEM ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────────────┐     │
│   │  Web UI      │  │  REST API    │  │  CLI     │  │  SDK / Library   │     │
│   │ (React)      │  │ (OpenAPI)    │  │  Tool    │  │                  │     │
│   └──────┬───────┘  └──────┬───────┘  └────┬─────┘  └────────┬─────────┘     │
│          │                  │                │               │                 │
└──────────┼──────────────────┼────────────────┼───────────────┼─────────────────┘
           │                  │                │               │
           └──────────────────┼────────────────┼───────────────┘
                              │                │
           ┌──────────────────▼────────────────▼──────────────────┐
           │         API GATEWAY (FastAPI)                        │
           ├─────────────────────────────────────────────────────┤
           │  • Request validation & routing                      │
           │  • Authentication (Bearer token, OAuth)              │
           │  • Rate limiting & quota enforcement                 │
           │  • OpenAPI/Swagger docs                              │
           │  • Request tracing (correlation IDs)                 │
           │  • Response formatting & error handling              │
           │  • Middleware chain (logging, CORS, compression)     │
           └────────────┬────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────────┬──────────────────┐
        │                                   │                  │
┌───────▼─────────────┐  ┌────────────────▼─────┐  ┌─────────▼──────────┐
│ ORCHESTRATION       │  │  ADAPTER LAYER       │  │  STATE & DATA      │
│ ENGINE              │  │                      │  │  LAYER             │
├─────────────────────┤  ├──────────────────────┤  ├────────────────────┤
│                     │  │                      │  │                    │
│ • State Machine     │  │  CanvaAdapter        │  │  PostgreSQL        │
│   - Submitted       │  │  • OAuth 2.0/PKCE    │  │  • Workflows       │
│   - Queued          │  │  • Create design     │  │  • Designs         │
│   - Processing      │  │  • Add content       │  │  • Audit logs      │
│   - Completed       │  │  • Export            │  │  • User data       │
│   - Failed          │  │                      │  │                    │
│                     │  │  NotebookLMAdapter   │  │  Redis Cache       │
│ • Task Graph        │  │  • Analyze content   │  │  • Sessions        │
│   Executor          │  │  • Fetch insights    │  │  • Rate limits     │
│   - Topological     │  │  • Get slides        │  │  • Layout cache    │
│     sort            │  │                      │  │                    │
│   - Parallel        │  │  LLMAdapter          │  │  S3 / Artifact     │
│     execution       │  │  • Decide layout     │  │  Store             │
│   - Checkpoint      │  │  • Refine design     │  │  • Exports (PDF,   │
│     state           │  │                      │  │    PNG, PPTX)      │
│                     │  │  Rate Limiter        │  │                    │
│ • Decision Engine   │  │  • Per-service quota │  │  Secrets Vault     │
│   (LLM-based)       │  │  • Backpressure      │  │  • API keys        │
│   - Content         │  │  • Token bucket      │  │  • OAuth tokens    │
│     abstraction     │  │                      │  │  • Encryption key  │
│   - Layout          │  │  Circuit Breaker     │  │                    │
│     planning        │  │  • Failure tracking  │  │  Audit Logs        │
│   - Brand           │  │  • Recovery          │  │  • Immutable       │
│     enforcement     │  │                      │  │  • Compliance      │
│                     │  │  Retry Manager       │  │                    │
│ • Event Emission    │  │  • Exponential       │  │                    │
│   - on state        │  │    backoff           │  │                    │
│     change          │  │  • Max retries       │  │                    │
│                     │  │                      │  │                    │
└─────────┬───────────┘  └──────────┬───────────┘  └────────┬───────────┘
          │                         │                       │
          │                         └──────────────────────┐│
          │                                                ││
     ┌────▼─────────────────────────────────────────────┐ ││
     │  ASYNC TASK QUEUE (Redis Streams)               │ ││
     ├──────────────────────────────────────────────────┤ ││
     │  • Priority queues (high, normal, low)           │ ││
     │  • Task state tracking                           │ ││
     │  • Worker distribution                           │ ││
     │  • Dead-letter queue (failed tasks)              │ ││
     │  • Consumer groups (worker coordination)         │ ││
     └────┬───────────────────────────────────────────┬─┘ ││
          │                                           │    ││
     ┌────▼──────────────────┐  ┌──────────────────────▼──┘│
     │  WORKER POOL          │  │   ┌────────────────────┐ │
     ├───────────────────────┤  │   │  OBSERVABILITY    │ │
     │                       │  │   │  LAYER             │ │
     │ • Transformer Workers │  │   ├────────────────────┤ │
     │   (scale: 8-50)       │  │   │                    │ │
     │   - Claim tasks       │  │   │ Structured Logging │ │
     │   - Execute workflow  │  │   │ (JSON → ELK)       │ │
     │   - Update state      │  │   │                    │ │
     │                       │  │   │ Distributed Tracing│ │
     │ • Poller Workers      │  │   │ (OpenTelemetry    │ │
     │   (scale: 2-4)        │  │   │  → Jaeger)         │ │
     │   - Poll NotebookLM   │  │   │                    │ │
     │   - Check status      │  │   │ Metrics Collection │ │
     │                       │  │   │ (Prometheus)       │ │
     │ • Cleanup Workers     │  │   │                    │ │
     │   (scale: 1-2)        │  │   │ Alerting           │ │
     │   - Expire artifacts  │  │   │ (AlertManager)     │ │
     │   - Compact logs      │  │   │                    │ │
     │                       │  │   │ Audit Trail        │ │
     │ • Metrics Workers     │  │   │ (PostgreSQL)       │ │
     │   (scale: 1)          │  │   │                    │ │
     │   - Collect metrics   │  │   └────────────────────┘ │
     │   - Push to Prometheus│  │                           │
     │                       │  └───────────────────────────┘
     └───────────────────────┘
           │
     ┌─────▼──────────────────────────────────────────────────┐
     │         EXTERNAL SERVICES (Cloud APIs)                │
     ├──────────────────────────────────────────────────────────┤
     │                                                         │
     │  • Canva API (https://api.canva.com/v1)               │
     │  • NotebookLM API (https://api.notebooklm.com/v1)    │
     │  • OpenAI API (LLM reasoning)                         │
     │  • SMTP Service (notifications)                       │
     │                                                         │
     └──────────────────────────────────────────────────────────┘
```

---

## DATA FLOW: HAPPY PATH

```
1. USER SUBMITS WORKFLOW
   ┌──────────────────────────────────────────────────────┐
   │ Web UI → POST /api/v1/workflows                     │
   │ {                                                    │
   │   "workflow_type": "content_to_presentation",        │
   │   "source_id": "notebooklm_src_123",                │
   │   "title": "Q4 Marketing Strategy"                  │
   │ }                                                    │
   └──────────────────────────────────────────────────────┘
                          │
                          ▼
2. API GATEWAY VALIDATES & AUTHENTICATES
   ├─ Check Bearer token
   ├─ Extract tenant_id, user_id
   ├─ Generate correlation ID
   ├─ Validate input schema
   └─ Rate limit check
                          │
                          ▼
3. ORCHESTRATOR CREATES WORKFLOW
   ├─ Create Workflow record (status: QUEUED)
   ├─ Emit event: workflow.submitted
   ├─ Enqueue task to Redis Streams
   └─ Return { workflow_id: "wf_abc123", status: "QUEUED" }
                          │
                          ▼
4. TASK QUEUE (Redis Streams)
   └─ Task waits for worker to claim it
                          │
                          ▼
5. WORKER CLAIMS & PROCESSES TASK
   ├─ Claim task from stream
   ├─ Update Workflow.status → PROCESSING
   └─ Execute workflow (see below)
                          │
                          ▼
6. WORKFLOW EXECUTION (State Machine)
   
   TASK 1: analyze_content
   ├─→ NotebookLM Adapter: analyze_source(src_123)
   ├─→ Wait for analysis (polling or webhook)
   ├─→ Extract: insights, outline, slides, references
   └─→ Cache result; emit event: content_analyzed
                          │
                          ▼
   TASK 2: plan_layout
   ├─→ LLM Adapter: decide_layout(content, brand_guidelines)
   ├─→ LLM decides: template, colors, fonts, layout
   ├─→ Cache decision (embeddings-based)
   └─→ Emit event: layout_planned
                          │
                          ▼
   TASK 3: create_design
   ├─→ Canva Adapter: create_presentation(title, template)
   ├─→ Canva returns design_id
   ├─→ Store design record in DB
   └─→ Emit event: design_created
                          │
                          ▼
   TASK 4: populate_slides
   ├─→ For each content block:
   │   ├─→ Canva Adapter: add_text_block(design_id, text)
   │   ├─→ Canva Adapter: add_image(design_id, img_url)
   │   └─→ Apply typography & spacing
   └─→ Emit event: slides_populated
                          │
                          ▼
   TASK 5: finalize
   ├─→ Canva Adapter: apply_brand_colors(design_id)
   ├─→ Canva Adapter: export_design(design_id, formats=[pdf, png])
   ├─→ Upload to S3; generate signed URLs
   └─→ Emit event: design_finalized
                          │
                          ▼
7. WORKFLOW COMPLETION
   ├─ Update Workflow.status → COMPLETED
   ├─ Store output_artifacts (URLs, design_id, metadata)
   ├─ Mark task as acknowledged in queue
   ├─ Emit event: workflow.completed
   └─ Schedule cleanup (7-day retention)
                          │
                          ▼
8. CLIENT POLLS STATUS
   GET /api/v1/workflows/wf_abc123
   Response: {
     "status": "COMPLETED",
     "output_artifacts": {
       "design_id": "canva_123abc",
       "pdf_url": "https://s3.../export.pdf?token=...",
       "png_url": "https://s3.../export.png?token=...",
       "created_at": "2026-01-17T10:45:30Z"
     }
   }
                          │
                          ▼
9. CLIENT DOWNLOADS ARTIFACTS
   GET <pdf_url> → Download PDF from S3
```

---

## DATA FLOW: ERROR RECOVERY

```
During TASK 2 (plan_layout):
   LLM API timeout (transient error)
                          │
                          ▼
1. WORKER DETECTS ERROR
   ├─ Catch exception (LLMTimeout)
   ├─ Check retry_count (0 < max_retries: 3)
   └─ Log error with context
                          │
                          ▼
2. RETRY DECISION
   ├─ Calculate backoff: 100ms * 2^0 = 100ms
   ├─ Create retry task with delay
   └─ Enqueue to queue with scheduled time
                          │
                          ▼
3. WAIT & RETRY
   ├─ Task sits in queue for 100ms
   ├─ After 100ms, task becomes ready again
   └─ Another worker picks it up
                          │
                          ▼
4. WORKER RETRIES TASK 2
   ├─ If succeeds:
   │  └─ Continue to TASK 3 (create_design)
   │
   └─ If fails again:
      ├─ Backoff: 200ms, retry_count = 2
      └─ Enqueue with 200ms delay
                          │
                          ▼
5. AFTER MAX_RETRIES EXCEEDED (3 attempts failed)
   ├─ Move task to dead-letter queue
   ├─ Update Workflow.status → FAILED
   ├─ Update Workflow.error_log:
   │  {
   │    "task": "plan_layout",
   │    "error": "LLM timeout after 3 retries",
   │    "last_error_time": "2026-01-17T10:45:35Z"
   │  }
   ├─ Emit event: workflow.failed
   └─ Alert on-call if error_rate > 5%
```

---

## MULTI-TENANCY ISOLATION

```
User A (tenant: acme.com)
├─ Credentials: { canva_token: "...", notebooklm_key: "..." }
│  └─ Stored encrypted in Vault with tenant_id
│
├─ Workflows:
│  ├─ wf_001 (status: COMPLETED)
│  ├─ wf_002 (status: PROCESSING)
│  └─ wf_003 (status: QUEUED)
│  └─ ALL query filtered: WHERE tenant_id = 'acme.com'
│
├─ Quota:
│  └─ 10,000 designs/month (5,234 used)
│  └─ 100 concurrent workflows
│  └─ Rate limit: 100 API calls/minute
│
└─ Audit Trail:
   ├─ "user_a submitted workflow wf_001"
   ├─ "workflow wf_001 completed"
   └─ ALL entries tagged with tenant_id

User B (tenant: startup.io) — COMPLETELY ISOLATED
├─ Credentials: different tokens in Vault
├─ Workflows: separate database records
├─ Quota: different limits
└─ Audit Trail: separate entries

Network isolation also: Each tenant's data cannot cross boundaries
```

---

## STATE MACHINE: WORKFLOW LIFECYCLE

```
                    ┌─────────────────┐
                    │   SUBMITTED     │
                    │ (User submits)  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │    QUEUED       │
                    │ (Waiting for    │
                    │  worker)        │
                    └────────┬────────┘
                             │
                             ▼
                 ┌───────────────────────────┐
                 │  ANALYZING_SOURCES        │
                 │ (Fetch from NotebookLM)   │
                 └────────┬──────────────────┘
                          │
                 ◄────────┴─────────► PAUSED (user action)
                 │
                 ▼
        ┌────────────────────────────┐
        │  GENERATING_LAYOUT         │
        │ (LLM decides structure)     │
        └────────┬───────────────────┘
                 │
        ◄────────┴─────────► PAUSED (user action)
                 │
                 ▼
        ┌────────────────────────────┐
        │  CREATING_DESIGN           │
        │ (Canva creates blank)      │
        └────────┬───────────────────┘
                 │
        ◄────────┴─────────► PAUSED (user action)
                 │
                 ▼
        ┌────────────────────────────┐
        │  POPULATING_CONTENT        │
        │ (Insert text, images)      │
        └────────┬───────────────────┘
                 │
        ◄────────┴─────────► PAUSED (user action)
                 │
                 ▼
        ┌────────────────────────────┐
        │  REFINING_VISUALS          │
        │ (Colors, fonts, effects)   │
        └────────┬───────────────────┘
                 │
        ◄────────┴─────────► PAUSED (user action)
                 │
                 ▼
        ┌────────────────────────────┐
        │  GENERATING_ARTIFACTS      │
        │ (Export PDF, PNG, etc.)    │
        └────────┬───────────────────┘
                 │
                 ├──────► COMPLETED ✓
                 │
                 └──────► FAILED (at any stage)
                          │
                          ▼
                    ┌──────────────┐
                    │  RETRY_      │
                    │  BACKLOG     │
                    │  (exponential│
                    │   backoff)   │
                    └──────┬───────┘
                           │
                           ├──────► PROCESSING (retry)
                           │
                           └──────► DEAD_LETTER (max retries exceeded)

User can:
- PAUSE at any stage
- RESUME from pause
- CANCEL (cleanup)
- REGENERATE (start at specific task)
```

---

## ADAPTER PATTERN (Provider Abstraction)

```
Canva Adapter Interface (Abstract)
┌─────────────────────────────────────┐
│ class CanvaAdapterInterface(ABC):   │
│   async def create_presentation()   │
│   async def add_text_block()        │
│   async def export_design()         │
│   ... (etc)                         │
└─────────────────────────────────────┘
         ▲
         │ implements
         │
    ┌────┴──────────────────────────────────┐
    │                                       │
    │ CanvaAdapterImpl                       │
    │ (production)                          │
    │ - Uses httpx to call real API         │
    │ - Handles OAuth token refresh         │
    │ - Rate limiting middleware            │
    │ - Error mapping & retries             │
    │ - Circuit breaker                     │
    │                                       │
    └───────────────────────────────────────┘
    
    Benefit: Easy to swap for testing, different implementations

Test usage:
┌──────────────────────────────────┐
│ MockCanvaAdapter                 │
│ (for unit tests)                 │
│ - Returns fake responses         │
│ - No network calls               │
│ - Instant execution              │
└──────────────────────────────────┘

Production usage:
┌──────────────────────────────────┐
│ CanvaAdapterImpl (real)           │
│ (for production)                 │
│ - Calls real Canva API           │
│ - Full error handling            │
│ - Rate limiting enforced         │
└──────────────────────────────────┘
```

---

## TECHNOLOGY STACK AT A GLANCE

```
┌─────────────┬──────────────────────┬───────────────────────┐
│ Layer       │ Technology           │ Purpose               │
├─────────────┼──────────────────────┼───────────────────────┤
│ API         │ FastAPI + Starlette  │ HTTP server, routing  │
│             │ Pydantic             │ Data validation       │
│             │ OpenAPI/Swagger      │ Documentation         │
├─────────────┼──────────────────────┼───────────────────────┤
│ Runtime     │ Python 3.8+ asyncio  │ Async execution       │
│             │ uvicorn              │ ASGI server           │
├─────────────┼──────────────────────┼───────────────────────┤
│ Persistence │ PostgreSQL 12+       │ Relational data       │
│             │ Alembic              │ Schema migrations     │
│             │ SQLAlchemy ORM       │ Object mapping        │
├─────────────┼──────────────────────┼───────────────────────┤
│ Cache       │ Redis 6.0+           │ Session, cache, locks │
│             │ Redis Streams        │ Task queue            │
├─────────────┼──────────────────────┼───────────────────────┤
│ Secrets     │ HashiCorp Vault      │ Credential storage    │
│             │ .env (dev)           │ Development config    │
├─────────────┼──────────────────────┼───────────────────────┤
│ Observ.     │ JSON + Fluentd       │ Log aggregation       │
│             │ Elasticsearch        │ Log storage           │
│             │ Kibana               │ Log visualization     │
│             ├──────────────────────┼───────────────────────┤
│             │ OpenTelemetry        │ Distributed tracing   │
│             │ Jaeger               │ Trace storage & UI    │
│             ├──────────────────────┼───────────────────────┤
│             │ Prometheus           │ Metrics collection    │
│             │ Grafana              │ Metrics visualization │
│             ├──────────────────────┼───────────────────────┤
│             │ AlertManager         │ Alert routing         │
├─────────────┼──────────────────────┼───────────────────────┤
│ Artifacts   │ S3 / MinIO           │ File storage (PDF,    │
│             │                      │ PNG, exports)         │
├─────────────┼──────────────────────┼───────────────────────┤
│ Container   │ Docker               │ Image packaging       │
│             │ Kubernetes           │ Orchestration (prod)  │
│             │ Docker Compose       │ Local dev              │
├─────────────┼──────────────────────┼───────────────────────┤
│ CI/CD       │ GitHub Actions       │ Tests, build, deploy  │
│             │ (or GitLab CI)       │                       │
├─────────────┼──────────────────────┼───────────────────────┤
│ Testing     │ pytest               │ Test framework        │
│             │ httpx                │ HTTP client testing   │
│             │ Mock/Unittest        │ Mocking               │
│             │ Locust               │ Load testing          │
└─────────────┴──────────────────────┴───────────────────────┘
```

---

## DEPLOYMENT TOPOLOGY

```
DEVELOPMENT (Local)
├─ Single machine
├─ Python venv
├─ PostgreSQL (Docker)
├─ Redis (Docker)
└─ Logs to stdout

STAGING (Cloud)
├─ Cloud VM (e.g., EC2 t3.large)
├─ Docker containers
├─ RDS PostgreSQL
├─ ElastiCache Redis
├─ CloudWatch logs
└─ Manual deploy

PRODUCTION (Kubernetes)
├─ 3+ node K8s cluster
├─ Namespace: canva-notebooklm-prod
├─ Pods:
│  ├─ API Gateway (3 replicas, HPA 1-10)
│  ├─ Workers (10-50 replicas, HPA based on queue depth)
│  ├─ PostgreSQL (1 primary + 2 replicas, StatefulSet)
│  └─ Redis (3 replicas, Sentinel)
├─ Services:
│  ├─ api (ClusterIP, internal)
│  ├─ ingress (LoadBalancer, public)
│  └─ postgres (Headless, internal)
├─ ConfigMaps: app config
├─ Secrets: API keys, DB passwords
├─ PVC: logs, artifacts (S3 preferred)
├─ Monitoring: Prometheus, Grafana
└─ Ingress: TLS termination, rate limiting
```

---

## TESTING PYRAMID

```
                    ▲
                   /│\
                  / │ \
                 /  │  \     E2E Tests (5%)
                /───┼───\    "Does the system work end-to-end?"
               /    │    \   • Full workflow submission to completion
              ├─────┼─────┤  • Real (or mocked) API calls
             /      │      \  • Database integration
            /───────┼───────\ • 50-100 tests
           /        │        \ (2-3 hours to run)
          ├─────────┼─────────┤
         /          │          \  Integration Tests (15%)
        /───────────┼───────────\ "Do the components work together?"
       /            │            \ • Adapter + Database
      ├─────────────┼─────────────┤ • API + Queue
     /              │              \ • Worker + Storage
    /───────────────┼───────────────\ • 150-250 tests
   /                │                \ (10-15 minutes to run)
  ├─────────────────┼─────────────────┤
 /                  │                  \  Unit Tests (80%)
/────────────────────┼────────────────────\ "Does each function work?"
                     │                     • Individual functions/methods
                     │                     • Mocked dependencies
                     │                     • 1000-2000 tests
                     │                     (1-2 minutes to run)
```

---

## PHASE 0-7 ROADMAP (GANTT)

```
             W1  W2  W3  W4  W5  W6  W7  W8  W9  W10 W11 W12 W13 W14 W15 W16
             |---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
Phase 0:     ███
Phase 1:         ███████
Phase 2:             ███████████
Phase 3:                     ███████████████
Phase 4:                                 ███████
Phase 5:                                     ███████
Phase 6:                                         ███████
Phase 7:                                             ███████

Parallelizable:
- Phase 1 Task 1 & 2 (DB + Cache): Can proceed in parallel
- Phase 2 Tasks: (Canva + NotebookLM can proceed in parallel)
- Phase 4 Tasks: (API + Queue in parallel after Phase 3)
- Phase 5 Tasks: (Unit tests + integration tests parallel)
- Phase 6 Tasks: (ELK + Jaeger + Prometheus parallel)

Critical Path: Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5+

With proper parallelization and a focused team, can compress to 12-14 weeks.
```

---

**See main documents for details:**
- [STEP1_ANALYSIS.md](./STEP1_ANALYSIS.md) — Requirements
- [STEP2_ARCHITECTURE.md](./STEP2_ARCHITECTURE.md) — Detailed design
- [STEP3_DEVELOPMENT_PLAN.md](./STEP3_DEVELOPMENT_PLAN.md) — Phase breakdown

