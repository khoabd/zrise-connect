#!/usr/bin/env python3
"""
config_agent.py - Cấu hình qua agent khác (1 lệnh)
Cho phép user override proposed_agent bằng agent họ chọn
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

def config_agent(task_id: int, agent: str, action: str = "config"):
    """Cấu hình agent cho task"""
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

    # Xử lý theo action
    if action == "reject":
        # Từ chối kết quả → task sang FAILED
        task_data["status"] = "FAILED"
        task_data["plan_stage"]["decision_made"] = True
        task_data["plan_stage"]["approved_agent"] = None

        task_data["audit_trail"].append({
            "event": "user_feedback_given",
            "timestamp": datetime.now().isoformat(),
            "actor": "user",
            "details": {
                "action": "reject",
                "message": "Task rejected by user"
            }
        })

        result = {
            "status": "success",
            "task_id": task_id,
            "message": f"Task {task_id} rejected",
            "new_status": "FAILED",
            "rejected": True
        }

    elif action == "request_changes":
        # Yêu cầu sửa đổi → về lại processing
        task_data["status"] = "PROCESSING"
        task_data["plan_stage"]["decision_made"] = False

        task_data["audit_trail"].append({
            "event": "user_feedback_given",
            "timestamp": datetime.now().isoformat(),
            "actor": "user",
            "details": {
                "action": "request_changes",
                "message": "User requested changes"
            }
        })

        result = {
            "status": "success",
            "task_id": task_id,
            "message": f"Change request recorded for task {task_id}",
            "new_status": "PROCESSING",
            "feedback_recorded": True
        }

    else:
        # Config agent → gán agent và chuyển sang READY_FOR_CLAIM
        task_data["plan_stage"]["approved_agent"] = agent
        task_data["plan_stage"]["decision_made"] = True
        task_data["plan_stage"]["planned_at"] = datetime.now().isoformat()

        task_data["status"] = "READY_FOR_CLAIM"
        task_data["assigned_agent"] = agent

        task_data["audit_trail"].append({
            "event": "plan_accepted",
            "timestamp": datetime.now().isoformat(),
            "actor": "user",
            "details": {
                "accepted_agent": agent,
                "plan_type": "user-configured",
                "override_from": plan_stage.get("proposed_agent")
            }
        })

        result = {
            "status": "success",
            "task_id": task_id,
            "message": f"Agent configured for task {task_id}. Agent: {agent}",
            "agent": agent,
            "new_status": "READY_FOR_CLAIM"
        }

    # Ghi task detail
    with open(task_file, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Cấu hình agent cho task')
    parser.add_argument('task_id', type=int, help='Task ID từ Zrise')
    parser.add_argument('--agent', default='', help='Agent ID để gán (ví dụ: sales-agent-v2)')
    parser.add_argument('--action', default='config', choices=['config', 'request_changes', 'reject'],
                       help='Hành động: config (gán agent), request_changes (yêu cầu sửa), reject (từ chối)')

    args = parser.parse_args()

    if args.action == 'config' and not args.agent:
        print("❌ Error: --agent required when action is 'config'")
        sys.exit(1)

    config_agent(args.task_id, args.agent, args.action)
