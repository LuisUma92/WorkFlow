-- lua/workflow/picker/topics.lua
-- Snacks.picker for workflow topics
-- <CR> inserts the topic id at cursor (frontmatter authoring workflow).

local server = require("workflow.server")

local M = {}

---@param opts table|nil picker opts (optional `discipline_area` filter)
function M.pick(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	local args = { "topic", "list", "--json" }
	if opts.discipline_area then
		table.insert(args, "--discipline-area")
		table.insert(args, opts.discipline_area)
	end

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("Failed to list topics:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json or not decoded or #decoded == 0 then
			if not ok_json then
				vim.notify("Invalid response from CLI", vim.log.levels.ERROR, { title = "workflow" })
			else
				vim.notify("No topics found.", vim.log.levels.INFO, { title = "workflow" })
			end
			return
		end

		local items = {}
		for _, entry in ipairs(decoded) do
			table.insert(items, {
				text = string.format(
					"[%s] #%d  %s (id=%d)",
					entry.discipline_area_code,
					entry.serial_number,
					entry.name,
					entry.id
				),
				item = entry,
			})
		end

		Snacks.picker({
			title = "Topics",
			items = items,
			format = function(item)
				return { { item.text } }
			end,
			confirm = function(picker, item)
				picker:close()
				if item then
					local id_str = tostring(item.item.id)
					local row, col = unpack(vim.api.nvim_win_get_cursor(0))
					vim.api.nvim_buf_set_text(0, row - 1, col, row - 1, col, { id_str })
					vim.api.nvim_win_set_cursor(0, { row, col + #id_str })
					vim.fn.setreg('"', id_str)
					vim.fn.setreg("+", id_str)
				end
			end,
		})
	end)
end

return M
