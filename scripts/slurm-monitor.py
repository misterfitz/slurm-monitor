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
import os
import shutil
import subprocess
import sys
import time
from typing import Optional


_cluster: Optional[str] = None


def run_slurm(cmd: str) -> str | None:
    """Run a Slurm command and return stdout, or None on failure."""
    if _cluster:
        # Insert -M cluster after the command name for multi-cluster support
        parts = cmd.split(None, 1)
        cmd = f"{parts[0]} -M {_cluster}" + (f" {parts[1]}" if len(parts) > 1 else "")
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
    """Get the highest and lowest fairshare across accounts.

    Uses account-level rows (where User is empty) from sshare.
    Excludes accounts ending with 'bot'.
    """
    out = run_slurm(
        "sshare -a -P -h --format=Account,User,FairShare"
    )
    if not out:
        return {}

    accounts = []
    for line in out.split("\n"):
        parts = line.split("|")
        if len(parts) >= 3:
            account = parts[0].strip()
            user = parts[1].strip()
            # Account-level rows have an empty User field
            if not user and account and account != "(null)":
                if account.lower().endswith("bot"):
                    continue
                fs = _safe_float(parts[2])
                accounts.append({"account": account, "fairshare": fs})

    if not accounts:
        return {}

    top = max(accounts, key=lambda x: x["fairshare"])
    low = min(accounts, key=lambda x: x["fairshare"])
    return {"top_fs": top, "low_fs": low}


def get_pending_details(user: str) -> list:
    """Get pending job details including estimated start time and reason.

    Returns [{"job_id": "123", "name": "train", "reason": "Priority",
              "start_time": "2025-01-15T12:00:00"}]
    """
    out = run_slurm(
        f"squeue -u {user} -h -t PENDING "
        f"-o '%i|%j|%r|%S' --sort=-p"
    )
    if not out:
        return []

    jobs = []
    for line in out.split("\n"):
        parts = line.strip().split("|")
        if len(parts) >= 4:
            start = parts[3].strip()
            if start in ("N/A", "n/a", ""):
                start = None
            jobs.append({
                "job_id": parts[0].strip(),
                "name": parts[1].strip(),
                "reason": parts[2].strip(),
                "start_time": start,
            })

    return jobs


def get_gpu_usage(user: str) -> dict:
    """Get GPU allocation info for a user's running jobs.

    Returns {"allocated": 4, "jobs": [{"job_id": "123", "name": "train", "gpus": 2}]}
    """
    out = run_slurm(
        f"squeue -u {user} -h -t RUNNING "
        f"-o '%i|%j|%b' --sort=-p"
    )
    if not out:
        return {"allocated": 0, "jobs": []}

    total_gpus = 0
    jobs = []
    for line in out.split("\n"):
        parts = line.strip().split("|")
        if len(parts) >= 3:
            gres = parts[2].strip()
            gpus = _parse_gres_gpus(gres)
            if gpus > 0:
                jobs.append({
                    "job_id": parts[0].strip(),
                    "name": parts[1].strip(),
                    "gpus": gpus,
                })
                total_gpus += gpus

    return {"allocated": total_gpus, "jobs": jobs}


def _parse_gres_gpus(gres: str) -> int:
    """Parse GPU count from GRES string like 'gpu:4' or 'gpu:a100:2'."""
    if not gres or gres in ("(null)", "N/A"):
        return 0
    import re
    match = re.search(r"gpu(?::[^:]+)?:(\d+)", gres)
    if match:
        return int(match.group(1))
    if gres == "gpu" or gres.startswith("gpu:"):
        # bare "gpu" or "gpu:type" without count means 1
        parts = gres.split(":")
        if len(parts) <= 2 and not parts[-1].isdigit():
            return 1
    return 0


