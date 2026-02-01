# Test Suite for Canva NotebookLM Agent

## Quick Start

### 1. Install Test Dependencies
```bash
pip install -r requirements-test.txt
```

### 2. Run Tests
```bash
# All tests
pytest

# Unit tests only
pytest -m unit tests/unit/

# Integration tests only
pytest -m integration tests/integration/

# With coverage report
pytest --cov=src --cov-report=html
```

### 3. Using Test Runner Script
```bash
python run_tests.py all              # All tests with coverage
python run_tests.py unit             # Unit tests only
python run_tests.py integration      # Integration tests only
python run_tests.py fast             # Fast tests (exclude slow)
```

---

## What's Included

### 📝 Test Files (841 lines of test code)

- **tests/unit/test_llm_adapter.py** (455 lines, 28 tests)
  - LLM adapter initialization and configuration
  - Text generation with error handling
  - JSON parsing and validation
  - Caching behavior
  - Fallback mechanisms
  - Decision engine

- **tests/integration/test_decision_pipeline.py** (386 lines, 15 tests)
  - Multi-step decision workflows
  - Error recovery scenarios
  - Performance metrics
  - Prompt versioning
  - End-to-end scenarios

### 🔧 Configuration

- **pytest.ini** - Test discovery, markers, asyncio mode, coverage
- **conftest.py** - Shared fixtures and environment setup
- **requirements-test.txt** - All test dependencies

### 🛠️ Utilities

- **tests/fixtures/mock_llm.py** - Mock builders and utilities
- **run_tests.py** - Command-line test runner

### 📚 Documentation

- **TESTING.md** - Comprehensive testing guide with examples
- **T2.3_SUMMARY.md** - Implementation summary
- **TEST_INVENTORY.md** - Detailed test inventory
- **T2.3_CHECKLIST.md** - Completion checklist

---

## Test Statistics

| Metric | Count |
|--------|-------|
| Total Test Methods | 43+ |
| Unit Tests | 28 |
| Integration Tests | 15 |
| Test Classes | 14 |
| Test Lines | 841 |
| Documentation Lines | 1000+ |

---

## Features

✅ **Comprehensive Coverage**
- Adapter functionality (initialization, generation, caching)
- JSON handling (parsing, validation, error handling)
- Error scenarios (timeouts, rate limits, fallbacks)
- Performance metrics (latency, tokens, costs)
- Multi-step workflows and end-to-end scenarios

✅ **Async Testing**
- Full pytest-asyncio support
- Parallel execution with asyncio.gather
- Proper timeout handling
- Async context manager testing

✅ **Mocking Framework**
- Mock response builders
- Cache mocking
- Async client mocking
- No real API calls

✅ **CI/CD Ready**
- Coverage reporting
- Test categorization
- Proper error handling
- Environment configuration

---

## Common Commands

```bash
# Run all tests with verbose output
pytest -vv

# Run specific test class
pytest tests/unit/test_llm_adapter.py::TestLLMAdapterGenerate -v

# Run specific test
pytest tests/unit/test_llm_adapter.py::TestLLMAdapterGenerate::test_generate_success -v

# Run with coverage and HTML report
pytest --cov=src --cov-report=html --cov-report=term-missing

# Run only fast tests (exclude slow)
pytest -m "not slow"

# Run tests matching pattern
pytest -k "test_generate"

# Collect tests without running
pytest --co -q
```

---

## Test Markers

```python
@pytest.mark.asyncio       # Async tests (auto-detected)
@pytest.mark.unit         # Unit tests
@pytest.mark.integration  # Integration tests
@pytest.mark.slow         # Slow running tests
@pytest.mark.llm          # LLM functionality
@pytest.mark.canva        # Canva integration
@pytest.mark.notebooklm   # NotebookLM integration
```

---

## Example: Running Specific Tests

```bash
# Run all unit tests
pytest -m unit

# Run all integration tests
pytest -m integration

# Run LLM-specific tests
pytest -m llm

# Run Canva integration
pytest -m canva

# Run everything except slow tests
pytest -m "not slow"
```

