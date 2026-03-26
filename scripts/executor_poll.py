#!/usr/bin/env python3
"""
executor_poll.py - Executor agent polls for assigned jobs and executes them.

Usage:
    python3 executor_poll.py --agent eng-agent
    
This script is shared by all executor agents. Each agent:
1. Polls jobs where agent_id = me AND status = 'assigned'
2. Claims the job (sets status = 'in_progress')
3. Executes in a resumable session
4. Writes result and marks job done (or failed)

For resume: If job has previous context (failed/revised), session is reused
to maintain memory of what was attempted before.
"""

import argparse
import json
import logging
import sys
import os
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
    get_jobs_for_agent,
    claim_job,
    complete_job,
    fail_job,
    get_job,
    get_task_detail_path,
    get_tasks_dir,
    init_db,
    update_heartbeat,
)


def get_job_context(job_id: int) -> dict:
    """Load context for a job (for resume).
    
    Returns:
        dict with keys: previous_result, previous_attempts, feedback, session_key
    Returns empty dict if no previous context.
    """
    context = {
        "previous_result": None,
        "previous_attempts": 0,
        "feedback": None,
        "session_key": None
    }
    
    job = get_job(job_id)
    if not job:
        return context
    
    task_id = job['task_id']
    job_dir = get_tasks_dir() / ".jobs" / str(job_id)
    task_dir = get_tasks_dir() / str(task_id)
    
    # Count previous attempts
    context["previous_attempts"] = job.get('attempts', 0)
    
    # Session key for resume (use same session to maintain memory)
    context["session_key"] = f"executor-{job['agent_id']}-{job_id}"
    
    # Load previous result if exists
    result_path = job_dir / "result.md"
    if result_path.exists():
        context["previous_result"] = result_path.read_text(encoding='utf-8')
    
    # Load feedback from task comments or job.error
    if job.get('error'):
        context["feedback"] = job['error']
    
    # Also check task logs for feedback
    logs_path = task_dir / "logs.json"
    if logs_path.exists():
        logs = json.loads(logs_path.read_text(encoding='utf-8'))
        for log in reversed(logs):
            if log.get('event') == 'revision' and log.get('details', {}).get('feedback'):
                context["feedback"] = log['details']['feedback']
                break
    
    return context


def save_job_context(job_id: int, result: str, error: str = None) -> Path:
    """Save job execution context for future resume."""
    job_dir = get_tasks_dir() / ".jobs" / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Save result
    result_path = job_dir / "result.md"
    result_path.write_text(result or '', encoding='utf-8')
    
    # Save error if any
    if error:
        error_path = job_dir / "error.txt"
        error_path.write_text(error, encoding='utf-8')
    
    return result_path


def load_task_for_execution(task_id: int) -> dict:
    """Load task details for execution."""
    # Load from detail.json
    detail_path = get_task_detail_path(task_id)
    if detail_path.exists():
        return json.loads(detail_path.read_text(encoding='utf-8'))
    
    # Fallback: minimal task info
    return {"task_id": task_id, "name": f"Task {task_id}"}


def build_execution_prompt(job: dict, task: dict, context: dict) -> str:
    """Build prompt for executor agent session.
    
    Includes:
    - Task info
    - Workflow type
    - Previous result (if resume)
    - Feedback (if revision)
    """
    agent_id = job['agent_id']
    workflow = job['workflow']
    task_id = job['task_id']
    
    prompt_parts = [
        f"# Execution Agent: {agent_id}",
        f"",
        f"## Task ID: {task_id}",
        f"## Workflow: {workflow}",
        f"## Task Name: {task.get('name', 'N/A')}",
        f"",
    ]
    
    # Add description if available
    desc = task.get('description', '')
    if desc:
        prompt_parts.append(f"## Description")
        prompt_parts.append(f"{desc[:2000]}")
        prompt_parts.append("")
    
    # Add previous context if resuming
    if context.get('previous_result'):
        prompt_parts.append("## Previous Attempt Result:")
        prompt_parts.append("(This was the output from the previous attempt)")
        prompt_parts.append(context['previous_result'][:3000])
        prompt_parts.append("")
    
    if context.get('feedback'):
        prompt_parts.append("## Feedback / Revision Request:")
        prompt_parts.append(context['feedback'])
        prompt_parts.append("")
    
    prompt_parts.extend([
        "## Instructions",
        f"- Execute this {workflow} task based on the information above.",
        f"- Output your final result in Markdown format.",
        f"- When done, save result to:",
        f"  `{get_tasks_dir() / str(task_id) / 'result.md'}`",
        "",
        "## Important Notes",
        "- Work in the task's context, apply the feedback if provided.",
        "- If this is a revision, only change what needs to be fixed.",
        "- Be concise but thorough.",
    ])
    
    return '\n'.join(prompt_parts)


