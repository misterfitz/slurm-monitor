-- Test that the Neovim Lua module loads correctly.
-- Run: nvim --headless -u NONE --cmd 'set rtp+=.' -l tests/test_neovim_load.lua

-- Load the vim plugin
vim.cmd('source plugin/slurm.vim')

-- Verify VimScript function exists
assert(vim.fn.exists('*SlurmStatus') == 1, 'SlurmStatus function not defined')

-- Verify it returns a string
local result = vim.fn.SlurmStatus()
assert(type(result) == 'string', 'SlurmStatus did not return a string, got: ' .. type(result))

-- Load the Lua module
local ok, monitor = pcall(require, 'slurm-monitor')
assert(ok, 'Failed to require slurm-monitor: ' .. tostring(monitor))

-- Verify module API
assert(type(monitor.status) == 'function', 'status() not a function')
assert(type(monitor.setup) == 'function', 'setup() not a function')

-- Verify status() returns a string
local status = monitor.status()
assert(type(status) == 'string', 'status() did not return a string, got: ' .. type(status))

print('PASS: neovim module loaded successfully')
vim.cmd('qall!')
