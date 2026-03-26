#!/usr/bin/env python3
"""
poll_employee_work.py - Lắng nghe task mới từ Zrise cho employee cụ thể
Hỗ trợ deduplication, rate limiting, và smart notification
"""

import os
import sys
import json
import ssl
import xmlrpc.client
import hashlib
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Disable SSL verification for macOS Python
_ssl_ctx = ssl._create_unverified_context()

DONE_KEYWORDS = ['done', 'cancelled', 'cancel', 'hoàn thành', 'hủy']
PROCESSED_KEYWORDS = ['completed', 'done', 'approved']

# Rate limit: re-notify về task pending sau bao lâu (giây)
DEFAULT_REMINDER_INTERVAL = 3600  # 1 tiếng

def get_openclaw_config_path():
    """Get path to openclaw.json config file."""
    global_config = Path.home() / '.openclaw' / 'openclaw.json'
    if global_config.exists():
        return global_config
    
    # Fallback: workspace root
    root = Path(__file__).parent.parent.parent.parent
    local = root / 'openclaw.json'
    if local.exists():
        return local
    
    return global_config

def get_state_path(subpath=''):
    """Get state directory path."""
    root = Path(__file__).parent.parent.parent.parent
    state_dir = root / 'state' / 'zrise'
    if subpath:
        state_dir = state_dir / subpath
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir

def get_workspace_root():
    """Get workspace root directory."""
    return Path(__file__).parent.parent.parent.parent

def load_poll_state(employee_id):
    """Load previous poll state for dedup/change detection."""
    state_dir = get_state_path('poll-state')
    state_file = state_dir / f'{employee_id}.json'
    if state_file.exists():
        return json.loads(state_file.read_text(encoding='utf-8'))
    return {
        'seen_tasks': {},
        'notified_tasks': {},  # {task_id: {"notified_at": ISO, "count": N}}
        'last_poll': None
    }

def save_poll_state(employee_id, state):
    """Save poll state."""
    state_dir = get_state_path('poll-state')
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f'{employee_id}.json'
    state['last_poll'] = datetime.now(timezone.utc).isoformat()
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

def load_pending_registry():
    """Đọc danh sách task pending từ registry"""
    workspace_root = get_workspace_root()
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

