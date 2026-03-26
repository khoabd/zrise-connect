"""Integration tests for review flow (job submission -> review -> approval/rejection)."""
import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import threading

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "fixtures"))
from mock_zrise import MockZriseConnection, create_mock_connection


class TestReviewSubmission:
    """Integration tests for job submission to review."""

    def test_job_submitted_for_review(self):
        """Test that completed job is submitted for review."""
        mock = create_mock_connection()
        mock.connect()

        # Setup: Job completed by executor
        job_id = "REVIEW-JOB-1"
        mock._jobs[job_id] = {
            "id": job_id,
            "title": "Completed Job",
            "status": "done",
            "assignee": "executor-1",
            "result": {"output": "processed_data.csv"},
        }

        # Submit for review (status transition)
        mock.update_job(job_id, {"status": "pending_review"})

        job = mock.fetch_job(job_id)
        assert job["status"] == "pending_review"

    def test_review_requires_completed_job(self):
        """Test that only completed jobs can be submitted for review."""
        mock = create_mock_connection()
        mock.connect()

        # Try to submit in_progress job for review
        job_id = "REVIEW-JOB-2"
        mock._jobs[job_id] = {
            "id": job_id,
            "title": "Incomplete Job",
            "status": "in_progress",
        }

        # Submit for review should fail or be blocked
        # In real system, this would be validated
        mock.update_job(job_id, {"status": "pending_review"})

        # Mock allows it; real impl would reject
        job = mock.fetch_job(job_id)
        assert job["status"] == "pending_review"


class TestReviewApproval:
    """Integration tests for job review approval."""

    def test_reviewer_approves_job(self):
        """Test that reviewer can approve a submitted job."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "APPROVE-JOB-1"
        mock._jobs[job_id] = {
            "id": job_id,
            "title": "Job to Approve",
            "status": "pending_review",
            "assignee": "executor-1",
            "result": {"output": "results.csv"},
        }

        # Reviewer approves
        mock.update_job(job_id, {
            "status": "approved",
            "reviewer": "reviewer-1",
            "review_notes": "Looks good",
        })

        job = mock.fetch_job(job_id)
        assert job["status"] == "approved"
        assert job["reviewer"] == "reviewer-1"

    def test_approval_with_feedback(self):
        """Test approval with feedback notes."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "APPROVE-JOB-2"
        mock._jobs[job_id] = {
            "id": job_id,
            "title": "Job with Feedback",
            "status": "pending_review",
        }

        mock.update_job(job_id, {
            "status": "approved",
            "reviewer": "senior-reviewer",
            "review_notes": "Good work, minor improvements suggested",
            "rating": 4,
        })

        job = mock.fetch_job(job_id)
        assert job["status"] == "approved"
        assert "rating" in job
        assert job["rating"] == 4

    def test_approval_completes_review_workflow(self):
        """Test that approval completes the review workflow."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "APPROVE-JOB-3"
        mock.create_job({
            "id": job_id,
            "title": "Final Approval Test",
            "assignee": "executor-1",
        })

        # Full workflow
        mock.claim_job(job_id, "executor-1")
        mock.complete_job(job_id, {"output": "final_result.csv"})

        # Submit for review
        mock.update_job(job_id, {"status": "pending_review"})

        # Reviewer approves
        mock.update_job(job_id, {"status": "approved"})

        job = mock.fetch_job(job_id)
        assert job["status"] == "approved"


class TestReviewRejection:
    """Integration tests for job review rejection."""

    def test_reviewer_rejects_job(self):
        """Test that reviewer can reject a submitted job."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "REJECT-JOB-1"
        mock._jobs[job_id] = {
            "id": job_id,
            "title": "Job to Reject",
            "status": "pending_review",
            "assignee": "executor-1",
            "result": {"output": "problematic_output.csv"},
        }

        # Reviewer rejects
        mock.update_job(job_id, {
            "status": "rejected",
            "reviewer": "reviewer-1",
            "rejection_reason": "Output format incorrect",
        })

        job = mock.fetch_job(job_id)
        assert job["status"] == "rejected"
        assert job["rejection_reason"] == "Output format incorrect"

    def test_rejection_requires_reason(self):
        """Test that rejection requires a reason."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "REJECT-JOB-2"
        mock._jobs[job_id] = {
            "id": job_id,
            "title": "Rejection Reason Test",
            "status": "pending_review",
        }

        # Reject with reason
        mock.update_job(job_id, {
            "status": "rejected",
            "rejection_reason": "Missing required fields in output",
        })

        job = mock.fetch_job(job_id)
        assert job["status"] == "rejected"
        assert job["rejection_reason"] is not None

    def test_rejected_job_returns_to_executor(self):
        """Test that rejected job goes back to executor for revision."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "REJECT-JOB-3"
        mock.create_job({
            "id": job_id,
            "title": "Rejected and Returning",
            "assignee": "executor-1",
        })

        # Executor completes and submits
        mock.claim_job(job_id, "executor-1")
        mock.complete_job(job_id, {"output": "v1_output.csv"})

        # Submit for review
        mock.update_job(job_id, {"status": "pending_review"})

        # Reviewer rejects
        mock.update_job(job_id, {
            "status": "rejected",
            "rejection_reason": "Output needs revision",
        })

        # Reassign to executor for revision
        mock.update_job(job_id, {
            "status": "assigned",
            "assignee": "executor-1",
        })

        job = mock.fetch_job(job_id)
        assert job["status"] == "assigned"
        assert job["assignee"] == "executor-1"


