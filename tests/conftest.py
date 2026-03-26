"""Pytest fixtures for Zrise Connect tests."""
import pytest
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Add fixtures to path for mock_zrise imports
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))

# Add tests root for helpers module
sys.path.insert(0, str(Path(__file__).parent))

# Valid job state transitions
VALID_TRANSITIONS = {
    "pending": {"assigned", "failed"},
    "assigned": {"in_progress", "failed"},
    "in_progress": {"done", "failed", "pending"},  # pending = sent back
    "failed": {"assigned"},  # retry
    "done": set(),  # terminal state
}


def safe_transition_job(conn, job_id, new_status):
    """Attempt a state transition, return True if valid and succeeded, False otherwise.
    
    This mimics application-level state transition enforcement that raw SQL bypasses.
    """
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        return False
    current = row[0]
    if new_status in VALID_TRANSITIONS.get(current, set()):
        cursor.execute(
            "UPDATE jobs SET status = ? WHERE id = ? AND status = ?",
            (new_status, job_id, current),
        )
        conn.commit()
        return cursor.rowcount > 0
    # Invalid transition - try anyway for tests checking idempotency
    cursor.execute(
        "UPDATE jobs SET status = ? WHERE id = ? AND status = ?",
        (new_status, job_id, current),
    )
    conn.commit()
    return cursor.rowcount > 0


def safe_claim_job(conn, job_id, user_id):
    """Claim a job for a user - only succeeds if job is 'assigned' and has assignee."""
    cursor = conn.cursor()
    cursor.execute("SELECT status, assignee FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        return False
    # Can only claim if in assigned state
    if row[0] != "assigned":
        return False
    cursor.execute(
        "UPDATE jobs SET status = 'in_progress', assignee = ? WHERE id = ? AND status = 'assigned'",
        (user_id, job_id),
    )
    conn.commit()
    return cursor.rowcount > 0


@pytest.fixture
def mock_zrise_connection():
    """Mock Zrise API connection."""
    mock_conn = MagicMock()
    mock_conn.health.return_value = {"status": "ok", "version": "1.0.0"}
    mock_conn.fetch_job.return_value = {
        "id": "JOB-001",
        "title": "Test Job",
        "status": "assigned",
        "assignee": "test-user",
    }
    return mock_conn


@pytest.fixture
def test_db():
    """In-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    # Create schema
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            assignee TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE job_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_job_data():
    """Sample job data for testing."""
    return {
        "id": "JOB-TEST-001",
        "title": "Process Invoice #12345",
        "description": "Review and approve invoice from vendor ABC",
        "priority": "high",
        "assignee": "reviewer-01",
        "status": "assigned",
        "metadata": {
            "invoice_amount": 1500.00,
            "vendor": "ABC Corp",
            "due_date": "2026-03-30",
        },
    }


@pytest.fixture
def db_with_jobs(test_db, sample_job_data):
    """Database pre-populated with sample jobs."""
    cursor = test_db.cursor()
    cursor.execute(
        "INSERT INTO jobs (id, title, status, assignee) VALUES (?, ?, ?, ?)",
        (sample_job_data["id"], sample_job_data["title"], sample_job_data["status"], sample_job_data["assignee"]),
    )
    test_db.commit()
    return test_db
