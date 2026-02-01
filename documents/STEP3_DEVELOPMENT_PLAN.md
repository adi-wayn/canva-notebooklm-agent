# STEP 3: Development Plan
## Canva-NotebookLM Integration Agent — Phase-Based Roadmap

**Status**: Ready for Implementation  
**Total Estimated Duration**: 12-16 weeks (with focused team)  
**Approach**: Incremental phases, working vertical slices, continuous integration

---

## PHASE OVERVIEW

```
PHASE 0: Preparation & Setup (Week 1)
├─ Confirm API access
├─ Project scaffolding
├─ Configuration management
└─ Development environment setup

PHASE 1: Core Infrastructure (Weeks 2-3)
├─ Database schema & migrations
├─ Redis setup & caching layer
├─ Configuration management
└─ Logging & observability infrastructure

PHASE 2: Adapter Implementation (Weeks 4-5)
├─ Canva API Client (create_design, add_content, export)
├─ NotebookLM API Client (analyze, poll, fetch insights)
├─ LLM Adapter (layout decisions, refinements)
├─ Rate limiting & backpressure
└─ Error handling & resilience

PHASE 3: Orchestration Engine (Weeks 6-8)
├─ Workflow state machine
├─ Task graph executor
├─ Decision engine integration
├─ Event system
└─ Error recovery

PHASE 4: API & Task Queue (Weeks 9-10)
├─ REST API endpoints (full surface)
├─ OpenAPI/Swagger documentation
├─ Redis Streams task queue
├─ Worker implementation
└─ Request/response persistence

PHASE 5: Testing & Reliability (Weeks 11-12)
├─ Unit tests (80%+ coverage)
├─ Integration tests (e2e workflows)
├─ Performance testing & optimization
├─ Chaos engineering (failure scenarios)
└─ Security audit

PHASE 6: Observability & Monitoring (Weeks 13-14)
├─ Structured logging (ELK stack)
├─ Distributed tracing (Jaeger)
├─ Metrics & dashboards (Prometheus/Grafana)
├─ Alerting rules
└─ Runbooks

PHASE 7: Deployment & Polish (Weeks 15-16)
├─ Docker containerization
├─ Kubernetes manifests
├─ CI/CD pipeline
├─ Production hardening
└─ Documentation & knowledge transfer
```

---

## DETAILED PHASES

---

## PHASE 0: Preparation & Setup
**Duration**: 1 week | **Effort**: 40 hours  
**Goal**: Validate environment, confirm API access, establish development workflow

### Tasks

#### T0.1: API Credential Validation
**Owner**: Project Lead / DevOps  
**Effort**: 8 hours

**Acceptance Criteria**:
- [ ] Canva OAuth 2.0 credentials configured and tested
- [ ] NotebookLM service account credentials configured and tested
- [ ] LLM API (OpenAI or alternative) credentials configured
- [ ] All external API endpoints are reachable and responding
- [ ] Rate limits and quotas are documented
- [ ] Credentials stored in `.env.example` (no secrets committed)

**Deliverables**:
- `.env.example` template
- `docs/API_CREDENTIALS.md` with setup instructions
- Validation script: `scripts/validate_credentials.py`

**Definition of Done**:
```bash
$ python scripts/validate_credentials.py
✓ Canva API: AUTHENTICATED (remaining quota: 10000/10000)
✓ NotebookLM API: AUTHENTICATED
✓ OpenAI API: AUTHENTICATED
✓ All systems operational
```

---

#### T0.2: Project Scaffolding
**Owner**: Tech Lead  
**Effort**: 12 hours

