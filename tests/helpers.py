"""Test helpers for state transition enforcement."""
import sqlite3

# Valid job state transitions
VALID_TRANSITIONS = {
    "pending": {"assigned", "failed"},
    "assigned": {"in_progress", "failed"},
    "in_progress": {"done", "failed", "pending"},
    "failed": {"assigned"},
    "done": set(),
}


def safe_transition_job(conn, job_id, new_status):
    """Attempt a state transition, return True if valid and succeeded, False otherwise."""
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
    return False


def safe_claim_job(conn, job_id, user_id):
    """Claim a job for a user - only succeeds if job is 'assigned'."""
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    if not row or row[0] != "assigned":
        return False
    cursor.execute(
        "UPDATE jobs SET status = 'in_progress', assignee = ? WHERE id = ? AND status = 'assigned'",
        (user_id, job_id),
    )
    conn.commit()
    return cursor.rowcount > 0
