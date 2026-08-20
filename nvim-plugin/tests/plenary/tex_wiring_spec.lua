-- nvim-plugin/tests/plenary/tex_wiring_spec.lua
-- Plenary busted tests for P2 wiring: config keys + the FileType tex autocmd
-- that wraps `includeexpr` with workflow.tex_paths.
-- minimal_init.lua centralizes package.path, so no per-spec bootstrap is needed.

require("plenary.busted")

local assert = require("luassert")
local config = require("workflow.config")
local autocmds = require("workflow.autocmds")
local tex_paths = require("workflow.tex_paths")

-- Any generated fixture belongs under tests/outputs/ (repo rule).
local script_dir = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
local repo_root = vim.fn.fnamemodify(script_dir .. "../../..", ":p"):gsub("/$", "")
local out_root = repo_root .. "/tests/outputs/tex_gf"

local function make_tex_buf()
	local bufnr = vim.api.nvim_create_buf(false, true)
	vim.api.nvim_set_current_buf(bufnr)
	return bufnr
end

-- FileType autocmds match on the filetype string, so the event is fired with
-- pattern = "tex" against the current buffer (args.buf defaults to it) — the
-- same shape Neovim uses when 'filetype' is actually set.
local function fire_filetype(bufnr)
	vim.api.nvim_set_current_buf(bufnr)
	vim.api.nvim_exec_autocmds("FileType", { pattern = "tex" })
	-- The wrapper is (re-)asserted from vim.schedule(), on purpose: the runtime
	-- / vimtex ftplugin for tex sets 'includeexpr' after our callback and would
	-- otherwise clobber us.  Let the scheduled callbacks run.
	vim.wait(200, function()
		return vim.bo[bufnr].includeexpr:find("workflow.tex_paths", 1, true) ~= nil
	end, 5)
	vim.wait(20)
end

describe("workflow.config tex keys", function()
	it("defaults tex_gf to true", function()
		local cfg = config.resolve({})
		assert.is_true(cfg.tex_gf)
	end)

	it("defaults tex_macro_sty_dirs to the workflow sty dir", function()
		local cfg = config.resolve({})
		assert.are.same({ "~/.local/share/workflow/latex/sty", "~/.local/share/workflow/sty" }, cfg.tex_macro_sty_dirs)
	end)

	it("lets the user override tex_macro_sty_dirs", function()
		local cfg = config.resolve({ tex_macro_sty_dirs = { out_root .. "/sty" } })
		assert.are.same({ out_root .. "/sty" }, cfg.tex_macro_sty_dirs)
	end)

	it("lets the user disable tex_gf", function()
		assert.is_false(config.resolve({ tex_gf = false }).tex_gf)
	end)
end)

describe("workflow.autocmds tex includeexpr wiring", function()
	before_each(function()
		tex_paths.clear_cache()
	end)

	after_each(function()
		-- Leave no live FileType tex autocmd behind for the next spec file.
		vim.api.nvim_create_augroup("Workflow", { clear = true })
	end)

	it("points includeexpr at workflow.tex_paths after FileType tex", function()
		autocmds.setup(config.resolve({ tex_macro_sty_dirs = { out_root .. "/sty" } }))
		local bufnr = make_tex_buf()
		vim.bo[bufnr].includeexpr = "vimtex#include#expr()"
		fire_filetype(bufnr)
		assert.is_truthy(vim.bo[bufnr].includeexpr:find("workflow.tex_paths", 1, true))
	end)

	it("threads the configured sty dirs into the includeexpr call", function()
		autocmds.setup(config.resolve({ tex_macro_sty_dirs = { out_root .. "/sty" } }))
		local bufnr = make_tex_buf()
		fire_filetype(bufnr)
		assert.is_truthy(vim.bo[bufnr].includeexpr:find(out_root .. "/sty", 1, true))
	end)

	it("never saves our own expr as previous, however often it fires", function()
		autocmds.setup(config.resolve({}))
		local bufnr = make_tex_buf()
		fire_filetype(bufnr)
		fire_filetype(bufnr)
		fire_filetype(bufnr)
		local saved = tex_paths.get_buf_previous(bufnr)
		assert.is_string(saved)
		assert.is_nil(saved:find("workflow.tex_paths", 1, true))
	end)

	it("re-asserts itself after the ftplugin clobbers includeexpr", function()
		autocmds.setup(config.resolve({}))
		local bufnr = make_tex_buf()
		fire_filetype(bufnr)
		-- The tex ftplugin really does clobber our synchronous assignment (it
		-- runs after our callback on every FileType tex); only the scheduled
		-- re-assert survives it, and the clobbering expr becomes "previous".
		vim.bo[bufnr].includeexpr = "vimtex#include#expr()"
		fire_filetype(bufnr)
		assert.is_truthy(vim.bo[bufnr].includeexpr:find("workflow.tex_paths", 1, true))
		local saved = tex_paths.get_buf_previous(bufnr)
		assert.is_string(saved)
		assert.is_nil(saved:find("workflow.tex_paths", 1, true))
	end)

	it("leaves includeexpr alone when tex_gf is false", function()
		autocmds.setup(config.resolve({ tex_gf = false }))
		local bufnr = make_tex_buf()
		vim.api.nvim_set_current_buf(bufnr)
		vim.api.nvim_exec_autocmds("FileType", { pattern = "tex" })
		vim.wait(50)
		assert.is_nil(vim.bo[bufnr].includeexpr:find("workflow.tex_paths", 1, true))
	end)
end)

-- attach_tex carries the save/idempotency contract; testing it directly keeps
-- those assertions free of whatever the runtime tex ftplugin does to the option.
describe("workflow.autocmds.attach_tex", function()
	it("saves the previous includeexpr for the buffer", function()
		local bufnr = make_tex_buf()
		vim.bo[bufnr].includeexpr = "vimtex#include#expr()"
		autocmds.attach_tex(bufnr, {})
		assert.are.equal("vimtex#include#expr()", tex_paths.get_buf_previous(bufnr))
		assert.is_truthy(vim.bo[bufnr].includeexpr:find("workflow.tex_paths", 1, true))
	end)

	it("is idempotent: a second attach keeps the original previous", function()
		local bufnr = make_tex_buf()
		vim.bo[bufnr].includeexpr = "vimtex#include#expr()"
		autocmds.attach_tex(bufnr, {})
		autocmds.attach_tex(bufnr, {})
		assert.are.equal("vimtex#include#expr()", tex_paths.get_buf_previous(bufnr))
	end)

	it("tolerates an invalid buffer", function()
		local bufnr = vim.api.nvim_create_buf(false, true)
		vim.api.nvim_buf_delete(bufnr, { force = true })
		assert.is_true(pcall(autocmds.attach_tex, bufnr, {}))
	end)

	it("does not touch non-tex buffers", function()
		autocmds.setup(config.resolve({}))
		local bufnr = vim.api.nvim_create_buf(false, true)
		vim.api.nvim_set_current_buf(bufnr)
		vim.bo[bufnr].includeexpr = ""
		vim.api.nvim_exec_autocmds("FileType", { pattern = "markdown" })
		assert.are.equal("", vim.bo[bufnr].includeexpr)
	end)
end)
