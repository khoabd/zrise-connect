#!/usr/bin/env python3
"""
accept_default_plan.py - Chấp nhận plan mặc định (1 lệnh)
Chuyển task sang READY_FOR_CLAIM sau khi user approve plan
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

def accept_default_plan(task_id: int):
    """Chấp nhận plan mặc định cho task"""
    workspace_root = Path(__file__).parent.parent.parent.parent
    tasks_dir = workspace_root / "tasks" / "details"
    task_file = tasks_dir / f"{task_id}.json"
    
    if not task_file.exists():
        result = {
            "status": "error",
            "task_id": task_id,
            "message": f"Task {task_id} not found. Run auto_plan.py first."
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
    
    plan_stage = task_data["plan_stage"]
    
    # Kiểm tra xem plan đã được approve chưa
    if plan_stage.get("decision_made"):
        result = {
            "status": "error",
            "task_id": task_id,
            "message": f"Task {task_id} plan already accepted.",
            "current_status": task_data.get("status")
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    
    # Lấy proposed_agent làm approved_agent
    approved_agent = plan_stage.get("proposed_agent")
    if not approved_agent:
        result = {
            "status": "error",
            "task_id": task_id,
            "message": f"Task {task_id} has no proposed_agent."
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    
    # Cập nhật plan_stage
    task_data["plan_stage"]["approved_agent"] = approved_agent
    task_data["plan_stage"]["decision_made"] = True
    task_data["plan_stage"]["planned_at"] = datetime.now().isoformat()
    
    # Cập nhật task status và assigned_agent
    task_data["status"] = "READY_FOR_CLAIM"
    task_data["assigned_agent"] = approved_agent
    
    # Thêm audit trail entry
    if "audit_trail" not in task_data:
        task_data["audit_trail"] = []
    
    task_data["audit_trail"].append({
        "event": "plan_accepted",
        "timestamp": datetime.now().isoformat(),
        "actor": "user",
        "details": {
            "accepted_agent": approved_agent,
            "plan_type": "auto-generated"
        }
    })
    
    # Ghi task detail
    with open(task_file, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
    
    result = {
        "status": "success",
        "task_id": task_id,
        "message": f"Default plan accepted for task {task_id}. Agent: {approved_agent}",
        "agent": approved_agent,
        "new_status": "READY_FOR_CLAIM"
    }
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Chấp nhận plan mặc định cho task')
    parser.add_argument('task_id', type=int, help='Task ID từ Zrise')
    
    args = parser.parse_args()
    
    accept_default_plan(args.task_id)