**Folder Structure** (target):
```
canva-notebooklm-agent/
├── src/
│   ├── __init__.py
│   ├── config.py                    # Centralized config (NEW)
│   ├── main.py                      # FastAPI app entry (REFACTOR)
│   ├── requirements.txt              # Dependencies
│   │
│   ├── auth/                         # ✅ Existing
│   │   ├── __init__.py
│   │   ├── canva_auth_manager.py
│   │   ├── notebooklm_auth_manager.py
│   │   ├── token_manager.py
│   │   └── auth_middleware.py
│   │
│   ├── adapters/                     # NEW
│   │   ├── __init__.py
│   │   ├── base_adapter.py           # Abstract base
│   │   ├── canva_adapter.py          # Canva API client
│   │   ├── notebooklm_adapter.py     # NotebookLM API client
│   │   └── llm_adapter.py            # LLM reasoning
│   │
│   ├── orchestration/                # NEW
│   │   ├── __init__.py
│   │   ├── workflow_engine.py        # State machine
│   │   ├── task_executor.py          # Task graph execution
│   │   ├── decision_engine.py        # LLM-based decisions
│   │   └── events.py                 # Event definitions
│   │
│   ├── storage/                      # NEW
│   │   ├── __init__.py
│   │   ├── database.py               # SQLAlchemy setup
│   │   ├── models.py                 # ORM models
│   │   ├── migrations/               # Alembic migrations
│   │   ├── repository.py             # Data access layer
│   │   ├── cache.py                  # Redis wrapper
│   │   └── artifact_store.py         # File storage
│   │
│   ├── queue/                        # NEW
│   │   ├── __init__.py
│   │   ├── redis_queue.py            # Task queue (Redis Streams)
│   │   ├── worker.py                 # Worker implementation
│   │   └── tasks.py                  # Task definitions
│   │
│   ├── api/                          # NEW
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── workflows.py          # /workflows endpoints
│   │   │   ├── designs.py            # /designs endpoints
│   │   │   ├── sources.py            # /sources endpoints
│   │   │   └── health.py             # /health endpoints
│   │   ├── schemas.py                # Pydantic models
│   │   └── dependencies.py           # FastAPI dependencies
│   │
│   ├── observability/                # NEW
│   │   ├── __init__.py
│   │   ├── logging.py                # Structured logging
│   │   ├── tracing.py                # Distributed tracing
│   │   ├── metrics.py                # Prometheus metrics
│   │   └── audit.py                  # Audit logging
│   │
│   └── utils/                        # NEW
│       ├── __init__.py
│       ├── errors.py                 # Custom exceptions
│       ├── decorators.py             # Retry, circuit breaker
│       ├── serialization.py          # JSON encoding
│       └── validation.py             # Input validation
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                   # Pytest fixtures (NEW)
│   ├── test_authentication.py        # ✅ Existing
│   ├── unit/                         # NEW
│   │   ├── __init__.py
│   │   ├── test_adapters.py
│   │   ├── test_orchestration.py
│   │   ├── test_storage.py
│   │   └── test_queue.py
│   ├── integration/                  # NEW
│   │   ├── __init__.py
│   │   ├── test_workflow_e2e.py
│   │   ├── test_api_integration.py
│   │   └── test_external_apis.py
│   └── fixtures/                     # NEW
│       ├── __init__.py
│       ├── mock_canva.py
│       ├── mock_notebooklm.py
│       └── factories.py
│
├── docs/                             # NEW
│   ├── API.md                        # API reference
│   ├── ARCHITECTURE.md               # (references STEP2_ARCHITECTURE.md)
│   ├── SETUP.md                      # Setup & configuration
│   ├── DEPLOYMENT.md                 # Deployment guide
│   └── TROUBLESHOOTING.md            # Common issues
│
├── scripts/                          # NEW
│   ├── validate_credentials.py
│   ├── setup_db.py
│   ├── seed_data.py
│   └── performance_test.py
│
├── docker/                           # NEW
│   ├── Dockerfile
│   ├── Dockerfile.worker
│   └── docker-compose.yml
│
├── k8s/                              # NEW
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── postgres.yaml
│   ├── redis.yaml
│   ├── api.yaml
│   ├── workers.yaml
│   └── ingress.yaml
│
├── .github/workflows/                # NEW
│   ├── tests.yml                     # Run tests on push
│   ├── lint.yml                      # Linting on push
│   └── deploy.yml                    # Deploy on merge to main
│
├── .env.example                      # NEW
├── .gitignore                        # Updated
├── pyproject.toml                    # NEW (Poetry or similar)
├── requirements.txt                  # Updated
├── setup.py                          # Updated
├── pytest.ini                        # NEW
├── Makefile                          # NEW (dev commands)
│
├── STEP1_ANALYSIS.md                 # ✅ Existing
├── STEP2_ARCHITECTURE.md             # ✅ Existing
├── STEP3_DEVELOPMENT_PLAN.md         # This file
└── README.md                         # Updated
```

**Acceptance Criteria**:
- [ ] All folders created with `__init__.py`
- [ ] `.gitignore` updated to exclude `.env`, `__pycache__`, `.venv`, etc.
- [ ] `pyproject.toml` or `setup.py` configured
- [ ] README.md has quick start instructions
- [ ] Makefile has common commands (`make test`, `make lint`, `make run`)

**Deliverables**:
- Folder structure (as above)
- `Makefile` with standard targets
- Updated `.gitignore`
- Updated `README.md`

---

#### T0.3: Configuration Management
**Owner**: DevOps / Tech Lead  
**Effort**: 8 hours

**Implementation**:

