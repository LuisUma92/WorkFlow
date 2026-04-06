-- lua/workflow/commands.lua
local M = {}

function M.setup(workflow)
  vim.api.nvim_create_user_command("WorkflowStart", function() workflow.server_start() end, {})
  vim.api.nvim_create_user_command("WorkflowStop", function() workflow.server_stop() end, {})
  vim.api.nvim_create_user_command("WorkflowRestart", function() workflow.server_restart() end, {})
  vim.api.nvim_create_user_command("WorkflowSync", function() workflow.sync_current() end, {})
  vim.api.nvim_create_user_command("WorkflowValidate", function() workflow.validate_frontmatter() end, {})
  vim.api.nvim_create_user_command("WorkflowRecent", function() workflow.list_recent() end, {})

  vim.api.nvim_create_user_command("WorkflowNewNote", function(args)
    local note_type = args.args ~= "" and args.args or "permanent"
    workflow.new_note(note_type)
  end, { nargs = "?", complete = function() return { "permanent", "literature", "fleeting" } end })
end

return M
