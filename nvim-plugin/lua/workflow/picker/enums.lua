-- lua/workflow/picker/enums.lua
-- Session-cached pickers sourced from `workflow notes enums --json`.
-- Never hard-codes vocab; all values come from the CLI at runtime.
-- Exposes: pick_relation_type, pick_edge_class, pick_note_type.
-- Cache cleared by M.reload() / :WorkflowReloadEnums.

local server = require("workflow.server")

local M = {}

-- Session-level cache; nil = not yet populated.
local _cache = nil

-- ---------------------------------------------------------------------------
-- Cache helpers
-- ---------------------------------------------------------------------------

--- Fetch enums, using session cache.
---@param config table  resolved workflow config
---@param on_done fun(ok: boolean, enums: table|nil, err: string|nil)
function M.get_enums(config, on_done)
	if _cache then
		on_done(true, _cache, nil)
		return
	end
	server.run_cli({ "notes", "enums", "--json" }, config, function(ok, output)
		if not ok then
			on_done(false, nil, output)
			return
		end
		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json or type(decoded) ~= "table" then
			on_done(false, nil, "Invalid JSON from `workflow notes enums --json`")
			return
		end
		_cache = decoded
		on_done(true, decoded, nil)
	end)
end

--- Clear the session cache.
function M.reload()
	_cache = nil
	vim.notify("workflow enums cache cleared", vim.log.levels.INFO, { title = "workflow" })
end

-- ---------------------------------------------------------------------------
-- Internal helpers
-- ---------------------------------------------------------------------------

local function _snacks()
	local ok, Snacks = pcall(require, "snacks")
	if not ok or not Snacks or not Snacks.picker then
		vim.notify(
			"snacks.nvim is required for pickers (https://github.com/folke/snacks.nvim)",
			vim.log.levels.ERROR,
			{ title = "workflow" }
		)
		return nil
	end
	return Snacks
end

