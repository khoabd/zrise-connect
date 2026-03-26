# zrise-multi-agent.lobster
# Multi-agent async workflow: Plan → Create Job → Executor runs async → Review → Finalize

name: zrise-multi-agent
description: "Multi-agent workflow: orchestrate, executor runs async, human reviews"

args:
  task_id:
    required: true
  user_message:
    default: ""
env:
  SHELL: /bin/bash
  PATH: "/opt/homebrew/bin:/Users/khoabui/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

steps:
  # === PHASE 1: FETCH + ANALYZE ===
  - id: fetch
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/fetch_task_data.py $LOBSTER_ARG_TASK_ID --save"
    description: "Fetch task from Zrise, save to .tasks folder"

  - id: task_dir
    run: "echo $fetch.stdout"
    description: "Get task directory path"

  - id: analyze
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/analyze_task.py --task-dir \"$task_dir.stdout\" --message \"$LOBSTER_ARG_USER_MESSAGE\""
    description: "Analyze task, select agent, generate plan"

  - id: post_plan
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/writeback_to_zrise.py --task-dir \"$task_dir.stdout\" --plan"
    description: "Post plan to Zrise for review"

  # === PHASE 2: HUMAN APPROVES PLAN ===
  - id: review_plan
    approval: "📋 Review Plan\n\nAgent: $analyze.stdout (suggested_agent)\n\nWorkflow will:\n1. Create job in queue\n2. Executor agent picks up\n3. Result posted for your review\n4. You approve or request revision\n\nProceed?"
    stdin: $analyze.stdout
    description: "Human approves plan + agent selection"

  # === PHASE 3: CREATE JOB (EXECUTOR WILL RUN ASYNC) ===
  - id: agent_id
    run: "python3 -c \"import sys,json; print(json.load(sys.stdin).get('suggested_agent','general-agent'))\""
    stdin: $analyze.json
    when: $review_plan.approved
    description: "Extract agent_id from plan"

  - id: workflow
    run: "python3 -c \"import sys,json; print(json.load(sys.stdin).get('workflow','general'))\""
    stdin: $analyze.json
    when: $review_plan.approved
    description: "Extract workflow type"

  - id: create_job
    run: "python3 -c \"\nimport sys\nsys.path.insert(0, '/Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts')\nfrom db import init_db, create_job\ninit_db()\njob = create_job(task_id=$LOBSTER_ARG_TASK_ID, agent_id=sys.argv[1], workflow=sys.argv[2])\nprint(job['id'])\n\" $agent_id.stdout $workflow.stdout"
    when: $review_plan.approved
    description: "Create job in SQLite queue"

  - id: job_created
    run: "echo \"Job $create_job.stdout created for task $LOBSTER_ARG_TASK_ID - Executor will pick up\""
    when: $review_plan.approved
    description: "Confirm job creation"

  - id: stage_in_progress
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/update_task_stage.py $LOBSTER_ARG_TASK_ID \"In Process\" --comment \"Job #$create_job.stdout queued for executor\""
    when: $review_plan.approved
    allow_failure: true
    description: "Update Zrise stage to In Process"

  - id: notify_executor
    run: "python3 -c \"\nimport sys\nsys.path.insert(0, '/Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts')\nfrom db import init_db, add_task_log\ninit_db()\nadd_task_log($LOBSTER_ARG_TASK_ID, 'job_queued', 'orchestrator', {'job_id': $create_job.stdout, 'agent': '$agent_id.stdout'})\nprint('logged')\n\""
    when: $review_plan.approved
    description: "Log job creation for executor"

  # === PHASE 4: EXIT - EXECUTOR RUNS ASYNC ===
  # At this point Lobster exits. Executor (via cron) will:
  # 1. Poll for jobs with status='assigned'
  # 2. Claim job (status='in_progress')
  # 3. Execute via Claude Code
  # 4. Write result.md
  # 5. Mark job status='done'
  # Then orchestrator polls for done jobs and posts for review

  - id: exit_message
    run: "echo \"EXIT: Job created. Executor will run async. Check result via orchestrator_review.py\""
    when: $review_plan.approved
    description: "Signal workflow pause - executor takes over"

  - id: exit
    stop: true
    when: $review_plan.approved
    description: "Exit workflow - executor handles execution"

  # === IF PLAN NOT APPROVED ===
  - id: plan_rejected
    run: "python3 /Users/khoabui/.openclaw/workspace-ai-company/skills/zrise-connect/scripts/update_task_stage.py $LOBSTER_ARG_TASK_ID \"Backlog\" --comment \"Plan rejected by manager\""
    when: $review_plan.rejected
    description: "Revert stage if plan rejected"