def generate_session_uuid(job_id: int) -> str:
    """Generate deterministic UUID from job_id for session continuity.
    
    Same job_id always generates same UUID, enabling session resume.
    """
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"executor-job-{job_id}"))


def execute_in_session(session_key: str, prompt: str, agent_id: str, job_id: int = None, heartbeat_interval: int = 60) -> tuple:
    """Execute task via Claude Code CLI (resumable session).
    
    Session is keyed by job_id (deterministic UUID) so executor can resume
    a job later and get the same session context.
    
    Heartbeat is updated every heartbeat_interval seconds during execution
    to signal to the watchdog that the executor is still alive.
    
    Args:
        session_key: Key for session continuity
        prompt: The execution prompt
        agent_id: Agent ID for context
        job_id: Job ID for heartbeat tracking
        heartbeat_interval: Seconds between heartbeat updates (default: 60)
    
    Returns:
        (result_text, error)
    """
    import subprocess
    import threading
    
    # Generate deterministic session ID for this job
    session_id = generate_session_uuid(job_id) if job_id else session_key
    
    # Heartbeat tracker
    heartbeat_stop = threading.Event()
    
    def heartbeat_worker():
        """Background thread to update heartbeat during execution."""
        while not heartbeat_stop.is_set():
            heartbeat_stop.wait(timeout=heartbeat_interval)
            if job_id and not heartbeat_stop.is_set():
                try:
                    update_heartbeat(job_id)
                    logger.debug(f"[{agent_id}] Heartbeat updated for job {job_id}")
                except Exception as e:
                    logger.warning(f"[{agent_id}] Failed to update heartbeat: {e}")
    
    # Start heartbeat thread
    heartbeat_thread = None
    if job_id:
        heartbeat_thread = threading.Thread(target=heartbeat_worker, daemon=True)
        heartbeat_thread.start()
    
    # Build prompt
    cc_prompt = f"""{prompt}

When complete:
1. Write your final output to: {get_tasks_dir() / '__latest_result.md'}
2. Reply with 'DONE' followed by brief summary
"""
    
    # Use Claude Code with session ID (must be UUID)
    cmd = [
        '/Users/khoabui/.local/bin/claude',
        '--print',
        '--permission-mode', 'bypassPermissions',
        '--session-id', session_id,
        cc_prompt
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes
            cwd=str(get_tasks_dir()),
        )
        
        # Stop heartbeat
        heartbeat_stop.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2)
        
        if result.returncode != 0:
            return None, f"Claude Code error: {result.stderr[-500:]}"
        
        return result.stdout.strip(), None
        
    except subprocess.TimeoutExpired:
        heartbeat_stop.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2)
        return None, "Execution timeout (5 min)"
    except Exception as e:
        heartbeat_stop.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2)
        return None, f"Execution error: {e}"


