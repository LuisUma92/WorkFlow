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

	-- Register LuaSnip snippets (opt-out with snippets = false)
	if M._config.snippets then
		local ok, ls = pcall(require, "luasnip")
		if ok then
			ls.add_snippets("yaml", require("workflow.snippets.yml"))
			ls.add_snippets("markdown", require("workflow.snippets.md"))
			ls.add_snippets("tex", require("workflow.snippets.tex"))
		end
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

-- Wave 1 Phase 3b: search + capture

function M.pick_search(opts)
	require("workflow.picker.search").pick(opts)
end

function M.capture_note(title, opts)
	require("workflow.notes").capture(title, opts)
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

function M.pick_graph_neighbors(opts)
	require("workflow.picker.graph_neighbors").pick(opts)
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

-- Bib-link wrappers (v1.13.0)

function M.pick_content_bib(opts)
	require("workflow.picker.content_bib").pick(opts)
end

function M.content_link_bib(
	content_id,
	bibkey,
	chapter,
	section,
	first_page,
	last_page,
	first_exercise,
	last_exercise,
	opts
)
	require("workflow.content_bib").link(
		content_id,
		bibkey,
		chapter,
		section,
		first_page,
		last_page,
		first_exercise,
		last_exercise,
		opts
	)
end

function M.content_unlink_bib(content_id, bibkey, opts)
	require("workflow.content_bib").unlink(content_id, bibkey, opts)
end

-- Statusline component
function M.statusline()
	return require("workflow.statusline").component()
end

-- Wave 5 EDITOR: enum pickers

function M.pick_relation_type(opts)
	require("workflow.picker.enums").pick_relation_type(opts)
end

function M.pick_edge_class(opts)
	require("workflow.picker.enums").pick_edge_class(opts)
end

function M.pick_note_type(opts)
	require("workflow.picker.enums").pick_note_type(opts)
end

function M.pick_frontmatter_relation_key(opts)
	require("workflow.picker.enums").pick_frontmatter_relation_key(opts)
end

function M.reload_enums()
	require("workflow.picker.enums").reload()
end

-- Wave 5 EDITOR: new zettel_id insert

--- Generate a fresh zettel_id via `workflow notes new-id --json` (or plain)
--- and insert it at the cursor position, also yanking to + register.
function M.insert_new_id(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)
	require("workflow.server").run_cli({ "notes", "new-id" }, config, function(ok, output)
		if not ok then
			vim.notify("Failed to generate new id:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local id = output:match("[A-Za-z0-9_%-]+")
		if not id or id == "" then
			vim.notify("No valid id in CLI output: " .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		vim.schedule(function()
			local row, col = unpack(vim.api.nvim_win_get_cursor(0))
			vim.api.nvim_buf_set_text(0, row - 1, col, row - 1, col, { id })
			vim.api.nvim_win_set_cursor(0, { row, col + #id })
			vim.fn.setreg('"', id)
			vim.fn.setreg("+", id)
			vim.notify("Inserted zettel_id: " .. id, vim.log.levels.INFO, { title = "workflow" })
		end)
	end)
end

-- Wave 5 EDITOR: graph validation

--- Run graph validation on current buffer and surface as diagnostics.
function M.validate_graph(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(vim.tbl_extend("force", opts, M._config or {}))
	require("workflow.validate").validate_buffer(0, config)
end

-- Wave 5 EDITOR: filtered edges picker

function M.pick_edges_filtered(opts)
	require("workflow.picker.edges").pick_with_class_filter(opts)
end

-- Wave 5 EDITOR / ITEP-0013: relation block insert
--
-- Delegates to workflow.picker.enums, which resolves the flat frontmatter
-- relation key (e.g. "derived_from_refines") from the live
-- `workflow notes enums --json` vocab — never a hard-coded key table.

--- Insert a flat-key YAML relation scaffold at the cursor.
--- If rtype (a relation_type, e.g. "refines") is provided, the matching
--- flat key is resolved and inserted directly; otherwise a picker opens
--- over all 9 flat keys.
---@param rtype string|nil  relation_type to pre-resolve
---@param opts table|nil
function M.insert_relation_block(rtype, opts)
	require("workflow.picker.enums").insert_relation_block(rtype, opts)
end

return M
