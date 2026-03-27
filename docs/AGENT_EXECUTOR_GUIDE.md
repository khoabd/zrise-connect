# Agent Executor Guide - Zrise Connect

Hướng dẫn cho các executor agents sử dụng zrise-connect skill.

## 🎯 Tổng quan

Executor agents nhận job từ Orchestrator queue, thực thi task, và gửi kết quả lên channel để user review qua `openclaw agent --deliver`.

## 📁 Script location

```
~/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/format_message_for_telegram_channels.py
```

## 📝 Message Types

### 1. Plan Message - Gửi khi có plan mới

```bash
MSG=$(python3 scripts/format_message_for_telegram_channels.py plan \
  --task-id <ID> \
  --task-name "<tên task>" \
  --agent <agent-id> \
  --steps "Bước 1" "Bước 2" "Bước 3" \
  --estimated "30 phút")

openclaw agent --message "$MSG" --deliver
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
MSG=$(python3 scripts/format_message_for_telegram_channels.py result \
  --task-id <ID> \
  --task-name "<tên task>" \
  --agent <agent-id> \
  --summary "<tóm tắt kết quả>" \
  --time "25 phút")

openclaw agent --message "$MSG" --deliver
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
from format_message_for_telegram_channels import format_plan_message, format_result_message
import subprocess

# Format plan message
msg = format_plan_message(
    task_id=42541,
    task_name="Viết quảng cáo máy bán hàng",
    selected_agent="sales-agent",
    execution_steps=["Soạn draft", "Review", "Gửi"],
    estimated_time="30 phút"
)

# Gửi bằng openclaw agent --deliver
subprocess.run(['openclaw', 'agent', '--message', msg, '--deliver'])
```

## 🔄 Workflow cho Executor Agent

```
1. Nhận job (status = 'assigned')
2. Execute task
3. Write result.md
4. Update job status = 'done'
5. Format message và gửi: openclaw agent --message "$MSG" --deliver
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

## 🔗 OpenClaw Agent Send

Doc: https://docs.openclaw.ai/tools/agent-send

```bash
# Gửi message tới channel mà agent đang được map
openclaw agent --message "Your message" --deliver

#指定 channel
openclaw agent --message "Your message" --deliver --channel telegram --reply-to "@your_channel"

#指定 agent
openclaw agent --agent sales-agent --message "$MSG" --deliver
```

**Key flags:**
- `--message` - Message cần gửi
- `--deliver` - Gửi reply tới channel (thay vì chỉ trả lời trong session)
- `--channel` - Channel type (telegram, discord, slack, whatsapp)
- `--reply-to` - Override target (chat ID, channel name)
- `--agent` - Dùng agent cụ thể để gửi

## ⚠️ Lưu ý

1. **CHỈ format message** - Script chỉ trả về text, không gửi đi
2. **Dùng `openclaw agent --deliver`** - Agent tự gửi tới channel mà nó được map
3. **Session tự động** - `--deliver` reply vào session/channel mà agent đang active
