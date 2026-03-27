#!/usr/bin/env python3
"""slurm-monitor — Compact Slurm priority and fairshare status for tmux & vim.

Talks directly to Slurm commands (squeue, sprio, sshare, scontrol).
Designed to run on an HPC login node where Slurm CLI tools are available.

Usage:
    slurm-monitor                      # Cluster overview: R:5k P:25k
    slurm-monitor -u $USER             # Personal: R:5k P:25k fs:0.82 #3
    slurm-monitor -u $USER --color     # With tmux color codes
    slurm-monitor -u $USER --json      # JSON output for scripting
    slurm-monitor --watch              # Refresh every 5s
    slurm-monitor --watch -r 10        # Refresh every 10s
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from typing import Optional


def run_slurm(cmd: str) -> str | None:
    """Run a Slurm command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def check_slurm_available() -> bool:
    """Check if Slurm CLI tools are on PATH."""
    return shutil.which("squeue") is not None


# ── Data gathering ──────────────────────────────────────────────────


def get_queue_counts(qos: "Optional[str]" = None) -> dict:
    """Get running/pending/total job counts, optionally filtered by QOS."""
    counts = {"running": 0, "pending": 0, "total": 0}

    cmd = "squeue -h -o '%T' --sort=-p"
    if qos:
        cmd += f" -q {qos}"
    out = run_slurm(cmd)
    if not out:
        return counts

    for line in out.split("\n"):
        state = line.strip().upper()
        if not state:
            continue
        counts["total"] += 1
        if state in ("RUNNING", "R", "COMPLETING", "CG"):
            counts["running"] += 1
        elif state in ("PENDING", "PD"):
            counts["pending"] += 1

    return counts


def get_user_qos(user: str, account: Optional[str] = None) -> dict:
    """Get QOS info for a user from sacctmgr.

    Returns {"default_qos": "normal", "allowed_qos": ["normal", "gpu", "high"],
             "details": [{"account": "physics", "default_qos": "normal", ...}]}
    """
    cmd = (
        f"sacctmgr show assoc user={user} "
        f"format=Account,DefaultQOS,QOS,MaxJobs,MaxSubmitJobs,Priority -P -n"
    )
    if account:
        cmd += f" account={account}"
    out = run_slurm(cmd)
    if not out:
        return {}

    result = {"default_qos": None, "allowed_qos": [], "details": []}
    seen_qos = set()

    for line in out.split("\n"):
        parts = line.split("|")
        if len(parts) < 6:
            continue

        acct = parts[0].strip()
        default_qos = parts[1].strip() or None
        qos_list_str = parts[2].strip()
        allowed = [q.strip() for q in qos_list_str.split(",") if q.strip()] if qos_list_str else []

        # Use the first association's default QOS (matching account takes priority)
        if default_qos and result["default_qos"] is None:
            result["default_qos"] = default_qos

        for q in allowed:
            seen_qos.add(q)

        result["details"].append({
            "account": acct,
            "default_qos": default_qos,
            "allowed_qos": allowed,
            "max_jobs": _safe_int(parts[3]) if parts[3].strip() else None,
            "max_submit": _safe_int(parts[4]) if parts[4].strip() else None,
            "priority": _safe_int(parts[5]) if parts[5].strip() else None,
        })

    result["allowed_qos"] = sorted(seen_qos)
    return result


def get_job_qos(user: str) -> dict:
    """Get per-QOS job breakdown for a user from squeue.

    Returns {"normal": {"running": 5, "pending": 10}, "gpu": {"running": 2, "pending": 3}}
    """
    out = run_slurm(f"squeue -u {user} -h -o '%T|%q'")
    if not out:
        return {}

    breakdown = {}
    for line in out.split("\n"):
        parts = line.strip().split("|")
        if len(parts) < 2:
            continue
        state = parts[0].strip().upper()
        qos = parts[1].strip()
        if not qos:
            qos = "default"

        if qos not in breakdown:
            breakdown[qos] = {"running": 0, "pending": 0}

        if state in ("RUNNING", "R", "COMPLETING", "CG"):
            breakdown[qos]["running"] += 1
        elif state in ("PENDING", "PD"):
            breakdown[qos]["pending"] += 1

    return breakdown


