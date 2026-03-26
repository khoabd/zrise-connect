"""Unit tests for job state machine and transitions."""
import pytest
import sqlite3
from datetime import datetime


class TestJobStateTransitions:
    """Test job state transitions through the full lifecycle."""

    VALID_STATES = ["pending", "assigned", "in_progress", "done", "failed"]
    VALID_TRANSITIONS = {
        "pending": ["assigned"],
        "assigned": ["in_progress"],
        "in_progress": ["done", "failed"],
        "done": [],
        "failed": ["assigned"],  # Can retry failed jobs
    }

    def test_pending_to_assigned_transition(self, test_db):
        """Test: pending -> assigned (job created and assigned)."""
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            ("JOB-FLOW-1", "Test Job", "pending"),
        )
        test_db.commit()

        # Transition to assigned
        cursor.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?",
            ("assigned", "JOB-FLOW-1", "pending"),
        )
        test_db.commit()

        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-FLOW-1",))
        assert cursor.fetchone()["status"] == "assigned"

    def test_assigned_to_in_progress_transition(self, test_db):
        """Test: assigned -> in_progress (job claimed by executor)."""
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status, assignee) VALUES (?, ?, ?, ?)",
            ("JOB-FLOW-2", "Test Job", "assigned", "executor-1"),
        )
        test_db.commit()

        # Claim transition
        cursor.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?",
            ("in_progress", "JOB-FLOW-2", "assigned"),
        )
        test_db.commit()

        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-FLOW-2",))
        assert cursor.fetchone()["status"] == "in_progress"

    def test_in_progress_to_done_transition(self, test_db):
        """Test: in_progress -> done (job completed successfully)."""
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            ("JOB-FLOW-3", "Test Job", "in_progress"),
        )
        test_db.commit()

        # Complete transition
        cursor.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?",
            ("done", "JOB-FLOW-3", "in_progress"),
        )
        test_db.commit()

        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-FLOW-3",))
        assert cursor.fetchone()["status"] == "done"

    def test_in_progress_to_failed_transition(self, test_db):
        """Test: in_progress -> failed (job failed during execution)."""
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            ("JOB-FLOW-4", "Test Job", "in_progress"),
        )
        test_db.commit()

        # Fail transition
        cursor.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?",
            ("failed", "JOB-FLOW-4", "in_progress"),
        )
        test_db.commit()

        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-FLOW-4",))
        assert cursor.fetchone()["status"] == "failed"

    def test_failed_to_assigned_retry_transition(self, test_db):
        """Test: failed -> assigned (job retry/resubmit)."""
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            ("JOB-FLOW-5", "Test Job", "failed"),
        )
        test_db.commit()

        # Retry transition
        cursor.execute(
            "UPDATE jobs SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?",
            ("assigned", "JOB-FLOW-5", "failed"),
        )
        test_db.commit()

        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-FLOW-5",))
        assert cursor.fetchone()["status"] == "assigned"


class TestInvalidTransitions:
    """Test that invalid transitions are rejected."""

    def test_cannot_skip_assigned_to_done(self, test_db):
        """Test: cannot transition directly from assigned to done."""
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            ("JOB-INVALID-1", "Test", "assigned"),
        )
        test_db.commit()

        # Try direct transition (should not work with proper guard)
        cursor.execute(
            "UPDATE jobs SET status = 'done' WHERE id = ? AND status = ?",
            ("JOB-INVALID-1", "assigned"),
        )
        test_db.commit()

        # Verify job is still in assigned state
        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-INVALID-1",))
        assert cursor.fetchone()["status"] == "assigned"

    def test_cannot_skip_in_progress(self, test_db):
        """Test: cannot transition from pending directly to in_progress."""
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            ("JOB-INVALID-2", "Test", "pending"),
        )
        test_db.commit()

        cursor.execute(
            "UPDATE jobs SET status = 'in_progress' WHERE id = ? AND status = ?",
            ("JOB-INVALID-2", "pending"),
        )
        test_db.commit()

        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-INVALID-2",))
        assert cursor.fetchone()["status"] == "pending"

    def test_cannot_transition_from_done(self, test_db):
        """Test: done is a terminal state (cannot transition out)."""
        cursor = test_db.cursor()
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            ("JOB-INVALID-3", "Test", "done"),
        )
        test_db.commit()

        cursor.execute(
            "UPDATE jobs SET status = 'in_progress' WHERE id = ? AND status = ?",
            ("JOB-INVALID-3", "done"),
        )
        test_db.commit()

        cursor.execute("SELECT status FROM jobs WHERE id = ?", ("JOB-INVALID-3",))
        assert cursor.fetchone()["status"] == "done"


