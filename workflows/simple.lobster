# simple.lobster
# Simple workflow - Single execute step
#
# Usage:
#   lobster run simple.lobster --argsJson '{"task_id": 42174}'
#
# Workflow:
#   1. Execute calls zrise-worker agent
#   2. Agent analyzes task
#   3. Agent spawns subagents if needed
#   4. Agent aggregates results
#   5. Agent writes back to Zrise
#
name: simple
description: Simple task execution with zrise-worker agent
args:
  task_id:
    required: true
    type: int
  workflow:
    default: "general"
    type: string
  feedback:
    default: ""
    type: string
steps:
  - id: execute
    command: python3 skills/zrise-connect/scripts/execute_task.py --task-id $args.task_id --workflow $args.workflow --feedback "$args.feedback"
    description: Execute task via zrise-worker agent
  
  - id: output
    command: cat
    stdin: $execute.stdout
    description: Output result
