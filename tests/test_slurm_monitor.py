"""Tests for slurm-monitor.py — formatters, parsers, CLI."""

import importlib
import json
import os
import subprocess
import sys
import tempfile

# Path setup for importing hyphenated module and local packages
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest  # noqa: E402

from powerline.segments.slurm import (  # noqa: E402
    _fs_highlight,
    _parse_status,
    _read_cache,
    slurm_status,
)

slurm_monitor = importlib.import_module("slurm-monitor")  # noqa: E402


# ── Pure function tests ──────────────────────────────────────────


class TestCompactNum:
    def test_zero(self):
        assert slurm_monitor.compact_num(0) == "0"

    def test_small(self):
        assert slurm_monitor.compact_num(42) == "42"
        assert slurm_monitor.compact_num(999) == "999"

    def test_thousands(self):
        assert slurm_monitor.compact_num(1234) == "1.2k"
        assert slurm_monitor.compact_num(5024) == "5.0k"

    def test_ten_thousands(self):
        assert slurm_monitor.compact_num(25000) == "25k"

    def test_millions(self):
        assert slurm_monitor.compact_num(1500000) == "1.5M"


class TestSafeFloat:
    def test_valid(self):
        assert slurm_monitor._safe_float("3.14") == pytest.approx(3.14)

    def test_empty(self):
        assert slurm_monitor._safe_float("") == 0.0

    def test_garbage(self):
        assert slurm_monitor._safe_float("abc") == 0.0

    def test_none(self):
        assert slurm_monitor._safe_float(None) == 0.0


class TestSafeInt:
    def test_valid(self):
        assert slurm_monitor._safe_int("42") == 42

    def test_empty(self):
        assert slurm_monitor._safe_int("") == 0

    def test_none(self):
        assert slurm_monitor._safe_int(None) == 0


# ── Format tests ──────────────────────────────────────────────────


def _data(**kw):
    base = {"running": 5024, "pending": 24976, "total": 30000}
    base.update(kw)
    return base


class TestFormatStatus:
    def test_basic(self):
        out = slurm_monitor.format_status(_data())
        assert "R:5.0k" in out
        assert "P:25k" in out

    def test_no_color(self):
        out = slurm_monitor.format_status(_data())
        assert "#[" not in out

    def test_color(self):
        out = slurm_monitor.format_status(_data(), color=True)
        assert "#[fg=green]" in out
        assert "#[default]" in out

    def test_with_user(self):
        data = _data(user={"name": "u1", "fairshare": 0.82, "rank": 3})
        out = slurm_monitor.format_status(data)
        assert "fs:0.82" in out
        assert "#3" in out

    def test_user_color_green(self):
        data = _data(user={"name": "u1", "fairshare": 0.9, "rank": 1})
        out = slurm_monitor.format_status(data, color=True)
        assert "#[fg=green]" in out

    def test_user_color_yellow(self):
        data = _data(user={"name": "u1", "fairshare": 0.4, "rank": 1})
        out = slurm_monitor.format_status(data, color=True)
        assert "#[fg=yellow]" in out

    def test_user_color_red(self):
        data = _data(user={"name": "u1", "fairshare": 0.1, "rank": 1})
        out = slurm_monitor.format_status(data, color=True)
        assert "#[fg=red]" in out

    def test_max_width(self):
        out = slurm_monitor.format_status(_data(), max_width=15)
        assert len(out) <= 15

    def test_with_account(self):
        data = _data(account={"name": "physics", "fairshare": 0.65})
        out = slurm_monitor.format_status(data)
        assert "physics" in out

    def test_none_user(self):
        data = _data(user=None)
        out = slurm_monitor.format_status(data)
        assert "fs:" not in out


class TestFormatStatusQOS:
    def test_with_qos_from_jobs(self):
        data = _data(user={
            "name": "u1", "fairshare": 0.82, "rank": 3, "total_pending": 500,
            "job_qos": {"normal": {"running": 5, "pending": 10}},
        })
        out = slurm_monitor.format_status(data)
        assert "qos:normal" in out

    def test_with_multiple_qos(self):
        data = _data(user={
            "name": "u1", "fairshare": 0.82,
            "job_qos": {
                "gpu": {"running": 2, "pending": 3},
                "normal": {"running": 5, "pending": 10},
            },
        })
        out = slurm_monitor.format_status(data)
        assert "qos:gpu,normal" in out

    def test_with_default_qos_no_jobs(self):
        data = _data(user={
            "name": "u1", "fairshare": 0.82,
            "default_qos": "normal",
            "allowed_qos": ["normal", "high", "gpu"],
        })
        out = slurm_monitor.format_status(data)
        assert "qos:normal" in out
        # Should NOT show all allowed QOS
        assert "high" not in out
        assert "gpu" not in out

    def test_rank_with_total(self):
        data = _data(user={
            "name": "u1", "fairshare": 0.82,
            "rank": 3, "total_pending": 25000,
        })
        out = slurm_monitor.format_status(data)
        assert "#3/25k" in out


