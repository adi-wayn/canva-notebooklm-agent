"""Pydantic schemas for workflow API (mirrors T2.4 Workflow model exactly)."""
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class WorkflowErrorSchema(BaseModel):
    """Error details for a failed workflow."""
    type: str  # TRANSIENT, PERMANENT, USER
    message: str
    retryable: bool


class WorkflowArtifactSchema(BaseModel):
    """Artifact produced during workflow execution."""
    name: str
    content_type: str
    url: Optional[str] = None
    data: Optional[str] = None
    created_at: Optional[datetime] = None


class WorkflowSchema(BaseModel):
    """Complete workflow state (matches T2.4 Workflow model)."""
    id: str
    tenant_id: str
    user_id: str
    status: str  # SUBMITTED, QUEUED, PROCESSING, COMPLETED, FAILED
    step: Optional[str] = None
    progress_pct: int = 0
    artifacts: List[WorkflowArtifactSchema] = Field(default_factory=list)
    error: Optional[WorkflowErrorSchema] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    request_id: Optional[str] = None

    class Config:
        from_attributes = True  # Allow conversion from WorkflowEngine's Workflow dataclass


class CreateWorkflowRequest(BaseModel):
    """Request body for creating a new workflow."""
    user_id: str
    tenant_id: str
    config: dict = Field(default_factory=dict)  # Opaque config passed to decision_engine


class RetryWorkflowRequest(BaseModel):
    """Request body for retrying a workflow (empty for now)."""
    pass


class WorkflowListResponse(BaseModel):
    """Response for listing workflows."""
    workflows: List[WorkflowSchema] = Field(default_factory=list)
    count: int = 0
