"""
Agent Data Schemas

Defines dataclasses for canonical output and design plan structures.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class SectionContent:
    """A single section in the canonical output."""
    heading: str
    content: str
    bullets: Optional[List[str]] = None
    visual_hint: Optional[str] = None  # 'chart', 'image', 'quote', 'text'


@dataclass
class ValidationResult:
    """Validation result for canonical output."""
    is_valid: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class CanonicalOutput:
    """
    Canonical output schema from NotebookLM extraction.
    
    This is the contract between NotebookLM → Agent → Canva → UI.
    See documents/workflows/CANONICAL_AGENT_OUTPUT.md for full specification.
    """
    version: str
    source: str
    extraction_metadata: Dict[str, Any]
    content: Dict[str, Any]  # Contains title, subtitle, sections, key_insights, suggested_theme
    validation: Dict[str, Any]  # Contains is_valid, warnings, errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "source": self.source,
            "extraction_metadata": self.extraction_metadata,
            "content": self.content,
            "validation": self.validation
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalOutput":
        """Create from dictionary."""
        return cls(
            version=data.get("version", "1.0"),
            source=data.get("source", "notebooklm"),
            extraction_metadata=data.get("extraction_metadata", {}),
            content=data.get("content", {}),
            validation=data.get("validation", {"is_valid": False, "errors": ["Invalid structure"]})
        )


@dataclass
class TraceElement:
    """A single element in the trace map linking Canva content back to source."""
    type: str  # title, subtitle, section_heading, section_content, bullet
    content_snippet: str
    source: str  # e.g., "notebooklm.sections[0].heading"
    reasoning: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "content_snippet": self.content_snippet,
            "source": self.source,
            "reasoning": self.reasoning
        }

@dataclass
class SlideTrace:
    """Traceability mapping for a single slide."""
    slide_index: int
    elements: List[TraceElement]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "slide_index": self.slide_index,
            "elements": [e.to_dict() for e in self.elements]
        }

@dataclass
class TraceMap:
    """
    Full traceability map for a generated design.
    """
    workflow_id: str
    design_id: str
    slides: List[SlideTrace]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "design_id": self.design_id,
            "slides": [s.to_dict() for s in self.slides]
        }


@dataclass
class DesignPlan:
    """
    Canva-specific design plan derived from canonical output.
    
    This transforms the canonical output into actionable Canva operations.
    """
    title: str
    subtitle: Optional[str]
    slide_count: int
    theme: str  # 'professional', 'creative', 'minimal'
    sections: List[SectionContent]
    reasoning: Optional[Dict[str, Any]] = None  # Agent reasoning metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/persistence."""
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "slide_count": self.slide_count,
            "theme": self.theme,
            "sections": [
                {
                    "heading": s.heading,
                    "content": s.content,
                    "bullets": s.bullets,
                    "visual_hint": s.visual_hint
                }
                for s in self.sections
            ],
            "reasoning": self.reasoning
        }
