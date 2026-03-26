#!/usr/bin/env python3
"""
claim_and_process.py - Agent claim và xử lý task
Chỉ claim task có status: READY_FOR_CLAIM
Sau khi xử lý xong → chuyển sang READY_FOR_FEEDBACK_REVIEW
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

def load_pending_registry():
    """Đọc danh sách task pending từ registry"""
    workspace_root = Path(__file__).parent.parent.parent.parent
    registry_file = workspace_root / "tasks" / "registry" / "pending.json"
    
    if registry_file.exists():
        try:
            with open(registry_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and 'task_ids' in data:
                return set(data['task_ids'])
            elif isinstance(data, list):
                return set(data)
            else:
                return set()
        except Exception as e:
            print(f"⚠️ Lỗi đọc registry pending: {e}")
            return set()
    else:
        return set()

def get_ready_for_claim_tasks():
    """Tìm tất cả task có status: READY_FOR_CLAIM"""
    workspace_root = Path(__file__).parent.parent.parent.parent
    tasks_dir = workspace_root / "tasks" / "details"
    
    ready_tasks = []
    
    if tasks_dir.exists():
        for task_file in tasks_dir.glob("*.json"):
            try:
                with open(task_file, 'r', encoding='utf-8') as f:
                    task_data = json.load(f)
                
                if task_data.get("status") == "READY_FOR_CLAIM":
                    task_id = task_data.get("task_id")
                    if task_id:
                        ready_tasks.append((task_id, task_data, task_file))
            except Exception as e:
                print(f"⚠️ Lỗi đọc task file {task_file}: {e}")
    
    return ready_tasks

def claim_task(task_id: int, task_data: dict, task_file: Path, agent_name: str = "general-agent"):
    """
    Claim task và xử lý.
    
    Flow:
    1. Claim task (đánh dấu là đang xử lý)
    2. Xử lý task (giả lập - thực tế sẽ gọi AI agent)
    3. Sau khi xong → chuyển sang READY_FOR_FEEDBACK_REVIEW
    """
    print(f"✅ {agent_name} claimed task {task_id}")
    
    # Cập nhật status thành processing
    task_data["status"] = "processing"
    task_data["processing_started_at"] = datetime.now().isoformat()
    
    # Thêm audit trail
    if "audit_trail" not in task_data:
        task_data["audit_trail"] = []
    
    task_data["audit_trail"].append({
        "event": "task_claimed",
        "timestamp": datetime.now().isoformat(),
        "actor": agent_name,
        "details": {
            "claimed_at": datetime.now().isoformat()
        }
    })
    
    task_data["audit_trail"].append({
        "event": "task_processing_started",
        "timestamp": datetime.now().isoformat(),
        "actor": agent_name,
        "details": {
            "processing_started_at": datetime.now().isoformat()
        }
    })
    
    # Ghi task detail
    with open(task_file, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
    
    # === XỬ LÝ TASK (GIẢ LẬP) ===
    # Trong thực tế, ở đây sẽ gọi AI agent để xử lý task
    # Ví dụ: gọi llm-task hoặc Gemini API
    # Giả lập xử lý trong 2 giây
    time.sleep(2)
    
    # Kết quả giả lập
    task_context = task_data.get("task_context", {})
    task_name = task_context.get("name", "Unknown task")
    
    result = f"Task '{task_name}' processed successfully by {agent_name}"
    
    # Cập nhật task sau khi xử lý xong
    task_data["status"] = "READY_FOR_FEEDBACK_REVIEW"
    task_data["output"] = result
    task_data["result"] = result
    task_data["processing_ended_at"] = datetime.now().isoformat()
    task_data["processing_time"] = 2  # giây (giả lập)
    
    task_data["audit_trail"].append({
        "event": "task_processing_completed",
        "timestamp": datetime.now().isoformat(),
        "actor": agent_name,
        "details": {
            "processing_ended_at": datetime.now().isoformat(),
            "result": result,
            "processing_time": 2
        }
    })
    
    task_data["audit_trail"].append({
        "event": "feedback_review_requested",
        "timestamp": datetime.now().isoformat(),
        "actor": "system",
        "details": {
            "ready_for_feedback_review": True,
            "suggested_actions": ["Approve and move stage", "Request changes", "Reject result"]
        }
    })
    
    # Ghi task detail
    with open(task_file, 'w', encoding='utf-8') as f:
        json.dump(task_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ {agent_name} finished processing task {task_id}")
    print(f"   Status: READY_FOR_FEEDBACK_REVIEW - waiting for you to review feedback")
    
    return result

def run_polling(agent_name: str = "general-agent", poll_interval: int = 5):
    """
    Chạy polling loop để lắng nghe task READY_FOR_CLAIM.
    
    Args:
        agent_name: Tên agent (ví dụ: general-agent, sales-agent)
        poll_interval: Thời gian giữa mỗi lần poll (giây)
    """
    print(f"🤖 {agent_name} agent started. Polling for READY_FOR_CLAIM tasks...")
    print(f"   Poll interval: {poll_interval}s")
    print(f"   Nhấn Ctrl+C để dừng\n")
    
    try:
        while True:
            # Tìm task READY_FOR_CLAIM
            ready_tasks = get_ready_for_claim_tasks()
            
            if ready_tasks:
                for task_id, task_data, task_file in ready_tasks:
                    # Kiểm tra xem task này đã được xử lý gần đây chưa
                    last_processed = task_data.get("processing_started_at")
                    if last_processed:
                        # Đã xử lý rồi, bỏ qua
                        continue
                    
                    print(f"🔍 {agent_name} found READY_FOR_CLAIM task: {task_id}")
                    
                    # Claim và xử lý task
                    claim_task(task_id, task_data, task_file, agent_name)
            else:
                print(f"ℹ️ {agent_name} no READY_FOR_CLAIM tasks found. Waiting {poll_interval}s...")
            
            time.sleep(poll_interval)
            
    except KeyboardInterrupt:
        print(f"\n🛑 {agent_name} stopped by user")
        sys.exit(0)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent claim và xử lý task từ Zrise')
    parser.add_argument('--agent', default='general-agent', help='Tên agent (ví dụ: general-agent, sales-agent)')
    parser.add_argument('--poll-interval', type=int, default=5, help='Thời gian giữa mỗi lần poll (giây)')
    parser.add_argument('--once', action='store_true', help='Xử lý 1 task rồi thoát (không lặp)')
    
    args = parser.parse_args()
    
    if args.once:
        # Xử lý 1 task rồi thoát
        ready_tasks = get_ready_for_claim_tasks()
        if ready_tasks:
            task_id, task_data, task_file = ready_tasks[0]
            claim_task(task_id, task_data, task_file, args.agent)
        else:
            print(f"ℹ️ No READY_FOR_CLAIM tasks found")
            sys.exit(0)
    else:
        # Chạy polling loop
        run_polling(args.agent, args.poll_interval)