def get_job_history(user: str, hours: int = 24) -> dict:
    """Get job completion history over the last N hours for sparkline.

    Returns {"buckets": [{"hour": 0, "completed": 5, "failed": 1}, ...],
             "total_completed": 40, "total_failed": 3}
    """
    out = run_slurm(
        f"sacct -u {user} -X -n -P "
        f"--starttime=now-{hours}hours "
        f"--format=State,End"
    )
    if not out:
        return {"buckets": [], "total_completed": 0, "total_failed": 0}

    from datetime import datetime
    now = datetime.now()
    buckets = [{"hour": i, "completed": 0, "failed": 0} for i in range(hours)]
    total_completed = 0
    total_failed = 0
    failed_states = {"FAILED", "TIMEOUT", "OOM", "NODE_FAIL", "CANCELLED", "PREEMPTED"}

    for line in out.split("\n"):
        parts = line.split("|")
        if len(parts) < 2:
            continue
        state = parts[0].strip().split(" ")[0].upper()
        end_str = parts[1].strip()
        if not end_str or end_str in ("Unknown", "None", ""):
            continue

        try:
            end_time = datetime.strptime(end_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue

        delta = now - end_time
        hours_ago = int(delta.total_seconds() / 3600)
        if 0 <= hours_ago < hours:
            bucket_idx = hours - 1 - hours_ago  # 0=oldest, hours-1=most recent
            if state == "COMPLETED":
                buckets[bucket_idx]["completed"] += 1
                total_completed += 1
            elif state in failed_states:
                buckets[bucket_idx]["failed"] += 1
                total_failed += 1

    return {
        "buckets": buckets,
        "total_completed": total_completed,
        "total_failed": total_failed,
    }


def make_sparkline(buckets: list, key: str = "completed") -> str:
    """Create a sparkline string from bucket data.

    Uses Unicode block characters: ▁▂▃▄▅▆▇█
    """
    chars = "▁▁▂▃▄▅▆▇█"
    values = [b.get(key, 0) for b in buckets]
    if not values:
        return ""
    max_val = max(values) or 1
    return "".join(chars[min(int(v / max_val * 8), 8)] for v in values)


def get_usage_budget(user: str, account: Optional[str] = None) -> dict | None:
    """Get usage budget info from sreport — hours used this month.

    Returns {"account": "physics", "used_hours": 1234.5, "user_hours": 500.2}
    """
    # Get account from sshare if not provided
    if not account:
        out = run_slurm(
            f"sshare -u {user} -U -P -h --format=Account,User"
        )
        if out:
            for line in out.split("\n"):
                parts = line.split("|")
                if len(parts) >= 2 and parts[1].strip() == user:
                    account = parts[0].strip()
                    break
    if not account:
        return None

    # Account usage this month
    out = run_slurm(
        f"sreport cluster AccountUtilizationByUser account={account} "
        f"-t Hours -P -n --parsable2 start=month"
    )
    if not out:
        return None

    result = {"account": account, "used_hours": 0, "user_hours": 0}
    for line in out.split("\n"):
        parts = line.split("|")
        if len(parts) < 4:
            continue
        login = parts[1].strip()
        try:
            hours = float(parts[3].strip())
        except (ValueError, IndexError):
            continue
        if not login or login == account:
            result["used_hours"] += hours
        if login == user:
            result["user_hours"] = hours

    return result if result["used_hours"] > 0 else None


def get_failed_jobs(user: str, since_minutes: int = 60) -> list:
    """Get recently failed/timed-out/OOM jobs for a user via sacct.

    Returns a list of dicts: [{"job_id": "123", "name": "train", "state": "FAILED",
                                "exit_code": "1:0", "end_time": "2025-01-15T10:30:00"}]
    """
    out = run_slurm(
        f"sacct -u {user} -X -n -P "
        f"--starttime=now-{since_minutes}minutes "
        f"--state=FAILED,TIMEOUT,CANCELLED,OOM,NODE_FAIL,PREEMPTED "
        f"--format=JobID,JobName%30,State,ExitCode,End"
    )
    if not out:
        return []

    jobs = []
    for line in out.split("\n"):
        parts = line.split("|")
        if len(parts) >= 5:
            state = parts[2].strip()
            # Skip jobs cancelled by user themselves (CANCELLED by 0 = system)
            if state.startswith("CANCELLED by") and "by 0" not in state:
                continue
            jobs.append({
                "job_id": parts[0].strip(),
                "name": parts[1].strip(),
                "state": state.split(" ")[0],  # normalize "CANCELLED by ..." to "CANCELLED"
                "exit_code": parts[3].strip(),
                "end_time": parts[4].strip(),
            })

    return jobs


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

    gpu = data.get("gpu")
    if gpu and gpu.get("allocated", 0) > 0:
        g = gpu["allocated"]
        if color:
            parts.append(f"#[fg=cyan]gpu:{g}#[default]")
        else:
            parts.append(f"gpu:{g}")

    failed = data.get("failed_jobs", [])
    if failed:
        count = len(failed)
        if color:
            parts.append(f"#[fg=red]!{count}#[default]")
        else:
            parts.append(f"!{count}")

    history = data.get("history")
    if history and (history["total_completed"] > 0 or history["total_failed"] > 0):
        spark = make_sparkline(history["buckets"], "completed")
        if spark.strip():
            parts.append(spark)

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

    gpu = data.get("gpu")
    if gpu and gpu.get("allocated", 0) > 0:
        parts.append(f"gpu:{gpu['allocated']}")

    failed = data.get("failed_jobs", [])
    if failed:
        parts.append(f"FAIL:{len(failed)}")

    budget = data.get("budget")
    if budget:
        parts.append(f"used:{budget['user_hours']:.0f}h/{budget['used_hours']:.0f}h")

    history = data.get("history")
    if history and (history["total_completed"] > 0 or history["total_failed"] > 0):
        spark = make_sparkline(history["buckets"], "completed")
        if spark.strip():
            parts.append(spark)

    if "top_fs" in data and "low_fs" in data:
        top = data["top_fs"]
        low = data["low_fs"]
        parts.append(f"hi:{top['account']}({top['fairshare']:.2f}) lo:{low['account']}({low['fairshare']:.2f})")

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
    cluster: Optional[str] = None,
) -> dict:
    """Collect all status data."""
    data = get_queue_counts(qos=qos)

    if cluster:
        data["cluster"] = cluster

    if user:
        data["user"] = get_user_info(user)
        if data["user"]:
            data["user"]["name"] = user

        failed = get_failed_jobs(user)
        if failed:
            data["failed_jobs"] = failed

        pending = get_pending_details(user)
        if pending:
            data["pending_details"] = pending

        gpu = get_gpu_usage(user)
        if gpu["allocated"] > 0:
            data["gpu"] = gpu

        history = get_job_history(user)
        if history["total_completed"] > 0 or history["total_failed"] > 0:
            data["history"] = history

        user_account = data["user"].get("account") if data.get("user") else None
        budget = get_usage_budget(user, account=user_account)
        if budget:
            data["budget"] = budget

    if account:
        data["account"] = get_account_info(account)

    extremes = get_fairshare_extremes()
    data.update(extremes)

    return data


