-- lua/workflow/graph.lua
-- Graph analysis commands: stats and orphans.
-- Results are rendered in a horizontal-split scratch buffer using vim.inspect.

local server = require("workflow.server")

local M = {}

--- Open a horizontal split scratch buffer and fill it with content lines.
---@param title string  Buffer name hint
---@param lines string[]
local function open_scratch(title, lines)
	local buf = vim.api.nvim_create_buf(false, true)
	vim.api.nvim_buf_set_option(buf, "buftype", "nofile")
	vim.api.nvim_buf_set_option(buf, "filetype", "json")
	vim.api.nvim_buf_set_name(buf, title)
	vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
	vim.cmd("split")
	vim.api.nvim_win_set_buf(vim.api.nvim_get_current_win(), buf)
end

---@param opts table|nil  Optional keys: main_topic, discipline_area, topic
function M.stats(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	local args = { "graph", "stats", "--json" }
	if opts.main_topic then
		table.insert(args, "--main-topic")
		table.insert(args, opts.main_topic)
	end
	if opts.discipline_area then
		table.insert(args, "--discipline-area")
		table.insert(args, opts.discipline_area)
	end
	if opts.topic then
		table.insert(args, "--topic")
		table.insert(args, opts.topic)
	end

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("graph stats failed:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json then
			vim.notify("Invalid JSON from graph stats", vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local lines = vim.split(vim.inspect(decoded), "\n")
		open_scratch("workflow://graph/stats", lines)
	end)
end

---@param opts table|nil  Optional keys: type, main_topic, discipline_area, topic
function M.orphans(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	local args = { "graph", "orphans", "--json" }
	if opts.type then
		table.insert(args, "--type")
		table.insert(args, opts.type)
	end
	if opts.main_topic then
		table.insert(args, "--main-topic")
		table.insert(args, opts.main_topic)
	end
	if opts.discipline_area then
		table.insert(args, "--discipline-area")
		table.insert(args, opts.discipline_area)
	end
	if opts.topic then
		table.insert(args, "--topic")
		table.insert(args, opts.topic)
	end

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("graph orphans failed:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json then
			vim.notify("Invalid JSON from graph orphans", vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local lines = vim.split(vim.inspect(decoded), "\n")
		open_scratch("workflow://graph/orphans", lines)
	end)
end

-- M.neighbors is intentionally not implemented.
-- Blocked by gap request: tasks/requests/2026-05-28-graph-neighbors-json.md

return M
