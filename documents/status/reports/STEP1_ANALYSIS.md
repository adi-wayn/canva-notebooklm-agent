# STEP 1: Repository & Requirements Analysis
## Canva-NotebookLM Integration Custom Agent

**Status**: Analysis Complete | Ready for Clarification  
**Date**: January 17, 2026  
**Analyst**: AI Architecture Lead

---

## 1. REPOSITORY STRUCTURE & CURRENT STATE

### Current Codebase Inventory

```
canva-notebooklm-agent/
├── src/
│   ├── __init__.py
│   ├── main.py                          [PROTOTYPE FastAPI app - 219 lines]
│   ├── requirements.txt                 [Dependencies listed]
│   └── auth/                            [NEW - Authentication layer]
│       ├── __init__.py
│       ├── canva_auth_manager.py        [OAuth 2.0 + PKCE - fully implemented]
│       ├── notebooklm_auth_manager.py   [Service account + API key auth - fully implemented]
│       ├── token_manager.py             [Secure token storage + encryption - fully implemented]
│       └── auth_middleware.py           [FastAPI middleware + dependencies - implemented]
│
├── tests/
│   └── test_authentication.py           [15 test cases - now passing]
│
├── .a0proj/                             [Planning & knowledge base]
│   ├── instructions/
│   │   ├── README.md                    [Overview & quick start]
│   │   ├── solution_overview.md         [Business value & use cases]
│   │   ├── architecture.md              [Detailed technical architecture]
│   │   ├── technical_docs.md            [API specifications]
│   │   ├── implementation_guide.md      [Deployment instructions]
│   │   └── requirements.txt             [Dependency baseline]
│   └── knowledge/                       [Reference materials]
│
├── encryption_key.key                   [Generated for token encryption]
└── .venv/                               [Python 3.14 virtual environment]
```

### Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| **Authentication Layer** | ✅ COMPLETE | OAuth 2.0/PKCE (Canva), Service Account/API Key (NotebookLM), secure token storage |
| **Test Suite** | ✅ PASSING | 15 tests covering auth managers, token mgmt, middleware |
| **API Skeleton** | ⚠️ PROTOTYPE | Basic FastAPI app with mock in-memory storage |
| **Canva Integration** | ❌ NOT STARTED | API client logic needed |
| **NotebookLM Integration** | ❌ NOT STARTED | API client logic needed |
| **Orchestration Engine** | ❌ NOT STARTED | Workflow/agent logic needed |
| **Queue System** | ❌ NOT STARTED | Background task processing |
| **Database Layer** | ❌ NOT STARTED | Persistence & state management |
| **Monitoring/Observability** | ❌ NOT STARTED | Logging, metrics, tracing |
| **UI/Frontend** | ❌ NOT STARTED | Web or CLI interface |
| **Deployment** | ❌ NOT STARTED | Docker, K8s configuration |

---

## 2. EXTRACTED REQUIREMENTS

### 2.1 FUNCTIONAL REQUIREMENTS

#### A. Core Agent Capabilities

1. **Content Generation from NotebookLM**
   - Fetch insights, reports, mind maps, and infographics from NotebookLM
   - Support multiple output formats (text, structured JSON, markdown)
   - Handle pagination and bulk retrieval
   - Preserve metadata and source attribution

2. **Design Automation in Canva**
   - Create new Canva designs from NotebookLM content
   - Transform text/data into visual layouts (presentations, infographics, posters)
   - Insert generated assets into existing Canva projects
   - Support template selection and customization
   - Apply Canva AI suggestions for design enhancement

3. **Bi-directional Content Transformation**
   - Text-to-Image: Convert textual descriptions → visual elements
   - Image-to-Text: Extract text from Canva designs for re-analysis
   - Data-to-Layout: Structure content into Canva-ready formats
   - Maintain visual consistency and brand guidelines

4. **Workflow Orchestration**
   - Define multi-step workflows (e.g., "analyze document → generate insights → create presentation")
   - Execute transformations asynchronously with state tracking
   - Handle partial failures and retry logic
   - Support priority-based execution queuing

