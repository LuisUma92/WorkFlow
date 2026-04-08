-- lua/workflow/keymaps.lua
-- Keybindings for workflow.nvim (non-overlapping with obsidian.nvim)
local M = {}

function M.setup(prefix, workflow)
  local opts = { noremap = true, silent = true }

  -- DB sync & validation
  vim.keymap.set("n", prefix .. "s", function() workflow.sync_current() end,
    vim.tbl_extend("force", opts, { desc = "workflow: sync DB" }))
  vim.keymap.set("n", prefix .. "v", function() workflow.validate_frontmatter() end,
    vim.tbl_extend("force", opts, { desc = "workflow: validate frontmatter" }))

  -- Note lifecycle
  vim.keymap.set("n", prefix .. "p", function() workflow.promote_note() end,
    vim.tbl_extend("force", opts, { desc = "workflow: promote fleeting → permanent" }))

  -- Server management
  vim.keymap.set("n", prefix .. "!", function() workflow.server_restart() end,
    vim.tbl_extend("force", opts, { desc = "workflow: restart server" }))
end

return M
