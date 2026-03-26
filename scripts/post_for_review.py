#!/usr/bin/env python3
"""
post_for_review.py - Post job result to Zrise for human review.

Usage:
    python3 post_for_review.py --job-id 4 --comment "Your review needed"
    
Workflow:
1. Read job result
2. Post result to Zrise task as comment
3. Update job status to 'pending_review'
4. Human responds: APPROVE or FEEDBACK
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from db import init_db, get_job, get_task_detail_path, get_tasks_dir, add_task_log, update_job_status


def format_review_message(job_id: int, job: dict, result_text: str, task_detail: dict = None) -> str:
    """Format result as review message for Zrise comment."""
    
    task_name = task_detail.get('name', f'Task {job["task_id"]}') if task_detail else f'Task {job["task_id"]}'
    
    lines = [
        f"🤖 **AI Execution Result - Review Required**",
        f"",
        f"**Job:** #{job_id}",
        f"**Task:** {task_name}",
        f"**Agent:** {job['agent_id']}",
        f"**Workflow:** {job['workflow']}",
        f"**Completed:** {job.get('completed_at', 'N/A')}",
        f"",
        f"---",
        f"",
        f"## 📝 Result:",
        f"",
    ]
    
    # Truncate result if too long (Zrise comment limits)
    if len(result_text) > 4000:
        lines.append(result_text[:4000])
        lines.append(f"\n... _(truncated, see full result in task details)_")
    else:
        lines.append(result_text)
    
    lines.extend([
        f"",
        f"---",
        f"",
        f"## ✅ Actions:",
        f"- **Approve** → I will finalize and mark task Done",
        f"- **Feedback** → I will re-run with your feedback",
        f"",
        f"_Reply with 'APPROVE' or 'FEEDBACK: <your comments>'_",
    ])
    
    return '\n'.join(lines)


def post_for_review(job_id: int, comment: str = None) -> dict:
    """Post job result to Zrise for human review."""
    
    job = get_job(job_id)
    if not job:
        return {"success": False, "error": f"Job {job_id} not found"}
    
    if job['status'] != 'done':
        return {"success": False, "error": f"Job {job_id} is not done (status: {job['status']})"}
    
    task_id = job['task_id']
    
    # Get result
    result_path = Path(job.get('result_path')) if job.get('result_path') else None
    if not result_path or not result_path.exists():
        result_path = get_tasks_dir() / ".jobs" / str(job_id) / "result.md"
    
    result_text = result_path.read_text(encoding='utf-8') if result_path and result_path.exists() else "No result"
    
    # Get task detail
    task_detail = None
    detail_path = get_task_detail_path(task_id)
    if detail_path.exists():
        task_detail = json.loads(detail_path.read_text(encoding='utf-8'))
    
    # Format message
    message = format_review_message(job_id, job, result_text, task_detail)
    
    # Add custom comment if provided
    if comment:
        message = f"{message}\n\n---\n\n**Note:** {comment}"
    
    message_id = None
    zrise_error = None
    
    # Post to Zrise
    try:
        from zrise_utils import connect_zrise
        db, uid, secret, models, url = connect_zrise()
        
        message_id = models.execute_kw(
            db, uid, secret, 'project.task', 'message_post',
            [[task_id]],
            {'body': message, 'message_type': 'comment'}
        )
    except Exception as e:
        zrise_error = str(e)
        print(f"⚠️ Zrise posting skipped: {zrise_error}")
    
    # Update job status regardless of Zrise result
    update_job_status(job_id, 'pending_review')
    
    # Log
    add_task_log(task_id, 'review_requested', 'orchestrator', {
        'job_id': job_id,
        'message_id': message_id,
        'comment': comment,
        'zrise_error': zrise_error
    })
    
    return {
        "success": True,
        "job_id": job_id,
        "task_id": task_id,
        "message_id": message_id,
        "status": "pending_review",
        "zrise_posted": message_id is not None
    }


def main():
    parser = argparse.ArgumentParser(description='Post job result to Zrise for review')
    parser.add_argument('--job-id', type=int, required=True, help='Job ID to post for review')
    parser.add_argument('--comment', type=str, help='Optional comment to add')
    
    args = parser.parse_args()
    
    init_db()
    
    result = post_for_review(args.job_id, args.comment)
    
    if result['success']:
        print(f"✅ Posted Job #{args.job_id} for review")
        print(f"   Task: {result['task_id']}")
        print(f"   Message ID: {result['message_id']}")
        print(f"   Status: {result['status']}")
    else:
        print(f"❌ Failed: {result.get('error')}")


if __name__ == '__main__':
    main()
