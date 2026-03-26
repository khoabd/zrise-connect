# zrise-connect — Zrise Integration Skill v3.5

## 🎯 Mục đích

Kết nối OpenClaw agent với Zrise qua XML-RPC API:
- Poll task tự động → SQLite + `.tasks/<task_id>/detail.json`
- AI agent tự lên plan
- User approve → Agent execute → Writeback → Done

## 📁 Data Structure

### SQLite: `.tasks/task_registry.db`

```sql
-- Tasks table
tasks(task_id, name, status, created_at, updated_at, assigned_agent, priority, deadline)

-- Agents table  
agents(id, name, department, workflow, is_active)
```

### File System

```
~/.openclaw/workspace-ai-company/.tasks/
└── <task_id>/
    ├── detail.json    # Task info + plan + feedback (toàn bộ decisions)
    └── logs.json     # Audit log
```

### Task Status Flow

```
new → pending → pending_approval → approved → executing → done
                         ↓
                    feedback → (replan) → new
```

---

## 🤖 AI Agent Tools

### Tool 1: poll_employee_work.py

```bash
python3 scripts/poll_employee_work.py --employee-id 200 --once
```

**Action:**
- Poll tasks từ Zrise
- Tạo record trong SQLite (status='new')
- Tạo `.tasks/<task_id>/detail.json`
- Tạo `.tasks/<task_id>/logs.json`

---

### Tool 2: auto_plan.py

```bash
# Process all new tasks
python3 scripts/auto_plan.py --info

# Process specific task
python3 scripts/auto_plan.py --task-id 42349 --info
```

**Action:**
- Đọc tasks có status='new' từ SQLite
- Move status → 'pending'
- Output info cho AI agent

**Output format:**
```
=== TASK INFO ===
TASK_ID: 42349
TASK_DIR: /path/.tasks/42349
AGENT_COUNT: 4
IS_REPLAN: false
--- TEXT START ---
📋 **Task cần lên kế hoạch:**

**Task ID:** 42349
**Tên:** Viết email giới thiệu công ty
...

**Available Agents (4):**
- sales-agent
- eng-agent
...

---
**Agent cần:**
1. Đọc task data từ: `.tasks/42349/detail.json`
2. Dùng AI phân tích task
3. Ghi plan vào: `.tasks/42349/detail.json`
--- TEXT END ---
=== END TASK INFO ===
```

---

### Tool 3: write_plan.py (⚠️ QUAN TRỌNG)

**AI Agent ghi plan vào detail.json**

```bash
python3 scripts/write_plan.py 42349 \
  --agent sales-agent \
  --steps "Soạn draft email,Xem lại nội dung,Gửi email" \
  --time "30 phút" \
  --notes "Cần xác nhận thông tin"
```

**detail.json structure sau khi write_plan:**
```json
{
  "task_id": 42349,
  "name": "Viết email",
  "description": "...",
  "stage": "In Progress",
  "status": "pending_approval",
  "selected_agent": "sales-agent",
  "execution_steps": ["Soạn draft email", "Xem lại", "Gửi"],
  "estimated_time": "30 phút",
  "plan_notes": "...",
  "plan_created_at": "2026-03-25T18:35:00+07:00"
}
```

---

## ✅ User Approval - 3 Cases

### Case 1: User đồng ý → execute

```bash
python3 scripts/approve_plan.py 42349 --action approve --notify
```

**Result:** status='approved', logs updated

---

### Case 2: User đồng ý nhưng đổi agent

```bash
python3 scripts/approve_plan.py 42349 --action change_agent --agent sales-agent-v2 --notify
```

**Result:** selected_agent updated in detail.json + SQLite

---

### Case 3: User feedback → re-plan

```bash
python3 scripts/approve_plan.py 42349 --action feedback --feedback-text "Cần thêm phần giá cả" --notify
```

**Result:**
- Task folder bị xóa + tạo lại ở .tasks/new/ (tưởng tượng)
- detail.json updated với: `user_feedback`, `previous_plan_attempt`, `re_plan_count`
- SQLite status = 'new'

**Auto plan sẽ thấy is_replan=true và hiển thị feedback cho user**

---

## 🔧 Setup

### 1. Init DB

```bash
python3 scripts/db.py
```

Tạo SQLite + sync agents từ YAML.

### 2. Config Credentials

`~/.openclaw/openclaw.json`:
```json
{
  "skills": {
    "entries": {
      "zrise-connect": {
        "enabled": true,
        "env": {
          "ZRISE_URL": "https://zrise.app",
          "ZRISE_DB": "zrise",
          "ZRISE_USERNAME": "your.email@company.com",
          "ZRISE_API_KEY": "your-api-key"
        }
      }
    }
  }
}
```

### 3. Setup Cron

Cần tạo **2 cron jobs riêng** để tách biệt poll và plan:

```bash
# Cron 1: Poll task từ Zrise (nhanh, mỗi 1 phút)
openclaw cron add \
  --name "zrise-poll" \
  --cron "* * * * *" \
  --agent <AGENT_ID> \
  --session isolated \
  --message "cd /path/to/skills/zrise-connect && python3 scripts/poll_employee_work.py --once" \
  --announce \
  --channel telegram

# Cron 2: Auto plan cho tasks (chậm hơn, mỗi 5 phút)
openclaw cron add \
  --name "zrise-auto-plan" \
  --cron "*/5 * * * *" \
  --agent <AGENT_ID> \
  --session isolated \
  --message "cd /path/to/skills/zrise-connect && python3 scripts/auto_plan.py --info" \
  --announce \
  --channel telegram
```

**Lưu ý:** Đường dẫn tuyệt đối đến skill directory (VD: `/Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect`)

---

## 📦 Scripts Reference

| Script | Mô tả |
|--------|-------|
| `db.py` | SQLite operations + detail/logs file ops |
| `poll_employee_work.py` | Poll từ Zrise → SQLite + detail.json |
| `auto_plan.py` | Prepare info cho AI plan |
| `write_plan.py` | AI ghi plan vào detail.json |
| `approve_plan.py` | Handle 3 approval cases |
| `writeback_to_zrise.py` | Gửi kết quả lên Zrise |
| `update_task_stage.py` | Update stage |
| `fill_timesheet.py` | Log timesheet |

---

## 🐛 Troubleshooting

| Vấn đề | Giải pháp |
|---------|-----------|
| Cron không chạy | `openclaw exec approve --pattern "poll_employee_work.py" --allow-always` |
| Task not found | Kiểm tra SQLite: `sqlite3 .tasks/task_registry.db "SELECT * FROM tasks"` |
| Detail.json missing | Chạy lại poll_employee_work.py |

---

## 📞 Paths

- **DB:** `~/.openclaw/workspace-ai-company/.tasks/task_registry.db`
- **Tasks:** `~/.openclaw/workspace-ai-company/.tasks/<task_id>/`
- **Agent registry:** SQLite `agents` table
