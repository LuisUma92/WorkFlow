-- lua/workflow/commands.lua
local M = {}

function M.setup(workflow)
  vim.api.nvim_create_user_command("WorkflowSync", function() workflow.sync_current() end, {})
  vim.api.nvim_create_user_command("WorkflowValidate", function() workflow.validate_frontmatter() end, {})
  vim.api.nvim_create_user_command("WorkflowPromote", function() workflow.promote_note() end, {})
end

return M
