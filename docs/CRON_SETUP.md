# Cron Setup Guide - Zrise Connect

Dùng **OpenClaw cron jobs** để poll task tự động từ Zrise. Không dùng crontab.

**Docs:** https://docs.openclaw.ai/automation/cron-jobs

## ⚠️ QUY TẮC SỐ 1: LUÔN DÙNG `--agent`

```bash
# ❌ SAI — cron chạy bằng main agent
openclaw cron add --name "zrise-poll" --cron "*/5 * * * *" ...

# ✅ ĐÚNG — chỉ định agent cụ thể
openclaw cron add \
  --name "zrise-poll" \
  --agent <AGENT_ID_CỦA_BẠN> \
  ...
```

## ⚠️ QUY TẮC SỐ 2: DELIVERY MODE = "none"

Scripts trong zrise-connect exit silent khi không có task mới. Nếu dùng `--announce` sẽ gây **SPAM** vì cron gửi "Script chạy thành công, không có output".

### Tạo cron với delivery="none"

Dùng OpenClaw tool API (hiện tại CLI chưa hỗ trợ `--delivery none` trực tiếp):

```bash
# Tạo cron với announce trước
openclaw cron add \
  --name "zrise-poll" \
  --cron "* * * * *" \
  --agent <AGENT_ID> \
  --session isolated \
  --message "cd ~/.openclaw/workspace-ai-company/skills/zrise-connect && python3 scripts/poll_employee_work.py --once" \
  --announce

# Sau đó sửa delivery mode thành "none" trong jobs.json
python3 -c "
import json
with open('$HOME/.openclaw/cron/jobs.json') as f:
    d = json.load(f)
for job in d.get('jobs', []):
    if 'zrise' in job.get('name', ''):
        job['delivery']['mode'] = 'none'
with open('$HOME/.openclaw/cron/jobs.json', 'w') as f:
    json.dump(d, f, indent=2)
print('Fixed delivery mode to none!')
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

## Quản lý Cron

```bash
openclaw cron list              # Liệt kê tất cả
openclaw cron list --json       # Xem chi tiết delivery mode
openclaw cron run <id>          # Chạy ngay
openclaw cron delete <id>       # Xóa
```

## 🐛 TROUBLESHOOTING

| Vấn đề | Giải pháp |
|---------|-----------|
| Spam tin nhắn | Kiểm tra `delivery.mode` phải là `none` |
| Cron không chạy | Approve exec: `openclaw exec approve --pattern "poll_employee_work.py" --allow-always` |
| Không thấy task mới | Chạy thủ công để debug: `python3 scripts/poll_employee_work.py --once` |

## 📚 THAM KHẢO

- **OpenClaw Cron Jobs:** https://docs.openclaw.ai/automation/cron-jobs
