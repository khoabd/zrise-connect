# Orchestrator Guide - Zrise Connect

Hướng dẫn cho **ai-company** (orchestrator agent) sử dụng zrise-connect skill để gửi message lên channel.

## 🎯 Tổng quan

`ai-company` là orchestrator - agent chính điều phối workflow. Khi cần gửi Plan/Result lên Telegram/Slack cho user review, dùng `openclaw agent --deliver`.

## 📁 Script location

```
~/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/format_message_for_telegram_channels.py
```

## 📝 Message Types

### 1. Plan Message - Gửi khi có plan mới cần user approve

```bash
MSG=$(python3 ~/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/format_message_for_telegram_channels.py \
  plan \
  --task-id <ID> \
  --task-name "<tên task>" \
  --agent <agent-id> \
  --steps "Bước 1" "Bước 2" "Bước 3" \
  --estimated "30 phút")

openclaw agent --message "$MSG" --deliver
```

**Output nhận được:**
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
MSG=$(python3 ~/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/format_message_for_telegram_channels.py \
  result \
  --task-id <ID> \
  --task-name "<tên task>" \
  --agent <agent-id> \
  --summary "<tóm tắt kết quả>" \
  --time "25 phút")

openclaw agent --message "$MSG" --deliver
```

**Output nhận được:**
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

## 🔄 Orchestrator Workflow

```
1. poll_employee_work.py → Poll task từ Zrise
2. auto_plan.py → AI lên plan
3. Gửi Plan lên channel: openclaw agent --message "$MSG" --deliver
4. User reply [APPROVE] hoặc [FEEDBACK]
5. Nếu APPROVE → Execute task
6. Gửi Result lên channel
7. User reply [APPROVE] → Done
```

## 🔗 OpenClaw Agent Send

Doc: https://docs.openclaw.ai/tools/agent-send

```bash
# Gửi message tới channel mà agent đang được map
openclaw agent --message "Your message" --deliver

# Chỉ định channel cụ thể
openclaw agent --message "Your message" --deliver --channel telegram --reply-to "@your_channel"
```

**Key flags:**
- `--message` - Message cần gửi
- `--deliver` - Gửi reply tới channel (thay vì chỉ trả lời trong session)
- `--channel` - Channel type (telegram, discord, slack, whatsapp)
- `--reply-to` - Override target (chat ID, channel name)

## ⚠️ Lưu ý

1. **CHỉ format message** - Script chỉ trả về text, không gửi đi
2. **Dùng `openclaw agent --deliver`** - Gửi tới channel mà agent được map
3. **Session tự động** - `--deliver` reply vào session/channel mà agent đang active