def execute_job(job_id: int) -> dict:
    """Execute a single job.
    
    Returns:
        dict with keys: success, result/error, output_path
    """
    job = get_job(job_id)
    if not job:
        return {"success": False, "error": f"Job {job_id} not found"}
    
    task_id = job['task_id']
    agent_id = job['agent_id']
    
    # ⚠️ SECURITY CHECK: Verify plan was approved before executing
    # Load task detail to check for plan_approved_at
    detail_path = get_task_detail_path(task_id)
    if detail_path.exists():
        detail = json.loads(detail_path.read_text(encoding='utf-8'))
        if not detail.get('plan_approved_at'):
            return {
                "success": False,
                "error": f"Task {task_id}: Plan chưa được approve! Không được phép execute."
            }
    
    # Claim job
    claim_result = claim_job(job_id)
    if not claim_result.get('claimed'):
        return {"success": False, "error": "Failed to claim job (already claimed?)"}
    
    # Load context for resume
    context = get_job_context(job_id)
    
    # Load task details
    task = load_task_for_execution(task_id)
    
    # Build execution prompt
    prompt = build_execution_prompt(job, task, context)
    
    # Session key for this execution (resumable via deterministic UUID)
    session_key = context.get('session_key') or f"executor-{agent_id}-{job_id}"
    
    # Execute in session (pass job_id for deterministic UUID)
    result_text, error = execute_in_session(session_key, prompt, agent_id, job_id=job_id)
    
    if error:
        # Mark job as failed
        fail_job(job_id, error)
        # Save error context
        save_job_context(job_id, result_text, error)
        return {"success": False, "error": error, "result": result_text}
    
    # Save successful result
    task_dir = get_tasks_dir() / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    result_path = task_dir / "result.md"
    result_path.write_text(result_text or '', encoding='utf-8')
    
    # Save to job context for resume
    save_job_context(job_id, result_text)
    
    # Mark job as done
    complete_job(job_id, str(result_path))
    
    return {
        "success": True,
        "result": result_text,
        "output_path": str(result_path),
        "session_key": session_key
    }


def poll_and_execute(agent_id: str, limit: int = 5) -> dict:
    """Poll for jobs assigned to this agent and execute them.
    
    Args:
        agent_id: The agent ID to poll for
        limit: Max number of jobs to process in one poll
    
    Returns:
        dict with execution results
    """
    # Get assigned jobs
    jobs = get_jobs_for_agent(agent_id, status='assigned')
    
    if not jobs:
        return {
            "agent_id": agent_id,
            "status": "no_jobs",
            "jobs_processed": 0
        }
    
    # Limit jobs to process
    jobs = jobs[:limit]
    
    results = []
    for job in jobs:
        job_id = job['id']
        task_id = job['task_id']
        
        logger.info(f"[{agent_id}] Processing job {job_id}: task {task_id} ({job['workflow']})")
        
        result = execute_job(job_id)
        results.append({
            "job_id": job_id,
            "task_id": task_id,
            **result
        })
        
        if result['success']:
            logger.info(f"[{agent_id}] Job {job_id} completed successfully")
        else:
            logger.error(f"[{agent_id}] Job {job_id} failed: {result.get('error')}")
    
    return {
        "agent_id": agent_id,
        "status": "completed",
        "jobs_processed": len(results),
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description='Executor agent poll and execute')
    parser.add_argument('--agent', required=True, help='Agent ID (e.g., eng-agent, sales-agent)')
    parser.add_argument('--limit', type=int, default=5, help='Max jobs per poll (default: 5)')
    parser.add_argument('--once', action='store_true', help='Poll once and exit (for cron)')
    
    args = parser.parse_args()
    
    # Init database
    init_db()
    
    if args.once:
        # Cron mode: poll once and exit
        result = poll_and_execute(args.agent, limit=args.limit)
        logger.info(f" Poll result: {json.dumps(result, indent=2, ensure_ascii=False)}")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        # Daemon mode: poll continuously
        import time
        logger.info(f"[{args.agent}] Starting executor poll (daemon mode)")
        logger.info(f"[{args.agent}] Polling every 60 seconds...")

        while True:
            result = poll_and_execute(args.agent, limit=args.limit)
            if result['jobs_processed'] > 0:
                logger.info(f"[{args.agent}] Processed {result['jobs_processed']} jobs")

            time.sleep(60)


if __name__ == '__main__':
    main()
