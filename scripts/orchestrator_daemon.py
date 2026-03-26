#!/usr/bin/env python3
"""
orchestrator_daemon.py - Orchestrator polls for done jobs and handles review flow.

Usage:
    python3 orchestrator_daemon.py --once        # Run once (for cron)
    python3 orchestrator_daemon.py               # Run continuously

This script:
1. Polls for jobs with status='done'
2. Posts them to Zrise for human review
3. Or auto-handles if configured
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db import init_db, get_all_agents, get_jobs_for_agent


def get_done_jobs():
    """Get all done jobs across all agents."""
    agents = get_all_agents()
    done_jobs = []
    
    for agent in agents:
        jobs = get_jobs_for_agent(agent['id'], status='done')
        done_jobs.extend(jobs)
    
    # Sort by completed_at
    done_jobs.sort(key=lambda x: x.get('completed_at', ''), reverse=True)
    return done_jobs


def process_done_jobs(auto_post: bool = False):
    """Process all done jobs.
    
    Args:
        auto_post: If True, automatically post for review.
                   If False, just report.
    """
    done_jobs = get_done_jobs()
    
    if not done_jobs:
        return {"status": "no_done_jobs", "count": 0}
    
    results = []
    for job in done_jobs:
        job_id = job['id']
        task_id = job['task_id']
        agent_id = job['agent_id']
        
        # Import here to avoid circular
        from post_for_review import post_for_review
        
        if auto_post:
            result = post_for_review(job_id)
            results.append({
                "job_id": job_id,
                "task_id": task_id,
                "success": result['success'],
                "zrise_posted": result.get('zrise_posted', False)
            })
        else:
            results.append({
                "job_id": job_id,
                "task_id": task_id,
                "agent_id": agent_id,
                "status": job['status'],
                "completed_at": job['completed_at'],
                "action_needed": "post_for_review --job-id {}".format(job_id)
            })
    
    return {
        "status": "processed",
        "count": len(results),
        "jobs": results
    }


def main():
    parser = argparse.ArgumentParser(description='Orchestrator daemon - poll done jobs')
    parser.add_argument('--once', action='store_true', help='Run once and exit (for cron)')
    parser.add_argument('--auto-post', action='store_true', help='Auto-post for review without prompting')
    parser.add_argument('--poll-interval', type=int, default=60, help='Seconds between polls (default: 60)')
    
    args = parser.parse_args()
    
    init_db()
    
    if args.once:
        # Cron mode: poll once
        result = process_done_jobs(auto_post=args.auto_post)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Daemon mode: poll continuously
        print("🤖 Orchestrator daemon started")
        print(f"   Poll interval: {args.poll_interval}s")
        print(f"   Auto-post: {args.auto_post}")
        print()
        
        while True:
            result = process_done_jobs(auto_post=args.auto_post)
            
            if result['count'] > 0:
                print(f"[{time.strftime('%H:%M:%S')}] Found {result['count']} done jobs:")
                for job in result['jobs']:
                    if args.auto_post:
                        print(f"  - Job #{job['job_id']}: task={job['task_id']} → posted={job['zrise_posted']}")
                    else:
                        print(f"  - Job #{job['job_id']}: task={job['task_id']} ({job['agent_id']})")
            
            time.sleep(args.poll_interval)


if __name__ == '__main__':
    main()
