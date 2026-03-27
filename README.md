# zrise-connect v3.4.0

Kết nối và vận hành Zrise qua XML-RPC API với AI workflow automation.

## 🎯 Mục đích

- Tự động hóa xử lý task Zrise qua Lobster workflows
- AI phân tích, lên plan, execute và writeback kết quả
- Poll task pending tự động (cron)
- Integration với Telegram notifications

## 📋 Quick Start

### 1. Setup Credentials

Config trong `~/.openclaw/openclaw.json`:

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

### 2. Test Connection

```bash
cd /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts
python3 zrise_utils.py
```

### 3. Tìm Employee ID

```bash
python3 -c "
import sys; sys.path.insert(0, '.')
from zrise_utils import connect_zrise
db, uid, secret, models, url = connect_zrise()
emp = models.execute_kw(db, uid, secret, 'hr.employee', 'search_read',
    [[('user_id', '=', uid)]], {'fields': ['id', 'name']})
print(f'Employee ID: {emp[0][\"id\"]}' if emp else 'Not found')
"
```

### 4. Poll Task Pending

```bash
python3 poll_employee_work.py --employee-id <ID> --limit 10 --json
```

### 5. Chạy Workflow

```bash
lobster run workflows/zrise-execute.lobster \
  --args-json '{"task_id": <TASK_ID>, "user_message": "xử lý task này"}'
```

## 🔄 Workflow Flow

```
1. Fetch task từ Zrise → .tasks/<id>/task.json
2. AI phân tích intent + lên plan → plan.json
3. Post plan lên Zrise (mail.compose.message)
4. Stage → In Process
   ⏸️ APPROVAL: Review plan
5. AI execute task → result.md
   ⏸️ APPROVAL: Review kết quả
6. Writeback result → Timesheet → Stage: Done
```

## 📦 Scripts

| Script | Chức năng |
|--------|-----------|
| `fetch_task_data.py` | Lấy task data từ Zrise |
| `analyze_task.py` | Phân tích intent, chọn agent, tạo plan |
| `execute_ai_task.py` | Execute via LLM (openclaw.invoke) |
| `writeback_to_zrise.py` | Post plan/result lên Zrise |
| `update_task_stage.py` | Update stage (New → In Process → Done) |
| `fill_timesheet.py` | Log timesheet |
| `poll_employee_work.py` | Poll task pending (cron) |
| `zrise_utils.py` | Common utilities (SSL-safe) |

## ⏰ Cron Setup

Dùng **OpenClaw cron jobs** (không dùng crontab). Xem chi tiết tại [docs/CRON_SETUP.md](docs/CRON_SETUP.md).

```bash
# Tạo cron poll task (mỗi 1 phút)
openclaw cron add \
  --name "zrise-poll" \
  --cron "* * * * *" \
  --agent <AGENT_ID> \
  --session isolated \
  --message "cd ~/.openclaw/workspace-ai-company/skills/zrise-connect && python3 scripts/poll_employee_work.py --once" \
  --announce

# Tạo cron auto-plan (mỗi 5 phút)
openclaw cron add \
  --name "zrise-auto-plan" \
  --cron "*/5 * * * *" \
  --agent <AGENT_ID> \
  --session isolated \
  --message "cd ~/.openclaw/workspace-ai-company/skills/zrise-connect && python3 scripts/auto_plan.py --info" \
  --announce

# Sau đó sửa delivery mode thành "none" để tránh spam
# (xem docs/CRON_SETUP.md)
```

## 🤖 Agent Routing

| Workflow | Agent | Use Case |
|----------|-------|----------|
| requirement-analysis | demo-ba | Checklist, BRD, user story |
| email-draft | ai-company | Soạn email, thông báo |
| technical-design | demo-architect | Architecture, API design |
| development | demo-be | Code, fix bug |
| testing | demo-qc | Test case, QA |
| general | ai-company | Mặc định |

## ⚠️ Lưu ý quan trọng

1. **PHẢI dùng Lobster workflow** — Không tự generate/post kết quả
2. **Timesheet TRƯỚC stage Done** — Zrise bắt buộc
3. **Approval 2 bước** — Plan + Result
4. **SSL verification disabled** — Fix cho macOS Python 3.11

## 📚 Docs

- [WORKFLOW_TEMPLATES.md](docs/WORKFLOW_TEMPLATES.md)
- [TELEGRAM_INTEGRATION.md](docs/TELEGRAM_INTEGRATION.md)
- [TEAM_ONBOARDING.md](docs/TEAM_ONBOARDING.md)
- [AGENT_ROUTING.md](docs/AGENT_ROUTING.md)

## 🔧 Troubleshooting

**SSL Certificate Error:**
```python
# Đã fix trong zrise_utils.py
_ssl_ctx = ssl._create_unverified_context()
```

**Exec Approval Timeout:**
- Setup từ terminal thay vì Telegram
- Dùng `/approve allow-always` cho session

**Employee Not Found:**
- Kiểm tra user_id linked với hr.employee
- Verify username trong config

## 📞 Support

- Skill path: `~/.openclaw/workspace-ai-company/skills/zrise-connect/`
- State: `~/.openclaw/workspace-ai-company/state/zrise/`
- Logs: `/tmp/zrise-poll.log`
