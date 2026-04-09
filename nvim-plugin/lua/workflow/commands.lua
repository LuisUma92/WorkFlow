-- lua/workflow/commands.lua
local M = {}

function M.setup(workflow)
  vim.api.nvim_create_user_command("WorkflowSync", function() workflow.sync_current() end, {})
  vim.api.nvim_create_user_command("WorkflowValidate", function() workflow.validate_frontmatter() end, {})
  vim.api.nvim_create_user_command("WorkflowPromote", function() workflow.promote_note() end, {})

  -- Telescope pickers (Phase 3)
  vim.api.nvim_create_user_command("WorkflowEvalPicker", function(cmd_opts)
    workflow.pick_evaluations({ inst = cmd_opts.fargs[1] })
  end, { nargs = "?" })
  vim.api.nvim_create_user_command("WorkflowItemPicker", function(cmd_opts)
    workflow.pick_items({ domain = cmd_opts.fargs[1], level = cmd_opts.fargs[2] })
  end, { nargs = "*" })
  vim.api.nvim_create_user_command("WorkflowCoursePicker", function(cmd_opts)
    workflow.pick_courses({ inst = cmd_opts.fargs[1] })
  end, { nargs = "?" })
end

return M
