# requirement-analysis.lobster
# Requirement analysis workflow using OpenClaw Agent
#
# Analyzes requirements, creates user stories, acceptance criteria.
#
# Usage:
#   lobster run requirement-analysis.lobster --args-json '{"task_id": 42174}'
#
name: requirement-analysis
description: Analyze requirements, create user stories, acceptance criteria
args:
  task_id:
    required: true
    type: int
  user_message:
    default: ""
    type: string
  feedback:
    default: ""
    type: string
steps:
  - id: fetch_task
    command: python3 skills/zrise-connect/scripts/fetch_task_data.py $args.task_id
    description: Fetch task from Zrise
  
  - id: agent_analyze
    command: >
      openclaw.invoke
      --agent zrise-analyst
      --task "Bạn là Business Analyst. Hãy phân tích requirement cho task.

Task ID: $args.task_id
User message: $args.user_message
Feedback: $args.feedback

Output:
1. **User Stories** — Format: 'As a [role], I want [feature] so that [benefit]'
2. **Acceptance Criteria** — Measurable, testable
3. **Questions cần làm rõ** — List questions cho PO/Stakeholder
4. **Assumptions** — Giả định đang có
5. **Priority recommendation** — P0/P1/P2 với lý do
6. **Risks** — Identify key risks

Viết bằng tiếng Việt, concrete, actionable."
    stdin: $fetch_task.stdout
    description: Agent analyzes requirements
  
  - id: format
    command: python3 -c "import json, sys; d = json.loads(sys.stdin.read()); print(json.dumps({'task_id': $args.task_id, 'workflow': 'requirement-analysis', 'result': d.get('output', d.get('result', '')), 'source': 'openclaw-agent'}, ensure_ascii=False, indent=2))"
    stdin: $agent_analyze.stdout
  
  - id: output
    command: cat
    stdin: $format.stdout
