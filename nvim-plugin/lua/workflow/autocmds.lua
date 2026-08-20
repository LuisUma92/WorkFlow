-- lua/workflow/autocmds.lua
-- Autocommands: sync on save, validate on save, LaTeX includeexpr wrapper
local M = {}

-- Substring that identifies an 'includeexpr' we installed ourselves.  Used as
-- the idempotency guard: without it a second FileType tex would save OUR expr
-- as the "previous" one and delegation would recurse forever.
local TEX_EXPR_MARKER = "workflow.tex_paths"

local function tex_includeexpr(sty_dirs)
	-- vim.fn.string() renders the Lua list as a Vimscript list literal, which
	-- v:lua converts back into a Lua table when the expression is evaluated.
	return string.format(
		"v:lua.require'workflow.tex_paths'.includeexpr(v:fname, {'sty_dirs': %s})",
		vim.fn.string(sty_dirs or {})
	)
end

-- Install the wrapper on `bufnr`, remembering whatever 'includeexpr' was in
-- effect (typically vimtex's) so tex_paths can delegate to it.  Idempotent.
function M.attach_tex(bufnr, sty_dirs)
	if not vim.api.nvim_buf_is_valid(bufnr) then
		return
	end
	local current = vim.bo[bufnr].includeexpr or ""
	if current:find(TEX_EXPR_MARKER, 1, true) then
		return -- already ours; never re-save our own expr as "previous"
	end
	require("workflow.tex_paths").set_buf_previous(bufnr, current)
	vim.bo[bufnr].includeexpr = tex_includeexpr(sty_dirs)
end

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

	-- LaTeX path-macro resolution: wrap 'includeexpr' rather than remapping
	-- `gf`, so vimtex (kpsewhich, $TEXINPUTS, .bib, \subimport) stays intact.
	-- vimtex sets includeexpr synchronously from its ftplugin
	-- (autoload/vimtex.vim: `setlocal includeexpr=vimtex#include#expr()`), and
	-- with lazy loading that ftplugin may be sourced AFTER this callback.  The
	-- vim.schedule() re-assert therefore runs once the whole FileType chain is
	-- done, which no synchronous setter can outrun; attach_tex is idempotent,
	-- so when we already won the race the scheduled call is a no-op.
	if config.tex_gf then
		vim.api.nvim_create_autocmd("FileType", {
			group = group,
			pattern = "tex",
			callback = function(args)
				local bufnr = args.buf
				M.attach_tex(bufnr, config.tex_macro_sty_dirs)
				vim.schedule(function()
					M.attach_tex(bufnr, config.tex_macro_sty_dirs)
				end)
			end,
		})
	end
end

return M