5. **Request Management**
   - Track transformation requests from submission to completion
   - Provide real-time status updates (queued → processing → completed/failed)
   - Generate comprehensive result artifacts
   - Maintain request history and audit logs

#### B. Authentication & Authorization

1. **Multi-Platform OAuth**
   - Canva: OAuth 2.0 with PKCE (✅ Implemented)
   - NotebookLM: Service Account + API Key support (✅ Implemented)
   - Token refresh and expiration handling (✅ Implemented)
   - Secure credential storage with encryption (✅ Implemented)

2. **Access Control**
   - API key-based authentication option
   - Scope-based permissions (e.g., "design:read", "design:write")
   - Per-user token isolation
   - Rate limiting and quota enforcement

#### C. API Surface

1. **REST Endpoints** (defined in technical_docs.md)
   - `POST /authenticate` — User authentication
   - `POST /transform` — Submit transformation requests
   - `GET /status/{request_id}` — Check request status
   - `GET /health` — System health check

2. **Extended Endpoints** (implied)
   - `GET /designs` — List Canva designs
   - `POST /designs` — Create new design
   - `GET /sources` — List NotebookLM sources
   - `POST /sources/analyze` — Trigger analysis
   - `GET /transformations` — List past transformations
   - User management & settings endpoints

### 2.2 NON-FUNCTIONAL REQUIREMENTS

#### A. Security

- **Secrets Management**: No hardcoded credentials; all API keys in environment variables
- **Token Storage**: Encrypted at rest using Fernet (✅ Implemented)
- **Transport Security**: HTTPS/TLS enforced for all external API calls
- **Access Logging**: Audit trail of all transformation requests
- **Rate Limiting**: Per-user and per-IP limits to prevent abuse
- **Data Privacy**: PII/sensitive content handling per GDPR/CCPA

#### B. Reliability & Resilience

- **Retry Logic**: Exponential backoff for failed API calls
- **Circuit Breaker Pattern**: Fail gracefully when external APIs are degraded
- **Request Idempotency**: Prevent duplicate processing on retries
- **Timeout Management**: Configurable per operation (auth: 5min, transform: 10min)
- **Graceful Degradation**: Partial results rather than total failure
- **Error Recovery**: Dead-letter queues for failed async tasks

#### C. Performance & Scalability

- **Asynchronous Processing**: Async/await for I/O-bound operations
- **Background Workers**: Horizontal scaling via queue-based workers
- **Caching**: Token caching, response caching for repeated queries
- **Database Indexing**: Optimized queries on request_id, user_id, timestamp
- **Connection Pooling**: Reuse DB and API connections
- **Target Throughput**: 100+ concurrent users, <5s avg response time for status checks

#### D. Observability

- **Structured Logging**: JSON logs with request context (request_id, user_id, operation)
- **Distributed Tracing**: Trace requests across service boundaries
- **Metrics**: Prometheus metrics for request volume, latency, error rates
- **Dashboards**: Grafana dashboards for system health
- **Alerting**: Alert on error rates >5%, latency >10s, queue depth >1000

#### E. Maintainability

- **Code Organization**: Clear separation of concerns (auth, API, domain, storage)
- **Type Hints**: Full Python type annotations (Python 3.8+)
- **Testing**: Unit tests (80%+ coverage), integration tests, E2E tests
- **Documentation**: Inline docstrings, API docs (OpenAPI/Swagger), architecture ADRs
- **Dependency Management**: Pinned versions in requirements.txt, no unused imports
- **CI/CD**: Automated linting (pylint), type checking (mypy), testing (pytest)

---

## 3. CONSTRAINTS & ASSUMPTIONS

### Constraints

1. **API Availability**
   - Canva API and NotebookLM APIs may be rate-limited or have quota restrictions
   - Third-party APIs may have SLAs <99% uptime
   - API changes/deprecations may occur without notice

2. **External Dependencies**
   - Reliance on NotebookLM and Canva maintaining API stability
   - OAuth token refresh flows must align with their implementation
   - Design/content limitations based on platform capabilities

