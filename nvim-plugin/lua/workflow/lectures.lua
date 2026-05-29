-- lua/workflow/lectures.lua
-- Lectures commands: scan and link.
-- Output (stdout/stderr) is rendered in a horizontal-split scratch buffer.

local server = require("workflow.server")

local M = {}

--- Open a horizontal split scratch buffer and fill it with content lines.
---@param title string
---@param lines string[]
local function open_scratch(title, lines)
	local buf = vim.api.nvim_create_buf(false, true)
	vim.api.nvim_buf_set_option(buf, "buftype", "nofile")
	vim.api.nvim_buf_set_option(buf, "filetype", "")
	vim.api.nvim_buf_set_name(buf, title)
	vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
	vim.cmd("split")
	vim.api.nvim_win_set_buf(vim.api.nvim_get_current_win(), buf)
end

---@param opts table|nil
function M.scan(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	server.run_cli({ "lectures", "scan" }, config, function(ok, output)
		local lines = vim.split(output or "", "\n")
		if not ok then
			vim.notify("lectures scan failed — see scratch buffer", vim.log.levels.ERROR, { title = "workflow" })
		end
		open_scratch("workflow://lectures/scan", lines)
	end)
end

---@param opts table|nil
function M.link(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	server.run_cli({ "lectures", "link" }, config, function(ok, output)
		local lines = vim.split(output or "", "\n")
		if not ok then
			vim.notify("lectures link failed — see scratch buffer", vim.log.levels.ERROR, { title = "workflow" })
		end
		open_scratch("workflow://lectures/link", lines)
	end)
end

-- M.build_eval is intentionally not implemented.
-- build-eval requires complex multi-arg taxonomy parameters unsuitable for a one-shot command.

return M
