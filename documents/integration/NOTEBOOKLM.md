# NotebookLM Integration Design

## Overview
**Goal**: Implement a real adapter to interact with NotebookLM API.
**Scope**: Fetch content summary/key points from a specific source.
**Status**: **In Progress (Adapter Shell Implemented)**

## Architecture
*   **Module**: `src.adapters.notebooklm_adapter.NotebookLMAdapter`
*   **Interface**:
    ```python
    class NotebookLMAdapter:
        def __init__(self, api_key: str, ..., mock_mode: bool = False): ...
        
        async def send_message(self, notebook_id: str, content: str) -> Message:
            """
            Sends a query to a NotebookLM notebook.
            Returns: Message object with content (simulated or real).
            Throws: AuthenticationError if API key missing in Real Mode.
            """
            ...
    ```

## Integration Details
### 1. API Interaction
*   **Endpoint**: `POST /v1/notebooks/{notebookId}/messages` (Using hypothetical/standard chat-like endpoint for now, to be refined in Verification).
*   **Auth**: API Key (Google Cloud style).
    *   Env Var: `NOTEBOOKLM_API_KEY`
*   **Payload**: `{"content": "..."}`

### 2. Real vs Mock Mode
*   **Strict Real Mode** (Default):
    *   The adapter attempts to contact the real API using `aiohttp` or `httpx`.
    *   **Failure Strategy**: If the Real API is unreachable or keys are invalid, the adapter RAISES an exception (`AuthenticationError`). It does NOT silently fall back to mock data.
*   **Mock Mode (Opt-in)**:
    *   Enabled via `NOTEBOOKLM_MOCK_MODE=true` or `settings.notebooklm.mock_mode = True`.
    *   Returns deterministic summary data ("Quantum Physics" example).
    *   Used strictly for CI/Tests.

### 3. Data Transformation
*   Raw API response -> `Message` model.
*   Extracted entities/summary passed to Canva Adapter.

## Error Handling
*   `401 Unauthorized`: Raise `AuthenticationError`.
*   `404 Notebook Not Found`: Raise `ResourceNotFoundError` (to be implemented).
*   `5xx`: Retry logic (to be refined).
