# STEP 2: Target Architecture
## Canva-NotebookLM Integration Agent — Production-Grade Design

**Status**: Architecture Proposal | Ready for Review & Feedback  
**Date**: January 17, 2026  
**Scope**: Cloud-native, multi-tenant, semantic integration, hybrid orchestration  
**Assumes**: Full API access, adapter-based design, LLM + deterministic hybrid, long-running workflows

---

## 1. SYSTEM ARCHITECTURE OVERVIEW

### 1.1 High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                                       │
├─────────────────────────────────────────────────────────────────────────┤
│  Web UI (React/Vue)  │  REST API (OpenAPI)  │  CLI Tool  │  SDK/Library│
└──────────────────────┬──────────────────────┬───────────────────────────┘
                       │                      │
┌──────────────────────┴──────────────────────┴───────────────────────────┐
│                      API GATEWAY LAYER (FastAPI)                        │
├──────────────────────────────────────────────────────────────────────────┤
│  • Request validation & routing                                          │
│  • Authentication & authorization (RBAC, tenant isolation)              │
│  • Rate limiting & quota enforcement                                     │
│  • OpenAPI/Swagger documentation                                         │
│  • Request tracing & correlation IDs                                     │
└──────────┬──────────────────────────┬───────────────────┬───────────────┘
           │                          │                   │
┌──────────▼──────┐  ┌───────────────▼──────┐  ┌────────▼─────────┐
│  ORCHESTRATION  │  │   ADAPTERS & CLIENTS │  │   STATE & DATA   │
│  ENGINE         │  │                      │  │   LAYER          │
├─────────────────┤  ├──────────────────────┤  ├──────────────────┤
│                 │  │  • Canva Adapter     │  │ • PostgreSQL     │
│ • Workflow      │  │    - OAuth 2.0/PKCE  │  │ • Redis Cache    │
│   State Machine │  │    - Design APIs     │  │ • Tenant         │
│                 │  │    - Rate Limiter    │  │   Isolation      │
│ • Task Graph    │  │                      │  │ • Audit Logs     │
│   Execution     │  │  • NotebookLM Adapter│  │                  │
│                 │  │    - Service Acct    │  │ • Artifacts      │
│ • Decision      │  │    - Content APIs    │  │   Storage        │
│   Logic (LLM)   │  │    - Rate Limiter    │  │                  │
│                 │  │                      │  │ • Secrets Vault  │
│ • Error Handling│  │  • Rate Limit Mgmt   │  │                  │
│ • Retries       │  │  • Backpressure      │  └──────────────────┘
│                 │  │  • Circuit Breaker   │
│ • Event Emission│  │                      │
└────────┬────────┘  └──────────┬───────────┘
         │                      │
    ┌────▼──────────────────────▼────────┐
    │  ASYNC TASK QUEUE (Redis Streams)  │
    ├───────────────────────────────────┤
    │  • Priority queues                 │
    │  • Task state tracking             │
    │  • Worker distribution             │
    │  • Dead-letter queue               │
    └────┬──────────────────────────────┘
         │
    ┌────▼──────────────────────────────┐
    │  WORKER POOL (Async Task Handlers) │
    ├───────────────────────────────────┤
    │  • Transformation workers          │
    │  • Polling workers (webhooks alt)  │
    │  • Cleanup workers                 │
    │  • Metrics collectors              │
    └──────────────────────────────────┘
         │
┌────────▼──────────────────────────┐
│  OBSERVABILITY LAYER              │
├───────────────────────────────────┤
│  • Structured Logging (JSON/ELK)  │
│  • Distributed Tracing (Jaeger)   │
│  • Metrics (Prometheus)           │
│  • Alerting (AlertManager)        │
│  • Audit & Compliance             │
└───────────────────────────────────┘
         │
    ┌────▼─────────────────────────────────┐
    │  EXTERNAL SERVICES                   │
    ├──────────────────────────────────────┤
    │  • Canva API (Cloud)                 │
    │  • NotebookLM API (Cloud)            │
    │  • LLM Service (e.g., OpenAI, etc.)  │
    │  • SMTP (Notifications)              │
    └──────────────────────────────────────┘
```

---

## 2. DETAILED COMPONENT RESPONSIBILITIES

### 2.1 API Gateway Layer

**Purpose**: Single entry point for all client requests; enforces security, validation, and resource quotas.

**Responsibilities**:
- HTTP request routing to service endpoints
- Authentication (Bearer tokens, API keys, OAuth)
- Authorization (RBAC, tenant isolation, scope validation)
- Request validation (schema, size limits, format)
- Rate limiting (per-user, per-tenant, per-endpoint)
- Request correlation ID propagation
- Response formatting & error handling
- OpenAPI/Swagger documentation generation
- Middleware chain (logging, tracing, CORS, compression)

**Technology**:
- **Framework**: FastAPI + Starlette
- **Auth**: Custom RBAC middleware (built on auth layer ✅)
- **Rate Limiting**: SlowAPI or custom implementation
- **Validation**: Pydantic models
- **Documentation**: FastAPI's automatic OpenAPI generation

**Key Endpoints**:
```
POST   /api/v1/workflows          Create workflow
GET    /api/v1/workflows/{id}     Get workflow status
PUT    /api/v1/workflows/{id}     Update workflow (iterate/regenerate)
GET    /api/v1/workflows          List workflows (paginated)
DELETE /api/v1/workflows/{id}     Cancel/delete workflow

