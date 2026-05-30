-- nvim-plugin/tests/plenary/picker/concepts_spec.lua
-- Plenary busted unit tests for workflow.picker.concepts
-- Stubs: server.run_cli, config.resolve, vim.notify, _G.Snacks

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

local CONCEPT_JSON = vim.json.encode({
  { domain = "Información", code = "CONC-001", label = "Newton's Laws", id = 50 },
  { domain = "Procedimiento Mental", code = "CONC-002", label = "Integration", id = 51 },
})

-- ---------------------------------------------------------------------------
-- Suite
-- ---------------------------------------------------------------------------

describe("workflow.picker.concepts", function()
  local concepts
  local server
  local config_mod

  local orig_run_cli
  local orig_config_resolve
  local orig_notify
  local orig_snacks

  local captured_spec
  local notify_calls

  before_each(function()
    -- Bust module cache.
    package.loaded["workflow.picker.concepts"] = nil
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
      cb(true, CONCEPT_JSON)
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

    concepts = require("workflow.picker.concepts")
  end)

  after_each(function()
    server.run_cli        = orig_run_cli
    config_mod.resolve    = orig_config_resolve
    vim.notify            = orig_notify
    _G.Snacks             = orig_snacks

    package.loaded["workflow.picker.concepts"] = nil
    package.loaded["workflow.server"]          = nil
    package.loaded["workflow.config"]          = nil
  end)

  -- -------------------------------------------------------------------------
  -- Case 1: contract — items built correctly from JSON
  -- -------------------------------------------------------------------------
  it("builds items with correct text and item fields from JSON", function()
    concepts.pick({})

    assert.is_not_nil(captured_spec, "Snacks.picker should have been called")
    assert.equals(2, #captured_spec.items)

    local item1 = captured_spec.items[1]
    assert.equals("[Información] CONC-001  Newton's Laws (id=50)", item1.text)
    assert.equals(50,         item1.item.id)
    assert.equals("CONC-001", item1.item.code)

    local item2 = captured_spec.items[2]
    assert.equals("[Procedimiento Mental] CONC-002  Integration (id=51)", item2.text)
    assert.equals(51,         item2.item.id)
  end)

  -- -------------------------------------------------------------------------
  -- Case 2: main_topic filter — opt forwarded into CLI args
  -- -------------------------------------------------------------------------
  it("forwards main_topic opt into CLI args", function()
    local captured_args
    server.run_cli = function(args, cfg, cb)
      captured_args = args
      cb(true, CONCEPT_JSON)
    end

    concepts.pick({ main_topic = "FIS001" })

    assert.is_not_nil(captured_args)
    local found_flag  = false
    local found_value = false
    for i, v in ipairs(captured_args) do
      if v == "--main-topic" then
        found_flag  = true
        found_value = (captured_args[i + 1] == "FIS001")
      end
    end
    assert.is_true(found_flag,  "--main-topic flag should be in args")
    assert.is_true(found_value, "--main-topic value should be 'FIS001'")
  end)

  -- -------------------------------------------------------------------------
  -- Case 3: confirm — inserts concept code slug into buffer at cursor
  -- -------------------------------------------------------------------------
  it("confirm() inserts concept code string into current buffer at cursor", function()
    concepts.pick({})

    assert.is_not_nil(captured_spec)

    local buf = vim.api.nvim_create_buf(false, true)
    vim.api.nvim_set_current_buf(buf)
    -- "prefix|" — cursor on '|' at col 6; code "CONC-001" inserts before it.
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "prefix|" })
    vim.api.nvim_win_set_cursor(0, { 1, 6 })

    local fake_picker = { close = function() end }
    captured_spec.confirm(fake_picker, captured_spec.items[1])

    local line = vim.api.nvim_buf_get_lines(buf, 0, 1, false)[1]
    -- "CONC-001" inserted at col 6 → "prefixCONC-001|"
    assert.equals("prefixCONC-001|", line)

    vim.api.nvim_buf_delete(buf, { force = true })
  end)

  -- -------------------------------------------------------------------------
  -- Case 4: empty — "[]" triggers "No concepts found." notify
  -- -------------------------------------------------------------------------
  it("notifies 'No concepts found.' when CLI returns empty array", function()
    server.run_cli = function(args, cfg, cb)
      cb(true, "[]")
    end

    concepts.pick({})

    assert.is_nil(captured_spec, "Snacks.picker should NOT be called for empty results")

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("No concepts found") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'No concepts found.' notification")
  end)

  -- -------------------------------------------------------------------------
  -- Case 5: snacks-guard — nil Snacks triggers notify, no error raised
  -- -------------------------------------------------------------------------
  it("notifies 'snacks.nvim picker not loaded' when _G.Snacks is nil", function()
    _G.Snacks = nil

    local ok, err = pcall(function()
      concepts.pick({})
    end)

    assert.is_true(ok, "concepts.pick() must not raise an error: " .. tostring(err))

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
