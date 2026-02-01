# Database Schema Documentation

## Overview

The schema is designed for multi-tenant SaaS with:
- **Multi-tenancy**: All tables have `tenant_id` FK to Tenants table
- **Audit trail**: Immutable AuditLog captures all state changes
- **Flexible metadata**: JSONB columns for evolving data without migrations
- **Relationships**: Proper cascading and referential integrity
- **Indexing**: Strategic indexes on common queries (tenant_id, user_id, created_at, status)

## Tables

### Tenants
Root entity for multi-tenancy. Each organization/team is a tenant.

```
id (UUID, PK)
name (String, UNIQUE) - Organization name
tier (String) - Subscription tier: free, pro, enterprise
is_active (Boolean) - Soft-delete support
metadata (JSON) - Custom attributes
created_at (TIMESTAMP TZ)
updated_at (TIMESTAMP TZ)

Indexes:
  - PRIMARY KEY (id)
  - UNIQUE (name)
  - INDEX (name)
```

**Relationships**:
- 1:N → Users
- 1:N → Workflows
- 1:N → Designs
- 1:N → AuditLogs
- 1:N → QuotaUsage

---

### Users
Person within a tenant.

```
id (UUID, PK)
tenant_id (UUID, FK) → Tenants (CASCADE)
email (String, UNIQUE)
display_name (String)
is_active (Boolean)
roles (JSON) - List: [admin, user, viewer]
metadata (JSON)
created_at (TIMESTAMP TZ)
updated_at (TIMESTAMP TZ)

Indexes:
  - PRIMARY KEY (id)
  - FK (tenant_id)
  - UNIQUE (email)
  - COMPOSITE (tenant_id, created_at)
```

**Relationships**:
- N:1 ← Tenant
- 1:N → Workflows

**Constraints**:
- Unique email per system (not per tenant)
- Soft delete via is_active flag

---

### Workflows
Main orchestration record. Tracks state of entire workflow execution.

```
id (UUID, PK)
tenant_id (UUID, FK) → Tenants (CASCADE)
user_id (UUID, FK) → Users (CASCADE)
status (String) - submitted, queued, analyzing, processing, completed, failed, cancelled
current_task_id (UUID, nullable)
input_config (JSON) - User's input parameters
output_artifacts (JSON) - Generated outputs
error_log (JSON, array) - History of errors
metadata (JSON)
created_at (TIMESTAMP TZ)
started_at (TIMESTAMP TZ, nullable)
completed_at (TIMESTAMP TZ, nullable)
updated_at (TIMESTAMP TZ)

Indexes:
  - PRIMARY KEY (id)
  - FK (tenant_id)
  - FK (user_id)
  - INDEX (status) - For filtering by status
  - INDEX (created_at)
  - COMPOSITE (tenant_id, created_at) - Optimized for per-tenant queries
```

**Relationships**:
- N:1 ← Tenant
- N:1 ← User
- 1:N → WorkflowTasks
- 1:N → Designs

**Status Transitions**:
```
submitted → queued → analyzing → processing → completed
                           ↓
                          failed
                           ↓
                        cancelled
```

---

### WorkflowTasks
Subtasks within a workflow. Enables checkpointing and granular error tracking.

```
id (UUID, PK)
workflow_id (UUID, FK) → Workflows (CASCADE)
task_name (String) - e.g., analyze_content, create_design
status (String) - pending, running, completed, failed, retrying
operation_type (String) - notebooklm, canva, llm, etc.
input_data (JSON) - Task input
output_data (JSON) - Task output
error (JSON, nullable) - Error details if failed
retry_count (Integer) - Number of retries attempted
duration_ms (Integer, nullable) - Execution time in milliseconds
created_at (TIMESTAMP TZ)
started_at (TIMESTAMP TZ, nullable)
completed_at (TIMESTAMP TZ, nullable)
updated_at (TIMESTAMP TZ)

Indexes:
  - PRIMARY KEY (id)
  - FK (workflow_id)
  - INDEX (status)
  - INDEX (created_at)
```

**Relationships**:
- N:1 ← Workflow

---

### Designs
Canva design generated for a workflow.

```
id (UUID, PK)
tenant_id (UUID, FK) → Tenants (CASCADE)
workflow_id (UUID, FK) → Workflows (CASCADE)
canva_design_id (String, UNIQUE) - External Canva API ID
title (String)
design_url (Text, nullable) - Canva edit URL
design_metadata (JSON) - Width, height, template_id, etc.
export_formats (JSON) - {png: url, pdf: url, jpg: url, ...}
created_at (TIMESTAMP TZ)
updated_at (TIMESTAMP TZ)

Indexes:
  - PRIMARY KEY (id)
  - FK (tenant_id)
  - FK (workflow_id)
  - UNIQUE (canva_design_id)
  - INDEX (created_at)
```

**Relationships**:
- N:1 ← Tenant
- N:1 ← Workflow

---

### AuditLogs
Immutable audit trail of all state changes. Append-only for compliance.