POST   /api/v1/designs            Create design request
GET    /api/v1/designs/{id}       Get design (with artifacts)
GET    /api/v1/designs            List user's designs

POST   /api/v1/sources            Register NotebookLM source
GET    /api/v1/sources/{id}       Get source analysis
GET    /api/v1/sources            List available sources

GET    /api/v1/health             System health
POST   /api/v1/admin/quotas       Update tenant quotas (admin)
GET    /api/v1/telemetry/metrics  Prometheus metrics (internal)
```

---

### 2.2 Orchestration Engine

**Purpose**: The "brain" of the system. Executes workflows, makes decisions, manages state, and coordinates external API calls.

**Core Responsibility**:
- Define and execute multi-step workflows (state machine)
- Manage task graphs and dependencies
- Apply decision logic (user intent + content → structured plan)
- Call adapters to execute API operations
- Handle retries, backoff, and partial failures
- Emit events for observability
- Persist state for recovery

**Internal Components**:

#### 2.2.1 Workflow State Machine

**State Diagram**:
```
[SUBMITTED]
    ↓
[QUEUED] 
    ↓
[ANALYZING_SOURCES]  ← Read NotebookLM content
    ↓
[GENERATING_LAYOUT]  ← LLM: Plan visual structure
    ↓
[CREATING_DESIGN]    ← Create Canva design
    ↓
[POPULATING_CONTENT] ← Insert content blocks
    ↓
[REFINING_VISUALS]   ← Apply branding, colors, fonts
    ↓
[GENERATING_ARTIFACTS] ← Export, optimize
    ↓
[COMPLETED] ✓

Failure paths → [FAILED] → [RETRY_BACKLOG] or [DEAD_LETTER]
User action  → [PAUSED], [CANCELLED]
```

**Transitions**:
- State changes are idempotent (can replay without side effects)
- All transitions are logged with timestamps & actor info
- Webhooks/events emitted on state change

#### 2.2.2 Task Graph Executor

**Definition**:
Workflows are composed of task graphs with explicit dependencies.

**Example**:
```yaml
workflow: "content_to_presentation"
tasks:
  - id: "analyze_content"
    operation: "notebooklm:analyze_source"
    inputs: { source_id: "src_123" }
    retry_config: { max_attempts: 3, backoff: "exponential" }
    depends_on: []
    
  - id: "plan_layout"
    operation: "orchestration:llm_decide_layout"
    inputs: { content_summary: "@analyze_content.output" }
    depends_on: ["analyze_content"]
    
  - id: "create_canva_design"
    operation: "canva:create_presentation"
    inputs: {
      template_id: "@plan_layout.template_choice",
      title: "@plan_layout.title"
    }
    depends_on: ["plan_layout"]
    
  - id: "populate_slides"
    operation: "canva:populate_slides"
    inputs: {
      design_id: "@create_canva_design.design_id",
      content_blocks: "@analyze_content.slide_blocks"
    }
    depends_on: ["create_canva_design", "analyze_content"]
    
  - id: "finalize"
    operation: "canva:finalize_design"
    inputs: { design_id: "@populate_slides.design_id" }
    depends_on: ["populate_slides"]
```

**Execution**:
- Topological sort to determine execution order
- Parallel execution where dependencies allow
- Input substitution (`@task.output` syntax)
- Output caching for repeated accesses
- Checkpoint state after each task completion

#### 2.2.3 Decision Engine (LLM Reasoning)

**Purpose**: Determine structured decisions based on content, user intent, and constraints.

**Responsibilities**:
- **Content Abstraction**: Parse NotebookLM output → structured knowledge graph
- **Layout Planning**: Given content, decide on visual hierarchy, template, flow
- **Branding Application**: Apply user/tenant brand guidelines
- **Refinement Suggestions**: Recommend improvements (colors, fonts, imagery)

**Operations**:
```python
# Pseudo-code
class DecisionEngine:
    async def plan_layout(
        self, 
        content_summary: ContentBlock,
        user_brand: BrandGuide,
        template_preferences: dict
    ) -> LayoutPlan:
        """
        Given content and constraints, decide:
        - Which template to use
        - Slide order and grouping
        - Typography and color scheme
        - Asset placement
        """
        
    async def suggest_refinements(
        self,
        current_design: Design,
        content: Content
    ) -> List[RefinementSuggestion]:
        """
        Analyze design-content fit and suggest:
        - Color/contrast improvements
        - Text readability issues
        - Missing visual hierarchy
        - Consistency violations
        """
