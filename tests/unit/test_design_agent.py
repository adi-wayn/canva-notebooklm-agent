"""
Unit tests for DesignAgent.

Tests the core orchestration logic of the AI Agent.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.agent.design_agent import DesignAgent
from src.agent.context import AgentContext
from src.orchestration.workflow_engine import WorkflowException, ErrorType


@pytest.fixture
def mock_notebooklm():
    """Mock NotebookLM adapter."""
    import json
    adapter = AsyncMock()
    # NotebookLM returns JSON string, not dict
    adapter.generate_presentation_structure = AsyncMock(return_value=json.dumps({
        "title": "Test Presentation",
        "sections": [
            {
                "heading": "Introduction",
                "content": "Test content",
                "bullets": ["Point 1", "Point 2"]
            }
        ]
    }))
    return adapter


@pytest.fixture
def mock_canva():
    """Mock Canva adapter."""
    adapter = AsyncMock()
    adapter.create_design = AsyncMock(return_value={
        "design": {
            "id": "DAF_test_design_id",
            "urls": {
                "edit_url": "https://canva.com/design/DAF_test/edit"
            }
        }
    })
    adapter.add_page = AsyncMock(return_value={"page": {"id": "page_1"}})
    adapter.add_text = AsyncMock(return_value={"element": {"id": "text_1"}})
    return adapter


@pytest.fixture
def mock_emit_event():
    """Mock event emission function."""
    return AsyncMock()


@pytest.fixture
def mock_logger():
    """Mock logger."""
    return MagicMock()


@pytest.fixture
def agent_context(mock_notebooklm, mock_canva, mock_emit_event, mock_logger):
    """Create AgentContext with mocked dependencies."""
    return AgentContext(
        workflow_id="test_workflow_123",
        tenant_id="tenant_1",
        notebooklm=mock_notebooklm,
        canva=mock_canva,
        emit_event=mock_emit_event,
        logger=mock_logger
    )


@pytest.fixture
def mock_workflow():
    """Mock workflow object."""
    workflow = MagicMock()
    workflow.id = "test_workflow_123"
    workflow.tenant_id = "tenant_1"
    return workflow


@pytest.fixture
def mock_engine():
    """Mock WorkflowEngine."""
    engine = MagicMock()
    engine.add_artifact = AsyncMock()
    return engine


class TestDesignAgentInitialization:
    """Test DesignAgent initialization."""
    
    def test_init_with_context(self, agent_context):
        """Test agent initializes correctly with context."""
        agent = DesignAgent(agent_context)
        
        assert agent.workflow_id == "test_workflow_123"
        assert agent.tenant_id == "tenant_1"
        assert agent.notebooklm is not None
        assert agent.canva is not None
        assert agent.emit_event is not None
        assert agent.logger is not None


class TestDesignAgentEventEmission:
    """Test that agent emits all expected semantic events."""
    
    @pytest.mark.asyncio
    async def test_emits_all_events_in_order(
        self, agent_context, mock_workflow, mock_engine, mock_emit_event
    ):
        """Test that agent emits all semantic events in correct order."""
        agent = DesignAgent(agent_context)
        
        await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        # Verify all events were emitted
        event_calls = mock_emit_event.call_args_list
        event_names = [call.kwargs["event_name"] for call in event_calls]
        
        expected_events = [
            "agent_thinking",
            "notebooklm_extraction_started",
            "notebooklm_extraction_completed",
            "design_plan_created",
            "canva_design_started",
            "canva_design_created"
        ]
        
        assert event_names == expected_events
    
    @pytest.mark.asyncio
    async def test_agent_thinking_event(
        self, agent_context, mock_workflow, mock_engine, mock_emit_event
    ):
        """Test agent_thinking event is emitted with correct metadata."""
        agent = DesignAgent(agent_context)
        
        await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        # Find agent_thinking event
        thinking_call = next(
            call for call in mock_emit_event.call_args_list
            if call.kwargs["event_name"] == "agent_thinking"
        )
        
        assert thinking_call.kwargs["message"] == "Analyzing your request..."
        assert thinking_call.kwargs["progress_pct"] == 5
        assert "prompt_length" in thinking_call.kwargs["metadata"]
    
    @pytest.mark.asyncio
    async def test_notebooklm_extraction_completed_event(
        self, agent_context, mock_workflow, mock_engine, mock_emit_event
    ):
        """Test notebooklm_extraction_completed event includes summary."""
        agent = DesignAgent(agent_context)
        
        await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        # Find extraction completed event
        extraction_call = next(
            call for call in mock_emit_event.call_args_list
            if call.kwargs["event_name"] == "notebooklm_extraction_completed"
        )
        
        assert extraction_call.kwargs["progress_pct"] == 30
        metadata = extraction_call.kwargs["metadata"]
        assert "title" in metadata
        assert "sections_count" in metadata
        assert "first_headings" in metadata
    
    @pytest.mark.asyncio
    async def test_design_plan_created_event(
        self, agent_context, mock_workflow, mock_engine, mock_emit_event
    ):
        """Test design_plan_created event includes slide count."""
        agent = DesignAgent(agent_context)
        
        await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        # Find design plan event
        plan_call = next(
            call for call in mock_emit_event.call_args_list
            if call.kwargs["event_name"] == "design_plan_created"
        )
        
        assert plan_call.kwargs["progress_pct"] == 50
        metadata = plan_call.kwargs["metadata"]
        assert "slide_count" in metadata
        assert "theme" in metadata


class TestDesignAgentCanonicalOutput:
    """Test canonical output validation and artifact saving."""
    
    @pytest.mark.asyncio
    async def test_validates_canonical_output(
        self, agent_context, mock_workflow, mock_engine
    ):
        """Test that agent validates canonical output from NotebookLM."""
        agent = DesignAgent(agent_context)
        
        # Execute should not raise if validation passes
        result = await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        assert result is not None
        assert "canva_design_id" in result
    
    @pytest.mark.asyncio
    async def test_saves_canonical_artifact(
        self, agent_context, mock_workflow, mock_engine
    ):
        """Test that agent saves canonical output as artifact."""
        agent = DesignAgent(agent_context)
        
        await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        # Verify artifact was saved
        mock_engine.add_artifact.assert_called_once()
        call_kwargs = mock_engine.add_artifact.call_args.kwargs
        
        assert call_kwargs["workflow"] == mock_workflow
        assert "NotebookLM Extraction" in call_kwargs["name"]
        assert call_kwargs["content_type"] == "application/json"
        assert "data" in call_kwargs
    
    @pytest.mark.asyncio
    async def test_raises_on_invalid_canonical_output(
        self, agent_context, mock_workflow, mock_engine, mock_notebooklm
    ):
        """Test that agent raises WorkflowException on invalid canonical output."""
        import json
        # Mock NotebookLM to return invalid output (missing title)
        mock_notebooklm.generate_presentation_structure = AsyncMock(return_value=json.dumps({
            "sections": [{"heading": "H1", "content": "C1"}]
            # Missing title - should fail validation
        }))
        
        agent = DesignAgent(agent_context)
        
        with pytest.raises(WorkflowException) as exc_info:
            await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        assert exc_info.value.type == ErrorType.EXTERNAL
        assert "validation" in str(exc_info.value).lower()


class TestDesignAgentCanvaIntegration:
    """Test Canva design creation and content addition."""
    
    @pytest.mark.asyncio
    async def test_creates_canva_design(
        self, agent_context, mock_workflow, mock_engine, mock_canva
    ):
        """Test that agent creates Canva design."""
        agent = DesignAgent(agent_context)
        
        result = await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        # Verify Canva design was created
        mock_canva.create_design.assert_called_once()
        assert result["canva_design_id"] == "DAF_test_design_id"
        assert "canva_edit_url" in result
    
    @pytest.mark.asyncio
    async def test_adds_content_to_canva(
        self, agent_context, mock_workflow, mock_engine, mock_canva
    ):
        """Test that agent adds content to Canva design."""
        agent = DesignAgent(agent_context)
        
        await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        # Verify pages and text were added
        assert mock_canva.add_page.called
        assert mock_canva.add_text.called
    
    @pytest.mark.asyncio
    async def test_handles_canva_errors(
        self, agent_context, mock_workflow, mock_engine, mock_canva
    ):
        """Test that agent handles Canva errors gracefully."""
        # Mock Canva to raise error
        mock_canva.create_design = AsyncMock(
            side_effect=Exception("Canva API error")
        )
        
        agent = DesignAgent(agent_context)
        
        with pytest.raises(WorkflowException) as exc_info:
            await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        assert exc_info.value.type == ErrorType.EXTERNAL


class TestDesignAgentErrorHandling:
    """Test error handling and validation."""
    
    @pytest.mark.asyncio
    async def test_raises_on_empty_prompt(
        self, agent_context, mock_workflow, mock_engine
    ):
        """Test that agent raises error on empty prompt."""
        agent = DesignAgent(agent_context)
        
        with pytest.raises(WorkflowException) as exc_info:
            await agent.execute("", mock_workflow, mock_engine)
        
        assert exc_info.value.type == ErrorType.USER
    
    @pytest.mark.asyncio
    async def test_raises_on_notebooklm_error(
        self, agent_context, mock_workflow, mock_engine, mock_notebooklm
    ):
        """Test that agent handles NotebookLM errors."""
        # Mock NotebookLM to raise error
        mock_notebooklm.generate_presentation_structure = AsyncMock(
            side_effect=Exception("NotebookLM API error")
        )
        
        agent = DesignAgent(agent_context)
        
        with pytest.raises(WorkflowException) as exc_info:
            await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        assert exc_info.value.type == ErrorType.EXTERNAL


class TestDesignAgentReturnValue:
    """Test agent return value structure."""
    
    @pytest.mark.asyncio
    async def test_returns_complete_result(
        self, agent_context, mock_workflow, mock_engine
    ):
        """Test that agent returns complete result with all required fields."""
        agent = DesignAgent(agent_context)
        
        result = await agent.execute("Test prompt", mock_workflow, mock_engine)
        
        # Verify result structure
        assert "canva_design_id" in result
        assert "canva_edit_url" in result
        assert result["canva_design_id"].startswith("DAF_")
        assert "canva.com" in result["canva_edit_url"]
