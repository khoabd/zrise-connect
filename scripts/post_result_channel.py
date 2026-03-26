#!/usr/bin/env python3
"""
post_result_channel.py - Post AI execution result via OpenClaw channel routing.

Displays execution result with APPROVE/FEEDBACK inline buttons.
Uses OpenClaw's native routing (Telegram/Discord/Slack) based on config.
"""

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from post_channel import send_channel_message, get_default_target, format_text
from db import init_db, get_job, get_tasks_dir, get_task_detail_path, add_task_log


def format_result_message(
    job_id: int,
    job: dict,
    result_text: str,
    task_detail: dict = None
) -> str:
    """
    Format execution result as message.
    
    Args:
        job_id: Job ID
        job: Job dict from database
        result_text: Result text/content
        task_detail: Optional task detail for richer context
    
    Returns:
        Formatted message string
    """
    task_id = job.get('task_id', '?')
    task_name = task_detail.get('name', f'Task #{task_id}') if task_detail else f'Task #{task_id}'
    agent_id = job.get('agent_id', 'coder')
    workflow = job.get('workflow', 'standard')
    status = job.get('status', 'done')
    completed_at = job.get('completed_at', 'N/A')
    
    # Status emoji
    status_emoji = {
        'done': '✅',
        'success': '✅',
        'approved': '✅',
        'error': '❌',
        'failed': '❌',
        'pending_review': '⏳',
    }.get(status, '📋')
    
    # Build message
    lines = [
        f"{status_emoji} *AI Execution Result - Review Required*",
        "",
        f"🏷️ *Job:* #{job_id} | 📋 *Task:* #{task_id}",
        f"📝 *Task:* {task_name}",
        f"🤖 *Agent:* {agent_id}",
        f"⚙️ *Workflow:* {workflow}",
        f"📊 *Status:* {status.upper()}",
        f"⏰ *Completed:* {completed_at}",
        "",
        "---",
        "",
    ]
    
    # Add result
    lines.append("📝 *Result:*")
    
    # Truncate result if too long
    if len(result_text) > 3000:
        lines.append(result_text[:3000])
        lines.append("\n... _(result truncated, see full output in logs)_")
    else:
        lines.append(result_text)
    
    lines.extend([
        "",
        "---",
        "",
        "_Review the result above and respond with:*",
        "• *APPROVE* → Finalize and mark task Done",
        "• *FEEDBACK* → Request revisions",
    ])
    
    return '\n'.join(lines)


def post_result_to_channel(job_id: int, target: str = None, channel: str = None) -> dict:
    """
    Post execution result via OpenClaw channel routing for human review.
    
    Args:
        job_id: Job ID to post result for
        target: Channel target (chat ID, user, etc.). Uses default from config if not provided
        channel: Specific channel to use (default: auto-detect from config)
    
    Returns:
        {"success": True, "target": ..., "job_id": ..., "task_id": ...} or error dict
    """
    try:
        init_db()
        
        # Get target (chat ID)
        if not target:
            target = get_default_target()
        
        if not target:
            return {
                "success": False,
                "error": "No target provided and default target not configured"
            }
        
        # Get job
        job = get_job(job_id)
        if not job:
            return {
                "success": False,
                "error": f"Job #{job_id} not found"
            }
        
        # Get result text
        result_text = "No result available"
        
        result_path = Path(job.get('result_path')) if job.get('result_path') else None
        if not result_path or not result_path.exists():
            result_path = get_tasks_dir() / ".jobs" / str(job_id) / "result.md"
        
        if result_path and result_path.exists():
            result_text = result_path.read_text(encoding='utf-8')
        else:
            # Try to get from job's error field or build from logs
            if job.get('error'):
                result_text = f"❌ Error: {job['error']}"
        
        # Get task detail
        task_detail = None
        task_id = job.get('task_id')
        if task_id:
            detail_path = get_task_detail_path(task_id)
            if detail_path.exists():
                try:
                    task_detail = json.loads(detail_path.read_text(encoding='utf-8'))
                except:
                    pass
        
        # Format message
        text = format_result_message(job_id, job, result_text, task_detail)
        
        # Format text for channel
        text = format_text(text)
        
        # Build buttons - APPROVE and FEEDBACK
        buttons = [
            [
                {"text": "✅ APPROVE", "callback_data": f"approve_{job_id}", "style": "success"},
                {"text": "💬 FEEDBACK", "callback_data": f"feedback_{job_id}", "style": "primary"},
            ]
        ]
        
        # Send message via OpenClaw channel routing
        result = send_channel_message(
            text=text,
            buttons=buttons,
            channel=channel,
            target=target,
            parse_mode="Markdown"
        )
        
        if result.get('success'):
            # Log to task
            if task_id:
                add_task_log(
                    task_id, 'result_posted_channel', 'coder',
                    {
                        'job_id': job_id,
                        'target': target,
                        'channel': channel,
                        'status': job.get('status'),
                        'message_preview': text[:200],
                    }
                )
            
            return {
                "success": True,
                "target": target,
                "channel": channel,
                "job_id": job_id,
                "task_id": task_id,
                "message_preview": text[:100],
            }
        else:
            return result
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "target": target,
        }


def main():
    """CLI for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Post result via OpenClaw channel')
    parser.add_argument('--job-id', type=int, required=True, help='Job ID')
    parser.add_argument('--target', type=str, help='Channel target (chat ID, user, etc.)')
    parser.add_argument('--channel', type=str, help='Specific channel (telegram, discord, slack)')
    
    args = parser.parse_args()
    
    result = post_result_to_channel(args.job_id, target=args.target, channel=args.channel)
    
    if result.get('success'):
        print(f"✅ Posted result for Job #{args.job_id} via OpenClaw channel")
        print(f"   Target: {result.get('target')}")
        print(f"   Channel: {result.get('channel') or 'auto'}")
        print(f"   Task ID: {result.get('task_id')}")
    else:
        print(f"❌ Failed: {result.get('error')}")


if __name__ == '__main__':
    main()
