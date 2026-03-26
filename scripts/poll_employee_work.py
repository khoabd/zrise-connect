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

def poll_tasks(employee_id, limit=20):
    """Poll tasks from Zrise, trả về dict với new_tasks."""
    # Init DB
    init_db()
    
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
        return {"new_tasks": [], "all_tasks": []}

    models = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object', allow_none=True, context=_ssl_ctx)

    # Find employee
    employees = models.execute_kw(db, uid, secret, 'hr.employee', 'search_read',
                                 [[('user_id', '=', uid)]],
                                 {'fields': ['id', 'name']})
    
    if not employees:
        print(f"❌ Không tìm thấy employee cho user ID {uid}")
        return {"new_tasks": [], "all_tasks": []}
    
    # Get tasks from Zrise
    try:
        tasks = models.execute_kw(db, uid, secret, 'project.task', 'search_read',
                                 [[('user_ids', 'in', [uid])]],
                                 {'fields': ['id', 'name', 'description', 'stage_id', 
                                            'project_id', 'date_deadline', 'priority',
                                            'user_ids', 'write_date'],
                                  'limit': limit, 'order': 'id desc'})
    except Exception as e:
        print(f"search_read failed: {e}")
        return {"new_tasks": [], "all_tasks": []}
    
    new_tasks = []
    all_tasks = []
    
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
            # Task đã tồn tại - bỏ qua
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
            "source": "zrise_poll",
            "stage": stage_name
        })
        
        new_tasks.append(task)
    
    return {
        "new_tasks_count": len(new_tasks),
        "new_tasks": [{'id': t['id'], 'name': t['name']} for t in new_tasks],
        "all_tasks_count": len(all_tasks)
    }

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Poll tasks from Zrise for employee')
    parser.add_argument('--employee-id', type=int, required=True)
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--once', action='store_true')
    
    args = parser.parse_args()
    
    result = poll_tasks(
        employee_id=args.employee_id,
        limit=args.limit
    )
    
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result['new_tasks_count'] > 0:
            print(f"📋 Có {result['new_tasks_count']} task mới:")
            for t in result['new_tasks']:
                print(f"   • [{t['id']}] {t['name']}")
        else:
            print("ℹ️ Không có task mới")

if __name__ == '__main__':
    main()
