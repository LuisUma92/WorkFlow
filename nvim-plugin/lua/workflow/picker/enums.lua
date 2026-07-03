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
