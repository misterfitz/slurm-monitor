#!/usr/bin/env bash
# mock-slurm-env.sh — Sets up fake Slurm commands for demo recording.
#
# Source this to get working squeue/sprio/sshare/sacctmgr/scontrol/sacct/sreport
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
STATE_FILTER=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -u) FILTER_USER="$2"; shift 2 ;;
        -A) shift 2 ;;
        -q) shift 2 ;;
        -t) STATE_FILTER="$2"; shift 2 ;;
        -o) FMT="$2"; shift 2 ;;
        -M) shift 2 ;;
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
    elif [[ "$FMT" == *"%b"* ]]; then
        # GPU GRES for running jobs
        echo "200101|train_gpt|gpu:a100:4"
        echo "200102|finetune_bert|gpu:a100:2"
        echo "200103|eval_model|gpu:1"
        echo "200104|preprocess|(null)"
        echo "200105|tokenize|(null)"
    elif [[ "$FMT" == *"%r"* ]] || [[ "$FMT" == *"%S"* ]]; then
        # Pending details with reasons and ETA
        echo "200110|large_train|Priority|2025-06-15T14:30:00"
        echo "200111|sweep_lr|Priority|2025-06-15T15:00:00"
        echo "200112|data_aug|Resources|N/A"
        echo "200113|eval_v2|Priority|N/A"
        echo "200114|ablation_1|QOSMaxJobsPerUser|N/A"
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
        -M) shift 2 ;;
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
        -M) shift 2 ;;
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

# ── sacct (job history + failures) ────────────────────────────────
cat > "$MOCK_DIR/sacct" <<'SACCT'
#!/usr/bin/env bash
STATE_FILTER=""
FMT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --state=*) STATE_FILTER="${1#--state=}"; shift ;;
        --format=*) FMT="${1#--format=}"; shift ;;
        -M) shift 2 ;;
        *) shift ;;
    esac
done

NOW=$(date +%s)

if [ -n "$STATE_FILTER" ]; then
    # Failed jobs query — return recent failures
    T1=$(date -r $((NOW - 1800)) "+%Y-%m-%dT%H:%M:%S" 2>/dev/null || date -d "@$((NOW - 1800))" "+%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "2025-06-15T10:30:00")
    T2=$(date -r $((NOW - 3600)) "+%Y-%m-%dT%H:%M:%S" 2>/dev/null || date -d "@$((NOW - 3600))" "+%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "2025-06-15T09:45:00")
    T3=$(date -r $((NOW - 5400)) "+%Y-%m-%dT%H:%M:%S" 2>/dev/null || date -d "@$((NOW - 5400))" "+%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "2025-06-15T09:15:00")
    echo "199801|train_gpt_large|FAILED|1:0|${T1}"
    echo "199795|eval_checkpoint|TIMEOUT|0:15|${T2}"
    echo "199780|data_pipeline|OOM|0:0|${T3}"
else
    # Job history query — return completed/failed over 24h
    for h in $(seq 0 23); do
        TS=$((NOW - h * 3600))
        T=$(date -r "$TS" "+%Y-%m-%dT%H:%M:%S" 2>/dev/null || date -d "@$TS" "+%Y-%m-%dT%H:%M:%S" 2>/dev/null || echo "2025-06-15T$(printf '%02d' $((h % 24))):00:00")
        # Generate varying completions per hour
        COMPLETIONS=$(( (h * 7 + 3) % 12 + 1 ))
        for j in $(seq 1 $COMPLETIONS); do
            echo "COMPLETED|${T}"
        done
        # Occasional failures
        if (( h % 8 == 0 )); then
            echo "FAILED|${T}"
        fi
    done
fi
SACCT
chmod +x "$MOCK_DIR/sacct"

# ── sreport (usage budget) ────────────────────────────────────────
cat > "$MOCK_DIR/sreport" <<'SREPORT'
#!/usr/bin/env bash
# Returns account utilization by user
echo "cluster1|physics||12450"
echo "cluster1|user01||3280"
echo "cluster1|user02||4100"
echo "cluster1|user03||5070"
SREPORT
chmod +x "$MOCK_DIR/sreport"

# ── scontrol (for check_slurm_available) ──────────────────────────
cat > "$MOCK_DIR/scontrol" <<'SCONTROL'
#!/usr/bin/env bash
echo "READY"
SCONTROL
chmod +x "$MOCK_DIR/scontrol"

export PATH="$MOCK_DIR:$PATH"
export MOCK_DIR

echo "Mock Slurm environment ready (commands in $MOCK_DIR)"
