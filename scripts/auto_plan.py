#!/usr/bin/env python3
"""
auto_plan.py - Chuẩn bị data cho AI agent lên plan
Dùng SQLite cho status, detail.json cho task info

Supports:
- New tasks: status='new' → pending → AI lên plan
- Re-plan tasks: status='feedback' → user đã feedback, cần revise plan

Khi có task cần plan, script sẽ spawn AI agent để tạo plan và gửi Telegram.
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db import get_connection, get_task, get_all_agents, get_task_detail_path, save_task_detail, add_task_log, get_tasks_dir

# Spam control: Don't repeat same "no tasks" message within 15 minutes
LAST_NO_TASKS_FILE = Path(__file__).parent.parent.parent / '.tasks' / '.last_no_tasks'
SPAM_INTERVAL_MINUTES = 15

def post_plan_to_telegram(task_id: int, plan: dict, task_detail: dict = None, is_replan: bool = False) -> dict:
    """
    Post plan to Telegram channel using openclaw agent --deliver.

    Uses format_message_for_telegram_channels.py to format the message,
    then sends via openclaw agent --deliver.
    """
    # Import formatter
    from format_message_for_telegram_channels import format_plan_message

    # Build plan text using formatter
    task_name = task_detail.get('name', f'Task #{task_id}') if task_detail else f'Task #{task_id}'
    selected_agent = plan.get('selected_agent', 'N/A')
    execution_steps = plan.get('execution_steps', [])
    estimated_time = plan.get('estimated_time', 'N/A')
    user_feedback = task_detail.get('user_feedback', '') if task_detail else ''
    previous_plan = task_detail.get('previous_plan_attempt') if is_replan else None
    priority = plan.get('priority', 'normal')

    # Format message
    text = format_plan_message(
        task_id=task_id,
        task_name=task_name,
        selected_agent=selected_agent,
        execution_steps=execution_steps,
        estimated_time=estimated_time,
        is_replan=is_replan,
        user_feedback=user_feedback,
        previous_plan=previous_plan,
        priority=priority
    )

    # Send via openclaw agent --deliver
    try:
        cmd = [
            'openclaw', 'agent',
            '--message', text,
            '--deliver',
            '--channel', 'telegram',
            '--agent', 'ai-company'
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            add_task_log(task_id, 'plan_posted_channel', 'auto_plan', {
                'output': result.stdout[:200] if result.stdout else 'sent'
            })
            return {"success": True, "output": result.stdout[:100] if result.stdout else "sent"}
        else:
            add_task_log(task_id, 'plan_posted_failed', 'auto_plan', {
                'error': result.stderr[:200] if result.stderr else 'unknown'
            })
            return {"success": False, "error": result.stderr[:200] if result.stderr else "failed"}
    except Exception as e:
        add_task_log(task_id, 'plan_posted_failed', 'auto_plan', {'error': str(e)})
        return {"success": False, "error": str(e)}


def _get_last_no_tasks_time():
    """Get timestamp of last 'no tasks' message."""
    if not LAST_NO_TASKS_FILE.exists():
        return None
    try:
        return datetime.fromisoformat(LAST_NO_TASKS_FILE.read_text().strip())
    except:
        return None

def _set_last_no_tasks_time():
    """Record that we just reported 'no tasks'."""
    LAST_NO_TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_NO_TASKS_FILE.write_text(datetime.now().isoformat())

def _should_skip_no_tasks_message():
    """Check if we should skip the 'no tasks' message due to spam control."""
    last_time = _get_last_no_tasks_time()
    if last_time is None:
        return False  # Never reported, so report now
    elapsed = datetime.now() - last_time
    return elapsed < timedelta(minutes=SPAM_INTERVAL_MINUTES)

def get_pending_without_plan():
    """Lấy task đang pending nhưng chưa có plan (stuck tasks cần được xử lý)."""
    conn = get_connection()
    c = conn.cursor()
    
    # Lấy tất cả task có status='pending'
    c.execute('SELECT task_id, name, status, updated_at FROM tasks WHERE status = ? ORDER BY updated_at', ('pending',))
    rows = c.fetchall()
    conn.close()
    
    pending_no_plan = []
    for row in rows:
        task_id = row[0]
        detail_path = get_task_detail_path(task_id)
        
        if not detail_path.exists():
            continue
        
        try:
            with open(detail_path, 'r', encoding='utf-8') as f:
                detail = json.load(f)
        except:
            continue
        
        # Skip if has execution_steps (already planned) OR selected_agent
        has_plan = detail.get('plan') or detail.get('execution_steps') or detail.get('selected_agent')
        if not has_plan:
            pending_no_plan.append({
                "task_id": task_id,
                "name": row[1],
                "status": 'pending_no_plan',
                "updated_at": row[3]
            })
    
    return pending_no_plan


def get_pending_with_plan_not_posted():
    """Lấy task đã có plan nhưng chưa được post lên Telegram.
    
    Đây là các task đã được AI agent tạo plan, nhưng do timeout hoặc lỗi
    nên chưa được gửi cho user approve.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Lấy tất cả task có status='pending'
    c.execute('SELECT task_id, name, status, updated_at FROM tasks WHERE status = ? ORDER BY updated_at', ('pending',))
    rows = c.fetchall()
    conn.close()
    
    needs_post = []
    for row in rows:
        task_id = row[0]
        detail_path = get_task_detail_path(task_id)
        logs_path = get_tasks_dir() / str(task_id) / 'logs.json'
        
        # Check nếu đã có plan
        if detail_path.exists():
            try:
                with open(detail_path, 'r', encoding='utf-8') as f:
                    detail = json.load(f)
                
                has_plan = detail.get('execution_steps') and detail.get('selected_agent')
                if not has_plan:
                    continue
                
                # Check logs để xem đã được post chưa
                already_posted = False
                if logs_path.exists():
                    try:
                        with open(logs_path, 'r', encoding='utf-8') as f:
                            logs = json.load(f)
                        for log in logs:
                            if log.get('event') == 'plan_posted_telegram':
                                already_posted = True
                                break
                    except:
                        pass
                
                if not already_posted:
                    needs_post.append({
                        "task_id": task_id,
                        "name": row[1],
                        "status": 'pending_plan_not_posted',
                        "updated_at": row[3]
                    })
            except:
                pass
    
    return needs_post

