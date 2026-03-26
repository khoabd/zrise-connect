# CLAUDE.md — Zrise Connect

## Project Overview

Zrise Connect là skill/plugin cho OpenClaw, kết nối OpenClaw agent với Zrise (project management system tại https://zrise.app).

**Multi-Agent Architecture:** Orchestrator điều phối executor agents async qua SQLite job queue.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  ORCHESTRATOR (ai-company)                                │
│  1. fetch → analyze → plan → APPROVE                      │
│  2. Create job in SQLite (agent_id + workflow)             │
│  3. Exit Lobster workflow                                  │
│  4. Poll done jobs → post to Zrise review                 │
│  5. Human: APPROVE / FEEDBACK                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│  EXECUTOR AGENTS (separate workspaces)                     │
│  ~/.openclaw/agents/<agent_id>/                           │
│  1. Poll jobs WHERE agent_id = me AND status = 'assigned' │
│  2. Execute via Claude Code (resumable session)           │
│  3. Write result.md → Mark job 'done'                     │
└─────────────────────────────────────────────────────────────┘
```

## Key Commands

```bash
# Orchestrator
/review-done          # List done jobs
/dispatch <task> <agent>  # Create job for executor
/approve <job>        # Approve result
/feedback <job> <text> # Request revision

# Direct scripts
python3 scripts/orchestrator_review.py --list-done
python3 scripts/post_for_review.py --job-id 4
python3 scripts/handle_review_response.py --job-id 4 --approve
```

## Job Status Lifecycle

```
pending → assigned → in_progress → done → pending_review → approved
                                   ↓                    ↓
                                failed              revision_sent
```

## Quick Rules

1. **Zrise API**: write() uses `[[id]], {vals}` format
2. **message_post()**: `[[id]], {body, message_type}`
3. **Timesheet BEFORE Done stage**
4. **Executor polls async** - don't wait for result in workflow

## See Also

- `.claude/rules/zrise-api.md` - Detailed API patterns + gotchas
- `.claude/rules/multi-agent.md` - Multi-agent architecture details
- `docs/OPERATIONS_STRATEGY.md` - Team operations playbook
