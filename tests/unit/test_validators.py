"""
Unit tests for canonical output validators.

Tests the validation logic for NotebookLM output against the canonical schema.
"""

import pytest
from src.agent.validators import validate_canonical_output, get_canonical_summary


class TestValidateCanonicalOutput:
    """Test suite for validate_canonical_output function."""
    
    def test_valid_output_minimal(self):
        """Test validation of minimal valid output."""
        data = {
            "version": "1.0",
            "source": "notebooklm",
            "extraction_metadata": {
                "notebook_id": "test_notebook",
                "query": "Test query",
                "timestamp": "2026-02-02T00:00:00Z"
            },
            "content": {
                "title": "Test Title",
                "sections": [
                    {
                        "heading": "Section 1",
                        "content": "Section content here"
                    }
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is True
        assert len(result["validation"]["errors"]) == 0
        assert result["version"] == "1.0"
        assert result["content"]["title"] == "Test Title"
    
    def test_valid_output_full(self):
        """Test validation of fully populated valid output."""
        data = {
            "version": "1.0",
            "source": "notebooklm",
            "extraction_metadata": {
                "notebook_id": "test_notebook",
                "query": "Create presentation about AI",
                "timestamp": "2026-02-02T00:00:00Z"
            },
            "content": {
                "title": "AI in Healthcare",
                "subtitle": "Transforming Patient Care",
                "sections": [
                    {
                        "heading": "Introduction",
                        "content": "AI is revolutionizing healthcare.",
                        "bullets": ["Point 1", "Point 2"],
                        "visual_hint": "text"
                    },
                    {
                        "heading": "Current Applications",
                        "content": "Medical imaging and diagnostics.",
                        "visual_hint": "chart"
                    }
                ],
                "key_insights": [
                    "AI reduces diagnostic errors by 30%",
                    "Market expected to reach $45B by 2026"
                ],
                "suggested_theme": "professional"
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is True
        assert len(result["validation"]["errors"]) == 0
        assert result["content"]["subtitle"] == "Transforming Patient Care"
        assert len(result["content"]["sections"]) == 2
        assert len(result["content"]["key_insights"]) == 2
    
    def test_missing_title_error(self):
        """Test that missing title produces validation error."""
        data = {
            "version": "1.0",
            "content": {
                "sections": [
                    {"heading": "H1", "content": "C1"}
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is False
        assert any("title" in err.lower() for err in result["validation"]["errors"])
    
    def test_empty_title_error(self):
        """Test that empty title produces validation error."""
        data = {
            "version": "1.0",
            "content": {
                "title": "   ",  # Whitespace only
                "sections": [
                    {"heading": "H1", "content": "C1"}
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is False
        assert any("title" in err.lower() for err in result["validation"]["errors"])
    
    def test_title_too_long_error(self):
        """Test that title exceeding max length produces error."""
        data = {
            "version": "1.0",
            "content": {
                "title": "A" * 101,  # 101 chars, max is 100
                "sections": [
                    {"heading": "H1", "content": "C1"}
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is False
        assert any("title too long" in err.lower() for err in result["validation"]["errors"])
    
    def test_no_sections_error(self):
        """Test that missing sections produces validation error."""
        data = {
            "version": "1.0",
            "content": {
                "title": "Test Title",
                "sections": []
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is False
        assert any("section" in err.lower() for err in result["validation"]["errors"])
    
    def test_too_many_sections_error(self):
        """Test that exceeding max sections produces error."""
        sections = [
            {"heading": f"Section {i}", "content": f"Content {i}"}
            for i in range(11)  # 11 sections, max is 10
        ]
        
        data = {
            "version": "1.0",
            "content": {
                "title": "Test Title",
                "sections": sections
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is False
        assert any("too many sections" in err.lower() for err in result["validation"]["errors"])
    
    def test_section_missing_heading_error(self):
        """Test that section without heading produces error."""
        data = {
            "version": "1.0",
            "content": {
                "title": "Test Title",
                "sections": [
                    {"content": "Content without heading"}
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is False
        assert any("heading" in err.lower() for err in result["validation"]["errors"])
    
    def test_section_missing_content_error(self):
        """Test that section without content produces error."""
        data = {
            "version": "1.0",
            "content": {
                "title": "Test Title",
                "sections": [
                    {"heading": "Heading without content"}
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is False
        assert any("content" in err.lower() for err in result["validation"]["errors"])
    
    def test_section_content_too_long_error(self):
        """Test that section content exceeding max length produces error."""
        data = {
            "version": "1.0",
            "content": {
                "title": "Test Title",
                "sections": [
                    {
                        "heading": "Section 1",
                        "content": "A" * 501  # 501 chars, max is 500
                    }
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is False
        assert any("content too long" in err.lower() for err in result["validation"]["errors"])
    
    def test_section_content_approaching_limit_warning(self):
        """Test that section content near limit produces warning."""
        data = {
            "version": "1.0",
            "content": {
                "title": "Test Title",
                "sections": [
                    {
                        "heading": "Section 1",
                        "content": "A" * 460  # 460 chars, approaching 500 limit
                    }
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is True
        assert any("approaching limit" in warn.lower() for warn in result["validation"]["warnings"])
    
    def test_invalid_visual_hint_warning(self):
        """Test that invalid visual hint produces warning."""
        data = {
            "version": "1.0",
            "content": {
                "title": "Test Title",
                "sections": [
                    {
                        "heading": "Section 1",
                        "content": "Content",
                        "visual_hint": "invalid_hint"
                    }
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is True
        assert any("visual_hint" in warn.lower() for warn in result["validation"]["warnings"])
    
    def test_too_many_bullets_warning(self):
        """Test that exceeding max bullets produces warning."""
        data = {
            "version": "1.0",
            "content": {
                "title": "Test Title",
                "sections": [
                    {
                        "heading": "Section 1",
                        "content": "Content",
                        "bullets": ["B1", "B2", "B3", "B4", "B5", "B6"]  # 6 bullets, max is 5
                    }
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is True
        assert any("too many bullets" in warn.lower() for warn in result["validation"]["warnings"])
    
    def test_invalid_data_type(self):
        """Test that non-dict data is handled gracefully."""
        data = "not a dictionary"
        
        result = validate_canonical_output(data)
        
        assert result["validation"]["is_valid"] is False
        assert any("dictionary" in err.lower() for err in result["validation"]["errors"])
    
    def test_adds_timestamp_if_missing(self):
        """Test that missing timestamp is added automatically."""
        data = {
            "version": "1.0",
            "content": {
                "title": "Test Title",
                "sections": [
                    {"heading": "H1", "content": "C1"}
                ]
            }
        }
        
        result = validate_canonical_output(data)
        
        assert "timestamp" in result["extraction_metadata"]
        assert result["extraction_metadata"]["timestamp"].endswith("Z")


class TestGetCanonicalSummary:
    """Test suite for get_canonical_summary function."""
    
    def test_summary_extraction(self):
        """Test extracting summary from canonical output."""
        canonical = {
            "content": {
                "title": "AI in Healthcare",
                "subtitle": "Transforming Care",
                "sections": [
                    {"heading": "Introduction", "content": "..."},
                    {"heading": "Current State", "content": "..."},
                    {"heading": "Future Trends", "content": "..."},
                    {"heading": "Conclusion", "content": "..."}
                ],
                "suggested_theme": "professional"
            }
        }
        
        summary = get_canonical_summary(canonical)
        
        assert summary["title"] == "AI in Healthcare"
        assert summary["sections_count"] == 4
        assert len(summary["first_headings"]) == 3
        assert summary["first_headings"] == ["Introduction", "Current State", "Future Trends"]
        assert summary["has_subtitle"] is True
        assert summary["suggested_theme"] == "professional"
    
    def test_summary_no_subtitle(self):
        """Test summary when subtitle is missing."""
        canonical = {
            "content": {
                "title": "Test Title",
                "sections": [
                    {"heading": "H1", "content": "C1"}
                ]
            }
        }
        
        summary = get_canonical_summary(canonical)
        
        assert summary["has_subtitle"] is False
    
    def test_summary_few_sections(self):
        """Test summary with fewer than 3 sections."""
        canonical = {
            "content": {
                "title": "Test Title",
                "sections": [
                    {"heading": "H1", "content": "C1"},
                    {"heading": "H2", "content": "C2"}
                ]
            }
        }
        
        summary = get_canonical_summary(canonical)
        
        assert summary["sections_count"] == 2
        assert len(summary["first_headings"]) == 2
    
    def test_summary_default_theme(self):
        """Test summary uses default theme when not specified."""
        canonical = {
            "content": {
                "title": "Test Title",
                "sections": [
                    {"heading": "H1", "content": "C1"}
                ]
            }
        }
        
        summary = get_canonical_summary(canonical)
        
        assert summary["suggested_theme"] == "professional"
