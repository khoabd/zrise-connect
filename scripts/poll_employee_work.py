#!/usr/bin/env python3
"""
poll_employee_work.py - Lắng nghe task mới từ Zrise
Tasks được lưu vào SQLite + .tasks/<task_id>/detail.json
"""

import os
import sys
import json
import ssl
import xmlrpc.client
from datetime import datetime
from pathlib import Path

# Import db module
sys.path.insert(0, str(Path(__file__).parent))
from db import init_db, create_task, get_task, update_task_status, get_all_agents, save_task_detail, add_task_log, get_tasks_dir

_ssl_ctx = ssl._create_unverified_context()

DONE_KEYWORDS = ['done', 'cancelled', 'cancel', 'hoàn thành', 'hủy']

def get_openclaw_config_path():
    global_config = Path.home() / '.openclaw' / 'openclaw.json'
    if global_config.exists():
        return global_config
    root = Path(__file__).parent.parent.parent.parent
    local = root / 'openclaw.json'
    if local.exists():
        return local
    return global_config

def is_done(stage_name):
    return any(kw in (stage_name or '').lower() for kw in DONE_KEYWORDS)

def poll_tasks(employee_id, limit=20, sync=False):
    """Poll tasks from Zrise, trả về dict với new_tasks.
    
    Args:
        employee_id: Employee ID to poll for
        limit: Max tasks to fetch
        sync: If True, sync ALL tasks (including already-seen) to catch up on missed tasks
    """
    # Init DB
    init_db()
    
    with open(str(get_openclaw_config_path()), 'r') as f:
        cfg = json.load(f)

    env = cfg['skills']['entries']['zrise-connect']['env']
    url = env['ZRISE_URL'].rstrip('/')
    db_name = env['ZRISE_DB']
    username = env['ZRISE_USERNAME']
    secret = env.get('ZRISE_API_KEY') or env.get('ZRISE_PASSWORD')

    if secret is not None:
        secret = str(secret)

    common = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common', allow_none=True, context=_ssl_ctx)
    uid = common.authenticate(db_name, username, secret, {})

    if not uid:
        print("❌ Zrise authentication failed")
        return {"new_tasks": [], "all_tasks": [], "synced": 0}

    models = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object', allow_none=True, context=_ssl_ctx)

    # Find employee
    employees = models.execute_kw(db_name, uid, secret, 'hr.employee', 'search_read',
                                 [[('user_id', '=', uid)]],
                                 {'fields': ['id', 'name']})
    
    if not employees:
        print(f"❌ Không tìm thấy employee cho user ID {uid}")
        return {"new_tasks": [], "all_tasks": [], "synced": 0}
    
    # Get tasks from Zrise
    try:
        tasks = models.execute_kw(db_name, uid, secret, 'project.task', 'search_read',
                                 [[('user_ids', 'in', [uid])]],
                                 {'fields': ['id', 'name', 'description', 'stage_id', 
                                            'project_id', 'date_deadline', 'priority',
                                            'user_ids', 'write_date'],
                                  'limit': limit, 'order': 'id desc'})
    except Exception as e:
        print(f"search_read failed: {e}")
        return {"new_tasks": [], "all_tasks": [], "synced": 0}
    
    new_tasks = []
    all_tasks = []
    synced_count = 0
    
    for task in tasks:
        task_id = task['id']
        stage_name = (task.get('stage_id') or ['', 'Unknown'])[1]
        
        all_tasks.append(task)
        
        # Skip done tasks
        if is_done(stage_name):
            continue
        
        # Check if task already exists in DB
        existing = get_task(task_id)
        
        if existing:
            # Task đã tồn tại - kiểm tra nếu cần sync
            if sync:
                # Update task info trong detail.json
                task_data = {
                    "task_id": task_id,
                    "name": task.get('name', ''),
                    "description": task.get('description', ''),
                    "stage": stage_name,
                    "project": task.get('project_id'),
                    "priority": task.get('priority'),
                    "deadline": task.get('date_deadline'),
                    "fetched_at": datetime.now().isoformat(),
                    "synced_at": datetime.now().isoformat()
                }
                save_task_detail(task_id, task_data)
                add_task_log(task_id, "task_synced", "system", {
                    "source": "zrise_sync",
                    "stage": stage_name
                })
                synced_count += 1
            continue
        
        # Task mới - tạo trong DB + detail.json
        task_data = {
            "task_id": task_id,
            "name": task.get('name', ''),
            "description": task.get('description', ''),
            "stage": stage_name,
            "project": task.get('project_id'),
            "priority": task.get('priority'),
            "deadline": task.get('date_deadline'),
            "fetched_at": datetime.now().isoformat()
        }
        
        # Create in DB
        create_task(
            task_id=task_id,
            name=task.get('name', ''),
            priority=task.get('priority', ''),
            deadline=task.get('date_deadline', '')
        )
        update_task_status(task_id, 'new')
        
        # Save detail.json
        save_task_detail(task_id, task_data)
        
        # Add log
        add_task_log(task_id, "task_fetched", "system", {
            "source": "zrise_poll" if not sync else "zrise_sync",
            "stage": stage_name
        })
        
        new_tasks.append(task)
    
    return {
        "new_tasks_count": len(new_tasks),
        "new_tasks": [{'id': t['id'], 'name': t['name']} for t in new_tasks],
        "all_tasks_count": len(all_tasks),
        "synced": synced_count
    }

def auto_detect_employee_id():
    """Tự động lấy employee ID từ Zrise session (user đang login)."""
    from zrise_utils import connect_zrise
    
    db_name, uid, secret, models, url = connect_zrise()
    
    # Tìm employee của user đang login
    employees = models.execute_kw(db_name, uid, secret, 'hr.employee', 'search_read',
                                 [[('user_id', '=', uid)]],
                                 {'fields': ['id', 'name']})
    
    if employees:
        return employees[0]['id']
    
    return None

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Poll tasks from Zrise for employee')
    parser.add_argument('--employee-id', type=int, help='Employee ID (auto-detected if not provided)')
    parser.add_argument('--limit', type=int, default=20, help='Max tasks to fetch (default: 20)')
    parser.add_argument('--sync', action='store_true', help='Sync ALL tasks from Zrise (catch up on missed tasks after restart)')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--once', action='store_true')
    
    args = parser.parse_args()
    
    # Auto-detect employee_id nếu không cung cấp
    employee_id = args.employee_id
    if employee_id is None:
        employee_id = auto_detect_employee_id()
        if employee_id is None:
            # Silent exit - can't work without credentials
            sys.exit(1)
    
    result = poll_tasks(
        employee_id=employee_id,
        limit=args.limit,
        sync=args.sync
    )
    
    # Only output if there ARE new tasks or sync happened
    # Otherwise silent exit - no agent needs to think
    if result['new_tasks_count'] > 0:
        print(f"📋 Có {result['new_tasks_count']} task mới:")
        for t in result['new_tasks']:
            print(f"   • [{t['id']}] {t['name']}")
    elif result.get('synced', 0) > 0:
        print(f"🔄 Đã sync {result['synced']} task(s) từ Zrise")
    # else: silent - no output, no agent call needed

if __name__ == '__main__':
    main()
