# Agent Executor Guide - Zrise Connect

Hướng dẫn cho các executor agents sử dụng zrise-connect skill để gửi kết quả lên Telegram.

## 🎯 Tổng quan

Executor agents nhận job từ Orchestrator queue, thực thi task, và gửi kết quả lên Telegram để user review.

## 📁 Script location

```
~/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/format_message_for_telegram_channels.py
```

## 📝 Message Types

### 1. Plan Message - Gửi khi có plan mới

```bash
python3 scripts/format_message_for_telegram_channels.py plan \
  --task-id <ID> \
  --task-name "<tên task>" \
  --agent <agent-id> \
  --steps "Bước 1" "Bước 2" "Bước 3" \
  --estimated "30 phút"
```

**Output:**
```
🤖 *AI Execution Plan - Review Required*

🔵 *Task:* `#42541`
📝 *Tên:* Viết quảng cáo máy bán hàng
🤖 *Agent:* `sales-agent`
⏱️  *Estimated:* 30 phút

📌 *Execution Steps:*
   1. Soạn draft
   2. Review nội dung
   3. Gửi email

---
*Reply với:*
• `[APPROVE]` → Execute as planned
• `[FEEDBACK] <text>` → Provide corrections
```

### 2. Result Message - Gửi khi hoàn thành task

```bash
python3 scripts/format_message_for_telegram_channels.py result \
  --task-id <ID> \
  --task-name "<tên task>" \
  --agent <agent-id> \
  --summary "<tóm tắt kết quả>" \
  --time "25 phút"
```

**Output:**
```
✅ *Task Completed*

📋 *Task:* `#42541`
📝 *Tên:* Viết quảng cáo máy bán hàng
🤖 *Agent:* `sales-agent`
⏱️  *Execution time:* 25 phút

📝 *Result Summary:*
_Đã soạn draft email quảng cáo_

---
*Review kết quả và reply:*
• `[APPROVE]` → Chấp nhận kết quả
• `[FEEDBACK] <text>` → Yêu cầu sửa đổi
```

## 🐍 Dùng trong Python Code

```python
from format_message_for_telegram_channels import (
    format_plan_message,
    format_result_message,
    format_plan_buttons,
    format_result_buttons
)

# Format plan message
msg = format_plan_message(
    task_id=42541,
    task_name="Viết quảng cáo máy bán hàng",
    selected_agent="sales-agent",
    execution_steps=["Soạn draft", "Review", "Gửi"],
    estimated_time="30 phút"
)
buttons = format_plan_buttons(42541)

# Format result message
msg = format_result_message(
    task_id=42541,
    task_name="Viết quảng cáo máy bán hàng",
    agent_id="sales-agent",
    result_summary="Đã hoàn thành draft email",
    execution_time="25 phút"
)
buttons = format_result_buttons(42541)
```

## 🔄 Workflow cho Executor Agent

```
1. Nhận job (status = 'assigned')
2. Execute task
3. Write result.md
4. Update job status = 'done'
5. Gửi result message lên Telegram
6. Update task status trong SQLite
```

## 📋 Các Agent hiện có

| Agent | Skills | Use Case |
|-------|--------|----------|
| sales-agent | email-draft, lead-qualification | Sales tasks |
| eng-agent | coding, bug-triage, code-review | Engineering tasks |
| pm-agent | requirement-analysis, sprint-planning | PM tasks |
| hr-agent | onboarding, offboarding | HR tasks |
| finance-agent | invoice-processing, expense-report | Finance tasks |
| support-agent | ticket-triage, faq-generation | Support tasks |

## ⚠️ Lưu ý

1. **Luôn dùng format_message_for_telegram_channels.py** - Đảm bảo format nhất quán
2. **Task ID phải đúng** - Dùng để callback buttons hoạt động
3. **Buttons được gửi kèm** - Telegram sẽ hiển thị inline buttons

## 🔧 Troubleshooting

**Script not found:**
```bash
# Đảm bảo path đúng
ls ~/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/format_message_for_telegram_channels.py
```

**Import error:**
```python
import sys
sys.path.insert(0, '~/.openclaw/workspace-ai-company/skills/zrise-connect/scripts')
from format_message_for_telegram_channels import ...
```
