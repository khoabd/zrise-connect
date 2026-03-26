#!/usr/bin/env python3
"""
retry_handler.py - Handle job retry logic for failed/timed out jobs.

Usage:
    from retry_handler import should_retry, retry_job
    
    if should_retry(job_id):
        result = retry_job(job_id)

This module provides functions to:
- Check if a job can be retried (within retry limit)
- Reset a job to 'assigned' status for re-execution
- Track retry count and max retries per job
"""

import sys
from pathlib import Path
from datetime import datetime

# Add scripts dir to path for db imports
sys.path.insert(0, str(Path(__file__).parent))

from db import (
    get_job,
    update_job_status,
    get_connection,
)


DEFAULT_MAX_RETRIES = 3


def should_retry(job_id: int) -> bool:
    """Check if job should be retried.
    
    A job should be retried if:
    1. It exists
    2. Its retry_count < max_retries
    
    Args:
        job_id: The job ID to check
    
    Returns:
        True if job can be retried, False otherwise
    """
    job = get_job(job_id)
    
    if not job:
        return False
    
    retry_count = job.get('retry_count', 0)
    max_retries = job.get('max_retries', DEFAULT_MAX_RETRIES)
    
    return retry_count < max_retries


def get_retry_count(job_id: int) -> int:
    """Get current retry count for a job.
    
    Args:
        job_id: The job ID
    
    Returns:
        Current retry count, or 0 if job not found
    """
    job = get_job(job_id)
    return job.get('retry_count', 0) if job else 0


def get_max_retries(job_id: int) -> int:
    """Get max retries configured for a job.
    
    Args:
        job_id: The job ID
    
    Returns:
        Max retries setting, or DEFAULT_MAX_RETRIES if not set
    """
    job = get_job(job_id)
    return job.get('max_retries', DEFAULT_MAX_RETRIES) if job else DEFAULT_MAX_RETRIES


def increment_retry_count(job_id: int) -> dict:
    """Increment retry count for a job.
    
    Args:
        job_id: The job ID
    
    Returns:
        dict with retry_count after increment
    """
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''
        UPDATE jobs 
        SET retry_count = retry_count + 1 
        WHERE id = ?
    ''', (job_id,))
    
    conn.commit()
    conn.close()
    
    new_count = get_retry_count(job_id)
    return {"job_id": job_id, "retry_count": new_count}


def set_max_retries(job_id: int, max_retries: int) -> dict:
    """Set max retries for a job.
    
    Args:
        job_id: The job ID
        max_retries: New max retries value
    
    Returns:
        dict with updated max_retries
    """
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''
        UPDATE jobs SET max_retries = ? WHERE id = ?
    ''', (max_retries, job_id))
    
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    
    return {"job_id": job_id, "max_retries": max_retries, "updated": success}


def retry_job(job_id: int) -> dict:
    """Reset job to assigned for retry.
    
    Increments retry_count and resets status to 'assigned' so the
    job can be picked up by an executor again.
    
    Args:
        job_id: The job ID to retry
    
    Returns:
        dict with:
            - success: bool
            - job_id: int
            - retry_count: int after increment
            - error: str if failed
    """
    job = get_job(job_id)
    
    if not job:
        return {"success": False, "job_id": job_id, "error": "Job not found"}
    
    # Check if retries exhausted
    if not should_retry(job_id):
        return {
            "success": False, 
            "job_id": job_id, 
            "error": "Max retries exhausted",
            "retry_count": job.get('retry_count', 0),
            "max_retries": job.get('max_retries', DEFAULT_MAX_RETRIES)
        }
    
    # Increment retry count
    increment_retry_count(job_id)
    
    # Reset job to assigned status
    result = update_job_status(job_id, 'assigned')
    
    if not result.get('updated'):
        return {
            "success": False, 
            "job_id": job_id, 
            "error": "Failed to update job status"
        }
    
    new_retry_count = get_retry_count(job_id)
    
    return {
        "success": True, 
        "job_id": job_id, 
        "retry_count": new_retry_count,
        "status": "assigned",
        "message": f"Job reset for retry (attempt {new_retry_count})"
    }


def reset_job_for_retry(job_id: int, reset_error: bool = True) -> dict:
    """Reset a failed job for retry, optionally clearing error.
    
    This is a more thorough reset than retry_job(), also clearing
    the error field and resetting started_at/completed_at.
    
    Args:
        job_id: The job ID
        reset_error: If True, clear the error field
    
    Returns:
        dict with reset result
    """
    conn = get_connection()
    c = conn.cursor()
    
    now = datetime.now().isoformat()
    
    if reset_error:
        c.execute('''
            UPDATE jobs 
            SET status = 'assigned',
                started_at = NULL,
                completed_at = NULL,
                error = NULL,
                retry_count = retry_count + 1
            WHERE id = ?
        ''', (job_id,))
    else:
        c.execute('''
            UPDATE jobs 
            SET status = 'assigned',
                started_at = NULL,
                completed_at = NULL,
                retry_count = retry_count + 1
            WHERE id = ?
        ''', (job_id,))
    
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    
    if success:
        return {
            "success": True,
            "job_id": job_id,
            "status": "assigned",
            "retry_count": get_retry_count(job_id)
        }
    
    return {"success": False, "job_id": job_id, "error": "Job not found or update failed"}


if __name__ == '__main__':
    import json
    import argparse
    
    parser = argparse.ArgumentParser(description='Retry handler for jobs')
    parser.add_argument('--job-id', type=int, required=True, help='Job ID to check/retry')
    parser.add_argument('--check', action='store_true', help='Check if job can be retried')
    parser.add_argument('--do-retry', action='store_true', help='Perform the retry')
    parser.add_argument('--set-max-retries', type=int, metavar='N', help='Set max retries to N')
    
    args = parser.parse_args()
    
    from db import init_db
    init_db()
    
    if args.check:
        result = {"job_id": args.job_id, "should_retry": should_retry(args.job_id)}
        print(json.dumps(result, indent=2))
    
    elif args.set_max_retries:
        result = set_max_retries(args.job_id, args.set_max_retries)
        print(json.dumps(result, indent=2))
    
    elif args.do_retry:
        if should_retry(args.job_id):
            result = retry_job(args.job_id)
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps({
                "success": False,
                "job_id": args.job_id,
                "error": "Max retries exhausted"
            }, indent=2))
    
    else:
        # Show job status
        job = get_job(args.job_id)
        if job:
            print(json.dumps({
                "job_id": job['id'],
                "status": job['status'],
                "retry_count": job.get('retry_count', 0),
                "max_retries": job.get('max_retries', DEFAULT_MAX_RETRIES),
                "should_retry": should_retry(args.job_id)
            }, indent=2))
        else:
            print(json.dumps({"error": "Job not found"}, indent=2))
