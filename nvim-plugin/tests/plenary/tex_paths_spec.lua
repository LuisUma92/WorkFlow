-- nvim-plugin/tests/plenary/tex_paths_spec.lua
-- Plenary busted tests for workflow.tex_paths (Neovim-facing glue over tex_macros).
-- minimal_init.lua centralizes package.path, so no per-spec bootstrap is needed.

require("plenary.busted")

local assert = require("luassert")
local tp = require("workflow.tex_paths")

-- All generated fixtures live under tests/outputs/ (repo rule).
local script_dir = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
local repo_root = vim.fn.fnamemodify(script_dir .. "../../..", ":p"):gsub("/$", "")
local out_root = repo_root .. "/tests/outputs/tex_gf"
local sty_dir = out_root .. "/sty"
local img_dir = out_root .. "/img"

local function write_file(path, lines)
  vim.fn.mkdir(vim.fn.fnamemodify(path, ":h"), "p")
  vim.fn.writefile(lines, path)
end

local function make_buf(lines)
  local bufnr = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(bufnr, 0, -1, false, lines or {})
  return bufnr
end

local function setup_fixtures()
  vim.fn.mkdir(sty_dir, "p")
  vim.fn.mkdir(img_dir, "p")
  write_file(sty_dir .. "/SetCommands.sty", {
    "% fixture mirroring share/latex/sty/SetCommands.sty:8-10",
    "\\newcommand{\\FisicaDir}{" .. out_root .. "}",
    "\\newcommand{\\IMGfolder}{\\FisicaDir/img}",
    "% \\newcommand{\\IMGfolder}{/mnt/c/bogus}",
    "\\newcommand{\\StyOnly}{/sty/only}",
  })
  write_file(img_dir .. "/diagram.tex", { "% readable target" })
end

setup_fixtures()

describe("workflow.tex_paths.collect_macros", function()
  before_each(function()
    tp.clear_cache()
  end)

  it("picks up a \\def from the buffer", function()
    local bufnr = make_buf({ "\\def\\FSfolder{/home/luis/01-U/0000EE}" })
    local m = tp.collect_macros(bufnr, { sty_dirs = {} })
    assert.are.equal("/home/luis/01-U/0000EE", m["\\FSfolder"])
  end)

  it("picks up \\FisicaDir and \\IMGfolder from a sty dir", function()
    local bufnr = make_buf({})
    local m = tp.collect_macros(bufnr, { sty_dirs = { sty_dir } })
    assert.are.equal(out_root, m["\\FisicaDir"])
    assert.are.equal("\\FisicaDir/img", m["\\IMGfolder"])
  end)

  it("expands \\IMGfolder nested through \\FisicaDir", function()
    local bufnr = make_buf({})
    local m = tp.collect_macros(bufnr, { sty_dirs = { sty_dir } })
    local tm = require("workflow.tex_macros")
    assert.are.equal(out_root .. "/img", tm.expand("\\IMGfolder", m))
  end)

  it("ignores a commented-out redefinition in the sty file", function()
    local m = tp.collect_macros(make_buf({}), { sty_dirs = { sty_dir } })
    assert.is_nil(m["\\IMGfolder"]:match("bogus"))
  end)

  it("lets a buffer definition win over the sty definition", function()
    local bufnr = make_buf({ "\\def\\FisicaDir{/buffer/wins}" })
    local m = tp.collect_macros(bufnr, { sty_dirs = { sty_dir } })
    assert.are.equal("/buffer/wins", m["\\FisicaDir"])
    -- non-conflicting sty macros are still merged in
    assert.are.equal("/sty/only", m["\\StyOnly"])
  end)

  it("returns the same macros on a second (cached) call", function()
    local bufnr = make_buf({})
    local first = tp.collect_macros(bufnr, { sty_dirs = { sty_dir } })
    local second = tp.collect_macros(bufnr, { sty_dirs = { sty_dir } })
    assert.are.same(first, second)
  end)

  it("tolerates a nonexistent sty dir", function()
    local m = tp.collect_macros(make_buf({}), { sty_dirs = { out_root .. "/nope" } })
    assert.are.same({}, m)
  end)
end)

describe("workflow.tex_paths.includeexpr", function()
  before_each(function()
    tp.clear_cache()
  end)

  it("returns the expanded path when the file is readable", function()
    local bufnr = make_buf({ "\\def\\FSfolder{" .. img_dir .. "}" })
    vim.api.nvim_set_current_buf(bufnr)
    local got = tp.includeexpr("\\FSfolder/diagram.tex", { sty_dirs = {} })
    assert.are.equal(img_dir .. "/diagram.tex", got)
  end)

  it("delegates to the saved expr when the expanded path is not readable", function()
    local bufnr = make_buf({ "\\def\\FSfolder{" .. img_dir .. "}" })
    vim.api.nvim_set_current_buf(bufnr)
    tp.set_buf_previous(bufnr, '"delegated-result.tex"')
    local got = tp.includeexpr("\\FSfolder/missing.tex", { sty_dirs = {} })
    assert.are.equal("delegated-result.tex", got)
  end)

  it("returns fname unchanged when there is no saved expr", function()
    local bufnr = make_buf({})
    vim.api.nvim_set_current_buf(bufnr)
    tp.set_buf_previous(bufnr, nil)
    assert.are.equal("amsmath", tp.includeexpr("amsmath", { sty_dirs = {} }))
  end)

  it("does not error when the saved expr is garbage", function()
    local bufnr = make_buf({})
    vim.api.nvim_set_current_buf(bufnr)
    tp.set_buf_previous(bufnr, "this is not ((valid vimscript")
    local ok, got
    ok, got = pcall(tp.includeexpr, "nowhere.tex", { sty_dirs = {} })
    assert.is_true(ok)
    assert.are.equal("nowhere.tex", got)
  end)

  it("does not error when the saved expr is an empty string", function()
    local bufnr = make_buf({})
    vim.api.nvim_set_current_buf(bufnr)
    tp.set_buf_previous(bufnr, "")
    assert.are.equal("nowhere.tex", tp.includeexpr("nowhere.tex", { sty_dirs = {} }))
  end)

  it("keeps saved exprs separate per buffer", function()
    local a = make_buf({})
    local b = make_buf({})
    tp.set_buf_previous(a, '"from-a"')
    tp.set_buf_previous(b, '"from-b"')
    vim.api.nvim_set_current_buf(b)
    assert.are.equal("from-b", tp.includeexpr("x.tex", { sty_dirs = {} }))
    vim.api.nvim_set_current_buf(a)
    assert.are.equal("from-a", tp.includeexpr("x.tex", { sty_dirs = {} }))
  end)
end)
