#!/usr/bin/env python3
"""
format_message_for_telegram_channels.py - Format messages for Telegram channels.

Dùng chung cho:
- Agent tạo Plan → gửi lên Telegram review
- System post kết quả → gửi lên Telegram

Chuẩn format:
- Plan: 📋 Task, 🤖 Agent, ⏱️ Estimated, 📌 Steps, ✅ APPROVE / 💬 FEEDBACK
- Result: 📋 Task, ✅ Done, 📝 Result summary
"""

import json
from typing import Optional


# ===== PLAN MESSAGE =====

def format_plan_message(
    task_id: int,
    task_name: str,
    selected_agent: str,
    execution_steps: list,
    estimated_time: str = "N/A",
    is_replan: bool = False,
    user_feedback: str = "",
    previous_plan: dict = None,
    priority: str = "normal"
) -> str:
    """
    Format message cho Plan gửi lên Telegram.

    Args:
        task_id: Task ID
        task_name: Tên task
        selected_agent: Agent được chọn (VD: sales-agent, eng-agent)
        execution_steps: List[str] các bước thực hiện
        estimated_time: Thời gian ước tính (VD: "30 phút")
        is_replan: True nếu là re-plan (có feedback)
        user_feedback: Nội dung feedback từ user
        previous_plan: Plan trước đó (dict với keys: selected_agent, execution_steps)
        priority: Priority (low/normal/high/urgent)

    Returns:
        Formatted message string cho Telegram
    """
    lines = []

    # Header
    if is_replan:
        lines.append("🔄 *AI Re-Plan - Review Required*")
        lines.append("")
        if user_feedback:
            lines.append(f"💬 *User Feedback:*")
            lines.append(f"_{user_feedback[:200]}_")
            lines.append("")
        if previous_plan:
            prev_agent = previous_plan.get('selected_agent', 'N/A')
            prev_steps = previous_plan.get('execution_steps', [])
            lines.append(f"📋 *Plan trước:* {prev_agent}")
            if prev_steps:
                lines.append(f"   Steps: {', '.join(prev_steps[:3])}")
            lines.append("")
        lines.append("---\n")
    else:
        lines.append("🤖 *AI Execution Plan - Review Required*")
        lines.append("")

    # Task info
    priority_emoji = {"low": "🟢", "normal": "🔵", "high": "🟠", "urgent": "🔴"}.get(priority.lower(), "🔵")
    lines.append(f"{priority_emoji} *Task:* `#{task_id}`")
    lines.append(f"📝 *Tên:* {task_name[:80]}")
    lines.append(f"🤖 *Agent:* `{selected_agent}`")
    lines.append(f"⏱️  *Estimated:* {estimated_time}")
    lines.append("")

    # Execution steps
    lines.append("📌 *Execution Steps:*")
    if execution_steps:
        for i, step in enumerate(execution_steps[:10], 1):
            step_text = step if isinstance(step, str) else (step.get('description') or step.get('name') or str(step))
            step_text = step_text[:100]  # Limit length
            lines.append(f"   {i}. {step_text}")
        if len(execution_steps) > 10:
            lines.append(f"   ... và {len(execution_steps) - 10} bước khác")
    else:
        lines.append("   (Chưa có steps)")
    lines.append("")

    # Footer
    lines.append("---\n")
    lines.append("*Reply với:*")
    lines.append("• `[APPROVE]` → Execute as planned")
    lines.append("• `[FEEDBACK] <text>` → Provide corrections")

    text = '\n'.join(lines)
    return text[:4096]


# ===== RESULT MESSAGE =====

def format_result_message(
    task_id: int,
    task_name: str,
    agent_id: str,
    result_summary: str = "",
    result_path: str = None,
    execution_time: str = "N/A",
    files_created: list = None
) -> str:
    """
    Format message cho Result gửi lên Telegram sau khi execute xong.

    Args:
        task_id: Task ID
        task_name: Tên task
        agent_id: Agent đã thực hiện
        result_summary: Tóm tắt kết quả
        result_path: Đường dẫn file kết quả (nếu có)
        execution_time: Thời gian thực hiện
        files_created: List file đã tạo

    Returns:
        Formatted message string cho Telegram
    """
    lines = []

    # Header
    lines.append("✅ *Task Completed*")
    lines.append("")

    # Task info
    lines.append(f"📋 *Task:* `#{task_id}`")
    lines.append(f"📝 *Tên:* {task_name[:80]}")
    lines.append(f"🤖 *Agent:* `{agent_id}`")
    lines.append(f"⏱️  *Execution time:* {execution_time}")
    lines.append("")

    # Result summary
    if result_summary:
        lines.append("📝 *Result Summary:*")
        lines.append(f"_{result_summary[:500]}_")
        lines.append("")

    # Files created
    if files_created:
        lines.append("📁 *Files Created:*")
        for f in files_created[:5]:
            lines.append(f"   • `{f}`")
        if len(files_created) > 5:
            lines.append(f"   ... và {len(files_created) - 5} file khác")
        lines.append("")

    # Result path
    if result_path:
        lines.append(f"📄 *Result:* `{result_path}`")
        lines.append("")

    # Footer
    lines.append("---\n")
    lines.append("*Review kết quả và reply:*")
    lines.append("• `[APPROVE]` → Chấp nhận kết quả")
    lines.append("• `[FEEDBACK] <text>` → Yêu cầu sửa đổi")

    text = '\n'.join(lines)
    return text[:4096]


