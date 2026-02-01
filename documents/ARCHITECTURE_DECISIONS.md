# Architecture Decision Record (ADR) Log
## Canva-NotebookLM Integration Agent

This document records major architectural decisions and their rationale.

---

## ADR-001: Adapter Pattern for External APIs

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Implement provider-agnostic adapter interfaces to abstract external API calls (Canva, NotebookLM, LLM).

### Context
- Need to support multiple external APIs with different rate limits, auth schemes, error handling
- System must be resilient to provider changes or replacements
- Testing requires mocking without coupling to implementation details

### Options Considered
1. **Direct API calls in orchestration** — Simple but tight coupling; hard to test; error handling repeated
2. **Adapter pattern (chosen)** — More complex initially; excellent separation; easy to test & replace
3. **API gateway pattern** — Over-engineered for MVP; adds latency

### Decision
Use adapter pattern with:
- Abstract interfaces (Python ABC)
- Multiple implementations (real prod, mock for testing)
- Rate limiting & circuit breaker at adapter layer
- Provider-specific error mapping

### Consequences
✅ Easy to swap implementations (testing, fallbacks, updates)  
✅ Centralized error handling & retry logic  
✅ Clear contracts between components  
❌ More boilerplate code upfront  
❌ Need to maintain multiple implementations initially

### Related Decisions
- ADR-003 (Retry & Backoff Strategy)
- ADR-004 (Error Handling)

---

## ADR-002: Redis Streams for Task Queue

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Use Redis Streams (not RabbitMQ, Celery, or Kafka) for asynchronous task processing in MVP.

### Context
- Need to decouple request submission from processing
- Support horizontal scaling with worker pool
- Handle retries, dead-letter queues, consumer groups
- Local development must work without complex dependencies
- Eventually scale to high throughput

### Options Considered
1. **RabbitMQ** — Mature, feature-rich, but adds operational complexity; overkill for MVP
2. **Celery + Redis** — Good option; adds dependency on Celery abstractions; more overhead
3. **Kafka** — Overkill; designed for streaming pipelines; high ops complexity
4. **Redis Streams (chosen)** — Built-in to Redis; consumer groups; simple; scales well
5. **In-memory async task queue** — Only for local dev; not production-ready

### Decision
Use Redis Streams with:
- Multiple priority streams (high, normal, low)
- Consumer groups for worker coordination
- Dead-letter queue for failed tasks
- Upgrade path to RabbitMQ if needed

### Consequences
✅ Minimal additional dependencies  
✅ Great for MVP; proven at scale  
✅ Easy local development (single Redis instance)  
✅ Built-in consumer groups & acknowledgment  
❌ Message ordering guarantees differ from RabbitMQ  
❌ If throughput >> 10k msg/sec, may need RabbitMQ later

### Upgrade Path
If MVP requires > 10k msg/sec or stream replication:
1. Keep adapters, just replace queue implementation
2. Add RabbitMQ alongside Redis
3. Deprecate Redis Streams for new tasks (keep for backward compat)

### Related Decisions
- ADR-005 (Worker Pool Architecture)

---

## ADR-003: Exponential Backoff for Retries

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Implement exponential backoff with jitter for transient API failures.

### Context
- External APIs (Canva, NotebookLM) may be temporarily unavailable or rate-limited
- Naive retry (immediate) can overwhelm failing service
- Need to balance resilience with latency

### Backoff Formula
```
backoff_ms = initial_backoff_ms * (multiplier ^ attempt) + random_jitter_ms
```

Configuration (per operation type):
```
Text-to-design (Canva): 
  - initial: 100ms, multiplier: 2, max: 30s, max_attempts: 3
  
Content analysis (NotebookLM): 
  - initial: 200ms, multiplier: 2, max: 60s, max_attempts: 5
```

### Consequences
✅ Gracefully degrades during provider outages  
✅ Jitter prevents thundering herd  
✅ Configurable per operation type  
❌ Increases e2e latency in failure case (acceptable tradeoff)

### Example Timeline
```
Attempt 1: 100ms wait, then retry
Attempt 2: 100-300ms wait (100*2 + jitter), then retry
Attempt 3: 200-600ms wait (100*4 + jitter), then retry
Max: 30s per attempt, give up after 3
Total: ~1.5 sec worst case
```

