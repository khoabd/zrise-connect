#!/usr/bin/env python3
"""
post_plan_to_telegram.py - Post AI execution plan to Telegram for human review.

Displays the execution plan with APPROVE/FEEDBACK inline buttons.
Uses OpenClaw's native channel routing.
"""

import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))

from post_channel import send_channel_message, get_default_target, format_text
from db import init_db, get_job, get_task_detail_path, add_task_log


def format_plan_message(plan: dict, job_id: int, task_detail: dict = None) -> str:
    """
    Format execution plan as Telegram message.
    
    Args:
        plan: Plan dict with keys: task_id, task_name, agent_id, steps, approach
        job_id: Job ID for reference
        task_detail: Optional task detail dict
    
    Returns:
        Formatted message string
    """
    task_id = plan.get('task_id', '?')
    task_name = plan.get('task_name') or task_detail.get('name', f'Task #{task_id}') if task_detail else f'Task #{task_id}'
    agent_id = plan.get('agent_id', 'coder')
    steps = plan.get('steps', [])
    approach = plan.get('approach', 'Standard execution')
    priority = plan.get('priority', '')
    
    # Build message
    lines = [
        "🤖 *AI Execution Plan - Review Required*",
        "",
        f"📋 *Task:* #{task_id} - {task_name}",
        f"🤖 *Agent:* {agent_id}",
        f"📊 *Priority:* {priority or 'Normal'}",
        "",
        "---",
        "",
        "📝 *Approach:*",
        f"{approach}",
        "",
    ]
    
    # Add steps if available
    if steps:
        lines.append("📌 *Execution Steps:*")
        for i, step in enumerate(steps[:10], 1):  # Limit to 10 steps
            step_text = step.get('description') or step.get('name') or str(step)
            lines.append(f"  {i}. {step_text}")
        if len(steps) > 10:
            lines.append(f"  ... and {len(steps) - 10} more steps")
        lines.append("")
    
    # Add context hints if available
    context = plan.get('context', {})
    if context:
        hints = context.get('hints', [])
        files = context.get('files', [])
        if hints:
            lines.append("💡 *Context Hints:*")
            for hint in hints[:3]:
                lines.append(f"  • {hint}")
            lines.append("")
        if files:
            lines.append("📁 *Relevant Files:*")
            for f in files[:5]:
                lines.append(f"  • `{f}`")
            lines.append("")
    
    lines.extend([
        "---",
        "",
        "_Review the plan above and respond with:*",
        "• *APPROVE* → Execute as planned",
        "• *FEEDBACK* → Provide corrections",
    ])
    
    return '\n'.join(lines)


def post_plan_to_telegram(plan: dict, target: str = None, job_id: int = None) -> dict:
    """
    Post execution plan to Telegram for human review.
    
    Args:
        plan: Plan dict with keys: task_id, task_name, agent_id, steps, approach
        target: Telegram chat ID (uses default from config if not provided)
        job_id: Optional job ID for tracking
    
    Returns:
        {"success": True, "target": ..., "job_id": ...} or error dict
    
    Example plan structure:
        {
            "task_id": 42174,
            "task_name": "Implement login feature",
            "agent_id": "coder",
            "approach": "Create Python script to handle auth",
            "steps": [
                {"description": "Create auth module"},
                {"description": "Add unit tests"},
            ],
            "priority": "high"
        }
    """
    try:
        init_db()
        
        # Get target
        if not target:
            target = get_default_target()
        
        if not target:
            return {
                "success": False,
                "error": "No target provided and default target not configured"
            }
        
        # Get job_id if not provided (try to find pending job for this task)
        if not job_id:
            task_id = plan.get('task_id')
            if task_id:
                job = get_job(task_id=task_id, status='pending')
                if job:
                    job_id = job['id']
        
        job_id_str = str(job_id) if job_id else "new"
        
        # Get task detail for richer message
        task_detail = None
        task_id = plan.get('task_id')
        if task_id:
            detail_path = get_task_detail_path(task_id)
            if detail_path.exists():
                try:
                    task_detail = json.loads(detail_path.read_text(encoding='utf-8'))
                except:
                    pass
        
        # Format message
        text = format_plan_message(plan, job_id or 0, task_detail)
        
        # Format text for channel (escape special chars, truncate)
        text = format_text(text)
        
        # Build buttons - APPROVE and FEEDBACK
        buttons = [
            [
                {"text": "✅ APPROVE", "callback_data": f"approve_{job_id_str}", "style": "success"},
                {"text": "💬 FEEDBACK", "callback_data": f"feedback_{job_id_str}", "style": "primary"},
            ]
        ]
        
        # Send message via OpenClaw channel routing
        result = send_channel_message(
            text=text,
            buttons=buttons,
            target=target,
            parse_mode="Markdown"
        )
        
        if result.get('success'):
            # Log to task
            if task_id:
                add_task_log(
                    task_id, 'plan_posted_telegram', 'coder',
                    {
                        'job_id': job_id,
                        'target': target,
                        'message_preview': text[:200],
                    }
                )
            
            return {
                "success": True,
                "target": target,
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
    
    parser = argparse.ArgumentParser(description='Post plan to Telegram')
    parser.add_argument('--target', type=str, help='Telegram chat ID')
    parser.add_argument('--job-id', type=int, help='Job ID')
    parser.add_argument('--task-id', type=int, help='Task ID')
    parser.add_argument('--task-name', type=str, default='Test Task', help='Task name')
    parser.add_argument('--approach', type=str, default='Standard approach', help='Execution approach')
    
    args = parser.parse_args()
    
    # Build test plan
    test_plan = {
        "task_id": args.task_id or 99999,
        "task_name": args.task_name,
        "agent_id": "coder",
        "approach": args.approach,
        "steps": [
            {"description": "Step 1: Analyze requirements"},
            {"description": "Step 2: Implement feature"},
            {"description": "Step 3: Write tests"},
            {"description": "Step 4: Create PR"},
        ],
        "priority": "normal",
    }
    
    result = post_plan_to_telegram(test_plan, target=args.target, job_id=args.job_id)
    
    if result.get('success'):
        print(f"✅ Posted plan to Telegram")
        print(f"   Target: {result.get('target')}")
        print(f"   Job ID: {result.get('job_id')}")
        print(f"   Preview: {result.get('message_preview', '')[:100]}")
    else:
        print(f"❌ Failed: {result.get('error')}")


if __name__ == '__main__':
    main()
