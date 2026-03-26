#!/usr/bin/env python3
"""
regenerate_plan.py - Tái tạo plan nếu cần (2 lệnh: regenerate + accept)
Dùng khi user không hài lòng với proposed_agent và muốn AI đề xuất lại
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Import từ auto_plan.py để tái sử dụng logic
sys.path.insert(0, str(Path(__file__).parent))
from auto_plan import sanitize_input, load_agent_registry, detect_department_and_workflow

def regenerate_plan(task_id: int, feedback: str = ""):
    """
    Tái tạo plan cho task dựa trên feedback.
    
    Args:
        task_id: Task ID từ Zrise
        feedback: Lý do yêu cầu tái tạo (optional)
    """
    workspace_root = Path(__file__).parent.parent.parent.parent
    tasks_dir = workspace_root / "tasks" / "details"
    task_file = tasks_dir / f"{task_id}.json"
    
    if not task_file.exists():
        result = {
            "status": "error",
            "task_id": task_id,
            "message": f"Task {task_id} not found."
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    
    # Đọc task detail
    with open(task_file, 'r', encoding='utf-8') as f:
        task_data = json.load(f)
    
    # Kiểm tra xem có plan_stage không
    if "plan_stage" not in task_data:
        result = {
            "status": "error",
            "task_id": task_id,
            "message": f"Task {task_id} has no plan_stage. Run auto_plan.py first."
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    
    # Lấy thông tin task để tái tạo plan
    task_context = task_data.get("task_context", {})
    task_name = task_context.get("name", "")
    task_description = task_context.get("description", "")
    project = task_context.get("project", "")
    
    # Load agent registry
    registry = load_agent_registry()
    
    # Detect department và workflow (có thể điều chỉnh dựa trên feedback)
    dept, workflow = detect_department_and_workflow(task_name, task_description, project)
    
    # Lookup agent từ registry
    if dept == "fallback":
        proposed_agent = registry.get("fallback", {}).get("general", "general-agent")
    else:
        proposed_agent = registry.get(dept, {}).get(workflow, registry.get("fallback", {}).get("general", "general-agent"))
    
    # Reset plan_stage
    task_data["plan_stage"]["proposed_agent"] = proposed_agent
    task_data["plan_stage"]["approved_agent"] = None
    task_data["plan_stage"]["decision_made"] = False
    task_data["plan_stage"]["planned_at"] = datetime.now().isoformat()
    
    # Thêm feedback vào history
    if feedback:
        task_data["plan_stage"]["feedback_history"].append({
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback
        })
    
    # Reset task status về pending
    task_data["status"] = "pending"
    task_data["assigned_agent"] = None
    
    # Thêm audit trail entry
    if "audit_trail" not in task_data:
        task_data["audit_trail"] = []
    
    task_data["audit_trail"].append({
        "event": "plan_regenerated",
        "timestamp": datetime.now().isoformat(),
        "actor": "system-auto-planner",
        "details": {
            "new_proposed_agent": proposed_agent,
            "feedback": feedback,
            "reason": "User requested plan regeneration"
        }
    })
    
    # Ghi task detail
    with open(task_file, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
    
    result = {
        "status": "success",
        "task_id": task_id,
        "message": f"Plan regenerated for task {task_id}. New proposed agent: {proposed_agent}",
        "auto_proposed_agent": proposed_agent,
        "requires_accept": True,
        "next_step": "Run accept_default_plan.py to accept this plan"
    }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Tái tạo plan cho task')
    parser.add_argument('task_id', type=int, help='Task ID từ Zrise')
    parser.add_argument('--feedback', default='', help='Lý do yêu cầu tái tạo (optional)')
    
    args = parser.parse_args()
    
    regenerate_plan(args.task_id, args.feedback)
