"""In-memory workflow store (MVP, T2.6 will add persistence)."""
from typing import Optional, Dict
from src.orchestration.workflow_engine import Workflow


class WorkflowStore:
    """Thread-safe in-memory storage for workflows."""

    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}

    def create(self, workflow: Workflow) -> Workflow:
        """Store a new workflow."""
        self._workflows[workflow.id] = workflow
        return workflow

    def get(self, workflow_id: str) -> Optional[Workflow]:
        """Retrieve a workflow by ID."""
        return self._workflows.get(workflow_id)

    def update(self, workflow: Workflow) -> None:
        """Update an existing workflow."""
        self._workflows[workflow.id] = workflow

    def list_by_tenant(self, tenant_id: str) -> list[Workflow]:
        """List all workflows for a tenant."""
        return [w for w in self._workflows.values() if w.tenant_id == tenant_id]

    def exists(self, workflow_id: str) -> bool:
        """Check if workflow exists."""
        return workflow_id in self._workflows


# Global singleton store
store = WorkflowStore()
