# Task B Step 1 Complete: Real Canva OAuth Integration

## Status: ✅ COMPLETE

All database, backend OAuth, and UI components for Canva OAuth integration have been implemented.

## What Was Built

### 1. Database Layer

#### UserConnection Model
- **File**: `src/storage/models.py`
- **Table**: `user_connections`
- **Purpose**: Store OAuth tokens securely with multi-tenant isolation
- **Fields**:
  - `id` (PK)
  - `user_id` (FK to users)
  - `tenant_id` (FK to tenants)
  - `provider` ('canva', 'notebooklm', etc.)
  - `access_token`, `refresh_token`
  - `token_expires_at`
  - `account_email`, `account_name`
  - `created_at`, `updated_at`
- **Indexes**:
  - Composite unique on (user_id, tenant_id, provider) - prevents duplicate connections
  - Index on (user_id, tenant_id) - quick lookups by user
  - Index on provider - efficient filtering by service

#### Alembic Migration
- **File**: `alembic/versions/002_user_connections.py`
- **Status**: Ready to run with `alembic upgrade head`
- **Contains**: Table creation + indexes, up/down functions

### 2. Repository Layer

#### UserConnectionRepository Class
- **File**: `src/storage/repository.py`
- **Pattern**: Extends BaseRepository[UserConnection, int]
- **Tenant-scoped**: All queries automatically filtered to tenant
- **User-scoped**: Initialized with user_id for token isolation
- **Methods**:
  - `get_connection(provider)` → UserConnection | None
  - `save_connection(provider, access_token, refresh_token, expires_at, ...)` → UserConnection
  - `update_tokens(provider, access_token, refresh_token, expires_at)` → UserConnection | None
  - `delete_connection(provider)` → bool
  - `has_connection(provider)` → bool

### 3. OAuth Endpoints

#### New File: `src/api/routes/auth.py`
Created complete Canva OAuth flow with 4 endpoints:

**1. GET `/api/v1/auth/canva/authorize`**
- Headers: `X-Tenant-ID`, `X-User-ID`
- Generates CSRF state token
- Redirects to Canva OAuth consent screen
- Scopes: `design:create`, `design:read`, `design:update`

**2. GET `/api/v1/auth/canva/callback`**
- Receives code and state from Canva
- Exchanges code for access/refresh tokens (real Canva API)
- Fetches user account info (email, name)
- Stores tokens in `user_connections` table
- Redirects to frontend with success/error status
- CSRF protection: Validates state token, checks expiration (5 min)

**3. GET `/api/v1/auth/canva/status`**
- Headers: `X-Tenant-ID`, `X-User-ID`
- Returns connection status:
  ```json
  {
    "connected": true,
    "provider": "canva",
    "account_email": "user@example.com",
    "account_name": "John Doe",
    "connected_at": "2025-01-18T10:30:00Z"
  }
  ```

**4. POST `/api/v1/auth/canva/disconnect`**
- Revokes connection and deletes tokens from database
- Requires confirmation to prevent accidental disconnection

#### OAuth Flow Integration
- Registered in `src/main.py`: `app.include_router(auth_router)`
- Uses real Canva OAuth endpoints
- Handles token exchange securely
- No mock tokens - real authentication

### 4. UI Components

#### ConnectionStatus Component
- **File**: `ui/src/components/ConnectionStatus.jsx`
- **Styling**: `ui/src/components/ConnectionStatus.css`
- **Features**:
  - Displays connection status on startup
  - Shows "Connect Canva" button when disconnected
  - Shows connected email when authorized
  - OAuth flow initiation (redirects to Canva consent)
  - One-click disconnect with confirmation
  - URL parameter handling for OAuth callback
  - Responsive design with icons

#### Integration with WorkflowPage
- Added to empty state section
- Shows before user creates first workflow
- Provides clear call-to-action to authorize Canva
- Persists connection state across page reloads

### 5. Canva Adapter Enhancement

#### Real Token Management
- **File**: `src/adapters/canva_adapter.py`
- **Changes**:
  - Added `user_id`, `tenant_id` parameters to `__init__`
  - Enhanced `_refresh_token()` to persist refreshed tokens to database
  - Added token expiration checking
  - Imports database and UserConnectionRepository

#### Factory Method
- New async function: `create_canva_adapter_from_db(user_id, tenant_id)`
- Retrieves tokens from database
- Validates token expiration
- Returns configured adapter ready to use
- Handles missing/expired connections gracefully

## Architecture

```
UI Layer
├── ConnectionStatus component
│   ├── Checks status on mount
│   ├── Initiates OAuth flow
│   ├── Shows connection state
│   └── Handles disconnect
│
API Layer
├── GET /auth/canva/authorize
│   └── Redirects to Canva OAuth
├── GET /auth/canva/callback  
│   └── Exchanges code for tokens
├── GET /auth/canva/status
│   └── Returns connection info
└── POST /auth/canva/disconnect
    └── Revokes tokens

Repository Layer
├── UserConnectionRepository
│   ├── CRUD operations
│   ├── Tenant-scoped
│   └── User-scoped

Database Layer
├── user_connections table
│   ├── Token storage
│   ├── Unique constraint per provider
│   └── Indexes for quick lookups
└── Alembic migration (002)
```

## Security

1. **CSRF Protection**: State token with 5-minute expiration
2. **Tenant Isolation**: All queries filtered by tenant_id
3. **User Isolation**: Connections belong to specific user
4. **Token Storage**: SQLAlchemy ORM (prepared for encryption)
5. **OAuth**: Standard authorization_code grant flow
6. **Token Refresh**: Secure Canva API endpoint with client credentials

## Testing Next Steps

1. **Setup**: Run migration: `alembic upgrade head`
2. **OAuth Flow Test**:
   - Click "Connect Canva" button
   - Authorize in Canva consent screen
   - Verify redirect + token storage
   - Check `user_connections` table
3. **Status Check**:
   - Verify GET `/auth/canva/status` returns connection
   - Email/name display in UI
4. **Token Refresh**:
   - Trigger 401 in adapter
   - Verify `_refresh_token()` updates DB
5. **Disconnect**:
   - Click disconnect button
   - Verify token deletion from DB

## Files Modified

1. ✅ `src/storage/models.py` - Added UserConnection model
2. ✅ `src/storage/repository.py` - Added UserConnectionRepository
3. ✅ `src/api/routes/auth.py` - New OAuth endpoints
4. ✅ `src/main.py` - Registered auth router
5. ✅ `src/adapters/canva_adapter.py` - Real token management
6. ✅ `ui/src/components/ConnectionStatus.jsx` - New component
7. ✅ `ui/src/components/ConnectionStatus.css` - Component styling
8. ✅ `ui/src/pages/WorkflowPage.jsx` - Integrated ConnectionStatus
9. ✅ `alembic/versions/002_user_connections.py` - Database migration

## Next: Task B Step 2

Once verified:
1. Update canva_adapter to call real Canva design creation API
2. Replace mock designs with real API responses
3. Add "Open in Canva" link with real design URLs
4. Wire workflow engine to require Canva connection
5. Test end-to-end: OAuth → Design Creation → Real URL

