-- lua/workflow/picker/courses.lua
-- Snacks.picker for courses

local server = require("workflow.server")

local M = {}

---@param opts table|nil picker opts (plus optional `inst` filter)
function M.pick(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	local args = { "course", "list", "--json" }
	if opts.inst then
		table.insert(args, "--inst")
		table.insert(args, opts.inst)
	end

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("Failed to list courses:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json or not decoded or #decoded == 0 then
			if not ok_json then
				vim.notify("Invalid response from CLI", vim.log.levels.ERROR, { title = "workflow" })
			else
				vim.notify("No courses found.", vim.log.levels.INFO, { title = "workflow" })
			end
			return
		end

		local items = {}
		for _, entry in ipairs(decoded) do
			table.insert(items, {
				text = string.format(
					"[%s] %-10s  %s  (%dlpw %dhpl)",
					entry.institution,
					entry.code,
					entry.name,
					entry.lectures_per_week,
					entry.hours_per_lecture
				),
				item = entry,
			})
		end

		Snacks.picker({
			title = "Courses",
			items = items,
			format = function(item)
				return {
					{ item.text },
				}
			end,
			confirm = function(picker, item)
				picker:close()
				if item then
					local msg = string.format(
						"Selected: [%s] %s — %s (id=%d)",
						item.item.institution,
						item.item.code,
						item.item.name,
						item.item.id
					)
					-- copy to default register
					vim.fn.setreg('"', msg)
					vim.fn.setreg("+", msg)
					vim.notify(msg, vim.log.levels.INFO, { title = "workflow" })
				end
			end,
		})
	end)
end

return M
