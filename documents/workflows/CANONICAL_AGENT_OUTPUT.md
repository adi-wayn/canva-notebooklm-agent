# Canonical Agent Output Schema

## Overview

This document defines the **canonical output schema** that serves as the contract between:
- **NotebookLM** (source of structured insights)
- **AI Agent** (orchestrator and validator)
- **Canva** (design creation target)
- **UI** (user-facing presentation)

---

## Schema Version 1.0

### JSON Structure

```json
{
  "version": "1.0",
  "source": "notebooklm",
  "extraction_metadata": {
    "notebook_id": "string",
    "query": "string",
    "timestamp": "ISO8601 string"
  },
  "content": {
    "title": "string (required, max 100 chars)",
    "subtitle": "string (optional, max 200 chars)",
    "sections": [
      {
        "heading": "string (required, max 80 chars)",
        "content": "string (required, max 500 chars)",
        "bullets": ["string"] (optional, max 5 items),
        "visual_hint": "string (optional: 'chart', 'image', 'quote', 'text')"
      }
    ],
    "key_insights": ["string"] (optional, max 5 items, max 150 chars each),
    "suggested_theme": "string (optional: 'professional', 'creative', 'minimal')"
  },
  "validation": {
    "is_valid": boolean,
    "warnings": ["string"],
    "errors": ["string"]
  }
}
```

---

## Field Specifications

### Root Level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version (currently "1.0") |
| `source` | string | Yes | Data source identifier (e.g., "notebooklm") |
| `extraction_metadata` | object | Yes | Metadata about the extraction process |
| `content` | object | Yes | The actual structured content |
| `validation` | object | Yes | Validation results |

### Extraction Metadata

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `notebook_id` | string | Yes | NotebookLM notebook identifier |
| `query` | string | Yes | User's original prompt/query |
| `timestamp` | string | Yes | ISO8601 timestamp of extraction |

### Content

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `title` | string | **Yes** | Max 100 chars | Main presentation title |
| `subtitle` | string | No | Max 200 chars | Optional subtitle |
| `sections` | array | **Yes** | Min 1, Max 10 | Content sections |
| `key_insights` | array | No | Max 5 items | High-level takeaways |
| `suggested_theme` | string | No | Enum values | Design theme hint |

### Section Object

| Field | Type | Required | Constraints | Description |
|-------|------|----------|-------------|-------------|
| `heading` | string | **Yes** | Max 80 chars | Section title |
| `content` | string | **Yes** | Max 500 chars | Section body text |
| `bullets` | array | No | Max 5 items | Bullet points |
| `visual_hint` | string | No | Enum values | Layout suggestion |

### Validation Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `is_valid` | boolean | Yes | Overall validation status |
| `warnings` | array | Yes | Non-fatal validation warnings |
| `errors` | array | Yes | Fatal validation errors |

---

## Validation Rules

### Critical (Must Pass)

1. **Title Required**: `content.title` must be present and non-empty
2. **Minimum Sections**: At least 1 section in `content.sections`
3. **Section Structure**: Each section must have `heading` and `content`
4. **Version Match**: `version` must be "1.0"

### Constraints (Enforced)

1. **Title Length**: Max 100 characters
2. **Subtitle Length**: Max 200 characters (if present)
3. **Section Count**: Max 10 sections (Canva design limit)
4. **Section Heading**: Max 80 characters
5. **Section Content**: Max 500 characters (readability)
6. **Bullets Per Section**: Max 5 items
7. **Key Insights**: Max 5 items, each max 150 characters

### Warnings (Non-Fatal)

1. **Empty Sections**: Section with heading but minimal content
2. **Long Content**: Section content approaching 500 char limit
3. **Missing Visual Hints**: No visual hints provided
4. **Generic Title**: Title is too generic (e.g., "Presentation")

---

## Examples

### Valid Output