def save_pending_registry(task_ids):
    """Ghi danh sách task pending vào registry"""
    workspace_root = get_workspace_root()
    registry_file = workspace_root / "tasks" / "registry" / "pending.json"
    registry_file.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        data = {"task_ids": sorted(list(task_ids))}
        with open(registry_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Lỗi ghi registry pending: {e}")
        return False

def task_hash(task):
    """Hash of fields that indicate a meaningful change."""
    payload = {
        'name': (task.get('name') or ''),
        'stage': (task.get('stage_id') or ['', ''])[1],
        'user_ids': sorted(task.get('user_ids', [])),
        'priority': task.get('priority', ''),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]

def is_done(stage_name):
    return any(kw in (stage_name or '').lower() for kw in DONE_KEYWORDS)

def is_processed(task):
    """Kiểm tra task đã được xử lý chưa (stage Done hoặc có output)."""
    stage_name = (task.get('stage_id') or ['', ''])[1]
    if is_done(stage_name):
        return True
    
    # Check task detail file for processed status
    workspace_root = get_workspace_root()
    task_file = workspace_root / "tasks" / "details" / f"{task['id']}.json"
    if task_file.exists():
        try:
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            status = task_data.get('status', '')
            # Task đã được claim và xử lý
            if status in ['READY_FOR_FEEDBACK_REVIEW', 'PENDING_FINAL_APPROVE', 'completed', 'done']:
                return True
            # Có output từ agent
            if task_data.get('output') or task_data.get('result'):
                return True
        except:
            pass
    
    return False

def should_remind(task_id, notified_tasks, reminder_interval=DEFAULT_REMINDER_INTERVAL):
    """Kiểm tra có nên remind về task này không.
    
    Returns: (should_remind: bool, reason: str, last_notified: datetime|None)
    """
    if task_id not in notified_tasks:
        return True, "first_time", None
    
    notified_info = notified_tasks[task_id]
    last_notified_str = notified_info.get('notified_at')
    if not last_notified_str:
        return True, "no_timestamp", None
    
    try:
        last_notified = datetime.fromisoformat(last_notified_str.replace('Z', '+00:00'))
        if not last_notified.tzinfo:
            last_notified = last_notified.replace(tzinfo=timezone.utc)
    except:
        return True, "invalid_timestamp", None
    
    now = datetime.now(timezone.utc)
    elapsed = (now - last_notified).total_seconds()
    
    if elapsed >= reminder_interval:
        return True, f"reminder_{int(elapsed/60)}min", last_notified
    else:
        return False, f"wait_{int((reminder_interval-elapsed)/60)}min", last_notified

def poll_tasks(employee_id, limit=20, sla_hours=24, deadline_hours=48, stale_hours=72,
               reminder_interval=DEFAULT_REMINDER_INTERVAL, include_reminders=False):
    """Poll and categorize tasks for employee.
    
    Args:
        employee_id: Employee ID in Zrise
        limit: Max tasks to fetch
        reminder_interval: Seconds between reminders for same task (default: 3600 = 1h)
        include_reminders: If True, include tasks that need reminders in "new" list
    
    Returns:
        dict với:
            - new_tasks: Task mới thực sự (chưa từng được notify)
            - pending_reminders: Task đang pending đã notify > reminder_interval
            - already_notified: Task đã notify gần đây (ko báo nữa)
            - processed: Task đã done/approved (ko báo)
            - stats: summary
    """
    with open(str(get_openclaw_config_path()), 'r') as f:
        cfg = json.load(f)

    env = cfg['skills']['entries']['zrise-connect']['env']
    url = env['ZRISE_URL'].rstrip('/')
    db = env['ZRISE_DB']
    username = env['ZRISE_USERNAME']
    secret = env.get('ZRISE_API_KEY') or env.get('ZRISE_PASSWORD')

    if secret is not None:
        secret = str(secret)

    common = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common', allow_none=True, context=_ssl_ctx)
    uid = common.authenticate(db, username, secret, {})

    if not uid:
        print("❌ Zrise authentication failed")
        return {"new_tasks": [], "pending_reminders": [], "already_notified": [], "processed": [], "stats": {}}

    models = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object', allow_none=True, context=_ssl_ctx)

    # Find employee by user
    employees = models.execute_kw(db, uid, secret, 'hr.employee', 'search_read',
                                 [[('user_id', '=', uid)]],
                                 {'fields': ['id', 'name']})
    
    if not employees:
        print(f"❌ Không tìm thấy employee cho user ID {uid}")
        return {"new_tasks": [], "pending_reminders": [], "already_notified": [], "processed": [], "stats": {}}
    
    actual_employee_id = employees[0]['id']
    
    # Get tasks from Zrise
    try:
        tasks = models.execute_kw(db, uid, secret, 'project.task', 'search_read',
                                 [[('user_ids', 'in', [uid])]],
                                 {'fields': ['id', 'name', 'description', 'stage_id', 
                                            'project_id', 'date_deadline', 'priority',
                                            'user_ids', 'write_date', 'create_date',
                                            'date_last_stage_update'],
                                  'limit': limit, 'order': 'id desc'})
    except Exception as e:
        print(f"search_read failed: {e}")
        return {"new_tasks": [], "pending_reminders": [], "already_notified": [], "processed": [], "stats": {}}
    
    # Load poll state
    poll_state = load_poll_state(employee_id)
    seen_tasks = poll_state.get('seen_tasks', {})
    notified_tasks = poll_state.get('notified_tasks', {})
    
    # Categorize tasks
    new_tasks = []           # Task mới, chưa từng notify
    pending_reminders = []    # Task đã notify nhưng quá reminder_interval
    already_notified = []    # Task đã notify gần đây, ko cần báo lại
    processed = []           # Task đã done/approved
    stale = []
    
    now = datetime.now(timezone.utc)
    
    for task in tasks:
        task_id = task['id']
        stage_name = (task.get('stage_id') or ['', 'Unknown'])[1]
        
        # Update seen_tasks
        current_hash = task_hash(task)
        seen_tasks[task_id] = current_hash
        
        # Skip done tasks
        if is_done(stage_name):
            processed.append(task)
            # Remove from notified tracking if completed
            if task_id in notified_tasks:
                del notified_tasks[task_id]
            continue
        
        # Check if processed (has output from agent)
        if is_processed(task):
            processed.append(task)
            continue
        
        # Check notification status
        print(f"DEBUG: Before should_remind call at line 274")
        print(f"DEBUG: task_id={task_id}, notified_tasks={notified_tasks}")
        should_remind, reason, last_notified = should_remind(
            task_id, notified_tasks, reminder_interval
        )
        
        if should_remind:
            # Mới hoặc cần reminder
            task['_notify_reason'] = reason
            task['_last_notified'] = last_notified.isoformat() if last_notified else None
            new_tasks.append(task)
            
            # Update notified tracking
            notified_tasks[task_id] = {
                'notified_at': now.isoformat(),
                'count': notified_tasks.get(task_id, {}).get('count', 0) + 1
            }
        else:
            # Đã notify gần đây
            task['_wait_remaining'] = int(reminder_interval - (now - last_notified).total_seconds())
            already_notified.append(task)
        
        # Check stale
        write_date = task.get('write_date')
        if write_date:
            try:
                write_dt = datetime.fromisoformat(write_date.replace('Z', '+00:00'))
                if not write_dt.tzinfo:
                    write_dt = write_dt.replace(tzinfo=timezone.utc)
                age = now - write_dt
                if age.total_seconds() > stale_hours * 3600:
                    stale.append(task)
            except:
                pass
    
    # Add new tasks to registry
    if new_tasks:
        pending_task_ids = load_pending_registry()
        new_task_ids = [task['id'] for task in new_tasks]
        pending_task_ids.update(new_task_ids)
        
        if save_pending_registry(pending_task_ids):
            print(f"✅ Đã thêm {len(new_task_ids)} task mới vào registry: {new_task_ids}")
        else:
            print(f"❌ Lỗi: Không thể lưu registry mới")
    
    # Save poll state
    poll_state['seen_tasks'] = seen_tasks
    poll_state['notified_tasks'] = notified_tasks
    save_poll_state(employee_id, poll_state)
    
    # Prepare result
    result = {
        "new_tasks_count": len(new_tasks),
        "pending_reminders_count": len(pending_reminders),
        "already_notified_count": len(already_notified),
        "processed_count": len(processed),
        "stale_count": len(stale),
        "new_tasks": [{'id': t['id'], 'name': t['name'], 'reason': t.get('_notify_reason')} for t in new_tasks],
        "pending_reminders": [{'id': t['id'], 'name': t['name']} for t in pending_reminders],
        "already_notified": [{'id': t['id'], 'name': t['name'], 'wait_sec': t.get('_wait_remaining', 0)} for t in already_notified],
        "processed": [{'id': t['id'], 'name': t['name']} for t in processed],
        "stale": [{'id': t['id'], 'name': t['name']} for t in stale],
        "stats": {
            "total_fetched": len(tasks),
            "reminder_interval_seconds": reminder_interval,
            "last_poll": now.isoformat()
        }
    }
    
    return result

def format_notification(result, employee_id):
    """Format kết quả thành message dễ đọc cho user."""
    messages = []
    
    if result['new_tasks_count'] > 0:
        task_list = '\n'.join([f"  • [{t['id']}] {t['name']}" for t in result['new_tasks']])
        messages.append(f"📋 **{result['new_tasks_count']} task mới:**\n{task_list}")
    
    if result['pending_reminders_count'] > 0:
        task_list = '\n'.join([f"  • [{t['id']}] {t['name']}" for t in result['pending_reminders']])
        messages.append(f"⏰ **{result['pending_reminders_count']} task cần xử lý (quá 1 tiếng):**\n{task_list}")
    
    if result['processed_count'] > 0:
        messages.append(f"✅ {result['processed_count']} task đã hoàn thành (đã loại)")
    
    if result['already_notified_count'] > 0:
        # Silent - don't mention these
        pass
    
    if not messages:
        messages.append("ℹ️ Không có task mới cần xử lý.")
    
    return '\n'.join(messages)

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Poll tasks from Zrise for employee')
    parser.add_argument('--employee-id', type=int, required=True, help='Employee ID in Zrise')
    parser.add_argument('--limit', type=int, default=20, help='Max tasks to fetch (default: 20)')
    parser.add_argument('--sla-hours', type=int, default=24, help='SLA breach threshold in hours (default: 24)')
    parser.add_argument('--deadline-hours', type=int, default=48, help='Deadline soon threshold in hours (default: 48)')
    parser.add_argument('--stale-hours', type=int, default=72, help='Stale task threshold in hours (default: 72)')
    parser.add_argument('--reminder-interval', type=int, default=3600, 
                       help='Seconds before re-notifying same task (default: 3600 = 1 hour)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--notify-only', action='store_true', help='Only notify about new tasks')
    parser.add_argument('--once', action='store_true', help='Run once and exit (no loop)')
    parser.add_argument('--quiet', action='store_true', help='Only output count, no details')
    
    args = parser.parse_args()
    
    result = poll_tasks(
        employee_id=args.employee_id,
        limit=args.limit,
        sla_hours=args.sla_hours,
        deadline_hours=args.deadline_hours,
        stale_hours=args.stale_hours,
        reminder_interval=args.reminder_interval,
        include_reminders=True
    )
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.notify_only:
        # Chế độ notify: chỉ báo task mới/thực sự cần xử lý
        if result['new_tasks_count'] > 0:
            print(format_notification(result, args.employee_id))
        elif result['pending_reminders_count'] > 0:
            print(format_notification(result, args.employee_id))
        else:
            if not args.quiet:
                print("ℹ️ Không có task mới cần xử lý.")
            # Still exit 0 for cron
    else:
        # Chế độ verbose
        print(f"📊 Poll result for employee {args.employee_id}:")
        print(f"   Task mới: {result['new_tasks_count']}")
        print(f"   Cần reminder: {result['pending_reminders_count']}")
        print(f"   Đã notify (chờ): {result['already_notified_count']}")
        print(f"   Đã xử lý: {result['processed_count']}")
        print(f"   Stale: {result['stale_count']}")
        
        if result['new_tasks']:
            print("\n📋 Task mới:")
            for t in result['new_tasks']:
                print(f"   • [{t['id']}] {t['name']}")

if __name__ == '__main__':
    main()
