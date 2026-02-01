import logging
from typing import Dict, Any
from src.orchestration.workflow_engine import WorkflowError, ErrorType, WorkflowException

logger = logging.getLogger(__name__)

async def handle_presentation_workflow(
    workflow_id: str,
    tenant_id: str,
    payload: Dict[str, Any],
    adapters: Dict[str, Any],
    storage: Any,
    emit_event_fn: Any,  # Event emission function
    workflow: Any,  # Workflow object for artifact management
    engine: Any  # WorkflowEngine instance
) -> Dict[str, Any]:
    """
    Thin wrapper that delegates to DesignAgent.
    
    This handler contains NO business logic - only validation and agent instantiation.
    All orchestration logic is owned by the DesignAgent.
    
    Args:
        workflow_id: Workflow identifier
        tenant_id: Tenant identifier
        payload: Workflow input data
        adapters: Adapter instances (notebooklm, canva)
        storage: Storage instance (unused)
        emit_event_fn: Event emission function
        workflow: Workflow object for artifact management
        engine: WorkflowEngine instance
        
    Returns:
        Dict with canva_design_id, canva_edit_url, etc.
        
    Raises:
        WorkflowException: On validation or execution errors
    """
    from src.agent.design_agent import DesignAgent
    from src.agent.context import AgentContext
    
    # Validate inputs
    prompt = payload.get("prompt")
    if not prompt:
        raise WorkflowException(ErrorType.USER, "Missing prompt", retryable=False)
    
    # Validate adapters
    if not adapters.get("notebooklm"):
        raise WorkflowException(
            ErrorType.TRANSIENT,
            "NotebookLM adapter not initialized",
            retryable=True
        )
    if not adapters.get("canva"):
        raise WorkflowException(
            ErrorType.USER,
            "Please connect Canva account to proceed",
            retryable=False
        )
    
    # Create AgentContext (no raw dict passing)
    context = AgentContext(
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        notebooklm=adapters["notebooklm"],
        canva=adapters["canva"],
        emit_event=emit_event_fn,
        logger=logger
    )
    
    # Instantiate and execute agent
    agent = DesignAgent(context)
    result = await agent.execute(prompt, workflow, engine)
    
    return result


HANDLERS = {
    "generate_presentation_from_notebooklm": handle_presentation_workflow
}
