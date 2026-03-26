#!/usr/bin/env python3
"""
Detect jobs stuck in 'in_progress' for > 1 hour.

Usage:
    python3 detect_orphaned_jobs.py

This script helps identify jobs that may have crashed or stalled,
allowing the system to recover or re-queue them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from db import get_connection


def detect_orphaned_jobs():
    """
    Detect jobs stuck in 'in_progress' for > 1 hour.

    Returns:
        list: List of tuples (id, task_id, agent_id, assigned_at)
    """
    conn = get_connection()
    c = conn.cursor()

    # Jobs in_progress for > 1 hour
    c.execute("""
        SELECT id, task_id, agent_id, assigned_at
        FROM jobs
        WHERE status = 'in_progress'
        AND assigned_at < datetime('now', '-1 hour')
    """)

    results = c.fetchall()
    conn.close()

    return results


def main():
    """Main entry point."""
    orphaned = detect_orphaned_jobs()

    if not orphaned:
        print("No orphaned jobs found.")
        return 0

    print(f"Found {len(orphaned)} orphaned job(s):")
    print("-" * 60)
    print(f"{'Job ID':<10} {'Task ID':<10} {'Agent ID':<20} {'Assigned At':<25}")
    print("-" * 60)

    for job in orphaned:
        job_id, task_id, agent_id, assigned_at = job
        print(f"{job_id:<10} {task_id:<10} {agent_id:<20} {assigned_at:<25}")

    return len(orphaned)


if __name__ == '__main__':
    sys.exit(main())