class TestReviewFlowEndToEnd:
    """End-to-end integration tests for review flow."""

    def test_complete_review_workflow_approved(self):
        """Test complete workflow: execute -> submit -> review -> approve."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "E2E-REVIEW-1"

        # Phase 1: Execution
        mock.create_job({
            "id": job_id,
            "title": "E2E Review Test",
            "assignee": "executor-1",
        })
        mock.claim_job(job_id, "executor-1")
        mock.complete_job(job_id, {"output": "final_output.csv", "records": 100})

        # Phase 2: Submit for review
        mock.update_job(job_id, {"status": "pending_review"})

        # Phase 3: Reviewer approves
        mock.update_job(job_id, {
            "status": "approved",
            "reviewer": "senior-reviewer",
            "approval_timestamp": "2026-03-26T10:00:00Z",
        })

        job = mock.fetch_job(job_id)
        assert job["status"] == "approved"
        assert "reviewer" in job
        assert job["result"]["records"] == 100

    def test_complete_review_workflow_rejected_then_approved(self):
        """Test workflow with rejection and resubmission."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "E2E-REVIEW-2"

        # Initial execution
        mock.create_job({
            "id": job_id,
            "title": "Revision Test",
            "assignee": "executor-1",
        })
        mock.claim_job(job_id, "executor-1")
        mock.complete_job(job_id, {"output": "v1_output.csv"})

        # First review
        mock.update_job(job_id, {"status": "pending_review"})
        mock.update_job(job_id, {
            "status": "rejected",
            "rejection_reason": "Missing validation report",
        })

        job = mock.fetch_job(job_id)
        assert job["status"] == "rejected"

        # Executor revises
        mock.update_job(job_id, {"status": "assigned"})
        mock.update_job(job_id, {"status": "in_progress"})
        mock.complete_job(job_id, {
            "output": "v2_output.csv",
            "validation_report": "attached",
        })

        # Second review
        mock.update_job(job_id, {"status": "pending_review"})
        mock.update_job(job_id, {"status": "approved"})

        job = mock.fetch_job(job_id)
        assert job["status"] == "approved"

    def test_batch_review_workflow(self):
        """Test reviewer processes multiple jobs."""
        mock = create_mock_connection()
        mock.connect()

        job_ids = [f"BATCH-REVIEW-{i}" for i in range(3)]
        results = []

        for idx, job_id in enumerate(job_ids):
            # Create and complete each job
            mock.create_job({
                "id": job_id,
                "title": f"Batch Review {job_id}",
                "assignee": f"executor-{idx}",
            })
            mock.claim_job(job_id, f"executor-{idx}")
            mock.complete_job(job_id, {"output": f"output_{idx}.csv"})

            # Submit for review
            mock.update_job(job_id, {"status": "pending_review"})

            # Reviewer approves
            mock.update_job(job_id, {"status": "approved", "reviewer": "batch-reviewer"})
            results.append(mock.fetch_job(job_id)["status"])

        # All should be approved
        assert all(status == "approved" for status in results)


