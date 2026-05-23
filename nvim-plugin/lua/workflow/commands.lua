-- lua/workflow/commands.lua
local M = {}

function M.setup(workflow)
	vim.api.nvim_create_user_command("WorkflowSync", function()
		workflow.sync_current()
	end, {})
	vim.api.nvim_create_user_command("WorkflowSyncExercise", function()
		workflow.sync_current_exercise()
	end, {})
	vim.api.nvim_create_user_command("WorkflowValidate", function()
		workflow.validate_frontmatter()
	end, {})
	vim.api.nvim_create_user_command("WorkflowPromote", function()
		workflow.promote_note()
	end, {})

	-- Snacks pickers (Phase 3)
	vim.api.nvim_create_user_command("WorkflowEvalPicker", function(cmd_opts)
		workflow.pick_evaluations({ inst = cmd_opts.fargs[1] })
	end, { nargs = "?" })
	vim.api.nvim_create_user_command("WorkflowItemPicker", function(cmd_opts)
		workflow.pick_items({ domain = cmd_opts.fargs[1], level = cmd_opts.fargs[2] })
	end, { nargs = "*" })
	vim.api.nvim_create_user_command("WorkflowCoursePicker", function(cmd_opts)
		workflow.pick_courses({ inst = cmd_opts.fargs[1] })
	end, { nargs = "?" })

	-- PRISMA pickers (P3)
	vim.api.nvim_create_user_command("WorkflowPrismaBibPicker", function(cmd_opts)
		local opts = {}
		for _, arg in ipairs(cmd_opts.fargs) do
			local k, v = arg:match("^(%w+)=(.+)$")
			if k and v then
				opts[k] = v
			end
		end
		workflow.pick_prisma_bib(opts)
	end, { nargs = "*" })
	-- Keyword picker takes no args (workspace-wide).
	vim.api.nvim_create_user_command("WorkflowPrismaKeywordPicker", function()
		workflow.pick_prisma_keywords({})
	end, { nargs = 0 })
	vim.api.nvim_create_user_command("WorkflowPrismaReviewPicker", function(cmd_opts)
		local kw_id = tonumber(cmd_opts.fargs[1])
		if not kw_id then
			vim.notify(
				"Usage: :WorkflowPrismaReviewPicker <keyword-id> [status]",
				vim.log.levels.ERROR,
				{ title = "workflow" }
			)
			return
		end
		workflow.pick_prisma_reviews({ keyword_id = kw_id, status = cmd_opts.fargs[2] })
	end, { nargs = "+" })

	-- Notes commands (ITEP-0011/0012/0013)

	-- :WorkflowNoteSync[!]  — ! adds --strict-concepts
	vim.api.nvim_create_user_command("WorkflowNoteSync", function(cmd_opts)
		workflow.sync_notes({ strict = cmd_opts.bang })
	end, { bang = true, nargs = 0 })

	-- :WorkflowNotePicker [key=value ...]
	vim.api.nvim_create_user_command("WorkflowNotePicker", function(cmd_opts)
		local opts = {}
		for _, arg in ipairs(cmd_opts.fargs) do
			local k, v = arg:match("^(%w+)=(.+)$")
			if k and v then
				opts[k] = v
			end
		end
		workflow.pick_notes(opts)
	end, { nargs = "*" })

	-- :WorkflowNoteShow [id]  — id optional; falls back to frontmatter
	vim.api.nvim_create_user_command("WorkflowNoteShow", function(cmd_opts)
		workflow.show_note(cmd_opts.fargs[1] or nil, {})
	end, { nargs = "?" })

	-- :WorkflowNoteTag {id} +tag1 -tag2 ...
	vim.api.nvim_create_user_command("WorkflowNoteTag", function(cmd_opts)
		local fargs = cmd_opts.fargs
		if #fargs < 1 then
			vim.notify("Usage: :WorkflowNoteTag {id} +tag1 -tag2 ...", vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local id = fargs[1]
		local add_tags, remove_tags = {}, {}
		for i = 2, #fargs do
			local token = fargs[i]
			if token:sub(1, 1) == "+" then
				table.insert(add_tags, token:sub(2))
			elseif token:sub(1, 1) == "-" then
				table.insert(remove_tags, token:sub(2))
			else
				table.insert(add_tags, token)
			end
		end
		workflow.tag_note(id, add_tags, remove_tags, {})
	end, { nargs = "+" })

	-- :WorkflowNoteLink {id} {concept|reference|exercise} {value} [remove]
	vim.api.nvim_create_user_command("WorkflowNoteLink", function(cmd_opts)
		local fargs = cmd_opts.fargs
		if #fargs < 3 then
			vim.notify(
				"Usage: :WorkflowNoteLink {id} {concept|reference|exercise} {value} [remove]",
				vim.log.levels.ERROR,
				{ title = "workflow" }
			)
			return
		end
		local link_opts = {}
		if fargs[4] and fargs[4]:lower() == "remove" then
			link_opts.remove = true
		end
		workflow.link_note(fargs[1], fargs[2], fargs[3], link_opts)
	end, { nargs = "+" })

	-- :WorkflowNoteNew {id} {title words ...}
	vim.api.nvim_create_user_command("WorkflowNoteNew", function(cmd_opts)
		local fargs = cmd_opts.fargs
		if #fargs < 1 then
			vim.notify("Usage: :WorkflowNoteNew {id} {title}", vim.log.levels.ERROR, { title = "workflow" })
			return
		end
		local id = fargs[1]
		local title_parts = {}
		for i = 2, #fargs do
			table.insert(title_parts, fargs[i])
		end
		local title = table.concat(title_parts, " ")
		workflow.new_note(id, title, {})
	end, { nargs = "+" })

	-- :WorkflowEdgesPicker [key=value ...]
	vim.api.nvim_create_user_command("WorkflowEdgesPicker", function(cmd_opts)
		local opts = {}
		for _, arg in ipairs(cmd_opts.fargs) do
			local k, v = arg:match("^(%w+)=(.+)$")
			if k and v then
				opts[k] = v
			end
		end
		workflow.pick_edges(opts)
	end, { nargs = "*" })

	-- :WorkflowEdgesCheck
	vim.api.nvim_create_user_command("WorkflowEdgesCheck", function()
		workflow.edges_check({})
	end, { nargs = 0 })
end

return M