```python
# src/config.py
from pydantic import BaseSettings, Field
import os

class Settings(BaseSettings):
    # API Configuration
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_WORKERS: int = Field(default=4)
    ENVIRONMENT: str = Field(default="development")  # dev, staging, prod
    
    # Database
    DATABASE_URL: str = Field(default="postgresql://user:password@localhost/db")
    DATABASE_POOL_SIZE: int = Field(default=10)
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # External APIs
    CANVA_CLIENT_ID: str = Field(default="")
    CANVA_CLIENT_SECRET: str = Field(default="")
    CANVA_API_BASE_URL: str = Field(default="https://api.canva.com/v1")
    CANVA_RATE_LIMIT: int = Field(default=100)  # requests/minute
    
    NOTEBOOKLM_API_KEY: str = Field(default="")
    NOTEBOOKLM_API_BASE_URL: str = Field(default="https://api.notebooklm.com/v1")
    NOTEBOOKLM_RATE_LIMIT: int = Field(default=50)
    
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = Field(default="gpt-4")
    
    # Secrets
    JWT_SECRET: str = Field(default="secret-change-in-prod")
    ENCRYPTION_KEY: str = Field(default="")  # from encryption_key.key file
    
    # Observability
    LOG_LEVEL: str = Field(default="INFO")
    SENTRY_DSN: str = Field(default="")  # Error tracking
    
    # Features
    ENABLE_TRACING: bool = Field(default=False)
    ENABLE_METRICS: bool = Field(default=False)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

settings = Settings()
```

**Acceptance Criteria**:
- [ ] `.env.example` created with all required variables
- [ ] `config.py` loads from environment
- [ ] Configuration validation on startup
- [ ] No hardcoded secrets in code
- [ ] Environment-specific configs (dev/staging/prod)

**Deliverables**:
- `src/config.py`
- `.env.example`
- Validation test: `test_config_loading()`

---

#### T0.4: Development Environment Setup
**Owner**: Team / Individual  
**Effort**: 12 hours

**Steps**:

```bash
# 1. Clone repo & set up venv
git clone <repo>
cd canva-notebooklm-agent
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # pytest, black, mypy, etc.

# 3. Set up .env
cp .env.example .env
# Edit .env with your local credentials

# 4. Start PostgreSQL & Redis (Docker)
docker-compose -f docker/docker-compose.yml up -d postgres redis

# 5. Initialize database
python scripts/setup_db.py

# 6. Run tests to confirm setup
make test

# 7. Start dev server
make run

# Visit http://localhost:8000/docs for Swagger UI
```

**Acceptance Criteria**:
- [ ] Python venv created and activated
- [ ] All dependencies installed (`pip list` shows all packages)
- [ ] PostgreSQL and Redis running (local Docker)
- [ ] Database initialized with schema
- [ ] Server starts without errors
- [ ] Swagger UI accessible at `/docs`
- [ ] Health check passes: `curl http://localhost:8000/health`

**Deliverables**:
- `Makefile` with `make setup`, `make run`, `make test`
- `docker/docker-compose.yml` with postgres, redis
- `docs/SETUP.md` with step-by-step instructions
- Validation checklist

---

### Phase 0 Summary

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| T0.1: API Credentials | Project Lead | 8h | Not Started |
| T0.2: Project Scaffolding | Tech Lead | 12h | Not Started |
| T0.3: Configuration | DevOps | 8h | Not Started |
| T0.4: Dev Environment | Team | 12h | Not Started |
| **Phase 0 Total** | | **40h** | **Not Started** |

**Definition of Done**:
- [ ] All 4 tasks completed and verified
- [ ] Team can run project locally
- [ ] External APIs validated and accessible
- [ ] No hardcoded secrets in repo
- [ ] CI/CD pipeline configured (even if minimal)

---

## PHASE 1: Core Infrastructure
**Duration**: 2 weeks | **Effort**: 80 hours  
**Goal**: Database, caching, configuration, observability foundation ready for development

### Tasks

#### T1.1: Database Schema & Migrations
**Owner**: Database Engineer / Tech Lead  
**Effort**: 24 hours

**Implementation**:
- Create `src/storage/models.py` with SQLAlchemy ORM models (as detailed in STEP2)
- Use Alembic for migrations
- Create `src/storage/migrations/versions/` directory

**Key Models**:
- `Tenant`, `User`, `Workflow`, `WorkflowTask`
- `Design`, `AuditLog`, `QuotaUsage`
- Foreign key relationships and indexes

**Migration Files**:
```
migrations/versions/
├── 001_create_initial_schema.py
├── 002_add_audit_tables.py
└── 003_add_quota_tracking.py
```

**Acceptance Criteria**:
- [ ] All tables created as per STEP2 schema
- [ ] Indexes on commonly queried columns
- [ ] Foreign keys with proper constraints
- [ ] Migration rollback tested
- [ ] Schema diagram documented
- [ ] Data retention policies defined

**Deliverables**:
- `src/storage/models.py` (SQLAlchemy ORM)
- `src/storage/migrations/` (Alembic)
- `docs/DATABASE_SCHEMA.md` (ER diagram, table descriptions)
- `scripts/setup_db.py` (initialization script)