# ===== TASK INFO MESSAGE =====

def format_task_info_message(
    task_id: int,
    task_name: str,
    description: str = "",
    project: str = "N/A",
    deadline: str = "N/A",
    priority: str = "normal"
) -> str:
    """
    Format message hiển thị thông tin task (cho notification/list).

    Args:
        task_id: Task ID
        task_name: Tên task
        description: Mô tả task
        project: Project name
        deadline: Deadline
        priority: Priority

    Returns:
        Formatted message string cho Telegram
    """
    priority_emoji = {"low": "🟢", "normal": "🔵", "high": "🟠", "urgent": "🔴"}.get(priority.lower(), "🔵")

    lines = [
        f"{priority_emoji} *Task:* `#{task_id}`",
        f"📝 *Tên:* {task_name[:80]}",
    ]

    if project and project != "N/A":
        lines.append(f"📁 *Project:* {project}")

    if deadline and deadline != "N/A":
        lines.append(f"⏰ *Deadline:* {deadline}")

    if description:
        desc = description[:200].replace('\n', ' ').strip()
        lines.append(f"📋 *Mô tả:* {desc}")

    return '\n'.join(lines)


# ===== BUTTONS =====

def format_plan_buttons(task_id: int, is_replan: bool = False) -> dict:
    """
    Format inline buttons cho Plan message.

    Args:
        task_id: Task ID
        is_replan: True nếu là re-plan

    Returns:
        Telegram reply_markup dict
    """
    label = "🔄 RE-PLAN" if is_replan else "✅ APPROVE"
    return {
        "inline_keyboard": [[
            {"text": label, "callback_data": f"approve_{task_id}"},
            {"text": "💬 FEEDBACK", "callback_data": f"feedback_{task_id}"}
        ]]
    }


def format_result_buttons(task_id: int) -> dict:
    """
    Format inline buttons cho Result message.

    Args:
        task_id: Task ID

    Returns:
        Telegram reply_markup dict
    """
    return {
        "inline_keyboard": [[
            {"text": "✅ APPROVE RESULT", "callback_data": f"approve_result_{task_id}"},
            {"text": "💬 FEEDBACK", "callback_data": f"feedback_{task_id}"}
        ]]
    }


# ===== CLI =====

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Format Telegram messages')
    sub = parser.add_subparsers(dest='type', help='Message type')

    # Plan message
    plan = sub.add_parser('plan', help='Format plan message')
    plan.add_argument('--task-id', type=int, required=True)
    plan.add_argument('--task-name', type=str, required=True)
    plan.add_argument('--agent', type=str, required=True)
    plan.add_argument('--steps', type=str, nargs='+', default=[])
    plan.add_argument('--estimated', type=str, default='N/A')
    plan.add_argument('--replan', action='store_true')
    plan.add_argument('--feedback', type=str, default='')

    # Result message
    result = sub.add_parser('result', help='Format result message')
    result.add_argument('--task-id', type=int, required=True)
    result.add_argument('--task-name', type=str, required=True)
    result.add_argument('--agent', type=str, required=True)
    result.add_argument('--summary', type=str, default='')
    result.add_argument('--path', type=str, default='')
    result.add_argument('--time', type=str, default='N/A')

    args = parser.parse_args()

    if args.type == 'plan':
        msg = format_plan_message(
            task_id=args.task_id,
            task_name=args.task_name,
            selected_agent=args.agent,
            execution_steps=args.steps,
            estimated_time=args.estimated,
            is_replan=args.replan,
            user_feedback=args.feedback
        )
        print(msg)
        print("\n--- Buttons ---")
        print(json.dumps(format_plan_buttons(args.task_id, args.replan), indent=2))

    elif args.type == 'result':
        msg = format_result_message(
            task_id=args.task_id,
            task_name=args.task_name,
            agent_id=args.agent,
            result_summary=args.summary,
            result_path=args.path,
            execution_time=args.time
        )
        print(msg)
        print("\n--- Buttons ---")
        print(json.dumps(format_result_buttons(args.task_id), indent=2))

    else:
        parser.print_help()
