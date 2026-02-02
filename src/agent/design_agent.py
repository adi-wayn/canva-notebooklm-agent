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
from src.agent.schemas import (
    CanonicalOutput, 
    DesignPlan, 
    SectionContent, 
    TraceMap, 
    SlideTrace, 
    TraceElement
)
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
        
        # 5.5. Agent reasoning: Decide how to structure the presentation
        reasoning = await self._reason_about_structure(canonical_output, design_plan)
        design_plan.reasoning = reasoning  # Attach reasoning to plan
        
        # 5.6. Save Design Plan as artifact (NEW)
        await self._save_design_plan_artifact(design_plan, workflow, engine)
        
        # 6. Execute Canva creation
        canva_result = await self._execute_canva_plan(design_plan, reasoning)
        
        # 7. Build and save Trace Map artifact (NEW)
        trace_map = await self._build_and_save_trace_map(
            canva_result["traceability"],
            workflow,
            engine,
            canva_result["canva_design_id"]
        )
        
        # 8. Enrich result with artifact IDs for Assistant
        canva_result["artifacts"] = {
            "canonical_output_id": "canonical_output_v1",  # Simplified ID for MVP
            "design_plan_id": "design_plan_v1",
            "trace_map_id": "trace_map_v1"
        }
        
        # 9. Compute Traceability Summary for Assistant Message
        stats = {
            "total_elements": len(canva_result.get("traceability", [])),
            "from_notebooklm": 0,
            "agent_decisions": 0
        }
        for item in canva_result.get("traceability", []):
            if "notebooklm" in item.get("source", "").lower() or "canonical" in item.get("source", "").lower():
                stats["from_notebooklm"] += 1
            else:
                stats["agent_decisions"] += 1
                
        canva_result["traceability_summary"] = stats
        
        self.logger.info(f"[DesignAgent] Execution complete. Traceability: {stats}")
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
            
            # Parse JSON (NotebookLM return content structure directly)
            parsed_content = json.loads(content_str)
            
            # Construct Canonical Output Envelope
            raw_data = {
                "version": "1.0",
                "source": "notebooklm",
                "content": parsed_content,
                "extraction_metadata": {
                    "notebook_id": "default_notebook",
                    "query": prompt,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            }
            
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
            await engine.add_artifact(
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
    
    async def _reason_about_structure(
        self,
        canonical_output: Dict[str, Any],
        design_plan: DesignPlan
    ) -> Dict[str, Any]:
        """
        Agent reasoning: Decide what matters and how to structure the presentation.
        
        This is where the agent demonstrates intelligence, not just orchestration.
        
        Decisions made:
        - Which sections become slides vs. combined
        - Slide ordering for narrative flow
        - What content to emphasize vs. de-emphasize
        - Layout hints based on content type
        
        Args:
            canonical_output: Validated canonical output from NotebookLM
            design_plan: Design plan built from canonical output
        
        Returns:
            Reasoning metadata with decisions
        """
        self.logger.info(f"[DesignAgent] Agent reasoning about presentation structure")
        
        content = canonical_output["content"]
        sections = content.get("sections", [])
        
        # DECISION 1: Slide structure
        # Rule: Sections with bullets → separate slides
        # Rule: Short sections → combine into one slide
        slide_decisions = []
        for idx, section in enumerate(sections):
            has_bullets = bool(section.get("bullets"))
            content_length = len(section.get("content", ""))
            
            decision = {
                "section_index": idx,
                "heading": section.get("heading"),
                "becomes_slide": has_bullets or content_length > 200,
                "reasoning": "Has bullets - needs dedicated slide" if has_bullets 
                            else "Long content - needs space" if content_length > 200
                            else "Short - may combine with next"
            }
            slide_decisions.append(decision)
        
        # DECISION 2: Narrative flow
        # Reorder if needed for logical progression
        # (For MVP: keep original order, but log the decision)
        flow_decision = {
            "original_order": [s.get("heading") for s in sections],
            "final_order": [s.get("heading") for s in sections],
            "reasoning": "Maintaining source order for clarity"
        }
        
        # DECISION 3: Visual treatment
        # Determine layout based on content characteristics
        visual_decisions = []
        for idx, section in enumerate(sections):
            hint = section.get("visual_hint", "text")
            has_bullets = bool(section.get("bullets"))
            
            layout = "bullet_list" if has_bullets else "text_block"
            visual_decisions.append({
                "heading": section.get("heading"),
                "layout": layout,
                "reasoning": f"Content has bullets" if has_bullets else "Narrative text"
            })
        
        # Emit reasoning event
        await self.emit_event(
            event_name="agent_reasoning_completed",
            message="Agent analyzed structure and made design decisions",
            progress_pct=55,
            metadata={
                "total_sections": len(sections),
                "slides_planned": sum(1 for d in slide_decisions if d["becomes_slide"]),
                "reasoning_summary": f"Creating {sum(1 for d in slide_decisions if d['becomes_slide'])} slides from {len(sections)} sections"
            }
        )
        
        self.logger.info(
            f"[DesignAgent] Reasoning complete: {len(sections)} sections → "
            f"{sum(1 for d in slide_decisions if d['becomes_slide'])} slides"
        )
        
        return {
            "slide_decisions": slide_decisions,
            "flow_decision": flow_decision,
            "visual_decisions": visual_decisions
        }
    
    async def _execute_canva_plan(
        self,
        design_plan: DesignPlan,
        reasoning: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create Canva design with content DIRECTLY FROM NotebookLM output.
        
        Every slide, every text block, every bullet must be traceable
        back to the canonical output.
        
        Emits:
            - canva_design_started
            - canva_design_created
            - canva_content_partial_warning (if content addition fails)
        
        Args:
            design_plan: Canva-specific design plan
            reasoning: Agent's reasoning decisions
            
        Returns:
            Dict with canva_design_id, canva_edit_url, etc.
            
        Raises:
            WorkflowException: On Canva errors
        """
        self.logger.info(f"[DesignAgent] Executing Canva plan with {design_plan.slide_count} slides")
        
        # Emit start event
        await self.emit_event(
            event_name="canva_design_started",
            message=f"Creating Canva design: {design_plan.title}",
            progress_pct=60,
            metadata={}
        )
        
        try:
            # Create Canva design with title FROM NotebookLM
            design = await self.canva.create_presentation(title=design_plan.title)
            
            self.logger.info(
                f"[DesignAgent] ✓ Created Canva design {design.design_id} "
                f"with title '{design_plan.title}' FROM NotebookLM"
            )
            
            # Track content additions for full traceability
            content_added = []
            content_warnings = []
            
            # SLIDE 1: Title FROM NotebookLM canonical output
            try:
                await self.canva.add_text_block(
                    design_id=design.design_id,
                    text=design_plan.title,  # FROM canonical_output.content.title
                    x=100.0, y=100.0, width=800.0, height=100.0, font_size=48
                )
                content_added.append({
                    "type": "title",
                    "text": design_plan.title,
                    "source": "canonical_output.content.title"
                })
                self.logger.info(f"[DesignAgent] ✓ Title: '{design_plan.title}'")
            except Exception as e:
                content_warnings.append(f"Failed to add title: {e}")
                self.logger.warning(f"[DesignAgent] ⚠ {content_warnings[-1]}")
            
            # Subtitle if present FROM NotebookLM
            if design_plan.subtitle:
                try:
                    await self.canva.add_text_block(
                        design_id=design.design_id,
                        text=design_plan.subtitle,  # FROM canonical_output.content.subtitle
                        x=100.0, y=220.0, width=800.0, height=50.0, font_size=24
                    )
                    content_added.append({
                        "type": "subtitle",
                        "text": design_plan.subtitle,
                        "source": "canonical_output.content.subtitle"
                    })
                    self.logger.info(f"[DesignAgent] ✓ Subtitle: '{design_plan.subtitle}'")
                except Exception as e:
                    content_warnings.append(f"Failed to add subtitle: {e}")
            
            # Content sections FROM NotebookLM
            y_offset = 300.0
            slides_completed = 0
            
            for idx, section in enumerate(design_plan.sections):
                try:
                    # Section heading FROM canonical_output.content.sections[idx].heading
                    await self.canva.add_text_block(
                        design_id=design.design_id,
                        text=section.heading,
                        x=100.0, y=y_offset, width=800.0, height=60.0, font_size=32
                    )
                    
                    # Section content FROM canonical_output.content.sections[idx].content
                    await self.canva.add_text_block(
                        design_id=design.design_id,
                        text=section.content,
                        x=100.0, y=y_offset + 70.0, width=800.0, height=120.0, font_size=16
                    )
                    
                    # Bullets FROM canonical_output.content.sections[idx].bullets
                    if section.bullets:
                        bullet_text = "\n".join(f"• {b}" for b in section.bullets)
                        await self.canva.add_text_block(
                            design_id=design.design_id,
                            text=bullet_text,
                            x=120.0, y=y_offset + 200.0, width=760.0, height=150.0, font_size=14
                        )
                    
                    content_added.append({
                        "section": idx + 1,
                        "heading": section.heading,
                        "content_chars": len(section.content),
                        "bullets": len(section.bullets) if section.bullets else 0,
                        "source": f"canonical_output.content.sections[{idx}]"
                    })
                    
                    self.logger.info(
                        f"[DesignAgent] ✓ Section {idx+1}: '{section.heading}' "
                        f"({len(section.content)} chars, {len(section.bullets) if section.bullets else 0} bullets)"
                    )
                    
                    slides_completed += 1
                    y_offset += 380.0
                    
                except Exception as e:
                    content_warnings.append(f"Section {idx+1} failed: {e}")
                    self.logger.warning(f"[DesignAgent] ⚠ {content_warnings[-1]}")
            
            # Log complete traceability
            self.logger.info(
                f"[DesignAgent] ✓ TRACEABILITY: Added {len(content_added)} elements "
                f"from NotebookLM → Canva design {design.design_id}"
            )
            
            # Emit partial warning if needed
            if content_warnings:
                await self.emit_event(
                    event_name="canva_content_partial_warning",
                    message=f"Design created, {len(content_warnings)} warnings",
                    progress_pct=85,
                    metadata={
                        "slides_completed": slides_completed,
                        "slides_total": len(design_plan.sections),
                        "warnings": content_warnings[:3]
                    }
                )
            
            # Emit success
            await self.emit_event(
                event_name="canva_design_created",
                message=f"Created design with {slides_completed} sections from NotebookLM",
                progress_pct=90,
                metadata={
                    "design_id": design.design_id,
                    "edit_url": f"https://www.canva.com/design/{design.design_id}/edit",
                    "content_elements": len(content_added),
                    "sections_completed": slides_completed
                }
            )
            
            # Return with traceability info
            return {
                "canva_design_id": design.design_id,
                "canva_edit_url": f"https://www.canva.com/design/{design.design_id}/edit",
                "canva_view_url": design.thumbnail_url,
                "content_source": "NotebookLM canonical output",
                "sections_completed": slides_completed,
                "traceability": content_added  # Full trace: NotebookLM → Canva
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

    async def _save_design_plan_artifact(
        self, 
        design_plan: DesignPlan, 
        workflow: Any, 
        engine: Any
    ):
        """Save the detailed design plan as a persistent artifact."""
        await engine.add_artifact(
            workflow=workflow,
            name="Design Plan (v1.0)",
            content_type="application/json",
            data=design_plan.to_dict(),
            metadata={
                "type": "design_plan",
                "slide_count": design_plan.slide_count,
                "theme": design_plan.theme
            }
        )
        self.logger.info(f"[DesignAgent] Saved Design Plan artifact")

    def _get_artifact(self, workflow_data: Dict[str, Any], artifact_type: str) -> Optional[Dict[str, Any]]:
        """Helper to retrieve specific artifact from workflow data"""
        if not workflow_data or "artifacts" not in workflow_data:
            return None
            
        for artifact in workflow_data["artifacts"]:
            if artifact.get("data") and artifact["data"].get("type") == artifact_type:
                # Return the inner data
                return artifact["data"]
            # Fallback check by name if metadata missing
            if artifact_type == "design_plan" and "Design Plan" in artifact["name"]:
                return artifact["data"]
            if artifact_type == "trace_map" and "Trace Map" in artifact["name"]:
                return artifact["data"]
                
        return None

    async def edit_design(
        self, 
        modification_prompt: str,
        previous_workflow_id: str,
        workflow: Any,
        engine: Any
    ) -> Dict[str, Any]:
        """
        Real Iteration Logic:
        1. Fetch previous workflow artifacts (DesignPlan)
        2. Ask NotebookLM to modify the plan
        3. Execute the new plan
        """
        self.logger.info(f"[DesignAgent] ITERATION: Modifying {previous_workflow_id} with request: {modification_prompt}")
        
        # 1. Fetch previous artifacts
        prev_workflow = engine.get_workflow(previous_workflow_id)
        if not prev_workflow:
            raise ValueError(f"Previous workflow {previous_workflow_id} not found")
            
        # Extract Design Plan (serializing workflow to dict to inspect artifacts)
        # Note: In real engine, we might have a better way, but to_dict() works
        prev_data = prev_workflow.to_dict()
        design_plan_data = self._get_artifact(prev_data, "design_plan")
        
        if not design_plan_data:
            raise ValueError(f"No Design Plan found in workflow {previous_workflow_id}")
            
        # 2. Reasoning: Ask NotebookLM to modify the plan
        # We construct a prompt that includes the OLD plan and the REQUEST
        prompt = f"""
        TASK: Modify the presentation design plan based on the USER REQUEST.
        
        CURRENT DESIGN PLAN (JSON):
        {json.dumps(design_plan_data, indent=2)}
        
        USER REQUEST: "{modification_prompt}"
        
        INSTRUCTIONS:
        1. Parse the Current Design Plan.
        2. Apply the changes requested by the user.
        3. Return the FULL updated Design Plan as valid JSON.
        4. Keep the same structure: {{ "theme": "...", "slides": [...] }}
        5. Do not explain, just return JSON.
        """
        
        await self.context.emit_event(
            "agent_thinking",
            f"Reasoning about modification: '{modification_prompt}'",
            10
        )
        
        try:
            # Query NotebookLM 
            # (Note: We use the adapter's send_message. If it's a new conversation, we might need a notebook_id.
            # Ideally, we'd reuse the same notebook, but for now we treat the Prompt as the context source of truth.)
            response = await self.context.notebooklm.send_message(
                notebook_id="default", # In real app, this might come from artifact
                content=prompt
            )
            
            # Parse JSON from response
            content_str = response.content
            if "```json" in content_str:
                content_str = content_str.split("```json")[1].split("```")[0].strip()
            elif "```" in content_str:
                content_str = content_str.split("```")[1].split("```")[0].strip()
            
            updated_plan_dict = json.loads(content_str)
            
            # Validate/Reconstruct DesignPlan object
            # Note: The prompt asked for "slides", but our schema uses "sections"
            # We also need title/subtitle/slide_count which might not be in the lightweight update
            # We'll preserve them from previous plan if not in update
            
            new_sections = [
                SectionContent(**s) if isinstance(s, dict) else s 
                for s in updated_plan_dict.get("slides", [])
            ]
            
            # Helper to safely get title/subtitle from prev data or update
            # (Assuming design_plan_data is dict from previous workflow)
            title = updated_plan_dict.get("title", design_plan_data.get("title", "Presentation"))
            subtitle = updated_plan_dict.get("subtitle", design_plan_data.get("subtitle", ""))
            
            new_design_plan = DesignPlan(
                title=title,
                subtitle=subtitle,
                slide_count=len(new_sections) + 1, # +1 for title slide
                theme=updated_plan_dict.get("theme", "professional"),
                sections=new_sections,
                reasoning={"modification": modification_prompt}
            )
            
            # 3. Execute the new plan
            # We treat this as a freshly generated plan
            await self.context.emit_event(
                "design_plan_created",
                f"Updated design plan: {new_design_plan.slide_count} slides",
                30,
                {"slide_count": new_design_plan.slide_count}
            )
            
            # Save the NEW plan as artifact for this NEW workflow
            await self._save_design_plan_artifact(new_design_plan, workflow, engine)
            
            # Execute Canva creation (Standard flow)
            # Use data from previous canonical output if needed, but here we just rely on the plan
            canva_result = await self._execute_canva_plan(new_design_plan, workflow)
            
            # Build new Trace Map
            trace_map = await self._build_and_save_trace_map(
                canva_result["traceability"],
                workflow,
                engine,
                canva_result["canva_design_id"]
            )
            
            # Result
            return {
                "canva_design_id": canva_result["canva_design_id"],
                "canva_edit_url": canva_result["canva_edit_url"],
                "slide_count": new_design_plan.slide_count,
                "modification_summary": f"Updated design based on request: {modification_prompt}",
                "artifacts": {
                    "design_plan_id": "design_plan_v2", # Simplified
                    "trace_map_id": "trace_map_v2"
                }
            }
            
        except Exception as e:
            self.logger.error(f"[DesignAgent] Iteration failed: {e}")
            raise

    async def explain_design(
        self, 
        query: str,
        previous_workflow_id: str,
        workflow: Any,
        engine: Any
    ) -> Dict[str, Any]:
        """
        Real Explainability Logic:
        1. Fetch TraceMap and CanonicalOutput from previous workflow
        2. Ask NotebookLM to explain based on traceability
        """
        self.logger.info(f"[DesignAgent] EXPLAIN: Answering '{query}' for {previous_workflow_id}")
        
        # 1. Fetch artifacts
        prev_workflow = engine.get_workflow(previous_workflow_id)
        if not prev_workflow:
            raise ValueError(f"Workflow {previous_workflow_id} not found")
            
        prev_data = prev_workflow.to_dict()
        trace_map = self._get_artifact(prev_data, "trace_map")
        
        if not trace_map:
            raise ValueError("No Trace Map found to explain design")
            
        # 2. Construct Prompt
        # Flatten trace map for context
        trace_summary = json.dumps(trace_map, indent=2)
        
        prompt = f"""
        TASK: Answer the USER QUESTION about the generated presentation.
        
        CONTEXT (Trace Map - links content to source):
        {trace_summary}
        
        USER QUESTION: "{query}"
        
        INSTRUCTIONS:
        1. Use the Trace Map to find the specific slide or content the user is asking about.
        2. Explain WHERE the content came from (e.g., "This comes from section X...").
        3. Explain WHY it was included (using the 'reasoning' field in the trace).
        4. Be conversational and helpful.
        """
        
        await self.context.emit_event(
            "agent_thinking",
            f"Analyzing trace map to answer: '{query}'",
            10
        )
        
        # Query NotebookLM
        explanation_msg = await self.context.notebooklm.send_message(
            notebook_id="default",
            content=prompt
        )
        explanation = explanation_msg.content
        
        # Log completion
        await self.context.emit_event(
            "agent_reasoning_completed",
            "Generated explanation from Trace Map",
            100,
            {"explanation_snippet": explanation[:50] + "..."}
        )
        
        return {
            "explanation": explanation,
            "artifacts_used": ["trace_map"]
        }

    async def _build_and_save_trace_map(
        self,
        traceability_data: List[Dict[str, Any]],
        workflow: Any,
        engine: Any,
        design_id: str
    ) -> TraceMap:
        """
        Construct and save the Trace Map artifact for explainability.
        
        Maps flat traceability list into structured SlideTrace objects.
        """
        # Group by section/slide index
        slides_map: Dict[int, List[TraceElement]] = {}
        
        for item in traceability_data:
            # Determine slide index (1-based)
            # Items like title/subtitle are on slide 1
            # Items with 'section' key enable mapping to slide index
            slide_idx = 1
            if "section" in item:
                # Assuming title slide is 1, section 1 is slide 2, etc.
                slide_idx = int(item["section"]) + 1
            elif item.get("type") in ["title", "subtitle"]:
                slide_idx = 1
            
            if slide_idx not in slides_map:
                slides_map[slide_idx] = []
            
            trace_element = TraceElement(
                type=item.get("type", "unknown"),
                content_snippet=str(item.get("text", ""))[:50] + "...",
                source=item.get("source", "unknown"),
                reasoning=item.get("reasoning", "Direct mapping")
            )
            slides_map[slide_idx].append(trace_element)
        
        # Build SlideTrace objects
        slide_traces = [
            SlideTrace(slide_index=idx, elements=elements)
            for idx, elements in slides_map.items()
        ]
        slide_traces.sort(key=lambda s: s.slide_index)
        
        trace_map = TraceMap(
            workflow_id=self.workflow_id,
            design_id=design_id,
            slides=slide_traces
        )
        
        # Save artifact
        await engine.add_artifact(
            workflow=workflow,
            name="Trace Map (v1.0)",
            content_type="application/json",
            data=trace_map.to_dict(),
            metadata={
                "type": "trace_map",
                "design_id": design_id,
                "slides_traced": len(slide_traces)
            }
        )
        self.logger.info(f"[DesignAgent] Saved Trace Map artifact with {len(slide_traces)} slides")
        
        return trace_map
