-- lualine component for slurm-monitor
--
-- Usage in lualine config:
--   require('lualine').setup {
--     sections = {
--       lualine_y = { 'slurm' }
--     }
--   }

local M = require('lualine.component'):extend()

local cache_file = vim.g.slurm_monitor_cache_file
    or ('/tmp/slurm-monitor-' .. (os.getenv('USER') or 'unknown') .. '.cache')

function M:init(options)
    M.super.init(self, options)
end

function M:update_status()
    local f = io.open(cache_file, 'r')
    if f then
        local line = f:read('*l')
        f:close()
        if line and #line > 0 then
            -- Strip tmux color codes
            return line:gsub('#%[.-%]', '')
        end
    end
    return ''
end

return M