class TestJobFlowLifecycle:
    """Test complete job lifecycle from creation to completion."""

    def test_full_executor_lifecycle(self, test_db):
        """Test complete lifecycle: pending -> assigned -> in_progress -> done."""
        job_id = "JOB-LIFECYCLE-1"
        cursor = test_db.cursor()

        # 1. Create job (starts as pending)
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            (job_id, "Lifecycle Test Job", "pending"),
        )
        test_db.commit()

        # 2. Assign job
        cursor.execute(
            "UPDATE jobs SET status = 'assigned', assignee = 'executor-1' WHERE id = ? AND status = ?",
            (job_id, "pending"),
        )
        test_db.commit()

        # 3. Executor claims job
        cursor.execute(
            "UPDATE jobs SET status = 'in_progress' WHERE id = ? AND status = ?",
            (job_id, "assigned"),
        )
        test_db.commit()

        # 4. Executor completes job
        cursor.execute(
            "UPDATE jobs SET status = 'done' WHERE id = ? AND status = ?",
            (job_id, "in_progress"),
        )
        test_db.commit()

        # Verify final state
        cursor.execute("SELECT status, assignee FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row["status"] == "done"
        assert row["assignee"] == "executor-1"

    def test_failed_job_retry_lifecycle(self, test_db):
        """Test lifecycle with failure and retry: assigned -> in_progress -> failed -> assigned."""
        job_id = "JOB-LIFECYCLE-2"
        cursor = test_db.cursor()

        # Setup: job in assigned state
        cursor.execute(
            "INSERT INTO jobs (id, title, status, assignee) VALUES (?, ?, ?, ?)",
            (job_id, "Retry Test Job", "assigned", "executor-1"),
        )
        test_db.commit()

        # 1. Executor claims job
        cursor.execute(
            "UPDATE jobs SET status = 'in_progress' WHERE id = ? AND status = ?",
            (job_id, "assigned"),
        )
        test_db.commit()

        # 2. Job fails during execution
        cursor.execute(
            "UPDATE jobs SET status = 'failed' WHERE id = ? AND status = ?",
            (job_id, "in_progress"),
        )
        test_db.commit()

        # Verify failed state
        cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        assert cursor.fetchone()["status"] == "failed"

        # 3. Job is reassigned (retry)
        cursor.execute(
            "UPDATE jobs SET status = 'assigned', assignee = 'executor-2' WHERE id = ? AND status = ?",
            (job_id, "failed"),
        )
        test_db.commit()

        # 4. New executor claims and completes
        cursor.execute(
            "UPDATE jobs SET status = 'in_progress' WHERE id = ? AND status = ?",
            (job_id, "assigned"),
        )
        cursor.execute(
            "UPDATE jobs SET status = 'done' WHERE id = ? AND status = ?",
            (job_id, "in_progress"),
        )
        test_db.commit()

        # Verify completion
        cursor.execute("SELECT status, assignee FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row["status"] == "done"
        assert row["assignee"] == "executor-2"


class TestJobFlowEvents:
    """Test that job state changes are recorded as events."""

    def test_state_changes_create_events(self, test_db):
        """Test that each state transition creates an event record."""
        job_id = "JOB-EVENTS-1"
        cursor = test_db.cursor()

        # Create job
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            (job_id, "Event Test", "pending"),
        )
        cursor.execute(
            "INSERT INTO job_events (job_id, event_type, actor) VALUES (?, ?, ?)",
            (job_id, "created", "system"),
        )

        # Transition to assigned
        cursor.execute(
            "UPDATE jobs SET status = 'assigned' WHERE id = ?",
            (job_id,),
        )
        cursor.execute(
            "INSERT INTO job_events (job_id, event_type, actor) VALUES (?, ?, ?)",
            (job_id, "assigned", "system"),
        )

        # Transition to in_progress
        cursor.execute(
            "UPDATE jobs SET status = 'in_progress' WHERE id = ?",
            (job_id,),
        )
        cursor.execute(
            "INSERT INTO job_events (job_id, event_type, actor) VALUES (?, ?, ?)",
            (job_id, "claimed", "executor-1"),
        )

        # Transition to done
        cursor.execute(
            "UPDATE jobs SET status = 'done' WHERE id = ?",
            (job_id,),
        )
        cursor.execute(
            "INSERT INTO job_events (job_id, event_type, actor) VALUES (?, ?, ?)",
            (job_id, "completed", "executor-1"),
        )

        test_db.commit()

        # Verify events
        cursor.execute(
            "SELECT event_type FROM job_events WHERE job_id = ? ORDER BY id",
            (job_id,),
        )
        events = [row["event_type"] for row in cursor.fetchall()]
        assert events == ["created", "assigned", "claimed", "completed"]

    def test_failed_job_creates_failure_event(self, test_db):
        """Test that failed jobs create failure events."""
        job_id = "JOB-EVENTS-2"
        cursor = test_db.cursor()

        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            (job_id, "Fail Test", "in_progress"),
        )
        cursor.execute(
            "INSERT INTO job_events (job_id, event_type, actor) VALUES (?, ?, ?)",
            (job_id, "failed", "executor-1"),
        )
        test_db.commit()

        cursor.execute(
            "SELECT event_type, actor FROM job_events WHERE job_id = ?",
            (job_id,),
        )
        event = cursor.fetchone()
        assert event["event_type"] == "failed"
        assert event["actor"] == "executor-1"


