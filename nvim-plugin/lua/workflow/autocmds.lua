-- lua/workflow/autocmds.lua
-- Autocommands: sync on save, validate on save
local M = {}

function M.setup(config)
	local group = vim.api.nvim_create_augroup("Workflow", { clear = true })
	local frontmatter = require("workflow.frontmatter")
	local server = require("workflow.server")

	-- Sync on save (via CLI, no server needed)
	if config.auto_sync_on_save then
		vim.api.nvim_create_autocmd("BufWritePost", {
			group = group,
			pattern = "*.md",
			callback = function(args)
				if
					not require("workflow.config").is_in_workspace(
						vim.api.nvim_buf_get_name(args.buf),
						config.workspace_dir
					)
				then
					return
				end
				server.sync(config)
			end,
		})
	end

	-- Validate frontmatter on save
	if config.auto_validate_on_save then
		vim.api.nvim_create_autocmd("BufWritePost", {
			group = group,
			pattern = "*.md",
			callback = function(args)
				if
					require("workflow.config").is_in_workspace(
						vim.api.nvim_buf_get_name(args.buf),
						config.workspace_dir
					)
				then
					frontmatter.validate_buffer(args.buf)
				end
			end,
		})
	end

	-- Graph validate on save: runs `workflow validate notes <path> --graph --json`
	-- and surfaces issues as Neovim diagnostics.  Opt-in via auto_graph_validate_on_save.
	if config.auto_graph_validate_on_save then
		vim.api.nvim_create_autocmd("BufWritePost", {
			group = group,
			pattern = "*.md",
			callback = function(args)
				local path = vim.api.nvim_buf_get_name(args.buf)
				-- Only fire for vault notes (inside vault_root or workspace_dir).
				local cfg = require("workflow.config")
				if
					cfg.is_in_workspace(path, config.vault_root)
					or cfg.is_in_workspace(path, config.workspace_dir)
				then
					require("workflow.validate").validate_buffer(args.buf, config)
				end
			end,
		})
	end
end

return M