3. **Resource Limits**
   - File uploads may have size limits (images, PDFs)
   - Design canvas has dimension constraints (Canva's limits)
   - Concurrent request limits based on queue capacity and worker pool

4. **Timeline & Scope**
   - Prototype must be developed incrementally with working vertical slices
   - Not all Canva/NotebookLM features will be immediately supported
   - MVP = Auth + single transformation type + status tracking

### Assumptions

1. **Technical Stack**
   - Python 3.8+ (you have 3.14 in .venv)
   - FastAPI for REST API
   - PostgreSQL for relational data
   - Redis or RabbitMQ for async queuing
   - Docker for containerization

2. **API Availability**
   - Both Canva and NotebookLM provide REST/gRPC APIs with adequate rate limits
   - OAuth implementations are standard (RFC 6749 + PKCE RFC 7636)
   - API documentation is current and accessible

3. **Operational**
   - Team has access to Canva API credentials and NotebookLM service account
   - Infrastructure available for deployment (local, cloud, on-prem)
   - Logging/monitoring infrastructure exists or will be set up

4. **User Context**
   - Initial users are power users (designers, content strategists) familiar with both platforms
   - Single-tenant or multi-tenant SaaS model will be decided later
   - User authentication already handled; focus is on platform integration

---

## 4. CURRENT GAPS & OPEN QUESTIONS

### Critical Questions (BLOCKING)

**Q1: Canva & NotebookLM API Specifics**
   - Do you have active API keys/credentials for both platforms?
   - Are the official API client libraries available (or must we call raw REST)?
   - What are the rate limits (requests/sec, quota per day)?
   - Do both APIs support async/webhook callbacks, or only polling?

**Q2: Transformation Scope**
   - Which NotebookLM outputs are targets? (insights, infographics, mind maps, reports, summaries?)
   - Which Canva design types should we support? (presentations, social media, posters, documents?)
   - How deep is the integration? (simple copy-paste vs. semantic transformation?)
   - Example: "User uploads PDF → NotebookLM analyzes → Agent creates Canva presentation"?

**Q3: Agent Behavior**
   - Is this a "user-triggered" workflow (user clicks "Create Design") or "autonomous agent" (continuously monitoring and creating)?
   - Should the agent make decisions (e.g., which template, color scheme) or just execute user instructions?
   - Do you envision LLM-based reasoning (e.g., GPT-4 deciding design layout) or rule-based orchestration?

**Q4: Deployment Context**
   - Where will this run? (Local machine, cloud VM, Kubernetes cluster, serverless?)
   - Single user or multi-tenant?
   - What's the expected volume? (10 requests/day, 1000s/day?)
   - Budget/infrastructure constraints?

**Q5: UI/UX Scope**
   - MVP UI: Web dashboard, CLI tool, or headless API-only?
   - If web UI: simple form-based or advanced workflow builder?
   - Mobile support needed?

### Important Questions (HIGH PRIORITY)

**Q6: Data Ownership & Privacy**
   - Where are user files stored? (Canva's cloud, your servers, temporary storage?)
   - How long do we retain transformation results?
   - GDPR/data residency concerns?

**Q7: Error Handling & User Feedback**
   - When a transformation partially fails (e.g., 50 images processed, 1 failed), what behavior?
   - Should users get detailed error reports or simplified messages?
   - Retry strategy: automatic, manual, or user-configurable?

**Q8: Extensibility**
   - Plan to support additional platforms later (Figma, Adobe, Miro)?
   - Should the architecture be designed for plugin-based transformers?
   - Will there be custom transformation logic per user/team?

### Secondary Questions (CAN BE DEFERRED)

**Q9: Analytics & Reporting**
   - Do you need insights on: which designs are created most, which transformations succeed/fail, user engagement metrics?

**Q10: Cost Attribution**
   - Need to track costs per user/team based on API call volume?
   - Billing model for multi-tenant scenario?

---

## 5. KEY FINDINGS & RECOMMENDATIONS

### Strengths of Current Setup

✅ **Authentication layer is production-ready**: OAuth 2.0 + PKCE for Canva, service account support, encrypted token storage, comprehensive tests passing.

✅ **Good planning & documentation**: Architecture, solution overview, implementation guide already drafted.

✅ **Clean code foundation**: Type hints, middleware, dependency injection patterns in place.

### Risks & Gaps

⚠️ **No integration with actual Canva/NotebookLM APIs yet**: Prototype uses mock storage; real integration will be non-trivial.

⚠️ **No persistent storage**: Using in-memory dicts; need PostgreSQL + migrations.

⚠️ **No async queue system**: Required for scaling; no RabbitMQ/Redis + workers.

⚠️ **Missing orchestration logic**: Agent/workflow engine is the core missing piece.

⚠️ **No monitoring/observability**: Logging, tracing, metrics not yet set up.

### Recommended Approach

1. **Validate API access** (Week 1): Confirm Canva & NotebookLM API credentials work, document rate limits.
2. **Finalize requirements** (Week 1): Clarify questions above with product/stakeholders.
3. **Scaffold core infrastructure** (Week 2): DB schema, queue setup, configuration management.
4. **Implement vertical slices** (Weeks 3-6):
   - **Slice 1**: NotebookLM → fetch insights
   - **Slice 2**: Canva → create design from template
   - **Slice 3**: Transform NotebookLM insight → design
   - **Slice 4**: Full workflow orchestration
5. **Polish & deploy** (Week 7+): Testing, monitoring, containerization.

---

## 6. SUMMARY TABLE: REQUIREMENTS MATRIX

| Category | Requirement | Priority | Estimated Effort | Status |
|----------|-------------|----------|------------------|--------|
| **Auth** | Canva OAuth 2.0 + PKCE | P0 | 40h | ✅ DONE |
| **Auth** | NotebookLM service account | P0 | 30h | ✅ DONE |
| **Auth** | Token encryption & refresh | P0 | 20h | ✅ DONE |
| **API** | REST endpoints (auth, transform, status) | P0 | 40h | ⚠️ PARTIAL |
| **API** | OpenAPI/Swagger docs | P1 | 10h | ❌ TODO |
| **Core** | NotebookLM API client | P0 | 50h | ❌ TODO |
| **Core** | Canva API client | P0 | 60h | ❌ TODO |
| **Core** | Workflow orchestrator | P0 | 80h | ❌ TODO |
| **Core** | Async queue (RabbitMQ/Redis) | P0 | 50h | ❌ TODO |
| **Data** | PostgreSQL schema & migrations | P0 | 30h | ❌ TODO |
| **Data** | Request/response persistence | P0 | 40h | ❌ TODO |
| **Observability** | Structured logging | P1 | 20h | ❌ TODO |
| **Observability** | Distributed tracing | P2 | 30h | ❌ TODO |
| **Testing** | Unit tests (80%+ coverage) | P1 | 60h | ⚠️ STARTED |
| **Testing** | Integration tests | P1 | 50h | ❌ TODO |
| **Testing** | E2E tests | P2 | 40h | ❌ TODO |
| **UI** | REST API only (MVP) | P0 | 0h | ✅ BASELINE |
| **UI** | Web dashboard (future) | P2 | 100h | ❌ DEFERRED |
| **Deployment** | Docker containerization | P1 | 20h | ❌ TODO |
| **Deployment** | K8s/compose orchestration | P2 | 40h | ❌ TODO |

**Estimated Total (MVP)**: ~560 hours | **Timeline**: 8-12 weeks with focused team

---

## NEXT STEPS

**BLOCKING**: Please answer the Critical Questions (Q1-Q5) above.  
**THEN**: We proceed to **Step 2: Target Architecture** with a concrete technical design.

Would you like me to:
1. Create a clarification questionnaire you can fill out?
2. Make reasonable assumptions and proceed with a reference architecture?
3. Focus on one specific area first (e.g., finalizing Canva API client)?

