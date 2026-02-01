# NotebookLM Integration Design (via Gemini)

## Overview
**Goal**: Implement a real adapter to interact with "NotebookLM-like" capabilities.
**Reality**: As of 2025, there is no public consumer API for NotebookLM.
**Solution**: We use the **Google Gemini API** (`google-generativeai` SDK) with **Gemini 1.5 Flash** to replicate NotebookLM's core functionality (RAG/Summarization).

**Status**: **Implemented (Phase 1)**

## Architecture
*   **Module**: `src.adapters.notebooklm_adapter.NotebookLMAdapter`
*   **Backend**: Google Gemini 2.0 Flash Lite (`gemini-2.0-flash-lite`).
*   **Interface**:
    ```python
    class NotebookLMAdapter:
        def __init__(self, api_key: str, ..., mock_mode: bool = False): ...
        
        async def send_message(self, notebook_id: str, content: str) -> Message:
            """
            Sends a prompt to Gemini 1.5 Flash.
            Returns: Message object with the model's response.
            Throws: AuthenticationError if API key is invalid.
            """
            ...
    ```

## Integration Details
### 1. API Interaction
*   **SDK**: `google-generativeai`
*   **Auth**: API Key from [Google AI Studio](https://aistudio.google.com/).
    *   Env Var: `NOTEBOOKLM_API_KEY` (Maps to Gemini API Key).
*   **Model**: Robust Fallback Strategy.
    *   Primary: `gemini-2.0-flash-lite` (Free/Fast).
    *   Fallbacks: `gemini-2.0-flash` -> `gemini-2.5-flash` -> `gemini-1.5-flash` -> `gemini-2.5-pro`.
    *   **Reasoning**: Automatically recovers from `429 Rate Limit` or `404 Model Not Found` errors common in the Free Tier.

### 2. Real vs Mock Mode
*   **Strict Real Mode** (Default):
    *   Requires valid `NOTEBOOKLM_API_KEY`.
    *   Connects to Google's servers.
    *   **Failure Strategy**: Raises `AuthenticationError` or `NotebookLMAPIError` on failure. No silent fallbacks.
*   **Mock Mode (Opt-in)**:
    *   Enabled via `NOTEBOOKLM_MOCK_MODE=true`.
    *   Returns deterministic "Quantum Physics" summary.

### 3. Payload Structure
*   **Request**:
    *   `content`: The prompt or context data.
*   **Prompt Engineering**:
    *   The adapter wraps the user content in a system instruction: *"You are NotebookLM... Output strictly valid JSON..."*.
*   **Response**:
    *   Expects a JSON string matching the Canonical Workflow schema.

## Verification
1.  **Get Key**: Obtain API Key from Google AI Studio.
2.  **Configure**: Set `NOTEBOOKLM_API_KEY` in `.env`.
3.  **Run**: `python3 scripts/verify_notebooklm_real.py`
4.  **Expect**: Valid JSON output describing Quantum Entanglement.

## Error Handling
*   `401 (Auth)`: "NotebookLM/Gemini API Key is missing/invalid".
*   `429 (Rate Limit)`: "Gemini Rate Limit Exceeded".
*   `500 (Other)`: "Gemini API Error".
