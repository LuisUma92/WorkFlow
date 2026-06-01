-- lua/workflow/bib_import.lua
-- Import the first ```bib fenced block in the current buffer via
-- `workflow prisma bib import --stdin --json`.

local server = require("workflow.server")

local M = {}

--- Extract the content of the first ```bib (or ~~~bib) fenced block from a
--- list of buffer lines.  Returns the inner text as a single string (lines
--- joined with "\n"), or nil when no block is found.
---@param lines string[]
---@return string|nil
function M._extract_bib_block(lines)
	local inside = false
	local inner = {}
	for _, line in ipairs(lines) do
		if not inside then
			if line:match("^```bib%s*$") or line:match("^~~~bib%s*$") then
				inside = true
			end
		else
			-- Closing fence: ``` or ~~~ (any trailing whitespace allowed)
			if line:match("^```%s*$") or line:match("^~~~%s*$") then
				return table.concat(inner, "\n")
			end
			table.insert(inner, line)
		end
	end
	return nil
end

--- Import the first ```bib block found in the current buffer.
--- Shells out to `workflow prisma bib import --stdin --json` and notifies
--- the result.  If no bib block is found the function returns early with an
--- INFO notification.
---@param opts table|nil  optional config overrides (passed to config.resolve)
function M.import_current_buffer(opts)
	opts = opts or {}

	local lines = vim.api.nvim_buf_get_lines(0, 0, -1, false)
	local bib_text = M._extract_bib_block(lines)

	if bib_text == nil then
		vim.notify(
			"no `bib` block found",
			vim.log.levels.INFO,
			{ title = "workflow" }
		)
		return
	end

	local config = require("workflow.config").resolve(opts)
	-- Attach stdin payload so server.run_cli sends it to the process.
	config.stdin = bib_text .. "\n"

	local args = { "prisma", "bib", "import", "--stdin", "--json" }

	server.run_cli(args, config, function(ok, output)
		if not ok then
			vim.notify(output, vim.log.levels.ERROR, { title = "workflow" })
			return
		end

		-- Attempt to parse summary counts from JSON output. `vim.json.decode`
		-- raises on non-JSON stdout, so guard it with pcall and fall back.
		local decoded_ok, decoded = pcall(vim.json.decode, output)
		if not (decoded_ok and type(decoded) == "table") then
			vim.notify(output, vim.log.levels.INFO, { title = "workflow" })
			return
		end

		-- `errors` is a JSON list in the CLI contract (may be a count in older
		-- shapes); normalise to a number before formatting.
		local created = decoded.created or 0
		local skipped = decoded.skipped or 0
		local errors = decoded.errors
		local err_count
		if type(errors) == "table" then
			err_count = #errors
		elseif type(errors) == "number" then
			err_count = errors
		else
			err_count = 0
		end

		vim.notify(
			string.format(
				"bib import: %d created, %d skipped, %d error(s)",
				created, skipped, err_count
			),
			vim.log.levels.INFO,
			{ title = "workflow" }
		)
	end)
end

return M
