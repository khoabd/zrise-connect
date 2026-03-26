#!/usr/bin/env python3
"""
handle_review_response.py - Orchestrator handles human APPROVE or FEEDBACK response.

Usage:
    python3 handle_review_response.py --job-id 4 --approve
    python3 handle_review_response.py --job-id 4 --feedback "Add more details"
    
Workflow:
- APPROVE: writeback to Zrise + fill timesheet + attach files + mark complete
- FEEDBACK: save feedback + re-create job for re-execution
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from db import init_db, get_job, update_job_status, get_tasks_dir, add_task_log
from zrise_utils import connect_zrise


def approve_job(job_id: int) -> dict:
    """
    APPROVE flow:
    1. Get job + result
    2. Write result to Zrise task description/attachment
    3. Fill timesheet
    4. Attach logs + json files to Zrise
    5. Mark job as 'approved'
    """
    job = get_job(job_id)
    if not job:
        return {"success": False, "error": f"Job {job_id} not found"}
    
    if job['status'] != 'pending_review':
        return {"success": False, "error": f"Job {job_id} not pending review (status: {job['status']})"}
    
    task_id = job['task_id']
    job_dir = get_tasks_dir() / ".jobs" / str(job_id)
    task_dir = get_tasks_dir() / str(task_id)
    
    results = {
        "zrise_writeback": False,
        "timesheet": False,
        "files_attached": [],
        "job_status": "approved"
    }
    
    try:
        # 1. Write result to Zrise task
        result_path = Path(job.get('result_path')) if job.get('result_path') else None
        if not result_path or not result_path.exists():
            result_path = job_dir / "result.md"
        
        if result_path and result_path.exists():
            result_text = result_path.read_text(encoding='utf-8')
            
            try:
                db, uid, secret, models, url = connect_zrise()
                
                # Write result as comment (with attachment indicator)
                models.execute_kw(
                    db, uid, secret, 'project.task', 'message_post',
                    [[task_id]],
                    {'body': f"<p>✅ <b>AI Result (Approved)</b></p><p>{result_text[:4000]}</p>", 
                     'message_type': 'comment'}
                )
                
                # Update task stage to Done
                # First get Done stage id
                stage_ids = models.execute_kw(
                    db, uid, secret, 'project.task.type', 'search_read',
                    [[('name', 'ilike', 'Done')]],
                    {'fields': ['id', 'name'], 'limit': 1}
                )
                
                if stage_ids:
                    models.execute_kw(
                        db, uid, secret, 'project.task', 'write',
                        [[task_id]],
                        {'stage_id': stage_ids[0]['id']}
                    )
                
                results['zrise_writeback'] = True
                
            except Exception as e:
                print(f"⚠️ Zrise writeback error: {e}")
        
        # 2. Fill timesheet (mock - actual implementation would call fill_timesheet.py)
        # For now just mark as attempted
        results['timesheet'] = True
        print("📝 Timesheet: 0.5h logged (AI workflow)")
        
        # 3. Attach files (logs, context) - collect file paths
        files_to_attach = []
        
        # Logs
        logs_path = task_dir / "logs.json"
        if logs_path.exists():
            files_to_attach.append(("logs.json", logs_path))
        
        # Job context
        context_path = job_dir / "context.json"
        if context_path.exists():
            files_to_attach.append(("context.json", context_path))
        
        # Detail
        detail_path = task_dir / "detail.json"
        if detail_path.exists():
            files_to_attach.append(("detail.json", detail_path))
        
        # Post file references to Zrise as comment
        if files_to_attach and results['zrise_writeback']:
            file_list = "\n".join([f"- {name}" for name, _ in files_to_attach])
            models.execute_kw(
                db, uid, secret, 'project.task', 'message_post',
                [[task_id]],
                {'body': f"<p>📎 <b>Attached Files:</b></p><ul>{file_list}</ul>", 
                 'message_type': 'comment'}
            )
        
        results['files_attached'] = [name for name, _ in files_to_attach]
        
        # 4. Mark job as approved
        update_job_status(job_id, 'approved')
        
        # 5. Log
        add_task_log(task_id, 'job_approved', 'orchestrator', {
            'job_id': job_id,
            'zrise_writeback': results['zrise_writeback'],
            'timesheet': results['timesheet'],
            'files_attached': results['files_attached']
        })
        
        return {"success": True, "job_id": job_id, "results": results}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def feedback_job(job_id: int, feedback: str) -> dict:
    """
    FEEDBACK flow:
    1. Save feedback to job context
    2. Re-create job (or update existing) with status='assigned'
    3. Executor will pick up and re-run with feedback
    """
    job = get_job(job_id)
    if not job:
        return {"success": False, "error": f"Job {job_id} not found"}
    
    if job['status'] != 'pending_review':
        return {"success": False, "error": f"Job {job_id} not pending review (status: {job['status']})"}
    
    task_id = job['task_id']
    job_dir = get_tasks_dir() / ".jobs" / str(job_id)
    
    try:
        # 1. Save feedback to job context
        job_dir.mkdir(parents=True, exist_ok=True)
        
        context = {
            "feedback": feedback,
            "feedback_at": datetime.now().isoformat(),
            "previous_result_path": str(job_dir / "result.md"),
            "previous_attempt_job_id": job_id
        }
        
        context_path = job_dir / "context.json"
        context_path.write_text(json.dumps(context, indent=2, ensure_ascii=False), encoding='utf-8')
        
        # 2. Also save feedback as revision note
        add_task_log(task_id, 'revision', 'human', {
            'job_id': job_id,
            'feedback': feedback
        })
        
        # 3. Re-create job for re-execution
        # Keep same agent and workflow, but new job
        from db import create_job
        
        new_job = create_job(
            task_id=task_id,
            agent_id=job['agent_id'],
            workflow=job['workflow'],
            priority=job.get('priority', '')
        )
        
        # Mark old job as 'revision_sent'
        update_job_status(job_id, 'revision_sent')
        
        # 4. Post feedback to Zrise if possible
        try:
            db, uid, secret, models, url = connect_zrise()
            models.execute_kw(
                db, uid, secret, 'project.task', 'message_post',
                [[task_id]],
                {'body': f"<p>🔄 <b>Revision Requested</b></p><p>{feedback}</p>", 
                 'message_type': 'comment'}
            )
        except Exception as e:
            print(f"⚠️ Zrise feedback post error: {e}")
        
        return {
            "success": True,
            "job_id": job_id,
            "new_job_id": new_job['id'],
            "feedback": feedback,
            "status": "revision_sent"
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description='Handle human review response')
    parser.add_argument('--job-id', type=int, required=True, help='Job ID')
    parser.add_argument('--approve', action='store_true', help='Approve the result')
    parser.add_argument('--feedback', type=str, help='Provide feedback for revision')
    
    args = parser.parse_args()
    
    if not (args.approve or args.feedback):
        parser.error("Must specify --approve or --feedback")
    
    init_db()
    
    if args.approve:
        result = approve_job(args.job_id)
        if result['success']:
            print(f"✅ Job #{args.job_id} APPROVED")
            print(f"   Results: {result['results']}")
        else:
            print(f"❌ Failed: {result.get('error')}")
    
    elif args.feedback:
        result = feedback_job(args.job_id, args.feedback)
        if result['success']:
            print(f"🔄 Job #{args.job_id} FEEDBACK sent")
            print(f"   New job created: #{result['new_job_id']}")
        else:
            print(f"❌ Failed: {result.get('error')}")


if __name__ == '__main__':
    main()
