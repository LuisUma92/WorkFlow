-- lua/workflow/picker/search.lua
-- Snacks.picker for `workflow notes search <query> --json` (Wave 1 Phase 3b).
--
-- Prompts for a query via vim.ui.input, runs the FTS5 bm25-ranked search,
-- and renders results (title + snippet) in a Snacks picker.  <CR> opens the
-- matched note file.
--
-- CLI JSON contract (`workflow notes search QUERY --json`):
--   {"query": "...", "results": [
--     {"note_id": N, "zettel_id": "...", "title": "...", "path": "...",
--      "snippet": "...<b>match</b>...", "rank": -0.00123},
--     ...
--   ]}
-- `path` is vault-relative (e.g. "20260607-ReglasDeKirchhoff.md").

local server = require("workflow.server")

local M = {}

--- Strip <b>/</b> highlight tags the CLI wraps around matched terms.
---@param s string|nil
---@return string
local function _strip_bold_tags(s)
	if not s or s == "" then
		return ""
	end
	return (s:gsub("</?b>", ""))
end

--- Resolve a (possibly vault-relative) note path to an absolute path.
---@param path string
---@param vault_root string|nil
---@return string
local function _resolve_note_path(path, vault_root)
	local expanded = vim.fn.expand(path)
	if vim.startswith(expanded, "/") then
		return expanded
	end
	if vault_root then
		return vim.fn.expand(vault_root) .. "/" .. expanded
	end
	return expanded
end

--- Prompt for a query and open a Snacks picker over `workflow notes search`.
---@param opts table|nil  opts.limit overrides --limit (default CLI: 20)
function M.pick(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	vim.ui.input({ prompt = "Search notes: " }, function(query)
		if not query or query == "" then
			return
		end

		local args = { "notes", "search", query, "--json" }
		if opts.limit then
			table.insert(args, "--limit")
			table.insert(args, tostring(opts.limit))
		end

		server.run_cli(args, config, function(ok, output)
			if not ok then
				vim.notify("notes search error:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
				return
			end

			local ok_json, decoded = pcall(vim.json.decode, output)
			if not ok_json or type(decoded) ~= "table" then
				vim.notify("Invalid JSON from CLI: " .. tostring(output), vim.log.levels.ERROR, { title = "workflow" })
				return
			end

			local results = decoded.results or {}
			if #results == 0 then
				vim.notify("No notes matched: " .. query, vim.log.levels.INFO, { title = "workflow" })
				return
			end

			local items = {}
			for _, entry in ipairs(results) do
				local snippet = _strip_bold_tags(entry.snippet):gsub("%s+", " "):gsub("^%s+", "")
				table.insert(items, {
					text = string.format(
						"%s — %s",
						entry.title or entry.zettel_id or "(no title)",
						snippet
					),
					item = entry,
				})
			end

			local ok_snacks, Snacks = pcall(require, "snacks")
			if not ok_snacks or not Snacks or not Snacks.picker then
				vim.notify(
					"snacks.nvim is required for pickers (https://github.com/folke/snacks.nvim)",
					vim.log.levels.ERROR,
					{ title = "workflow" }
				)
				return
			end

			Snacks.picker({
				title = "Search notes: " .. query,
				items = items,
				format = function(item)
					return { { item.text } }
				end,
				preview = function(ctx)
					local e = ctx.item.item
					local lines = {
						string.format("zettel_id: %s", e.zettel_id or "?"),
						string.format("title:     %s", e.title or "(no title)"),
						string.format("path:      %s", e.path or "?"),
						string.format("rank:      %s", tostring(e.rank)),
						"",
						"---",
						"",
						_strip_bold_tags(e.snippet),
					}
					return lines
				end,
				confirm = function(picker, item)
					picker:close()
					if not item or not item.item or not item.item.path then
						return
					end
					local resolved = _resolve_note_path(item.item.path, config.vault_root)
					if
						require("workflow.config").is_in_workspace(resolved, config.vault_root)
						or require("workflow.config").is_in_workspace(resolved, config.workspace_dir)
					then
						vim.cmd("edit " .. vim.fn.fnameescape(resolved))
					else
						vim.notify(
							"Path outside workspace — refusing to open: " .. resolved,
							vim.log.levels.ERROR,
							{ title = "workflow" }
						)
					end
				end,
			})
		end)
	end)
end

return M
