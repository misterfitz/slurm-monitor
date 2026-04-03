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

# Fast typing effect
type_cmd() {
    local cmd="\$1"
    printf '\033[1;32m\$\033[0m '
    for (( i=0; i<\${#cmd}; i++ )); do
        printf '%s' "\${cmd:\$i:1}"
        sleep 0.0\$(( RANDOM % 4 + 2 ))
    done
    echo ""
    sleep 0.1
}

echo ""
echo -e "\033[1;36m  slurm-monitor — Slurm status in your tmux & vim\033[0m"
echo ""
sleep 0.8

# 1. Basic cluster overview
type_cmd "slurm-monitor"
python3 "$REPO_DIR/scripts/slurm-monitor.py"
echo ""
sleep 1

# 2. Personal status with failures, GPU, sparkline
type_cmd "slurm-monitor -u user01"
python3 "$REPO_DIR/scripts/slurm-monitor.py" -u user01
echo ""
sleep 1.5

# 3. Long format with everything
type_cmd "slurm-monitor -u user01 --long"
python3 "$REPO_DIR/scripts/slurm-monitor.py" -u user01 --long
echo ""
sleep 2

# 4. Popup dashboard
echo ""
echo -e "\033[1;36m  prefix+S opens the detail popup:\033[0m"
sleep 0.5
echo "q" | "$REPO_DIR/scripts/slurm-popup.sh" -u user01 2>/dev/null || true
sleep 2

echo ""
echo -e "\033[2m  github.com/misterfitz/slurm-monitor\033[0m"
sleep 1
SCRIPT
chmod +x "$PLAY_SCRIPT"

echo "Recording demo..."
asciinema rec "$CAST_FILE" \
    --cols 80 \
    --rows 46 \
    --overwrite \
    --command "bash $PLAY_SCRIPT"

rm -f "$PLAY_SCRIPT"

echo ""
echo "Converting to GIF..."
agg "$CAST_FILE" "$GIF_FILE" \
    --font-size 14 \
    --cols 80 \
    --rows 46 \
    --speed 1.5 \
    --theme monokai

echo ""
echo "Done: $GIF_FILE"
echo "Cast: $CAST_FILE"