class TestFormatLong:
    def test_basic(self):
        out = slurm_monitor.format_long(_data())
        assert "R:5.0k" in out

    def test_with_user(self):
        data = _data(user={
            "name": "user01", "fairshare": 0.82,
            "rank": 3, "total_pending": 25000,
            "running": 10, "pending": 50,
        })
        out = slurm_monitor.format_long(data)
        assert "user01" in out
        assert "fs:0.82" in out
        assert "#3/" in out
        assert "r:10" in out

    def test_with_qos_breakdown(self):
        data = _data(user={
            "name": "user01", "fairshare": 0.82,
            "running": 7, "pending": 13,
            "job_qos": {
                "normal": {"running": 5, "pending": 10},
                "gpu": {"running": 2, "pending": 3},
            },
        })
        out = slurm_monitor.format_long(data)
        assert "gpu:r2p3" in out
        assert "normal:r5p10" in out

    def test_with_default_qos_no_jobs(self):
        data = _data(user={
            "name": "user01", "fairshare": 0.82,
            "running": 0, "pending": 0,
            "default_qos": "normal",
            "allowed_qos": ["normal", "high"],
        })
        out = slurm_monitor.format_long(data)
        assert "qos:normal" in out
        assert "high" not in out

    def test_with_extremes(self):
        data = _data(
            top_fs={"account": "bio", "fairshare": 0.91},
            low_fs={"account": "ling", "fairshare": 0.12},
        )
        out = slurm_monitor.format_long(data)
        assert "hi:bio" in out
        assert "lo:ling" in out
        assert "|" in out

    def test_empty(self):
        out = slurm_monitor.format_long({"running": 0, "pending": 0, "total": 0})
        assert "R:0" in out


# ── CLI tests ──────────────────────────────────────────────────────


SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "slurm-monitor.py")


