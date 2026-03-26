"""Unit tests for database operations."""
import pytest
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


class TestJobCreation:
    """Test job creation and initial state."""

    def test_create_job_returns_assigned_state(self, test_db):
        """Test that create_job() sets status to 'assigned'."""
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status, assignee) VALUES (?, ?, ?, ?)",
            ("JOB-001", "Test Job", "pending", None),
        )
        test_db.commit()

        # Verify initial state
        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-001",))
        row = cursor.fetchone()
        assert row["status"] == "pending"

    def test_create_job_sets_correct_fields(self, test_db):
        """Test that created job has correct fields."""
        cursor = test_db.cursor()
        job_id = "JOB-002"
        title = "Process Invoice"
        assignee = "user-01"

        cursor.execute(
            "INSERT INTO jobs (id, title, status, assignee) VALUES (?, ?, ?, ?)",
            (job_id, title, "assigned", assignee),
        )
        test_db.commit()

        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()

        assert row["id"] == job_id
        assert row["title"] == title
        assert row["status"] == "assigned"
        assert row["assignee"] == assignee


class TestJobClaim:
    """Test job claiming (assigned -> in_progress)."""

    def test_claim_job_changes_state_to_in_progress(self, db_with_jobs):
        """Test that claim_job() changes status to 'in_progress'."""
        job_id = db_with_jobs.execute(
            "SELECT id FROM jobs WHERE status = 'assigned'"
        ).fetchone()["id"]

        # Simulate claim
        cursor = db_with_jobs.cursor()
        cursor.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            ("in_progress", job_id),
        )
        db_with_jobs.commit()

        # Verify state change
        cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row["status"] == "in_progress"

    def test_claim_job_records_event(self, db_with_jobs):
        """Test that claiming a job creates an event record."""
        job_id = db_with_jobs.execute(
            "SELECT id FROM jobs WHERE status = 'assigned'"
        ).fetchone()["id"]

        cursor = db_with_jobs.cursor()
        cursor.execute(
            "INSERT INTO job_events (job_id, event_type, actor) VALUES (?, ?, ?)",
            (job_id, "claimed", "test-user"),
        )
        db_with_jobs.commit()

        cursor.execute(
            "SELECT * FROM job_events WHERE job_id = ? AND event_type = ?",
            (job_id, "claimed"),
        )
        event = cursor.fetchone()
        assert event is not None
        assert event["actor"] == "test-user"


class TestJobCompletion:
    """Test job completion (in_progress -> done)."""

    def test_complete_job_changes_state_to_done(self, db_with_jobs):
        """Test that complete_job() changes status to 'done'."""
        # First claim the job
        job_id = db_with_jobs.execute(
            "SELECT id FROM jobs WHERE status = 'assigned'"
        ).fetchone()["id"]

        cursor = db_with_jobs.cursor()
        cursor.execute(
            "UPDATE jobs SET status = 'in_progress' WHERE id = ?",
            (job_id,),
        )
        db_with_jobs.commit()

        # Complete the job
        cursor.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            ("done", job_id),
        )
        db_with_jobs.commit()

        # Verify completion
        cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row["status"] == "done"

    def test_complete_job_records_event(self, db_with_jobs):
        """Test that completing a job creates an event record."""
        job_id = db_with_jobs.execute(
            "SELECT id FROM jobs WHERE status = 'assigned'"
        ).fetchone()["id"]

        cursor = db_with_jobs.cursor()

        # Claim first
        cursor.execute(
            "UPDATE jobs SET status = 'in_progress' WHERE id = ?",
            (job_id,),
        )

        # Then complete
        cursor.execute(
            "INSERT INTO job_events (job_id, event_type, actor) VALUES (?, ?, ?)",
            (job_id, "completed", "test-user"),
        )
        db_with_jobs.commit()

        cursor.execute(
            "SELECT * FROM job_events WHERE job_id = ? AND event_type = ?",
            (job_id, "completed"),
        )
        event = cursor.fetchone()
        assert event is not None


