# slurm-monitor

[![Tests](https://github.com/misterfitz/slurm-monitor/actions/workflows/test.yml/badge.svg)](https://github.com/misterfitz/slurm-monitor/actions/workflows/test.yml)
[![Slurm Integration](https://github.com/misterfitz/slurm-monitor/actions/workflows/slurm-integration.yml/badge.svg)](https://github.com/misterfitz/slurm-monitor/actions/workflows/slurm-integration.yml)

Always-visible Slurm job status in your tmux status bar and Vim/Neovim statusline. See running/pending jobs, your fairshare score, QOS, and queue rank without leaving your editor. Press a key to pop up the full dashboard.

Works with **tmux** (TPM + powerline), **Vim 9+**, **Neovim 0.9+** (lualine, native statusline, heirline, feline), **LazyVim**, and **powerline**. Tested against Slurm 24.11 and 25.05.

![demo](https://raw.githubusercontent.com/misterfitz/slurm-monitor/main/demo/priority-demo.gif)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 0:vim  1:bash  2:logs              R:4.8k P:25k fs:0.73 #42/25k qos:normal │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  your code here              ┌─── prefix+S ──────────────────┐              │
│                              │  Slurm Cluster Status          │              │
│                              │  Running   4.8k  ███░░░░░░░░░ │              │
│                              │  Pending    25k  ████████████░ │              │
│                              │                                │              │
│                              │  user01                        │              │
│                              │  Fairshare  0.7284  ██████████ │              │
│                              │  Queue Pos  #42 of 25k (0.2%) │              │
│                              │  Your Jobs  11 running, 17 pen │              │
│                              │  Default QOS  normal           │              │
│                              │  Jobs by QOS:                  │              │
│                              │    normal   r:8  p:12          │              │
│                              │    gpu      r:3  p:5           │              │
│                              └────────────────────────────────┘              │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│ NORMAL      statusline              R:4.8k P:25k fs:0.73 #42/25k qos:normal│
└──────────────────────────────────────────────────────────────────────────────┘
```

## What it shows

```
R:4.8k P:25k fs:0.73 #42/25k qos:normal
│      │      │       │       └── Your account's default QOS (or active job QOS)
│      │      │       └────────── Your best pending job is #42 of 25k in queue
│      │      └────────────────── Your fairshare score (higher = more priority)
│      └───────────────────────── 25,000 pending jobs cluster-wide
└──────────────────────────────── 4,823 running jobs cluster-wide
```

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
bind S display-popup -E -w 60 -h 22 '~/.tmux/plugins/slurm-monitor/scripts/slurm-popup.sh -u $USER'
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
green (good), yellow (warning), red (critical). See `powerline/colorschemes/slurm.json`
for the color scheme.

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
slurm-monitor -u $USER                 # R:4.8k P:25k fs:0.73 #42/25k qos:normal
slurm-monitor -u $USER --color         # With tmux color codes
slurm-monitor -u $USER --long          # Full line with QOS breakdown
slurm-monitor -u $USER --json          # Full JSON (includes allowed_qos, job_qos, etc.)
slurm-monitor -u $USER -q gpu          # Filter by QOS name
slurm-monitor --watch                  # Refresh every 5s
slurm-monitor --watch -r 10            # Refresh every 10s
slurm-monitor -a mygroup               # Account-level summary
```

### Long format

```
R:4.8k P:25k | user01 fs:0.73 #42/25k (r:11 p:17) [gpu:r3p5 normal:r8p12] | hi:user04(0.95) lo:user09(0.08)
```

The `[gpu:r3p5 normal:r8p12]` shows per-QOS job breakdown (running/pending counts per QOS).

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

  ────────────────────────────────────────────────────────
  Cluster Fairshare Range
  Highest  user04 (0.95)
  Lowest   user09 (0.08)
```

Or run it directly: `scripts/slurm-popup.sh -u $USER`

## Configuration

### tmux (TPM options)

| Option | Default | Description |
|--------|---------|-------------|
| `@slurm-monitor-user` | *(none)* | User to show fairshare/rank for |
| `@slurm-monitor-color` | `off` | `on` to use tmux color codes |
| `@slurm-monitor-interval` | `10` | Cache TTL in seconds |
| `@slurm-monitor-position` | `right` | `left` or `right` status side |
| `@slurm-monitor-popup` | `S` | Key for detail popup (set empty to disable) |

### Vim options

| Variable | Default | Description |
|----------|---------|-------------|
| `g:slurm_monitor_user` | *(none)* | User to query (triggers cache generation) |
| `g:slurm_monitor_qos` | *(none)* | Filter by QOS name |
| `g:slurm_monitor_refresh` | `10000` | Refresh interval in milliseconds |
| `g:slurm_monitor_cache_file` | `/tmp/slurm-monitor-$USER.cache` | Cache file path |
| `g:slurm_monitor_fallback` | `''` | Text to show when no data available |

### Neovim Lua options (require('slurm-monitor').setup)

| Option | Default | Description |
|--------|---------|-------------|
| `user` | `nil` | User to query for fairshare/rank |
| `qos` | `nil` | Filter by QOS name |
| `cache_file` | `/tmp/slurm-monitor-$USER.cache` | Cache file path |
| `refresh_ms` | `10000` | Refresh interval in milliseconds |
| `fallback` | `''` | Text when no data available |
| `auto_generate` | `true` | Auto-call slurm-status.sh if cache missing |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SLURM_MONITOR_CACHE_TTL` | `10` | Cache lifetime in seconds |
| `SLURM_MONITOR_CMD` | *(auto-detect)* | Override the monitor command path |

## How it works

```
slurm-status.sh  ──calls──>  slurm-monitor.py
       │                           │
       │                     squeue / sprio / sshare / sacctmgr
       │                           │
       v                           v
  /tmp/slurm-monitor-$USER.cache  (10s TTL)
       │
       ├──── tmux reads via #(...)
       ├──── vim/neovim reads the same cache file (zero overhead)
       └──── slurm-popup.sh reads via --json for the detail popup
```

The cache architecture means vim doesn't spawn any subprocesses — it reads the file that tmux's status script already updates. If you're not using tmux, the vim plugin will call the script itself on first load.

## Re-recording the demo

```bash
# Requirements: brew install asciinema agg
demo/record.sh
```

Uses mock Slurm commands so it works on any machine.

## Requirements

- Python 3.8+ (for the monitor script)
- Slurm CLI tools (`squeue`, `sprio`, `sshare`, `sacctmgr`) on PATH
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
