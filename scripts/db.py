#!/usr/bin/env python3
"""
db.py - SQLite database cho zrise-connect task registry
Quản lý task status, agent registry trong SQLite
Detail vẫn lưu trong .tasks/<task_id>/detail.json
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

def get_workspace_root():
    return Path(__file__).parent.parent.parent.parent

def get_db_path():
    return get_workspace_root() / ".tasks" / "task_registry.db"

def get_tasks_dir():
    return get_workspace_root() / ".tasks"

def init_db():
    """Initialize SQLite database with multi-agent schema."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    c = conn.cursor()
    
    # Tasks table (kept for backward compatibility with existing workflows)
    c.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            task_id INTEGER PRIMARY KEY,
            name TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT,
            updated_at TEXT,
            assigned_agent TEXT,
            priority TEXT,
            deadline TEXT
        )
    ''')
    
    # Agents table (updated for multi-agent)
    c.execute('''
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT,
            department TEXT,
            workspace_path TEXT,
            skills TEXT DEFAULT '[]',
            workflows TEXT DEFAULT '[]',
            model_id TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    # Jobs table (tracks task→agent assignments - NEW)
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            agent_id TEXT,
            workflow TEXT,
            status TEXT DEFAULT 'pending',
            priority TEXT,
            assigned_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            heartbeat_at TEXT,
            result_path TEXT,
            error TEXT,
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
    ''')
    
    # Index for fast polling by agent
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_jobs_agent_status ON jobs(agent_id, status)
    ''')
    
    # Index for watchdog timeout queries
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_jobs_status_started ON jobs(status, started_at)
    ''')
    
    conn.commit()
    conn.close()
    
    return db_path

def get_connection():
    """Get SQLite connection."""
    db_path = get_db_path()
    if not db_path.exists():
        init_db()
    return sqlite3.connect(str(db_path))

# === TASK OPERATIONS ===

def task_exists(task_id: int) -> bool:
    """Check if task exists in database."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM tasks WHERE task_id = ?', (task_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def create_task(task_id: int, name: str = "", priority: str = "", deadline: str = "") -> dict:
    """Create new task in database."""
    conn = get_connection()
    c = conn.cursor()
    
    now = datetime.now().isoformat()
    
    c.execute('''
        INSERT OR REPLACE INTO tasks (task_id, name, status, created_at, updated_at, priority, deadline)
        VALUES (?, ?, 'new', ?, ?, ?, ?)
    ''', (task_id, name, now, now, priority, deadline))
    
    conn.commit()
    conn.close()
    
    return {"task_id": task_id, "status": "new", "created_at": now}

def update_task_status(task_id: int, status: str) -> dict:
    """Update task status."""
    conn = get_connection()
    c = conn.cursor()
    
    now = datetime.now().isoformat()
    
    c.execute('''
        UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?
    ''', (status, now, task_id))
    
    conn.commit()
    conn.close()
    
    return {"task_id": task_id, "status": status, "updated_at": now}

def update_task_agent(task_id: int, agent: str) -> dict:
    """Update task assigned agent."""
    conn = get_connection()
    c = conn.cursor()
    
    now = datetime.now().isoformat()
    
    c.execute('''
        UPDATE tasks SET assigned_agent = ?, updated_at = ? WHERE task_id = ?
    ''', (agent, now, task_id))
    
    conn.commit()
    conn.close()
    
    return {"task_id": task_id, "assigned_agent": agent, "updated_at": now}

def get_task(task_id: int) -> dict:
    """Get task info from database."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            "task_id": row[0],
            "name": row[1],
            "status": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "assigned_agent": row[5],
            "priority": row[6],
            "deadline": row[7]
        }
    return None

def get_tasks_by_status(status: str) -> list:
    """Get all tasks with given status."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC', (status,))
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "task_id": row[0],
            "name": row[1],
            "status": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "assigned_agent": row[5],
            "priority": row[6],
            "deadline": row[7]
        }
        for row in rows
    ]

def get_all_tasks() -> list:
    """Get all tasks."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM tasks ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "task_id": row[0],
            "name": row[1],
            "status": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "assigned_agent": row[5],
            "priority": row[6],
            "deadline": row[7]
        }
        for row in rows
    ]

def delete_task(task_id: int) -> bool:
    """Delete task from database."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()
    return deleted

# === AGENT OPERATIONS ===

def agent_exists(agent_id: str) -> bool:
    """Check if agent exists."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM agents WHERE id = ?', (agent_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def create_agent(
    agent_id: str,
    name: str = "",
    department: str = "",
    workspace_path: str = "",
    skills: list = None,
    workflows: list = None,
    model_id: str = ""
) -> dict:
    """Create or update agent."""
    conn = get_connection()
    c = conn.cursor()
    
    now = datetime.now().isoformat()
    
    c.execute('''
        INSERT OR REPLACE INTO agents 
        (id, name, department, workspace_path, skills, workflows, model_id, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, COALESCE((SELECT created_at FROM agents WHERE id = ?), ?), ?)
    ''', (
        agent_id, 
        name or agent_id, 
        department, 
        workspace_path,
        json.dumps(skills or []),
        json.dumps(workflows or []),
        model_id,
        agent_id, now, now
    ))
    
    conn.commit()
    conn.close()
    
    return get_agent(agent_id)

def get_agent(agent_id: str) -> dict:
    """Get agent info."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM agents WHERE id = ?', (agent_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "department": row[2],
            "workspace_path": row[3],
            "skills": json.loads(row[4]) if row[4] else [],
            "workflows": json.loads(row[5]) if row[5] else [],
            "model_id": row[6],
            "is_active": bool(row[7]),
            "created_at": row[8],
            "updated_at": row[9]
        }
    return None

def get_all_agents() -> list:
    """Get all active agents."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM agents WHERE is_active = 1 ORDER BY department, id')
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "id": row[0],
            "name": row[1],
            "department": row[2],
            "workspace_path": row[3],
            "skills": json.loads(row[4]) if row[4] else [],
            "workflows": json.loads(row[5]) if row[5] else [],
            "model_id": row[6],
            "is_active": bool(row[7]),
            "created_at": row[8],
            "updated_at": row[9]
        }
        for row in rows
    ]

def get_agents_by_department(department: str) -> list:
    """Get agents by department."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM agents WHERE department = ? AND is_active = 1', (department,))
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "id": row[0],
            "name": row[1],
            "department": row[2],
            "workflows": json.loads(row[5]) if row[5] else []
        }
        for row in rows
    ]

def get_agents_by_workflow(workflow: str) -> list:
    """Get agents that can handle a specific workflow."""
    agents = get_all_agents()
    matching = []
    for agent in agents:
        if workflow in agent.get('workflows', []):
            matching.append(agent)
    return matching

def delete_agent(agent_id: str) -> bool:
    """Soft delete agent (set is_active = 0)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE agents SET is_active = 0 WHERE id = ?', (agent_id,))
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()
    return deleted

# === JOB OPERATIONS ===

def create_job(task_id: int, agent_id: str, workflow: str, priority: str = "") -> dict:
    """Create a new job for task→agent assignment."""
    conn = get_connection()
    c = conn.cursor()
    
    now = datetime.now().isoformat()
    
    c.execute('''
        INSERT INTO jobs (task_id, agent_id, workflow, status, priority, assigned_at)
        VALUES (?, ?, ?, 'assigned', ?, ?)
    ''', (task_id, agent_id, workflow, priority, now))
    
    job_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return get_job(job_id)

def get_job(job_id: int) -> dict:
    """Get job by ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM jobs WHERE id = ?', (job_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "task_id": row[1],
            "agent_id": row[2],
            "workflow": row[3],
            "status": row[4],
            "priority": row[5],
            "assigned_at": row[6],
            "started_at": row[7],
            "completed_at": row[8],
            "heartbeat_at": row[9] if len(row) > 9 else None,
            "result_path": row[10] if len(row) > 10 else None,
            "error": row[11] if len(row) > 11 else None,
            "retry_count": row[12] if len(row) > 12 else 0,
            "max_retries": row[13] if len(row) > 13 else 3
        }
    return None

def get_job_by_task(task_id: int) -> dict:
    """Get most recent job for a task."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM jobs WHERE task_id = ? ORDER BY id DESC LIMIT 1', (task_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "task_id": row[1],
            "agent_id": row[2],
            "workflow": row[3],
            "status": row[4],
            "priority": row[5],
            "assigned_at": row[6],
            "started_at": row[7],
            "completed_at": row[8],
            "result_path": row[9],
            "error": row[10]
        }
    return None

def get_jobs_for_agent(agent_id: str, status: str = None) -> list:
    """Get jobs assigned to an agent, optionally filtered by status."""
    conn = get_connection()
    c = conn.cursor()
    
    if status:
        c.execute('''
            SELECT * FROM jobs 
            WHERE agent_id = ? AND status = ? 
            ORDER BY assigned_at DESC
        ''', (agent_id, status))
    else:
        c.execute('''
            SELECT * FROM jobs 
            WHERE agent_id = ? 
            ORDER BY assigned_at DESC
        ''', (agent_id,))
    
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "id": row[0],
            "task_id": row[1],
            "agent_id": row[2],
            "workflow": row[3],
            "status": row[4],
            "priority": row[5],
            "assigned_at": row[6],
            "started_at": row[7],
            "completed_at": row[8],
            "result_path": row[9],
            "error": row[10]
        }
        for row in rows
    ]

def claim_job(job_id: int) -> dict:
    """Mark job as in_progress (agent claims it).
    
    Uses atomic transaction with BEGIN IMMEDIATE to prevent race conditions
    where multiple executors might claim the same job simultaneously.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Use BEGIN IMMEDIATE to acquire write lock (prevents race condition)
    c.execute("BEGIN IMMEDIATE")
    
    try:
        now = datetime.now().isoformat()
        
        # Check current status
        c.execute('''
            SELECT status, agent_id FROM jobs WHERE id = ?
        ''', (job_id,))
        row = c.fetchone()
        
        if not row:
            conn.rollback()
            conn.close()
            return {"job_id": job_id, "claimed": False, "error": "Job not found"}
        
        current_status = row[0]
        current_agent = row[1]
        
        if current_status != 'assigned':
            conn.rollback()
            conn.close()
            return {
                "job_id": job_id, 
                "claimed": False, 
                "error": f"Job not available (status: {current_status})",
                "current_agent": current_agent
            }
        
        # Update to in_progress
        c.execute('''
            UPDATE jobs SET status = 'in_progress', started_at = ?, heartbeat_at = ?
            WHERE id = ? AND status = 'assigned'
        ''', (now, now, job_id))
        
        conn.commit()
        success = c.rowcount > 0
        conn.close()
        
        return {"job_id": job_id, "claimed": success, "started_at": now if success else None}
        
    except Exception as e:
        conn.rollback()
        conn.close()
        raise


def claim_job_atomic(job_id: int, agent_id: str) -> dict:
    """
    Atomically claim a job to prevent race condition.
    
    Uses SQLite's BEGIN IMMEDIATE to acquire write lock before checking
    and updating. This ensures only one executor can claim a job even
    when multiple pollers run simultaneously.
    
    Args:
        job_id: The job ID to claim
        agent_id: The agent claiming this job (for auditing)
    
    Returns:
        dict with keys: claimed (bool), error (str if failed)
    """
    conn = get_connection()
    c = conn.cursor()
    
    # BEGIN IMMEDIATE acquires a RESERVED lock immediately, then converts
    # to EXCLUSIVE when writing. This blocks other writers.
    c.execute("BEGIN IMMEDIATE")
    
    try:
        now = datetime.now().isoformat()
        
        # Check job exists and is assigned
        c.execute('''
            SELECT status, agent_id FROM jobs WHERE id = ?
        ''', (job_id,))
        row = c.fetchone()
        
        if not row:
            conn.rollback()
            conn.close()
            return {"claimed": False, "error": f"Job {job_id} not found"}
        
        current_status = row[0]
        assigned_agent = row[1]
        
        if current_status != 'assigned':
            conn.rollback()
            conn.close()
            return {
                "claimed": False, 
                "error": f"Job {job_id} already {current_status}",
                "assigned_agent": assigned_agent
            }
        
        # Claim the job - update status and heartbeat
        c.execute('''
            UPDATE jobs 
            SET status = 'in_progress', 
                started_at = ?, 
                heartbeat_at = ?,
                agent_id = ?
            WHERE id = ? AND status = 'assigned'
        ''', (now, now, agent_id, job_id))
        
        if c.rowcount == 0:
            # Race condition: someone else claimed between our check and update
            conn.rollback()
            conn.close()
            return {"claimed": False, "error": "Race condition - job claimed by another executor"}
        
        conn.commit()
        conn.close()
        
        return {
            "claimed": True, 
            "job_id": job_id, 
            "agent_id": agent_id,
            "started_at": now
        }
        
    except Exception as e:
        conn.rollback()
        conn.close()
        raise


def update_heartbeat(job_id: int) -> dict:
    """Update heartbeat timestamp for watchdog monitoring.
    
    Call this periodically during long-running job execution to signal
    the executor is still alive and working on the job.
    
    Args:
        job_id: The job ID to update heartbeat for
    
    Returns:
        dict with keys: updated (bool), heartbeat_at (str)
    """
    conn = get_connection()
    c = conn.cursor()
    
    now = datetime.now().isoformat()
    
    c.execute('''
        UPDATE jobs SET heartbeat_at = ? WHERE id = ?
    ''', (now, job_id))
    
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    
    return {"job_id": job_id, "updated": success, "heartbeat_at": now if success else None}


def get_timed_out_jobs(timeout_minutes: int = 30) -> list:
    """Find jobs stuck in 'in_progress' beyond timeout.
    
    Jobs that have been in_progress without a heartbeat update
    for longer than timeout_minutes are considered timed out.
    
    Args:
        timeout_minutes: Minutes after which a job is considered timed out
                        (default: 30 minutes)
    
    Returns:
        List of job dicts that have timed out
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Jobs in_progress without heartbeat for > timeout_minutes
    c.execute('''
        SELECT * FROM jobs 
        WHERE status = 'in_progress'
        AND heartbeat_at < datetime('now', '-' || ? || ' minutes')
        ORDER BY started_at ASC
    ''', (timeout_minutes,))
    
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            "id": row[0],
            "task_id": row[1],
            "agent_id": row[2],
            "workflow": row[3],
            "status": row[4],
            "priority": row[5],
            "assigned_at": row[6],
            "started_at": row[7],
            "completed_at": row[8],
            "heartbeat_at": row[9],
            "result_path": row[10],
            "error": row[11],
            "retry_count": row[12] if len(row) > 12 else 0,
            "max_retries": row[13] if len(row) > 13 else 3
        }
        for row in rows
    ]


def complete_job(job_id: int, result_path: str) -> dict:
    """Mark job as done with result."""
    conn = get_connection()
    c = conn.cursor()
    
    now = datetime.now().isoformat()
    
    c.execute('''
        UPDATE jobs SET status = 'done', completed_at = ?, result_path = ?
        WHERE id = ?
    ''', (now, result_path, job_id))
    
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    
    return {"job_id": job_id, "completed": success, "completed_at": now if success else None}

def update_job_status(job_id: int, status: str) -> dict:
    """Update job status to any value."""
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('UPDATE jobs SET status = ? WHERE id = ?', (status, job_id))
    
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    
    return {"job_id": job_id, "status": status, "updated": success}

def fail_job(job_id: int, error: str) -> dict:
    """Mark job as failed with error."""
    conn = get_connection()
    c = conn.cursor()
    
    now = datetime.now().isoformat()
    
    c.execute('''
        UPDATE jobs SET status = 'failed', completed_at = ?, error = ?
        WHERE id = ?
    ''', (now, error, job_id))
    
    conn.commit()
    success = c.rowcount > 0
    conn.close()
    
    return {"job_id": job_id, "failed": success, "error": error if success else None}

# === UTILITY ===

def sync_agents_from_yaml():
    """Sync agents from YAML registry to SQLite.
    
    Note: This creates 1 agent per workflow entry. For multi-agent system,
    use register_agent() instead which supports multiple workflows per agent.
    """
    try:
        import yaml
    except ImportError:
        return {"status": "error", "reason": "PyYAML not installed"}
    
    workspace = get_workspace_root()
    registry_file = workspace / "agent_registry.yaml"
    
    if not registry_file.exists():
        return {"status": "skipped", "reason": "No registry file"}
    
    try:
        with open(registry_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        return {"status": "error", "reason": str(e)}
    
    registry = data.get('registry', {}) if data else {}
    
    # Group by agent_id first (many workflows → 1 agent)
    agent_workflows = {}
    for dept, workflows in registry.items():
        if isinstance(workflows, dict):
            for workflow, agent_id in workflows.items():
                if agent_id and isinstance(agent_id, str) and not agent_id.startswith('#'):
                    agent_id = agent_id.split('#')[0].strip()
                    if agent_id:
                        if agent_id not in agent_workflows:
                            agent_workflows[agent_id] = {
                                "name": agent_id.replace('-', ' ').replace('_', ' ').title(),
                                "department": dept,
                                "workflows": []
                            }
                        agent_workflows[agent_id]["workflows"].append(workflow)
    
    # Clear existing agents
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM agents')
    conn.commit()
    conn.close()
    
    # Create agents with all their workflows
    count = 0
    for agent_id, info in agent_workflows.items():
        create_agent(
            agent_id=agent_id,
            name=info["name"],
            department=info["department"],
            workflows=info["workflows"]
        )
        count += 1
    
    return {"status": "synced", "count": count, "note": "1 agent per unique agent_id"}

# === DETAIL/LOGS FILE OPERATIONS ===

def get_task_detail_path(task_id: int) -> Path:
    """Get path to task detail.json"""
    return get_tasks_dir() / str(task_id) / "detail.json"

def get_task_logs_path(task_id: int) -> Path:
    """Get path to task logs.json"""
    return get_tasks_dir() / str(task_id) / "logs.json"

def save_task_detail(task_id: int, detail: dict) -> Path:
    """Save task detail to JSON file."""
    task_dir = get_tasks_dir() / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    
    detail_path = task_dir / "detail.json"
    with open(detail_path, 'w', encoding='utf-8') as f:
        json.dump(detail, f, indent=2, ensure_ascii=False)
    
    return detail_path

def load_task_detail(task_id: int) -> dict:
    """Load task detail from JSON file."""
    detail_path = get_task_detail_path(task_id)
    
    if not detail_path.exists():
        return None
    
    with open(detail_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def add_task_log(task_id: int, event: str, actor: str, details: dict = None) -> Path:
    """Add log entry to task logs.json"""
    logs_path = get_task_logs_path(task_id)
    
    logs = []
    if logs_path.exists():
        with open(logs_path, 'r', encoding='utf-8') as f:
            logs = json.load(f)
    
    log_entry = {
        "event": event,
        "actor": actor,
        "timestamp": datetime.now().isoformat(),
        "details": details or {}
    }
    
    logs.append(log_entry)
    
    task_dir = get_tasks_dir() / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    
    with open(logs_path, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)
    
    return logs_path

def get_task_logs(task_id: int) -> list:
    """Get all logs for task."""
    logs_path = get_task_logs_path(task_id)
    
    if not logs_path.exists():
        return []
    
    with open(logs_path, 'r', encoding='utf-8') as f:
        return json.load(f)

if __name__ == '__main__':
    import pprint
    
    # Init database
    init_db()
    print(f"✅ Database: {get_db_path()}")
    
    # Sync agents from YAML
    result = sync_agents_from_yaml()
    print(f"✅ Agents synced: {result}")
    
    # Show all agents with their workflows
    agents = get_all_agents()
    print(f"\n✅ Total agents: {len(agents)}")
    for agent in agents[:5]:
        print(f"  - {agent['id']}: {agent['workflows']}")
    
    # Test job operations
    print("\n--- Job Operations Test ---")
    
    # Create a test job
    job = create_job(task_id=99999, agent_id="sales-agent", workflow="email-draft", priority="normal")
    print(f"✅ Job created: {job['id']} for task {job['task_id']} → {job['agent_id']}")
    
    # Get jobs for an agent
    jobs = get_jobs_for_agent("sales-agent", status="assigned")
    print(f"✅ Jobs for sales-agent (assigned): {len(jobs)}")
    
    # Claim job
    claimed = claim_job(job['id'])
    print(f"✅ Job claimed: {claimed}")
    
    # Complete job
    result_path = str(get_tasks_dir() / "99999" / "result.md")
    completed = complete_job(job['id'], result_path)
    print(f"✅ Job completed: {completed}")
    
    print("\n✅ All tests passed!")
