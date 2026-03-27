#!/usr/bin/env bash
# slurm-popup.sh — Rich Slurm dashboard for tmux display-popup.
#
# Shows detailed cluster status, your jobs, fairshare, QOS, and queue
# position in a formatted panel. Designed to be triggered from a tmux
# keybinding.
#
# Usage:
#   tmux display-popup -E -w 60 -h 20 '/path/to/slurm-popup.sh -u $USER'
#
# Keybinding (add to ~/.tmux.conf):
#   bind S display-popup -E -w 60 -h 20 '~/.tmux/plugins/slurm-monitor/scripts/slurm-popup.sh -u $USER'

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find the monitor command
if [ -n "${SLURM_MONITOR_CMD:-}" ]; then
    MONITOR_CMD="$SLURM_MONITOR_CMD"
elif command -v slurm-monitor &>/dev/null; then
    MONITOR_CMD="slurm-monitor"
elif [ -x "$SCRIPT_DIR/slurm-monitor.py" ]; then
    MONITOR_CMD="python3 $SCRIPT_DIR/slurm-monitor.py"
else
    echo "slurm-monitor not found"
    exit 1
fi

# Parse args — pass through to slurm-monitor
ARGS=("$@")

# Get JSON data
json=$($MONITOR_CMD "${ARGS[@]}" --json 2>/dev/null) || json=""
if [ -z "$json" ] || [ "$json" = "null" ]; then
    echo "  No data available (Slurm CLI not found or not responding)"
    echo ""
    echo "  Press any key to close."
    read -rsn1
    exit 0
fi

# Use python to format the dashboard from JSON
python3 - "$json" <<'PYTHON'
import json, sys, os

try:
    data = json.loads(sys.argv[1])
except (json.JSONDecodeError, IndexError):
    print("  Failed to parse Slurm data")
    sys.exit(1)

# Terminal width for the popup
try:
    cols = int(os.environ.get("COLUMNS", 56))
except ValueError:
    cols = 56
W = min(cols, 56)
HR = "\033[2m" + "\u2500" * W + "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"

def compact(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 10_000: return f"{n/1_000:.0f}k"
    if n >= 1_000: return f"{n/1_000:.1f}k"
    return str(int(n))

def fs_color(v):
    if v >= 0.5: return GREEN
    if v >= 0.3: return YELLOW
    return RED

def bar(val, max_val, width=20):
    if max_val <= 0: return " " * width
    filled = int(val / max_val * width)
    filled = min(filled, width)
    return f"{GREEN}{'█' * filled}{DIM}{'░' * (width - filled)}{RESET}"

print()
print(f"  {BOLD}Slurm Cluster Status{RESET}")
print(f"  {HR}")

# Cluster overview
r = data.get("running", 0)
p = data.get("pending", 0)
t = data.get("total", r + p)
print(f"  {CYAN}Running{RESET}  {compact(r):>6}  {bar(r, t)}")
print(f"  {CYAN}Pending{RESET}  {compact(p):>6}  {bar(p, t)}")
print(f"  {DIM}Total{RESET}    {compact(t):>6}")

# User section
user = data.get("user")
if user:
    name = user.get("name", "?")
    fs = user.get("fairshare", 0)
    fc = fs_color(fs)
    print()
    print(f"  {HR}")
    print(f"  {BOLD}{name}{RESET}")
    print()

    # Fairshare
    print(f"  Fairshare    {fc}{fs:.4f}{RESET}  {bar(fs, 1.0)}")

    # Queue rank
    rank = user.get("rank")
    total_pending = user.get("total_pending")
    if rank and total_pending:
        pct = rank / total_pending * 100
        rank_color = GREEN if pct <= 10 else (YELLOW if pct <= 30 else RED)
        print(f"  Queue Pos    {rank_color}#{rank}{RESET} of {compact(total_pending)}  ({pct:.1f}%)")
    elif rank:
        print(f"  Queue Pos    #{rank}")

    # User's jobs
    ur = user.get("running", 0)
    up = user.get("pending", 0)
    print(f"  Your Jobs    {GREEN}{ur} running{RESET}, {up} pending")

    # Account
    acct = user.get("account")
    if acct:
        print(f"  Account      {acct}")

    # QOS
    default_qos = user.get("default_qos")
    allowed_qos = user.get("allowed_qos", [])
    if default_qos:
        print(f"  Default QOS  {CYAN}{default_qos}{RESET}")
    if allowed_qos:
        others = [q for q in allowed_qos if q != default_qos]
        if others:
            print(f"  {DIM}Allowed QOS  {', '.join(others)}{RESET}")

    # Per-QOS job breakdown
    job_qos = user.get("job_qos", {})
    if job_qos:
        print()
        print(f"  {DIM}Jobs by QOS:{RESET}")
        for qname in sorted(job_qos.keys()):
            jq = job_qos[qname]
            jr, jp = jq["running"], jq["pending"]
            active = f"{CYAN}{qname}{RESET}" if default_qos and qname == default_qos else qname
            print(f"    {active:30s}  r:{GREEN}{jr}{RESET}  p:{jp}")

# Account section
account = data.get("account")
if account:
    print()
    print(f"  {HR}")
    aname = account.get("name", "?")
    afs = account.get("fairshare", 0)
    ar = account.get("running", 0)
    ap = account.get("pending", 0)
    ausers = account.get("users", 0)
    print(f"  {BOLD}Account: {aname}{RESET}")
    print(f"  Fairshare    {fs_color(afs)}{afs:.4f}{RESET}")
    print(f"  Jobs         {GREEN}{ar} running{RESET}, {ap} pending")
    if ausers:
        print(f"  Users        {ausers}")

# Fairshare extremes
top = data.get("top_fs")
low = data.get("low_fs")
if top and low:
    print()
    print(f"  {HR}")
    print(f"  {DIM}Cluster Fairshare Range{RESET}")
    print(f"  {GREEN}Highest{RESET}  {top['user']} ({top['fairshare']:.2f})")
    print(f"  {RED}Lowest{RESET}   {low['user']} ({low['fairshare']:.2f})")

print()
print(f"  {DIM}Press any key to close.{RESET}")
PYTHON

# Wait for keypress
read -rsn1