---

#### T1.2: Redis Caching & Session Management
**Owner**: Backend Engineer  
**Effort**: 16 hours

**Implementation**:
```python
# src/storage/cache.py
class RedisCache:
    async def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None: ...
    async def get(self, key: str) -> Any: ...
    async def delete(self, key: str) -> None: ...
    async def exists(self, key: str) -> bool: ...
    
    # Session management
    async def create_session(self, token: str, user_id: UUID, ttl_seconds: int = 86400) -> None: ...
    async def get_session(self, token: str) -> dict: ...
    async def invalidate_session(self, token: str) -> None: ...
    
    # Rate limiting
    async def check_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool: ...
```

**Acceptance Criteria**:
- [ ] Connection pooling configured
- [ ] TTL policies per entity type
- [ ] Session management working
- [ ] Rate limit counters working
- [ ] Redis persistence enabled
- [ ] Failover strategy documented

**Deliverables**:
- `src/storage/cache.py`
- Tests for cache operations
- Configuration for Redis cluster (future)

---

#### T1.3: Observability Infrastructure
**Owner**: DevOps / Observability Engineer  
**Effort**: 24 hours

**Sub-tasks**:

**1.3a: Structured Logging**
```python
# src/observability/logging.py
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add extra fields (request_id, user_id, etc.)
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        return json.dumps(log_data)

# Usage
logger = logging.getLogger(__name__)
logger.info("workflow.started", extra={
    "workflow_id": "wf_123",
    "user_id": "user_456"
})
```

**1.3b: Distributed Tracing**
```python
# src/observability/tracing.py
from opentelemetry import trace, metrics
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider

jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831
)
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(...)

tracer = trace.get_tracer(__name__)

@app.middleware("http")
async def tracing_middleware(request, call_next):
    with tracer.start_as_current_span("http_request") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", str(request.url))
        response = await call_next(request)
        span.set_attribute("http.status_code", response.status_code)
        return response
```

**1.3c: Metrics & Alerting**
```python
# src/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge

workflows_submitted = Counter(
    "workflows_submitted_total",
    "Total workflows submitted",
    ["tenant_id", "workflow_type"]
)

workflow_duration = Histogram(
    "workflow_duration_seconds",
    "Workflow execution time",
    buckets=[10, 30, 60, 120, 300, 600]
)

api_requests = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "path", "status"]
)
```

**Acceptance Criteria**:
- [ ] JSON logging configured (no human-readable strings)
- [ ] Trace ID propagation working
- [ ] Jaeger backend running and receiving traces
- [ ] Prometheus metrics endpoint at `/metrics`
- [ ] Key metrics defined (workflows, API calls, errors)
- [ ] Alerts configured (error rate, latency, queue depth)

**Deliverables**:
- `src/observability/logging.py`
- `src/observability/tracing.py`
- `src/observability/metrics.py`
- `docker/docker-compose.yml` updated with ELK stack, Jaeger, Prometheus
- `k8s/prometheus.yaml`, `k8s/grafana.yaml` (future)

---

#### T1.4: Error Handling & Resilience Framework
**Owner**: Backend Engineer  
**Effort**: 16 hours

**Implementation**:
```python
# src/utils/errors.py
class CanvaAPIError(Exception): pass
class NotebookLMAPIError(Exception): pass
class WorkflowExecutionError(Exception): pass
class RateLimitError(Exception): pass
class ValidationError(Exception): pass

# src/utils/decorators.py
def retry_on_transient(max_attempts=3, backoff_multiplier=2, initial_backoff_ms=100):
    """Decorator for retry logic with exponential backoff"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (asyncio.TimeoutError, ConnectionError) as e:
                    if attempt == max_attempts - 1:
                        raise
                    backoff_ms = initial_backoff_ms * (backoff_multiplier ** attempt)
                    await asyncio.sleep(backoff_ms / 1000)
        return wrapper
    return decorator

def circuit_breaker(failure_threshold=5, recovery_timeout_ms=60000):
    """Decorator for circuit breaker pattern"""
    # Implementation: track failures, open circuit on threshold, reset after timeout
    pass
```

**Acceptance Criteria**:
- [ ] Custom exception hierarchy defined
- [ ] Retry decorator working with exponential backoff
- [ ] Circuit breaker pattern implemented
- [ ] Timeout handling for all async operations
- [ ] Graceful degradation strategy documented
- [ ] Error messages user-friendly (no stack traces)

**Deliverables**:
- `src/utils/errors.py`
- `src/utils/decorators.py`
- Tests for retry logic, circuit breaker
- Error handling documentation

---

