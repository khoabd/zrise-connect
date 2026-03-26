# Cron Setup Guide - Zrise Connect

Hướng dẫn setup cron để poll task tự động từ Zrise.

**Docs:** https://docs.openclaw.ai/automation/cron-jobs

## ⚠️ TẠI SAO CẦN CRON?

Không có cron → agent không bao giờ biết có task mới từ Zrise.

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

**Tìm agent ID:** Xem trong `~/.openclaw/openclaw.json` hoặc hỏi admin.

## CÁCH 1: openclaw cron add (Recommended)

```bash
openclaw cron add \
  --name "zrise-poll" \
  --cron "*/5 * * * *" \
  --tz "Asia/Ho_Chi_Minh" \
  --agent <AGENT_ID> \
  --session isolated \
  --message "Poll task từ Zrise. Dùng poll_employee_work.py trong skill zrise-connect. Sau khi poll xong, báo số task mới trong registry." \
  --announce \
  --channel telegram

# Verify
openclaw cron list
openclaw cron run <job-id>  # Test ngay
openclaw cron runs --id <job-id>  # Xem lịch sử
```

### Session Types

| Type | Mô tả |
|------|--------|
| `isolated` | Mỗi run là session mới |
| `session:zrise-poll` | Persistent session, giữ context |

### Delivery Modes

| Mode | Mô tả |
|------|--------|
| `announce` | Gửi summary về chat |
| `webhook` | POST JSON đến URL |
| `none` | Internal only |

## CÁCH 2: Custom Persistent Session

Giữ context giữa các lần chạy — tránh duplicate:

```bash
openclaw cron add \
  --name "zrise-poll-persistent" \
  --cron "*/5 * * * *" \
  --agent <AGENT_ID> \
  --session "session:zrise-poll" \
  --message "Poll task từ Zrise..." \
  --announce \
  --channel telegram
```

## ⚠️ EXEC APPROVAL

Nếu cron bị block:

```bash
openclaw exec approve --pattern "poll_employee_work.py" --allow-always
```

## MANAGE

```bash
openclaw cron list              # Liệt kê tất cả
openclaw cron runs --id <id>    # Lịch sử
openclaw cron run <id>          # Chạy ngay
openclaw cron delete <id>       # Xóa
```

## 🐛 TROUBLESHOOTING

| Vấn đề | Giải pháp |
|---------|-----------|
| Cron không chạy | Approve exec: `openclaw exec approve --pattern "poll_employee_work.py" --allow-always` |
| Không thấy task mới | Kiểm tra `--employee-id` đúng chưa |
| Cron chạy bằng main agent | Thêm `--agent <AGENT_ID>` khi tạo cron |

## 📚 THAM KHẢO

- **Cron Jobs:** https://docs.openclaw.ai/automation/cron-jobs
- **Cron vs Heartbeat:** https://docs.openclaw.ai/automation/cron-vs-heartbeat
