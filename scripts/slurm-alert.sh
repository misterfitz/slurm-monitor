#!/usr/bin/env bash
# slurm-alert.sh — Background watcher that sends tmux display-message on job failures.
#
# Compares the current failure count against the last known count and
# sends a tmux notification when new failures are detected.
#
# Usage:
#   slurm-alert.sh -u $USER -i 30    # check every 30s
#
# Designed to be launched from slurm-monitor.tmux when @slurm-monitor-alert is "on".

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="/tmp/slurm-alert-${USER:-unknown}.state"
INTERVAL=30

# Parse args
while getopts "u:i:" opt; do
    case $opt in
        u) SLURM_USER="$OPTARG" ;;
        i) INTERVAL="$OPTARG" ;;
        *) ;;
    esac
done

if [ -z "${SLURM_USER:-}" ]; then
    exit 1
fi

# Find the monitor command
if [ -n "${SLURM_MONITOR_CMD:-}" ]; then
    MONITOR_CMD="$SLURM_MONITOR_CMD"
elif command -v slurm-monitor &>/dev/null; then
    MONITOR_CMD="slurm-monitor"
elif [ -x "$SCRIPT_DIR/slurm-monitor.py" ]; then
    MONITOR_CMD="python3 $SCRIPT_DIR/slurm-monitor.py"
else
    exit 1
fi

# Read last known failure count
last_count=0
if [ -f "$STATE_FILE" ]; then
    last_count=$(cat "$STATE_FILE" 2>/dev/null || echo 0)
fi

while true; do
    sleep "$INTERVAL"

    # Get current failure count from JSON
    json=$($MONITOR_CMD -u "$SLURM_USER" --json 2>/dev/null) || continue
    count=$(echo "$json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('failed_jobs',[])))" 2>/dev/null) || continue

    if [ "$count" -gt "$last_count" ] && [ "$count" -gt 0 ]; then
        new_failures=$((count - last_count))
        # Get the most recent failure name
        name=$(echo "$json" | python3 -c "
import sys,json
d=json.load(sys.stdin)
jobs=d.get('failed_jobs',[])
if jobs: print(jobs[0].get('name','?'))
else: print('?')
" 2>/dev/null) || name="?"

        if [ "$new_failures" -eq 1 ]; then
            msg="Slurm: job '$name' failed"
        else
            msg="Slurm: $new_failures new job failures (latest: $name)"
        fi

        # Send tmux display-message if tmux is running
        if command -v tmux &>/dev/null && tmux list-sessions &>/dev/null 2>&1; then
            tmux display-message -d 5000 "#[fg=red,bold]$msg"
        fi
    fi

    last_count="$count"
    echo "$last_count" > "$STATE_FILE"
done