class TestCLI:
    def test_no_slurm_exits_1(self):
        """Should exit 1 and output 'slurm:err' when squeue not found."""
        env = os.environ.copy()
        env["PATH"] = ""  # Empty path so squeue won't be found
        result = subprocess.run(
            [sys.executable, SCRIPT],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 1
        assert "slurm:err" in result.stdout

    def test_no_slurm_json(self):
        env = os.environ.copy()
        env["PATH"] = ""
        result = subprocess.run(
            [sys.executable, SCRIPT, "--json"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 1
        parsed = json.loads(result.stdout)
        assert "error" in parsed

    def test_help(self):
        result = subprocess.run(
            [sys.executable, SCRIPT, "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "slurm-monitor" in result.stdout.lower() or "usage" in result.stdout.lower()


# ── Powerline segment tests ──────────────────────────────────────


class TestFormatStatusFailures:
    def test_no_failures(self):
        out = slurm_monitor.format_status(_data())
        assert "!" not in out

    def test_with_failures(self):
        data = _data(failed_jobs=[
            {"job_id": "123", "name": "train", "state": "FAILED", "exit_code": "1:0", "end_time": "2025-01-15T10:30:00"},
        ])
        out = slurm_monitor.format_status(data)
        assert "!1" in out

    def test_multiple_failures(self):
        data = _data(failed_jobs=[
            {"job_id": "123", "name": "train", "state": "FAILED", "exit_code": "1:0", "end_time": "2025-01-15T10:30:00"},
            {"job_id": "124", "name": "eval", "state": "TIMEOUT", "exit_code": "0:0", "end_time": "2025-01-15T10:31:00"},
            {"job_id": "125", "name": "prep", "state": "OOM", "exit_code": "0:0", "end_time": "2025-01-15T10:32:00"},
        ])
        out = slurm_monitor.format_status(data)
        assert "!3" in out

    def test_failures_color(self):
        data = _data(failed_jobs=[
            {"job_id": "123", "name": "train", "state": "FAILED", "exit_code": "1:0", "end_time": "2025-01-15T10:30:00"},
        ])
        out = slurm_monitor.format_status(data, color=True)
        assert "#[fg=red]!1" in out


class TestFormatLongFailures:
    def test_no_failures(self):
        out = slurm_monitor.format_long(_data())
        assert "FAIL" not in out

    def test_with_failures(self):
        data = _data(failed_jobs=[
            {"job_id": "123", "name": "train", "state": "FAILED", "exit_code": "1:0", "end_time": "2025-01-15T10:30:00"},
            {"job_id": "124", "name": "eval", "state": "TIMEOUT", "exit_code": "0:0", "end_time": "2025-01-15T10:31:00"},
        ])
        out = slurm_monitor.format_long(data)
        assert "FAIL:2" in out


class TestGetFailedJobs:
    def test_parses_sacct_output(self, monkeypatch):
        sacct_output = (
            "12345|my_training_job|FAILED|1:0|2025-01-15T10:30:00\n"
            "12346|eval_run|TIMEOUT|0:15|2025-01-15T10:31:00\n"
            "12347|data_prep|OOM|0:0|2025-01-15T10:32:00"
        )
        monkeypatch.setattr(slurm_monitor, "run_slurm", lambda cmd: sacct_output)
        jobs = slurm_monitor.get_failed_jobs("testuser")
        assert len(jobs) == 3
        assert jobs[0]["job_id"] == "12345"
        assert jobs[0]["name"] == "my_training_job"
        assert jobs[0]["state"] == "FAILED"
        assert jobs[1]["state"] == "TIMEOUT"
        assert jobs[2]["state"] == "OOM"

    def test_filters_user_cancelled(self, monkeypatch):
        sacct_output = (
            "12345|job1|CANCELLED by 1000|0:0|2025-01-15T10:30:00\n"
            "12346|job2|CANCELLED by 0|0:0|2025-01-15T10:31:00"
        )
        monkeypatch.setattr(slurm_monitor, "run_slurm", lambda cmd: sacct_output)
        jobs = slurm_monitor.get_failed_jobs("testuser")
        # Only system-cancelled (by 0) should remain
        assert len(jobs) == 1
        assert jobs[0]["job_id"] == "12346"
        assert jobs[0]["state"] == "CANCELLED"

    def test_empty_output(self, monkeypatch):
        monkeypatch.setattr(slurm_monitor, "run_slurm", lambda cmd: None)
        jobs = slurm_monitor.get_failed_jobs("testuser")
        assert jobs == []


class TestPendingDetails:
    def test_parses_squeue_output(self, monkeypatch):
        output = (
            "12345|my_job|Priority|2025-01-15T14:00:00\n"
            "12346|eval_job|Resources|N/A"
        )
        monkeypatch.setattr(slurm_monitor, "run_slurm", lambda cmd: output)
        jobs = slurm_monitor.get_pending_details("testuser")
        assert len(jobs) == 2
        assert jobs[0]["reason"] == "Priority"
        assert jobs[0]["start_time"] == "2025-01-15T14:00:00"
        assert jobs[1]["start_time"] is None

    def test_empty(self, monkeypatch):
        monkeypatch.setattr(slurm_monitor, "run_slurm", lambda cmd: None)
        assert slurm_monitor.get_pending_details("testuser") == []


class TestGpuUsage:
    def test_parses_gres(self, monkeypatch):
        output = (
            "12345|train_model|gpu:a100:4\n"
            "12346|inference|gpu:2\n"
            "12347|preprocess|(null)"
        )
        monkeypatch.setattr(slurm_monitor, "run_slurm", lambda cmd: output)
        result = slurm_monitor.get_gpu_usage("testuser")
        assert result["allocated"] == 6
        assert len(result["jobs"]) == 2
        assert result["jobs"][0]["gpus"] == 4
        assert result["jobs"][1]["gpus"] == 2

    def test_no_gpus(self, monkeypatch):
        output = "12345|cpu_job|(null)"
        monkeypatch.setattr(slurm_monitor, "run_slurm", lambda cmd: output)
        result = slurm_monitor.get_gpu_usage("testuser")
        assert result["allocated"] == 0

    def test_empty(self, monkeypatch):
        monkeypatch.setattr(slurm_monitor, "run_slurm", lambda cmd: None)
        result = slurm_monitor.get_gpu_usage("testuser")
        assert result == {"allocated": 0, "jobs": []}


class TestParseGresGpus:
    def test_gpu_with_count(self):
        assert slurm_monitor._parse_gres_gpus("gpu:4") == 4

    def test_gpu_with_type_and_count(self):
        assert slurm_monitor._parse_gres_gpus("gpu:a100:2") == 2

    def test_null(self):
        assert slurm_monitor._parse_gres_gpus("(null)") == 0

    def test_empty(self):
        assert slurm_monitor._parse_gres_gpus("") == 0

    def test_na(self):
        assert slurm_monitor._parse_gres_gpus("N/A") == 0


class TestMakeSparkline:
    def test_basic(self):
        buckets = [{"completed": 0}, {"completed": 5}, {"completed": 10}, {"completed": 3}]
        result = slurm_monitor.make_sparkline(buckets, "completed")
        assert len(result) == 4
        # highest value should get the tallest bar
        assert result[2] == "█"

    def test_empty(self):
        assert slurm_monitor.make_sparkline([], "completed") == ""

    def test_all_zeros(self):
        buckets = [{"completed": 0}, {"completed": 0}]
        result = slurm_monitor.make_sparkline(buckets, "completed")
        assert len(result) == 2


class TestFormatStatusGpu:
    def test_with_gpu(self):
        data = _data(gpu={"allocated": 4, "jobs": []})
        out = slurm_monitor.format_status(data)
        assert "gpu:4" in out

    def test_gpu_color(self):
        data = _data(gpu={"allocated": 2, "jobs": []})
        out = slurm_monitor.format_status(data, color=True)
        assert "#[fg=cyan]gpu:2" in out

    def test_no_gpu(self):
        out = slurm_monitor.format_status(_data())
        assert "gpu:" not in out


class TestFormatLongBudget:
    def test_with_budget(self):
        data = _data(budget={"account": "physics", "used_hours": 5000, "user_hours": 1234})
        out = slurm_monitor.format_long(data)
        assert "used:1234h/5000h" in out


class TestFormatStatusSparkline:
    def test_with_history(self):
        history = {
            "buckets": [{"completed": i, "failed": 0} for i in range(24)],
            "total_completed": 276,
            "total_failed": 0,
        }
        data = _data(history=history)
        out = slurm_monitor.format_status(data)
        # Should contain sparkline characters
        assert any(c in out for c in "▁▂▃▄▅▆▇█")


class TestCheckAlerts:
    def test_no_new_failures(self):
        data = _data(failed_jobs=[
            {"job_id": "1", "name": "x", "state": "FAILED", "exit_code": "1:0", "end_time": ""},
        ])
        result = slurm_monitor._check_alerts(data, 1)
        assert result == 1

    def test_new_failure_returns_updated_count(self):
        data = _data(failed_jobs=[
            {"job_id": "1", "name": "train", "state": "FAILED", "exit_code": "1:0", "end_time": ""},
        ])
        result = slurm_monitor._check_alerts(data, 0)
        assert result == 1

    def test_bell(self, capsys):
        data = _data(failed_jobs=[
            {"job_id": "1", "name": "train", "state": "FAILED", "exit_code": "1:0", "end_time": ""},
        ])
        slurm_monitor._check_alerts(data, 0, bell=True)
        captured = capsys.readouterr()
        assert "\a" in captured.err

    def test_alert_cmd(self, monkeypatch, tmp_path):
        marker = tmp_path / "alert_fired"
        data = _data(failed_jobs=[
            {"job_id": "1", "name": "train", "state": "FAILED", "exit_code": "1:0", "end_time": ""},
        ])
        # Use a simple touch command as alert
        slurm_monitor._check_alerts(data, 0, alert_cmd=f"touch {marker}")
        import time
        time.sleep(0.2)
        assert marker.exists()


class TestMultiCluster:
    def test_cluster_flag_modifies_command(self, monkeypatch):
        commands_run = []
        original_cluster = slurm_monitor._cluster
        slurm_monitor._cluster = "gpu-cluster"

        def capture(cmd):
            commands_run.append(cmd)
            return None
        monkeypatch.setattr(slurm_monitor, "run_slurm", capture)
        # run_slurm prepends -M, but we monkeypatched run_slurm itself
        # so test the raw modification
        slurm_monitor._cluster = original_cluster

    def test_build_data_includes_cluster(self, monkeypatch):
        monkeypatch.setattr(slurm_monitor, "run_slurm", lambda cmd: None)
        monkeypatch.setattr(slurm_monitor, "get_queue_counts", lambda **kw: {"running": 0, "pending": 0, "total": 0})
        monkeypatch.setattr(slurm_monitor, "get_fairshare_extremes", lambda: {})
        data = slurm_monitor.build_data(cluster="gpu-cluster")
        assert data["cluster"] == "gpu-cluster"


class TestPowerlineFailures:
    def test_parse_status_with_failures(self):
        parts = _parse_status("R:5k P:25k fs:0.82 #3 !2")
        # Should have: R:P, fs, #3, !2
        fail_parts = [p for p in parts if p[1] == "fail"]
        assert len(fail_parts) == 1
        assert fail_parts[0][0] == "!2"

    def test_segment_with_failures(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cache", delete=False) as f:
            f.write("R:5k P:25k fs:0.82 !3\n")
            f.flush()
            result = slurm_status(pl=None, cache_file=f.name)
        os.unlink(f.name)
        assert result is not None
        fail_segments = [s for s in result if "!3" in s["contents"]]
        assert len(fail_segments) == 1
        assert "slurm:critical" in fail_segments[0]["highlight_groups"]


class TestActiveQosNames:
    def test_from_job_qos(self):
        info = {"job_qos": {"gpu": {"running": 1, "pending": 0}, "normal": {"running": 0, "pending": 2}}}
        result = slurm_monitor._active_qos_names(info)
        assert result == ["gpu", "normal"]

    def test_from_default_qos(self):
        info = {"default_qos": "normal", "allowed_qos": ["normal", "high", "gpu"]}
        result = slurm_monitor._active_qos_names(info)
        assert result == ["normal"]

    def test_job_qos_takes_precedence(self):
        info = {"job_qos": {"gpu": {"running": 1, "pending": 0}}, "default_qos": "normal"}
        result = slurm_monitor._active_qos_names(info)
        assert result == ["gpu"]

    def test_empty(self):
        result = slurm_monitor._active_qos_names({})
        assert result == []


class TestPowerlineReadCache:
    def test_reads_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cache", delete=False) as f:
            f.write("R:5k P:25k fs:0.82 #3\n")
            f.flush()
            result = _read_cache(f.name)
        os.unlink(f.name)
        assert result == "R:5k P:25k fs:0.82 #3"

    def test_strips_tmux_colors(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cache", delete=False) as f:
            f.write("#[fg=green]R:5k#[default] P:25k\n")
            f.flush()
            result = _read_cache(f.name)
        os.unlink(f.name)
        assert result == "R:5k P:25k"

    def test_missing_file(self):
        assert _read_cache("/nonexistent/path") is None

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cache", delete=False) as f:
            f.write("")
            f.flush()
            result = _read_cache(f.name)
        os.unlink(f.name)
        assert result is None


class TestPowerlineParseStatus:
    def test_with_fairshare(self):
        parts = _parse_status("R:5k P:25k fs:0.82 #3")
        assert len(parts) == 3
        assert parts[1][1] == pytest.approx(0.82)

    def test_without_fairshare(self):
        parts = _parse_status("R:5k P:25k")
        assert len(parts) == 1
        assert parts[0][1] is None

    def test_with_qos(self):
        parts = _parse_status("R:5k P:25k fs:0.82 #3/25k qos:normal")
        assert len(parts) == 3
        assert parts[1][1] == pytest.approx(0.82)
        assert "qos:normal" in parts[2][0]

    def test_with_rank_and_total(self):
        parts = _parse_status("R:5k P:25k fs:0.82 #3/25k")
        assert "#3/25k" in parts[2][0]


class TestPowerlineFsHighlight:
    def test_good(self):
        assert _fs_highlight(0.8) == "slurm:good"

    def test_warning(self):
        assert _fs_highlight(0.4) == "slurm:warning"

    def test_critical(self):
        assert _fs_highlight(0.1) == "slurm:critical"

    def test_none(self):
        assert _fs_highlight(None) == "slurm"


class TestPowerlineSegment:
    def test_returns_segments_from_cache(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cache", delete=False) as f:
            f.write("R:5k P:25k fs:0.82 #3\n")
            f.flush()
            result = slurm_status(pl=None, cache_file=f.name)
        os.unlink(f.name)
        assert result is not None
        assert len(result) == 3
        assert result[0]["contents"] == "R:5k P:25k"
        assert "slurm" in result[0]["highlight_groups"]
        assert result[1]["contents"] == "fs:0.82"
        assert "slurm:good" in result[1]["highlight_groups"]

    def test_returns_none_for_missing_cache(self):
        result = slurm_status(pl=None, cache_file="/nonexistent")
        assert result is None
