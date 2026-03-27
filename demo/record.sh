#!/usr/bin/env bash
# record.sh — Record the demo gif for the README.
#
# Requirements:
#   brew install asciinema agg    (or: cargo install agg)
#
# Usage:
#   demo/record.sh                # Records demo/demo.cast, converts to demo/priority-demo.gif
#
# The script uses mock Slurm commands so it works anywhere.

set -euo pipefail

DEMO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$DEMO_DIR/.." && pwd)"
CAST_FILE="$DEMO_DIR/demo.cast"
GIF_FILE="$DEMO_DIR/priority-demo.gif"

# Check dependencies
for cmd in asciinema agg; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Missing: $cmd"
        echo "Install: brew install asciinema agg"
        exit 1
    fi
done

# Create a script that asciinema will record
PLAY_SCRIPT=$(mktemp)
cat > "$PLAY_SCRIPT" <<SCRIPT
#!/usr/bin/env bash
source "$DEMO_DIR/mock-slurm-env.sh" >/dev/null 2>&1
export SLURM_MONITOR_CMD="python3 $REPO_DIR/scripts/slurm-monitor.py"

clear

# Simulate typing with realistic delays
type_cmd() {
    local cmd="\$1"
    printf '\033[1;32m\$\033[0m '
    for (( i=0; i<\${#cmd}; i++ )); do
        printf '%s' "\${cmd:\$i:1}"
        sleep 0.\$(( RANDOM % 8 + 2 ))
    done
    echo ""
    sleep 0.3
}

echo ""
echo -e "\033[1;36m  slurm-monitor — Slurm status in your tmux & vim\033[0m"
echo ""
sleep 1.5

# 1. Basic cluster overview
type_cmd "slurm-monitor"
python3 "$REPO_DIR/scripts/slurm-monitor.py"
echo ""
sleep 2

# 2. Personal status with QOS and rank
type_cmd "slurm-monitor -u user01"
python3 "$REPO_DIR/scripts/slurm-monitor.py" -u user01
echo ""
sleep 2.5

# 3. Long format with QOS breakdown
type_cmd "slurm-monitor -u user01 --long"
python3 "$REPO_DIR/scripts/slurm-monitor.py" -u user01 --long
echo ""
sleep 3

# 4. Color output (for tmux)
type_cmd "slurm-monitor -u user01 --color"
python3 "$REPO_DIR/scripts/slurm-monitor.py" -u user01 --color
echo ""
sleep 2

# 5. JSON output
type_cmd "slurm-monitor -u user01 --json | python3 -m json.tool | head -20"
python3 "$REPO_DIR/scripts/slurm-monitor.py" -u user01 --json | python3 -m json.tool | head -20
echo "  ..."
echo ""
sleep 3

# 6. Popup dashboard
echo -e "\033[1;36m  prefix+S opens the detail popup in tmux:\033[0m"
echo ""
sleep 1
echo "q" | "$REPO_DIR/scripts/slurm-popup.sh" -u user01 2>/dev/null || true
sleep 3

echo ""
echo -e "\033[2m  github.com/misterfitz/slurm-monitor\033[0m"
sleep 2
SCRIPT
chmod +x "$PLAY_SCRIPT"

echo "Recording demo..."
asciinema rec "$CAST_FILE" \
    --cols 80 \
    --rows 36 \
    --overwrite \
    --command "bash $PLAY_SCRIPT"

rm -f "$PLAY_SCRIPT"

echo ""
echo "Converting to GIF..."
agg "$CAST_FILE" "$GIF_FILE" \
    --font-size 14 \
    --cols 80 \
    --rows 36 \
    --theme monokai

echo ""
echo "Done: $GIF_FILE"
echo "Cast: $CAST_FILE"