def get_new_tasks():
    """Lấy tất cả task có status = 'new' từ SQLite (new tasks cần lên plan)."""
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

def get_replan_tasks():
    """Lấy task cần re-plan (status='feedback' hoặc có user_feedback trong detail.json)."""
    conn = get_connection()
    c = conn.cursor()
    
    # Lấy tasks có status='feedback' (đã được approve plan nhưng bị reject)
    c.execute('SELECT task_id, name, status, updated_at FROM tasks WHERE status = ? ORDER BY updated_at', ('feedback',))
    feedback_rows = c.fetchall()
    
    # Hoặc tasks có detail.json chứa user_feedback nhưng chưa được re-plan
    replan_tasks = []
    for row in feedback_rows:
        task_id = row[0]
        detail_path = get_task_detail_path(task_id)
        if detail_path.exists():
            try:
                with open(detail_path, 'r', encoding='utf-8') as f:
                    detail = json.load(f)
                # Nếu có user_feedback và chưa được resolved
                if detail.get('user_feedback') and not detail.get('plan_after_feedback'):
                    replan_tasks.append({
                        "task_id": task_id,
                        "name": row[1],
                        "status": row[2],
                        "updated_at": row[3]
                    })
            except:
                pass
    
    conn.close()
    return replan_tasks

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

def move_to_feedback(task_id: int):
    """Move task sang feedback status (sau khi plan bị reject)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?', 
              ('feedback', datetime.now().isoformat(), task_id))
    conn.commit()
    conn.close()
    add_task_log(task_id, "moved_to_feedback", "system")

def format_task_info(task_id: int, detail: dict, agents: list, is_replan: bool = False):
    """Format thông tin task cho AI agent."""
    previous_plan = detail.get('previous_plan_attempt') if is_replan else None
    feedback = detail.get('user_feedback', '') if is_replan else ''
    re_plan_count = detail.get('re_plan_count', 0)
    
    # Safe get description - always return string
    description = detail.get('description', '') or ''
    if not isinstance(description, str):
        description = str(description) if description else ''
    description = description[:200] if description else 'Không có mô tả'
    
    # Safe get name
    name = detail.get('name', 'N/A') or 'N/A'
    
    # Safe get project
    project = detail.get('project', 'N/A')
    if isinstance(project, list):
        project = project[1] if len(project) > 1 else 'N/A'
    project = project or 'N/A'
    
    # Safe get deadline
    deadline = detail.get('deadline', 'N/A') or 'N/A'
    
    # Agent list
    agent_lines = "\n".join([f"- {a['id']}" for a in agents])
    
    # Build text
    text_parts = []
    
    if is_replan:
        plan_steps = ', '.join(previous_plan.get('execution_steps', [])[:3]) if previous_plan and previous_plan.get('execution_steps') else 'N/A'
        text_parts.append(f"""🔄 **Task cần re-plan (lần {re_plan_count}):**