def _check_alerts(
    data: dict,
    last_fail_count: int,
    alert_cmd: Optional[str] = None,
    bell: bool = False,
) -> int:
    """Check for new failures and fire alerts. Returns updated fail count."""
    failed = data.get("failed_jobs", [])
    count = len(failed)
    if count <= last_fail_count:
        return count

    new_count = count - last_fail_count
    latest = failed[0] if failed else {}
    name = latest.get("name", "?")
    state = latest.get("state", "FAILED")

    if new_count == 1:
        msg = f"Slurm: job '{name}' {state}"
    else:
        msg = f"Slurm: {new_count} new failures (latest: {name} {state})"

    if bell:
        sys.stderr.write("\a")
        sys.stderr.flush()

    if alert_cmd:
        env = os.environ.copy()
        env["SLURM_ALERT_MESSAGE"] = msg
        env["SLURM_ALERT_COUNT"] = str(new_count)
        env["SLURM_ALERT_JOB_NAME"] = name
        env["SLURM_ALERT_JOB_STATE"] = state
        env["SLURM_ALERT_JOB_ID"] = latest.get("job_id", "")
        try:
            subprocess.Popen(
                alert_cmd, shell=True, env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            pass

    return count


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
    parser.add_argument("-M", "--cluster", default=None,
                        help="Target a specific Slurm cluster")
    parser.add_argument("--alert-cmd", default=None,
                        help="Command to run on new failures (e.g. notify-send, curl)")
    parser.add_argument("--bell", action="store_true",
                        help="Ring terminal bell on new failures")

    args = parser.parse_args()

    global _cluster
    if args.cluster:
        _cluster = args.cluster

    if not check_slurm_available():
        if args.json:
            print(json.dumps({"error": "slurm not found"}))
        else:
            print("slurm:err")
        sys.exit(1)

    last_fail_count = 0
    alert_cmd = args.alert_cmd or os.environ.get("SLURM_MONITOR_ALERT_CMD")

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
                last_fail_count = _check_alerts(
                    data, last_fail_count, alert_cmd, bell=args.bell,
                )
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
        _check_alerts(data, 0, alert_cmd, bell=args.bell)


if __name__ == "__main__":
    main()
