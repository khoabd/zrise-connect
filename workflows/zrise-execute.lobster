# zrise-execute.lobster
name: zrise-execute
description: "Process Zrise task via file-based data bus + Gemini API"
args:
  task_id:
    required: true
  user_message:
    default: ""
  feedback:
    default: ""
env:
  SHELL: /bin/bash
  PATH: "/opt/homebrew/bin:/Users/khoabui/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
steps:
  # Phase 1: Fetch + Analyze
  - id: fetch
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/fetch_task_data.py $LOBSTER_ARG_TASK_ID --save"
    description: "Fetch task, save to .tasks folder"

  - id: task_dir
    run: "echo $fetch.stdout"
    description: "Get task dir path"

  - id: analyze
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/analyze_task.py --task-dir \"$task_dir.stdout\" --message \"$LOBSTER_ARG_USER_MESSAGE\""
    description: "Analyze, select agent, save plan"

  - id: post_plan
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/writeback_to_zrise.py --task-dir \"$task_dir.stdout\" --plan"
    description: "Post plan to Zrise"

  - id: start_progress
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/update_task_stage.py $LOBSTER_ARG_TASK_ID \"In Process\" --comment \"AI dang xu ly task\""
    description: "Stage In Process"
    allow_failure: true

  # Phase 2: Approve Plan
  - id: review_plan
    approval: "Review plan cho task. Xem items de biet agent. Approve de thuc thi?"
    stdin: $analyze.stdout
    description: "Review plan"

  # Phase 3: Execute
  - id: agent_name
    run: "python3 -c \"import sys,json; print(json.load(sys.stdin).get('suggested_agent','ai-company'))\""
    stdin: $analyze.json
    when: $review_plan.approved
    description: "Get agent name"

  - id: execute
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/execute_ai_task.py --task-dir \"$task_dir.stdout\" --agent \"$agent_name.stdout\" --feedback \"$LOBSTER_ARG_FEEDBACK\""
    when: $review_plan.approved
    description: "Execute via Gemini API"

  # Phase 4: Approve Result
  - id: review_result
    approval: "Review ket qua task. Approve de gui len Zrise + timesheet + Done."
    stdin: $execute.stdout
    when: $review_plan.approved
    description: "Review result"

  # Phase 5: Finalize
  - id: writeback
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/writeback_to_zrise.py --task-dir \"$task_dir.stdout\""
    when: $review_result.approved
    description: "Write result to Zrise"

  - id: timesheet
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/fill_timesheet.py --task-id $LOBSTER_ARG_TASK_ID --hours 0.5 --description \"AI workflow - Task #$LOBSTER_ARG_TASK_ID\""
    when: $review_result.approved
    allow_failure: true
    description: "Log timesheet"

  - id: mark_done
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/update_task_stage.py $LOBSTER_ARG_TASK_ID \"Done\" --comment \"Task processed via AI workflow\""
    when: $review_result.approved
    allow_failure: true
    description: "Stage Done"

  - id: final
    run: "echo done"
    description: "Completed"
