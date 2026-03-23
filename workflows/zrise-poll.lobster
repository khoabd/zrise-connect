# zrise-poll.lobster
# Steps 1-2: Poll new tasks + format notification
#
# Usage (from cron or manual):
#   lobster run zrise-poll.lobster --args '{"employee_id": 10}'
#
name: zrise-poll
description: |
  Poll Zrise tasks for employee, filter new/changed/SLA, format notification.
  Steps 1-2 of the 8-step flow.
args:
  employee_id:
    required: true
  sla_hours:
    default: "24"
  deadline_hours:
    default: "48"
  limit:
    default: "20"
steps:
  - id: poll
    command: >
      python3 skills/zrise-connect/scripts/poll_employee_work.py
      --employee-id $args.employee_id
      --limit $args.limit
      --sla-hours $args.sla_hours
      --deadline-hours $args.deadline_hours
      --json
      --notify-only
    description: Poll Zrise tasks, filter new/changed/SLA

  - id: has_tasks
    command: >
      exec --json "echo '{\"has_tasks\": $(cat /dev/stdin | python3 -c \"import json,sys; d=json.load(sys.stdin); print('true' if d.get('notify_count',0)>0 else 'false')\")}'"
    stdin: $poll.stdout
    description: Check if there are tasks to notify

  - id: format
    command: >
      python3 skills/zrise-connect/scripts/format_work_item_notification.py --stdin
    stdin: $poll.stdout
    condition: $has_tasks.stdout.has_tasks == "true"
    description: Format notification message

  - id: deliver
    command: >
      approve
      --preview-from-stdin
      --prompt "Gửi notification này cho nhân viên?"
    stdin: $format.stdout
    approval: required
    condition: $has_tasks.stdout.has_tasks == "true"
    description: Approval gate before sending notification

  - id: move_to_in_progress
    command: >
      python3 -c "
      import json, sys
      data = json.load(sys.stdin)
      tasks = [t for t in data.get('notify_tasks', []) if t.get('category') == 'new']
      if not tasks:
        print(json.dumps({'moved': 0}))
        sys.exit(0)
      task_ids = [str(t['task_id']) for t in tasks]
      print(json.dumps({'move_tasks': task_ids}))
      "
    stdin: $poll.stdout
    condition: $has_tasks.stdout.has_tasks == "true"
    description: Extract new task IDs for stage transition

  - id: update_stages
    command: >
      python3 skills/zrise-connect/scripts/update_task_stage.py
      --batch-stdin
      --stage "In Progress"
    stdin: $move_to_in_progress.stdout
    condition: $has_tasks.stdout.has_tasks == "true" && $move_to_in_progress.stdout.moved != "0"
    description: Move new tasks to In Progress

  - id: result
    command: |
      echo '{"ok": true, "tasks_notified": $poll.stdout.notify_count}'
    description: Poll complete
