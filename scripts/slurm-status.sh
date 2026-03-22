#!/usr/bin/env bash
# slurm-status.sh — Cached wrapper for tmux/vim integration.
#
# Calls slurm-monitor and caches the result to avoid hammering
# the Slurm scheduler on every tmux refresh cycle.
#
# Usage in ~/.tmux.conf:
#   set -g status-right '#(/path/to/slurm-status.sh -u $USER)'
#   set -g status-interval 10
#
# Environment:
#   SLURM_MONITOR_CACHE_TTL  Cache lifetime in seconds (default: 10)
#   SLURM_MONITOR_CMD        Override the monitor command path

set -euo pipefail

CACHE_TTL="${SLURM_MONITOR_CACHE_TTL:-10}"
CACHE_FILE="/tmp/slurm-monitor-${USER:-unknown}.cache"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Serve from cache if fresh enough
if [ -f "$CACHE_FILE" ]; then
    if [[ "$OSTYPE" == darwin* ]]; then
        mod_time=$(stat -f%m "$CACHE_FILE" 2>/dev/null || echo 0)
    else
        mod_time=$(stat -c%Y "$CACHE_FILE" 2>/dev/null || echo 0)
    fi
    now=$(date +%s)
    age=$(( now - mod_time ))
    if [ "$age" -lt "$CACHE_TTL" ]; then
        cat "$CACHE_FILE"
        exit 0
    fi
fi

# Find the monitor command
if [ -n "${SLURM_MONITOR_CMD:-}" ]; then
    MONITOR_CMD="$SLURM_MONITOR_CMD"
elif command -v slurm-monitor &>/dev/null; then
    MONITOR_CMD="slurm-monitor"
elif [ -x "$SCRIPT_DIR/slurm-monitor.py" ]; then
    MONITOR_CMD="python3 $SCRIPT_DIR/slurm-monitor.py"
else
    echo "slurm:?" > "$CACHE_FILE"
    cat "$CACHE_FILE"
    exit 0
fi

# Refresh cache
$MONITOR_CMD "$@" > "$CACHE_FILE" 2>/dev/null || echo "slurm:err" > "$CACHE_FILE"
cat "$CACHE_FILE"
