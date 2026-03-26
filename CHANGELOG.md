# Changelog - Zrise Connect Skill

Tất cả các thay đổi đáng chú ý cho skill này sẽ được ghi lại trong file này.

## 3.3.4 (2026-03-25)

### Tính năng mới
- Thêm 4 script tự động: validate-skill.py, improve-skill.py, version-skill.py, lint-skill.py
- Thêm script agent registry: auto_plan.py, accept_default_plan.py, config_agent.py, regenerate_plan.py
- Thêm script claim_and_process.py để agent claim và xử lý task
- Cập nhật poll_employee_work.py để tự động thêm task vào registry

### Sửa lỗi
- Fix: poll_employee_work.py không add task vào registry sau khi poll
- Fix: Context poisoning - agent nói trước khi làm (tạo niềm tin sai lầm về file tồn tại)
- Fix: Thiếu VERSION.md và CHANGELOG.md

### Cải thiện
- Cập nhật SKILL.md với hướng dẫn sử dụng script có sẵn
- Thêm tài liệu cho developer
- Cải thiện audit trail logging

## 3.3.3 (2026-03-25)

### Bảo mật
- Thêm bảo vệ prompt injection trong execute_task.py và auto_plan.py (sanitize input)
- Thêm audit trail hoàn chỉnh để ghi lại toàn bộ lịch sử trao đổi
- Giới hạn độ dài input (name:100, description:500, project:100 ký tự)

### Quy trình
- Bắt buộc approve 2 lần (lần 1: chọn agent, lần 2: chấp nhận kết quả)
- Task KHÔNG THỂ được claim nếu chưa approve lần 1
- Task KHÔNG THỂ được push lên Zrise nếu chưa approve lần 2
- Mọi feedback → đưa task về lại trạng thái xử lý

## 3.3.2 (2026-03-24)

### Tính năng mới
- Tự động tạo agent plan mặc định dựa trên agent registry + task context
- Chấp nhận plan mặc định (1 lệnh) → Chuyển sang READY_FOR_CLAIM
- Cấu hình qua agent khác (1 lệnh) → Chuyển sang READY_FOR_CLAIM
- Tái tạo plan nếu cần (2 lệnh: regenerate + accept)

### Cải thiện
- Agent registry stored at workspace root cho sharing across all skills/agents
- Fallback to general-agent cho unmatched department/type combinations
- User overrides (e.g., khoa → sales-agent-v2) take priority over registry mappings

## 3.3.1 (2026-03-24)

### Phát hành
- Phát hành phiên bản ổn định đầu tiên với Lobster workflow
- 8-step flow: Poll → Analyze → Execute → Review → Writeback
- Web UI workflow manager trên port 8888
- 30/32 tests passed (93.75%)

## 3.2.0 (2026-03-23)

### Tính năng
- Workflow Management qua Web UI
- AI-Powered xử lý tasks
- Session Management
- Clarification Flow
- HTML Comments format đẹp trên Zrise
- Permission Control (Private/Team/Public)
- 10+ workflow templates
