-- lua/workflow/config.lua
-- Configuration schema and workspace detection

local M = {}

M.defaults = {
  server_cmd = { "python", "-m", "latexzettel.server.main" },
  protocol_version = 1,
  debug = false,
  request_timeout_ms = 30000,
  auto_start = true,
  auto_sync_on_save = true,
  auto_validate_on_save = true,
  workspace_dir = nil, -- auto-detected
  vault_dir = "0000AA-Vault",
  templates_dir = "0000AA-Vault/templates",
  keymaps = true,
  keymap_prefix = "<leader>z",
  conceallevel = 2,
}

function M.resolve(opts)
  local config = vim.tbl_deep_extend("force", M.defaults, opts or {})
  if not config.workspace_dir then
    config.workspace_dir = M.detect_workspace()
  end
  return config
end

function M.detect_workspace()
  -- Walk up from cwd looking for .workflow/config.yaml
  local dir = vim.fn.getcwd()
  while dir ~= "/" do
    if vim.fn.filereadable(dir .. "/.workflow/config.yaml") == 1 then
      return dir
    end
    dir = vim.fn.fnamemodify(dir, ":h")
  end
  return nil
end

function M.is_in_workspace(filepath, workspace_dir)
  if not workspace_dir then return false end
  return vim.startswith(vim.fn.fnamemodify(filepath, ":p"), workspace_dir)
end

return M
