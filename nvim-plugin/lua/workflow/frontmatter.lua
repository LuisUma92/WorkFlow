-- lua/workflow/frontmatter.lua
-- YAML frontmatter extraction and validation

local M = {}

local VALID_NOTE_TYPES = { permanent = true, literature = true, fleeting = true }
local VALID_SOURCE_FORMATS = { md = true, tex = true }

local ns_id = vim.api.nvim_create_namespace("workflow_frontmatter")

function M.extract(bufnr)
	local lines = vim.api.nvim_buf_get_lines(bufnr, 0, 50, false)
	if #lines == 0 or vim.trim(lines[1]) ~= "---" then
		return nil, "No frontmatter delimiter found"
	end

	local end_line = nil
	for i = 2, #lines do
		if vim.trim(lines[i]) == "---" then
			end_line = i
			break
		end
	end

	if not end_line then
		return nil, "No closing frontmatter delimiter"
	end

	-- Flat key/value parser. Values stay strings: a zettel_id like 20240101
	-- must never be coerced to a number.
	local data = {}
	for _, line in ipairs(vim.list_slice(lines, 2, end_line - 1)) do
		local key, value = line:match("^(%w[%w_]*):(.*)$")
		if key then
			value = vim.trim(value)
			if value:match("^%[.*%]$") then
				local items = {}
				for item in value:sub(2, -2):gmatch("[^,]+") do
					table.insert(items, vim.trim(item))
				end
				data[key] = items
			elseif value == "" then
				data[key] = nil
			else
				data[key] = value
			end
		end
	end

	return data, nil, end_line
end

function M.validate(data)
	local errors = {}

	if not data.id or data.id == "" then
		table.insert(errors, "'id' is required")
	end
	if not data.title or data.title == "" then
		table.insert(errors, "'title' is required")
	end
	if data.type and not VALID_NOTE_TYPES[data.type] then
		table.insert(errors, "'type' must be permanent, literature, or fleeting")
	end

	return errors
end

function M.set_diagnostics(bufnr, errors)
	vim.diagnostic.reset(ns_id, bufnr)
	if #errors == 0 then
		return
	end

	local diagnostics = {}
	for _, err in ipairs(errors) do
		table.insert(diagnostics, {
			lnum = 0,
			col = 0,
			message = err,
			severity = vim.diagnostic.severity.WARN,
			source = "workflow",
		})
	end
	vim.diagnostic.set(ns_id, bufnr, diagnostics)
end

function M.validate_buffer(bufnr)
	local data, err = M.extract(bufnr)
	if not data then
		M.set_diagnostics(bufnr, { err })
		return
	end
	local errors = M.validate(data)
	M.set_diagnostics(bufnr, errors)
end

return M
