-- nvim-plugin/tests/plenary/picker/content_bib_spec.lua
-- Plenary busted unit tests for workflow.picker.content_bib
-- Stubs: server.run_cli, config.resolve, frontmatter.extract, vim.notify, _G.Snacks

require("plenary.busted")

local assert = require("luassert")

-- Ensure the plugin lua dir is on package.path so require() finds workflow.*
-- modules even when run via plenary's loadfile() in a headless context.
do
  local script = debug.getinfo(1, "S").source:sub(2)
  local spec_dir = script:match("(.*/)")
  local lua_dir = vim.fn.fnamemodify(spec_dir .. "../../../lua", ":p"):gsub("/$", "")
  local entry = lua_dir .. "/?.lua;" .. lua_dir .. "/?/init.lua"
  if not package.path:find(lua_dir, 1, true) then
    package.path = entry .. ";" .. package.path
  end
end

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

local BIB_JSON = vim.json.encode({
  {
    bib_entry_bibkey = "Smith2020",
    chapter_number   = 3,
    section_number   = 2,
    first_page       = 45,
    last_page        = 60,
    content_id       = 7,
  },
  {
    bib_entry_bibkey = "Jones2019",
    chapter_number   = 1,
    section_number   = 1,
    first_page       = 1,
    last_page        = 10,
    content_id       = 7,
  },
})

-- ---------------------------------------------------------------------------
-- Suite
-- ---------------------------------------------------------------------------

