-- lua/workflow/tex_paths.lua
-- Neovim-facing glue for LaTeX path-macro expansion.
--
-- tex_macros.lua is pure string handling; this module supplies it with the
-- macros that actually exist in the user's project (buffer, vimtex main file,
-- WorkFlow .sty dirs) and exposes an `includeexpr` wrapper.
--
-- Design rule (see tasks/plans/2026-08-19-tex-gf-macro-expansion.md): we WRAP
-- `includeexpr` instead of remapping `gf`, so vimtex's resolution (kpsewhich,
-- $TEXINPUTS, .bib, \subimport) and every builtin that consults `includeexpr`
-- (`gf`, `gF`, `[f`, `<C-w>f`, `:checkpath`, `<C-x><C-i>`) keep working.

local tex_macros = require("workflow.tex_macros")

local M = {}

-- Fallback used when the caller passes no sty dirs.  P2 will feed the real
-- value from config.lua (`tex_macro_sty_dirs`); the default mirrors it so the
-- module is useful standalone.
local DEFAULT_STY_DIRS = { "~/.local/share/workflow/sty" }

-- Cache of scanned .sty dirs: resolved_dir -> { signature = "...", macros = {} }.
-- Invalidated by a signature built from every .sty file's mtime (a dir mtime
-- alone does not change when a file inside is edited in place).
local sty_cache = {}

-- Previous `includeexpr` per buffer, saved by P2's FileType autocmd.
local previous_expr = {}

local function resolve_bufnr(bufnr)
	if bufnr == nil or bufnr == 0 then
		return vim.api.nvim_get_current_buf()
	end
	return bufnr
end

-- Merge `src` into `dst` WITHOUT overwriting: first definition wins overall,
-- which is why callers must merge sources in precedence order.
local function merge_keep_first(dst, src)
	for name, value in pairs(src) do
		if dst[name] == nil then
			dst[name] = value
		end
	end
end

-- Save (or clear, with nil) the `includeexpr` that was in effect before we
-- installed ours.  P2 calls this from the FileType autocmd.
function M.set_buf_previous(bufnr, expr)
	previous_expr[resolve_bufnr(bufnr)] = expr
end

function M.get_buf_previous(bufnr)
	return previous_expr[resolve_bufnr(bufnr)]
end

-- Drop the .sty scan cache.  Tests use it; nothing in normal operation needs
-- it because the mtime signature already invalidates stale entries.
function M.clear_cache()
	sty_cache = {}
end

local function scan_buffer(bufnr)
	local ok, lines = pcall(vim.api.nvim_buf_get_lines, resolve_bufnr(bufnr), 0, -1, false)
	if not ok then
		return {}
	end
	return tex_macros.scan_macros(lines)
end

-- Macros from the vimtex project main file, when vimtex is present and knows
-- one.  Guarded: vimtex may be absent, or the buffer may have no state yet.
local function scan_vimtex_main(bufnr)
	bufnr = resolve_bufnr(bufnr)
	local ok, state = pcall(function()
		return vim.b[bufnr].vimtex
	end)
	if not ok or type(state) ~= "table" then
		return {}
	end
	local main = state.tex or state.main
	if type(main) ~= "string" or main == "" or vim.fn.filereadable(main) ~= 1 then
		return {}
	end
	local read_ok, lines = pcall(vim.fn.readfile, main)
	if not read_ok or type(lines) ~= "table" then
		return {}
	end
	return tex_macros.scan_macros(lines)
end

local function dir_signature(files)
	local parts = {}
	for _, file in ipairs(files) do
		local stat = vim.uv.fs_stat(file)
		local mtime = stat and stat.mtime and stat.mtime.sec or 0
		parts[#parts + 1] = file .. ":" .. tostring(mtime)
	end
	return table.concat(parts, "|")
end

-- Scan every *.sty under one directory, cached by mtime signature.
local function scan_sty_dir(dir)
	local resolved = vim.fn.expand(dir)
	if vim.fn.isdirectory(resolved) ~= 1 then
		return {}
	end

	local files = vim.fn.glob(resolved .. "/*.sty", true, true)
	table.sort(files)
	local signature = dir_signature(files)

	local cached = sty_cache[resolved]
	if cached and cached.signature == signature then
		return cached.macros
	end

	local macros = {}
	for _, file in ipairs(files) do
		local ok, lines = pcall(vim.fn.readfile, file)
		if ok and type(lines) == "table" then
			merge_keep_first(macros, tex_macros.scan_macros(lines))
		end
	end

	sty_cache[resolved] = { signature = signature, macros = macros }
	return macros
end

-- Gather every macro visible to `bufnr`, in precedence order:
--   1. the buffer itself (always re-scanned, never cached)
--   2. the vimtex project main file, if vimtex is loaded
--   3. the configured .sty dirs (cached by mtime)
-- First definition wins overall, so a local \def beats a shipped .sty.
function M.collect_macros(bufnr, opts)
	opts = opts or {}
	local sty_dirs = opts.sty_dirs or DEFAULT_STY_DIRS

	local macros = {}
	merge_keep_first(macros, scan_buffer(bufnr))
	merge_keep_first(macros, scan_vimtex_main(bufnr))
	for _, dir in ipairs(sty_dirs) do
		merge_keep_first(macros, scan_sty_dir(dir))
	end
	return macros
end

-- Evaluate the saved previous `includeexpr` (typically
-- `vimtex#include#expr()`), which reads `v:fname` itself.  Never throws.
local function delegate(bufnr, fname)
	local saved = previous_expr[bufnr]
	if type(saved) ~= "string" or saved == "" then
		return fname
	end
	local ok, result = pcall(vim.fn.eval, saved)
	if ok and type(result) == "string" and result ~= "" then
		return result
	end
	return fname
end

-- The `includeexpr` wrapper itself.
--
-- `fname` defaults to `vim.v.fname` so the option can be set to
-- `v:lua.require'workflow.tex_paths'.includeexpr()`; the explicit parameter
-- exists so the logic is testable without Neovim setting `v:fname` for us.
function M.includeexpr(fname, opts)
	fname = fname or vim.v.fname
	if type(fname) ~= "string" or fname == "" then
		return fname
	end

	local bufnr = vim.api.nvim_get_current_buf()

	local ok, expanded = pcall(function()
		return tex_macros.expand(fname, M.collect_macros(bufnr, opts))
	end)

	if ok and expanded ~= fname and vim.fn.filereadable(expanded) == 1 then
		return expanded
	end

	return delegate(bufnr, fname)
end

return M
