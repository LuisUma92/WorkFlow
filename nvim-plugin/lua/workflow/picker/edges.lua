-- lua/workflow/picker/edges.lua
-- Snacks.picker for `workflow notes edges list --json`
-- Filters: source, edge-class, relation-type
-- Preview: full edge JSON + rationale
-- <CR>: open source note file

local server = require("workflow.server")

local M = {}

---@param opts table|nil  source, edge_class, relation_type filter keys
function M.pick(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)
	local vault = config.vault_root and vim.fn.expand(config.vault_root) or nil

	local args = { "notes", "edges", "list", "--json" }
	if opts.source then
		table.insert(args, "--source")
		table.insert(args, opts.source)
	end
	if opts.edge_class then
		table.insert(args, "--edge-class")
		table.insert(args, opts.edge_class)
	end
	if opts.relation_type then
		table.insert(args, "--relation-type")
		table.insert(args, opts.relation_type)
	end

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("Failed to list note edges:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json or not decoded then
			vim.notify("Invalid JSON from CLI", vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		if #decoded == 0 then
			vim.notify("No note edges found.", vim.log.levels.INFO, { title = "workflow" })
			return
		end

		local items = {}
		for _, entry in ipairs(decoded) do
			local src = entry.source_zettel_id or entry.source_id or "?"
			local tgt = entry.target_zettel_id or entry.target_id or "?"
			local cls = entry.edge_class or "?"
			local rel = entry.relation_type or "?"
			table.insert(items, {
				text = string.format("[%s] %s → %s (%s)", cls, src, tgt, rel),
				item = entry,
			})
		end

		Snacks.picker({
			title = "Note Edges",
			items = items,
			format = function(item)
				return { { item.text } }
			end,
			preview = function(ctx)
				local e = ctx.item.item
				local lines = {
					string.format("edge_class:    %s", e.edge_class or "?"),
					string.format("relation_type: %s", e.relation_type or "?"),
					string.format("source:        %s", e.source_zettel_id or e.source_id or "?"),
					string.format("target:        %s", e.target_zettel_id or e.target_id or "?"),
				}
				if e.id then
					table.insert(lines, string.format("edge_id:       %s", e.id))
				end
				if e.weight ~= nil then
					table.insert(lines, string.format("weight:        %s", tostring(e.weight)))
				end
				if e.rationale and e.rationale ~= "" then
					table.insert(lines, "")
					table.insert(lines, "Rationale:")
					for line in (e.rationale .. "\n"):gmatch("([^\n]*)\n") do
						table.insert(lines, "  " .. line)
					end
				end
				table.insert(lines, "")
				table.insert(lines, "--- raw ---")
				local raw_ok, raw = pcall(vim.json.encode, e)
				if raw_ok then
					-- pretty-print by splitting on commas for readability
					table.insert(lines, raw)
				end
				return lines
			end,
			confirm = function(picker, item)
				picker:close()
				if not item then return end
				local src_id = item.item.source_zettel_id or item.item.source_id
				if not src_id then
					vim.notify("No source zettel_id on edge", vim.log.levels.WARN, { title = "workflow" })
					return
				end
				-- Resolve the source note path via `notes show`
				local config2 = require("workflow.config").resolve(opts)
				local show_args = { "notes", "show", src_id, "--json" }
				if vault then
					table.insert(show_args, "--dir")
					table.insert(show_args, vault)
				end
				server.run_cli(show_args, config2, function(ok2, out2)
					if not ok2 then
						vim.notify("Cannot resolve note path for " .. src_id, vim.log.levels.WARN, { title = "workflow" })
						return
					end
					local ok3, note = pcall(vim.json.decode, out2)
					if ok3 and note and note.path then
						vim.cmd("edit " .. vim.fn.fnameescape(note.path))
					else
						vim.notify("No file path for note " .. src_id, vim.log.levels.WARN, { title = "workflow" })
					end
				end)
			end,
		})
	end)
end

return M
