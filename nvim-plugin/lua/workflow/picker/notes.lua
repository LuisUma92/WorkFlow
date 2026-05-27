-- lua/workflow/picker/notes.lua
-- Snacks.picker for `workflow notes list --json`
-- Filters: tag, concept, note_type, candidate_project
-- Preview: frontmatter table + first 30 body lines
-- <CR>: edit note file; <C-t>: tag prompt; <C-l>: link prompt

local server = require("workflow.server")

local M = {}

---@param opts table|nil  tag, concept, note_type, candidate_project filter keys
function M.pick(opts)
	opts = opts or {}
	local config = require("workflow.config").resolve(opts)
	local vault = config.vault_root and vim.fn.expand(config.vault_root) or nil

	local args = { "notes", "list", "--json" }
	if vault then
		table.insert(args, "--dir")
		table.insert(args, vault)
	end
	if opts.tag then
		table.insert(args, "--tag")
		table.insert(args, opts.tag)
	end
	if opts.concept then
		table.insert(args, "--concept")
		table.insert(args, opts.concept)
	end
	if opts.note_type then
		table.insert(args, "--note-type")
		table.insert(args, opts.note_type)
	end
	if opts.candidate_project then
		table.insert(args, "--candidate-project")
		table.insert(args, opts.candidate_project)
	end

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify("Failed to list notes:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		local ok_json, decoded = pcall(vim.json.decode, output)
		if not ok_json or not decoded then
			vim.notify("Invalid JSON from CLI", vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		if #decoded == 0 then
			vim.notify("No notes found.", vim.log.levels.INFO, { title = "workflow" })
			return
		end

		local items = {}
		for _, entry in ipairs(decoded) do
			table.insert(items, {
				text = string.format("[%s] %s — %s", entry.id or "?", entry.title or "(no title)", entry.type or "?"),
				item = entry,
			})
		end

		local ok_snacks, Snacks = pcall(require, "snacks")
		if not ok_snacks or not Snacks or not Snacks.picker then
			vim.notify("snacks.nvim is required for pickers (https://github.com/folke/snacks.nvim)", vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		Snacks.picker({
			title = "Notes",
			items = items,
			format = function(item)
				return { { item.text } }
			end,
			preview = function(ctx)
				local e = ctx.item.item
				local lines = {
					string.format("id:       %s", e.id or "?"),
					string.format("title:    %s", e.title or "(no title)"),
					string.format("type:     %s", e.type or "?"),
				}
				if e.tags and #e.tags > 0 then
					table.insert(lines, "tags:     " .. table.concat(e.tags, ", "))
				end
				if e.concepts and #e.concepts > 0 then
					table.insert(lines, "concepts: " .. table.concat(e.concepts, ", "))
				end
				table.insert(lines, "")
				table.insert(lines, "---")
				table.insert(lines, "")
				if e.path and e.path ~= "" then
					local expanded = vim.fn.expand(e.path)
					if require("workflow.config").is_in_workspace(expanded, config.vault_root) or require("workflow.config").is_in_workspace(expanded, config.workspace_dir) then
						local body = vim.fn.readfile(expanded, "", 30)
						for _, l in ipairs(body) do
							table.insert(lines, l)
						end
					else
						table.insert(lines, "(path outside workspace — not displayed)")
					end
				end
				return lines
			end,
			confirm = function(picker, item)
				picker:close()
				if item and item.item and item.item.path then
					local expanded = vim.fn.expand(item.item.path)
					if require("workflow.config").is_in_workspace(expanded, config.vault_root) or require("workflow.config").is_in_workspace(expanded, config.workspace_dir) then
						vim.cmd("edit " .. vim.fn.fnameescape(expanded))
					else
						vim.notify("Path outside workspace — refusing to open: " .. expanded, vim.log.levels.ERROR, { title = "workflow" })
					end
				elseif item then
					vim.notify("No file path for note " .. (item.item.id or "?"), vim.log.levels.WARN, { title = "workflow" })
				end
			end,
			keys = {
				["<C-t>"] = {
					desc = "Tag note",
					action = function(picker, item)
						picker:close()
						if not item then return end
						vim.ui.input({ prompt = "Tags (+add -remove): " }, function(input)
							if not input or input == "" then return end
							local add_tags, remove_tags = {}, {}
							for token in input:gmatch("%S+") do
								if token:sub(1, 1) == "+" then
									table.insert(add_tags, token:sub(2))
								elseif token:sub(1, 1) == "-" then
									table.insert(remove_tags, token:sub(2))
								else
									table.insert(add_tags, token)
								end
							end
							require("workflow.notes").tag(item.item.id, add_tags, remove_tags, opts)
						end)
					end,
				},
				["<C-l>"] = {
					desc = "Link note",
					action = function(picker, item)
						picker:close()
						if not item then return end
						vim.ui.input({ prompt = "Link kind (concept/reference/exercise): " }, function(kind)
							if not kind or kind == "" then return end
							vim.ui.input({ prompt = "Value: " }, function(value)
								if not value or value == "" then return end
								require("workflow.notes").link(item.item.id, kind, value, opts)
							end)
						end)
					end,
				},
			},
		})
	end)
end

return M
