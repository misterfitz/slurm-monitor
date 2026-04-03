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
slurm_popup_key=$(get_tmux_option "@slurm-monitor-popup" "S")
slurm_alert=$(get_tmux_option "@slurm-monitor-alert" "off")
slurm_cluster=$(get_tmux_option "@slurm-monitor-cluster" "")

# Build the command
cmd="$CURRENT_DIR/scripts/slurm-status.sh"
args=""

if [ -n "$slurm_user" ]; then
    args="$args -u $slurm_user"
fi

if [ "$slurm_color" = "on" ]; then
    args="$args --color"
fi

if [ -n "$slurm_cluster" ]; then
    args="$args -M $slurm_cluster"
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

# Bind popup key (prefix + S by default)
popup_cmd="$CURRENT_DIR/scripts/slurm-popup.sh"
popup_args=""
if [ -n "$slurm_user" ]; then
    popup_args="$popup_args -u $slurm_user"
fi
if [ -n "$slurm_cluster" ]; then
    popup_args="$popup_args -M $slurm_cluster"
fi

if [ -n "$slurm_popup_key" ]; then
    tmux bind-key "$slurm_popup_key" display-popup -E -w 62 -h 40 "$popup_cmd $popup_args"
fi

# Job failure alert watcher
if [ "$slurm_alert" = "on" ] && [ -n "$slurm_user" ]; then
    alert_script="$CURRENT_DIR/scripts/slurm-alert.sh"
    if [ -x "$alert_script" ]; then
        # Run alert watcher in background
        "$alert_script" -u "$slurm_user" -i "$slurm_interval" &
    fi
fi