### Phase 1 Summary

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| T1.1: Database & Migrations | DBA | 24h | Not Started |
| T1.2: Caching | Backend | 16h | Not Started |
| T1.3: Observability | DevOps | 24h | Not Started |
| T1.4: Error Handling | Backend | 16h | Not Started |
| **Phase 1 Total** | | **80h** | **Not Started** |

**Definition of Done**:
- [ ] All 4 tasks completed and verified
- [ ] Database running with schema
- [ ] Redis running and connected
- [ ] Logging to JSON format
- [ ] Tracing integration working
- [ ] Metrics endpoint accessible
- [ ] All infrastructure tests passing
- [ ] Ready for adapter development (Phase 2)

---

## PHASE 2: Adapter Implementation
**Duration**: 2 weeks | **Effort**: 100 hours  
**Goal**: Functional adapters for Canva, NotebookLM, and LLM with full error handling and rate limiting

### Tasks

#### T2.1: Canva API Client & Adapter
**Owner**: Backend Engineer (API Integration Specialist)  
**Effort**: 40 hours

**Overview**:
- Implement full Canva adapter behind interface
- Handle OAuth token refresh
- Implement rate limiting & backpressure
- Add error handling & retries
- Mock for testing

**Key Methods**:
```python
class CanvaAdapterInterface(ABC):
    async def create_presentation(self, title: str, template_id: Optional[str] = None) -> Design: ...
    async def get_design(self, design_id: str) -> Design: ...
    async def add_text_block(self, design_id: str, text: str, ...) -> ContentElement: ...
    async def add_image(self, design_id: str, image_url: str, ...) -> ContentElement: ...
    async def apply_template(self, design_id: str, template_id: str) -> Design: ...
    async def export_design(self, design_id: str, format: ExportFormat) -> bytes: ...
    async def list_templates(self, design_type: str) -> List[Template]: ...
```

**Implementation Path**:
1. Define interface (abstract class)
2. Implement HTTP client (httpx with connection pooling)
3. Add OAuth token refresh logic
4. Implement rate limiter middleware
5. Add circuit breaker for fault tolerance
6. Create mock implementation for testing
7. Add comprehensive tests

**Acceptance Criteria**:
- [ ] All interface methods implemented
- [ ] Rate limiting enforced
- [ ] Token refresh working
- [ ] Errors mapped to custom exceptions
- [ ] Retries on transient failures
- [ ] Mock adapter works for testing
- [ ] Integration tests with real API (optional, gated)
- [ ] Performance: 95% calls complete <2s

**Deliverables**:
- `src/adapters/canva_adapter.py`
- `tests/unit/test_canva_adapter.py`
- `tests/fixtures/mock_canva.py`
- Integration test (if real API available)

---

#### T2.2: NotebookLM API Client & Adapter
**Owner**: Backend Engineer (API Integration Specialist)  
**Effort**: 35 hours

**Overview**:
- Implement NotebookLM adapter (service account auth)
- Handle both polling and webhook modes
- Fetch structured outputs (insights, outlines, slides)
- Rate limiting & quota management
- Error handling & timeouts

**Key Methods**:
```python
class NotebookLMAdapterInterface(ABC):
    async def create_notebook(self, source_id: str) -> Notebook: ...
    async def analyze_source(self, source_id: str) -> ContentAnalysis: ...
    async def get_insights(self, notebook_id: str) -> List[Insight]: ...
    async def get_outline(self, notebook_id: str) -> Outline: ...
    async def get_slides(self, notebook_id: str) -> List[SlideBlock]: ...
    async def poll_status(self, notebook_id: str) -> AnalysisStatus: ...
```

**Polling Strategy**:
```python
async def poll_until_complete(notebook_id: str, timeout_seconds: int = 600):
    start_time = time.time()
    while time.time() - start_time < timeout_seconds:
        status = await self.poll_status(notebook_id)
        if status.is_complete:
            return status
        await asyncio.sleep(5)  # poll every 5 seconds
    raise TimeoutError(f"Analysis timeout for {notebook_id}")
```

**Acceptance Criteria**:
- [ ] All interface methods implemented
- [ ] Polling loop working with configurable interval
- [ ] Webhook support (if available)
- [ ] Timeout handling
- [ ] Rate limit enforcement
- [ ] Mock adapter for testing
- [ ] Structured output parsing
- [ ] Error messages user-friendly

**Deliverables**:
- `src/adapters/notebooklm_adapter.py`
- `tests/unit/test_notebooklm_adapter.py`
- `tests/fixtures/mock_notebooklm.py`
- Polling simulation test

---

#### T2.3: LLM Adapter & Decision Engine
**Owner**: Backend Engineer (ML Integration Specialist)  
**Effort**: 25 hours

**Overview**:
- Wrapper around LLM API (OpenAI default)
- Parse structured outputs (JSON)
- Fallback to rule-based logic if LLM fails
- Caching of decisions (embeddings-based)
- Cost & latency tracking