```

**LLM Integration**:
- Use provider-agnostic LLM abstraction (OpenAI, Anthropic, or self-hosted)
- Prompts are version-controlled and tested
- Outputs parsed into typed structures
- Fallback to rule-based logic if LLM fails
- Cost & latency tracked per operation

**Decision Cache**:
- Cache layout plans for similar content to reduce LLM calls
- Embeddings-based similarity (for future ML optimization)

#### 2.2.4 Error Handling & Resilience

**Strategy**:
1. **Transient Errors** (network, timeout): Exponential backoff + circuit breaker
2. **Provider Quota Exceeded**: Backpressure, request budgeting, queue stall
3. **Validation Errors**: User feedback, allow correction
4. **System Errors**: Log, alert, escalate

**Implementation**:
```python
class ResilienceConfig:
    max_retries: int = 3
    backoff_multiplier: float = 2.0
    initial_backoff_ms: int = 100
    max_backoff_ms: int = 30000
    
    circuit_breaker_threshold: int = 5  # failures before open
    circuit_breaker_timeout_ms: int = 60000  # reset after 1 min
    
    timeout_ms: int = 30000  # per operation
    total_timeout_ms: int = 600000  # per workflow

class FailureMode:
    RETRY = "retry"
    SKIP = "skip"
    FAIL = "fail"
    ESCALATE = "escalate"
```

---

### 2.3 Adapter Layer

**Purpose**: Isolate external API interactions behind clean, replaceable interfaces.

**Pattern**: Provider Adapter + Retry/Rate Limit Middleware

#### 2.3.1 Canva Adapter

**Interface**:
```python
class CanvaAdapterInterface(ABC):
    """Provider-agnostic interface for Canva operations"""
    
    async def create_presentation(
        self,
        title: str,
        template_id: Optional[str] = None
    ) -> Design:
        """Create a new Canva design"""
        
    async def get_design(self, design_id: str) -> Design:
        """Fetch design metadata and content"""
        
    async def add_text_block(
        self,
        design_id: str,
        text: str,
        position: Position,
        style: TextStyle
    ) -> ContentElement:
        """Insert text element"""
        
    async def add_image(
        self,
        design_id: str,
        image_url: str,
        position: Position
    ) -> ContentElement:
        """Insert image element"""
        
    async def apply_template(
        self,
        design_id: str,
        template_id: str
    ) -> Design:
        """Apply design template"""
        
    async def export_design(
        self,
        design_id: str,
        format: ExportFormat  # PDF, PNG, PPTX, etc.
    ) -> bytes:
        """Export finalized design"""
        
    async def list_templates(self, design_type: str) -> List[Template]:
        """Fetch available templates"""
```

**Implementation** (`canva_adapter.py`):
```python
class CanvaAdapter(CanvaAdapterInterface):
    def __init__(
        self,
        client: CanvaAuthManager,
        rate_limiter: RateLimiter,
        circuit_breaker: CircuitBreaker,
        logger: Logger
    ):
        self.client = client
        self.rate_limiter = rate_limiter
        self.circuit_breaker = circuit_breaker
        self.logger = logger
    
    async def create_presentation(self, title: str, template_id: Optional[str] = None):
        """
        1. Check rate limit quota
        2. Call Canva API
        3. Handle errors with retry/fallback
        4. Log with tracing ID
        """
        async with self.circuit_breaker.call():
            await self.rate_limiter.acquire("canva.create_design")
            
            response = await self.client.post(
                "https://api.canva.com/v1/designs",
                json={"type": "presentation", "title": title, ...}
            )
            
            if response.status_code == 200:
                return Design.from_api(response.json())
            else:
                # Handle rate limits, auth errors, validation errors
                raise CanvaAPIError(response)
```

**Rate Limiting Middleware**:
- Per-operation quotas (e.g., 100 design creates/day per tenant)
- Burst allowance (e.g., 10/minute)
- Fair queuing across tenants
- Backpressure signaling to orchestrator

#### 2.3.2 NotebookLM Adapter

**Interface**:
```python
class NotebookLMAdapterInterface(ABC):
    """Provider-agnostic interface for NotebookLM operations"""
    
    async def create_notebook(self, source_id: str) -> Notebook:
        """Create a NotebookLM instance from source"""
        
    async def analyze_source(self, source_id: str) -> ContentAnalysis:
        """Trigger analysis and fetch structured output"""
        
    async def get_insights(self, notebook_id: str) -> List[Insight]:
        """Fetch generated insights"""
        
    async def get_outline(self, notebook_id: str) -> Outline:
        """Get hierarchical outline of content"""
        
    async def get_slides(self, notebook_id: str) -> List[SlideBlock]:
        """Get slide-ready content blocks"""
        
    async def get_references(self, notebook_id: str) -> List[Reference]:
        """Get cited references and metadata"""
        
    async def poll_status(self, notebook_id: str) -> AnalysisStatus:
        """Check analysis progress (for polling mode)"""
```

**Implementation**:
- Polling-based: Check status every 5-30 seconds until complete
- Webhook-based: Register callback URL; receive notifications asynchronously
- Hybrid: Start with polling; upgrade to webhook if supported

#### 2.3.3 LLM Adapter

**Interface**:
```python
class LLMAdapterInterface(ABC):
    """Provider-agnostic interface for LLM operations"""
    
    async def decide_layout(
        self,
        content: ContentBlock,
        constraints: LayoutConstraints
    ) -> LayoutDecision:
        """Decide visual layout structure"""
        
    async def suggest_refinements(
        self,
        design: Design,
        content: Content
    ) -> List[Suggestion]:
        """Suggest design improvements"""
        
    async def extract_key_points(
        self,
        text: str,
        max_points: int
    ) -> List[str]:
        """Summarize text to key points"""
