# Canva Integration Design

## Overview
**Goal**: Implement a real adapter to create designs via Canva Connect API.
**Scope**: Create a Presentation, add text/slides, return URLs.
**Status**: **Implemented (Phase 1)**

## Architecture
*   **Module**: `src.adapters.canva_adapter.CanvaAdapter`
*   **Interface**:
    ```python
    class CanvaAdapter:
        def __init__(self, ..., mock_mode: bool = False): ...
        
        async def create_presentation(self, title: str, template_id: str = None) -> Design:
            """
            Creates a new design.
            Returns: Design object with design_id, title, urls.
            Throws: AuthenticationError if tokens are missing/invalid in Real Mode.
            """
            ...
    ```

## Integration Details
### 1. API Interaction
*   **Authentication**: OAuth 2.0 (Access/Refresh Tokens).
*   **Management**:
    *   `src/setup_db.py` seeds a test connection.
    *   Adapter handles token refresh automatically in real mode.
*   **Endpoints Used**:
    *   `POST /v1/designs`: Create design.
    *   `POST /v1/designs/{id}/pages`: Add page (if supported).

### 2. Implementation Strategy
*   **Handler Approach**: `src/workflows/handlers.py` orchestrates the logic.
*   **Capabilities**:
    *   `create_presentation(title)`: Creates design.
    *   `add_text_block(design_id, text, ...)`: Adds Title, Sub-headings, Bullets.
*   **Strict Real Mode** (Default):
    *   Requires valid `access_token` or `refresh_token` in DB.
    *   If credentials missing: Raises `AuthenticationError`.
    *   **No Auto-Mocking**: Does not fall back to mocks if auth fails.
*   **Mock Mode (Opt-in)**:
    *   Enabled via `CANVA_MOCK_MODE=true` or `settings.canva.mock_mode = True`.
    *   Returns deterministic 'DAF_mock_...' IDs for testing.
    *   Used strictly for CI/Integration tests.

## Error Handling
*   **User Facing**: `AuthenticationError` -> "Please connect Canva account".
*   **System**: `TokenRefreshError` -> triggers workflow failure, asking user to re-login.
*   **Persistence**: Saves `design_id` and resolvable `edit_url` to workflow artifacts.