---

## ADR-004: Multi-Tenancy by Design

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Build multi-tenancy isolation from day 1, not as afterthought.

### Context
- Product likely to be SaaS or internal tool with multiple teams/orgs
- Adding multi-tenancy later is expensive (audit, security, performance implications)
- Data isolation and quota enforcement must be built-in

### Implementation
- Every table has `tenant_id` FK
- All queries filtered by `tenant_id`
- Credentials stored per-tenant in Secrets Vault
- Quota tracking per-tenant
- Audit logs include tenant_id + user_id
- Rate limiting per-tenant + per-user

### Consequences
✅ Simple to move from single→multi-tenant later  
✅ Quota enforcement at database level  
✅ Clear audit trail for compliance  
✅ Easy to on-board new tenants  
❌ Slightly more query overhead (but negligible with indexes)

### Security Guarantee
Impossible for User A (tenant A) to see User B's (tenant B) data due to schema design.

---

## ADR-005: Worker Pool Architecture

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Implement horizontal scaling with stateless workers + Redis queue.

### Context
- Single-threaded FastAPI handler cannot process long-running workflows
- Need to process 100s of concurrent workflows
- Must support elastic scaling (add/remove workers dynamically)

### Architecture
```
API Gateway (stateless, 3-10 replicas)
    ↓
Redis Streams (shared state)
    ↓
Worker Pool (stateless, 10-50 replicas)
    - All workers identical
    - Can die/restart without data loss
    - Heartbeat detects failures
```

