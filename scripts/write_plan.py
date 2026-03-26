#!/usr/bin/env python3
"""
write_plan.py - Tool để AI agent ghi kế hoạch xuống detail.json
Dùng sau khi AI đã phân tích task và quyết định agent + execution steps
Detail.json sẽ chứa toàn bộ decisions
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection, update_task_agent, load_task_detail, save_task_detail, add_task_log, get_tasks_dir

def write_plan(task_id: int, selected_agent: str, execution_steps: list, estimated_time: str = "", notes: str = ""):
    """Ghi plan vào detail.json.
    
    Args:
        task_id: Task ID
        selected_agent: Agent được chọn
        execution_steps: List các bước thực hiện
        estimated_time: Thời gian ước tính
        notes: Ghi chú thêm từ AI
    
    Returns:
        dict với status và message
    """
    # Load existing detail
    detail = load_task_detail(task_id)
    
    if detail is None:
        return {
            "status": "error",
            "message": f"Task {task_id} detail not found"
        }
    
    # Update detail with plan
    detail["selected_agent"] = selected_agent
    detail["execution_steps"] = execution_steps
    detail["estimated_time"] = estimated_time
    detail["plan_notes"] = notes
    detail["status"] = "pending_approval"
    detail["plan_created_at"] = datetime.now().isoformat()
    
    # Save detail
    save_task_detail(task_id, detail)
    
    # Update agent in DB
    update_task_agent(task_id, selected_agent)
    
    # Add log
    add_task_log(task_id, "plan_written", "ai-agent", {
        "selected_agent": selected_agent,
        "steps_count": len(execution_steps)
    })
    
    return {
        "status": "success",
        "message": f"Plan written for task {task_id}",
        "task_dir": str(get_tasks_dir() / str(task_id)),
        "detail_file": str(get_tasks_dir() / str(task_id) / "detail.json"),
        "selected_agent": selected_agent,
        "steps_count": len(execution_steps)
    }

def read_plan(task_id: int):
    """Đọc plan hiện có của task (từ detail.json)."""
    detail = load_task_detail(task_id)
    
    if detail is None:
        return None
    
    return {
        "task_id": task_id,
        "selected_agent": detail.get("selected_agent"),
        "execution_steps": detail.get("execution_steps", []),
        "estimated_time": detail.get("estimated_time"),
        "notes": detail.get("plan_notes"),
        "status": detail.get("status"),
        "created_at": detail.get("plan_created_at")
    }

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Ghi kế hoạch xuống JSON cho task')
    parser.add_argument('task_id', type=int, help='Task ID')
    parser.add_argument('--agent', required=True, help='Agent được chọn')
    parser.add_argument('--steps', required=True, help='Execution steps (comma-separated)')
    parser.add_argument('--time', default='', help='Thời gian ước tính')
    parser.add_argument('--notes', default='', help='Ghi chú thêm')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--read', action='store_true', help='Đọc plan hiện có')
    
    args = parser.parse_args()
    
    if args.read:
        plan = read_plan(args.task_id)
        if plan:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
        else:
            print(f"❌ No plan found for task {args.task_id}")
            sys.exit(1)
        return
    
    # Parse steps
    steps = [s.strip() for s in args.steps.split(',') if s.strip()]
    
    result = write_plan(
        task_id=args.task_id,
        selected_agent=args.agent,
        execution_steps=steps,
        estimated_time=args.time,
        notes=args.notes
    )
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result['status'] == 'success':
            print(f"✅ Plan written for task {args.task_id}")
            print(f"   Agent: {result['selected_agent']}")
            print(f"   Steps: {result['steps_count']}")
            print(f"   File: {result['detail_file']}")
        else:
            print(f"❌ {result['message']}")
            sys.exit(1)

if __name__ == '__main__':
    main()
