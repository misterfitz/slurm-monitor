# slurm-monitor

[![Tests](https://github.com/misterfitz/slurm-monitor/actions/workflows/test.yml/badge.svg)](https://github.com/misterfitz/slurm-monitor/actions/workflows/test.yml)
[![Slurm Integration](https://github.com/misterfitz/slurm-monitor/actions/workflows/slurm-integration.yml/badge.svg)](https://github.com/misterfitz/slurm-monitor/actions/workflows/slurm-integration.yml)

Always-visible Slurm job status in your tmux status bar and Vim/Neovim statusline. See running/pending jobs, fairshare, queue rank, GPU usage, job failures, and a 24-hour sparkline — without leaving your editor. Press a key to pop up the full dashboard.

Works with **tmux** (TPM + powerline), **Vim 9+**, **Neovim 0.9+** (lualine, native statusline, heirline, feline), **LazyVim**, and **powerline**. Tested against Slurm 24.11 and 25.05.

![demo](https://raw.githubusercontent.com/misterfitz/slurm-monitor/main/demo/priority-demo.gif)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ 0:vim  1:bash          R:4.8k P:25k fs:0.73 #42/25k qos:normal gpu:7 !3 ▁▃▅█▂▁│
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  your code here              ┌─── prefix+S ──────────────────────┐              │
│                              │  Slurm Cluster Status              │              │
│                              │  Running   4.8k  ███░░░░░░░░░░░░░ │              │
│                              │  Pending    25k  ████████████████░ │              │
│                              │                                    │              │
│                              │  user01                            │              │
│                              │  Fairshare  0.7284  ██████████████ │              │
│                              │  Queue Pos  #42 of 25k (0.2%)     │              │
│                              │  Your Jobs  11 running, 17 pending │              │
│                              │                                    │              │
│                              │  GPU Allocation:  7 GPUs           │              │
│                              │    train_gpt        4 GPUs  200101 │              │
│                              │    finetune_bert    2 GPUs  200102 │              │
│                              │                                    │              │
│                              │  Recent Failures (3)               │              │
│                              │    FAILED    train_gpt_large  1:0  │              │
│                              │    TIMEOUT   eval_checkpoint  0:15 │              │
│                              │                                    │              │
│                              │  24h Job History  40 done  3 fail  │              │
│                              │  ▁▃▅▆█▇▅▃▂▁▃▅▇█▆▅▃▂▁▂▃▅▇          │              │
│                              └────────────────────────────────────┘              │
│                                                                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│ NORMAL      statusline        R:4.8k P:25k fs:0.73 #42/25k gpu:7 !3 ▁▃▅█▂▁    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## What it shows

```
R:4.8k P:25k fs:0.73 #42/25k qos:normal gpu:7 !3 ▁▃▅█▂▁
│      │      │       │       │          │     │   └── 24h job completion sparkline
│      │      │       │       │          │     └────── 3 recent job failures
│      │      │       │       │          └──────────── 7 GPUs allocated
│      │      │       │       └─────────────────────── Active QOS
│      │      │       └─────────────────────────────── #42 of 25k in queue
│      │      └─────────────────────────────────────── Your fairshare score
│      └────────────────────────────────────────────── 25,000 pending jobs cluster-wide
└───────────────────────────────────────────────────── 4,823 running jobs cluster-wide
```

## Features

- **Job status** — running/pending counts, cluster-wide and per-user
- **Fairshare score** — color-coded (green/yellow/red)
- **Queue rank** — your best pending job's position
- **QOS breakdown** — per-QOS running/pending counts
- **GPU tracking** — allocated GPUs per job
- **Failure detection** — recent FAILED, TIMEOUT, OOM, NODE_FAIL jobs via `sacct`
- **Failure alerts** — optional popup in tmux, Vim, Neovim; webhook for Slack/email/ntfy.sh
- **Job history sparkline** — 24-hour completion/failure trend
- **Pending reasons** — why jobs are stuck (Priority, Resources, QOSMaxJobsPerUser)
- **Estimated start time** — ETA for pending jobs from `squeue --start`
- **Usage budget** — monthly CPU-hours consumed (you vs. account) via `sreport`
- **Multi-cluster** — target a specific cluster with `-M`
- **Terminal bell** — `\a` alert on failures

## Install

### tmux (via TPM)

```bash
# ~/.tmux.conf
set -g @plugin 'misterfitz/slurm-monitor'
set -g @slurm-monitor-user "$USER"
set -g @slurm-monitor-color "on"
```

Then `prefix + I` to install. Press `prefix + S` to open the detail popup.

### tmux (manual)

```bash
git clone https://github.com/misterfitz/slurm-monitor ~/.tmux/plugins/slurm-monitor

# ~/.tmux.conf — status bar
set -g status-right '#(~/.tmux/plugins/slurm-monitor/scripts/slurm-status.sh -u $USER --color)'
set -g status-interval 10

# Detail popup (prefix+S)
bind S display-popup -E -w 62 -h 40 '~/.tmux/plugins/slurm-monitor/scripts/slurm-popup.sh -u $USER'
```

### Vim (via vim-plug)

```vim
Plug 'misterfitz/slurm-monitor'
set statusline+=%{SlurmStatus()}
```

### Vim (via lazy.nvim)

```lua
{ 'misterfitz/slurm-monitor' }

-- statusline
vim.o.statusline = vim.o.statusline .. '%{SlurmStatus()}'
```

### Neovim + lualine

```lua
require('lualine').setup {
  sections = {
    lualine_y = { 'slurm' }
  }
}
```

### LazyVim

```lua
-- ~/.config/nvim/lua/plugins/slurm.lua
return {
  { 'misterfitz/slurm-monitor',
    opts = { user = vim.env.USER },
    config = function(_, opts)
      require('slurm-monitor').setup(opts)
    end,
  },
}
```

Slurm status appears in your lualine automatically (LazyVim ships with lualine).

### Neovim native statusline (no plugin required)

```lua
-- Use the Lua module directly with any statusline
require('slurm-monitor').setup({ user = vim.env.USER })
vim.o.statusline = '%f %=%{v:lua.require("slurm-monitor").status()}'
```

Works with heirline, feline, galaxyline, or any custom statusline:

```lua
{ provider = function() return require('slurm-monitor').status() end }
```

### vim-airline

```vim
Plug 'misterfitz/slurm-monitor'
let g:airline_section_y = '%{SlurmStatus()}'
```

### Powerline

Add the slurm segment to your powerline theme:

```json
// ~/.config/powerline/themes/tmux/default.json
{
    "segments": {
        "right": [{
            "function": "powerline.segments.slurm.slurm_status",
            "args": { "user": "myuser" }
        }]
    }
}
```

Works for both tmux-powerline and vim-powerline. Fairshare is color-coded:
green (good), yellow (warning), red (critical). Failure count (`!N`) shows in
red. See `powerline/colorschemes/slurm.json` for the color scheme.

To install the segment module, add this repo to your Python path or symlink:

```bash
ln -s /path/to/slurm-monitor/powerline/segments/slurm.py \
  $(python3 -c "import powerline; print(powerline.__path__[0])")/segments/slurm.py
```

### Standalone CLI

```bash
# Copy to somewhere on your PATH
cp scripts/slurm-monitor.py ~/.local/bin/slurm-monitor
chmod +x ~/.local/bin/slurm-monitor

# Or symlink
ln -s $(pwd)/scripts/slurm-monitor.py ~/.local/bin/slurm-monitor
```

## Usage

### CLI

```bash
slurm-monitor                          # R:4.8k P:25k
slurm-monitor -u $USER                 # R:4.8k P:25k fs:0.73 #42/25k qos:normal gpu:7 !3 ▁▃▅█▂▁
slurm-monitor -u $USER --color         # With tmux color codes
slurm-monitor -u $USER --long          # Full line with everything
slurm-monitor -u $USER --json          # Full JSON (all data)
slurm-monitor -u $USER -q gpu          # Filter by QOS name
slurm-monitor -M gpu-cluster -u $USER  # Target a specific cluster
slurm-monitor --watch                  # Refresh every 5s
slurm-monitor --watch -r 10            # Refresh every 10s
slurm-monitor -a mygroup               # Account-level summary

# Failure alerts
slurm-monitor --watch -u $USER --bell                   # Terminal bell on failures
slurm-monitor --watch -u $USER --alert-cmd 'notify-send "$SLURM_ALERT_MESSAGE"'
SLURM_MONITOR_ALERT_CMD='curl -d "$SLURM_ALERT_MESSAGE" ntfy.sh/mytopic' slurm-monitor --watch -u $USER
```

### Long format

```
R:4.8k P:25k | user01 fs:0.73 #42/25k (r:11 p:17) [gpu:r3p5 normal:r8p12] | gpu:7 | FAIL:3 | used:3280h/12450h | ▁▃▅█▂▁ | hi:bio(0.91) lo:ling(0.12)
```

### tmux popup

Press `prefix + S` (configurable) to open a popup with the full dashboard:

```
  Slurm Cluster Status
  ────────────────────────────────────────────────────────
  Running   4.8k  ███░░░░░░░░░░░░░░░░░
  Pending    25k  ████████████████░░░░
  Total      30k

  ────────────────────────────────────────────────────────
  user01

  Fairshare    0.7284  ██████████████░░░░░░
  Queue Pos    #42 of 25k  (0.2%)
  Your Jobs    11 running, 17 pending
  Account      physics
  Default QOS  normal
  Allowed QOS  gpu, high

  Jobs by QOS:
    gpu           r:3  p:5
    normal        r:8  p:12

  GPU Allocation:  7 GPUs
    train_gpt             4 GPUs  200101
    finetune_bert         2 GPUs  200102
    eval_model            1 GPU   200103

  Pending Reasons:
    Priority                  3 jobs
    Resources                 1 job
    QOSMaxJobsPerUser         1 job
  Next ETA:  14:30:00  (large_train)

  Usage This Month (physics):
    You        3,280 hours
    Account    12,450 hours

  ────────────────────────────────────────────────────────
  24h Job History  120 done  3 failed
  ▁▃▅▆█▇▅▃▂▁▃▅▇█▆▅▃▂▁▂▃▅▇

  ────────────────────────────────────────────────────────
  Recent Failures (3)

    FAILED       train_gpt_large       199801  exit:1:0   10:30:00
    TIMEOUT      eval_checkpoint       199795  exit:0:15  09:45:00
    OOM          data_pipeline         199780  exit:0:0   09:15:00

  ────────────────────────────────────────────────────────
  Account Fairshare Range
  Highest  bio (0.91)
  Lowest   ling (0.12)
```

Or run it directly: `scripts/slurm-popup.sh -u $USER`

### Failure alerts

Alerts fire when new failures are detected (compared to the previous check). Available in:

| Where | How to enable |
|-------|---------------|
| **tmux status bar** | Automatic — shows `!3` in red when `--color` is on |
| **tmux display-message** | `set -g @slurm-monitor-alert "on"` |
| **Vim popup** | `let g:slurm_monitor_alert = 1` |
| **Neovim vim.notify()** | `require('slurm-monitor').setup({ alert = true })` |
| **Terminal bell** | `--bell` flag |
| **Custom webhook** | `--alert-cmd 'your-command'` or `SLURM_MONITOR_ALERT_CMD` env var |

The webhook command receives these environment variables:

| Variable | Example |
|----------|---------|
| `SLURM_ALERT_MESSAGE` | `Slurm: job 'train_gpt' FAILED` |
| `SLURM_ALERT_COUNT` | `1` |
| `SLURM_ALERT_JOB_NAME` | `train_gpt` |
| `SLURM_ALERT_JOB_STATE` | `FAILED` |
| `SLURM_ALERT_JOB_ID` | `199801` |

Webhook examples:

```bash
# Desktop notification (Linux)
--alert-cmd 'notify-send "Slurm" "$SLURM_ALERT_MESSAGE"'

# ntfy.sh push notification
--alert-cmd 'curl -s -d "$SLURM_ALERT_MESSAGE" ntfy.sh/my-slurm-alerts'

# Slack incoming webhook
--alert-cmd 'curl -s -X POST -H "Content-type: application/json" -d "{\"text\":\"$SLURM_ALERT_MESSAGE\"}" $SLACK_WEBHOOK_URL'

# Email via mailx
--alert-cmd 'echo "$SLURM_ALERT_MESSAGE" | mail -s "Slurm Alert" me@example.com'
```

## Configuration

### tmux (TPM options)

| Option | Default | Description |
|--------|---------|-------------|
| `@slurm-monitor-user` | *(none)* | User to show fairshare/rank for |
| `@slurm-monitor-color` | `off` | `on` to use tmux color codes |
| `@slurm-monitor-interval` | `10` | Cache TTL in seconds |
| `@slurm-monitor-position` | `right` | `left` or `right` status side |
| `@slurm-monitor-popup` | `S` | Key for detail popup (set empty to disable) |
| `@slurm-monitor-alert` | `off` | `on` to enable tmux display-message on failures |
| `@slurm-monitor-cluster` | *(none)* | Target a specific Slurm cluster |

### Vim options

| Variable | Default | Description |
|----------|---------|-------------|
| `g:slurm_monitor_user` | *(none)* | User to query (triggers cache generation) |
| `g:slurm_monitor_qos` | *(none)* | Filter by QOS name |
| `g:slurm_monitor_refresh` | `10000` | Refresh interval in milliseconds |
| `g:slurm_monitor_cache_file` | `/tmp/slurm-monitor-$USER.cache` | Cache file path |
| `g:slurm_monitor_fallback` | `''` | Text to show when no data available |
| `g:slurm_monitor_alert` | `0` | `1` to show popup/notification on job failures |

### Neovim Lua options (require('slurm-monitor').setup)

| Option | Default | Description |
|--------|---------|-------------|
| `user` | `nil` | User to query for fairshare/rank |
| `qos` | `nil` | Filter by QOS name |
| `cache_file` | `/tmp/slurm-monitor-$USER.cache` | Cache file path |
| `refresh_ms` | `10000` | Refresh interval in milliseconds |
| `fallback` | `''` | Text when no data available |
| `auto_generate` | `true` | Auto-call slurm-status.sh if cache missing |
| `alert` | `false` | Show `vim.notify()` on job failures |

### CLI flags

| Flag | Description |
|------|-------------|
| `-u`, `--user` | Show personal fairshare, rank, jobs, failures |
| `-a`, `--account` | Show account-level summary |
| `-q`, `--qos` | Filter by QOS name |
| `-M`, `--cluster` | Target a specific Slurm cluster |
| `--color` | Output tmux color codes |
| `--json` | Full JSON output |
| `--long` | Longer format with all details |
| `--watch` | Continuously refresh |
| `-r`, `--refresh` | Refresh interval in seconds (default: 5) |
| `--max-width` | Truncate output to N characters |
| `--bell` | Ring terminal bell on new failures |
| `--alert-cmd` | Command to run on new failures |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SLURM_MONITOR_CACHE_TTL` | `10` | Cache lifetime in seconds |
| `SLURM_MONITOR_CMD` | *(auto-detect)* | Override the monitor command path |
| `SLURM_MONITOR_ALERT_CMD` | *(none)* | Command to run on failures (same as `--alert-cmd`) |

## How it works

```
slurm-status.sh  ──calls──>  slurm-monitor.py
       │                           │
       │                     squeue / sprio / sshare / sacctmgr / sacct / sreport
       │                           │
       v                           v
  /tmp/slurm-monitor-$USER.cache       (10s TTL, text for statusline)
  /tmp/slurm-monitor-$USER.cache.json  (structured data for alerts)
       │
       ├──── tmux reads text cache via #(...)
       ├──── vim/neovim reads the same cache file (zero overhead)
       ├──── vim/neovim reads JSON cache for failure alerts
       └──── slurm-popup.sh calls --json for the detail popup
```

The cache architecture means vim doesn't spawn any subprocesses — it reads the file that tmux's status script already updates. If you're not using tmux, the vim plugin will call the script itself on first load.

### Slurm commands used

| Command | Data |
|---------|------|
| `squeue` | Job counts, QOS breakdown, GPU GRES, pending reasons/ETA |
| `sprio` | Queue rank (priority ordering) |
| `sshare` | Fairshare scores (user + account level) |
| `sacctmgr` | QOS associations (default, allowed, limits) |
| `sacct` | Failed jobs, job completion history |
| `sreport` | Monthly usage budget (hours consumed) |

## Re-recording the demo

```bash
# Requirements: brew install asciinema agg
demo/record.sh
```

Uses mock Slurm commands so it works on any machine.

## Requirements

- Python 3.8+ (for the monitor script)
- Slurm CLI tools (`squeue`, `sprio`, `sshare`, `sacctmgr`, `sacct`, `sreport`) on PATH
- tmux 3.3+ for popup support (status bar works on any tmux)
- Works on any HPC login node — no Docker required

## Tested Against

| Component | Versions |
|-----------|----------|
| **Slurm** | 24.11, 25.05 |
| **Python** | 3.8, 3.9, 3.10, 3.11, 3.12, 3.13 |
| **Vim** | 9.0, 9.1 |
| **Neovim** | 0.9, 0.10, nightly |

CI runs on every push via GitHub Actions — see the badges at the top.

## License

MIT
