-- lua/workflow/validate.lua
-- Graph validation: runs `workflow validate notes <path> --graph --json`
-- and surfaces results as Neovim diagnostics (dedicated namespace).
-- Opt-in via config.auto_graph_validate_on_save (default true for vault notes).

local server = require("workflow.server")

local M = {}

-- Dedicated diagnostic namespace; created once.
local _ns = vim.api.nvim_create_namespace("workflow_graph_validate")

--- Map a severity string to vim.diagnostic severity constant.
---@param sev string|nil  "error" | "warning" | "info" | nil
---@return integer
local function _sev(sev)
	if sev == "error" then
		return vim.diagnostic.severity.ERROR
	elseif sev == "warning" or sev == "warn" then
		return vim.diagnostic.severity.WARN
	else
		return vim.diagnostic.severity.INFO
	end
end

--- Parse the JSON output from `workflow validate notes <path> --graph --json`.
--- Accepted shape (flexible – handles both flat and nested formats):
---   { "files": [{"path":..,"errors":[..],"warnings":[..]}],
---     "graph_issues": [{"severity":..,"message":..}],
---     "issues": [...],   -- flat alternative
---     "valid": bool }
---@param raw string  raw stdout from CLI
---@param buf_path string  absolute path of the validated buffer
---@return table  list of vim.diagnostic-style dicts
local function _parse_diagnostics(raw, buf_path)
	local diags = {}
	local ok, data = pcall(vim.json.decode, raw)
	if not ok or type(data) ~= "table" then
		-- Non-JSON output: treat whole output as a single error diagnostic.
		table.insert(diags, {
			lnum = 0,
			col = 0,
			severity = vim.diagnostic.severity.ERROR,
			message = "validate: " .. raw,
			source = "workflow",
		})
		return diags
	end

	-- Per-file errors / warnings.
	local files = data.files or {}
	for _, entry in ipairs(files) do
		local lnum = 0
		local col = 0
		if entry.line then
			lnum = (entry.line or 1) - 1
		end
		for _, msg in ipairs(entry.errors or {}) do
			table.insert(diags, {
				lnum = lnum, col = col,
				severity = vim.diagnostic.severity.ERROR,
				message = msg,
				source = "workflow",
			})
		end
		for _, msg in ipairs(entry.warnings or {}) do
			table.insert(diags, {
				lnum = lnum, col = col,
				severity = vim.diagnostic.severity.WARN,
				message = msg,
				source = "workflow",
			})
		end
	end

	-- Flat "issues" list.
	for _, issue in ipairs(data.issues or {}) do
		local msg = type(issue) == "string" and issue or (issue.message or tostring(issue))
		local lnum = issue.line and (issue.line - 1) or 0
		table.insert(diags, {
			lnum = lnum, col = 0,
			severity = _sev(issue.severity),
			message = msg,
			source = "workflow",
		})
	end

	-- Vault-wide graph issues (not tied to a specific line).
	for _, issue in ipairs(data.graph_issues or {}) do
		local msg = type(issue) == "string" and issue or (issue.message or tostring(issue))
		table.insert(diags, {
			lnum = 0, col = 0,
			severity = _sev(issue.severity),
			message = "[graph] " .. msg,
			source = "workflow",
		})
	end

	return diags
end

--- Run graph validation on `bufnr` and set diagnostics.
--- config is the resolved workflow config table.
---@param bufnr integer  buffer number (0 = current)
---@param config table
function M.validate_buffer(bufnr, config)
	bufnr = (bufnr == nil or bufnr == 0) and vim.api.nvim_get_current_buf() or bufnr
	local path = vim.api.nvim_buf_get_name(bufnr)
	if not path or path == "" then
		vim.notify("No file in buffer — cannot graph-validate", vim.log.levels.WARN, { title = "workflow" })
		return
	end
	if vim.fn.fnamemodify(path, ":e"):lower() ~= "md" then
		return -- silently skip non-markdown buffers
	end
	local expanded = vim.fn.expand(path)
	local args = { "validate", "notes", expanded, "--graph", "--json" }
	server.run_cli(args, config, function(ok, output)
		-- ok=false means non-zero exit (can happen even with JSON on validation errors)
		-- Still try to parse the output for diagnostics.
		local diags = _parse_diagnostics(output, expanded)
		vim.schedule(function()
			vim.diagnostic.set(_ns, bufnr, diags, {})
			if #diags > 0 then
				local nerr = 0
				local nwarn = 0
				for _, d in ipairs(diags) do
					if d.severity == vim.diagnostic.severity.ERROR then
						nerr = nerr + 1
					else
						nwarn = nwarn + 1
					end
				end
				vim.notify(
					string.format("workflow validate: %d error(s), %d warning(s)", nerr, nwarn),
					nerr > 0 and vim.log.levels.WARN or vim.log.levels.INFO,
					{ title = "workflow" }
				)
			else
				vim.notify("workflow validate: OK", vim.log.levels.INFO, { title = "workflow" })
			end
		end)
	end)
end

--- Clear diagnostics for `bufnr`.
---@param bufnr integer|nil
function M.clear(bufnr)
	bufnr = bufnr or vim.api.nvim_get_current_buf()
	vim.diagnostic.set(_ns, bufnr, {}, {})
end

--- Return the diagnostic namespace id (for testing / external use).
function M.namespace()
	return _ns
end

return M
