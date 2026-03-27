#!/usr/bin/env bash
# mock-slurm-env.sh — Sets up fake Slurm commands for demo recording.
#
# Source this to get working squeue/sprio/sshare/sacctmgr/scontrol
# commands that return realistic data. Used by demo/record.sh.
#
# Usage: source demo/mock-slurm-env.sh

MOCK_DIR=$(mktemp -d)

# ── squeue: cluster-wide ──────────────────────────────────────────
cat > "$MOCK_DIR/squeue" <<'SQUEUE'
#!/usr/bin/env bash
# Mock squeue returning realistic job states
FILTER_USER=""
FMT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -u) FILTER_USER="$2"; shift 2 ;;
        -A) shift 2 ;;
        -q) shift 2 ;;
        -o) FMT="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [ -n "$FILTER_USER" ]; then
    if [[ "$FMT" == *"%q"* ]]; then
        # Per-QOS breakdown for user
        for i in $(seq 1 8); do echo "RUNNING|normal"; done
        for i in $(seq 1 12); do echo "PENDING|normal"; done
        for i in $(seq 1 3); do echo "RUNNING|gpu"; done
        for i in $(seq 1 5); do echo "PENDING|gpu"; done
    else
        for i in $(seq 1 11); do echo "RUNNING"; done
        for i in $(seq 1 17); do echo "PENDING"; done
    fi
else
    for i in $(seq 1 4823); do echo "RUNNING"; done
    for i in $(seq 1 24691); do echo "PENDING"; done
fi
SQUEUE
chmod +x "$MOCK_DIR/squeue"

# ── sprio ─────────────────────────────────────────────────────────
cat > "$MOCK_DIR/sprio" <<'SPRIO'
#!/usr/bin/env bash
FILTER_USER=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -u) FILTER_USER="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [ -n "$FILTER_USER" ]; then
    echo "100247|89420"
else
    # 24691 pending jobs sorted by priority — user's job #100247 at position 42
    for i in $(seq 1 41); do echo "$((100000 + i))"; done
    echo "100247"
    for i in $(seq 43 24691); do echo "$((100000 + i))"; done
fi
SPRIO
chmod +x "$MOCK_DIR/sprio"

# ── sshare ────────────────────────────────────────────────────────
cat > "$MOCK_DIR/sshare" <<'SSHARE'
#!/usr/bin/env bash
FILTER_USER=""
ALL=""
FILTER_ACCT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -u) FILTER_USER="$2"; shift 2 ;;
        -a) ALL="1"; shift ;;
        -A) FILTER_ACCT="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [ -n "$FILTER_USER" ]; then
    echo "physics|${FILTER_USER}|1000|0.7284|48293012|0.032100"
elif [ -n "$FILTER_ACCT" ]; then
    echo "${FILTER_ACCT}||0.6500"
    echo "${FILTER_ACCT}|user01|0.7284"
    echo "${FILTER_ACCT}|user02|0.5100"
    echo "${FILTER_ACCT}|user03|0.8200"
elif [ -n "$ALL" ]; then
    echo "physics||0.6500"
    echo "physics|user01|0.7284"
    echo "physics|user02|0.5100"
    echo "physics|user03|0.8200"
    echo "cs||0.8800"
    echo "cs|user04|0.9510"
    echo "cs|user05|0.3200"
    echo "chem||0.2300"
    echo "chem|user06|0.1150"
    echo "chem|user07|0.4400"
    echo "bio||0.9100"
    echo "bio|user08|0.8800"
    echo "ling||0.1200"
    echo "ling|user09|0.0820"
    echo "cibot||0.5000"
fi
SSHARE
chmod +x "$MOCK_DIR/sshare"

# ── sacctmgr ─────────────────────────────────────────────────────
cat > "$MOCK_DIR/sacctmgr" <<'SACCTMGR'
#!/usr/bin/env bash
# Returns association with DefaultQOS and allowed QOS list
echo "physics|normal|normal,gpu,high|||1000"
SACCTMGR
chmod +x "$MOCK_DIR/sacctmgr"

# ── scontrol (for check_slurm_available) ──────────────────────────
cat > "$MOCK_DIR/scontrol" <<'SCONTROL'
#!/usr/bin/env bash
echo "READY"
SCONTROL
chmod +x "$MOCK_DIR/scontrol"

export PATH="$MOCK_DIR:$PATH"
export MOCK_DIR

echo "Mock Slurm environment ready (commands in $MOCK_DIR)"
