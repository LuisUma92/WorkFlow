-- lua/workflow/server.lua
-- Server lifecycle management

local M = {}

function M.ensure_running(client, config)
  if client:is_running() then return true end
  -- Set working directory to workspace for server
  local prev_cwd = vim.fn.getcwd()
  if config.workspace_dir then
    vim.cmd("cd " .. vim.fn.fnameescape(config.workspace_dir))
  end
  local ok = client:start()
  if prev_cwd ~= vim.fn.getcwd() then
    vim.cmd("cd " .. vim.fn.fnameescape(prev_cwd))
  end
  return ok
end

function M.health(client)
  return {
    running = client:is_running(),
    initialized = client.initialized,
  }
end

function M.status_text(client)
  if not client then return "ZK ○" end
  if not client:is_running() then return "ZK ○" end
  if not client.initialized then return "ZK …" end
  return "ZK ●"
end

function M.maybe_auto_start(client, config, bufnr)
  if not config.auto_start then return end
  if not config.workspace_dir then return end
  local filepath = vim.api.nvim_buf_get_name(bufnr)
  if not M._is_note_buffer(filepath, config) then return end
  M.ensure_running(client, config)
end

function M._is_note_buffer(filepath, config)
  if not filepath or filepath == "" then return false end
  local ext = vim.fn.fnamemodify(filepath, ":e")
  if ext ~= "md" and ext ~= "tex" then return false end
  return require("workflow.config").is_in_workspace(filepath, config.workspace_dir)
end

return M
