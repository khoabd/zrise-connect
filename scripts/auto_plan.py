#!/usr/bin/env python3
"""
auto_plan.py - Chuẩn bị data cho AI agent lên plan
Dùng SQLite cho status, detail.json cho task info
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection, get_task, get_all_agents, get_task_detail_path, save_task_detail, add_task_log, get_tasks_dir

def get_new_tasks():
    """Lấy tất cả task có status = 'new' từ SQLite."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT task_id, name, status, created_at FROM tasks WHERE status = ? ORDER BY created_at', ('new',))
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "task_id": row[0],
            "name": row[1],
            "status": row[2],
            "created_at": row[3]
        }
        for row in rows
    ]

def move_to_pending(task_id: int):
    """Move task từ new sang pending (trong SQLite)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?', 
              ('pending', datetime.now().isoformat(), task_id))
    conn.commit()
    conn.close()
    
    # Add log
    add_task_log(task_id, "moved_to_pending", "system")

def format_task_info(task_id: int, detail: dict, agents: list, is_replan: bool = False):
    """Format thông tin task cho AI agent."""
    previous_plan = detail.get('previous_plan_attempt') if is_replan else None
    feedback = detail.get('user_feedback', '') if is_replan else ''
    re_plan_count = detail.get('re_plan_count', 0)
    
    # Agent list
    agent_lines = "\n".join([f"- {a['id']}" for a in agents])
    
    # Build text
    text_parts = []
    
    if is_replan:
        text_parts.append(f"""🔄 **Task cần re-plan (lần {re_plan_count}):**

**Task ID:** {task_id}
**Tên:** {detail.get('name', 'N/A')}
**Mô tả:** {detail.get('description', 'N/A')[:200]}...
**Project:** {detail.get('project', 'N/A')}
**Deadline:** {detail.get('deadline', 'N/A')}

**User Feedback:**
{feedback}

**Plan trước đó:**
- Agent: {previous_plan.get('selected_agent') if previous_plan else 'N/A'}
- Steps: {', '.join(previous_plan.get('execution_steps', [])[:3]) if previous_plan else 'N/A'}""")
    else:
        text_parts.append(f"""📋 **Task cần lên kế hoạch:**

**Task ID:** {task_id}
**Tên:** {detail.get('name', 'N/A')}
**Mô tả:** {detail.get('description', 'N/A')[:200]}...
**Project:** {detail.get('project', 'N/A')}
**Deadline:** {detail.get('deadline', 'N/A')}""")
    
    text_parts.append(f"""
**Available Agents ({len(agents)}):**
{agent_lines}

---
**Agent cần:**
1. Đọc task data từ: `.tasks/{task_id}/detail.json`
2. Dùng AI phân tích task""")
    
    if is_replan:
        text_parts.append(f"""3. Xem xét feedback từ user
4. Revise plan nếu cần""")
    else:
        text_parts.append(f"""3. Quyết định agent và cách xử lý""")
    
    text_parts.append(f"""5. Ghi plan vào: `.tasks/{task_id}/detail.json`

Plan cần có:
- selected_agent: agent được chọn
- execution_steps: các bước thực hiện
- estimated_time: thời gian ước tính""")
    
    return {
        "task_id": task_id,
        "text": '\n'.join(text_parts),
        "task_dir": str(get_tasks_dir() / str(task_id)),
        "agent_count": len(agents),
        "is_replan": is_replan
    }

def process_new_tasks():
    """Process tất cả task mới."""
    new_tasks = get_new_tasks()
    
    if not new_tasks:
        return {"status": "no_new_tasks", "count": 0, "tasks": []}
    
    agents = get_all_agents()
    results = []
    
    for task in new_tasks:
        task_id = task['task_id']
        
        # Load detail.json
        detail_path = get_task_detail_path(task_id)
        if not detail_path.exists():
            continue
        
        with open(detail_path, 'r', encoding='utf-8') as f:
            detail = json.load(f)
        
        # Move to pending in DB
        move_to_pending(task_id)
        
        # Format info
        is_replan = 'user_feedback' in detail and detail['user_feedback']
        info = format_task_info(task_id, detail, agents, is_replan)
        results.append(info)
    
    return {
        "status": "success",
        "count": len(results),
        "tasks": results
    }

def print_task_info(info):
    """Print task info cho AI agent."""
    print(f"=== TASK INFO ===")
    print(f"TASK_ID: {info['task_id']}")
    print(f"TASK_DIR: {info['task_dir']}")
    print(f"AGENT_COUNT: {info['agent_count']}")
    print(f"IS_REPLAN: {info['is_replan']}")
    print(f"--- TEXT START ---")
    print(info['text'])
    print(f"--- TEXT END ---")
    print(f"=== END TASK INFO ===")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Chuẩn bị data để AI agent lên plan')
    parser.add_argument('--task-id', type=int, help='Process specific task ID')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--info', action='store_true', help='Output task info for AI')
    parser.add_argument('--once', action='store_true', help='Process once and exit')
    
    args = parser.parse_args()
    
    if args.task_id:
        # Process specific task
        task = get_task(args.task_id)
        if not task:
            print(f"❌ Task {args.task_id} not found")
            sys.exit(1)
        
        detail_path = get_task_detail_path(args.task_id)
        if not detail_path.exists():
            print(f"❌ Task detail not found: {detail_path}")
            sys.exit(1)
        
        with open(detail_path, 'r', encoding='utf-8') as f:
            detail = json.load(f)
        
        agents = get_all_agents()
        is_replan = 'user_feedback' in detail and detail['user_feedback']
        info = format_task_info(args.task_id, detail, agents, is_replan)
        
        if args.info:
            print_task_info(info)
        elif args.json:
            print(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            print(f"✅ Task {args.task_id} ready for planning")
            print(f"   Dir: {info['task_dir']}")
            print(f"   Agents: {info['agent_count']}")
    
    else:
        # Process all new tasks
        result = process_new_tasks()
        
        if result['status'] == 'no_new_tasks':
            if not args.json:
                print("ℹ️ Không có task mới trong SQLite (status='new')")
            sys.exit(0)
        
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.info:
            for task in result['tasks']:
                print_task_info(task)
                print()
        else:
            print(f"✅ Đã move {result['count']} task(s) sang pending:")
            for task in result['tasks']:
                print(f"   [{task['task_id']}] - {task['agent_count']} agents")
            print()
            print("Dùng --info để xem chi tiết từng task cho AI agent")

if __name__ == '__main__':
    main()