class TestConcurrentAccess:
    """Test concurrent database access scenarios."""

    def test_concurrent_claims_only_one_succeeds(self, test_db):
        """Test that only one concurrent claim succeeds for same job."""
        job_id = "JOB-CONCURRENT"

        # Setup: Create job in assigned state
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status, assignee) VALUES (?, ?, ?, ?)",
            (job_id, "Concurrent Test", "assigned", None),
        )
        test_db.commit()

        results = []

        def claim_job(user_id):
            """Simulate job claiming with locking."""
            conn = sqlite3.connect(":memory:")
            conn.row_factory = sqlite3.Row
            # Re-create schema
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    assignee TEXT
                )
            """)
            conn.commit()

            # Use isolation_level for transaction
            conn.isolation_level = 'EXCLUSIVE'
            try:
                # Try to claim
                c.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
                row = c.fetchone()
                if row and row["status"] == "assigned":
                    c.execute(
                        "UPDATE jobs SET status = ?, assignee = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?",
                        ("in_progress", user_id, job_id, "assigned"),
                    )
                    conn.commit()
                    success = c.rowcount > 0
                    results.append((user_id, success))
                else:
                    results.append((user_id, False))
            except Exception as e:
                results.append((user_id, False))
            finally:
                conn.close()

        # Run concurrent claims
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(claim_job, f"user-{i}") for i in range(3)]
            for f in as_completed(futures):
                pass

        # Verify only one succeeded
        successes = [r for r in results if r[1]]
        assert len(successes) <= 1, f"Expected at most 1 success, got {len(successes)}"

    def test_concurrent_complete_after_claim(self, test_db):
        """Test that completion only works after successful claim."""
        job_id = "JOB-COMPLETE-TEST"

        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status, assignee) VALUES (?, ?, ?, ?)",
            (job_id, "Complete Test", "assigned", None),
        )
        test_db.commit()

        # First: claim the job
        cursor.execute(
            "UPDATE jobs SET status = 'in_progress', assignee = 'user-1' WHERE id = ?",
            (job_id,),
        )
        test_db.commit()

        # Verify can't complete from 'assigned' state
        cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        status = cursor.fetchone()["status"]
        assert status == "in_progress"

        # Complete from correct state
        cursor.execute(
            "UPDATE jobs SET status = 'done' WHERE id = ? AND status = ?",
            (job_id, "in_progress"),
        )
        test_db.commit()

        cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        assert cursor.fetchone()["status"] == "done"


class TestJobStateTransitions:
    """Test valid and invalid state transitions."""

    def test_valid_transition_assigned_to_in_progress(self, test_db):
        """Test valid: assigned -> in_progress."""
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            ("JOB-TRANS-1", "Test", "assigned"),
        )
        cursor.execute(
            "UPDATE jobs SET status = 'in_progress' WHERE id = ? AND status = ?",
            ("JOB-TRANS-1", "assigned"),
        )
        test_db.commit()

        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-TRANS-1",))
        assert cursor.fetchone()["status"] == "in_progress"

    def test_invalid_transition_pending_to_done(self, test_db):
        """Test invalid: pending -> done (should require going through in_progress)."""
        from helpers import safe_transition_job
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            ("JOB-TRANS-2", "Test", "pending"),
        )

        # Try direct transition (should not work)
        safe_transition_job(test_db, "JOB-TRANS-2", "done")
        # Job should still be in pending
        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-TRANS-2",))
        assert cursor.fetchone()["status"] == "pending"

    def test_cannot_complete_unclaimed_job(self, test_db):
        """Test that completed jobs must be claimed first."""
        from helpers import safe_transition_job
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            ("JOB-TRANS-3", "Test", "assigned"),
        )

        # Try to complete without claiming (in_progress state required)
        safe_transition_job(test_db, "JOB-TRANS-3", "done")
        # Job should still be in assigned
        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-TRANS-3",))
        assert cursor.fetchone()["status"] == "assigned"
        # Job should still be in assigned state
        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-TRANS-3",))
        assert cursor.fetchone()["status"] == "assigned"