```

**Implementations**:
- OpenAI GPT-4 (default, production)
- Anthropic Claude
- Self-hosted (LLaMA, Mistral)
- Fallback to rule-based if LLM unavailable

---

### 2.4 State & Data Layer

**Purpose**: Persistent, consistent storage of workflows, designs, and audit trails.

#### 2.4.1 Data Model (PostgreSQL)

```sql
-- Core workflow tables
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    tier VARCHAR,  -- "starter", "pro", "enterprise"
    quotas JSONB  -- rate limits per service
);

CREATE TABLE users (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR UNIQUE NOT NULL,
    display_name VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

CREATE TABLE workflows (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID NOT NULL REFERENCES users(id),
    
    title VARCHAR NOT NULL,
    description TEXT,
    
    workflow_type VARCHAR,  -- "content_to_presentation", etc.
    status VARCHAR,  -- "SUBMITTED", "QUEUED", "PROCESSING", "COMPLETED", "FAILED"
    current_task_id VARCHAR,
    
    input_config JSONB,  -- user parameters
    output_artifacts JSONB,  -- {design_id, export_urls, ...}
    
    error_log JSONB,  -- [{timestamp, task_id, error, recovery_action}]
    
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    parent_workflow_id UUID,  -- for iterations/regenerations
    
    INDEX (tenant_id, user_id, created_at DESC),
    INDEX (status, created_at DESC)
);

CREATE TABLE workflow_tasks (
    id UUID PRIMARY KEY,
    workflow_id UUID NOT NULL REFERENCES workflows(id),
    
    task_name VARCHAR NOT NULL,
    task_status VARCHAR,  -- "PENDING", "RUNNING", "COMPLETED", "FAILED"
    
    operation_type VARCHAR,  -- "notebooklm:analyze", "canva:create_design", ...
    input_data JSONB,
    output_data JSONB,
    error_message TEXT,
    
    retry_count INT DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INT,
    
    INDEX (workflow_id, task_name)
);

-- Design & Content tracking
CREATE TABLE designs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    workflow_id UUID REFERENCES workflows(id),
    
    canva_design_id VARCHAR UNIQUE NOT NULL,
    title VARCHAR,
    
    content_summary TEXT,
    design_metadata JSONB,  -- template, dimensions, colors, ...
    
    created_at TIMESTAMP DEFAULT NOW(),
    last_modified_at TIMESTAMP,
    exported_at TIMESTAMP,
    
    export_formats JSONB,  -- {pdf_url, png_url, pptx_url, ...}
    
    INDEX (tenant_id, created_at DESC),
    INDEX (canva_design_id)
);

-- Audit & Compliance
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),
    
    action VARCHAR NOT NULL,  -- "create_workflow", "export_design", "update_quota", ...
    resource_type VARCHAR,  -- "workflow", "design", "tenant", ...
    resource_id VARCHAR,
    
    previous_state JSONB,
    new_state JSONB,
    metadata JSONB,  -- request_id, ip_address, user_agent, ...
    
    timestamp TIMESTAMP DEFAULT NOW(),
    
    INDEX (tenant_id, timestamp DESC),
    INDEX (user_id, timestamp DESC)
);

-- Rate limit & quota tracking
CREATE TABLE quota_usage (
    id BIGSERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    
    service VARCHAR,  -- "canva", "notebooklm", "llm"
    metric VARCHAR,  -- "api_calls", "concurrent_workflows", "storage_gb"
    
    current_usage INT,
    limit_value INT,
    reset_at TIMESTAMP,  -- monthly, daily, etc.
    
    INDEX (tenant_id, service, metric)
);
```

**Design Decisions**:
- **UUID for IDs**: Universally unique, privacy-preserving
- **Partitioning by tenant_id**: Supports multi-tenancy at database level (future)
- **JSONB for semi-structured**: Flexible, queryable, future-proof
- **Audit logs**: Immutable, for compliance and debugging
- **Indexes**: Optimized for common queries (tenant/user/time lookups)

#### 2.4.2 Caching Layer (Redis)

```python
class RedisCache:
    """High-performance caching for frequently accessed data"""
    
    # Pattern: "cache:{entity_type}:{id}"
    workflows: Set[str]  # "cache:workflow:{id}" → serialized Workflow
    designs: Set[str]    # "cache:design:{id}" → serialized Design
    
    # Semantic cache (for LLM decisions)
    layout_plans: Set[str]  # "cache:layout_plan:{content_hash}" → LayoutPlan
    
    # Session management
    user_sessions: Set[str]  # "session:{token}" → {user_id, tenant_id, scopes, ...}
    
    # Rate limit state
    rate_limits: Set[str]  # "ratelimit:{tenant_id}:{service}:{metric}" → {count, reset_at}