**Key Methods**:
```python
class LLMAdapterInterface(ABC):
    async def decide_layout(self, content: ContentBlock, constraints: LayoutConstraints) -> LayoutDecision: ...
    async def suggest_refinements(self, design: Design, content: Content) -> List[Suggestion]: ...
    async def extract_key_points(self, text: str, max_points: int) -> List[str]: ...
```

**Implementation**:
```python
class OpenAILLMAdapter(LLMAdapterInterface):
    async def decide_layout(self, content: ContentBlock, constraints: LayoutConstraints) -> LayoutDecision:
        # 1. Check cache (embeddings-based)
        cached = await self.cache.get_similar("layout_plan", content.embedding)
        if cached:
            return cached
        
        # 2. Build prompt
        prompt = self._build_layout_prompt(content, constraints)
        
        # 3. Call OpenAI
        response = await self.client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            response_format={"type": "json_object"}  # structured output
        )
        
        # 4. Parse response
        decision = LayoutDecision.parse_obj(json.loads(response.choices[0].message.content))
        
        # 5. Cache result
        await self.cache.set("layout_plan", decision, embedding=content.embedding)
        
        return decision
```

**Acceptance Criteria**:
- [ ] OpenAI integration working
- [ ] JSON response parsing
- [ ] Fallback to rule-based logic
- [ ] Caching of decisions
- [ ] Cost tracking (tokens used)
- [ ] Timeout handling (10-30s per call)
- [ ] Mock LLM for testing
- [ ] Prompt versioning (for A/B testing)

**Deliverables**:
- `src/adapters/llm_adapter.py`
- `src/orchestration/decision_engine.py`
- `tests/unit/test_llm_adapter.py`
- Prompt templates in `src/prompts/`

---

#### T2.4: Rate Limiting & Backpressure
**Owner**: Backend Engineer  
**Effort**: 15 hours

**Overview**:
- Implement per-service rate limiting (Canva, NotebookLM)
- Track usage per tenant
- Enforce quota limits
- Signal backpressure to orchestrator

**Implementation**:
```python
# src/adapters/rate_limiter.py
class RateLimiter:
    def __init__(self, redis_client, service: str, limit_per_minute: int):
        self.redis = redis_client
        self.service = service
        self.limit_per_minute = limit_per_minute
    
    async def acquire(self, tenant_id: UUID) -> None:
        """
        Check rate limit; raise RateLimitError if exceeded
        Uses token bucket algorithm
        """
        key = f"ratelimit:{self.service}:{tenant_id}:current_minute"
        current_count = await self.redis.incr(key)
        
        if current_count == 1:
            # First request in this minute; set expiry
            await self.redis.expire(key, 60)
        
        if current_count > self.limit_per_minute:
            raise RateLimitError(
                f"Rate limit exceeded for {self.service}. "
                f"Limit: {self.limit_per_minute}/minute. "
                f"Current: {current_count}"
            )
        
        # Calculate and emit backpressure signal
        utilization = current_count / self.limit_per_minute
        if utilization > 0.8:
            await self.emit_backpressure_signal(utilization)
```

**Acceptance Criteria**:
- [ ] Token bucket algorithm working
- [ ] Per-tenant quotas enforced
- [ ] Backpressure signals emitted
- [ ] Quota reset at correct time
- [ ] Tests for edge cases (concurrent requests, boundary)
- [ ] Monitoring of rate limit usage

**Deliverables**:
- `src/adapters/rate_limiter.py`
- Tests for all rate limit scenarios
- Metrics for quota usage

---

### Phase 2 Summary

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| T2.1: Canva Adapter | Backend | 40h | Not Started |
| T2.2: NotebookLM Adapter | Backend | 35h | Not Started |
| T2.3: LLM Adapter | Backend | 25h | Not Started |
| T2.4: Rate Limiting | Backend | 15h | Not Started |
| **Phase 2 Total** | | **100h** | **Not Started** |

**Definition of Done**:
- [ ] All 4 adapters implemented and tested
- [ ] Rate limiting enforced
- [ ] Mocks work for local testing
- [ ] Real API integration tested (if credentials available)
- [ ] 80%+ unit test coverage
- [ ] Performance targets met (<2s per operation)
- [ ] Error handling comprehensive
- [ ] Ready for orchestration engine (Phase 3)

---

## PHASE 3: Orchestration Engine
**Duration**: 3 weeks | **Effort**: 120 hours  
**Goal**: Complete workflow orchestration with state machine, task graph execution, and LLM-based decision logic

### Tasks (High-Level)

#### T3.1: Workflow State Machine (30 hours)
- Define states and transitions
- Implement state persistence
- Event emission on state changes
- Replay/recovery logic

