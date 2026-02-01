# Canva-NotebookLM Integration - Developer Guide

## API Reference

### Authentication API

#### POST /authenticate

Authenticate with both Canva and NotebookLM platforms.

**Request:**
```json
{
  "canva_auth_token": "string",
  "notebooklm_auth_token": "string"
}
```

**Response:**
```json
{
  "auth_id": "string",
  "status": "authenticated",
  "message": "string"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/authenticate \
  -H "Content-Type: application/json" \
  -d '{"canva_auth_token": "your_canva_token", "notebooklm_auth_token": "your_notebooklm_token"}'
```

### Transformation API

#### POST /transform

Request content transformation between platforms.

**Request:**
```json
{
  "canva_design_id": "string",
  "notebooklm_source_id": "string",
  "transformation_type": "text_to_image|image_to_text|layout_generation",
  "content_data": "object",
  "priority": "integer"
}
```

**Response:**
```json
{
  "request_id": "string",
  "status": "queued",
  "message": "string"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/transform \
  -H "Content-Type: application/json" \
  -d '{
    "canva_design_id": "design_123",
    "notebooklm_source_id": "source_456",
    "transformation_type": "text_to_image",
    "content_data": {"text": "Sample text to convert to image"},
    "priority": 1
  }'
```

### Status API

#### GET /status/{request_id}

Check transformation request status.

**Response:**
```json
{
  "request_id": "string",
  "status": "queued|processing|completed|failed",
  "request_details": "object",
  "response_details": "object"
}
```

**Example:**
```bash
curl http://localhost:8000/status/YOUR_REQUEST_ID
```

### Health API

#### GET /health

Check system health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "string",
  "active_requests": "integer",
  "completed_requests": "integer"
}
```

**Example:**
```bash
curl http://localhost:8000/health
```

## Code Examples

### Python Client Example

```python
import requests
import json

class CanvaNotebookLMClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    def authenticate(self, canva_token, notebooklm_token):
        url = f"{self.base_url}/authenticate"
        payload = {
            "canva_auth_token": canva_token,
            "notebooklm_auth_token": notebooklm_token
        }

        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def request_transformation(self, canva_design_id, notebooklm_source_id, 
                             transformation_type, content_data, priority=1):
        url = f"{self.base_url}/transform"
        payload = {
            "canva_design_id": canva_design_id,
            "notebooklm_source_id": notebooklm_source_id,
            "transformation_type": transformation_type,
            "content_data": content_data,
            "priority": priority
        }

        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    def get_status(self, request_id):
        url = f"{self.base_url}/status/{request_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_health(self):
        url = f"{self.base_url}/health"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

# Usage example
if __name__ == "__main__":
    client = CanvaNotebookLMClient()

    # Authenticate
    auth_response = client.authenticate("your_canva_token", "your_notebooklm_token")
    print("Authentication:", auth_response)

    # Request transformation
    transform_response = client.request_transformation(
        canva_design_id="design_123",
        notebooklm_source_id="source_456",
        transformation_type="text_to_image",
        content_data={"text": "Sample text to convert to image"}
    )
    print("Transformation request:", transform_response)

    # Check status
    status_response = client.get_status(transform_response["request_id"])
    print("Status:", status_response)

    # Check health
    health_response = client.get_health()
    print("Health:", health_response)
```

### JavaScript Client Example

```javascript
class CanvaNotebookLMClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
    }

    async authenticate(canvaToken, notebooklmToken) {
        const url = `${this.baseUrl}/authenticate`;
        const payload = {
            canva_auth_token: canvaToken,
            notebooklm_auth_token: notebooklmToken
        };

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`Authentication failed: ${response.statusText}`);
        }

        return response.json();
    }

    async requestTransformation(canvaDesignId, notebooklmSourceId, transformationType, contentData, priority = 1) {
        const url = `${this.baseUrl}/transform`;
        const payload = {
            canva_design_id: canvaDesignId,
            notebooklm_source_id: notebooklmSourceId,
            transformation_type: transformationType,
            content_data: contentData,
            priority: priority
        };

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            throw new Error(`Transformation request failed: ${response.statusText}`);
        }

        return response.json();
    }

    async getStatus(requestId) {
        const url = `${this.baseUrl}/status/${requestId}`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Status check failed: ${response.statusText}`);
        }

        return response.json();
    }

    async getHealth() {
        const url = `${this.baseUrl}/health`;
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Health check failed: ${response.statusText}`);
        }

        return response.json();
    }
}

// Usage example
(async () => {
    const client = new CanvaNotebookLMClient();

    try {
        // Authenticate
        const authResponse = await client.authenticate('your_canva_token', 'your_notebooklm_token');
        console.log('Authentication:', authResponse);

        // Request transformation
        const transformResponse = await client.requestTransformation(
            'design_123',
            'source_456',
            'text_to_image',
            {text: 'Sample text to convert to image'}
        );
        console.log('Transformation request:', transformResponse);

        // Check status
        const statusResponse = await client.getStatus(transformResponse.request_id);
        console.log('Status:', statusResponse);

        // Check health
        const healthResponse = await client.getHealth();
        console.log('Health:', healthResponse);

    } catch (error) {
        console.error('Error:', error.message);
    }
})();
```

## Testing Strategies

### Unit Testing

Test individual components and functions in isolation.

```python
# Example unit test using pytest
import pytest
from main import simulate_text_to_image

