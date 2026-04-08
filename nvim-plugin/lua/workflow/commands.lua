-- lua/workflow/commands.lua
-- User commands for workflow.nvim (non-overlapping with obsidian.nvim)
local M = {}

function M.setup(workflow)
  -- Server lifecycle
  vim.api.nvim_create_user_command("WorkflowStart", function() workflow.server_start() end, {})
  vim.api.nvim_create_user_command("WorkflowStop", function() workflow.server_stop() end, {})
  vim.api.nvim_create_user_command("WorkflowRestart", function() workflow.server_restart() end, {})

  -- DB & validation
  vim.api.nvim_create_user_command("WorkflowSync", function() workflow.sync_current() end, {})
  vim.api.nvim_create_user_command("WorkflowValidate", function() workflow.validate_frontmatter() end, {})

  -- Note lifecycle
  vim.api.nvim_create_user_command("WorkflowPromote", function() workflow.promote_note() end, {})
end

return M