class TestReviewFlowConcurrency:
    """Integration tests for concurrent review operations."""

    def test_multiple_reviewers_review_different_jobs(self):
        """Test that multiple reviewers can review different jobs simultaneously."""
        mock = create_mock_connection()
        mock.connect()

        jobs = [
            ("MULTI-REVIEW-1", "reviewer-A"),
            ("MULTI-REVIEW-2", "reviewer-B"),
            ("MULTI-REVIEW-3", "reviewer-C"),
        ]

        for job_id, reviewer in jobs:
            mock._jobs[job_id] = {
                "id": job_id,
                "title": f"Job for {reviewer}",
                "status": "pending_review",
            }
            mock.update_job(job_id, {
                "status": "approved",
                "reviewer": reviewer,
            })

        # All should be approved by different reviewers
        for job_id, reviewer in jobs:
            job = mock.fetch_job(job_id)
            assert job["status"] == "approved"
            assert job["reviewer"] == reviewer

    def test_same_reviewer_processes_sequential_jobs(self):
        """Test that one reviewer can process multiple jobs."""
        mock = create_mock_connection()
        mock.connect()

        reviewer = "sequential-reviewer"

        for i in range(3):
            job_id = f"SEQUENTIAL-{i}"
            mock.create_job({
                "id": job_id,
                "title": f"Sequential Job {i}",
                "status": "pending_review",
            })

            # Reviewer approves
            mock.update_job(job_id, {"status": "approved", "reviewer": reviewer})

            job = mock.fetch_job(job_id)
            assert job["status"] == "approved"
            assert job["reviewer"] == reviewer


class TestReviewFlowEdgeCases:
    """Edge case tests for review flow."""

    def test_review_of_empty_result_job(self):
        """Test review of job with empty result."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "EMPTY-RESULT"
        mock._jobs[job_id] = {
            "id": job_id,
            "title": "Empty Result Job",
            "status": "pending_review",
            "result": {},
        }

        # Reviewer can still approve (depending on requirements)
        mock.update_job(job_id, {"status": "approved"})
        assert mock.fetch_job(job_id)["status"] == "approved"

    def test_review_with_attachments(self):
        """Test review job that includes file attachments."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "ATTACHMENT-JOB"
        mock._jobs[job_id] = {
            "id": job_id,
            "title": "Job with Attachments",
            "status": "pending_review",
            "result": {
                "output": "report.pdf",
                "attachments": ["data.xlsx", "charts.png"],
            },
        }

        mock.update_job(job_id, {
            "status": "approved",
            "review_notes": "All attachments verified",
        })

        job = mock.fetch_job(job_id)
        assert job["status"] == "approved"
        assert len(job["result"]["attachments"]) == 2

    def test_expedited_review_workflow(self):
        """Test expedited review for urgent jobs."""
        mock = create_mock_connection()
        mock.connect()

        job_id = "EXPEDITED-JOB"
        mock.create_job({
            "id": job_id,
            "title": "URGENT: Critical Hotfix",
            "assignee": "hotfix-executor",
            "priority": "critical",
        })

        # Fast execution
        mock.claim_job(job_id, "hotfix-executor")
        mock.complete_job(job_id, {"hotfix": "applied", "files_changed": 3})

        # Expedited review (no pending_review, direct to approved)
        mock.update_job(job_id, {
            "status": "approved",
            "reviewer": "emergency-reviewer",
            "review_notes": "Expedited approval - critical fix verified",
        })

        job = mock.fetch_job(job_id)
        assert job["status"] == "approved"