---

## Key Test Classes

### Unit Tests (test_llm_adapter.py)
- **TestLLMAdapterBasics** - Initialization, timeout, context manager
- **TestLLMAdapterGenerate** - Text generation, versioning, errors
- **TestLLMAdapterJSON** - JSON parsing, validation, error handling
- **TestLLMAdapterCaching** - Cache hit/miss, versioning
- **TestLLMAdapterFallback** - Fallback success and failure
- **TestDecisionEngine** - Decision making, rules, JSON decisions
- **TestLLMAdapterErrors** - Error details and wrapping
- **TestLLMAdapterIntegration** - Pipeline and error chains

### Integration Tests (test_decision_pipeline.py)
- **TestDecisionPipeline** - Sequential, parallel decisions
- **TestErrorRecovery** - Retry, rate limits
- **TestPerformanceMetrics** - Latency, tokens, costs
- **TestPromptVersioning** - Version isolation and upgrade
- **TestDecisionEngineFallbackRegistry** - Rule execution
- **TestEndToEndScenarios** - Canva flows, error handling

---

## Fixtures & Mocks

### Available Fixtures
```python
from tests.fixtures.mock_llm import (
    build_llm_response,      # Create LLMResponse
    build_openai_response,   # Create OpenAI response mock
    mock_cache,              # Create mock cache
    mock_async_openai_client # Create mock client
)
```

### Example Usage
```python
response = build_openai_response(
    content="Test response",
    input_tokens=100,
    output_tokens=50
)

with patch.object(adapter.client.chat.completions, "create", return_value=response):
    result = await adapter.generate("Test prompt")
    assert result.content == "Test response"
```

---

## Best Practices

1. **Test Isolation** - Each test is independent
2. **Clear Names** - Descriptive test method names
3. **Proper Mocking** - No real API calls
4. **Async Handling** - Correct async/await usage
5. **Error Testing** - Specific exception types
6. **Documentation** - Clear docstrings
7. **Fixtures** - Reusable test utilities

---

## Troubleshooting

### Tests Not Running
- Check `pytest.ini` exists and has `asyncio_mode = auto`
- Verify test dependencies installed: `pip install -r requirements-test.txt`

### Async Test Issues
- Ensure all async tests have `@pytest.mark.asyncio`
- Use `AsyncMock` for async functions
- Check event loop configuration in conftest.py

### Mock Not Working
- Verify correct patch path for mocking
- Use `patch.object()` for method mocking
- Ensure mock is set before function call

### Coverage Issues
- Run with `--cov-branch` for branch coverage
- Check `htmlcov/index.html` for detailed report
- Look for untested code paths

---

## Documentation

- **TESTING.md** - Complete testing guide
- **T2.3_SUMMARY.md** - Implementation details
- **TEST_INVENTORY.md** - Detailed test listing
- **T2.3_CHECKLIST.md** - Task completion checklist

---

## Installation & Setup

```bash
# 1. Install dependencies
pip install -r requirements-test.txt

# 2. Run tests to verify
pytest tests/unit/test_llm_adapter.py -v

# 3. Check coverage
pytest --cov=src --cov-report=html

# 4. View coverage report
open htmlcov/index.html  # macOS
```

---

## Integration with CI/CD

See **TESTING.md** for complete CI/CD integration examples including:
- GitHub Actions
- Azure DevOps
- GitLab CI
- Other platforms

---

## Performance

- **Average test execution**: < 5 seconds (with mocks)
- **Total test suite**: < 30 seconds
- **With coverage analysis**: < 1 minute

---

For more details, see the comprehensive guides in:
- [TESTING.md](TESTING.md) - Complete testing guide
- [T2.3_SUMMARY.md](T2.3_SUMMARY.md) - Implementation summary
- [TEST_INVENTORY.md](TEST_INVENTORY.md) - Test inventory
- [T2.3_CHECKLIST.md](T2.3_CHECKLIST.md) - Completion checklist