#### T3.2: Task Graph Executor (35 hours)
- Parse workflow definitions (YAML/JSON)
- Topological sort for dependencies
- Parallel execution where possible
- Input substitution and output caching
- Checkpoint state after each task

#### T3.3: Decision Engine Integration (30 hours)
- Integrate LLM adapter
- Content abstraction from NotebookLM output
- Layout planning logic
- Brand constraint enforcement
- Refinement suggestions

#### T3.4: Event System & Hooks (25 hours)
- Define event types (workflow.started, task.completed, error.occurred)
- Event store (append-only log)
- Event subscribers/handlers
- Webhook emission for external systems

### Phase 3 Summary

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| T3.1: State Machine | Backend | 30h | Not Started |
| T3.2: Task Executor | Backend | 35h | Not Started |
| T3.3: Decision Engine | Backend | 30h | Not Started |
| T3.4: Events | Backend | 25h | Not Started |
| **Phase 3 Total** | | **120h** | **Not Started** |

**Definition of Done**:
- [ ] All orchestration components implemented
- [ ] Workflow execution end-to-end
- [ ] State persistence and recovery
- [ ] LLM reasoning integrated
- [ ] Error recovery working
- [ ] Event system operational
- [ ] 70%+ coverage on orchestration tests
- [ ] Ready for API & Queue integration (Phase 4)

---

## PHASE 4: API & Task Queue
**Duration**: 2 weeks | **Effort**: 80 hours  
**Goal**: REST API fully operational, async task queue distributing work to workers

### Tasks (High-Level)

#### T4.1: REST API Endpoints (25 hours)
- Workflow CRUD
- Design management
- Source management
- Status tracking
- Pagination, filtering, sorting
- Error responses (proper HTTP status codes)

#### T4.2: OpenAPI Documentation (10 hours)
- Automatic Swagger generation
- API reference documentation
- Example requests/responses
- Authentication details

#### T4.3: Redis Streams Task Queue (20 hours)
- Task enqueue logic
- Priority queue management
- Dead-letter queue for failed tasks
- Task state tracking
- Consumer group coordination

#### T4.4: Worker Implementation (25 hours)
- Worker pool architecture
- Task claiming and processing
- Heartbeat/liveness detection
- Graceful shutdown
- Metrics collection

### Phase 4 Summary

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| T4.1: REST API | Backend | 25h | Not Started |
| T4.2: Documentation | Tech Writer | 10h | Not Started |
| T4.3: Task Queue | Backend | 20h | Not Started |
| T4.4: Workers | Backend | 25h | Not Started |
| **Phase 4 Total** | | **80h** | **Not Started** |

**Definition of Done**:
- [ ] All REST endpoints operational
- [ ] Swagger documentation complete and accurate
- [ ] Task queue processing workflows
- [ ] Workers handling tasks concurrently
- [ ] Graceful error handling
- [ ] Ready for testing phase (Phase 5)

---

## PHASE 5: Testing & Reliability
**Duration**: 2 weeks | **Effort**: 100 hours  
**Goal**: 80%+ test coverage, performance optimization, chaos engineering

### Tasks (High-Level)

#### T5.1: Unit Tests (40 hours)
- Comprehensive unit test suite
- 80%+ coverage
- Mocked dependencies
- Edge case coverage

#### T5.2: Integration Tests (30 hours)
- E2E workflow tests
- API integration tests
- Database integration tests
- Real adapter tests (with mock APIs)

#### T5.3: Performance Testing (20 hours)
- Load testing (100s concurrent users)
- Latency profiling
- Memory usage analysis
- Database query optimization

#### T5.4: Chaos Engineering (10 hours)
- Simulate API failures
- Network timeouts
- Database connection loss
- Verify graceful degradation

### Phase 5 Summary

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| T5.1: Unit Tests | QA | 40h | Not Started |
| T5.2: Integration Tests | QA | 30h | Not Started |
| T5.3: Performance | QA | 20h | Not Started |
| T5.4: Chaos Engineering | QA | 10h | Not Started |
| **Phase 5 Total** | | **100h** | **Not Started** |

**Definition of Done**:
- [ ] 80%+ test coverage
- [ ] All tests passing
- [ ] Performance benchmarks met
- [ ] Chaos tests passing
- [ ] Ready for observability phase (Phase 6)

---

## PHASE 6: Observability & Monitoring
**Duration**: 2 weeks | **Effort**: 80 hours  
**Goal**: Complete observability stack with logging, tracing, metrics, and alerting

### Tasks (High-Level)

#### T6.1: ELK Stack Integration (25 hours)
- Structured logging to Elasticsearch
- Kibana dashboards
- Log retention policies
- Index management

#### T6.2: Jaeger Tracing (20 hours)
- Trace propagation across services
- Jaeger UI configuration
- Performance analysis
- Root cause analysis workflows

