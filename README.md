# slurm-monitor

[![Tests](https://github.com/misterfitz/slurm-monitor/actions/workflows/test.yml/badge.svg)](https://github.com/misterfitz/slurm-monitor/actions/workflows/test.yml)
[![Slurm Integration](https://github.com/misterfitz/slurm-monitor/actions/workflows/slurm-integration.yml/badge.svg)](https://github.com/misterfitz/slurm-monitor/actions/workflows/slurm-integration.yml)

Always-visible Slurm job status in your tmux status bar and Vim/Neovim statusline. See running/pending jobs, your fairshare score, and queue rank without leaving your editor.

Works with **tmux** (TPM + powerline), **Vim 9+**, **Neovim 0.9+** (lualine, native statusline, heirline, feline), **LazyVim**, and **powerline**. Tested against Slurm 24.11 and 25.05.

![demo](https://raw.githubusercontent.com/misterfitz/slurm-monitor/main/demo/priority-demo.gif)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 0:vim  1:bash  2:logs                       R:5k P:25k fs:0.82 #3     │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  your code here                                                        │
│                                                                        │
├──────────────────────────────────────────────────────────────────────────┤
│ statusline                                  R:5k P:25k fs:0.82 #3     │
└──────────────────────────────────────────────────────────────────────────┘
```

## What it shows

```
R:5k P:25k fs:0.82 #3/25k qos:normal
│    │      │       │      └── Your active QOS (from jobs or account association)
│    │      │       └──────── Your best pending job is #3 of 25k in the queue
│    │      └──────────────── Your fairshare score (higher = more priority)
│    └─────────────────────── 25,000 pending jobs cluster-wide
└──────────────────────────── 5,000 running jobs cluster-wide
```

## Install

### tmux (via TPM)

```bash
# ~/.tmux.conf
set -g @plugin 'misterfitz/slurm-monitor'
set -g @slurm-monitor-user "$USER"
set -g @slurm-monitor-color "on"
```

Then `prefix + I` to install.

### tmux (manual)

```bash
git clone https://github.com/misterfitz/slurm-monitor ~/.tmux/plugins/slurm-monitor

# ~/.tmux.conf
set -g status-right '#(~/.tmux/plugins/slurm-monitor/scripts/slurm-status.sh -u $USER --color)'
set -g status-interval 10
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
slurm-monitor                          # R:5k P:25k
slurm-monitor -u $USER                 # R:5k P:25k fs:0.82 #3/25k qos:normal
slurm-monitor -u $USER --color         # With tmux color codes
slurm-monitor -u $USER --long          # Full line with QOS breakdown
slurm-monitor -u $USER --json          # {"running": 5024, "pending": 24976, ...}
slurm-monitor -u $USER -q gpu          # Filter by QOS name
slurm-monitor --watch                  # Refresh every 5s
slurm-monitor --watch -r 10            # Refresh every 10s
slurm-monitor -a mygroup               # Account-level summary
```

### Long format

```
R:5k P:25k | user01 fs:0.82 #3/25k (r:10 p:50) [normal:r5p10 gpu:r5p40] | hi:user44(0.97) lo:user13(0.15)
```

The `[normal:r5p10 gpu:r5p40]` shows per-QOS job breakdown (running/pending counts per QOS).

## Configuration

### tmux (TPM options)

| Option | Default | Description |
|--------|---------|-------------|
| `@slurm-monitor-user` | *(none)* | User to show fairshare/rank for |
| `@slurm-monitor-color` | `off` | `on` to use tmux color codes |
| `@slurm-monitor-interval` | `10` | Cache TTL in seconds |
| `@slurm-monitor-position` | `right` | `left` or `right` status side |

### Vim options

| Variable | Default | Description |
|----------|---------|-------------|
| `g:slurm_monitor_user` | *(none)* | User to query (triggers cache generation) |
| `g:slurm_monitor_qos` | *(none)* | Filter by QOS name |
| `g:slurm_monitor_refresh` | `10000` | Refresh interval in milliseconds |
| `g:slurm_monitor_cache_file` | `/tmp/slurm-monitor-$USER.cache` | Cache file path |
| `g:slurm_monitor_fallback` | `''` | Text to show when no data available |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SLURM_MONITOR_CACHE_TTL` | `10` | Cache lifetime in seconds |
| `SLURM_MONITOR_CMD` | *(auto-detect)* | Override the monitor command path |

## How it works

```
slurm-status.sh  ──calls──►  slurm-monitor.py
       │                           │
       │                     squeue / sprio / sshare
       │                           │
       ▼                           ▼
  /tmp/slurm-monitor-$USER.cache  (10s TTL)
       │
       ├──── tmux reads via #(...)
       └──── vim/neovim reads the same cache file (zero overhead)
```

The cache architecture means vim doesn't spawn any subprocesses — it reads the file that tmux's status script already updates. If you're not using tmux, the vim plugin will call the script itself on first load.

### Neovim Lua options (require('slurm-monitor').setup)

| Option | Default | Description |
|--------|---------|-------------|
| `user` | `nil` | User to query for fairshare/rank |
| `qos` | `nil` | Filter by QOS name |
| `cache_file` | `/tmp/slurm-monitor-$USER.cache` | Cache file path |
| `refresh_ms` | `10000` | Refresh interval in milliseconds |
| `fallback` | `''` | Text when no data available |
| `auto_generate` | `true` | Auto-call slurm-status.sh if cache missing |

## Requirements

- Python 3.8+ (for the monitor script)
- Slurm CLI tools (`squeue`, `sprio`, `sshare`) on PATH
- Works on any HPC login node — no Docker required

## Tested Against

| Component | Versions |
|-----------|----------|
| **Slurm** | 24.11, 25.05 |
| **Python** | 3.10, 3.11, 3.12, 3.13 |
| **Vim** | 9.0, 9.1 |
| **Neovim** | 0.9, 0.10, nightly |

CI runs on every push via GitHub Actions — see the badges at the top.

## License

MIT
