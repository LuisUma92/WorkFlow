-- nvim-plugin/tests/plenary/minimal_init.lua
-- Minimal init for plenary.busted headless test runs.
-- Usage:
--   nvim --headless --noplugin -u nvim-plugin/tests/plenary/minimal_init.lua \
--     -c "PlenaryBustedDirectory nvim-plugin/tests/plenary/ { minimal_init = 'nvim-plugin/tests/plenary/minimal_init.lua' }"

-- Resolve plenary path: honor env var, else use default lazy location.
local plenary_path = os.getenv("WORKFLOW_PLENARY_PATH")
  or (os.getenv("HOME") .. "/.local/share/nvim/lazy/plenary.nvim")

-- Repo root is three levels up from this file's directory:
--   this file:  nvim-plugin/tests/plenary/minimal_init.lua
--   repo root:  ../../..
local script_dir = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
local repo_root = vim.fn.fnamemodify(script_dir .. "../../..", ":p"):gsub("/$", "")
local plugin_dir = repo_root .. "/nvim-plugin"

-- Add plenary and the plugin lua dir to runtimepath.
vim.opt.rtp:prepend(plenary_path)
vim.opt.rtp:prepend(plugin_dir)

-- Load plenary so :PlenaryBustedDirectory is defined.
vim.cmd("runtime plugin/plenary.vim")
