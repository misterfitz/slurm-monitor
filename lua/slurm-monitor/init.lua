-- slurm-monitor — Native Neovim module for Slurm job status.
--
-- Works with any statusline (native, heirline, feline, galaxyline, etc.)
-- Reads from the cache file populated by slurm-status.sh.
--
-- Usage:
--   require('slurm-monitor').setup({ user = 'myuser' })
--   vim.o.statusline = '%f %=%{v:lua.require("slurm-monitor").status()}'
--
-- Or with any statusline plugin:
--   { provider = function() return require('slurm-monitor').status() end }

local M = {}

local config = {
    cache_file = '/tmp/slurm-monitor-' .. (os.getenv('USER') or 'unknown') .. '.cache',
    refresh_ms = 10000,
    fallback = '',
    user = nil,
    qos = nil,
    auto_generate = true,
}

local cached_value = ''
local timer = nil

--- Read the cache file and update the cached value.
local function refresh()
    local f = io.open(config.cache_file, 'r')
    if f then
        local line = f:read('*l')
        f:close()
        if line and #line > 0 then
            -- Strip tmux color codes (#[...])
            cached_value = line:gsub('#%[.-%]', '')
            return
        end
    end

    -- If cache doesn't exist and auto_generate is on, try to create it
    if config.auto_generate then
        local plugin_dir = debug.getinfo(1, 'S').source:match('@?(.*/)') or ''
        local script = plugin_dir .. '../../scripts/slurm-status.sh'

        -- Check if the script exists
        local sf = io.open(script, 'r')
        if sf then
            sf:close()
            local cmd = script
            if config.user then
                cmd = cmd .. ' -u ' .. config.user
            end
            if config.qos then
                cmd = cmd .. ' -q ' .. config.qos
            end
            vim.fn.system(cmd)
            -- Re-read after generation
            local f2 = io.open(config.cache_file, 'r')
            if f2 then
                local line = f2:read('*l')
                f2:close()
                if line and #line > 0 then
                    cached_value = line:gsub('#%[.-%]', '')
                    return
                end
            end
        end
    end

    cached_value = config.fallback
end

--- Get the current Slurm status string.
--- @return string
function M.status()
    return cached_value
end

--- Get the current status as structured data (if JSON cache exists).
--- @return table|nil
function M.data()
    local f = io.open(config.cache_file .. '.json', 'r')
    if f then
        local content = f:read('*a')
        f:close()
        local ok, data = pcall(vim.json.decode, content)
        if ok then
            return data
        end
    end
    return nil
end

--- Setup the module with options.
--- @param opts table|nil
---   - cache_file: string — path to cache file
---   - refresh_ms: number — refresh interval in milliseconds (default 10000)
---   - fallback: string — text when no data available (default '')
---   - user: string|nil — user to query
---   - auto_generate: boolean — auto-call slurm-status.sh if cache missing (default true)
function M.setup(opts)
    opts = opts or {}
    for k, v in pairs(opts) do
        if config[k] ~= nil then
            config[k] = v
        end
    end

    -- Update cache file if user changed
    if opts.user and not opts.cache_file then
        config.cache_file = '/tmp/slurm-monitor-' .. (os.getenv('USER') or 'unknown') .. '.cache'
    end

    -- Initial load
    refresh()

    -- Set up timer
    if timer then
        vim.fn.timer_stop(timer)
    end
    timer = vim.fn.timer_start(config.refresh_ms, function()
        refresh()
        vim.cmd('redrawstatus')
    end, { ['repeat'] = -1 })

    -- Refresh on focus
    vim.api.nvim_create_autocmd('FocusGained', {
        group = vim.api.nvim_create_augroup('SlurmMonitor', { clear = true }),
        callback = function()
            refresh()
        end,
    })
end

return M
