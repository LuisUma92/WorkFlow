-- lua/workflow/picker/content_bib.lua
-- Snacks.picker for bib links attached to a content node.
-- <CR> inserts the bibkey at cursor (frontmatter / LaTeX authoring workflow).

local server = require("workflow.server")

local M = {}

---@param opts table|nil picker opts. Recognises `content_id` (integer).
function M.pick(opts)
	opts = opts or {}

	-- Fallback: read content_id from current buffer frontmatter.
	if not opts.content_id then
		local data = require("workflow.frontmatter").extract(vim.api.nvim_get_current_buf())
		if data and data.content_id then
			opts.content_id = tonumber(data.content_id)
		end
	end

	if not opts.content_id then
		vim.notify(
			"content_id required (pass content-id=N or set in frontmatter)",
			vim.log.levels.ERROR,
			{ title = "workflow" }
		)
		return
	end

	local config = require("workflow.config").resolve(opts)

	local args = { "content", "bib-links", "--json", tostring(opts.content_id) }

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify(
				"Failed to list bib links:\n" .. output,
				vim.log.levels.ERROR,
				{ title = "workflow" }
			)
			return
		end

		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json or not decoded or #decoded == 0 then
			if not ok_json then
				vim.notify("Invalid response from CLI", vim.log.levels.ERROR, { title = "workflow" })
			else
				vim.notify("No bib links found.", vim.log.levels.INFO, { title = "workflow" })
			end
			return
		end

		local items = {}
		for _, entry in ipairs(decoded) do
			local ch = entry.chapter_number or "?"
			local sec = entry.section_number or "?"
			local fp = entry.first_page or "?"
			local lp = entry.last_page or "?"
			local row_text = string.format(
				"[%s]  ch.%s §%s  pp.%s-%s",
				entry.bib_entry_bibkey,
				tostring(ch),
				tostring(sec),
				tostring(fp),
				tostring(lp)
			)
			table.insert(items, {
				text = row_text,
				item = entry,
			})
		end

		local ok_snacks, _ = pcall(function() return Snacks end)
		if not ok_snacks or not Snacks then
			vim.notify("snacks.nvim is required for pickers", vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		Snacks.picker({
			title = "Bib Links (content " .. tostring(opts.content_id) .. ")",
			items = items,
			format = function(item)
				return { { item.text } }
			end,
			confirm = function(picker, item)
				picker:close()
				if item then
					local bibkey = tostring(item.item.bib_entry_bibkey)
					local row, col = unpack(vim.api.nvim_win_get_cursor(0))
					vim.api.nvim_buf_set_text(0, row - 1, col, row - 1, col, { bibkey })
					vim.api.nvim_win_set_cursor(0, { row, col + #bibkey })
					vim.fn.setreg('"', bibkey)
					vim.fn.setreg("+", bibkey)
				end
			end,
		})
	end)
end

return M
