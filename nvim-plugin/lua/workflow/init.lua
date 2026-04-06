-- lua/workflow/init.lua
-- WorkFlow Neovim plugin — Zettelkasten daily workflow

local Client = require("workflow.client")
local Config = require("workflow.config")
local UI = require("workflow.ui")

local M = {}

M._client = nil
M._config = nil

function M.setup(opts)
  M._config = Config.resolve(opts)

  M._client = Client.new({
    cmd = M._config.server_cmd,
    protocol_version = M._config.protocol_version,
    debug = M._config.debug,
    request_timeout_ms = M._config.request_timeout_ms,
  })

  -- Register autocommands
  require("workflow.autocmds").setup(function() return M._client end, M._config)

  -- Register user commands
  require("workflow.commands").setup(M)

  -- Register keymaps
  if M._config.keymaps then
    require("workflow.keymaps").setup(M._config.keymap_prefix, M)
  end

  -- Set up buffer-local gf for markdown files already open
  for _, bufnr in ipairs(vim.api.nvim_list_bufs()) do
    if vim.api.nvim_buf_is_loaded(bufnr) then
      local name = vim.api.nvim_buf_get_name(bufnr)
      if name:match("%.md$") and Config.is_in_workspace(name, M._config.workspace_dir) then
        require("workflow.keymaps").setup_buffer_gf(bufnr, M._config)
      end
    end
  end
end

function M.client()
  if not M._client then M.setup({}) end
  return M._client
end

-- Public actions

function M.new_note(note_type)
  require("workflow.templates").prompt_new_note(note_type or "permanent", M._config)
end

function M.sync_current()
  local client = M.client()
  local server = require("workflow.server")
  server.ensure_running(client, M._config)
  client:request("sync.synchronize", {}, function(result, err)
    vim.schedule(function()
      if err then
        vim.notify("Sync error: " .. vim.inspect(err), vim.log.levels.ERROR, { title = "workflow" })
      else
        vim.notify("Synced", vim.log.levels.INFO, { title = "workflow" })
      end
    end)
  end)
end

function M.validate_frontmatter()
  require("workflow.frontmatter").validate_buffer(vim.api.nvim_get_current_buf())
end

function M.list_recent()
  local client = M.client()
  local server = require("workflow.server")
  server.ensure_running(client, M._config)
  client:request("notes.list_recent", { n = 20 }, function(result, err)
    vim.schedule(function()
      if err then
        vim.notify("Error: " .. vim.inspect(err), vim.log.levels.ERROR, { title = "workflow" })
        return
      end
      local lines = { "Recent notes:" }
      for i, it in ipairs(result.items or {}) do
        table.insert(lines, ("%02d  %s"):format(i, it.filename))
      end
      UI.show_output("Recent Notes", lines)
    end)
  end)
end

function M.server_start()
  require("workflow.server").ensure_running(M.client(), M._config)
end

function M.server_stop()
  M.client():stop()
end

function M.server_restart()
  M.client():restart()
end

-- Statusline component
function M.statusline()
  return require("workflow.statusline").component(function() return M._client end)
end

return M