### Consequences
✅ Linear scaling (add workers = more throughput)  
✅ Fault tolerance (worker crash doesn't lose work)  
✅ Easy monitoring (queue depth, worker count)  
❌ Eventual consistency (workflow state lag between updates)

### Monitoring
- Queue depth (num tasks waiting)
- Active workers (num claimed tasks)
- Worker heartbeat (detect stalls)
- Task latency (p50, p95, p99)

---

## ADR-006: LLM as Decision Engine, Not Orchestrator

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Use LLM for semantic decisions (layout planning, content abstraction) but keep orchestration deterministic.

### Context
- LLMs are great at reasoning about content (structure, design) but not good at state management
- Need reliable, debuggable workflow execution
- Decisions should be cacheable and consistent

### Split of Responsibilities
```
Deterministic Orchestration:
  - State transitions (SUBMITTED → QUEUED → PROCESSING)
  - Task graph execution
  - Retry logic
  - Error handling
  
LLM-Based Decisions:
  - "Given this content, what template should we use?"
  - "What colors match this brand guide?"
  - "Suggest improvements to this design"
```

### Consequences
✅ Reliable, reproducible workflow execution  
✅ Easy to debug (state is explicit)  
✅ Can swap LLM without changing orchestration  
✅ Decisions are cached (reduce LLM costs)  
❌ Some nuance lost if rules-based fallback used

### Cache Strategy
- Embeddings-based similarity for layout decisions
- Hash-based cache for fixed content
- TTL: 90 days

---

## ADR-007: Structured Logging with JSON

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
All logging is JSON format with structured fields, no human-readable strings.

### Context
- Need to aggregate and query logs from many workers
- Must support root-cause analysis in production
- Compliance may require immutable audit trail

### Log Format
```json
{
  "timestamp": "2026-01-17T10:45:30Z",
  "level": "INFO",
  "logger": "src.orchestration.workflow_engine",
  "message": "workflow.started",
  "workflow_id": "wf_abc123",
  "user_id": "user_456",
  "tenant_id": "acme.com",
  "request_id": "req_xyz789",
  "duration_ms": 150,
  "error": null
}
```

### Toolchain
- **Collection**: Python `logging` module (custom JSONFormatter)
- **Aggregation**: Fluentd or Logstash
- **Storage**: Elasticsearch
- **Query/Visualization**: Kibana

### Consequences
✅ Machine-parseable logs  
✅ Easy full-text search + filtering  
✅ Integration with APM tools  
✅ Compliance-friendly (immutable in Elasticsearch)  
❌ Requires discipline (never printf debugging in prod)

---

## ADR-008: Distributed Tracing from Day 1

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Instrument entire system with OpenTelemetry for distributed tracing from start.

### Context
- Multi-service system (API, workers, adapters) with async flows
- Need to debug issues in production
- Trace end-to-end request flow across services

### Trace Structure
```
trace_id: "trace_abc123"
  ├─ span: http_request (API)
  │   ├─ span: authenticate
  │   ├─ span: enqueue_task
  │   └─ span: return_response
  │
  ├─ span: task_processing (Worker)
  │   ├─ span: analyze_content
  │   │   └─ span: notebooklm_api_call
  │   ├─ span: plan_layout
  │   │   └─ span: llm_api_call
  │   └─ ...
  │
  └─ span: database_write
      └─ SQL query + duration
```

### Export & Storage
- **Collector**: OpenTelemetry collector (optional)
- **Backend**: Jaeger (all-in-one for MVP)
- **Query UI**: Jaeger UI

### Consequences
✅ Complete visibility into request flow  
✅ Easy to identify bottlenecks  
✅ Root-cause analysis (trace each error back to origin)  
❌ Overhead (1-2% latency increase)  
❌ Storage cost (traces can be large)

---

## ADR-009: PostgreSQL with JSONB for Semi-Structured Data

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Use PostgreSQL with JSONB columns for flexible, schema-less attributes while maintaining relational integrity.

### Context
- Workflow configs, LLM decisions, API responses vary by type
- Need to query structured data (workflow status, user_id) relationally
- But also store flexible metadata without schema migration

### Example Schema
```sql
CREATE TABLE workflows (
  id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,          -- Relational
  user_id UUID NOT NULL,            -- Relational
  status VARCHAR,                   -- Relational (indexed)
  
  input_config JSONB,               -- Semi-structured
  output_artifacts JSONB,           -- Semi-structured
  error_log JSONB,                  -- Semi-structured
  
  created_at TIMESTAMP,             -- Relational (indexed)
  
  INDEX (tenant_id, user_id, created_at)
);
```

### Consequences
✅ Best of both worlds (relational + flexible)  
✅ Can query JSONB: `WHERE input_config->>'workflow_type' = 'presentation'`  
✅ Easy to evolve without migrations  
✅ Excellent performance (JSONB is indexed)  
❌ JSONB queries less performant than relational (but usually fine)

### Related Decisions
- ADR-002 (Redis Streams for caching)

---

## ADR-010: Observability as First-Class Citizen

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Invest in observability (logging, tracing, metrics) from day 1, not as afterthought.

### Rationale
- Debugging production issues without observability is nearly impossible
- Performance bottlenecks hidden until too late
- Multi-tenant system requires detailed audit trail

### Three Pillars
1. **Logs** (What happened?) — JSON logs → Elasticsearch
2. **Traces** (How did it happen?) — Distributed traces → Jaeger
3. **Metrics** (How much?) — Prometheus metrics → Grafana

### Key Metrics
- Request volume (requests/sec per endpoint)
- Latency (p50, p95, p99 per operation)
- Error rate (% failed requests)
- Queue depth (pending tasks)
- Worker utilization (active/idle workers)
- API quota usage (per provider, per tenant)

### Consequences
✅ Production debugging becomes feasible  
✅ Capacity planning data-driven  
✅ Performance improvements traceable  
✅ Compliance audit trail natural byproduct  
❌ Operational overhead (3 additional services: ELK, Jaeger, Prometheus)  
❌ Storage costs (logs/traces accumulate)

### MVP Implementation
- Logs: JSON to stdout (parse with Fluentd later)
- Traces: No-op exporter (Jaeger optional)
- Metrics: Prometheus exporter on `/metrics`

### Production Implementation
- Logs: Elasticsearch 7+ with 30-day retention
- Traces: Jaeger backend with 7-day retention
- Metrics: Prometheus + Grafana with 1-year storage

---

## ADR-011: API-First Design

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
REST API is the source of truth; UI/CLI/SDK all consume the same API.

### Context
- Multiple client types (web UI, CLI, mobile SDK, third-party integrations)
- If UI owns business logic, other clients must duplicate it
- API-first ensures consistency and enables extensibility

### API Guarantees
- OpenAPI 3.0 schema
- Pagination & filtering standard
- Error responses consistent (RFC 7807)
- Rate limiting headers (RateLimit-*, Retry-After)
- Webhook notifications for long-running operations

### Consequence of API-First
✅ Web UI is "just another client"  
✅ Easy to add CLI, mobile, SDKs later  
✅ Third-party integrations possible  
✅ Better testability (API specs are executable)  
❌ UI slightly more complex (must handle async workflows)

### Client Implementation Example
```python
# Python SDK (uses API)
client = CanvaNotebookLMClient(api_key="...", base_url="https://...")
workflow = client.workflows.create(
    workflow_type="content_to_presentation",
    source_id="notebooklm_src_123"
)
```

---

## ADR-012: Cost & Reliability Tradeoff: Polling vs Webhooks

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Use polling as default for NotebookLM completion; upgrade to webhooks if available.

### Context
- NotebookLM analysis takes 5-30 seconds (asynchronous)
- Options: Client polls for status, or provider sends webhook on completion
- Polling is simpler to implement; webhooks scale better

### Strategy
1. **MVP**: Polling every 5 seconds (simple, works locally)
2. **If NotebookLM supports webhooks**: Register callback URL; handle webhook in API
3. **Hybrid**: Polling as fallback if webhook delivery fails

### Polling Implementation
```python
async def poll_until_complete(notebook_id: str, timeout_ms: int = 600000):
    start = time.time()
    poll_interval_ms = 5000  # 5 seconds
    
    while (time.time() - start) * 1000 < timeout_ms:
        status = await notebooklm_adapter.poll_status(notebook_id)
        if status.is_complete:
            return status
        await asyncio.sleep(poll_interval_ms / 1000)
    
    raise TimeoutError(f"Analysis did not complete within {timeout_ms}ms")
```

### Webhook Implementation (if available)
```python
@app.post("/webhooks/notebooklm/analysis_complete")
async def handle_analysis_complete(payload: NotebookLMWebhook):
    notebook_id = payload.notebook_id
    # Resume waiting workflow
    await workflow_engine.resume_from_analysis(notebook_id)
```

### Consequences
✅ Polling: Simple, works everywhere, no infrastructure needed  
✅ Webhooks: Faster completion, lower resource usage  
❌ Polling: 5-sec delay + network overhead  
❌ Webhooks: Requires public API endpoint, IP whitelisting

---

## ADR-013: Error Categorization

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Categorize errors by recoverability: Transient (retry), Permanent (fail), User (feedback).

### Error Categories

**Transient Errors** (Retry with backoff)
- Network timeout
- 5xx server errors
- Rate limit exceeded (429)
- Temporarily resource unavailable
- Action: Exponential backoff, max 3 attempts

**Permanent Errors** (Fail immediately)
- 4xx client errors (malformed request)
- Authentication failure (401)
- Authorization failure (403)
- Resource not found (404)
- Invalid configuration
- Action: Move to dead-letter queue, notify user

**User Errors** (Require user action)
- Source content invalid
- Incompatible template selection
- Insufficient quota
- Action: Return actionable error message, suggest fix

### Error Response Format
```json
{
  "error_id": "err_abc123",
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "API rate limit exceeded",
  "category": "TRANSIENT",
  "details": {
    "service": "canva",
    "limit": 100,
    "current": 101,
    "reset_at": "2026-01-17T10:46:00Z"
  },
  "recoverable": true,
  "suggested_action": "Retry after 60 seconds"
}
```

### Consequences
✅ Deterministic error handling  
✅ Clients can make smart decisions (retry vs fail)  
✅ Observability (categorize errors for metrics)  
❌ More error types to handle

---

## ADR-014: Deployment Strategy

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Support three deployment modes: Local (dev), Cloud VM (staging), Kubernetes (production).

### Deployment Modes

**Local (Development)**
```
Docker Compose:
  - API container (FastAPI)
  - PostgreSQL container
  - Redis container
Single-machine, all-in-one
```

**Cloud VM (Staging)**
```
Single VM (e.g., AWS EC2 t3.large):
  - API service (systemd or Docker)
  - Worker processes (systemd or Docker)
  - PostgreSQL (managed RDS or local)
  - Redis (ElastiCache or local)
Manual or basic automation
```

**Kubernetes (Production)**
```
Multi-node K8s cluster:
  - API Deployment (3 replicas, HPA)
  - Worker Deployment (10-50 replicas, HPA)
  - PostgreSQL StatefulSet
  - Redis StatefulSet
Fully automated scaling and recovery
```

### CI/CD Pipeline
```
Git push → GitHub Actions:
  1. Lint (pylint, flake8)
  2. Type check (mypy)
  3. Unit tests (pytest)
  4. Build Docker image
  5. Push to registry
  6. Deploy to staging (auto)
  7. Integration tests (on staging)
  8. (Manual approval)
  9. Deploy to production (manual)
```

### Consequences
✅ Same code in all environments  
✅ Easy local development  
✅ Staging mirrors production  
✅ Production ready for scale  
❌ Kubernetes adds operational complexity  
❌ Must maintain multiple deployment configs

---

## ADR-015: Security: Secrets Management

**Status**: DECIDED | **Date**: 2026-01-17

### Decision
Use environment variables for development; HashiCorp Vault for production.

### Secret Categories

**Short-Lived** (API tokens, OAuth tokens)
- Stored encrypted in Vault
- Rotated automatically
- Never logged
- Example: Canva OAuth token, NotebookLM API key

**Long-Lived** (Database password, encryption key)
- Stored encrypted in Vault
- Rotated quarterly
- Accessible only by authentication
- Example: DB password, JWT secret

**Configuration** (Feature flags, API endpoints)
- Stored as environment variables
- Not secrets, but sensitive
- Example: SENTRY_DSN, LOG_LEVEL

### Implementation
```python
# Local development
# .env file (in .gitignore)
CANVA_CLIENT_ID=...
CANVA_CLIENT_SECRET=...

# Production
# HashiCorp Vault
vault kv get secret/canva/prod/client_id
```

### Consequences
✅ No secrets in git  
✅ Automatic rotation  
✅ Audit trail of secret access  
✅ Easy to use different secrets per environment  
❌ Vault adds operational overhead  
❌ Need to manage Vault access

---

## Summary of Key Decisions

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-001 | Adapter Pattern | Decoupling, testability, replaceability |
| ADR-002 | Redis Streams | MVP speed, local dev ease, scalability |
| ADR-003 | Exponential Backoff | Resilient to transient failures, prevents thundering herd |
| ADR-004 | Multi-Tenancy by Design | Future-proof, compliance-ready, quota enforcement |
| ADR-005 | Stateless Worker Pool | Elastic scaling, fault tolerance |
| ADR-006 | LLM as Decision Engine | Reliable orchestration + smart decisions |
| ADR-007 | Structured JSON Logging | Observability, searchability, compliance |
| ADR-008 | Distributed Tracing | Root-cause analysis, performance insights |
| ADR-009 | PostgreSQL + JSONB | Flexibility + relational integrity |
| ADR-010 | Observability First | Debuggability, compliance, capacity planning |
| ADR-011 | API-First Design | Multi-client support, consistency, testability |
| ADR-012 | Polling Default | MVP simplicity, fallback to webhooks |
| ADR-013 | Error Categorization | Deterministic handling, client awareness |
| ADR-014 | Multi-Mode Deployment | Dev flexibility, production scale |
| ADR-015 | Vault for Secrets | Security, rotation, audit trail |

---

## How to Update This Log

When making architectural decisions:

1. **Create new ADR** with: Status, Date, Decision, Context, Options, Consequences
2. **Link related ADRs** at the bottom
3. **Update summary table** above
4. **Notify team** of new decision
5. **Reference ADR in code comments** where relevant

Example:
```python
# See ADR-006: LLM used here for layout decisions, not orchestration
async def plan_layout(content: ContentBlock) -> LayoutDecision:
    ...
```

---

**Last Updated**: January 17, 2026  
**Total ADRs**: 15  
**Status**: All Decided (Ready for Implementation)