**Task ID:** {task_id}
**Tên:** {name}
**Mô tả:** {description}
**Project:** {project}
**Deadline:** {deadline}

**User Feedback:**
{feedback}

**Plan trước đó:**
- Agent: {previous_plan.get('selected_agent') if previous_plan else 'N/A'}
- Steps: {plan_steps}""")
    else:
        text_parts.append(f"""📋 **Task cần lên kế hoạch:**

**Task ID:** {task_id}
**Tên:** {name}
**Mô tả:** {description}
**Project:** {project}
**Deadline:** {deadline}""")
    
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

def process_all_planning_tasks():
    """Process tất cả task cần lên plan (new + re-plan + pending không plan + pending đã plan chưa post)."""
    new_tasks = get_new_tasks()
    replan_tasks = get_replan_tasks()
    pending_no_plan_tasks = get_pending_without_plan()
    pending_plan_not_posted = get_pending_with_plan_not_posted()
    
    # Tasks cần spawn agent (chưa có plan)
    tasks_needing_agent = new_tasks + pending_no_plan_tasks + replan_tasks
    
    # Tasks đã có plan nhưng cần post Telegram
    tasks_needing_post = pending_plan_not_posted
    
    all_tasks = tasks_needing_agent + tasks_needing_post
    
    if not all_tasks:
        # Silent exit - no output, no agent call needed
        # Only report if we haven't skipped recently (for logging purposes)
        if not _should_skip_no_tasks_message():
            _set_last_no_tasks_time()
        sys.exit(0)  # Silent - no print, no agent needs to think
    
    agents = get_all_agents()
    results = []
    
    for task in all_tasks:
        task_id = task['task_id']
        
        # Load detail.json
        detail_path = get_task_detail_path(task_id)
        if not detail_path.exists():
            continue
        
        with open(detail_path, 'r', encoding='utf-8') as f:
            detail = json.load(f)
        
        # Determine if this is a re-plan
        is_replan = task['status'] == 'feedback' or bool(detail.get('user_feedback'))
        is_pending_no_plan = task['status'] == 'pending_no_plan'
        
        # Only move to pending if task is actually 'new'
        if task['status'] == 'new':
            move_to_pending(task_id)
        
        # Update re_plan_count nếu là re-plan
        if is_replan:
            current_count = detail.get('re_plan_count', 0)
            detail['re_plan_count'] = current_count + 1
            save_task_detail(task_id, detail)
        
        # Determine status for this task
        if task['status'] == 'pending_plan_not_posted':
            task_status = 'pending_plan_not_posted'
        elif task['status'] == 'pending_no_plan':
            task_status = 'pending_no_plan'
        elif is_replan:
            task_status = 'replan'
        else:
            task_status = 'new'
        
        # Format info
        info = format_task_info(task_id, detail, agents, is_replan)
        info['status'] = task_status  # Include status for filtering later
        results.append(info)
    
    return {
        "status": "success",
        "count": len(results),
        "new_count": len(new_tasks),
        "replan_count": len(replan_tasks),
        "tasks": results
    }


def spawn_plan_agent(task_id: int, is_replan: bool = False) -> dict:
    """
    Spawn AI agent để tạo plan cho task.
    
    Uses openclaw CLI để spawn agent với task info.
    """
    from post_channel import get_default_target
    
    workspace = Path(__file__).parent.parent.parent
    task_dir = workspace / '.tasks' / str(task_id)
    detail_path = task_dir / 'detail.json'
    target = get_default_target() or ""
    
    # Build prompt cho agent
    if is_replan:
        prompt = f"""Bạn cần revise plan cho task #{task_id}.

Đọc task detail từ: {detail_path}

Sau đó:
1. Xem xét user feedback trong detail.json
2. Revise plan nếu cần
3. Cập nhật detail.json với:
   - plan: {{
     "selected_agent": "agent phù hợp",
     "execution_steps": [...],
     "estimated_time": "X phút"
   }}
