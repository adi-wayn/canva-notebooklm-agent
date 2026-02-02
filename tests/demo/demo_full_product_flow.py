import asyncio
import sys
import os
import json
from typing import Dict, Any, List
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.agent.design_agent import DesignAgent
from src.agent.schemas import DesignPlan, SectionContent
from src.orchestration.workflow_engine import Workflow

# --- Mocks ---

class MockNotebookLMAdapter:
    async def send_message(self, notebook_id: str, content: str) -> Any:
        print(f"  [NotebookLM] Parsing request: {content[:50]}...")
        # If we have a pre-loaded mock response (for iteration/explain tests), return it
        if hasattr(self, 'mock_response') and self.mock_response:
             # Wrap in object if it's a raw string, to match Agent expectation of message.content
             if isinstance(self.mock_response, str):
                 return MagicMock(content=self.mock_response)
             return self.mock_response
             
        # Return content-rich JSON string simulating the enhanced prompt output
        json_content = json.dumps({
            "title": "Quantum Computing: A New Era",
            "subtitle": "Harnessing the laws of physics",
            "sections": [
                {
                    "heading": "Superposition",
                    "content": "Quantum superposition allows particles to exist in multiple states at once.",
                    "bullets": ["Qubits can be 0 and 1", "Basis for parallelism"],
                    "visual_hint": "chart"
                },
                {
                    "heading": "Entanglement",
                    "content": "Entangled particles share a state regardless of distance.",
                    "bullets": ["Spooky action at a distance", "Key for teleportation"],
                    "visual_hint": "image"
                }
            ],
            "key_insights": ["Exponential speedup", "New algorithms"],
            "suggested_theme": "professional"
        })
        return MagicMock(content=json_content)

    async def add_source(self, *args, **kwargs): pass
    async def configure_session(self, *args, **kwargs): pass

class MockCanvaAdapter:
    async def create_presentation(self, title, **kwargs):
        print(f"  [Canva] Creating presentation: '{title}'")
        return MagicMock(design_id="DAF_mock123", thumbnail_url="http://canva.com/thumb.png")

    async def add_text_block(self, design_id, text, **kwargs):
        snippet = text[:30] + "..." if len(text) > 30 else text
        print(f"  [Canva] Adding text to {design_id}: '{snippet.replace(chr(10), ' ')}'")
        return {"id": "elt_123"}

    async def add_page(self, **kwargs):
        print("  [Canva] Adding new page")

class MockEngine:
    def __init__(self):
        self.artifacts = {}
        self.workflows = []

    async def add_artifact(self, workflow, name, content_type, data, metadata=None):
        print(f"  [Engine] Saving artifact: '{name}' ({content_type})")
        if metadata:
            print(f"  [Engine] Metadata: {metadata}")
        
        # Store artifact in the workflow object so it can be retrieved
        if not hasattr(workflow, "artifacts"):
            workflow.artifacts = []
            
        workflow.artifacts.append({
            "name": name,
            "data": data,
            "metadata": metadata
        })
        if name == "Trace Map (v1.0)":
            print("  [Engine] Trace Map stored with " + str(metadata.get("slides_traced")) + " slides")

    def get_workflow(self, workflow_id):
        # Return a mock workflow object that has a to_dict method
        # We need to find the workflow matching ID, or just return the last one for demo simplicity
        # For the demo, we'll store created workflows in a list
        for wf in self.workflows:
             if wf.id == workflow_id:
                 return wf
        return None

class MockWorkflow:
    def __init__(self, id, tenant_id, user_id, status, step, progress_pct, input_data):
        self.id = id
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.status = status
        self.step = step
        self.progress_pct = progress_pct
        self.input_data = input_data
        self.artifacts = [] # Store artifacts here
        
    def to_dict(self):
        return {
            "id": self.id,
            "artifacts": self.artifacts
        }

