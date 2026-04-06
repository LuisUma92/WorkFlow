-- plugin/workflow.lua
-- Bootstrap: auto-setup with defaults, register filetype detection

if vim.g.loaded_workflow then return end
vim.g.loaded_workflow = 1

-- Don't auto-setup; let user call require("workflow").setup(opts) in their config
-- This file just ensures the plugin is loadable
