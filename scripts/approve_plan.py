#!/usr/bin/env python3
"""
approve_plan.py - Handle user approval responses
3 cases:
  1. approve - đồng ý → execute
  2. change_agent - đồng ý nhưng đổi agent
  3. feedback - reply kèm feedback → move về new để re-plan
"""

import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection, update_task_status, update_task_agent, load_task_detail, save_task_detail, add_task_log, get_tasks_dir

def case_approve(task_id: int, detail: dict):
    """Case 1: User đồng ý → thực thi task."""
    # Update status in DB
    update_task_status(task_id, 'approved')
    
    # Update detail with approval info
    detail['status'] = 'approved'
    detail['approved_at'] = datetime.now().isoformat()
    detail['plan_approved_at'] = datetime.now().isoformat()  # ⚠️ CRITICAL: For executor to verify
    save_task_detail(task_id, detail)
    
    # Add log
    add_task_log(task_id, "approved", "user", {
        "selected_agent": detail.get("selected_agent")
    })
    
    agent = detail.get("selected_agent", "unknown")
    steps = detail.get("execution_steps", [])
    
    return {
        "status": "approved",
        "task_id": task_id,
        "action": "execute",
        "selected_agent": agent,
        "execution_steps": steps,
        "task_dir": str(get_tasks_dir() / str(task_id)),
        "notification": f"""✅ **Task approved!**

**Task:** {detail.get('name', 'N/A')}
**ID:** {task_id}
**Agent:** {agent}

**Steps:**
{chr(10).join([f"{i+1}. {s}" for i, s in enumerate(steps)])}

---
Ready to execute. Agent {agent} should start working."""
    }

def case_change_agent(task_id: int, detail: dict, new_agent: str):
    """Case 2: User đồng ý nhưng đổi agent."""
    old_agent = detail.get("selected_agent")
    
    # Update DB
    update_task_agent(task_id, new_agent)
    update_task_status(task_id, 'approved')
    
    # Update detail
    detail['status'] = 'approved'
    detail['previous_agent'] = old_agent
    detail['selected_agent'] = new_agent
    detail['agent_changed_by_user'] = True
    detail['approved_at'] = datetime.now().isoformat()
    detail['plan_approved_at'] = datetime.now().isoformat()  # ⚠️ CRITICAL: For executor to verify
    save_task_detail(task_id, detail)
    
    # Add log
    add_task_log(task_id, "approved_with_agent_change", "user", {
        "old_agent": old_agent,
        "new_agent": new_agent
    })
    
    steps = detail.get("execution_steps", [])
    
    return {
        "status": "approved",
        "task_id": task_id,
        "action": "execute",
        "selected_agent": new_agent,
        "previous_agent": old_agent,
        "execution_steps": steps,
        "task_dir": str(get_tasks_dir() / str(task_id)),
        "notification": f"""✅ **Task approved with agent change!**

**Task:** {detail.get('name', 'N/A')}
**ID:** {task_id}
**Agent:** ~~{old_agent}~~ → **{new_agent}**

**Steps:**
{chr(10).join([f"{i+1}. {s}" for i, s in enumerate(steps)])}

---
Ready to execute. Agent {new_agent} should start working."""
    }

def case_feedback(task_id: int, detail: dict, feedback: str):
    """Case 3: User reply kèm feedback → move về new để re-plan."""
    # Save previous plan in detail
    previous_plan = {
        "selected_agent": detail.get("selected_agent"),
        "execution_steps": detail.get("execution_steps", []),
        "estimated_time": detail.get("estimated_time"),
        "notes": detail.get("plan_notes")
    }
    
    re_plan_count = (detail.get("re_plan_count") or 0) + 1
    
    # Update detail with feedback + previous plan
    detail['user_feedback'] = feedback
    detail['previous_plan_attempt'] = previous_plan
    detail['re_plan_count'] = re_plan_count
    detail['moved_to_new_at'] = datetime.now().isoformat()
    detail['status'] = 'new'  # Reset status
    
    # Delete task folder
    task_dir = get_tasks_dir() / str(task_id)
    if task_dir.exists():
        shutil.rmtree(task_dir)
    
    # Save detail to new location (will be recreated by auto_plan)
    task_dir.mkdir(parents=True, exist_ok=True)
    save_task_detail(task_id, detail)
    
    # Update status in DB
    update_task_status(task_id, 'new')
    
    # Add log
    add_task_log(task_id, "feedback_moved_to_new", "user", {
        "feedback": feedback,
        "re_plan_count": re_plan_count
    })
    
    return {
        "status": "moved_to_new",
        "task_id": task_id,
        "action": "replan",
        "feedback": feedback,
        "re_plan_count": re_plan_count,
        "task_dir": str(task_dir),
        "notification": f"""🔄 **Task returned for revision**

**Task:** {detail.get('name', 'N/A')}
**ID:** {task_id}

**User Feedback:**
{feedback}

**Plan trước đó:**
- Agent: {previous_plan.get('selected_agent')}
- Steps: {', '.join(previous_plan.get('execution_steps', [])[:3])}

---
Task moved to new. Run `auto_plan.py` to re-plan (lần {re_plan_count})."""
    }

def format_notification(notif_data: dict):
    """Format notification theo structured output."""
    print(f"=== NOTIFICATION ===")
    print(f"ACTION: {notif_data['action']}")
    print(f"TASK_ID: {notif_data['task_id']}")
    print(f"STATUS: {notif_data['status']}")
    if 'selected_agent' in notif_data:
        print(f"SELECTED_AGENT: {notif_data['selected_agent']}")
    if 'previous_agent' in notif_data:
        print(f"PREVIOUS_AGENT: {notif_data['previous_agent']}")
    print(f"TASK_DIR: {notif_data['task_dir']}")
    print(f"--- TEXT START ---")
    print(notif_data['notification'])
    print(f"--- TEXT END ---")
    print(f"=== END NOTIFICATION ===")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Handle user approval responses')
    parser.add_argument('task_id', type=int, help='Task ID')
    parser.add_argument('--action', required=True, 
                       choices=['approve', 'change_agent', 'feedback'],
                       help='Action: approve | change_agent | feedback')
    parser.add_argument('--agent', help='New agent (for change_agent action)')
    parser.add_argument('--feedback-text', help='Feedback text (for feedback action)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--notify', action='store_true', help='Output notification')
    
    args = parser.parse_args()
    
    # Validate
    if args.action == 'change_agent' and not args.agent:
        print("❌ --agent required for change_agent action")
        sys.exit(1)
    
    if args.action == 'feedback' and not args.feedback_text:
        print("❌ --feedback-text required for feedback action")
        sys.exit(1)
    
    # Load detail
    detail = load_task_detail(args.task_id)
    
    if detail is None:
        print(f"❌ Task {args.task_id} not found")
        sys.exit(1)
    
    # Handle action
    if args.action == 'approve':
        result = case_approve(args.task_id, detail)
    elif args.action == 'change_agent':
        result = case_change_agent(args.task_id, detail, args.agent)
    elif args.action == 'feedback':
        result = case_feedback(args.task_id, detail, args.feedback_text)
    
    # Output
    if args.notify:
        format_notification(result)
    elif args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"✅ {result['message']}")
        if result['action'] == 'execute':
            print(f"   Agent: {result.get('selected_agent')}")
            print(f"   Steps: {len(result.get('execution_steps', []))}")
        elif result['action'] == 'replan':
            print(f"   Feedback: {result.get('feedback', '')[:50]}...")

if __name__ == '__main__':
    main()