```json
{
  "version": "1.0",
  "source": "notebooklm",
  "extraction_metadata": {
    "notebook_id": "default_notebook",
    "query": "Create a presentation about AI in healthcare",
    "timestamp": "2026-02-02T00:30:00Z"
  },
  "content": {
    "title": "AI in Healthcare: Transforming Patient Care",
    "subtitle": "Current Applications and Future Potential",
    "sections": [
      {
        "heading": "Introduction",
        "content": "Artificial intelligence is revolutionizing healthcare delivery, from diagnosis to treatment planning.",
        "bullets": [
          "Improved diagnostic accuracy",
          "Personalized treatment plans",
          "Reduced healthcare costs"
        ],
        "visual_hint": "text"
      },
      {
        "heading": "Current Applications",
        "content": "AI is currently being used in medical imaging, drug discovery, and patient monitoring systems.",
        "visual_hint": "chart"
      },
      {
        "heading": "Future Trends",
        "content": "Emerging applications include AI-powered surgical robots and predictive health analytics.",
        "bullets": [
          "Robotic surgery assistance",
          "Predictive disease modeling"
        ],
        "visual_hint": "image"
      }
    ],
    "key_insights": [
      "AI can reduce diagnostic errors by up to 30%",
      "Healthcare AI market expected to reach $45B by 2026",
      "Patient outcomes improve with AI-assisted care"
    ],
    "suggested_theme": "professional"
  },
  "validation": {
    "is_valid": true,
    "warnings": [],
    "errors": []
  }
}
```

### Invalid Output (Missing Title)

```json
{
  "version": "1.0",
  "source": "notebooklm",
  "extraction_metadata": {
    "notebook_id": "default_notebook",
    "query": "Test",
    "timestamp": "2026-02-02T00:30:00Z"
  },
  "content": {
    "sections": [
      {
        "heading": "Section 1",
        "content": "Some content"
      }
    ]
  },
  "validation": {
    "is_valid": false,
    "warnings": [],
    "errors": ["Missing required field: content.title"]
  }
}
```

### Invalid Output (Too Many Sections)

```json
{
  "version": "1.0",
  "content": {
    "title": "Test",
    "sections": [
      /* 11 sections - exceeds limit of 10 */
    ]
  },
  "validation": {
    "is_valid": false,
    "warnings": [],
    "errors": ["Too many sections: 11 (max 10)"]
  }
}
```

---

## Versioning Strategy

### Current Version: 1.0

**Stability**: This is the initial stable version. Breaking changes will increment the major version.

### Future Versions

- **1.1**: Add optional fields (backwards-compatible)
- **2.0**: Breaking changes to schema structure

### Migration Path

When NotebookLM response format changes:

1. Update parser in `src/agent/design_agent.py`
2. Update validator in `src/agent/validators.py`
3. Increment schema version
4. Document migration in this file
5. Support both old and new versions during transition

---

## Storage

### As Artifact

Canonical output is stored as a **first-class artifact** in the database:

- **Artifact Type**: `canonical_output`
- **Name**: `NotebookLM Extraction (v1.0)`
- **Content Type**: `application/json`
- **Data**: Full canonical JSON

### In SSE Events

SSE events contain **summary only** (not full canonical output):

```json
{
  "event_type": "agent_step",
  "payload": {
    "event_name": "notebooklm_extraction_completed",
    "metadata": {
      "title": "AI in Healthcare",
      "sections_count": 3,
      "first_headings": ["Introduction", "Current Applications", "Future Trends"]
    }
  }
}
```

**Rationale**: Prevents large JSON payloads in SSE stream; DB is source of truth.

---

## Usage

### In Agent Code

```python
from src.agent.validators import validate_canonical_output

# Parse NotebookLM response
raw_data = json.loads(notebooklm_response)

# Validate
canonical = validate_canonical_output(raw_data)

if not canonical["validation"]["is_valid"]:
    raise ValueError(f"Invalid canonical output: {canonical['validation']['errors']}")

# Save as artifact
await engine.add_artifact(
    workflow=workflow,
    name="NotebookLM Extraction (v1.0)",
    content_type="application/json",
    data=canonical
)
```

### In UI

```javascript
// Fetch workflow with artifacts
const workflow = await api.getWorkflow(workflowId, tenantId);

// Find canonical output artifact
const canonicalArtifact = workflow.artifacts.find(
  a => a.content_type === 'application/json' && a.name.includes('NotebookLM Extraction')
);

// Display summary in UI
const summary = canonicalArtifact.data.content;
console.log(`Title: ${summary.title}`);
console.log(`Sections: ${summary.sections.length}`);
```

---

## Contract Guarantees

1. **Immutability**: Once validated and saved, canonical output is immutable
2. **Versioning**: Schema version is always present and checked
3. **Validation**: All outputs are validated before use
4. **Traceability**: Extraction metadata links back to source
5. **Artifact Storage**: Full JSON always available in DB
