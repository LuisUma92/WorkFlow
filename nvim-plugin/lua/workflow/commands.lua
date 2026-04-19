-- lua/workflow/commands.lua
local M = {}

function M.setup(workflow)
  vim.api.nvim_create_user_command("WorkflowSync", function() workflow.sync_current() end, {})
  vim.api.nvim_create_user_command("WorkflowValidate", function() workflow.validate_frontmatter() end, {})
  vim.api.nvim_create_user_command("WorkflowPromote", function() workflow.promote_note() end, {})

  -- Snacks pickers (Phase 3)
  vim.api.nvim_create_user_command("WorkflowEvalPicker", function(cmd_opts)
    workflow.pick_evaluations({ inst = cmd_opts.fargs[1] })
  end, { nargs = "?" })
  vim.api.nvim_create_user_command("WorkflowItemPicker", function(cmd_opts)
    workflow.pick_items({ domain = cmd_opts.fargs[1], level = cmd_opts.fargs[2] })
  end, { nargs = "*" })
  vim.api.nvim_create_user_command("WorkflowCoursePicker", function(cmd_opts)
    workflow.pick_courses({ inst = cmd_opts.fargs[1] })
  end, { nargs = "?" })

  -- PRISMA pickers (P3)
  vim.api.nvim_create_user_command("WorkflowPrismaBibPicker", function(cmd_opts)
    local opts = {}
    for _, arg in ipairs(cmd_opts.fargs) do
      local k, v = arg:match("^(%w+)=(.+)$")
      if k and v then opts[k] = v end
    end
    workflow.pick_prisma_bib(opts)
  end, { nargs = "*" })
  -- Keyword picker takes no args (workspace-wide).
  vim.api.nvim_create_user_command("WorkflowPrismaKeywordPicker", function()
    workflow.pick_prisma_keywords({})
  end, { nargs = 0 })
  vim.api.nvim_create_user_command("WorkflowPrismaReviewPicker", function(cmd_opts)
    local kw_id = tonumber(cmd_opts.fargs[1])
    if not kw_id then
      vim.notify(
        "Usage: :WorkflowPrismaReviewPicker <keyword-id> [status]",
        vim.log.levels.ERROR,
        { title = "workflow" }
      )
      return
    end
    workflow.pick_prisma_reviews({ keyword_id = kw_id, status = cmd_opts.fargs[2] })
  end, { nargs = "+" })
end

return M
