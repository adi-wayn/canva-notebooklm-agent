# Workflow Handler Architecture

## Motivation
The original `WorkflowWorker` Monolith was becoming hard to maintain as we added more workflow types. To support diverse workflows (Canva, NotebookLM, etc.) with different data flows and external dependencies, we decoupled the **execution logic** from the **worker infrastructure**.

## Architecture
### 1. The Worker (`src/workers/workflow_worker.py`)
*   **Role**: Infrastructure Shell.
*   **Responsibilities**:
    *   Polling Redis Stream for tasks.
    *   Managing Workflow lifecycle (Submitted -> Processing -> Terminated).
    *   State Persistence (DB updates).
    *   Event Emission (SSE).
    *   Error Classification (Retry vs Fatal).
    *   **Routing**: Dispatches the payload to a specific Handler.

### 2. The Handlers (`src/workflows/handlers.py`)
*   **Role**: Business Logic.
*   **Responsibilities**:
    *   Receives `payload`, `adapters`, `tenant_id`.
    *   Orchestrates the sequence of steps (e.g., Call NotebookLM -> Transform -> Call Canva).
    *   Returns a dictionary of result artifacts.
*   **Contract**:
    ```python
    async def specific_workflow_handler(
        workflow_id: str,
        tenant_id: str,
        payload: Dict[str, Any],
        adapters: Dict[str, Any],
        storage: Any
    ) -> Dict[str, Any]:
    ```

### 3. Registry
*   `HANDLERS`: A dictionary mapping `workflow_type` string to the handler function.
*   The Worker looks up the handler using `workflow.input_data.get("type")`.

### 4. Adapter Injection
*   The Worker initializes Adapters (Canva, NotebookLM) based on configuration (and checks for Mock Mode).
*   It passes these initialized, ready-to-use adapters to the handler.
*   This keeps the Handler clean of initialization/config logic.

## Benefits
*   **Testability**: Handlers are pure functions (mostly) that take mocks easily.
*   **Separation of Concerns**: Worker deals with plumbing; Handlers deal with product logic.
*   **Extensibility**: Adding a new workflow just means writing a function and adding it to `HANDLERS`.