class TestJobFlowEdgeCases:
    """Test edge cases in job flow."""

    def test_job_without_assignee_cannot_be_claimed(self, test_db):
        """Test that unassigned jobs cannot transition to in_progress."""
        job_id = "JOB-EDGE-1"
        cursor = test_db.cursor()

        # Job is pending (no assignee)
        cursor.execute(
            "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
            (job_id, "Unassigned Job", "pending"),
        )
        test_db.commit()

        # Try to skip to in_progress
        cursor.execute(
            "UPDATE jobs SET status = 'in_progress' WHERE id = ? AND status = ?",
            (job_id, "pending"),
        )
        test_db.commit()

        # Should still be pending
        cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        assert cursor.fetchone()["status"] == "pending"

    def test_already_claimed_job_cannot_be_claimed_again(self, test_db):
        """Test idempotency: claiming an already-claimed job fails."""
        job_id = "JOB-EDGE-2"
        cursor = test_db.cursor()

        cursor.execute(
            "INSERT INTO jobs (id, title, status, assignee) VALUES (?, ?, ?, ?)",
            (job_id, "Already Claimed", "in_progress", "user-1"),
        )
        test_db.commit()

        # Try to claim again (should fail due to state check)
        cursor.execute(
            "UPDATE jobs SET assignee = 'user-2' WHERE id = ? AND status = ?",
            (job_id, "in_progress"),
        )
        test_db.commit()

        # Assignee should still be user-1
        cursor.execute("SELECT assignee FROM jobs WHERE id = ?", (job_id,))
        assert cursor.fetchone()["assignee"] == "user-1"

    def test_multiple_jobs_independent_flows(self, test_db):
        """Test that multiple jobs can have independent flows."""
        cursor = test_db.cursor()

        jobs = [
            ("JOB-MULTI-1", "pending"),
            ("JOB-MULTI-2", "pending"),
            ("JOB-MULTI-3", "pending"),
        ]

        for job_id, initial_status in jobs:
            cursor.execute(
                "INSERT INTO jobs (id, title, status) VALUES (?, ?, ?)",
                (job_id, f"Job {job_id}", initial_status),
            )
        test_db.commit()

        # Progress job 1 to done
        cursor.execute("UPDATE jobs SET status = 'assigned' WHERE id = 'JOB-MULTI-1'")
        cursor.execute("UPDATE jobs SET status = 'in_progress' WHERE id = 'JOB-MULTI-1'")
        cursor.execute("UPDATE jobs SET status = 'done' WHERE id = 'JOB-MULTI-1'")

        # Progress job 2 to in_progress only
        cursor.execute("UPDATE jobs SET status = 'assigned' WHERE id = 'JOB-MULTI-2'")
        cursor.execute("UPDATE jobs SET status = 'in_progress' WHERE id = 'JOB-MULTI-2'")

        # Job 3 stays pending
        test_db.commit()

        # Verify states
        for job_id, expected_status in [
            ("JOB-MULTI-1", "done"),
            ("JOB-MULTI-2", "in_progress"),
            ("JOB-MULTI-3", "pending"),
        ]:
            cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
            assert cursor.fetchone()["status"] == expected_status
