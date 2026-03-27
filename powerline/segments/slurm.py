"""Powerline segment for Slurm job status.

Shows running/pending jobs, fairshare score, and queue rank in your
powerline-enabled tmux status bar, vim statusline, or shell prompt.

Setup (tmux):
    Add to ~/.config/powerline/themes/tmux/default.json:
    {
        "segments": {
            "right": [{
                "function": "powerline.segments.slurm.slurm_status",
                "args": { "user": "myuser" }
            }]
        }
    }

Setup (vim):
    Add to ~/.config/powerline/themes/vim/default.json:
    {
        "segments": {
            "right": [{
                "function": "powerline.segments.slurm.slurm_status",
                "args": { "user": "myuser" }
            }]
        }
    }
"""

import os
import re


_DEFAULT_CACHE = "/tmp/slurm-monitor-{user}.cache"


def _read_cache(cache_file):
    """Read the first line of the cache file, stripping tmux color codes."""
    try:
        with open(cache_file) as f:
            line = f.readline().strip()
        if line:
            # Strip tmux color codes: #[fg=green], #[default], etc.
            return re.sub(r"#\[[^\]]*\]", "", line)
    except (OSError, IOError):
        pass
    return None


def _parse_status(text):
    """Parse a status string into components for highlight grouping.

    Input:  'R:5k P:25k fs:0.82 #3/25k qos:normal'
    Output: [('R:5k P:25k', None), ('fs:0.82', 0.82), ('#3/25k qos:normal', None)]
    """
    parts = []
    fs_value = None

    # Extract fairshare value if present
    fs_match = re.search(r"fs:(\d+\.\d+)", text)
    if fs_match:
        fs_value = float(fs_match.group(1))

    # Split around the fs: token for separate highlighting
    if fs_match:
        before = text[:fs_match.start()].strip()
        fs_part = fs_match.group(0)
        after = text[fs_match.end():].strip()
        if before:
            parts.append((before, None))
        parts.append((fs_part, fs_value))
        if after:
            parts.append((after, None))
    else:
        parts.append((text, None))

    return parts


def _fs_highlight(fs_value):
    """Return the appropriate highlight group for a fairshare value."""
    if fs_value is None:
        return "slurm"
    if fs_value >= 0.5:
        return "slurm:good"
    if fs_value >= 0.3:
        return "slurm:warning"
    return "slurm:critical"


def slurm_status(pl, user=None, cache_file=None):
    """Powerline segment: Slurm cluster status with fairshare.

    Args:
        pl: Powerline logger instance.
        user: Username to show personal fairshare/rank for.
        cache_file: Path to the cache file. Default: /tmp/slurm-monitor-$USER.cache
    """
    if cache_file is None:
        effective_user = user or os.environ.get("USER", "unknown")
        cache_file = _DEFAULT_CACHE.format(user=effective_user)

    text = _read_cache(cache_file)
    if not text:
        return None

    segments = []
    parts = _parse_status(text)

    for content, fs_value in parts:
        hl = _fs_highlight(fs_value)
        segments.append({
            "contents": content,
            "highlight_groups": [hl, "slurm"],
        })

    return segments or None
