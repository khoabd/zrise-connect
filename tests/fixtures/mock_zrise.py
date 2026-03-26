"""Mock Zrise API client for testing."""
import json
from unittest.mock import MagicMock, patch
from typing import Dict, Any, Optional
import time


class MockZriseResponse:
    """Mock response object that mimics Zrise API responses."""

    def __init__(self, data: Dict[str, Any], status_code: int = 200):
        self.data = data
        self.status_code = status_code
        self.ok = status_code >= 200 and status_code < 300

    def json(self):
        return self.data


class MockZriseConnection:
    """Mock Zrise connection for testing."""

    def __init__(self, base_url: str = "https://zrise.test/api", api_key: str = "test-key"):
        self.base_url = base_url
        self.api_key = api_key
        self._connected = False
        self._jobs = {}
        self._call_count = 0

    def connect(self, timeout: int = 30) -> bool:
        """Simulate connection to Zrise."""
        self._connected = True
        return True

    def disconnect(self):
        """Simulate disconnection."""
        self._connected = False

    def health(self) -> Dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy" if self._connected else "disconnected",
            "version": "1.0.0",
            "timestamp": time.time(),
        }

    def fetch_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a job by ID."""
        self._call_count += 1
        return self._jobs.get(job_id)

    def create_job(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new job."""
        self._call_count += 1
        job_id = job_data.get("id", f"JOB-{self._call_count}")
        job = {
            "id": job_id,
            "title": job_data.get("title", ""),
            "status": "assigned",
            "assignee": job_data.get("assignee"),
            "created_at": time.time(),
        }
        self._jobs[job_id] = job
        return job

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a job."""
        self._call_count += 1
        if job_id in self._jobs:
            self._jobs[job_id].update(updates)
            return self._jobs[job_id]
        return None

    def claim_job(self, job_id: str, user_id: str) -> bool:
        """Claim a job for a user."""
        self._call_count += 1
        if job_id in self._jobs:
            self._jobs[job_id]["status"] = "in_progress"
            self._jobs[job_id]["assignee"] = user_id
            return True
        return False

    def complete_job(self, job_id: str, result: Dict[str, Any] = None) -> bool:
        """Mark a job as completed."""
        self._call_count += 1
        if job_id in self._jobs:
            self._jobs[job_id]["status"] = "done"
            if result:
                self._jobs[job_id]["result"] = result
            return True
        return False

    def get_call_count(self) -> int:
        """Get number of API calls made."""
        return self._call_count


def create_mock_connection(
    jobs: Dict[str, Dict[str, Any]] = None,
    raise_on_connect: Exception = None,
    raise_on_fetch: Exception = None,
) -> MockZriseConnection:
    """Factory to create mock Zrise connections."""
    mock = MockZriseConnection()

    if jobs:
        for job_id, job_data in jobs.items():
            mock._jobs[job_id] = job_data

    if raise_on_connect:
        def failing_connect(*args, **kwargs):
            raise raise_on_connect
        mock.connect = failing_connect

    if raise_on_fetch:
        def failing_fetch(*args, **kwargs):
            raise raise_on_fetch
        mock.fetch_job = failing_fetch

    return mock


# Connection timeout simulation
class MockZriseTimeoutConnection(MockZriseConnection):
    """Mock connection that simulates timeouts."""

    def connect(self, timeout: int = 30) -> bool:
        raise TimeoutError(f"Connection timed out after {timeout}s")


# Connection failure simulation
class MockZriseFailedConnection(MockZriseConnection):
    """Mock connection that simulates connection failures."""

    def connect(self, timeout: int = 30) -> bool:
        raise ConnectionError("Failed to connect to Zrise API")
