"""
Agent Context

Bundles all dependencies needed for agent execution.
Prevents raw dict passing and provides clean dependency injection.
"""

from dataclasses import dataclass
from typing import Callable, Any
import logging


@dataclass
class AgentContext:
    """
    Bundled context for agent execution.
    
    This prevents coupling the agent to generic dict shapes and provides
    clear dependency injection.
    
    Attributes:
        workflow_id: Workflow identifier
        tenant_id: Tenant identifier
        notebooklm: NotebookLM adapter instance
        canva: Canva adapter instance
        emit_event: Event emission function (async callable)
        logger: Logger instance for agent operations
    """
    workflow_id: str
    tenant_id: str
    notebooklm: Any  # NotebookLMAdapter
    canva: Any  # CanvaAdapter
    emit_event: Callable  # async (event_name, message, progress_pct, metadata) -> None
    logger: logging.Logger
