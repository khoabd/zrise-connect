# Cron Setup Guide - Zrise Connect

Hướng dẫn setup cron để poll task tự động từ Zrise.

**Docs:** https://docs.openclaw.ai/automation/cron-jobs

## ⚠️ QUY TẮC SỐ 1: LUÔN DÙNG `--agent`

```bash
# ❌ SAI — cron chạy bằng main agent
openclaw cron add --name "zrise-poll" --cron "*/5 * * * *" ...

# ✅ ĐÚNG — chỉ định agent hiện tại
openclaw cron add \
  --name "zrise-poll" \
  --agent <AGENT_ID_CỦA_BẠN> \
  ...
```

## ⚠️ QUY TẮC SỐ 2: DELIVERY PHẢI LÀ "none"

**KHI SCRIPT exit SILENT (không có output), delivery mode phải là `none`!**

Nếu dùng `announce`:
- Script exit silent → cron gửi "Script chạy thành công, không có task mới" → **SPAM**

### Tạo cron đúng cho zrise-connect:

```bash
# Tạo cron với default delivery (sẽ là announce)
openclaw cron add \
  --name "zrise-poll" \
  --cron "* * * * *" \
  --agent <AGENT_ID> \
  --session isolated \
  --message "cd ~/.openclaw/workspace-ai-company/skills/zrise-connect && python3 scripts/poll_employee_work.py --once"

# SAU ĐÓ: Sửa delivery mode thành "none" trong jobs.json
python3 -c "
import json
with open('/Users/khoabui/.openclaw/cron/jobs.json') as f:
    d = json.load(f)
for job in d.get('jobs', []):
    if 'zrise' in job.get('name', ''):
        job['delivery']['mode'] = 'none'
with open('/Users/khoabui/.openclaw/cron/jobs.json', 'w') as f:
    json.dump(d, f, indent=2)
print('Fixed!')
"
```

### Verify:

```bash
openclaw cron list --json | python3 -c "import json,sys; [print(j['name'], j['delivery']['mode']) for j in json.load(sys.stdin)['jobs']]"
```

## Cron Jobs Cần Thiết Lập

| Name | Schedule | Script | Delivery |
|------|----------|--------|----------|
| zrise-poll | `* * * * *` | poll_employee_work.py | none |
| zrise-auto-plan | `*/5 * * * *` | auto_plan.py | none |

## MANAGE

```bash
openclaw cron list              # Liệt kê tất cả
openclaw cron list --json       # Xem delivery mode
openclaw cron run <id>          # Chạy ngay
openclaw cron delete <id>       # Xóa
```

## 🐛 TROUBLESHOOTING

| Vấn đề | Giải pháp |
|---------|-----------|
| Spam tin nhắn | Kiểm tra `delivery.mode` phải là `none` |
| Cron không chạy | Approve exec: `openclaw exec approve --pattern "poll_employee_work.py" --allow-always` |
| Không thấy task mới | Kiểm tra `--employee-id` đúng chưa |

## 📚 THAM KHẢO

- **Cron Jobs:** https://docs.openclaw.ai/automation/cron-jobs