```
id (BigInt, PK, auto-increment) - Sequential immutable ID
tenant_id (UUID, FK) → Tenants (CASCADE)
user_id (UUID, FK, nullable) → Users (SET NULL)
action (String) - create, update, delete, state_transition, api_call, error
resource_type (String) - workflow, design, user, etc.
resource_id (UUID)
previous_state (JSON, nullable) - State before change
new_state (JSON) - State after change
metadata (JSON) - request_id, ip_address, etc.
timestamp (TIMESTAMP TZ, indexed)

Indexes:
  - PRIMARY KEY (id)
  - FK (tenant_id)
  - COMPOSITE (resource_type, resource_id) - Audit per resource
  - INDEX (timestamp)
```

**Relationships**:
- N:1 ← Tenant
- N:1 ← User (optional, for system actions)

**Design Rationale**:
- BigInt ID: Allows sequential ordering without UUIDs
- Immutable: No updates, only inserts
- Cascading user_id to NULL: User deletion doesn't hide audit trail
- JSON metadata: Extensible for request context (request_id, ip, etc.)

---

### QuotaUsage
Per-tenant quota tracking for rate limiting and billing.

```
id (BigInt, PK, auto-increment)
tenant_id (UUID, FK) → Tenants (CASCADE)
service (String) - canva, notebooklm, llm, api_calls
metric (String) - designs_created, notebooks_analyzed, api_requests, etc.
current_usage (Integer)
limit_value (Integer) - -1 = unlimited
reset_at (TIMESTAMP TZ) - When quota resets (daily, monthly, etc.)
metadata (JSON) - Additional context
created_at (TIMESTAMP TZ)
updated_at (TIMESTAMP TZ)

Indexes:
  - PRIMARY KEY (id)
  - COMPOSITE (tenant_id, service) - Query per service
  - INDEX (reset_at) - Find expired quotas
```

**Relationships**:
- N:1 ← Tenant

**Usage**:
- Enforce per-tenant rate limits
- Track usage for billing
- Detect abuse/anomalies

---

## Multi-Tenancy Guarantees

1. **Schema**: Every table except Tenants has `tenant_id` FK
2. **Queries**: Repository layer enforces `WHERE tenant_id = ?` automatically
3. **Cascading**: Deleting tenant cascades to all child entities
4. **Isolation**: Impossible for User A (tenant A) to read User B's (tenant B) data
5. **Audit**: Audit logs include tenant_id for compliance

---

## JSON Columns

JSONB columns used for flexibility without schema migrations:

| Table | Column | Purpose | Example |
|-------|--------|---------|---------|
| Tenants | metadata | Org-specific settings | `{branding: {...}, integrations: {...}}` |
| Users | metadata | User preferences | `{theme: dark, language: en}` |
| Workflows | input_config | User input | `{source_id: "nb_123", template: "presentation"}` |
| Workflows | output_artifacts | Generated outputs | `{design_ids: [...], exports: {...}}` |
| Workflows | error_log | Error history | `[{code: "...", message: "...", timestamp: ...}]` |
| WorkflowTasks | input_data | Task input | `{notebook_id: "...", analysis_type: "..."}` |
| WorkflowTasks | output_data | Task result | `{summary: "...", insights: [...]}` |
| Designs | design_metadata | Design properties | `{width: 1920, height: 1080, template_id: "..."}` |
| Designs | export_formats | Export URLs | `{png: "url", pdf: "url", jpg: "url"}` |
| AuditLogs | previous_state | Old values | `{status: "submitted"}` |
| AuditLogs | new_state | New values | `{status: "queued"}` |
| QuotaUsage | metadata | Context | `{last_reset: "...", overage: 0}` |

---

## Indexes Strategy

**Golden Rule**: Index on queries that:
1. Filter by status (WORKFLOW.status)
2. Filter by tenant (all tables on tenant_id)
3. Filter by user (USERS.user_id, WORKFLOWS.user_id)
4. Order by created_at (all tables)
5. Composite queries (tenant_id + created_at for paginated per-tenant queries)

**Avoid**: Indexing columns rarely used in WHERE/ORDER BY (bloats DB).

---

## Async Requirements

- All DB access is **async-native** (AsyncSession, AsyncEngine)
- No sync sessions allowed
- See `src/storage/database.py` for connection management
- See `src/storage/repository.py` for async query patterns

---

## Migration Process

Migrations are managed by Alembic:

```bash
# Create new migration (auto-detect changes)
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Rollback one revision
alembic downgrade -1

# View migration history
alembic history
```

Initial migration: `001_initial_schema.py` (all tables created)

---

## See Also

- [ADR-009: PostgreSQL + JSONB](../ARCHITECTURE_DECISIONS.md#adr-009-postgresql-with-jsonb-for-semi-structured-data)
- [ADR-004: Multi-Tenancy by Design](../ARCHITECTURE_DECISIONS.md#adr-004-multi-tenancy-by-design)
- `src/storage/models.py` — Python ORM definitions
- `src/storage/database.py` — Async engine and session management
