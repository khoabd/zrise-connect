#!/usr/bin/env python3
"""
watchdog.py - Monitor executor jobs for timeout.

Usage:
    python3 watchdog.py --once  # For cron (run every 5-10 min)
    python3 watchdog.py          # Daemon mode (continuous monitoring)
    
The watchdog monitors jobs stuck in 'in_progress' status and handles
them based on configured action (notify, retry, or fail).

Timeout Detection:
- Default timeout: 30 minutes (no heartbeat update)
- Heartbeat is updated by executor during long-running tasks
- Jobs without heartbeat for > timeout_minutes are considered stuck

Actions on timeout:
- 'notify': Send Telegram alert (default)
- 'retry': Reset job to 'assigned' for re-execution  
- 'fail': Mark job as failed

CRON EXAMPLE (every 5 minutes):
    */5 * * * * cd ~/.openclaw/workspace-ai-company/skills/zrise-connect/scripts && python3 watchdog.py --once
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add scripts dir to path for db imports
sys.path.insert(0, str(Path(__file__).parent))

from db import (
    get_timed_out_jobs,
    get_job,
    update_job_status,
    init_db,
)

# Default timeout in minutes
DEFAULT_TIMEOUT_MINUTES = 30

# Telegram config (loaded from environment or config)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')


def send_telegram_message(message: str) -> bool:
    """Send alert message via Telegram bot.
    
    Args:
        message: The alert message to send
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured, skipping notification")
        return False
    
    import urllib.request
    import urllib.parse
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(data).encode('utf-8'),
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def detect_timed_out_jobs(timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES) -> list:
    """Find jobs stuck in 'in_progress' too long.
    
    Uses heartbeat_at to determine if job is truly stuck. A job is
    considered timed out if:
    1. status = 'in_progress'
    2. heartbeat_at < now - timeout_minutes
    
    Args:
        timeout_minutes: Minutes after which a job is considered timed out
    
    Returns:
        List of timed out job dicts
    """
    return get_timed_out_jobs(timeout_minutes)


def handle_timeout(job_id: int, action: str = 'notify') -> dict:
    """
    Handle timed out job.
    
    Args:
        job_id: The job ID to handle
        action: How to handle the timeout:
            - 'notify': Send Telegram alert only
            - 'retry': Reset to assigned for re-execution
            - 'fail': Mark as failed
    
    Returns:
        dict with action result
    """
    job = get_job(job_id)
    if not job:
        return {"success": False, "error": f"Job {job_id} not found"}
    
    task_id = job['task_id']
    agent_id = job['agent_id']
    workflow = job['workflow']
    started_at = job.get('started_at', 'unknown')
    heartbeat_at = job.get('heartbeat_at', 'none')
    retry_count = job.get('retry_count', 0)
    max_retries = job.get('max_retries', 3)
    
    # Build alert message
    message = (
        f"⚠️ <b>Job Timeout Detected</b>\n\n"
        f"Job ID: <code>{job_id}</code>\n"
        f"Task ID: <code>{task_id}</code>\n"
        f"Agent: <code>{agent_id}</code>\n"
        f"Workflow: {workflow}\n"
        f"Started: {started_at}\n"
        f"Last heartbeat: {heartbeat_at}\n"
        f"Retry count: {retry_count}/{max_retries}\n\n"
    )
    
    if action == 'notify':
        # Just notify, don't change job state
        message += "Action: <b>NOTIFIED</b> (no change to job status)"
        send_telegram_message(message)
        return {"success": True, "action": "notify", "job_id": job_id}
    
    elif action == 'retry':
        # Check if retries exhausted
        if retry_count >= max_retries:
            message += f"Action: <b>FAILED</b> (max retries {max_retries} exhausted)"
            update_job_status(job_id, 'failed')
            send_telegram_message(message)
            return {
                "success": True, 
                "action": "fail", 
                "reason": "max_retries_exhausted",
                "job_id": job_id
            }
        
        # Reset to assigned for retry
        update_job_status(job_id, 'assigned')
        message += f"Action: <b>RETRY</b> (attempt {retry_count + 1}/{max_retries})"
        send_telegram_message(message)
        return {
            "success": True, 
            "action": "retry", 
            "retry_count": retry_count + 1,
            "job_id": job_id
        }
    
    elif action == 'fail':
        # Mark as failed
        update_job_status(job_id, 'failed')
        message += "Action: <b>FAILED</b>"
        send_telegram_message(message)
        return {"success": True, "action": "fail", "job_id": job_id}
    
    else:
        return {"success": False, "error": f"Unknown action: {action}"}


def process_timeouts(timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES, 
                     action: str = 'notify',
                     dry_run: bool = False) -> dict:
    """
    Process all timed out jobs.
    
    Args:
        timeout_minutes: Minutes after which a job is considered timed out
        action: How to handle each timeout ('notify', 'retry', 'fail')
        dry_run: If True, don't actually take action, just report
    
    Returns:
        dict with processing results
    """
    timed_out_jobs = detect_timed_out_jobs(timeout_minutes)
    
    if not timed_out_jobs:
        return {
            "status": "ok",
            "timed_out_count": 0,
            "processed": 0
        }
    
    results = []
    for job in timed_out_jobs:
        job_id = job['id']
        task_id = job['task_id']
        agent_id = job['agent_id']
        
        logger.warning(f"[WATCHDOG] Job {job_id} timed out: task={task_id}, agent={agent_id}")
        
        if dry_run:
            results.append({
                "job_id": job_id,
                "task_id": task_id,
                "action": "would_" + action,
                "dry_run": True
            })
        else:
            result = handle_timeout(job_id, action)
            results.append({
                "job_id": job_id,
                "task_id": task_id,
                **result
            })
    
    return {
        "status": "processed",
        "timed_out_count": len(timed_out_jobs),
        "processed": len(results),
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description='Watchdog - Monitor executor job timeouts')
    parser.add_argument('--once', action='store_true', 
                       help='Run once and exit (for cron)')
    parser.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT_MINUTES,
                       help=f'Timeout in minutes (default: {DEFAULT_TIMEOUT_MINUTES})')
    parser.add_argument('--action', choices=['notify', 'retry', 'fail'], 
                       default='notify',
                       help='Action on timeout (default: notify)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without doing it')
    parser.add_argument('--interval', type=int, default=60,
                       help='Check interval in seconds (daemon mode, default: 60)')
    
    args = parser.parse_args()
    
    # Init database
    init_db()
    
    if args.once:
        # Cron mode: check once and exit
        logger.info(f"[WATCHDOG] Checking for jobs timed out > {args.timeout} min...")
        result = process_timeouts(
            timeout_minutes=args.timeout,
            action=args.action,
            dry_run=args.dry_run
        )
        
        if result['timed_out_count'] > 0:
            logger.warning(f"[WATCHDOG] Found {result['timed_out_count']} timed out jobs")
            for r in result.get('results', []):
                logger.info(f"  - Job {r.get('job_id')}: {r.get('action', 'unknown')}")
        else:
            logger.info("[WATCHDOG] No timed out jobs found")
        
        print(json.dumps(result, indent=2, default=str))
        
    else:
        # Daemon mode: monitor continuously
        logger.info(f"[WATCHDOG] Starting watchdog daemon (interval: {args.interval}s, timeout: {args.timeout}min)")
        
        while True:
            result = process_timeouts(
                timeout_minutes=args.timeout,
                action=args.action
            )
            
            if result['timed_out_count'] > 0:
                logger.warning(f"[WATCHDOG] Processed {result['processed']} timed out jobs")
            
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
