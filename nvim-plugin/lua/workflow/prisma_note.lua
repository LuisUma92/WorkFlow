-- lua/workflow/prisma_note.lua
-- Generate literature notes from PRISMA-accepted bibliography entries (Wave C3).
--
-- Single:  workflow prisma bib accept-to-note <BIBKEY> --json
-- Bulk:    workflow prisma bib accept-to-note --all-accepted --keyword-id N --json

local server = require("workflow.server")

local M = {}

--- Open *path* in a vertical split.
---@param path string absolute path to the note file
local function _open_split(path)
	vim.cmd("vsplit " .. vim.fn.fnameescape(path))
end

--- Prompt for a bibkey (single) or keyword-id (bulk) and generate literature note(s).
---@param opts table|nil  extra overrides: vault_root, keyword_id (rarely used directly)
function M.accept_to_note(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)

	vim.ui.input({ prompt = "Bibkey (leave blank for bulk by keyword-id): " }, function(bibkey)
		if bibkey == nil then
			-- User cancelled (Esc / abort)
			return
		end

		if bibkey ~= "" then
			-- ── Single mode ───────────────────────────────────────────────────
			local args = { "prisma", "bib", "accept-to-note", bibkey, "--json" }
			if opts.keyword_id then
				table.insert(args, "--keyword-id")
				table.insert(args, tostring(opts.keyword_id))
			end
			if opts.vault_root then
				table.insert(args, "--vault-root")
				table.insert(args, opts.vault_root)
			end

			server.run_cli(args, config, function(ok, output)
				if not ok then
					vim.notify(output, vim.log.levels.ERROR, { title = "workflow" })
					return
				end
				local ok2, data = pcall(vim.fn.json_decode, output)
				if not ok2 or type(data) ~= "table" then
					vim.notify(
						"accept-to-note: unexpected JSON: " .. tostring(output),
						vim.log.levels.ERROR,
						{ title = "workflow" }
					)
					return
				end
				local note_path = data.note_path
				if not note_path then
					vim.notify(
						"accept-to-note: no note_path in response",
						vim.log.levels.ERROR,
						{ title = "workflow" }
					)
					return
				end
				local verb = data.created and "Created" or "Already exists"
				vim.notify(
					string.format("%s: %s", verb, note_path),
					vim.log.levels.INFO,
					{ title = "workflow" }
				)
				_open_split(note_path)
			end)

		else
			-- ── Bulk mode: prompt for keyword-id ─────────────────────────────
			vim.ui.input({ prompt = "Keyword ID (integer): " }, function(kw_input)
				if kw_input == nil or kw_input == "" then
					vim.notify(
						"accept-to-note: aborted (no keyword-id given)",
						vim.log.levels.WARN,
						{ title = "workflow" }
					)
					return
				end

				local args = {
					"prisma", "bib", "accept-to-note",
					"--all-accepted",
					"--keyword-id", kw_input,
					"--json",
				}
				if opts.vault_root then
					table.insert(args, "--vault-root")
					table.insert(args, opts.vault_root)
				end

				server.run_cli(args, config, function(ok, output)
					if not ok then
						vim.notify(output, vim.log.levels.ERROR, { title = "workflow" })
						return
					end
					local ok2, data = pcall(vim.fn.json_decode, output)
					if not ok2 or type(data) ~= "table" then
						vim.notify(
							"accept-to-note: unexpected JSON: " .. tostring(output),
							vim.log.levels.ERROR,
							{ title = "workflow" }
						)
						return
					end
					local created = data.created or 0
					local skipped = data.skipped or 0
					local notes   = data.notes   or {}

					vim.notify(
						string.format("accept-to-note: %d created, %d skipped", created, skipped),
						vim.log.levels.INFO,
						{ title = "workflow" }
					)

					if #notes == 0 then
						vim.notify(
							"accept-to-note: no notes generated",
							vim.log.levels.WARN,
							{ title = "workflow" }
						)
						return
					end
					-- Open the first note in a split.
					local first_path = notes[1].note_path
					if first_path then
						_open_split(first_path)
					end
				end)
			end)
		end
	end)
end

return M
