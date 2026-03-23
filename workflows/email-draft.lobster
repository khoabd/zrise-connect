# email-draft.lobster
# Workflow đơn giản để soạn thảo email thông báo
#
# Usage:
#   lobster run --file skills/zrise-connect/workflows/email-draft.lobster --args-json '{"task_id": 42174}'
#
name: email-draft
description: Soạn thảo email thông báo đơn giản
args:
  task_id:
    required: true
    type: int
steps:
  - id: fetch
    command: python3 skills/zrise-connect/scripts/fetch_task_data.py $args.task_id
    description: Fetch task from Zrise
  
  - id: draft
    command: python3 skills/zrise-connect/scripts/invoke_agent_for_task.py --task-id $args.task_id --workflow email-draft
    description: Agent drafts email
    stdin: $fetch.stdout
  
  - id: output
    command: cat
    stdin: $draft.stdout
    description: Output email draft
