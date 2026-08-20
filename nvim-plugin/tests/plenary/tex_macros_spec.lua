-- nvim-plugin/tests/plenary/tex_macros_spec.lua
-- Plenary busted unit tests for workflow.tex_macros (pure Lua, no Neovim API).
-- minimal_init.lua centralizes package.path, so no per-spec bootstrap is needed.

require("plenary.busted")

local assert = require("luassert")
local tm = require("workflow.tex_macros")

describe("workflow.tex_macros.strip_comments", function()
  it("drops everything from an unescaped % onward", function()
    assert.are.equal("\\def\\A{/x} ", tm.strip_comments("\\def\\A{/x} % ojo"))
  end)

  it("keeps an escaped \\% and the text after it", function()
    assert.are.equal("50\\% off ", tm.strip_comments("50\\% off % nota"))
  end)

  it("returns an empty string for a fully commented line", function()
    assert.are.equal("", tm.strip_comments("% \\newcommand{\\AAfolder}{/mnt/c}"))
  end)

  it("leaves a comment-free line untouched", function()
    assert.are.equal("\\input{\\FSfolder/a.tex}", tm.strip_comments("\\input{\\FSfolder/a.tex}"))
  end)
end)

describe("workflow.tex_macros.scan_macros", function()
  it("reads \\def\\FOO{bar}", function()
    local m = tm.scan_macros({ "\\def\\FSfolder{/home/luis/01-U/0000EE}" })
    assert.are.equal("/home/luis/01-U/0000EE", m["\\FSfolder"])
  end)

  it("reads all five definition forms", function()
    local m = tm.scan_macros({
      "\\def\\A{/a}",
      "\\newcommand{\\B}{/b}",
      "\\newcommand\\C{/c}",
      "\\providecommand{\\D}{/d}",
      "\\renewcommand{\\E}{/e}",
    })
    assert.are.equal("/a", m["\\A"])
    assert.are.equal("/b", m["\\B"])
    assert.are.equal("/c", m["\\C"])
    assert.are.equal("/d", m["\\D"])
    assert.are.equal("/e", m["\\E"])
  end)

  it("accepts leading indentation (as in SetCommands.sty)", function()
    local m = tm.scan_macros({ "  \\newcommand{\\FisicaDir}{/home/luis/01-U}" })
    assert.are.equal("/home/luis/01-U", m["\\FisicaDir"])
  end)

  it("ignores a commented-out definition (TNN.tex:251 regression)", function()
    local m = tm.scan_macros({
      "\\newcommand{\\AAfolder}{/home/luis/Documents/00-00AA-Apuntes}",
      "% \\newcommand{\\AAfolder}{/mnt/c/MyFiles/Documents}",
    })
    assert.are.equal("/home/luis/Documents/00-00AA-Apuntes", m["\\AAfolder"])
  end)

  it("keeps the FIRST definition when a name is defined twice", function()
    local m = tm.scan_macros({
      "\\newcommand{\\F}{/first}",
      "\\newcommand{\\F}{/second}",
    })
    assert.are.equal("/first", m["\\F"])
  end)

  it("ignores macros that take arguments", function()
    local m = tm.scan_macros({ "\\newcommand{\\labq}[2]{\\texttt{`#1(#2)'}}" })
    assert.is_nil(m["\\labq"])
  end)

  it("accepts @ in a macro name", function()
    local m = tm.scan_macros({ "\\def\\my@dir{/at}" })
    assert.are.equal("/at", m["\\my@dir"])
  end)

  it("returns an empty table when there is nothing to find", function()
    assert.are.same({}, tm.scan_macros({ "\\section{Vectores}" }))
  end)
end)

describe("workflow.tex_macros.expand", function()
  it("substitutes a single macro", function()
    local m = { ["\\FSfolder"] = "/home/luis/01-U/0000EE" }
    assert.are.equal(
      "/home/luis/01-U/0000EE/Vectores.tex",
      tm.expand("\\FSfolder/Vectores.tex", m)
    )
  end)

  it("resolves nested macros (\\IMGfolder → \\FisicaDir)", function()
    local m = {
      ["\\FisicaDir"] = "/home/luis/01-U",
      ["\\IMGfolder"] = "\\FisicaDir/0000II-ImagesFigures",
    }
    assert.are.equal(
      "/home/luis/01-U/0000II-ImagesFigures/fig.png",
      tm.expand("\\IMGfolder/fig.png", m)
    )
  end)

  it("does not bite a longer macro sharing a prefix", function()
    local m = { ["\\FSfolder"] = "/short", ["\\FSfolderTwo"] = "/long" }
    assert.are.equal("/long/a.tex", tm.expand("\\FSfolderTwo/a.tex", m))
    assert.are.equal("/short/a.tex", tm.expand("\\FSfolder/a.tex", m))
  end)

  it("gives up instead of hanging on a self-referential macro", function()
    local m = { ["\\A"] = "\\A/x" }
    local out = tm.expand("\\A/f.tex", m)
    assert.is_string(out)
  end)

  it("leaves an unknown macro untouched", function()
    assert.are.equal("\\Nope/a.tex", tm.expand("\\Nope/a.tex", {}))
  end)

  it("is a no-op on a plain relative path", function()
    assert.are.equal("eval/01_vectores/a.tex", tm.expand("eval/01_vectores/a.tex", {}))
  end)
end)