async def run_demo():
    print("=== FULL AGENT PRODUCT FLOW DEMO (REAL LOGIC STRUCTURE) ===\n")

    # 1. Setup
    print("1. SETUP: Initializing Agent with Mocks")
    # Create Real-ish mocks that behave like the actual dependencies
    notebooklm = MockNotebookLMAdapter()
    canva = MockCanvaAdapter()
    engine = MockEngine()
    engine.workflows = [] # Store workflows for retrieval
    
    # Mock context dependencies
    import logging
    logger = logging.getLogger("DesignAgent")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('  [Log] %(message)s'))
    logger.addHandler(handler)
    
    async def mock_emit(event_name, message, progress_pct=0, metadata=None):
        print(f"  [Event] {event_name} ({progress_pct}%): {message}")

    # Use relative import for AgentContext if needed, mimicking the import above
    # But since we appended sys.path, we can import from src.agent.context
    from src.agent.context import AgentContext

    context = AgentContext(
        workflow_id="wf_1",
        tenant_id="tenant_1",
        notebooklm=notebooklm,
        canva=canva,
        emit_event=mock_emit,
        logger=logger
    )
    
    agent = DesignAgent(context)
    from src.orchestration.workflow_engine import Workflow, WorkflowStatus
    import uuid
    
    # Create a workflow object that can store artifacts
    workflow = MockWorkflow(
        id="wf_1",
        tenant_id="tenant_1", 
        user_id="user_1",
        status="PROCESSING",
        step="init",
        progress_pct=0,
        input_data={}
    )
    engine.workflows.append(workflow) # Register it so get_workflow finds it
    
    # 2. Golden Path
    print("\n2. GOLDEN PATH: Prompt -> Canva + Assistant Message")
    print("   User: 'Create a presentation about Quantum Computing'")
    
    result = await agent.execute(
        prompt="Create a presentation about Quantum Computing",
        workflow=workflow,
        engine=engine
    )
    
    print("\n   [Assistant Final Response Data]")
    print(f"   Canva Link: {result['canva_edit_url']}")
    print(f"   Summary: Created {result['sections_completed']} sections")
    print(f"   Traceability Summary: {result['traceability_summary']}")
    print(f"   Artifacts: {list(result['artifacts'].keys())}")
    
    # 3. Iteration
    print("\n3. ITERATION: User requests a change")
    print("   User: 'Change the first section heading to 'Quantum Superposition Deep Dive''")
    
    # Pre-load the Mock NotebookLM with the Expected JSON Response
    # The real agent will call notebooklm.send_message(prompt)
    # This mock needs to return a valid JSON string that looks like a DesignPlan
    notebooklm.mock_response = json.dumps({
        "theme": "professional",
        "slides": [
            {
               "heading": "Quantum Superposition Deep Dive", # <--- The change
               "content": "Quantum superposition allows particles to exist in multiple states simultaneously.",
               "bullets": ["Qubits can be 0 and 1", "Basis of quantum speedup"],
               "visual_hint": "text" 
            },
            {
               "heading": "Entanglement",
               "content": "Entangled particles share a state regardless of distance.",
               "bullets": ["Spooky action at a distance", "Correlation verified"],
               "visual_hint": "text" 
            }
        ]
    })
    
    modification_prompt = "Change the first section heading to 'Quantum Superposition Deep Dive'"
    
    # In the REAL logic, we call agent.edit_design, passing the previous workflow ID.
    # The agent will look up the workflow in the engine, get the artifacts, and reason.
    
    result_iter = await agent.edit_design(
        modification_prompt=modification_prompt,
        previous_workflow_id="wf_1",
        workflow=workflow, # In reality this would be a NEW workflow object, but for demo we reuse context
        engine=engine
    )
    
    print("   [Agent] Reasoning about modification request...")
    print(f"   [Agent] Updated Plan: {result_iter.get('modification_summary')}")
    print("   [Agent] Re-executing Canva plan (Traceable)...")
    
    # Retrieve artifacts from the result of edit_design
    # The agent logic already saved them to the engine, so we can check the result dict
    # or the result object itself if it returns one.
    # Our updated edit_design returns a dict with keys like 'canva_design_id'
    
    # For verification, we can assume the agent did its job and logged the output
    print(f"   [Iteration Result] Agent returned Canva ID: {result_iter.get('canva_design_id')}")
    
    # 4. Explainability
    print("\n4. EXPLAINABILITY: User asks 'Why is slide 2 content like that?'")
    print("   [Agent] looking up Trace Map for slide 2...")
    
    # Pre-load response for Explainability
    notebooklm.mock_response = "Slide 2 covers 'Entanglement' because it is a key concept in quantum mechanics. It comes from section 2 of the source document."
    
    result_explain = await agent.explain_design(
        query="Why is slide 2 content like that?",
        previous_workflow_id="wf_1",
        workflow=workflow,
        engine=engine
    )

    print("   [Agent Answer Grounded in Artifacts]:")
    print(f"   '{result_explain.get('explanation')}'")

    print("\n=== DEMO COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(run_demo())
