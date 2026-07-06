-- lua/workflow/keymaps.lua
local M = {}

function M.setup(prefix, workflow)
	local opts = { noremap = true, silent = true }

	vim.keymap.set("n", prefix .. "sn", function()
		workflow.sync_current()
	end, vim.tbl_extend("force", opts, { desc = "workflow: sync DB" }))
	vim.keymap.set("n", prefix .. "se", function()
		workflow.sync_current_exercise()
	end, vim.tbl_extend("force", opts, { desc = "workflow: sync exercise DB" }))
	vim.keymap.set("n", prefix .. "v", function()
		workflow.validate_frontmatter()
	end, vim.tbl_extend("force", opts, { desc = "workflow: validate frontmatter" }))
	vim.keymap.set("n", prefix .. "p", function()
		workflow.promote_note()
	end, vim.tbl_extend("force", opts, { desc = "workflow: promote fleeting → permanent" }))

	-- Snacks pickers (Phase 3)
	vim.keymap.set("n", prefix .. "te", function()
		workflow.pick_evaluations()
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick evaluations" }))
	vim.keymap.set("n", prefix .. "ti", function()
		workflow.pick_items()
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick items" }))
	vim.keymap.set("n", prefix .. "tc", function()
		workflow.pick_courses()
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick courses" }))

	-- Notes keymaps (ITEP-0011/0012/0013)
	vim.keymap.set("n", prefix .. "np", function()
		workflow.pick_notes()
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick notes" }))
	vim.keymap.set("n", prefix .. "ns", function()
		workflow.sync_notes()
	end, vim.tbl_extend("force", opts, { desc = "workflow: sync notes" }))
	vim.keymap.set("n", prefix .. "nn", function()
		vim.ui.input({ prompt = "Note id (blank to auto-generate): " }, function(id)
			vim.ui.input({ prompt = "Note title: " }, function(title)
				if title and title ~= "" then
					workflow.new_note(id ~= "" and id or nil, title, {})
				end
			end)
		end)
	end, vim.tbl_extend("force", opts, { desc = "workflow: new note" }))
	vim.keymap.set("n", prefix .. "nt", function()
		vim.ui.input({ prompt = "Tags (+add -remove): " }, function(input)
			if not input or input == "" then
				return
			end
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
			workflow.tag_note(nil, add_tags, remove_tags, {})
		end)
	end, vim.tbl_extend("force", opts, { desc = "workflow: tag current note" }))
	vim.keymap.set("n", prefix .. "nl", function()
		vim.ui.input({ prompt = "Link kind (concept/reference/exercise): " }, function(kind)
			if not kind or kind == "" then
				return
			end
			vim.ui.input({ prompt = "Value: " }, function(value)
				if not value or value == "" then
					return
				end
				workflow.link_note(nil, kind, value, {})
			end)
		end)
	end, vim.tbl_extend("force", opts, { desc = "workflow: link current note" }))
	vim.keymap.set("n", prefix .. "ne", function()
		workflow.pick_edges()
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick note edges" }))
	vim.keymap.set("n", prefix .. "nc", function()
		workflow.edges_check()
	end, vim.tbl_extend("force", opts, { desc = "workflow: check note edge cycles" }))

	-- Wave 5 EDITOR keymaps
	-- <prefix>en — generate a fresh zettel_id and insert at cursor
	vim.keymap.set("n", prefix .. "en", function()
		workflow.insert_new_id({})
	end, vim.tbl_extend("force", opts, { desc = "workflow: insert new zettel_id at cursor" }))

	-- <prefix>er — pick relation_type from live enums and insert at cursor
	vim.keymap.set("n", prefix .. "er", function()
		workflow.pick_relation_type({})
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick relation_type (enums)" }))

	-- <prefix>ec — pick edge_class from live enums and insert at cursor
	vim.keymap.set("n", prefix .. "ec", function()
		workflow.pick_edge_class({})
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick edge_class (enums)" }))

	-- <prefix>eg — manual graph validate for current buffer
	vim.keymap.set("n", prefix .. "eg", function()
		workflow.validate_graph({})
	end, vim.tbl_extend("force", opts, { desc = "workflow: graph-validate current note" }))

	-- <prefix>ei — pick a note by zettel_id, insert the id at cursor
	vim.keymap.set("n", prefix .. "ei", function()
		workflow.pick_notes({ mode = "insert_id" })
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick note, insert zettel_id" }))

	-- <prefix>eI — pick a note, insert as full YAML `- id: …\n  type: …` item
	vim.keymap.set("n", prefix .. "eI", function()
		workflow.pick_notes({ mode = "insert_yaml" })
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick note, insert YAML item" }))

	-- <prefix>eb — pick a bibkey (yanks to + register; see picker/prisma_bib.lua)
	vim.keymap.set("n", prefix .. "eb", function()
		workflow.pick_prisma_bib({})
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick bibkey" }))

	-- <prefix>ek — pick a concept code, insert at cursor
	vim.keymap.set("n", prefix .. "ek", function()
		workflow.pick_concepts({})
	end, vim.tbl_extend("force", opts, { desc = "workflow: pick concept code" }))

	-- <prefix>nC — capture note from... (TODO: CLI lands in a parallel track; do not bind yet)
end

return M