def test_text_to_image_transformation():
    content_data = {"text": "Test content"}
    result = simulate_text_to_image(content_data)

    assert "transformation_type" in result
    assert result["transformation_type"] == "text_to_image"
    assert "generated_image_url" in result
    assert result["generated_image_url"].startswith("https://")

def test_image_to_text_transformation():
    content_data = {"image_url": "https://example.com/test.jpg"}
    result = simulate_image_to_text(content_data)

    assert "transformation_type" in result
    assert result["transformation_type"] == "image_to_text"
    assert "extracted_text" in result
    assert len(result["extracted_text"]) > 0

def test_layout_generation():
    content_data = {"content": "Test layout content"}
    result = simulate_layout_generation(content_data)

    assert "transformation_type" in result
    assert result["transformation_type"] == "layout_generation"
    assert "generated_layout" in result
    assert "elements" in result["generated_layout"]
```

### Integration Testing

Test interactions between components and external systems.

```python
# Example integration test
def test_authentication_integration():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    # Test successful authentication
    response = client.post("/authenticate", json={
        "canva_auth_token": "valid_token",
        "notebooklm_auth_token": "valid_token"
    })

    assert response.status_code == 200
    assert "auth_id" in response.json()
    assert response.json()["status"] == "authenticated"

def test_transformation_integration():
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)

    # Test transformation request
    response = client.post("/transform", json={
        "canva_design_id": "test_design",
        "notebooklm_source_id": "test_source",
        "transformation_type": "text_to_image",
        "content_data": {"text": "test content"},
        "priority": 1
    })

    assert response.status_code == 200
    assert "request_id" in response.json()
    assert response.json()["status"] == "queued"
```

## Debugging Guide

### Common Issues and Solutions

#### Authentication Issues

**Symptom**: Authentication fails with invalid token error

**Debugging Steps**:
1. Verify token format and validity
2. Check token expiration
3. Test external API connectivity
4. Review authentication logs

**Solution**:
```bash
# Check authentication logs
tail -f /var/log/canva-notebooklm/auth.log

# Test token validation
curl -X POST http://localhost:8000/authenticate \
  -H "Content-Type: application/json" \
  -d '{"canva_auth_token": "test_token", "notebooklm_auth_token": "test_token"}'
```

#### Transformation Errors

**Symptom**: Transformation requests fail or return errors

**Debugging Steps**:
1. Check transformation type validity
2. Validate content data format
3. Review transformation logs
4. Test with minimal content

**Solution**:
```bash
# Check transformation logs
tail -f /var/log/canva-notebooklm/transform.log

# Test with minimal content
curl -X POST http://localhost:8000/transform \
  -H "Content-Type: application/json" \
  -d '{
    "canva_design_id": "test",
    "notebooklm_source_id": "test",
    "transformation_type": "text_to_image",
    "content_data": {"text": "minimal test"},
    "priority": 1
  }'
```

## Contribution Guidelines

### Code Style Guide

1. **Python**: Follow PEP 8 style guide
2. **JavaScript**: Follow Airbnb style guide
3. **Documentation**: Use Markdown format
4. **Comments**: Use descriptive comments
5. **Naming**: Use descriptive variable names

### Development Workflow

```
FEATURE_REQUEST -> BRANCH_CREATION -> IMPLEMENTATION -> CODE_REVIEW -> TESTING -> MERGE -> DEPLOYMENT
```

### Branch Strategy

1. **main**: Production-ready code
2. **develop**: Integration branch
3. **feature/**: Feature development branches
4. **bugfix/**: Bug fix branches
5. **release/**: Release preparation branches

### Commit Guidelines

1. **Commit Messages**: Use descriptive commit messages
2. **Commit Size**: Keep commits focused and small
3. **Commit Frequency**: Commit frequently with meaningful changes
4. **Commit Format**: Use conventional commit format

## Appendix

### Glossary

- **API**: Application Programming Interface
- **OAuth**: Open Authorization protocol
- **REST**: Representational State Transfer
- **JSON**: JavaScript Object Notation
- **HTTP**: Hypertext Transfer Protocol
- **HTTPS**: HTTP Secure

### References

- FastAPI Documentation: https://fastapi.tiangolo.com/
- Pydantic Documentation: https://pydantic.dev/
- Python Documentation: https://docs.python.org/3/
- REST API Design: https://restfulapi.net/
- OAuth 2.0: https://oauth.net/2/

### Support Resources

- **Developer Forum**: https://dev-forum.canva-notebooklm-integration.com
- **API Documentation**: https://api-docs.canva-notebooklm-integration.com
- **GitHub Repository**: https://github.com/your-org/canva-notebooklm-integration
- **Issue Tracker**: https://github.com/your-org/canva-notebooklm-integration/issues

## Contact Information

For developer support and inquiries:

- **Developer Support**: dev-support@canva-notebooklm-integration.com
- **API Support**: api-support@canva-notebooklm-integration.com
- **Security Issues**: security@canva-notebooklm-integration.com
- **Contributions**: contributions@canva-notebooklm-integration.com
