# Canonical Workflow: Content to Canva Presentation

## Overview
**Name**: `generate_presentation_from_notebooklm`
**Goal**: Create a Canva presentation based on insights extracted from a NotebookLM source.
**Scope**: End-to-End integration using real adapters (NotebookLM -> Canva).

## 1. Input Interface
The user makes a `POST /api/v1/workflows` request with:
```json
{
  "prompt": "Create a 5-slide pitch deck about this research",
  "notebooklm_source_id": "<valid_source_id>", 
  "canva_design_type": "presentation"
}
```
*Assumption*: The user must provide a valid `notebooklm_source_id` accessible by the configured API key.

## 2. Process Flow

### Step A: NotebookLM Analysis
**Action**: Query NotebookLM to summarize/structure the content.
*   **Adapter Method**: `NotebookLMAdapter.query_source(source_id, query)`
*   **Query**: "Summarize the key points of this document into a structured outline for a presentation."
*   **Output (Internal)**:
    ```json
    {
      "title": "Main Title",
      "sections": [
        {"heading": "Key Point 1", "bullets": ["Detail A", "Detail B"]},
        ...
      ]
    }
    ```

### Step B: Transformation (Deterministic)
**Action**: Map analysis output to a visual design plan.
*   **Logic**:
    *   Create 1 Title Slide (`title`, `subtitle`).
    *   Create 1 Content Slide per Section (Max 5).
    *   Map `heading` to Title Text.
    *   Map `bullets` to Body Text.
*   **Output (Internal)**: `DesignPlan` object.

### Step C: Canva Design Creation
**Action**: Use Canva Connect API to generate unique artifacts.
*   **Adapter Method**: `CanvaAdapter.create_presentation(title=...)`
*   **Operations**:
    1.  `create_presentation(title=...)` -> Returns `design_id`.
    2.  `add_text_block(text={title}, font_size=48)` -> Main Title.
    3.  Iterate sections:
        *   `add_text_block(text={heading}, font_size=32)` -> Section Header.
        *   `add_text_block(text={bullet}, font_size=24)` -> Bullet Point.
*   **Output**:
    ```json
    {
      "canva_design_id": "DAxxxx",
      "canva_edit_url": "https://www.canva.com/design/DAxxxx/edit",
      "canva_view_url": "https://..."
    }
    ```

## 3. Terminal State
*   **Workflow Status**: `COMPLETED`
*   **Artifacts**:
    1.  `NotebookLM Summary` (Text/JSON)
    2.  `Canva Presentation` (Link)

## 4. Error Handling
*   **NotebookLM Failure** (e.g., Invalid Source): Status `FAILED`, Error `NotebookLMError`.
*   **Canva Failure** (e.g., Token Expired): Status `FAILED`, Error `CanvaAuthError`.

## 5. Verification Steps
1.  **Seed**: Ensure DB has valid user with linked Canva token (handled via auth mock or real flow).
2.  **Execute**: Submit request.
3.  **Verify**: Click the returned `edit_url`. It must open a real Canva design.