```

**TTL Policies**:
- Session: 24 hours
- Workflow: Until completion + 7 days
- Rate limit: Per reset window (daily, monthly)
- Layout plan: 90 days

#### 2.4.3 Artifact Storage

**Responsibility**: Store generated files (PDFs, images, exports).

**Strategy**:
- **Local Development**: Filesystem (`/tmp/artifacts/`)
- **Production**: S3-compatible object storage (AWS S3, MinIO, etc.)
- **Lifecycle**: Auto-delete after retention period (configurable per tenant)

```python
class ArtifactStore:
    async def store_artifact(
        self,
        tenant_id: UUID,
        artifact_type: str,  # "design_pdf", "design_png", "thumbnail"
        content: bytes,
        metadata: dict
    ) -> ArtifactReference:
        """
        Store artifact and return downloadable URL
        Example: s3://tenant-123/workflows/wf-456/design.pdf
        """
        
    async def get_artifact_url(
        self,
        artifact_id: str,
        expires_in_hours: int = 24
    ) -> str:
        """
        Get signed, time-limited download URL
        """
```

#### 2.4.4 Secrets Management

**Responsibility**: Securely store API keys, OAuth tokens, encryption keys.

**Strategy**:
- **Local Development**: `.env` file (in .gitignore)
- **Production**: HashiCorp Vault, AWS Secrets Manager, or equivalent
- **Rotation**: Automatic token refresh; manual secret rotation

```python
class SecretsManager:
    async def store_user_token(
        self,
        tenant_id: UUID,
        user_id: UUID,
        service: str,  # "canva", "notebooklm"
        token_data: dict
    ) -> None:
        """
        Encrypt and store OAuth token securely
        Uses TokenManager ✅ (already implemented)
        """
```

---

### 2.5 Async Task Queue (Redis Streams)

**Purpose**: Decouple request submission from processing; enable horizontal scaling.

**Architecture**:

```python
class TaskQueue:
    """
    Use Redis Streams for distributed task processing
    Alternative: RabbitMQ (for very high throughput)
    """
    
    # Streams per priority
    streams = {
        "high": "tasks:high",    # SLA: process within 30s
        "normal": "tasks:normal",  # SLA: process within 5 min
        "low": "tasks:low"         # SLA: process within 1 hour
    }
    
    # Consumer groups for worker coordination
    consumer_groups = {
        "transformers": "tasks:consumers:transformers",
        "cleaners": "tasks:consumers:cleaners"
    }
    
    async def enqueue(
        self,
        task_type: str,
        priority: str,
        payload: dict,
        tenant_id: UUID,
        retry_count: int = 0
    ) -> str:
        """Add task to appropriate stream"""
        
    async def claim_and_process(
        self,
        consumer_group: str,
        timeout_ms: int = 60000
    ) -> Tuple[str, dict]:
        """
        Worker claims task and processes it
        Returns (task_id, payload)
        """
        
    async def acknowledge_task(self, task_id: str) -> None:
        """Mark task as completed; remove from pending"""
```

**Task Structure**:
```python
@dataclass
class Task:
    id: str
    type: str  # "transform_workflow", "poll_notebooklm", "export_design"
    priority: str  # "high", "normal", "low"
    tenant_id: UUID
    user_id: UUID
    workflow_id: UUID
    payload: dict
    created_at: datetime
    retry_count: int
    max_retries: int
    metadata: dict  # tracing_id, correlation_id, etc.
