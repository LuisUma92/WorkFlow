-- nvim-plugin/tests/plenary/picker/contents_spec.lua
-- Plenary busted unit tests for workflow.picker.contents
-- Stubs: server.run_cli, config.resolve, vim.notify, _G.Snacks

require("plenary.busted")

local assert = require("luassert")

-- Ensure the plugin lua dir is on package.path so require() finds workflow.*
-- modules even when run via plenary's loadfile() in a headless context.
do
  local script = debug.getinfo(1, "S").source:sub(2)
  local spec_dir = script:match("(.*/)")
  -- spec_dir: .../nvim-plugin/tests/plenary/picker/
  -- plugin lua dir: four levels up + /lua
  local lua_dir = vim.fn.fnamemodify(spec_dir .. "../../../lua", ":p"):gsub("/$", "")
  local entry = lua_dir .. "/?.lua;" .. lua_dir .. "/?/init.lua"
  if not package.path:find(lua_dir, 1, true) then
    package.path = entry .. ";" .. package.path
  end
end

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

local CONTENT_JSON = vim.json.encode({
  { topic_id = 3, name = "Kinematics", id = 101 },
  { topic_id = 3, name = "Dynamics",   id = 102 },
})

-- ---------------------------------------------------------------------------
-- Suite
-- ---------------------------------------------------------------------------

describe("workflow.picker.contents", function()
  local contents
  local server
  local config_mod

  local orig_run_cli
  local orig_config_resolve
  local orig_notify
  local orig_snacks

  local captured_spec
  local notify_calls

  before_each(function()
    -- Bust the module cache on every test.
    package.loaded["workflow.picker.contents"] = nil
    package.loaded["workflow.server"]          = nil
    package.loaded["workflow.config"]          = nil

    server     = require("workflow.server")
    config_mod = require("workflow.config")

    orig_run_cli        = server.run_cli
    orig_config_resolve = config_mod.resolve
    orig_notify         = vim.notify
    orig_snacks         = _G.Snacks

    -- Default stubs.
    server.run_cli = function(args, cfg, cb)
      cb(true, CONTENT_JSON)
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

    contents = require("workflow.picker.contents")
  end)

  after_each(function()
    server.run_cli        = orig_run_cli
    config_mod.resolve    = orig_config_resolve
    vim.notify            = orig_notify
    _G.Snacks             = orig_snacks

    package.loaded["workflow.picker.contents"] = nil
    package.loaded["workflow.server"]          = nil
    package.loaded["workflow.config"]          = nil
  end)

  -- -------------------------------------------------------------------------
  -- Case 1: contract — items built correctly from JSON
  -- -------------------------------------------------------------------------
  it("builds items with correct text and item fields from JSON", function()
    contents.pick({})

    assert.is_not_nil(captured_spec, "Snacks.picker should have been called")
    assert.equals(2, #captured_spec.items)

    local item1 = captured_spec.items[1]
    assert.equals("topic=3  Kinematics (id=101)", item1.text)
    assert.equals(101, item1.item.id)
    assert.equals(3,   item1.item.topic_id)

    local item2 = captured_spec.items[2]
    assert.equals("topic=3  Dynamics (id=102)", item2.text)
    assert.equals(102, item2.item.id)
  end)

  -- -------------------------------------------------------------------------
  -- Case 2: topic_id filter — opt forwarded into CLI args
  -- -------------------------------------------------------------------------
  it("forwards topic_id opt into CLI args", function()
    local captured_args
    server.run_cli = function(args, cfg, cb)
      captured_args = args
      cb(true, CONTENT_JSON)
    end

    contents.pick({ topic_id = 7 })

    assert.is_not_nil(captured_args)
    local found_flag  = false
    local found_value = false
    for i, v in ipairs(captured_args) do
      if v == "--topic-id" then
        found_flag  = true
        found_value = (captured_args[i + 1] == "7")
      end
    end
    assert.is_true(found_flag,  "--topic-id flag should be in args")
    assert.is_true(found_value, "--topic-id value should be '7'")
  end)

  -- -------------------------------------------------------------------------
  -- Case 3: confirm — inserts content id into buffer at cursor
  -- -------------------------------------------------------------------------
  it("confirm() inserts content id string into current buffer at cursor", function()
    contents.pick({})

    assert.is_not_nil(captured_spec)

    local buf = vim.api.nvim_create_buf(false, true)
    vim.api.nvim_set_current_buf(buf)
    -- "prefix|" — cursor on '|' at col 6; id "101" inserts before it.
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "prefix|" })
    vim.api.nvim_win_set_cursor(0, { 1, 6 })

    local fake_picker = { close = function() end }
    captured_spec.confirm(fake_picker, captured_spec.items[1])

    local line = vim.api.nvim_buf_get_lines(buf, 0, 1, false)[1]
    -- "101" inserted at col 6 → "prefix101|"
    assert.equals("prefix101|", line)

    vim.api.nvim_buf_delete(buf, { force = true })
  end)

  -- -------------------------------------------------------------------------
  -- Case 4: empty — "[]" triggers "No contents found." notify
  -- -------------------------------------------------------------------------
  it("notifies 'No contents found.' when CLI returns empty array", function()
    server.run_cli = function(args, cfg, cb)
      cb(true, "[]")
    end

    contents.pick({})

    assert.is_nil(captured_spec, "Snacks.picker should NOT be called for empty results")

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("No contents found") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'No contents found.' notification")
  end)

  -- -------------------------------------------------------------------------
  -- Case 5: snacks-guard — nil Snacks triggers notify, no error raised
  -- -------------------------------------------------------------------------
  it("notifies 'snacks.nvim picker not loaded' when _G.Snacks is nil", function()
    _G.Snacks = nil

    local ok, err = pcall(function()
      contents.pick({})
    end)

    assert.is_true(ok, "contents.pick() must not raise an error: " .. tostring(err))

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("snacks.nvim picker not loaded") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'snacks.nvim picker not loaded' notification")
  end)
end)