4. Gửi plan lên Telegram để review (channel: {target})
5. Dùng post_plan_channel.py để gửi

Nếu không có feedback cụ thể, giữ nguyên plan cũ và approve.
"""
    else:
        prompt = f"""Bạn cần tạo plan cho task #{task_id}.

Đọc task detail từ: {detail_path}

Sau đó:
1. Phân tích task
2. Chọn agent phù hợp (coder, design-ba, qa-tester, hoặc ai-company)
3. Tạo plan và ghi vào detail.json:
   - plan: {{
     "selected_agent": "agent phù hợp",
     "execution_steps": [...],
     "estimated_time": "X phút"
   }}
4. Gửi plan lên Telegram để review (channel: {target})
5. Dùng post_plan_channel.py để gửi

Ưu tiên:
- coder cho code/script tasks
- design-ba cho doc/requirement tasks  
- qa-tester cho testing tasks
- ai-company cho general tasks
"""
    
    try:
        # Spawn agent using openclaw CLI in background
        # Use --deliver to send reply back to Telegram
        # Run in background so script doesn't block
        cmd = [
            'nohup', 'openclaw', 'agent',
            '--agent', 'zrise',
            '--message', prompt,
            '--deliver'
        ]
        
        # Run in background, redirect output
        with open('/dev/null', 'w') as devnull:
            subprocess.Popen(cmd, stdout=devnull, stderr=devnull, cwd=str(workspace))
        
        return {
            "success": True,
            "task_id": task_id,
            "is_replan": is_replan,
            "output": "Agent spawned in background"
        }
    except Exception as e:
        return {
            "success": False,
            "task_id": task_id,
            "is_replan": is_replan,
            "error": str(e)
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
        # Process all tasks needing planning (new + re-plan)
        result = process_all_planning_tasks()
        
        # process_all_planning_tasks() exits silently if no tasks
        # Only reach here if there ARE tasks
        
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif args.info:
            for task in result['tasks']:
                print_task_info(task)
                print()
        else:
            # Process tasks: spawn agents for new tasks, post plans for existing plans
            spawned = 0
            posted = 0
            
            # Get separate lists based on status field from get_pending_with_plan_not_posted
            tasks_needing_agent = [t for t in result['tasks'] if t.get('status') == 'pending_no_plan']
            tasks_needing_post = [t for t in result['tasks'] if t.get('status') == 'pending_plan_not_posted']
            
            # 1. Tasks cần spawn agent (chưa có plan) - skip trong vòng lặp này
            # Agent spawning không hoạt động tốt - chỉ log
            if tasks_needing_agent:
                print(f"📋 {len(tasks_needing_agent)} task(s) cần tạo plan (agent spawning tạm tắt)")
                for task_info in tasks_needing_agent:
                    print(f"   - Task #{task_info['task_id']}")
            
            # 2. Tasks đã có plan nhưng cần post Telegram
            if tasks_needing_post:
                print(f"📤 {len(tasks_needing_post)} task(s) đã có plan - đang post lên Telegram...")
                
                for task_info in tasks_needing_post:
                    task_id = task_info['task_id']
                    task_name = task_info.get('name', f'Task #{task_id}')
                    print(f"   Posting #{task_id}: {task_name[:40]}...")
                    
                    # Load detail
                    detail_path = get_task_detail_path(task_id)
                    if detail_path.exists():
                        try:
                            with open(detail_path, 'r', encoding='utf-8') as f:
                                task_detail = json.load(f)
                            
                            plan = {
                                'selected_agent': task_detail.get('selected_agent', 'unknown'),
                                'execution_steps': task_detail.get('execution_steps', []),
                                'estimated_time': task_detail.get('estimated_time', 'N/A')
                            }
                            
                            # Post to Telegram
                            post_result = post_plan_to_telegram(
                                task_id=task_id,
                                plan=plan,
                                task_detail=task_detail,
                                is_replan=False
                            )
                            
                            if post_result.get('success'):
                                print(f"      ✅ Posted successfully")
                                posted += 1
                            else:
                                print(f"      ⚠️ Failed: {str(post_result.get('error'))[:50]}")
                        except Exception as e:
                            print(f"      ❌ Error: {e}")
            
            if spawned > 0 or posted > 0:
                print(f"\n✅ Hoàn thành: {spawned} spawned, {posted} posted")
            else:
                print(f"\n✅ Không có task nào cần xử lý")

if __name__ == '__main__':
    main()