```

**Worker Pool**:
- **Transformer Workers** (8-32): Execute workflow tasks
- **Poller Workers** (2-4): Poll NotebookLM for completion
- **Cleanup Workers** (1-2): Expire old artifacts, compact logs
- **Metrics Workers** (1): Collect and push metrics

---

### 2.6 Observability Layer

**Principle**: Instrument from day 1; observability is not an afterthought.

#### 2.6.1 Structured Logging

```python
class StructuredLogger:
    """All logs are JSON with consistent schema"""
    
    async def log_workflow_start(self, workflow: Workflow):
        logger.info("workflow.started", extra={
            "workflow_id": workflow.id,
            "user_id": workflow.user_id,
            "tenant_id": workflow.tenant_id,
            "workflow_type": workflow.workflow_type,
            "request_id": context.request_id,  # correlation ID
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def log_api_call(self, service: str, operation: str, result: str, duration_ms: int):
        logger.info("api_call", extra={
            "service": service,  # "canva", "notebooklm"
            "operation": operation,
            "result": result,  # "success", "timeout", "rate_limited"
            "duration_ms": duration_ms,
            "request_id": context.request_id
        })
    
    async def log_error(self, error: Exception, context: dict):
        logger.error("workflow.error", extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            "workflow_id": context.get("workflow_id"),
            "task_id": context.get("task_id"),
            "request_id": context.request_id,
            "traceback": traceback.format_exc()
        })
```

**Logging Stack**:
- **Collection**: Python `logging` module (structured JSON)
- **Aggregation**: Fluentd or Logstash
- **Storage**: Elasticsearch
- **Visualization**: Kibana

#### 2.6.2 Distributed Tracing

```python
class TracingMiddleware:
    """
    Every request gets a unique trace ID.
    Trace spans for:
    - API request
    - Workflow execution
    - Adapter calls
    - Database queries
    """
    
    async def __call__(self, request: Request, call_next):
        # Generate/extract trace ID
        trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
        
        with tracer.start_as_current_span("api_request") as span:
            span.set_attribute("trace_id", trace_id)
            span.set_attribute("method", request.method)
            span.set_attribute("path", request.url.path)
            span.set_attribute("user_id", request.user.id if request.user else None)
            
            response = await call_next(request)
            
            span.set_attribute("status_code", response.status_code)
            response.headers["x-trace-id"] = trace_id
            
            return response
```

**Tracing Stack**:
- **Instrumentation**: OpenTelemetry (language-agnostic)
- **Export**: Jaeger collector
- **Storage**: Jaeger backend
- **Visualization**: Jaeger UI

#### 2.6.3 Metrics & Alerting

```python
# Prometheus metrics (standard)

# Workflow metrics
workflows_submitted_total = Counter(
    "workflows_submitted_total",
    "Total workflows submitted",
    ["tenant_id", "workflow_type"]
)
workflows_completed_total = Counter(
    "workflows_completed_total",
    "Total workflows completed",
    ["status"]  # "success", "failed"
)
workflow_duration_seconds = Histogram(
    "workflow_duration_seconds",
    "Time to complete workflow"
)

# API metrics
api_call_duration_seconds = Histogram(
    "api_call_duration_seconds",
    "Time for API call",
    ["service", "operation", "status"]  # "canva", "create_design", "success"
)
api_rate_limit_hits_total = Counter(
    "api_rate_limit_hits_total",
    "Rate limit hits per service",
    ["service", "tenant_id"]
)

# System metrics
queue_depth = Gauge(
    "task_queue_depth",
    "Number of pending tasks",
    ["priority"]
)
active_workers = Gauge(
    "active_workers",
    "Number of active workers",
    ["worker_type"]
)
```

**Alerting Rules** (AlertManager):
- Workflow error rate > 5% → Page on-call
- API latency p99 > 10s → Warning
- Queue depth > 10,000 → Page on-call
- Disk usage > 80% → Warning

#### 2.6.4 Audit & Compliance

```python
class AuditLogger:
    """Immutable audit trail for compliance & security"""
    
    async def log_action(
        self,
        action: str,
        resource_type: str,
        resource_id: str,
        actor: User,
        changes: dict
    ):
        # Always persisted to audit_logs table
        # Never deleted; only archived
        await db.audit_logs.insert({
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "actor_id": actor.id,
            "previous_state": previous_state,
            "new_state": new_state,
            "timestamp": datetime.utcnow(),
            "ip_address": context.remote_ip,
            "user_agent": context.user_agent
        })
```

---

## 3. DATA FLOW: END-TO-END WORKFLOW EXECUTION

### 3.1 Happy Path: User Submits Workflow

```
1. CLIENT (Web UI)
   └─→ POST /api/v1/workflows
       {
         "workflow_type": "content_to_presentation",
         "source_id": "notebooklm_src_123",
         "title": "Q4 2025 Marketing Strategy",
         "brand_id": "brand_acme"
       }

2. API GATEWAY
   └─→ Validate request
   └─→ Check auth (Bearer token)
   └─→ Extract tenant_id, user_id from token
   └─→ Generate correlation ID
   └─→ Forward to ORCHESTRATOR

3. ORCHESTRATION ENGINE
   └─→ Create Workflow record (status: SUBMITTED)
   └─→ Validate input (source exists, user has access)
   └─→ Enqueue task to Redis Stream (priority: normal)
   └─→ Return workflow_id to client
       { "workflow_id": "wf_abc123", "status": "QUEUED" }

4. CLIENT (Polling)
   └─→ GET /api/v1/workflows/wf_abc123 (every 2s)
       { "status": "QUEUED", "current_task": null }

5. TASK QUEUE (Redis Streams)
   └─→ Task sits in queue until WORKER claims it

6. WORKER (Transformer)
   └─→ Claim task from queue
   └─→ Update Workflow.status → PROCESSING
   └─→ Deserialize task → execute_workflow(wf_abc123)

7. WORKFLOW EXECUTION (State Machine)
   └─→ TASK 1: analyze_content
       ├─→ Adapter: NotebookLM.analyze_source(src_123)
       ├─→ Wait for analysis (polling)
       ├─→ Extract: insights, outline, slides, references
       └─→ Cache result; emit event "content_analyzed"
       
   └─→ TASK 2: plan_layout
       ├─→ LLM Adapter: decide_layout(content, brand_guidelines)
       ├─→ Decision: template="presentation_tech", colors=[blue, white], fonts=[Inter, Mono]
       └─→ Emit event "layout_planned"
       
   └─→ TASK 3: create_design
       ├─→ Canva Adapter: create_presentation(title, template)
       ├─→ Canva API returns design_id
       └─→ Store design record in DB
       
   └─→ TASK 4: populate_slides
       ├─→ For each content block in analysis:
       │   ├─→ Canva Adapter: add_text_block(design_id, text)
       │   ├─→ Canva Adapter: add_image(design_id, img_url)
       │   └─→ Apply typography & spacing
       └─→ Emit event "slides_populated"
       
   └─→ TASK 5: finalize
       ├─→ Canva Adapter: apply_brand_colors(design_id)
       ├─→ Canva Adapter: export_design(design_id, [pdf, png])
       └─→ Upload exports to S3; get signed URLs

8. WORKFLOW COMPLETION
   └─→ Workflow.status → COMPLETED
   └─→ Store output artifacts in workflow.output_artifacts
   └─→ Mark task as acknowledged in queue
   └─→ Emit event "workflow.completed"

9. CLIENT (Next poll)
   └─→ GET /api/v1/workflows/wf_abc123
       {
         "status": "COMPLETED",
         "current_task": null,
         "output_artifacts": {
           "design_id": "canva_123abc",
           "pdf_url": "https://s3.../designs/wf_abc123/export.pdf?token=...",
           "png_url": "https://s3.../designs/wf_abc123/export.png?token=...",
           "created_at": "2026-01-17T10:45:30Z"
         }
       }

10. CLIENT (Download)
    └─→ GET <pdf_url>
        └─→ Download PDF from S3
```

### 3.2 Error Path: Transient Failure → Retry

```
During TASK 2 (plan_layout):
   LLM API timeout

1. ERROR HANDLER detects timeout
   └─→ Check retry_count (0 < 3)
   └─→ Calculate backoff: 100ms * 2^0 = 100ms
   └─→ Enqueue retry task to queue with delay

2. TASK QUEUE
   └─→ Task sits for 100ms, then ready again

3. WORKER
   └─→ Claims task, retries TASK 2
   └─→ If succeeds: continue to TASK 3
   └─→ If fails again: backoff 200ms, retry_count=2
   
4. After max_retries exceeded:
   └─→ Workflow.status → FAILED
   └─→ Workflow.error_log: [
       { "task": "plan_layout", "error": "LLM timeout", "retry_count": 3 }
     ]
   └─→ Emit event "workflow.failed"
   └─→ Task moved to dead-letter queue for manual review
   └─→ Alert on-call (if error_rate > 5%)
```

### 3.3 User Iteration: Regenerate/Refine

```
User views design, wants changes:

POST /api/v1/workflows/wf_abc123/regenerate
{
  "scope": "layout_only",  # Don't re-analyze, just replan
  "overrides": {
    "color_scheme": "dark_mode",
    "template": "minimalist"
  }
}

Orchestrator:
1. Create child workflow (parent_id = wf_abc123)
2. Skip tasks 1 & 2, start at task 3 (create_design with new template)
3. Execute 3, 4, 5
4. Return new artifacts
5. Link old & new workflows for audit trail
```

---

## 4. MULTI-TENANCY & SECURITY

### 4.1 Tenant Isolation Strategy

**Data Isolation**:
- All tables have `tenant_id` FK
- Query filters always include `WHERE tenant_id = ?`
- No cross-tenant data queries possible

**Credential Isolation**:
- Each tenant's Canva OAuth tokens stored separately in Secrets Vault
- Tenant-scoped encryption keys
- No tenant can access another's tokens

**Rate Limiting**:
- Per-tenant quotas (e.g., 10,000 designs/month)
- Per-tenant concurrent request limit (e.g., 100)
- Fair resource sharing across tenants

**Audit Trail**:
- Every action logged with tenant_id + user_id
- Separate audit log view per tenant

### 4.2 Authentication & Authorization

**Authentication**:
- API key (long-lived, for CLI/automation)
- OAuth 2.0 token (for web UI, short-lived)
- Both validated against user's tenant

**Authorization** (RBAC):
```python
class Role(Enum):
    ADMIN = "admin"        # All actions, tenant management
    EDITOR = "editor"      # Create, edit workflows
    VIEWER = "viewer"      # Read-only access

class Permission(Enum):
    WORKFLOW_CREATE = "workflow:create"
    WORKFLOW_READ = "workflow:read"
    WORKFLOW_DELETE = "workflow:delete"
    QUOTA_MANAGE = "quota:manage"  # admin only

# Middleware enforces scopes
@require_permission("workflow:create")
async def submit_workflow(...): ...
```

**Scope Enforcement**:
- API Gateway validates Bearer token scopes
- Rate limiter per user + service
- Blocked at API layer; never reaches orchestrator

---

## 5. SCALABILITY & PERFORMANCE

### 5.1 Horizontal Scaling

```
┌─────────────────────────────────────────────────────────┐
│  Load Balancer (HAProxy, AWS ALB)                       │
└────┬──────────────────────────────────────────────────┬─┘
     │                                                  │
┌────▼──────────┐  ┌────────────────┐  ┌─────────────▼──┐
│ API Gateway 1 │  │ API Gateway 2   │  │ API Gateway 3  │
│ (FastAPI)     │  │ (FastAPI)       │  │ (FastAPI)      │
└────┬──────────┘  └────────┬───────┘  └────────┬───────┘
     │                      │                   │
     └──────────────────────┼───────────────────┘
                            │
     ┌──────────────────────▼───────────────────┐
     │  Redis Streams (Task Queue)              │
     │  • Shared state                          │
     │  • Task distribution                     │
     │  • Consumer group coordination           │
     └──────────┬──────────────────────────────┘
                │
    ┌───────────┼───────────┬───────────┐
    │           │           │           │
┌───▼──┐  ┌────▼───┐  ┌───▼────┐  ┌──▼────┐
│ W1   │  │  W2    │  │  W3    │  │ W4    │
│      │  │        │  │        │  │       │
│      │  │        │  │        │  │       │
└──┬───┘  └──┬─────┘  └───┬────┘  └──┬────┘
   │         │            │          │
   └─────────┼────────────┼──────────┘
             │            │
     ┌───────▼────────────▼──────┐
     │  PostgreSQL (Primary)      │
     │  • Workflow state          │
     │  • Audit logs              │
     │  • Design metadata         │
     │  • Query replication       │
     └────────────────────────────┘
         │
         ├─────────────────────────┐
         │  PostgreSQL (Read Replica)
         │  • Status checks
         │  • Analytics
```

**Scaling Strategy**:
- **API Gateway**: Stateless, horizontal scaling automatic
- **Workers**: Add/remove based on queue depth
- **Database**: Read replicas for queries; write to primary
- **Cache**: Redis cluster mode for HA

### 5.2 Performance Targets

| Operation | Latency | Throughput |
|-----------|---------|------------|
| Submit workflow | <100ms | 1000/sec |
| Check status | <50ms | 10000/sec |
| Analyze content (NotebookLM) | 5-30s | 10 concurrent |
| Create design (Canva) | 2-5s | 50 concurrent |
| Export design | 1-3s | 100 concurrent |
| Full workflow (e2e) | 30-120s | 50 concurrent |

**Optimization Tactics**:
- Request batching (where APIs allow)
- Response caching (Redis)
- Parallel task execution (topological sort)
- Connection pooling (HTTP, DB)
- Compression (gzip for large responses)

---

## 6. TECHNOLOGY STACK SUMMARY

| Layer | Component | Justification |
|-------|-----------|---------------|
| **API** | FastAPI | Async-native, automatic OpenAPI, type-safe |
| **Async Runtime** | asyncio + uvicorn | Standard Python, proven at scale |
| **Task Queue** | Redis Streams | Simpler than RabbitMQ for MVP; upgrade path to RabbitMQ if needed |
| **Database** | PostgreSQL | ACID, JSONB, array types, proven reliability |
| **Cache** | Redis | In-memory speed, distributed locking, sessions |
| **Secrets** | Vault or .env | Local dev with .env; production Vault |
| **Logging** | JSON + Fluentd → Elasticsearch | Structured, queryable, scalable |
| **Tracing** | OpenTelemetry + Jaeger | Language-agnostic, CNCF-standard |
| **Metrics** | Prometheus | De-facto standard, mature ecosystem |
| **Alerting** | AlertManager | Prometheus-native, rule-based |
| **Containerization** | Docker | Standard, widely supported |
| **Orchestration** | Kubernetes (future) | Pod auto-scaling, declarative |
| **LLM** | OpenAI API (default) | Latest models, reliable, fallback to self-hosted |
| **Object Storage** | S3-compatible | AWS, MinIO, etc.; portable |

---

## 7. DEPLOYMENT ARCHITECTURE

### 7.1 Development Environment

```
Local machine:
- Python 3.8+ venv
- PostgreSQL (local or Docker)
- Redis (Docker)
- .env file with test credentials
```

### 7.2 Staging / Production Environment

```
Kubernetes cluster (3+ nodes):

Namespace: canva-notebooklm-prod
├── Deployment: api-gateway (3 replicas)
├── Deployment: workers (10-50 replicas, HPA)
├── StatefulSet: redis (3 replicas, sentinel)
├── StatefulSet: postgres (primary + 2 replicas)
├── Service: api (ClusterIP, LoadBalancer for ingress)
├── Ingress: HTTPS, TLS termination
├── ConfigMap: application config
├── Secret: API keys, DB passwords
├── PVC: Persistent storage (logs, artifacts)
```

### 7.3 CI/CD Pipeline

```
On every git push:
1. Lint (pylint, flake8)
2. Type check (mypy)
3. Unit tests (pytest, 80%+ coverage)
4. Security scan (bandit)
5. Build Docker image
6. Push to registry
7. Deploy to staging (automated)
8. Run integration tests
9. Manual approval → Deploy to production
```

---

## 8. SUMMARY: ARCHITECTURE DECISIONS

| Decision | Rationale |
|----------|-----------|
| **Adapter Pattern** | Isolate provider APIs; enable replaceable implementations |
| **Event-Driven** | Decouple components; enable observability hooks |
| **State Machine** | Explicit state transitions; easier to test, debug, monitor |
| **Multi-tenant by design** | Not bolted on later; isolate data & quotas from start |
| **Async/await** | Python native; efficient for I/O-heavy operations |
| **Redis Streams** | Simpler than RabbitMQ for MVP; good throughput; competitive advantage |
| **Structured logging** | Debug production issues without SSH; compliance audit trail |
| **LLM hybrid approach** | Deterministic orchestration for reliability; LLM for reasoning |
| **Horizontal scaling** | Support burst traffic; cost-efficient during low traffic |

---

## NEXT STEPS: Step 3 Development Plan

Once you approve this architecture, we will:

1. **Refine data model** (any adjustments based on feedback?)
2. **Design API contracts** (request/response schemas)
3. **Create Step 3: Development Plan** (phases, deliverables, tasks)
4. **Begin Phase 1: Project Scaffolding** (folder structure, configs, base classes)

**Questions for you**:

1. Does this architecture align with your vision?
2. Any specific concerns (scalability, cost, complexity)?
3. Should we add/remove components (e.g., message queue vs streams)?
4. Timeline constraints? (When do you need initial working version?)
5. Team size? (Who will implement what?)

