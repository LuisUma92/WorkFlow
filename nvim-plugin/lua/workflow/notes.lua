-- lua/workflow/notes.lua
-- High-level actions for `workflow notes *` commands.
-- All shell-out via server.run_cli(); JSON responses where supported.

local server = require("workflow.server")

local M = {}

--- Resolve vault_root from config, expand ~
local function vault_from_config(config)
	return config.vault_root and vim.fn.expand(config.vault_root) or nil
end

--- Open a scratch buffer with formatted note output
local function open_scratch(lines, title)
	local buf = vim.api.nvim_create_buf(false, true)
	vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
	vim.bo[buf].buftype = "nofile"
	vim.bo[buf].bufhidden = "wipe"
	vim.bo[buf].filetype = "markdown"
	vim.api.nvim_buf_set_name(buf, title or "workflow://note")
	vim.cmd("split")
	vim.api.nvim_set_current_buf(buf)
end

--- Get current buffer's zettel_id from frontmatter if available
local function id_from_current_buf()
	local bufnr = vim.api.nvim_get_current_buf()
	local ok, fm = pcall(require, "workflow.frontmatter")
	if not ok then return nil end
	local data = fm.extract(bufnr)
	return data and data.id or nil
end

--- Sync notes vault.
---@param opts table|nil  opts.strict → pass --strict-concepts; opts.workspace_dir override
function M.sync(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)
	local vault = vault_from_config(config)
	if not vault then
		vim.notify("No vault root configured", vim.log.levels.WARN, { title = "workflow" })
		return
	end
	local args = { "notes", "sync", "--dir", vault, "--json" }
	if opts.strict then
		table.insert(args, "--strict-concepts")
	end
	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("notes sync error:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local ok_json, decoded = pcall(vim.json.decode, output)
		if ok_json and decoded then
			local msg = string.format(
				"Synced: %d added, %d updated, %d removed",
				decoded.added or 0,
				decoded.updated or 0,
				decoded.removed or 0
			)
			vim.notify(msg, vim.log.levels.INFO, { title = "workflow" })
		else
			vim.notify("Notes synced", vim.log.levels.INFO, { title = "workflow" })
		end
	end)
end

