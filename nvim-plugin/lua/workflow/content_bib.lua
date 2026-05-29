-- lua/workflow/content_bib.lua
-- Bib-link wrappers (v1.13.0): link-bib / unlink-bib shells out to CLI.

local server = require("workflow.server")

local M = {}

---Link a bib entry to a content node.
---@param content_id integer
---@param bibkey string
---@param chapter integer
---@param section integer
---@param first_page integer
---@param last_page integer
---@param first_exercise integer|nil
---@param last_exercise integer|nil
---@param opts table|nil
function M.link(content_id, bibkey, chapter, section, first_page, last_page, first_exercise, last_exercise, opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	local args = {
		"content", "link-bib",
		tostring(content_id),
		bibkey,
		tostring(chapter),
		tostring(section),
		tostring(first_page),
		tostring(last_page),
	}
	if first_exercise then
		table.insert(args, tostring(first_exercise))
	end
	if last_exercise then
		table.insert(args, tostring(last_exercise))
	end

	server.run_cli(args, config, function(ok, output)
		if ok then
			vim.notify(
				string.format("Linked bibkey=%s to content id=%d", bibkey, content_id),
				vim.log.levels.INFO,
				{ title = "workflow" }
			)
		else
			vim.notify(output, vim.log.levels.ERROR, { title = "workflow" })
		end
	end)
end

---Unlink a bib entry from a content node.
---@param content_id integer
---@param bibkey string
---@param opts table|nil
function M.unlink(content_id, bibkey, opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	local args = {
		"content", "unlink-bib",
		tostring(content_id),
		bibkey,
	}

	server.run_cli(args, config, function(ok, output)
		if ok then
			vim.notify(
				string.format("Unlinked bibkey=%s from content id=%d", bibkey, content_id),
				vim.log.levels.INFO,
				{ title = "workflow" }
			)
		else
			vim.notify(output, vim.log.levels.ERROR, { title = "workflow" })
		end
	end)
end

return M