def get_user_info(user: str) -> dict | None:
    """Get fairshare, QOS, and queue info for a specific user."""
    info = {}

    # Fairshare from sshare
    out = run_slurm(
        f"sshare -u {user} -U -P -h "
        f"--format=Account,User,RawShares,FairShare,RawUsage,EffectvUsage"
    )
    if out:
        for line in out.split("\n"):
            parts = line.split("|")
            if len(parts) >= 6 and parts[1].strip() == user:
                info["account"] = parts[0].strip()
                info["fairshare"] = _safe_float(parts[3])
                info["raw_usage"] = _safe_int(parts[4])
                info["effectv_usage"] = _safe_float(parts[5])
                break

    if not info:
        return None

    # QOS associations
    qos_info = get_user_qos(user, info.get("account"))
    if qos_info:
        info["default_qos"] = qos_info.get("default_qos")
        info["allowed_qos"] = qos_info.get("allowed_qos", [])
        info["qos_details"] = qos_info.get("details", [])

    # Per-QOS job breakdown
    job_qos = get_job_qos(user)
    if job_qos:
        info["job_qos"] = job_qos

    # User's job counts
    out = run_slurm(f"squeue -u {user} -h -o '%T'")
    running = pending = 0
    if out:
        for line in out.split("\n"):
            s = line.strip().upper()
            if s in ("RUNNING", "R", "COMPLETING", "CG"):
                running += 1
            elif s in ("PENDING", "PD"):
                pending += 1
    info["running"] = running
    info["pending"] = pending

    # Queue rank — user's best pending job vs all pending
    out = run_slurm(
        f"sprio -u {user} -h --sort=-Y --format='%i|%Y' 2>/dev/null"
    )
    user_best_id = None
    user_best_prio = 0
    if out:
        for line in out.split("\n"):
            parts = line.strip().split("|")
            if len(parts) >= 2:
                prio = _safe_float(parts[1])
                if prio > user_best_prio:
                    user_best_prio = prio
                    user_best_id = parts[0].strip()
                break  # already sorted

    if user_best_id:
        # Count how many pending jobs have higher priority
        out = run_slurm("sprio -h --sort=-Y --format='%i' 2>/dev/null")
        if out:
            all_ids = [line.strip() for line in out.split("\n") if line.strip()]
            try:
                rank = all_ids.index(user_best_id) + 1
                info["rank"] = rank
                info["total_pending"] = len(all_ids)
            except ValueError:
                pass

    return info


def get_fairshare_extremes() -> dict:
    """Get the highest and lowest fairshare users."""
    out = run_slurm(
        "sshare -a -P -h --format=Account,User,FairShare"
    )
    if not out:
        return {}

    users = []
    for line in out.split("\n"):
        parts = line.split("|")
        if len(parts) >= 3:
            user = parts[1].strip()
            if user and user != "(null)":
                fs = _safe_float(parts[2])
                users.append({"user": user, "account": parts[0].strip(), "fairshare": fs})

    if not users:
        return {}

    top = max(users, key=lambda x: x["fairshare"])
    low = min(users, key=lambda x: x["fairshare"])
    return {"top_fs": top, "low_fs": low}


def get_account_info(account: str) -> dict | None:
    """Get summary info for a specific account."""
    out = run_slurm(
        f"sshare -A {account} -P -h --format=Account,User,FairShare"
    )
    if not out:
        return None

    info = {"name": account, "users": 0, "fairshare": 0}
    for line in out.split("\n"):
        parts = line.split("|")
        if len(parts) >= 3 and parts[0].strip() == account:
            user = parts[1].strip()
            if not user:
                info["fairshare"] = _safe_float(parts[2])
            else:
                info["users"] += 1

    # Account job counts
    out = run_slurm(f"squeue -A {account} -h -o '%T'")
    running = pending = 0
    if out:
        for line in out.split("\n"):
            s = line.strip().upper()
            if s in ("RUNNING", "R"):
                running += 1
            elif s in ("PENDING", "PD"):
                pending += 1
    info["running"] = running
    info["pending"] = pending

    return info


# ── Formatting ──────────────────────────────────────────────────────


