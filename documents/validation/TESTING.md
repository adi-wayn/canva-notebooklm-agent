# Testing Guide for Canva NotebookLM Agent

This document provides a comprehensive guide for writing and running tests for the LLM adapter and decision engine components.

## Overview

The test suite is organized into:
- **Unit Tests** (`tests/unit/`): Test individual components in isolation
- **Integration Tests** (`tests/integration/`): Test component interactions and workflows
- **Fixtures** (`tests/fixtures/`): Reusable test utilities and mock builders

## Test Structure

### Unit Tests (`test_llm_adapter.py`)

Tests for the LLM adapter covering:

#### Basic Functionality
- Adapter initialization and configuration
- Timeout clamping to valid ranges
- Async context manager support
- Resource cleanup

#### Text Generation
- Successful text generation with token tracking
- Prompt version handling
- Timeout error handling
- Rate limit error handling
- Latency measurement
- Cost calculation

#### JSON Generation
- Valid JSON parsing
- Markdown-wrapped JSON handling
- Invalid JSON error handling
- Schema validation

#### Caching
- Cache hit returns cached response
- Cache miss triggers API call and stores result
- Cache respects prompt versions

#### Fallback Logic
- Successful fallback execution
- Fallback failure handling
- Preserves error chains

#### Decision Engine
- Basic decisions
- JSON decisions
- Decisions with fallback rules
- Rule registration and lookup

### Integration Tests (`test_decision_pipeline.py`)

Tests for complete workflows:

#### Decision Pipelines
- Multi-step sequential decisions
- Context passing between steps
- Parallel independent decisions

#### Error Recovery
- Automatic retry on timeout
- Rate limit recovery
- Graceful degradation

#### Performance Metrics
- Latency tracking accuracy
- Token usage aggregation
- Cost tracking across multiple calls

#### Prompt Versioning
- Different versions produce different results
- Version upgrade paths
- Cache separation by version

#### End-to-End Scenarios
- Complete Canva design flow
- Error handling in workflows
- Timeout handling in long operations

## Running Tests

### Basic Test Execution

```bash
# Run all tests
pytest

# Run with verbose output
pytest -vv

# Run specific test file
pytest tests/unit/test_llm_adapter.py

# Run specific test class
pytest tests/unit/test_llm_adapter.py::TestLLMAdapterBasics

# Run specific test
pytest tests/unit/test_llm_adapter.py::TestLLMAdapterBasics::test_adapter_initialization
```

### Test Categories

```bash
# Run only unit tests
pytest -m unit tests/unit/

# Run only integration tests
pytest -m integration tests/integration/

# Run all except slow tests
pytest -m "not slow"

# Run LLM-specific tests
pytest -m llm

# Run Canva integration tests
pytest -m canva
```

### Coverage Analysis

```bash
# Generate coverage report
pytest --cov=src --cov-report=html

# View coverage with missing lines
pytest --cov=src --cov-report=term-missing --cov-branch

# Generate detailed coverage report
coverage report -m
coverage html  # Creates htmlcov/index.html
```

### Using the Test Runner Script

```bash
# Run all tests with coverage
python run_tests.py all

# Run only unit tests
python run_tests.py unit

# Run only integration tests
python run_tests.py integration

# Run fast tests only
python run_tests.py fast

# Run without coverage
python run_tests.py all --no-cov

# Run quietly
python run_tests.py all --quiet
```

## Test Fixtures and Mocks

### Available Fixtures

#### Response Builders
```python
from tests.fixtures.mock_llm import build_llm_response, build_openai_response

# Build a mock LLM response
response = build_llm_response(
    content="Test response",
    input_tokens=100,
    output_tokens=50,
    latency_ms=150.0
)

# Build a mock OpenAI API response
openai_response = build_openai_response(
    content="API response",
    input_tokens=100,
    output_tokens=50
)
```

#### Cache Mocking
```python
from tests.fixtures.mock_llm import mock_cache, MockCache

# Get a simple mock cache
cache = mock_cache()

# Use in-memory mock cache
cache = MockCache()
```

#### Client Mocking
```python
from tests.fixtures.mock_llm import mock_async_openai_client

client = mock_async_openai_client()
```

### Conftest Fixtures

The `conftest.py` provides project-wide fixtures:

- `event_loop`: AsyncIO event loop for async tests
- `mock_openai_key`: Mocked OpenAI API key
- Various auth and token manager fixtures

## Writing New Tests

### Basic Test Template

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
class TestMyComponent:
    """Test suite for MyComponent."""

    async def test_basic_functionality(self):
        """Test basic functionality."""
        # Setup
        component = MyComponent()
        
        # Act
        result = await component.do_something()
        
        # Assert
        assert result is not None

    async def test_error_handling(self):
        """Test error handling."""
        # Setup
        component = MyComponent()
        
        # Act & Assert
        with pytest.raises(ExpectedException):
            await component.failing_method()
```

### Mocking API Calls

```python
@pytest.mark.asyncio
async def test_with_mock_api():
    """Test with mocked API call."""
    from unittest.mock import patch
    from tests.fixtures.mock_llm import build_openai_response
    
    adapter = LLMAdapter("test_key")
    response = build_openai_response(content="Test")
    
    with patch.object(adapter.client.chat.completions, "create", return_value=response):
        result = await adapter.generate("Test prompt")
        assert result.content == "Test"
```

### Testing Async Code

```python
@pytest.mark.asyncio
async def test_async_operation():
    """Test async operation."""
    result = await async_function()
    assert result == expected_value

# For multiple parallel operations
@pytest.mark.asyncio
async def test_parallel_operations():
    """Test parallel async operations."""
    results = await asyncio.gather(
        async_op_1(),
        async_op_2(),
        async_op_3(),
    )
    assert len(results) == 3
```

## Test Data and Examples

### Example Contexts
```python
# Design context
context = {
    "user_preferences": {
        "theme": "dark",
        "style": "modern"
    },
    "canvas_size": [1920, 1080],
    "elements": [
        {"type": "text", "content": "Title"},
        {"type": "image", "src": "image.jpg"}
    ]
}

# Canva-specific context
canva_context = {
    "brand_guide": {
        "colors": ["#3B82F6", "#10B981"],
        "fonts": ["Inter", "Open Sans"]
    },
    "design_type": "social_post",
    "dimensions": "1080x1080"
}
```

### Example Responses
```python
# Text response
response = build_llm_response(
    content="Recommendation: Use asymmetric grid layout"
)

# JSON response
json_response = build_openai_response(
    content='{"layout": "grid", "columns": 3, "gap": 20}'
)

# Response with metadata
response = build_llm_response(
    content="Design decision",
    latency_ms=250.5,
    input_tokens=150,
    output_tokens=75
)
```

## Best Practices

### 1. Test Isolation
- Each test should be independent
- Use fixtures for setup/teardown
- Mock external dependencies

### 2. Async Testing
- Always use `@pytest.mark.asyncio` for async tests
- Use `AsyncMock` for mocking async functions
- Use `asyncio.gather()` for parallel tests

### 3. Error Testing
```python
# Test specific exception
with pytest.raises(SpecificError):
    await function_that_raises()

# Test with error details
with pytest.raises(SpecificError) as exc_info:
    await function()
assert "specific message" in str(exc_info.value)
```

### 4. Mock Management
```python
# Verify mock was called
mock_func.assert_called_once()

# Verify call arguments
mock_func.assert_called_with(expected_arg)

# Get call count
assert mock_func.call_count == 2
```

### 5. Naming Conventions
- Test files: `test_*.py`
- Test classes: `Test*`
- Test methods: `test_*`
- Use descriptive names: `test_generate_with_valid_prompt_returns_response`

## Troubleshooting

### Tests Fail with Import Errors
```bash
# Ensure src is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:./src"
pytest
```

### Async Tests Not Running
- Check `pytest.ini` has `asyncio_mode = auto`
- Ensure `pytest-asyncio` is installed
- Use `@pytest.mark.asyncio` decorator

### Mock Not Working
- Verify correct import path for patching
- Use `patch.object()` for method mocking
- Ensure mock is set before function call

### Coverage Report Missing Lines
- Check `--cov-branch` is used
- Verify code paths are actually tested
- Look at `htmlcov/index.html` for details

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
      - run: pip install -r requirements.txt -r requirements-test.txt
      - run: pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v2
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [OpenAI Python Client](https://github.com/openai/openai-python)
