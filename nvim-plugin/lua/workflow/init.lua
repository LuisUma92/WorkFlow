-- lua/workflow/init.lua
-- WorkFlow Neovim plugin — complements obsidian.nvim with DB sync,
-- validation, server RPC, and exercise/image/graph integration.
--
-- Note creation and wiki-link navigation are handled by obsidian.nvim.

local Client = require("workflow.client")
local Config = require("workflow.config")

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
end

function M.client()
  if not M._client then M.setup({}) end
  return M._client
end

-- Public actions (unique to workflow, not in obsidian.nvim)

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

function M.promote_note()
  local bufnr = vim.api.nvim_get_current_buf()
  local filepath = vim.api.nvim_buf_get_name(bufnr)

  if not filepath or filepath == "" then
    vim.notify("No file open", vim.log.levels.WARN, { title = "workflow" })
    return
  end

  if not M._config or not M._config.workspace_dir then
    vim.notify("No workspace configured", vim.log.levels.WARN, { title = "workflow" })
    return
  end

  local workspace = vim.fn.expand(M._config.workspace_dir)
  local vault = workspace .. "/" .. M._config.vault_dir
  local inbox = vault .. "/inbox"

  -- Check if file is in inbox
  if not vim.startswith(filepath, inbox) then
    vim.notify("Note is not in inbox — already promoted?", vim.log.levels.INFO, { title = "workflow" })
    return
  end

  -- Parse frontmatter to update type
  local fm = require("workflow.frontmatter")
  local data, err = fm.extract(bufnr)
  if not data then
    vim.notify("No frontmatter: " .. (err or ""), vim.log.levels.WARN, { title = "workflow" })
    return
  end

  -- Move file from inbox/ to vault root
  local filename = vim.fn.fnamemodify(filepath, ":t")
  local dest = vault .. "/" .. filename

  if vim.fn.filereadable(dest) == 1 then
    vim.notify("Destination exists: " .. dest, vim.log.levels.ERROR, { title = "workflow" })
    return
  end

  -- Save buffer, close, move file, reopen
  vim.cmd("write")
  vim.cmd("bdelete")
  vim.fn.rename(filepath, dest)

  -- Update type from fleeting to permanent in the moved file
  local lines = vim.fn.readfile(dest)
  for i, line in ipairs(lines) do
    if line:match("^type:%s*fleeting") then
      lines[i] = "type: permanent"
      break
    end
  end
  vim.fn.writefile(lines, dest)

  -- Open the promoted note
  vim.cmd("edit " .. vim.fn.fnameescape(dest))
  vim.notify("Promoted to permanent: " .. filename, vim.log.levels.INFO, { title = "workflow" })
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
