-- lua/workflow/server.lua
-- Server lifecycle management
--
-- Hybrid approach: sync/validate run as one-shot Python CLI calls
-- (reliable, no server process needed). The JSONL server is optional
-- for future Telescope/graph integration.

local M = {}

--- Run a workflow CLI command asynchronously.
--- Optional stdin: set config.stdin (string) to write text to the process's
--- stdin and close it after jobstart.  Existing 3-arg callers are unaffected
--- (nil config.stdin means no stdin is sent).
---@param args string[] CLI arguments after "workflow"
---@param config table workspace config (may include config.stdin: string|nil)
---@param on_done fun(ok: boolean, output: string)|nil
function M.run_cli(args, config, on_done)
	local cmd_path = vim.fn.expand(config.workflow_cmd or "~/.local/bin/workflow")
	local basename = vim.fn.fnamemodify(cmd_path, ":t")
	if basename ~= "workflow" then
		vim.notify(
			"workflow_cmd basename must be 'workflow' (got '" .. basename .. "')",
			vim.log.levels.ERROR,
			{ title = "workflow" }
		)
		return
	end
	local cmd = { cmd_path }
	for _, a in ipairs(args) do
		table.insert(cmd, a)
	end

	local stdout_chunks = {}
	local stderr_chunks = {}

	local expanded_cwd = config.workspace_dir and vim.fn.expand(config.workspace_dir) or nil
	local job_opts = {
		stdout_buffered = true,
		stderr_buffered = true,
		on_stdout = function(_, data)
			if data then
				for _, line in ipairs(data) do
					if line ~= "" then
						table.insert(stdout_chunks, line)
					end
				end
			end
		end,
		on_stderr = function(_, data)
			if data then
				for _, line in ipairs(data) do
					if line ~= "" then
						table.insert(stderr_chunks, line)
					end
				end
			end
		end,
		on_exit = function(_, code)
			if on_done then
				vim.schedule(function()
					local output = table.concat(stdout_chunks, "\n")
					if code ~= 0 then
						output = output .. "\n" .. table.concat(stderr_chunks, "\n")
					end
					on_done(code == 0, output)
				end)
			end
		end,
	}
	if expanded_cwd and vim.fn.isdirectory(expanded_cwd) == 1 then
		job_opts.cwd = expanded_cwd
	end
	local job = vim.fn.jobstart(cmd, job_opts)
	-- If a stdin payload is present, send it and close the channel.
	if job > 0 and config.stdin ~= nil then
		vim.fn.chansend(job, config.stdin)
		vim.fn.chanclose(job, "stdin")
	end
end

--- Sync notes in the vault
function M.sync(config)
	if not config.vault_root then
		vim.notify("No vault root configured", vim.log.levels.WARN, { title = "workflow" })
		return
	end
	local vault = vim.fn.expand(config.vault_root)
	-- --project-root is reserved/ignored by the CLI (ITEP-0011 P5); notes
	-- register against GlobalBase, so the vault root is the only argument.
	M.run_cli(
		{ "lectures", "scan", vault },
		config,
		function(ok, output)
			if ok then
				vim.notify("Synced", vim.log.levels.INFO, { title = "workflow" })
			else
				vim.notify("Sync error:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
			end
		end
	)
end

--- Sync current exercise file
function M.sync_exercise(config)
	local current_file = vim.api.nvim_buf_get_name(0)

	if current_file == "" then
		vim.notify("No file in current buffer", vim.log.levels.WARN, {
			title = "workflow",
		})
		return
	end

	if vim.fn.fnamemodify(current_file, ":e") ~= "tex" then
		vim.notify("Current buffer is not a .tex file", vim.log.levels.WARN, {
			title = "workflow",
		})
		return
	end

	M.run_cli({ "exercise", "sync", current_file }, config, function(ok, output)
		if ok then
			vim.notify("Exercise synced", vim.log.levels.INFO, {
				title = "workflow",
			})
		else
			vim.notify("Exercise sync error:\n" .. output, vim.log.levels.ERROR, {
				title = "workflow",
			})
		end
	end)
end

--- Status text for statusline (simplified — no server dependency)
function M.status_text()
	return "ZK"
end

function M.maybe_auto_start(config, bufnr)
	-- No-op: CLI approach doesn't need a persistent server
end

return M
