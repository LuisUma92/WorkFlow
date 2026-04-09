-- lua/workflow/server.lua
-- Server lifecycle management
-- 
-- Hybrid approach: sync/validate run as one-shot Python CLI calls
-- (reliable, no server process needed). The JSONL server is optional
-- for future Telescope/graph integration.

local M = {}

--- Run a workflow CLI command asynchronously
---@param args string[] CLI arguments after "workflow"
---@param config table workspace config
---@param on_done fun(ok: boolean, output: string)|nil
function M.run_cli(args, config, on_done)
  local cmd = { config.workflow_cmd or "/home/luis/Projects/WorkFlow/.venv/bin/workflow" }
  for _, a in ipairs(args) do
    table.insert(cmd, a)
  end

  local stdout_chunks = {}
  local stderr_chunks = {}

  vim.fn.jobstart(cmd, {
    cwd = config.workspace_dir and vim.fn.expand(config.workspace_dir) or nil,
    stdout_buffered = true,
    stderr_buffered = true,
    on_stdout = function(_, data)
      if data then
        for _, line in ipairs(data) do
          if line ~= "" then table.insert(stdout_chunks, line) end
        end
      end
    end,
    on_stderr = function(_, data)
      if data then
        for _, line in ipairs(data) do
          if line ~= "" then table.insert(stderr_chunks, line) end
        end
      end
    end,
    on_exit = function(_, code)
      if on_done then
        vim.schedule(function()
          local output = table.concat(stdout_chunks, "\n")
          if code ~= 0 then
            output = output .. "\n" .. table.concat(stderr_chunks, "\n")
          end
          on_done(code == 0, output)
        end)
      end
    end,
  })
end

--- Sync notes in the vault
function M.sync(config)
  if not config.workspace_dir then
    vim.notify("No workspace configured", vim.log.levels.WARN, { title = "workflow" })
    return
  end
  local vault = vim.fn.expand(config.workspace_dir) .. "/" .. config.vault_dir
  M.run_cli({ "lectures", "scan", vault, "--project-root", vim.fn.expand(config.workspace_dir) }, config, function(ok, output)
    if ok then
      vim.notify("Synced", vim.log.levels.INFO, { title = "workflow" })
    else
      vim.notify("Sync error:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
    end
  end)
end

--- Status text for statusline (simplified — no server dependency)
function M.status_text()
  return "ZK"
end

function M.maybe_auto_start(config, bufnr)
  -- No-op: CLI approach doesn't need a persistent server
end

return M
