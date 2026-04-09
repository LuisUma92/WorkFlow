-- lua/workflow/keymaps.lua
local M = {}

function M.setup(prefix, workflow)
  local opts = { noremap = true, silent = true }

  vim.keymap.set("n", prefix .. "s", function() workflow.sync_current() end,
    vim.tbl_extend("force", opts, { desc = "workflow: sync DB" }))
  vim.keymap.set("n", prefix .. "v", function() workflow.validate_frontmatter() end,
    vim.tbl_extend("force", opts, { desc = "workflow: validate frontmatter" }))
  vim.keymap.set("n", prefix .. "p", function() workflow.promote_note() end,
    vim.tbl_extend("force", opts, { desc = "workflow: promote fleeting → permanent" }))

  -- Telescope pickers (Phase 3)
  vim.keymap.set("n", prefix .. "te", function() workflow.pick_evaluations() end,
    vim.tbl_extend("force", opts, { desc = "workflow: telescope evaluations" }))
  vim.keymap.set("n", prefix .. "ti", function() workflow.pick_items() end,
    vim.tbl_extend("force", opts, { desc = "workflow: telescope items" }))
  vim.keymap.set("n", prefix .. "tc", function() workflow.pick_courses() end,
    vim.tbl_extend("force", opts, { desc = "workflow: telescope courses" }))
end

return M
