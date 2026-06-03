-- lua/workflow/picker/graph_neighbors.lua
-- Snacks.picker for `workflow graph neighbors <node-id> --json [--depth N]`
-- <CR>: open neighbor file if path is non-null

local server = require("workflow.server")

local M = {}

---@param opts table  node_id (string, required), depth (number, optional)
function M.pick(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	if not opts.node_id then
		vim.notify("pick_graph_neighbors: opts.node_id is required", vim.log.levels.ERROR, { title = "workflow" })
		return
	end

	local args = { "graph", "neighbors", opts.node_id, "--json" }
	if opts.depth then
		table.insert(args, "--depth")
		table.insert(args, tostring(opts.depth))
	end

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("Failed to get graph neighbors:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json or not decoded then
			vim.notify("Invalid response from CLI", vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local neighbors = decoded.neighbors
		if not neighbors or #neighbors == 0 then
			vim.notify("No neighbors found.", vim.log.levels.INFO, { title = "workflow" })
			return
		end

		local items = {}
		for _, n in ipairs(neighbors) do
			local rel = n.edge_type or n.edge_class or "?"
			table.insert(items, {
				text = string.format("[d%d] %s  (%s)", n.depth, n.title or n.id, rel),
				item = n,
			})
		end

		local ok_snacks, Snacks = pcall(require, "snacks")
		if not ok_snacks or not Snacks or not Snacks.picker then
			vim.notify("snacks.nvim is required for pickers (https://github.com/folke/snacks.nvim)", vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		Snacks.picker({
			title = "Graph neighbors",
			items = items,
			format = function(item)
				return { { item.text } }
			end,
			confirm = function(picker, item)
				picker:close()
				if not item then return end
				local p = item.item.path
				if p ~= nil and p ~= vim.NIL then
					vim.cmd("edit " .. vim.fn.fnameescape(p))
				else
					vim.notify("No file for this node", vim.log.levels.WARN, { title = "workflow" })
				end
			end,
		})
	end)
end

return M
