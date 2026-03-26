# Zrise-Connect Setup Complete ✅

## 📦 Version: 3.4.0

---

## 🎯 Setup Summary

| Component | Status | Details |
|-----------|--------|---------|
| **Lobster CLI** | ✅ | v2026.1.21-1 at `/opt/homebrew/bin/lobster` |
| **Zrise Connection** | ✅ | uid=200 (khoa.bd@atomsolution.com.vn) |
| **Employee ID** | ✅ | 10 (Bùi Đăng Khoa) |
| **SSL Fix** | ✅ | Applied in `zrise_utils.py` & `poll_employee_work.py` |
| **Scripts** | ✅ | 10+ scripts ready |
| **Workflows** | ✅ | 5 workflows available |
| **Cron Script** | ✅ | `zrise-poll-cron.sh` (mỗi 1 phút) |

---

## 📁 Directory Structure

```
zrise-connect/
├── SKILL.md              # Full documentation (v3.4)
├── README.md             # Quick start guide
├── VERSION.md            # 3.4.0
├── skill.json            # Metadata
├── README-SETUP.md       # Setup guide
├── docs/
│   ├── SETUP_COMPLETE.md     # This file
│   ├── WORKFLOW_TEMPLATES.md # 10 templates
│   ├── AGENT_ROUTING.md      # Agent selection logic
│   ├── TELEGRAM_INTEGRATION.md
│   └── TEAM_ONBOARDING.md
├── workflows/
│   ├── zrise-execute.lobster   # Main (8-step flow)
│   ├── zrise-poll.lobster      # Poll & notify
│   ├── simple.lobster          # Simple execution
│   ├── email-draft.lobster     # Email drafting
│   └── requirement-analysis.lobster
└── scripts/
    ├── zrise_utils.py          # Connection (SSL-safe)
    ├── fetch_task_data.py
    ├── analyze_task.py
    ├── execute_ai_task.py
    ├── writeback_to_zrise.py
    ├── update_task_stage.py
    ├── fill_timesheet.py
    ├── poll_employee_work.py
    ├── zrise-poll-cron.sh
    └── zrise_task_info.py
```

---

## 🚀 Quick Commands

### Test Connection
```bash
python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/zrise_utils.py
```

### Poll Tasks
```bash
python3 poll_employee_work.py --employee-id 10 --limit 10 --json
```

### Run Workflow
```bash
lobster run workflows/zrise-execute.lobster \
  --args-json '{"task_id": 28113, "user_message": "xử lý task này"}'
```

### Setup Cron (mỗi 1 phút)
```bash
chmod +x scripts/zrise-poll-cron.sh
(crontab -l 2>/dev/null; echo "* * * * * /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/zrise-poll-cron.sh 10 /tmp/zrise-poll-latest.json") | crontab -
```

---

## 📊 Current Tasks (Employee ID: 10)

| Category | Count |
|----------|-------|
| Total Pending | 8 |
| 🆕 New | 0 |
| 🔄 Changed | 1 |
| ⚠️ SLA Breach | 7 |
| 🔴 Deadline Soon | 0 |

**Task nổi bật:**
- **28113** — GenQR với thông tin tài khoản thật (Changed)
- **41986** — [DEMO] BA - Làm rõ requirement (SLA 181h)
- **37330** — [NR] - Migrate address (SLA 529h)

---

## 🤖 Agent Routing

| Workflow | Agent | Role |
|----------|-------|------|
| requirement-analysis | demo-ba | Business Analyst |
| email-draft | ai-company | AI Assistant |
| technical-design | demo-architect | Technical Architect |
| development | demo-be | Backend Developer |
| testing | demo-qc | QA Engineer |
| general | ai-company | AI Assistant |

---

## 🔄 Workflow Flow (zrise-execute)

```
1. Fetch task từ Zrise → .tasks/<id>/task.json
2. AI phân tích intent + lên plan → plan.json
3. Post plan lên Zrise
4. Stage → In Process
   ⏸️ APPROVAL: Review plan
5. AI execute task → result.md
   ⏸️ APPROVAL: Review kết quả
6. Writeback result → Zrise
7. Fill timesheet
8. Stage → Done
```

---

## ⚠️ Important Notes

1. **PHẢI dùng Lobster workflow** — Không tự generate/post
2. **Timesheet TRƯỚC stage Done** — Zrise bắt buộc
3. **Approval 2 bước** — Plan + Result
4. **SSL verification disabled** — Fix cho macOS Python 3.11

---

## 📞 Paths Reference

| Resource | Path |
|----------|------|
| Skill | `/Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/` |
| Scripts | `/Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/` |
| Workflows | `/Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/workflows/` |
| State | `/Users/khoabui/.openclaw/workspace-ai-company/state/zrise/` |
| Config | `/Users/khoabui/.openclaw/openclaw.json` |
| Poll Output | `/tmp/zrise-poll-latest.json` |
| Poll Log | `/tmp/zrise-poll.log` |

---

## 🐛 Troubleshooting

### SSL Certificate Error
Fixed: `ssl._create_unverified_context()` applied

### Exec Approval Timeout
- Approve từ Web UI / terminal UI
- Telegram không hỗ trợ approve trực tiếp

### Employee Not Found
- Verify `hr.employee.user_id` linked với `res.users.id`
- Check username trong `openclaw.json`

---

**Setup complete! Ready to automate Zrise tasks.** 🎯