#### T6.3: Prometheus & Grafana (20 hours)
- Metrics export
- Grafana dashboards
- Alert rules
- Runbooks for on-call

#### T6.4: Audit & Compliance Logging (15 hours)
- Immutable audit logs
- Compliance reporting
- Data retention policies

### Phase 6 Summary

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| T6.1: ELK Stack | DevOps | 25h | Not Started |
| T6.2: Jaeger | DevOps | 20h | Not Started |
| T6.3: Prometheus | DevOps | 20h | Not Started |
| T6.4: Audit Logs | Security | 15h | Not Started |
| **Phase 6 Total** | | **80h** | **Not Started** |

**Definition of Done**:
- [ ] Logs flowing to ELK
- [ ] Traces visible in Jaeger
- [ ] Metrics in Prometheus/Grafana
- [ ] Dashboards created
- [ ] Alert rules configured
- [ ] Runbooks written
- [ ] Ready for deployment (Phase 7)

---

## PHASE 7: Deployment & Polish
**Duration**: 2 weeks | **Effort**: 80 hours  
**Goal**: Production-ready containerization, K8s manifests, CI/CD, documentation

### Tasks (High-Level)

#### T7.1: Docker Containerization (15 hours)
- Multi-stage Dockerfile
- Alpine base image
- Image optimization
- Security scanning

#### T7.2: Kubernetes Manifests (25 hours)
- Deployments, Services, Ingress
- ConfigMaps, Secrets
- StatefulSets for postgres/redis
- Horizontal Pod Autoscaler

#### T7.3: CI/CD Pipeline (20 hours)
- GitHub Actions / GitLab CI
- Automated tests on push
- Build and push to registry
- Automated deployment to staging
- Manual approval for production

#### T7.4: Documentation & Handoff (20 hours)
- Deployment guide
- Runbook for on-call
- Troubleshooting guide
- Knowledge transfer sessions

### Phase 7 Summary

| Task | Owner | Effort | Status |
|------|-------|--------|--------|
| T7.1: Docker | DevOps | 15h | Not Started |
| T7.2: Kubernetes | DevOps | 25h | Not Started |
| T7.3: CI/CD | DevOps | 20h | Not Started |
| T7.4: Documentation | Tech Writer | 20h | Not Started |
| **Phase 7 Total** | | **80h** | **Not Started** |

**Definition of Done**:
- [ ] Docker images built and tested
- [ ] K8s manifests reviewed and tested
- [ ] CI/CD pipeline operational
- [ ] Deployment to production successful
- [ ] Runbooks tested
- [ ] Documentation complete
- [ ] Project ready for handoff/operations

---

## OVERALL SUMMARY

### Timeline

```
Week 1    PHASE 0: Setup (40h)
Week 2-3  PHASE 1: Infrastructure (80h)
Week 4-5  PHASE 2: Adapters (100h)
Week 6-8  PHASE 3: Orchestration (120h)
Week 9-10 PHASE 4: API & Queue (80h)
Week 11-12 PHASE 5: Testing (100h)
Week 13-14 PHASE 6: Observability (80h)
Week 15-16 PHASE 7: Deployment (80h)

Total: 16 weeks | ~680 hours
```

### Effort Breakdown

| Component | Hours | % |
|-----------|-------|---|
| Setup & Infrastructure | 120 | 18% |
| Adapter Implementation | 100 | 15% |
| Orchestration | 120 | 18% |
| API & Queue | 80 | 12% |
| Testing | 100 | 15% |
| Observability | 80 | 12% |
| Deployment | 80 | 12% |
| **Total** | **680** | **100%** |

### Team Composition (Suggested)

- **Tech Lead / Architect**: Oversight, design decisions
- **Backend Engineers** (2-3): Core development
- **QA Engineer**: Testing, performance validation
- **DevOps Engineer**: Infrastructure, CI/CD, deployment
- **Tech Writer**: Documentation
- **Security Engineer**: Security audit, secrets management

### Success Metrics

- [ ] 80%+ test coverage
- [ ] <5s avg response time for status checks
- [ ] <30s avg workflow completion (simple case)
- [ ] 99.9% uptime (SLA)
- [ ] <5% error rate
- [ ] Documentation complete and clear
- [ ] Team trained and confident
- [ ] Production deployment successful

---

## NEXT STEPS

1. **Confirm timeline**: Can your team commit 12-16 weeks?
2. **Allocate resources**: Who owns each phase?
3. **Prioritize**: Any phases that can be deferred?
4. **Begin Phase 0**: Start with setup and environment validation

Would you like me to:
- Create detailed task cards for Phase 0?
- Refine any phase estimates?
- Adjust the timeline or scope?
- Proceed with Phase 0 implementation now?

