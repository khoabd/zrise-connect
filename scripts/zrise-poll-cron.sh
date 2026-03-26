#!/bin/bash
# Zrise Poll Cron Job - Chạy mỗi 1 phút
# Usage: ./zrise-poll-cron.sh [employee_id] [output_file]

EMPLOYEE_ID=${1:-10}
OUTPUT_FILE=${2:-/tmp/zrise-poll-latest.json}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"

# Poll tasks
python3 poll_employee_work.py \
  --employee-id "$EMPLOYEE_ID" \
  --limit 20 \
  --sla-hours 24 \
  --deadline-hours 48 \
  --json > "$OUTPUT_FILE" 2>&1

# Log timestamp
echo "Poll completed at $(date -Iseconds)" >> /tmp/zrise-poll.log

# Optional: Send notification if there are tasks to notify
NOTIFY_COUNT=$(python3 -c "import json; print(json.load(open('$OUTPUT_FILE')).get('notify_count', 0))" 2>/dev/null || echo 0)

if [ "$NOTIFY_COUNT" -gt 0 ]; then
  echo "[$(date -Iseconds)] $NOTIFY_COUNT tasks need attention" >> /tmp/zrise-poll.log
fi
