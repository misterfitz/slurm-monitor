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