describe("workflow.picker.content_bib", function()
  local content_bib
  local server
  local config_mod
  local frontmatter_mod

  local orig_run_cli
  local orig_config_resolve
  local orig_notify
  local orig_snacks

  local captured_spec
  local notify_calls

  before_each(function()
    -- Bust module cache.
    package.loaded["workflow.picker.content_bib"] = nil
    package.loaded["workflow.server"]             = nil
    package.loaded["workflow.config"]             = nil
    package.loaded["workflow.frontmatter"]        = nil

    server     = require("workflow.server")
    config_mod = require("workflow.config")

    -- Stub frontmatter so content_bib doesn't need a real buffer with YAML.
    package.loaded["workflow.frontmatter"] = {
      extract = function(_buf) return nil end,
    }
    frontmatter_mod = package.loaded["workflow.frontmatter"]

    orig_run_cli        = server.run_cli
    orig_config_resolve = config_mod.resolve
    orig_notify         = vim.notify
    orig_snacks         = _G.Snacks

    -- Default stubs.
    server.run_cli = function(args, cfg, cb)
      cb(true, BIB_JSON)
    end

    config_mod.resolve = function(_) return {} end

    captured_spec = nil
    _G.Snacks = {
      picker = function(spec)
        captured_spec = spec
      end,
    }

    notify_calls = {}
    vim.notify = function(msg, level, opts)
      table.insert(notify_calls, { msg = msg, level = level, opts = opts })
    end

    content_bib = require("workflow.picker.content_bib")
  end)

  after_each(function()
    server.run_cli        = orig_run_cli
    config_mod.resolve    = orig_config_resolve
    vim.notify            = orig_notify
    _G.Snacks             = orig_snacks

    package.loaded["workflow.picker.content_bib"] = nil
    package.loaded["workflow.server"]             = nil
    package.loaded["workflow.config"]             = nil
    package.loaded["workflow.frontmatter"]        = nil
  end)

  -- -------------------------------------------------------------------------
  -- Case 1: contract — items built correctly from JSON
  -- -------------------------------------------------------------------------
  it("builds items with correct text and item fields from JSON", function()
    content_bib.pick({ content_id = 7 })

    assert.is_not_nil(captured_spec, "Snacks.picker should have been called")
    assert.equals(2, #captured_spec.items)

    local item1 = captured_spec.items[1]
    assert.equals("[Smith2020]  ch.3 §2  pp.45-60", item1.text)
    assert.equals("Smith2020",  item1.item.bib_entry_bibkey)
    assert.equals(7,            item1.item.content_id)

    local item2 = captured_spec.items[2]
    assert.equals("[Jones2019]  ch.1 §1  pp.1-10", item2.text)
    assert.equals("Jones2019",  item2.item.bib_entry_bibkey)
  end)

  -- -------------------------------------------------------------------------
  -- Case 2: content_id forwarded into CLI args
  -- -------------------------------------------------------------------------
  it("forwards content_id into CLI args as positional argument", function()
    local captured_args
    server.run_cli = function(args, cfg, cb)
      captured_args = args
      cb(true, BIB_JSON)
    end

    content_bib.pick({ content_id = 7 })

    assert.is_not_nil(captured_args)
    -- Expected args: { "content", "bib-links", "--json", "7" }
    local found = false
    for _, v in ipairs(captured_args) do
      if v == "7" then found = true end
    end
    assert.is_true(found, "content_id '7' should appear as positional arg in CLI args")
    assert.equals("bib-links", captured_args[2])
  end)

  -- -------------------------------------------------------------------------
  -- Case 3: confirm — inserts bibkey into buffer at cursor
  -- -------------------------------------------------------------------------
  it("confirm() inserts bibkey string into current buffer at cursor", function()
    content_bib.pick({ content_id = 7 })

    assert.is_not_nil(captured_spec)

    local buf = vim.api.nvim_create_buf(false, true)
    vim.api.nvim_set_current_buf(buf)
    -- "prefix|" — cursor on '|' at col 6; bibkey "Smith2020" inserts before it.
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "prefix|" })
    vim.api.nvim_win_set_cursor(0, { 1, 6 })

    local fake_picker = { close = function() end }
    captured_spec.confirm(fake_picker, captured_spec.items[1])

    local line = vim.api.nvim_buf_get_lines(buf, 0, 1, false)[1]
    -- "Smith2020" inserted at col 6 → "prefixSmith2020|"
    assert.equals("prefixSmith2020|", line)

    vim.api.nvim_buf_delete(buf, { force = true })
  end)

  -- -------------------------------------------------------------------------
  -- Case 4: empty — "[]" triggers "No bib links found." notify
  -- -------------------------------------------------------------------------
  it("notifies 'No bib links found.' when CLI returns empty array", function()
    server.run_cli = function(args, cfg, cb)
      cb(true, "[]")
    end

    content_bib.pick({ content_id = 7 })

    assert.is_nil(captured_spec, "Snacks.picker should NOT be called for empty results")

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("No bib links found") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'No bib links found.' notification")
  end)

  -- -------------------------------------------------------------------------
  -- Case 5: missing content_id — notifies and returns early (no CLI call)
  -- -------------------------------------------------------------------------
  it("notifies when content_id is missing and does not call run_cli", function()
    -- frontmatter stub returns nil (already default), no content_id opt passed.
    local cli_called = false
    server.run_cli = function(args, cfg, cb)
      cli_called = true
      cb(true, BIB_JSON)
    end

    local ok, err = pcall(function()
      content_bib.pick({})
    end)

    assert.is_true(ok, "pick() must not raise: " .. tostring(err))
    assert.is_false(cli_called, "run_cli should not be called when content_id is missing")

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("content_id required") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'content_id required' notification")
  end)

  -- -------------------------------------------------------------------------
  -- Case 6: snacks-guard — nil Snacks triggers notify, no error raised
  -- -------------------------------------------------------------------------
  it("notifies 'snacks.nvim is required for pickers' when _G.Snacks is nil", function()
    _G.Snacks = nil

    local ok, err = pcall(function()
      content_bib.pick({ content_id = 7 })
    end)

    assert.is_true(ok, "content_bib.pick() must not raise an error: " .. tostring(err))

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("snacks.nvim is required for pickers") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'snacks.nvim is required for pickers' notification")
  end)
end)
