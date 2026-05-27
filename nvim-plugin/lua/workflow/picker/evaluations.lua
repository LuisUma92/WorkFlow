-- lua/workflow/picker/evaluations.lua
-- Snacks.picker for evaluation templates

local server = require("workflow.server")

local M = {}

---@param opts table|nil picker opts (plus optional `inst` filter)
function M.pick(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	local args = { "evaluations", "list", "--json", "--full" }
	if opts.inst then
		table.insert(args, "--inst")
		table.insert(args, opts.inst)
	end

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("Failed to list evaluations:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json or not decoded or #decoded == 0 then
			if not ok_json then
				vim.notify("Invalid response from CLI", vim.log.levels.ERROR, { title = "workflow" })
			else
				vim.notify("No evaluation templates found.", vim.log.levels.INFO, { title = "workflow" })
			end
			return
		end

		local items = {}
		for _, entry in ipairs(decoded) do
			table.insert(items, {
				text = string.format(
					"[%s] %s (%d pts, %d items)",
					entry.institution,
					entry.name,
					entry.total_points,
					entry.item_count
				),
				item = entry,
			})
		end

		Snacks.picker({
			title = "Evaluation Templates",
			items = items,
			format = function(item)
				return {
					{ item.text },
				}
			end,
			preview = function(ctx)
				local val = ctx.item.item
				local lines = {
					string.format("[%s] %s", val.institution, val.name),
					string.format("Total: %d pts  |  Items: %d", val.total_points, val.item_count),
					"",
				}
				if val.description and val.description ~= "" then
					table.insert(lines, "Description: " .. val.description)
					table.insert(lines, "")
				end
				if val.items then
					for i, it in ipairs(val.items) do
						table.insert(
							lines,
							string.format(
								"  %d. %s — %s / %s  %d × %d pts",
								i,
								it.item_name,
								it.taxonomy_domain,
								it.taxonomy_level,
								it.amount,
								it.points_per_item
							)
						)
					end
				end
				return lines
			end,
			confirm = function(picker, item)
				picker:close()
				if item then
					local msg =
						string.format("Selected: [%s] %s (id=%d)", item.item.institution, item.item.name, item.item.id)

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