def compact_num(n: float) -> str:
    """Format a number compactly: 1234 → 1.2k, 25000 → 25k."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    elif n >= 10_000:
        return f"{n / 1_000:.0f}k"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}k"
    else:
        return f"{n:.0f}"


def format_status(data: dict, color: bool = False, max_width: int = 0) -> str:
    """Format the status data as a compact string."""
    parts = []

    r = compact_num(data["running"])
    p = compact_num(data["pending"])
    if color:
        parts.append(f"#[fg=green]R:{r}#[default] P:{p}")
    else:
        parts.append(f"R:{r} P:{p}")

    if "user" in data and data["user"]:
        u = data["user"]
        fs = u.get("fairshare", 0)

        if color:
            if fs >= 0.5:
                fc = "green"
            elif fs >= 0.3:
                fc = "yellow"
            else:
                fc = "red"
            segment = f"#[fg={fc}]fs:{fs:.2f}#[default]"
        else:
            segment = f"fs:{fs:.2f}"

        if "rank" in u and "total_pending" in u:
            segment += f" #{u['rank']}/{compact_num(u['total_pending'])}"
        elif "rank" in u:
            segment += f" #{u['rank']}"

        # Show active QOS (the ones with running/pending jobs)
        qos_names = _active_qos_names(u)
        if qos_names:
            segment += f" qos:{','.join(qos_names)}"

        parts.append(segment)

    if "account" in data and data["account"]:
        a = data["account"]
        parts.append(f"{a['name']} fs:{a['fairshare']:.2f}")

    result = " ".join(parts)

    if max_width and not color and len(result) > max_width:
        result = result[:max_width - 1] + "~"

    return result


def _active_qos_names(user_info: dict) -> list:
    """Return QOS names from running jobs, or the account default QOS."""
    job_qos = user_info.get("job_qos", {})
    if job_qos:
        return sorted(job_qos.keys())
    default = user_info.get("default_qos")
    if default:
        return [default]
    return []


def format_long(data: dict) -> str:
    """Format as a longer one-liner with fairshare extremes and QOS."""
    parts = []

    parts.append(f"R:{compact_num(data['running'])} P:{compact_num(data['pending'])}")

    if "user" in data and data["user"]:
        u = data["user"]
        seg = f"{u.get('name', '?')} fs:{u.get('fairshare', 0):.2f}"
        if "rank" in u:
            seg += f" #{u['rank']}/{compact_num(u.get('total_pending', 0))}"
        if u.get("running") or u.get("pending"):
            seg += f" (r:{u.get('running', 0)} p:{u.get('pending', 0)})"
        # QOS breakdown per-QOS job counts
        job_qos = u.get("job_qos", {})
        if job_qos:
            qos_parts = []
            for qname in sorted(job_qos.keys()):
                jq = job_qos[qname]
                qos_parts.append(f"{qname}:r{jq['running']}p{jq['pending']}")
            seg += f" [{' '.join(qos_parts)}]"
        elif u.get("default_qos"):
            seg += f" qos:{u['default_qos']}"
        parts.append(seg)

    if "account" in data and data["account"]:
        a = data["account"]
        seg = f"{a['name']} fs:{a['fairshare']:.2f}"
        if a.get("running") or a.get("pending"):
            seg += f" (r:{a.get('running', 0)} p:{a.get('pending', 0)})"
        parts.append(seg)

    if "top_fs" in data and "low_fs" in data:
        top = data["top_fs"]
        low = data["low_fs"]
        parts.append(f"hi:{top['user']}({top['fairshare']:.2f}) lo:{low['user']}({low['fairshare']:.2f})")

    return " | ".join(parts)


def _safe_float(val: str) -> float:
    try:
        return float(val.strip())
    except (ValueError, AttributeError, TypeError):
        return 0.0


def _safe_int(val: str) -> int:
    try:
        return int(val.strip())
    except (ValueError, AttributeError, TypeError):
        return 0


# ── Main ────────────────────────────────────────────────────────────


def build_data(
    user: Optional[str] = None,
    account: Optional[str] = None,
    qos: Optional[str] = None,
) -> dict:
    """Collect all status data."""
    data = get_queue_counts(qos=qos)

    if user:
        data["user"] = get_user_info(user)
        if data["user"]:
            data["user"]["name"] = user

    if account:
        data["account"] = get_account_info(account)

    extremes = get_fairshare_extremes()
    data.update(extremes)

    return data


def main():
    parser = argparse.ArgumentParser(
        description="Compact Slurm priority & fairshare status for tmux/vim.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  slurm-monitor                       Cluster overview
  slurm-monitor -u $USER              Personal status with QOS and queue rank
  slurm-monitor -u $USER --color      With tmux color codes
  slurm-monitor -u $USER --json       Machine-readable JSON (includes QOS details)
  slurm-monitor -u $USER -q gpu       Filter by QOS name
  slurm-monitor --watch               Refresh every 5s
  slurm-monitor --long                Full one-liner with QOS breakdown

tmux.conf:
  set -g status-right '#(slurm-monitor -u $USER)'
  set -g status-interval 10
""",
    )
    parser.add_argument("-u", "--user", default=None,
                        help="Show personal fairshare and queue rank")
    parser.add_argument("-a", "--account", default=None,
                        help="Show account-level summary")
    parser.add_argument("--color", action="store_true",
                        help="Output tmux color codes (#[fg=...])")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON")
    parser.add_argument("--long", action="store_true",
                        help="Longer format with fairshare extremes")
    parser.add_argument("--watch", action="store_true",
                        help="Continuously refresh")
    parser.add_argument("-r", "--refresh", type=int, default=5,
                        help="Refresh interval in seconds (default: 5)")
    parser.add_argument("-q", "--qos", default=None,
                        help="Filter by QOS name")
    parser.add_argument("--max-width", type=int, default=0,
                        help="Truncate output to N characters")

    args = parser.parse_args()

    if not check_slurm_available():
        if args.json:
            print(json.dumps({"error": "slurm not found"}))
        else:
            print("slurm:err")
        sys.exit(1)

    if args.watch:
        try:
            while True:
                data = build_data(user=args.user, account=args.account, qos=args.qos)
                if args.json:
                    line = json.dumps(data, default=str)
                elif args.long:
                    line = format_long(data)
                else:
                    line = format_status(data, color=args.color, max_width=args.max_width)
                sys.stdout.write(f"\r\033[K{line}")
                sys.stdout.flush()
                time.sleep(args.refresh)
        except KeyboardInterrupt:
            sys.stdout.write("\n")
    else:
        data = build_data(user=args.user, account=args.account, qos=args.qos)
        if args.json:
            print(json.dumps(data, default=str))
        elif args.long:
            print(format_long(data))
        else:
            print(format_status(data, color=args.color, max_width=args.max_width))


if __name__ == "__main__":
    main()
