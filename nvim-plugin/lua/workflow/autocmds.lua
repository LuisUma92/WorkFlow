-- lua/workflow/autocmds.lua
-- Autocommands for workflow.nvim (sync + validation only, no gf/conceal)
local M = {}

function M.setup(get_client, config)
  local group = vim.api.nvim_create_augroup("Workflow", { clear = true })
  local server = require("workflow.server")
  local frontmatter = require("workflow.frontmatter")

  -- Auto-start server on entering a note buffer
  vim.api.nvim_create_autocmd("BufEnter", {
    group = group,
    pattern = { "*.md", "*.tex" },
    callback = function(args)
      server.maybe_auto_start(get_client(), config, args.buf)
    end,
  })

  -- Sync on save
  if config.auto_sync_on_save then
    vim.api.nvim_create_autocmd("BufWritePost", {
      group = group,
      pattern = "*.md",
      callback = function(args)
        local client = get_client()
        if not client or not client:is_running() then return end
        if not require("workflow.config").is_in_workspace(
          vim.api.nvim_buf_get_name(args.buf), config.workspace_dir
        ) then return end
        client:request("sync.synchronize", {}, function(_, err)
          if err then
            vim.schedule(function()
              vim.notify("Sync error: " .. vim.inspect(err), vim.log.levels.WARN, { title = "workflow" })
            end)
          end
        end)
      end,
    })
  end

  -- Validate frontmatter on save
  if config.auto_validate_on_save then
    vim.api.nvim_create_autocmd("BufWritePost", {
      group = group,
      pattern = "*.md",
      callback = function(args)
        if require("workflow.config").is_in_workspace(
          vim.api.nvim_buf_get_name(args.buf), config.workspace_dir
        ) then
          frontmatter.validate_buffer(args.buf)
        end
      end,
    })
  end

  -- Clean shutdown
  vim.api.nvim_create_autocmd("VimLeavePre", {
    group = group,
    callback = function()
      local client = get_client()
      if client and client:is_running() then
        client:stop()
      end
    end,
  })
end

return M
