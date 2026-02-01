"""
Design Agent

First-class AI Agent that orchestrates NotebookLM → Canonical Output → Canva.

This agent owns all business logic for transforming user prompts into Canva designs.
It emits semantic events at each step to make the AI's "thinking" visible to users.

Hard constraints:
- No mocks in golden path (ADAPTERS_MOCK_MODE=false)
- Canonical output saved as artifact (not in SSE payload)
- All events go through single emit_agent_event code path
"""

import json
import logging
from typing import Dict, Any
from datetime import datetime

from src.agent.context import AgentContext
from src.agent.schemas import CanonicalOutput, DesignPlan, SectionContent
from src.agent.validators import validate_canonical_output, get_canonical_summary
from src.orchestration.workflow_engine import WorkflowException, ErrorType


class DesignAgent:
    """
    AI Agent that orchestrates presentation generation from NotebookLM to Canva.
    
    Responsibilities:
    - Analyze user prompts
    - Extract structured insights from NotebookLM
    - Validate against canonical schema
    - Save canonical output as artifact
    - Build Canva-specific design plan
    - Execute Canva design creation
    - Emit semantic events at each step
    
    The agent is the ONLY owner of business logic. Handlers are thin wrappers.
    """
    
    def __init__(self, context: AgentContext):
        """
        Initialize agent with bundled context.
        
        Args:
            context: AgentContext with all dependencies
        """
        self.context = context
        self.workflow_id = context.workflow_id
        self.tenant_id = context.tenant_id
        self.notebooklm = context.notebooklm
        self.canva = context.canva
        self.emit_event = context.emit_event
        self.logger = context.logger
    
    async def execute(self, prompt: str, workflow, engine) -> Dict[str, Any]:
        """
        Main orchestration method.
        
        Flow:
        1. Analyze prompt
        2. Extract from NotebookLM
        3. Validate canonical output
        4. Save canonical output as artifact
        5. Build design plan
        6. Execute Canva creation
        
        Args:
            prompt: User's design request
            workflow: Workflow object for artifact management
            engine: WorkflowEngine instance
            
        Returns:
            Dict with canva_design_id, canva_edit_url, etc.
            
        Raises:
            WorkflowException: On validation or execution errors
        """
        self.logger.info(f"[DesignAgent] Starting execution for workflow {self.workflow_id}")
        
        # 1. Analyze prompt
        await self._analyze_prompt(prompt)
        
        # 2. Extract from NotebookLM
        canonical_output = await self._extract_structure_from_notebooklm(prompt)
        
        # 3. Validate canonical output
        if not canonical_output["validation"]["is_valid"]:
            errors = canonical_output["validation"]["errors"]
            raise WorkflowException(
                ErrorType.TRANSIENT,
                f"Invalid NotebookLM output: {'; '.join(errors)}",
                retryable=True
            )
        
        # 4. Save canonical output as artifact
        await self._save_canonical_artifact(canonical_output, workflow, engine)
        
        # 5. Build design plan
        design_plan = await self._build_design_plan(canonical_output)
        
        # 6. Execute Canva creation
        canva_result = await self._execute_canva_plan(design_plan)
        
        self.logger.info(f"[DesignAgent] Completed execution for workflow {self.workflow_id}")
        return canva_result
    
    async def _analyze_prompt(self, prompt: str):
        """
        Validate user input and emit agent_thinking event.
        
        Args:
            prompt: User's input prompt
        """
        self.logger.debug(f"[DesignAgent] Analyzing prompt: {prompt[:100]}...")
        
        await self.emit_event(
            event_name="agent_thinking",
            message="Analyzing your request...",
            progress_pct=5,
            metadata={"prompt_length": len(prompt)}
        )
    
    async def _extract_structure_from_notebooklm(self, prompt: str) -> Dict[str, Any]:
        """
        Call NotebookLM, parse response, validate against canonical schema.
        
        Emits:
            - notebooklm_extraction_started
            - notebooklm_extraction_completed
        
        Args:
            prompt: User's prompt
            
        Returns:
            Validated canonical output
            
        Raises:
            WorkflowException: On NotebookLM errors
        """
        self.logger.info(f"[DesignAgent] Extracting structure from NotebookLM")
        
        # Emit start event
        await self.emit_event(
            event_name="notebooklm_extraction_started",
            message="Extracting insights from NotebookLM...",
            progress_pct=10,
            metadata={"notebook_id": "default_notebook"}
        )
        
        try:
            # Call NotebookLM adapter
            message = await self.notebooklm.send_message(
                notebook_id="default_notebook",
                content=prompt
            )
            
            # Parse JSON from response
            content_str = message.content
            
            # Handle markdown code blocks if present
            if "```json" in content_str:
                content_str = content_str.split("```json")[1].split("```")[0].strip()
            elif "```" in content_str:
                content_str = content_str.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            raw_data = json.loads(content_str)
            
            # Add extraction metadata
            if "extraction_metadata" not in raw_data:
                raw_data["extraction_metadata"] = {}
            
            raw_data["extraction_metadata"].update({
                "notebook_id": "default_notebook",
                "query": prompt,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            })
            
            # Validate against canonical schema
            canonical_output = validate_canonical_output(raw_data)
            
            # Get summary for SSE event (NOT full canonical output)
            summary = get_canonical_summary(canonical_output)
            
            # Emit completion event with summary only
            await self.emit_event(
                event_name="notebooklm_extraction_completed",
                message=f"Extracted insights from NotebookLM",
                progress_pct=30,
                metadata=summary  # Only summary, not full canonical output
            )
            
            self.logger.info(
                f"[DesignAgent] NotebookLM extraction completed: {summary['title']}"
            )
            
            return canonical_output
            
        except json.JSONDecodeError as e:
            self.logger.error(f"[DesignAgent] Failed to parse NotebookLM JSON: {e}")
            raise WorkflowException(
                ErrorType.TRANSIENT,
                f"NotebookLM returned invalid JSON: {e}",
                retryable=True
            )
        except Exception as e:
            self.logger.error(f"[DesignAgent] NotebookLM extraction failed: {e}")
            raise WorkflowException(
                ErrorType.TRANSIENT,
                f"NotebookLM Error: {e}",
                retryable=True
            )
    
    async def _save_canonical_artifact(
        self,
        canonical_output: Dict[str, Any],
        workflow,
        engine
    ):
        """
        Save canonical output as a first-class artifact.
        
        Artifact:
            - Type: canonical_output
            - Name: NotebookLM Extraction (v1.0)
            - Content Type: application/json
            - Data: Full canonical JSON
        
        Args:
            canonical_output: Validated canonical output
            workflow: Workflow object
            engine: WorkflowEngine instance
        """
        self.logger.info(f"[DesignAgent] Saving canonical output as artifact")
        
        try:
            # Save as artifact (full JSON in DB, not in SSE)
            engine.add_artifact(
                workflow=workflow,
                name="NotebookLM Extraction (v1.0)",
                content_type="application/json",
                data=canonical_output
            )
            
            self.logger.info(f"[DesignAgent] Canonical output saved as artifact")
            
        except Exception as e:
            self.logger.error(f"[DesignAgent] Failed to save canonical artifact: {e}")
            # Non-fatal - continue execution
    
    async def _build_design_plan(self, canonical_output: Dict[str, Any]) -> DesignPlan:
        """
        Transform canonical output into Canva-specific design plan.
        
        Emits: design_plan_created
        
        Args:
            canonical_output: Validated canonical output
            
        Returns:
            DesignPlan with Canva-specific structure
        """
        self.logger.info(f"[DesignAgent] Building design plan")
        
        content = canonical_output["content"]
        
        # Extract sections
        sections = []
        for section_data in content.get("sections", []):
            sections.append(SectionContent(
                heading=section_data.get("heading", ""),
                content=section_data.get("content", ""),
                bullets=section_data.get("bullets"),
                visual_hint=section_data.get("visual_hint", "text")
            ))
        
        # Build design plan
        design_plan = DesignPlan(
            title=content.get("title", "Untitled"),
            subtitle=content.get("subtitle"),
            slide_count=len(sections) + 1,  # +1 for title slide
            theme=content.get("suggested_theme", "professional"),
            sections=sections
        )
        
        # Emit event
        await self.emit_event(
            event_name="design_plan_created",
            message=f"Created design plan with {design_plan.slide_count} slides",
            progress_pct=50,
            metadata={
                "slide_count": design_plan.slide_count,
                "theme": design_plan.theme
            }
        )
        
        self.logger.info(
            f"[DesignAgent] Design plan created: {design_plan.slide_count} slides"
        )
        
        return design_plan
    
    async def _execute_canva_plan(self, design_plan: DesignPlan) -> Dict[str, Any]:
        """
        Create Canva design and add content.
        
        Emits:
            - canva_design_started
            - canva_design_created
            - canva_content_partial_warning (if content addition fails)
        
        Args:
            design_plan: Canva-specific design plan
            
        Returns:
            Dict with canva_design_id, canva_edit_url, etc.
            
        Raises:
            WorkflowException: On Canva errors
        """
        self.logger.info(f"[DesignAgent] Executing Canva plan")
        
        # Emit start event
        await self.emit_event(
            event_name="canva_design_started",
            message="Creating Canva design...",
            progress_pct=60,
            metadata={}
        )
        
        try:
            # Create Canva design
            design = await self.canva.create_presentation(title=design_plan.title)
            
            self.logger.info(f"[DesignAgent] Created Canva design: {design.design_id}")
            
            # Try to add content (non-fatal if fails due to API limits)
            content_warnings = []
            
            try:
                # Add title
                await self.canva.add_text_block(
                    design_id=design.design_id,
                    text=design_plan.title,
                    x=100.0, y=100.0, width=800.0, height=100.0, font_size=48
                )
            except Exception as e:
                content_warnings.append(f"Failed to add title: {e}")
                self.logger.warning(f"[DesignAgent] {content_warnings[-1]}")
            
            # Add sections
            y_offset = 250.0
            slides_completed = 0
            for idx, section in enumerate(design_plan.sections):
                try:
                    text = f"{section.heading}\n{section.content[:500]}"
                    await self.canva.add_text_block(
                        design_id=design.design_id,
                        text=text,
                        x=100.0, y=y_offset, width=800.0, height=200.0, font_size=24
                    )
                    slides_completed += 1
                    y_offset += 220.0
                except Exception as e:
                    content_warnings.append(f"Failed to add section {idx}: {e}")
                    self.logger.warning(f"[DesignAgent] {content_warnings[-1]}")
            
            # Emit partial warning if content addition failed
            if content_warnings:
                await self.emit_event(
                    event_name="canva_content_partial_warning",
                    message="Design created but some content couldn't be added",
                    progress_pct=90,
                    metadata={
                        "warning": "Canva API limits prevented adding all text blocks",
                        "slides_completed": slides_completed,
                        "slides_total": len(design_plan.sections)
                    }
                )
            
            # Emit success event
            await self.emit_event(
                event_name="canva_design_created",
                message="Canva design created successfully",
                progress_pct=90,
                metadata={
                    "design_id": design.design_id,
                    "edit_url": f"https://www.canva.com/design/{design.design_id}/edit"
                }
            )
            
            # Return artifact metadata
            return {
                "canva_design_id": design.design_id,
                "canva_edit_url": f"https://www.canva.com/design/{design.design_id}/edit",
                "canva_view_url": design.thumbnail_url
            }
            
        except Exception as e:
            # Classify Canva errors
            err_msg = str(e)
            if "Authentication failed" in err_msg or "401" in err_msg:
                raise WorkflowException(
                    ErrorType.USER,
                    "Please connect Canva account",
                    retryable=False
                )
            
            self.logger.error(f"[DesignAgent] Canva execution failed: {e}")
            raise WorkflowException(
                ErrorType.TRANSIENT,
                f"Canva Error: {e}",
                retryable=True
            )
