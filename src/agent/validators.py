"""
Canonical Output Validator

Validates NotebookLM output against the canonical schema.
See documents/workflows/CANONICAL_AGENT_OUTPUT.md for specification.
"""

from typing import Dict, Any, List
from datetime import datetime


def validate_canonical_output(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate data against canonical output schema v1.0.
    
    Args:
        data: Raw data to validate (typically from NotebookLM)
        
    Returns:
        Canonical output with validation results
        
    Validation Rules:
        - Title required and non-empty (max 100 chars)
        - At least 1 section with heading and content
        - Max 10 sections (Canva design limit)
        - Section heading max 80 chars
        - Section content max 500 chars
        - Max 5 bullets per section
        - Max 5 key insights, each max 150 chars
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    # Ensure structure exists
    if not isinstance(data, dict):
        return {
            "version": "1.0",
            "source": "notebooklm",
            "extraction_metadata": {},
            "content": {},
            "validation": {
                "is_valid": False,
                "errors": ["Data must be a dictionary"],
                "warnings": []
            }
        }
    
    # Version check
    version = data.get("version", "1.0")
    if version != "1.0":
        warnings.append(f"Schema version mismatch: expected 1.0, got {version}")
    
    # Content validation
    content = data.get("content", {})
    if not isinstance(content, dict):
        errors.append("Missing or invalid 'content' object")
        content = {}
    
    # Title validation (CRITICAL)
    title = content.get("title", "").strip()
    if not title:
        errors.append("Missing required field: content.title")
    elif len(title) > 100:
        errors.append(f"Title too long: {len(title)} chars (max 100)")
    elif len(title) < 5:
        warnings.append("Title is very short (less than 5 characters)")
    
    # Subtitle validation (optional)
    subtitle = content.get("subtitle", "")
    if subtitle and len(subtitle) > 200:
        errors.append(f"Subtitle too long: {len(subtitle)} chars (max 200)")
    
    # Sections validation (CRITICAL)
    sections = content.get("sections", [])
    if not isinstance(sections, list):
        errors.append("'sections' must be an array")
        sections = []
    elif len(sections) == 0:
        errors.append("At least 1 section required")
    elif len(sections) > 10:
        errors.append(f"Too many sections: {len(sections)} (max 10)")
    
    # Validate each section
    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            errors.append(f"Section {idx} must be an object")
            continue
        
        # Heading validation
        heading = section.get("heading", "").strip()
        if not heading:
            errors.append(f"Section {idx}: missing required field 'heading'")
        elif len(heading) > 80:
            errors.append(f"Section {idx}: heading too long ({len(heading)} chars, max 80)")
        
        # Content validation
        section_content = section.get("content", "").strip()
        if not section_content:
            errors.append(f"Section {idx}: missing required field 'content'")
        elif len(section_content) > 500:
            errors.append(f"Section {idx}: content too long ({len(section_content)} chars, max 500)")
        elif len(section_content) > 450:
            warnings.append(f"Section {idx}: content approaching limit ({len(section_content)}/500 chars)")
        
        # Bullets validation (optional)
        bullets = section.get("bullets", [])
        if bullets:
            if not isinstance(bullets, list):
                warnings.append(f"Section {idx}: bullets should be an array")
            elif len(bullets) > 5:
                warnings.append(f"Section {idx}: too many bullets ({len(bullets)}, max 5)")
        
        # Visual hint validation (optional)
        visual_hint = section.get("visual_hint")
        if visual_hint and visual_hint not in ["chart", "image", "quote", "text"]:
            warnings.append(f"Section {idx}: invalid visual_hint '{visual_hint}'")
    
    # Key insights validation (optional)
    key_insights = content.get("key_insights", [])
    if key_insights:
        if not isinstance(key_insights, list):
            warnings.append("'key_insights' should be an array")
        elif len(key_insights) > 5:
            warnings.append(f"Too many key insights: {len(key_insights)} (max 5)")
        else:
            for idx, insight in enumerate(key_insights):
                if isinstance(insight, str) and len(insight) > 150:
                    warnings.append(f"Key insight {idx} too long: {len(insight)} chars (max 150)")
    
    # Suggested theme validation (optional)
    suggested_theme = content.get("suggested_theme")
    if suggested_theme and suggested_theme not in ["professional", "creative", "minimal"]:
        warnings.append(f"Invalid suggested_theme: '{suggested_theme}'")
    
    # Extraction metadata validation
    extraction_metadata = data.get("extraction_metadata", {})
    if not extraction_metadata.get("notebook_id"):
        warnings.append("Missing extraction_metadata.notebook_id")
    if not extraction_metadata.get("query"):
        warnings.append("Missing extraction_metadata.query")
    if not extraction_metadata.get("timestamp"):
        # Add timestamp if missing
        extraction_metadata["timestamp"] = datetime.utcnow().isoformat() + "Z"
    
    # Build validated canonical output
    is_valid = len(errors) == 0
    
    canonical = {
        "version": "1.0",
        "source": data.get("source", "notebooklm"),
        "extraction_metadata": extraction_metadata,
        "content": content,
        "validation": {
            "is_valid": is_valid,
            "warnings": warnings,
            "errors": errors
        }
    }
    
    return canonical


def get_canonical_summary(canonical: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract summary from canonical output for SSE events.
    
    Returns only title, section count, and first few headings.
    Full canonical output is saved as artifact.
    
    Args:
        canonical: Full canonical output
        
    Returns:
        Summary dict for SSE event metadata
    """
    content = canonical.get("content", {})
    sections = content.get("sections", [])
    
    # Get first 3 section headings
    first_headings = [
        s.get("heading", "") 
        for s in sections[:3] 
        if isinstance(s, dict)
    ]
    
    return {
        "title": content.get("title", "Untitled"),
        "sections_count": len(sections),
        "first_headings": first_headings,
        "has_subtitle": bool(content.get("subtitle")),
        "suggested_theme": content.get("suggested_theme", "professional")
    }
