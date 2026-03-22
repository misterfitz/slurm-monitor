-- lualine component for slurm-monitor
--
-- Usage in lualine config:
--   require('lualine').setup {
--     sections = {
--       lualine_y = { 'slurm' }
--     }
--   }
--
-- LazyVim: add to lua/plugins/slurm.lua:
--   return {
--     { 'misterfitz/slurm-monitor',
--       opts = { user = vim.env.USER },
--       config = function(_, opts) require('slurm-monitor').setup(opts) end },
--   }

local M = require('lualine.component'):extend()

function M:init(options)
    M.super.init(self, options)
    -- Ensure the core module is initialized
    local monitor = require('slurm-monitor')
    if options.user or options.cache_file then
        monitor.setup(options)
    end
end

function M:update_status()
    return require('slurm-monitor').status()
end

return M
