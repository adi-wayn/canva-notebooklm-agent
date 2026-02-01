import logging
from typing import Dict, Any
from src.orchestration.workflow_engine import WorkflowError, ErrorType

logger = logging.getLogger(__name__)

async def handle_presentation_workflow(
    workflow_id: str,
    tenant_id: str,
    payload: Dict[str, Any],
    adapters: Dict[str, Any],
    storage: Any
) -> Dict[str, Any]:
    """
    Handle the 'generate_presentation_from_notebooklm' workflow.
    
    Flow:
    1. Validate inputs.
    2. Query NotebookLM for summary.
    3. Create Canva presentation.
    4. Return artifact metadata.
    """
    notebooklm = adapters.get("notebooklm")
    canva = adapters.get("canva")
    
    if not notebooklm or not canva:
        raise WorkflowError(
            ErrorType.SYSTEM, 
            "Adapters not initialized", 
            retryable=False
        )

    # 1. Validation
    prompt = payload.get("prompt")
    source_id = payload.get("source_id") # Optional: might come from prompt analysis or direct input
    
    logger.info(f"[{workflow_id}] Starting presentation generation: {prompt}")

    # 2. NotebookLM (Real)
    try:
        # In a real scenario, we might first search for a source or use a provided one.
        # For this canonical workflow, if source_id is missing, we might search or fail.
        # Let's assume we use a default or search.
        # For now, we'll ask NotebookLM to specific task based on prompt.
        
        # If no source_id provided, we might fail or use a default 'demo' source if configured (but we want real).
        # We will assume the user provides a source_id OR we query the generic 'notebook'.
        # Let's assume we query a specific notebook or create one.
        # Simplified: Send message to a "default" notebook if configured, or fail if no context.
        pass 
        # TODO: Implement actual NotebookLM call when adapter is ready.
        # summary_data = await notebooklm.query_source(...)
    except Exception as e:
         raise WorkflowError(ErrorType.DEPENDENCY, f"NotebookLM Error: {e}", retryable=True)

    # 3. Canva (Real)
    try:
        # Create Design
        design = await canva.create_presentation(title=f"Presentation: {prompt}")
        
        # Add slide (Text)
        # await canva.add_text_block(design.design_id, text=prompt, ...)
        
        logger.info(f"[{workflow_id}] Created Canva design: {design.design_id}")
        
        return {
            "canva_design_id": design.design_id,
            "canva_edit_url": f"https://www.canva.com/design/{design.design_id}/edit", # Real URL pattern
            "canva_view_url": design.thumbnail_url
        }

    except Exception as e:
        # Classify Canva errors
        # If auth error, raise USER error
        if "Authentication failed" in str(e):
             raise WorkflowError(ErrorType.USER, "Please connect Canva account", retryable=False)
        raise WorkflowError(ErrorType.DEPENDENCY, f"Canva Error: {e}", retryable=True)


HANDLERS = {
    "generate_presentation_from_notebooklm": handle_presentation_workflow
}
