-- lua/workflow/init.lua
-- WorkFlow Neovim plugin — complements obsidian.nvim with DB sync,
-- validation, promote, and exercise/image integration.
--
-- Uses CLI calls (not JSONL server) for reliability.

local Config = require("workflow.config")

local M = {}

M._config = nil

function M.setup(opts)
	M._config = Config.resolve(opts)

	-- Register autocommands
	require("workflow.autocmds").setup(M._config)

	-- Register user commands
	require("workflow.commands").setup(M)

	-- Register keymaps
	if M._config.keymaps then
		require("workflow.keymaps").setup(M._config.keymap_prefix, M)
	end
end

-- Public actions

function M.sync_current()
	require("workflow.server").sync(M._config)
end
function M.sync_current_exercise()
	require("workflow.server").sync_exercise(M._config)
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

	if not M._config or not M._config.vault_root then
		vim.notify("No vault root configured", vim.log.levels.WARN, { title = "workflow" })
		return
	end

	local vault = vim.fn.expand(M._config.vault_root)
	local inbox = vault .. "/inbox"

	-- Check if file is in inbox
	if not vim.startswith(filepath, inbox) then
		vim.notify("Note is not in inbox — already promoted?", vim.log.levels.INFO, { title = "workflow" })
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

-- Snacks pickers (Phase 3)

function M.pick_evaluations(opts)
	require("workflow.picker.evaluations").pick(opts)
end

function M.pick_items(opts)
	require("workflow.picker.items").pick(opts)
end

function M.pick_courses(opts)
	require("workflow.picker.courses").pick(opts)
end

-- PRISMA pickers (P3)

function M.pick_prisma_bib(opts)
	require("workflow.picker.prisma_bib").pick(opts)
end

function M.pick_prisma_keywords(opts)
	require("workflow.picker.prisma_keywords").pick(opts)
end

function M.pick_prisma_reviews(opts)
	require("workflow.picker.prisma_reviews").pick(opts)
end

-- Notes module (ITEP-0011/0012/0013)

function M.sync_notes(opts)
	require("workflow.notes").sync(opts)
end

function M.show_note(id, opts)
	require("workflow.notes").show(id, opts)
end

function M.tag_note(id, add, remove, opts)
	require("workflow.notes").tag(id, add, remove, opts)
end

function M.link_note(id, kind, value, opts)
	require("workflow.notes").link(id, kind, value, opts)
end

function M.new_note(id, title, opts)
	require("workflow.notes").new(id, title, opts)
end

function M.pick_notes(opts)
	require("workflow.picker.notes").pick(opts)
end

function M.pick_edges(opts)
	require("workflow.picker.edges").pick(opts)
end

function M.edges_check(opts)
	require("workflow.notes").edges_check(opts)
end

-- Taxonomy pickers (v1.12.0)

function M.pick_topics(opts)
	require("workflow.picker.topics").pick(opts)
end

function M.pick_contents(opts)
	require("workflow.picker.contents").pick(opts)
end

function M.pick_concepts(opts)
	require("workflow.picker.concepts").pick(opts)
end

function M.graph_stats(opts)
	require("workflow.graph").stats(opts)
end

function M.graph_orphans(opts)
	require("workflow.graph").orphans(opts)
end

function M.lecture_scan(opts)
	require("workflow.lectures").scan(opts)
end

function M.lecture_link(opts)
	require("workflow.lectures").link(opts)
end

-- Statusline component
function M.statusline()
	return require("workflow.statusline").component()
end

return M
