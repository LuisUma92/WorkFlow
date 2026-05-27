-- lua/workflow/config.lua
-- Configuration schema and workspace detection

local M = {}

M.defaults = {
	workflow_cmd = nil, -- auto-detected from venv or PATH
	auto_sync_on_save = true,
	auto_validate_on_save = true,
	workspace_dir = nil, -- auto-detected from .workflow/config.yaml
	vault_dir = "/home/luis/01-U/0000AA-Vault",
	keymaps = true,
	keymap_prefix = "<leader>z",
}

function M.resolve(opts)
	local config = vim.tbl_deep_extend("force", M.defaults, opts or {})
	if not config.workspace_dir then
		config.workspace_dir = M.detect_workspace()
	end
	config.vault_root = M.resolve_vault_root(config)
	return config
end

-- Resolve the unified vault root (ITEP-0011).
-- WORKFLOW_VAULT_ROOT env var wins (absolute path); otherwise fall back to
-- <workspace_dir>/<vault_dir>. Returns nil if neither is available.
function M.resolve_vault_root(config)
	local env = vim.env.WORKFLOW_VAULT_ROOT
	if env and env ~= "" then
		return vim.fn.expand(env)
	end
	if config.workspace_dir then
		return vim.fn.expand(config.workspace_dir) .. "/" .. config.vault_dir
	end
	return nil
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
	if not workspace_dir then
		return false
	end
	return vim.startswith(vim.fn.fnamemodify(filepath, ":p"), workspace_dir)
end

return M
