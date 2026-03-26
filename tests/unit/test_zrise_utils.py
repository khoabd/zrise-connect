"""Unit tests for Zrise connection and utilities."""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import socket
import ssl

# Add fixtures to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "fixtures"))
from mock_zrise import (
    MockZriseConnection,
    MockZriseTimeoutConnection,
    MockZriseFailedConnection,
    create_mock_connection,
)


class TestZriseConnection:
    """Test Zrise connection functionality."""

    def test_connect_zrise_success(self):
        """Test successful connection to Zrise."""
        mock_conn = MockZriseConnection(base_url="https://zrise.test/api")
        result = mock_conn.connect()

        assert result is True
        assert mock_conn._connected is True

    def test_connect_zrise_health_check(self):
        """Test health check after connection."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()

        health = mock_conn.health()
        assert health["status"] == "healthy"
        assert "version" in health
        assert "timestamp" in health

    def test_connect_zrise_disconnect(self):
        """Test disconnection from Zrise."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()
        mock_conn.disconnect()

        assert mock_conn._connected is False
        health = mock_conn.health()
        assert health["status"] == "disconnected"


class TestZriseErrorHandling:
    """Test error handling for connection issues."""

    def test_connect_timeout(self):
        """Test handling of connection timeout."""
        mock_conn = MockZriseTimeoutConnection()

        with pytest.raises(TimeoutError) as exc_info:
            mock_conn.connect(timeout=5)

        assert "timed out" in str(exc_info.value)
        assert "5s" in str(exc_info.value)

    def test_connection_failed(self):
        """Test handling of connection failure."""
        mock_conn = MockZriseFailedConnection()

        with pytest.raises(ConnectionError) as exc_info:
            mock_conn.connect()

        assert "Failed to connect" in str(exc_info.value)

    def test_fetch_job_not_found(self):
        """Test fetching non-existent job."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()

        result = mock_conn.fetch_job("NON-EXISTENT-JOB")
        assert result is None

    def test_claim_nonexistent_job(self):
        """Test claiming a job that doesn't exist."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()

        result = mock_conn.claim_job("NON-EXISTENT", "user-1")
        assert result is False

    def test_complete_nonexistent_job(self):
        """Test completing a job that doesn't exist."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()

        result = mock_conn.complete_job("NON-EXISTENT")
        assert result is False


class TestZriseJobOperations:
    """Test job operations via connection."""

    def test_create_and_fetch_job(self):
        """Test creating and fetching a job."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()

        job_data = {
            "id": "JOB-001",
            "title": "Test Job",
            "assignee": "user-01",
        }

        created = mock_conn.create_job(job_data)
        assert created["id"] == "JOB-001"
        assert created["status"] == "assigned"

        fetched = mock_conn.fetch_job("JOB-001")
        assert fetched["id"] == "JOB-001"
        assert fetched["title"] == "Test Job"

    def test_claim_job(self):
        """Test claiming an existing job."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()

        # Pre-populate job
        mock_conn._jobs["JOB-002"] = {
            "id": "JOB-002",
            "title": "Unclaimed Job",
            "status": "assigned",
            "assignee": None,
        }

        result = mock_conn.claim_job("JOB-002", "user-02")
        assert result is True
        assert mock_conn._jobs["JOB-002"]["status"] == "in_progress"
        assert mock_conn._jobs["JOB-002"]["assignee"] == "user-02"

    def test_complete_job(self):
        """Test completing a job."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()

        # Pre-populate in_progress job
        mock_conn._jobs["JOB-003"] = {
            "id": "JOB-003",
            "title": "In Progress Job",
            "status": "in_progress",
            "assignee": "user-03",
        }

        result = mock_conn.complete_job("JOB-003", {"output": "test result"})
        assert result is True
        assert mock_conn._jobs["JOB-003"]["status"] == "done"
        assert mock_conn._jobs["JOB-003"]["result"]["output"] == "test result"

    def test_update_job(self):
        """Test updating job fields."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()

        # Create job
        mock_conn.create_job({"id": "JOB-004", "title": "Original Title"})

        # Update it
        updated = mock_conn.update_job("JOB-004", {"title": "Updated Title"})
        assert updated["title"] == "Updated Title"


class TestZriseParsing:
    """Test response parsing functionality."""

    def test_parse_job_response(self):
        """Test parsing job response from API."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()

        mock_conn.create_job({
            "id": "JOB-PARSE",
            "title": "Parse Test",
            "priority": "high",
            "metadata": {"key": "value"},
        })

        job = mock_conn.fetch_job("JOB-PARSE")
        assert job is not None
        assert job["id"] == "JOB-PARSE"
        assert "metadata" in job

    def test_parse_health_response(self):
        """Test parsing health check response."""
        mock_conn = MockZriseConnection()
        mock_conn.connect()

        health = mock_conn.health()

        assert health["status"] == "healthy"
        assert isinstance(health["timestamp"], (int, float))


class TestZriseMockFactory:
    """Test mock connection factory."""

    def test_create_mock_with_jobs(self):
        """Test factory with pre-populated jobs."""
        jobs = {
            "JOB-A": {"id": "JOB-A", "title": "Job A", "status": "assigned"},
            "JOB-B": {"id": "JOB-B", "title": "Job B", "status": "in_progress"},
        }

        mock = create_mock_connection(jobs=jobs)
        mock.connect()

        assert mock.fetch_job("JOB-A")["title"] == "Job A"
        assert mock.fetch_job("JOB-B")["status"] == "in_progress"

    def test_create_mock_with_connect_error(self):
        """Test factory with connection error simulation."""
        mock = create_mock_connection(raise_on_connect=ConnectionError("Test error"))

        with pytest.raises(ConnectionError):
            mock.connect()

    def test_create_mock_with_fetch_error(self):
        """Test factory with fetch error simulation."""
        mock = create_mock_connection(raise_on_fetch=TimeoutError("Fetch timeout"))

        with pytest.raises(TimeoutError):
            mock.fetch_job("any-job")

    def test_call_count_tracking(self):
        """Test that API call count is tracked."""
        mock = create_mock_connection()
        mock.connect()

        mock.create_job({"id": "J1"})
        mock.create_job({"id": "J2"})
        mock.fetch_job("J1")

        assert mock.get_call_count() == 3


class TestZriseEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_job_id(self):
        """Test operations with empty job ID."""
        mock = MockZriseConnection()
        mock.connect()

        result = mock.fetch_job("")
        assert result is None

    def test_special_characters_in_title(self):
        """Test job with special characters in title."""
        mock = MockZriseConnection()
        mock.connect()

        job = mock.create_job({
            "id": "JOB-SPECIAL",
            "title": "Job with 'quotes' and \"double quotes\" & <special> chars",
        })

        assert job["title"] == "Job with 'quotes' and \"double quotes\" & <special> chars"

    def test_none_values_in_metadata(self):
        """Test handling of None values in job metadata."""
        mock = MockZriseConnection()
        mock.connect()

        job = mock.create_job({
            "id": "JOB-NONE",
            "title": "None Test",
            "assignee": None,
        })

        assert job["assignee"] is None

    def test_concurrent_operations(self):
        """Test multiple operations in sequence."""
        mock = MockZriseConnection()
        mock.connect()

        # Create multiple jobs
        for i in range(5):
            mock.create_job({"id": f"JOB-{i}", "title": f"Job {i}"})

        # Claim and complete some
        mock.claim_job("JOB-0", "user-1")
        mock.complete_job("JOB-0")

        assert mock.fetch_job("JOB-0")["status"] == "done"
        assert mock.fetch_job("JOB-1")["status"] == "assigned"
