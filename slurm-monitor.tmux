#!/usr/bin/env bash
# TPM (Tmux Plugin Manager) entry point for slurm-monitor.
#
# Install via TPM:
#   set -g @plugin 'misterfitz/slurm-monitor'
#
# Configuration (set before the plugin line):
#   set -g @slurm-monitor-user "$USER"        # Show personal fairshare/rank
#   set -g @slurm-monitor-color "on"          # Use tmux color codes
#   set -g @slurm-monitor-interval "10"       # Cache TTL in seconds
#   set -g @slurm-monitor-position "right"    # status-left or status-right

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Read tmux options
get_tmux_option() {
    local option=$1
    local default_value=$2
    local value
    value=$(tmux show-option -gqv "$option")
    if [ -n "$value" ]; then
        echo "$value"
    else
        echo "$default_value"
    fi
}

slurm_user=$(get_tmux_option "@slurm-monitor-user" "")
slurm_color=$(get_tmux_option "@slurm-monitor-color" "off")
slurm_interval=$(get_tmux_option "@slurm-monitor-interval" "10")
slurm_position=$(get_tmux_option "@slurm-monitor-position" "right")

# Build the command
cmd="$CURRENT_DIR/scripts/slurm-status.sh"
args=""

if [ -n "$slurm_user" ]; then
    args="$args -u $slurm_user"
fi

if [ "$slurm_color" = "on" ]; then
    args="$args --color"
fi

export SLURM_MONITOR_CACHE_TTL="$slurm_interval"

# Interpolation string for tmux
interpolation="#($cmd $args)"

# Append to the appropriate status side
if [ "$slurm_position" = "left" ]; then
    current=$(tmux show-option -gqv "status-left")
    tmux set-option -g "status-left" "$current $interpolation"
else
    current=$(tmux show-option -gqv "status-right")
    tmux set-option -g "status-right" "$interpolation $current"
fi