--- Show a note in a scratch buffer.
---@param id string|nil  zettel_id; if nil, parses current buffer frontmatter
---@param opts table|nil
function M.show(id, opts)
	opts = opts or {}
	id = id or id_from_current_buf()
	if not id or id == "" then
		vim.notify("No note id provided or found in frontmatter", vim.log.levels.WARN, { title = "workflow" })
		return
	end
	local config = require("workflow.config").resolve(opts)
	local vault = vault_from_config(config)
	local args = { "notes", "show", id, "--json" }
	if vault then
		table.insert(args, "--dir")
		table.insert(args, vault)
	end
	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("notes show error:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local ok_json, note = pcall(vim.json.decode, output)
		if not ok_json or not note then
			vim.notify("Invalid response from CLI", vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local lines = {
			"# " .. (note.title or id),
			"",
			string.format("id:    %s", note.id or id),
			string.format("type:  %s", note.type or "?"),
			string.format("tags:  %s", vim.inspect(note.tags or {})),
			string.format("concepts: %s", vim.inspect(note.concepts or {})),
			"",
			"---",
			"",
		}
		if note.body and note.body ~= "" then
			for line in (note.body .. "\n"):gmatch("([^\n]*)\n") do
				table.insert(lines, line)
			end
		end
		open_scratch(lines, "workflow://" .. id)
	end)
end

--- Add/remove tags on a note.
---@param id string|nil
---@param add string[]|nil  tags to add
---@param remove string[]|nil  tags to remove
---@param opts table|nil
function M.tag(id, add, remove, opts)
	opts = opts or {}
	id = id or id_from_current_buf()
	if not id or id == "" then
		vim.notify("No note id provided or found in frontmatter", vim.log.levels.WARN, { title = "workflow" })
		return
	end
	local config = require("workflow.config").resolve(opts)
	local args = { "notes", "tag", id, "--json" }
	for _, t in ipairs(add or {}) do
		table.insert(args, "--add")
		table.insert(args, t)
	end
	for _, t in ipairs(remove or {}) do
		table.insert(args, "--remove")
		table.insert(args, t)
	end
	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("notes tag error:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
		else
			vim.notify("Tags updated for " .. id, vim.log.levels.INFO, { title = "workflow" })
		end
	end)
end

--- Link a note to a concept, reference, or exercise.
---@param id string|nil
---@param kind string  "concept" | "reference" | "exercise"
---@param value string
---@param opts table|nil  opts.remove=true to unlink; opts.strict=true
function M.link(id, kind, value, opts)
	opts = opts or {}
	id = id or id_from_current_buf()
	if not id or id == "" then
		vim.notify("No note id provided or found in frontmatter", vim.log.levels.WARN, { title = "workflow" })
		return
	end
	local valid_kinds = { concept = true, reference = true, exercise = true }
	if not valid_kinds[kind] then
		vim.notify("Invalid link kind: " .. tostring(kind) .. " (must be concept|reference|exercise)", vim.log.levels.ERROR, { title = "workflow" })
		return
	end
	local config = require("workflow.config").resolve(opts)
	local args = { "notes", "link", id, "--" .. kind, value, "--json" }
	if opts.remove then
		table.insert(args, "--remove")
	end
	if opts.strict then
		table.insert(args, "--strict")
	end
	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("notes link error:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
		else
			vim.notify(string.format("Linked %s -[%s]-> %s", id, kind, value), vim.log.levels.INFO, { title = "workflow" })
		end
	end)
end

--- Create a new note.
---@param id string|nil   nanoid; CLI will generate one if absent
---@param title string|nil
---@param opts table|nil  opts.type, opts.tags (string[])
function M.new(id, title, opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)
	local args = { "notes", "new", "--json" }
	if id and id ~= "" then
		table.insert(args, "--id")
		table.insert(args, id)
	end
	if title and title ~= "" then
		table.insert(args, "--title")
		table.insert(args, title)
	end
	if opts.type and opts.type ~= "" then
		table.insert(args, "--type")
		table.insert(args, opts.type)
	end
	for _, t in ipairs(opts.tags or {}) do
		table.insert(args, "--tag")
		table.insert(args, t)
	end
	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("notes new error:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local ok_json, note = pcall(vim.json.decode, output)
		if ok_json and note and note.path then
			vim.notify("Created: " .. (note.path or note.id or ""), vim.log.levels.INFO, { title = "workflow" })
			vim.cmd("edit " .. vim.fn.fnameescape(note.path))
		else
			vim.notify("Note created", vim.log.levels.INFO, { title = "workflow" })
		end
	end)
end

--- Check for cycles in the structural edge graph.
--- On cycles (exit code 1) populates quickfix list.
---@param opts table|nil
function M.edges_check(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)
	local args = { "notes", "edges", "check", "--json" }
	server.run_cli(args, config, function(ok, output)
		if ok then
			vim.notify("No cycles found in note edges", vim.log.levels.INFO, { title = "workflow" })
			return
		end
		-- Parse JSON cycle list if available
		local ok_json, decoded = pcall(vim.json.decode, output)
		local qf_items = {}
		if ok_json and decoded and type(decoded) == "table" then
			local cycles = decoded.cycles or decoded
			if type(cycles) == "table" then
				for _, node in ipairs(cycles) do
					local node_id = type(node) == "table" and (node.zettel_id or node.id or vim.inspect(node)) or tostring(node)
					table.insert(qf_items, {
						text = "Cycle node: " .. node_id,
						type = "E",
					})
				end
			end
		end
		if #qf_items == 0 then
			table.insert(qf_items, { text = "Cycles detected in structural note edges. Run: workflow notes edges check --json", type = "E" })
		end
		vim.fn.setqflist(qf_items, " ")
		vim.cmd("copen")
		vim.notify("Cycles detected in structural note edges", vim.log.levels.WARN, { title = "workflow" })
	end)
end

return M
