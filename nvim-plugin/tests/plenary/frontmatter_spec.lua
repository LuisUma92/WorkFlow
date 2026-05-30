-- nvim-plugin/tests/plenary/frontmatter_spec.lua
-- Plenary busted unit tests for workflow.frontmatter (hand-rolled YAML parser).
-- minimal_init.lua centralizes package.path, so no per-spec bootstrap is needed.

require("plenary.busted")

local assert = require("luassert")
local fm = require("workflow.frontmatter")

local function make_buf(lines)
  local buf = vim.api.nvim_create_buf(false, true)
  vim.api.nvim_buf_set_lines(buf, 0, -1, false, lines)
  return buf
end

local function contains(list, needle)
  for _, v in ipairs(list) do
    if v:find(needle, 1, true) then
      return true
    end
  end
  return false
end

describe("workflow.frontmatter.extract", function()
  it("parses a valid flat frontmatter block into a data table", function()
    local buf = make_buf({ "---", "id: 20240101", "title: Foo", "---", "body" })
    local data, err, end_line = fm.extract(buf)
    assert.is_nil(err)
    assert.are.equal("20240101", data.id)
    assert.are.equal("Foo", data.title)
    assert.are.equal(4, end_line)
  end)

  it("returns an error when the first line is not a delimiter", function()
    local buf = make_buf({ "id: x", "title: y" })
    local data, err = fm.extract(buf)
    assert.is_nil(data)
    assert.are.equal("No frontmatter delimiter found", err)
  end)

  it("returns an error when there is no closing delimiter", function()
    local buf = make_buf({ "---", "id: x", "title: y" })
    local data, err = fm.extract(buf)
    assert.is_nil(data)
    assert.are.equal("No closing frontmatter delimiter", err)
  end)

  it("parses a bracketed list value into a trimmed table", function()
    local buf = make_buf({ "---", "concepts: [a, b, c]", "---" })
    local data = fm.extract(buf)
    assert.are.same({ "a", "b", "c" }, data.concepts)
  end)

  it("drops keys whose value is empty", function()
    local buf = make_buf({ "---", "summary:", "id: 1", "title: T", "---" })
    local data = fm.extract(buf)
    assert.is_nil(data.summary)
    assert.are.equal("1", data.id)
  end)

  it("accepts underscore keys and ignores comment lines", function()
    local buf = make_buf({ "---", "main_topic: FI0001", "# just a comment", "---" })
    local data = fm.extract(buf)
    assert.are.equal("FI0001", data.main_topic)
    -- the comment line produced no key
    local n = 0
    for _ in pairs(data) do n = n + 1 end
    assert.are.equal(1, n)
  end)
end)

describe("workflow.frontmatter.validate", function()
  it("flags a missing id", function()
    local errors = fm.validate({ title = "T" })
    assert.is_true(contains(errors, "'id' is required"))
  end)

  it("flags a missing title", function()
    local errors = fm.validate({ id = "1" })
    assert.is_true(contains(errors, "'title' is required"))
  end)

  it("rejects an invalid note type but accepts a valid one", function()
    local bad = fm.validate({ id = "1", title = "T", type = "bogus" })
    assert.is_true(contains(bad, "permanent"))
    local ok = fm.validate({ id = "1", title = "T", type = "permanent" })
    assert.are.equal(0, #ok)
  end)

  it("returns no errors for a fully valid table", function()
    local errors = fm.validate({ id = "1", title = "T", type = "fleeting" })
    assert.are.equal(0, #errors)
  end)
end)
