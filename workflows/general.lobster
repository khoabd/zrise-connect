# general.lobster
# General task processing workflow using OpenClaw Agent
#
# Usage:
#   lobster run general.lobster --argsJson '{"task_id": 42174}'
#
name: general
description: General task processing with OpenClaw Agent
args:
  task_id:
    required: true
    type: int
  feedback:
    default: ""
    type: string
steps:
  - id: invoke_agent
    command: python3 skills/zrise-connect/scripts/invoke_agent_for_task.py --task-id $args.task_id --workflow general --feedback "$args.feedback"
    description: Invoke OpenClaw Agent for general task processing
  
  - id: output
    command: cat
    stdin: $invoke_agent.stdout
    description: Output result