--- Insert text at cursor and yank to + and " registers.
local function _insert_at_cursor(text)
	local row, col = unpack(vim.api.nvim_win_get_cursor(0))
	vim.api.nvim_buf_set_text(0, row - 1, col, row - 1, col, { text })
	vim.api.nvim_win_set_cursor(0, { row, col + #text })
	vim.fn.setreg('"', text)
	vim.fn.setreg("+", text)
end

--- Open a simple Snacks picker over a flat string list.
--- mode = "insert" (default) inserts at cursor; "yank" yanks to + register.
---@param title string
---@param values string[]
---@param mode string  "insert"|"yank"
local function _string_picker(title, values, mode)
	local Snacks = _snacks()
	if not Snacks then return end
	if #values == 0 then
		vim.notify("No values available for: " .. title, vim.log.levels.INFO, { title = "workflow" })
		return
	end
	local items = {}
	for _, v in ipairs(values) do
		table.insert(items, { text = v, value = v })
	end
	Snacks.picker({
		title = title,
		items = items,
		format = function(item) return { { item.text } } end,
		confirm = function(picker, item)
			picker:close()
			if not item then return end
			local value = item.value
			if mode == "yank" then
				vim.fn.setreg('"', value)
				vim.fn.setreg("+", value)
				vim.notify("Yanked: " .. value, vim.log.levels.INFO, { title = "workflow" })
			else
				_insert_at_cursor(value)
			end
		end,
	})
end

-- ---------------------------------------------------------------------------
-- Public pickers
-- ---------------------------------------------------------------------------

--- Pick a relation_type from the live vocab.
--- opts.edge_class filters to that class's types; omit for all types.
--- opts.mode = "insert" (default) | "yank"
---@param opts table|nil
function M.pick_relation_type(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)
	local mode = opts.mode or "insert"
	M.get_enums(config, function(ok, enums, err)
		if not ok then
			vim.notify("Failed to load enums:\n" .. (err or "?"), vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local rt = enums.relation_type
		if not rt or type(rt) ~= "table" then
			vim.notify("No relation_type in enums response", vim.log.levels.WARN, { title = "workflow" })
			return
		end
		local values = {}
		if opts.edge_class and rt[opts.edge_class] then
			for _, v in ipairs(rt[opts.edge_class]) do
				table.insert(values, v)
			end
		else
			-- Merge all classes, deduplicated, sorted.
			local seen = {}
			for _, class_vals in pairs(rt) do
				for _, v in ipairs(class_vals) do
					if not seen[v] then
						seen[v] = true
						table.insert(values, v)
					end
				end
			end
			table.sort(values)
		end
		local title = opts.edge_class
			and ("Relation types [" .. opts.edge_class .. "]")
			or "Relation types"
		_string_picker(title, values, mode)
	end)
end

--- Pick an edge_class from the live vocab.
--- opts.mode = "insert" (default) | "yank"
---@param opts table|nil
function M.pick_edge_class(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)
	local mode = opts.mode or "insert"
	M.get_enums(config, function(ok, enums, err)
		if not ok then
			vim.notify("Failed to load enums:\n" .. (err or "?"), vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local values = enums.edge_class
		if not values or #values == 0 then
			vim.notify("No edge_class values in enums response", vim.log.levels.WARN, { title = "workflow" })
			return
		end
		_string_picker("Edge classes", values, mode)
	end)
end

--- Resolve a flat frontmatter relation key from a relation_type using live
--- enums (`frontmatter_relation_keys`). Never hard-codes the 9 key strings —
--- always derived from the CLI response (ADR ITEP-0013 MUST rule).
---@param enums table
---@param relation_type string
---@return string|nil key
local function _key_for_relation_type(enums, relation_type)
	local frk = enums.frontmatter_relation_keys
	if not frk then return nil end
	for key, meta in pairs(frk) do
		if meta.relation_type == relation_type then
			return key
		end
	end
	return nil
end

--- Insert a flat-key relation list scaffold at cursor, e.g.:
---   derived_from_refines:
---     -
---@param key string
local function _insert_relation_key_scaffold(key)
	local row = vim.api.nvim_win_get_cursor(0)[1]
	local block = { key .. ":", "  - " }
	vim.api.nvim_buf_set_lines(0, row, row, false, block)
	vim.api.nvim_win_set_cursor(0, { row + 2, 4 })
end

--- Pick a frontmatter relation key (one of the 9 flat ITEP-0013 keys) from
--- the live vocab and insert a YAML list scaffold at cursor, or yank it.
--- opts.mode = "insert" (default) | "yank"
---@param opts table|nil
function M.pick_frontmatter_relation_key(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)
	local mode = opts.mode or "insert"
	M.get_enums(config, function(ok, enums, err)
		if not ok then
			vim.notify("Failed to load enums:\n" .. (err or "?"), vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local frk = enums.frontmatter_relation_keys
		if not frk or vim.tbl_isempty(frk) then
			vim.notify("No frontmatter_relation_keys in enums response", vim.log.levels.WARN, { title = "workflow" })
			return
		end
		local Snacks = _snacks()
		if not Snacks then return end
		local items = {}
		for key, meta in pairs(frk) do
			table.insert(items, {
				text = key .. "  (" .. meta.edge_class .. "/" .. meta.relation_type .. ")",
				value = key,
			})
		end
		table.sort(items, function(a, b) return a.value < b.value end)
		vim.schedule(function()
			Snacks.picker({
				title = "Frontmatter relation keys",
				items = items,
				format = function(item) return { { item.text } } end,
				confirm = function(picker, item)
					picker:close()
					if not item then return end
					local key = item.value
					if mode == "yank" then
						vim.fn.setreg('"', key)
						vim.fn.setreg("+", key)
						vim.notify("Yanked: " .. key, vim.log.levels.INFO, { title = "workflow" })
					else
						_insert_relation_key_scaffold(key)
					end
				end,
			})
		end)
	end)
end

--- Insert a flat-key relation scaffold at cursor.
--- If rtype (a relation_type, e.g. "refines") is given, resolves the flat
--- key from the live CLI vocab and inserts it directly. If omitted, opens
--- the frontmatter-relation-key picker instead.
---@param rtype string|nil
---@param opts table|nil
function M.insert_relation_block(rtype, opts)
	opts = opts or {}
	if not rtype or rtype == "" then
		M.pick_frontmatter_relation_key(opts)
		return
	end
	local config = require("workflow.config").resolve(opts)
	M.get_enums(config, function(ok, enums, err)
		if not ok then
			vim.notify("Failed to load enums:\n" .. (err or "?"), vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local key = _key_for_relation_type(enums, rtype)
		if not key then
			vim.notify("Unknown relation_type: " .. rtype, vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		vim.schedule(function()
			_insert_relation_key_scaffold(key)
		end)
	end)
end

--- Pick a note_type from the live vocab.
--- opts.mode = "insert" (default) | "yank"
---@param opts table|nil
function M.pick_note_type(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)
	local mode = opts.mode or "insert"
	M.get_enums(config, function(ok, enums, err)
		if not ok then
			vim.notify("Failed to load enums:\n" .. (err or "?"), vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local values = enums.note_type
		if not values or #values == 0 then
			vim.notify("No note_type values in enums response", vim.log.levels.WARN, { title = "workflow" })
			return
		end
		_string_picker("Note types", values, mode)
	end)
end

return M
