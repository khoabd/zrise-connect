#!/usr/bin/env python3
"""
orchestrator_review.py - Orchestrator reads done jobs and prepares for human review.

Usage:
    python3 orchestrator_review.py --list-done          # List all done jobs
    python3 orchestrator_review.py --job-id 4 --details  # Get details of specific job
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from db import init_db, get_all_agents, get_job, get_jobs_for_agent
from db import get_tasks_dir


def get_job_result(job_id: int) -> dict:
    """Get full result of a completed job."""
    job = get_job(job_id)
    if not job:
        return {"error": f"Job {job_id} not found"}
    
    task_id = job['task_id']
    job_dir = get_tasks_dir() / ".jobs" / str(job_id)
    task_dir = get_tasks_dir() / str(task_id)
    
    result = {
        "job": job,
        "task_id": task_id,
        "agent_id": job['agent_id'],
        "workflow": job['workflow'],
        "status": job['status'],
        "completed_at": job['completed_at'],
    }
    
    # Read result.md
    result_path = job.get('result_path') or (job_dir / "result.md")
    if Path(result_path).exists():
        result["result_text"] = Path(result_path).read_text(encoding='utf-8')
    else:
        result["result_text"] = None
    
    # Read task detail
    detail_path = task_dir / "detail.json"
    if detail_path.exists():
        result["task_detail"] = json.loads(detail_path.read_text(encoding='utf-8'))
    
    # Read logs
    logs_path = task_dir / "logs.json"
    if logs_path.exists():
        result["logs"] = json.loads(logs_path.read_text(encoding='utf-8'))
    
    # Read job context
    context_path = job_dir / "context.json"
    if context_path.exists():
        result["context"] = json.loads(context_path.read_text(encoding='utf-8'))
    
    return result


def list_done_jobs() -> list:
    """List all jobs with status='done'."""
    agents = get_all_agents()
    done_jobs = []
    
    for agent in agents:
        jobs = get_jobs_for_agent(agent['id'], status='done')
        done_jobs.extend(jobs)
    
    # Sort by completed_at descending
    done_jobs.sort(key=lambda x: x.get('completed_at', ''), reverse=True)
    
    return done_jobs


def format_job_summary(job: dict, result_data: dict = None) -> str:
    """Format job as readable summary."""
    lines = [
        f"📋 **Job #{job['id']}** - Task {job['task_id']}",
        f"   Agent: {job['agent_id']}",
        f"   Workflow: {job['workflow']}",
        f"   Status: ✅ {job['status']}",
        f"   Completed: {job.get('completed_at', 'N/A')}",
    ]
    
    if result_data and result_data.get('task_detail'):
        td = result_data['task_detail']
        lines.append(f"   Task: {td.get('name', 'N/A')}")
    
    if job.get('result_path'):
        lines.append(f"   Result: {job['result_path']}")
    
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Orchestrator review - read done jobs')
    parser.add_argument('--list-done', action='store_true', help='List all done jobs')
    parser.add_argument('--job-id', type=int, help='Get details of specific job')
    parser.add_argument('--details', action='store_true', help='Show full details (with result text)')
    
    args = parser.parse_args()
    
    init_db()
    
    if args.list_done:
        print("📋 Done Jobs:")
        jobs = list_done_jobs()
        if not jobs:
            print("   No done jobs found.")
        else:
            for job in jobs[:20]:  # Limit to 20
                print(format_job_summary(job))
    
    elif args.job_id:
        print(f"📋 Job #{args.job_id} Details:")
        result = get_job_result(args.job_id)
        
        if result.get('error'):
            print(f"   ❌ {result['error']}")
            return
        
        print(format_job_summary(result['job'], result))
        print()
        
        if args.details:
            if result.get('result_text'):
                print("📝 **Result:**")
                print(result['result_text'][:2000])  # First 2000 chars
                if len(result['result_text']) > 2000:
                    print(f"... (truncated, full in {result['job'].get('result_path')})")
                print()
            
            if result.get('logs'):
                print(f"📜 **Logs ({len(result['logs'])} entries):**")
                for log in result['logs'][-5:]:  # Last 5 logs
                    print(f"   - [{log.get('timestamp', '')}] {log.get('event', '')}")
                    if log.get('details'):
                        for k, v in log['details'].items():
                            print(f"       {k}: {str(v)[:100]}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
