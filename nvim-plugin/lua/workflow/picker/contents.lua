-- lua/workflow/picker/contents.lua
-- Snacks.picker for workflow contents
-- <CR> inserts the content id at cursor (frontmatter authoring workflow).

local server = require("workflow.server")

local M = {}

---@param opts table|nil picker opts (optional `topic_id` filter)
function M.pick(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	local args = { "content", "list", "--json" }
	if opts.topic_id then
		table.insert(args, "--topic-id")
		table.insert(args, tostring(opts.topic_id))
	end

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("Failed to list contents:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json or not decoded or #decoded == 0 then
			if not ok_json then
				vim.notify("Invalid response from CLI", vim.log.levels.ERROR, { title = "workflow" })
			else
				vim.notify("No contents found.", vim.log.levels.INFO, { title = "workflow" })
			end
			return
		end

		local items = {}
		for _, entry in ipairs(decoded) do
			table.insert(items, {
				text = string.format("topic=%d  %s (id=%d)", entry.topic_id, entry.name, entry.id),
				item = entry,
			})
		end

		if not _G.Snacks or not _G.Snacks.picker then
			vim.notify("snacks.nvim picker not loaded", vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		Snacks.picker({
			title = "Contents",
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
