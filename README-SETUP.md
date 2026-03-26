# Zrise-Connect - Hướng dẫn setup & sử dụng

## ✅ Setup đã hoàn tất

- **Lobster CLI:** v2026.1.21-1 tại `/opt/homebrew/bin/lobster`
- **Zrise Connection:** ✅ (uid=200)
- **Config:** `~/.openclaw/openclaw.json` (skills.entries.zrise-connect.env)

---

## 🔍 Tìm Employee ID của bạn

```bash
cd ~/.openclaw/workspace-ai-company/skills/zrise-connect/scripts
python3 -c "
import sys, json
sys.path.insert(0, '.')
from zrise_utils import connect_zrise
db, uid, secret, models, url = connect_zrise()
employees = models.execute_kw(db, uid, secret, 'hr.employee', 'search_read',
    [[('user_id', '=', uid)]], {'fields': ['id', 'name', 'user_id']})
print(f'Employee ID: {employees[0][\"id\"] if employees else \"Not found\"}')
print(f'Name: {employees[0][\"name\"] if employees else \"N/A\"}')
"
```

---

## 📋 Poll task pending

```bash
# Thay <EMPLOYEE_ID> bằng ID của bạn
python3 poll_employee_work.py --employee-id <EMPLOYEE_ID> --limit 20 --json
```

**Output categories:**
- `new` — Task mới chưa seen
- `changed` — Task có thay đổi
- `sla_breach` — Quá 24h không update
- `deadline_soon` — Còn <48h đến deadline

---

## 🚀 Chạy workflow cho task

```bash
# Step 1: Fetch task data
python3 fetch_task_data.py <TASK_ID> --save

# Step 2: Chạy Lobster workflow (có approval steps)
lobster run skills/zrise-connect/workflows/zrise-execute.lobster \
  --args-json '{"task_id": <TASK_ID>, "user_message": "mô tả yêu cầu"}'
```

**Workflow flow:**
```
1. Fetch task từ Zrise
2. AI phân tích intent + lên plan
3. Post plan lên Zrise
4. Stage → In Process
   ⏸️ APPROVAL: Review plan
5. AI execute task
   ⏸️ APPROVAL: Review kết quả
6. Writeback result → Timesheet → Stage: Done
```

---

## ⏰ Setup cron poll tự động

```bash
# Thêm vào crontab (poll mỗi 30 phút)
crontab -e

# Thêm dòng:
*/30 * * * * cd ~/.openclaw/workspace-ai-company/skills/zrise-connect/scripts && \
  python3 poll_employee_work.py --employee-id <EMPLOYEE_ID> --limit 10 --json > /tmp/zrise-poll.json
```

---

## 📁 Scripts reference

| Script | Usage |
|--------|-------|
| `fetch_task_data.py <id> --save` | Lưu task data vào `.tasks/<id>/` |
| `analyze_task.py --task-dir <dir>` | Tạo plan.json |
| `execute_ai_task.py --task-dir <dir> --agent <id>` | Execute via LLM |
| `writeback_to_zrise.py --task-dir <dir>` | Post result lên Zrise |
| `update_task_stage.py <id> "Done" --comment "..."` | Update stage |
| `fill_timesheet.py --task-id <id> --hours 0.5` | Log timesheet |

---

## 🎯 Agent mapping

| Workflow | Agent | Use case |
|----------|-------|----------|
| requirement-analysis | demo-ba | Checklist, BRD, user story |
| email-draft | ai-company | Soạn email, thông báo |
| technical-design | demo-architect | Architecture, API design |
| development | demo-be | Code, fix bug |
| testing | demo-qc | Test case, QA |
| general | ai-company | Mặc định |

---

## 📞 Hỗ trợ

- Skill path: `~/.openclaw/workspace-ai-company/skills/zrise-connect/`
- Workflow: `workflows/zrise-execute.lobster`
- State: `~/.openclaw/workspace-ai-company/state/zrise/`
