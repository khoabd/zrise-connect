# Zrise Connect Test Suite

Test infrastructure for the Zrise Connect job processing system.

## Structure

```
tests/
├── unit/                   # Unit tests for individual components
│   ├── test_db.py          # Database operations
│   ├── test_zrise_utils.py # Zrise connection and utilities
│   └── test_job_flow.py    # Job state transitions
├── integration/            # Integration tests for full workflows
│   ├── test_executor_flow.py  # Executor job processing
│   └── test_review_flow.py    # Review and approval flow
├── fixtures/               # Test fixtures and mocks
│   └── mock_zrise.py       # Mock Zrise API
├── conftest.py             # pytest configuration and fixtures
└── README.md               # This file
```

## Requirements

```bash
pip install pytest
```

## Running Tests

### Run all tests
```bash
cd ~/.openclaw/workspace-ai-company/skills/zrise-connect
python -m pytest tests/ -v
```

### Run unit tests only
```bash
python -m pytest tests/unit/ -v
```

### Run integration tests only
```bash
python -m pytest tests/integration/ -v
```

### Run specific test file
```bash
python -m pytest tests/unit/test_db.py -v
```

### Run with coverage
```bash
pip install pytest-cov
python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Test Categories

### Unit Tests

- **test_db.py**: Tests database operations including:
  - `create_job()` → `assigned` state
  - `claim_job()` → `in_progress` state
  - `complete_job()` → `done` state
  - Concurrent access handling

- **test_zrise_utils.py**: Tests Zrise connection including:
  - `connect_zrise()` with mock
  - Error handling (timeout, connection failed)
  - Job operations (fetch, create, update)
  - Response parsing

- **test_job_flow.py**: Tests job state machine including:
  - Valid state transitions
  - Invalid transition rejection
  - Full job lifecycle
  - Event recording

### Integration Tests

- **test_executor_flow.py**: Tests executor workflow:
  - Job claiming
  - Job execution and completion
  - Batch processing
  - Concurrent operations

- **test_review_flow.py**: Tests review workflow:
  - Job submission for review
  - Approval flow
  - Rejection and revision flow
  - Batch review

## Fixtures

Fixtures are defined in `conftest.py`:

- `mock_zrise_connection`: Mock Zrise API connection
- `test_db`: In-memory SQLite database for testing
- `sample_job_data`: Sample job data for tests
- `db_with_jobs`: Database pre-populated with sample jobs

## Mock Zrise

The `mock_zrise.py` module provides:

- `MockZriseConnection`: Full mock API client
- `MockZriseTimeoutConnection`: Simulates timeouts
- `MockZriseFailedConnection`: Simulates connection failures
- `create_mock_connection()`: Factory for custom mocks

## Adding Tests

1. **Unit tests**: Add to appropriate file in `tests/unit/`
2. **Integration tests**: Add to appropriate file in `tests/integration/`
3. **New fixtures**: Add to `conftest.py`

Example test:

```python
def test_my_feature(mock_zrise_connection, test_db):
    """Test my feature works correctly."""
    result = my_function(mock_zrise_connection)
    assert result is expected_value
```

## Continuous Integration

Run tests before commits:

```bash
python -m pytest tests/ -v --tb=short
```

Run with strict warnings:

```bash
python -m pytest tests/ -v -W error::Warning
```
