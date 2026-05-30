-- nvim-plugin/tests/plenary/picker/topics_spec.lua
-- Plenary busted unit tests for workflow.picker.topics
-- Stubs: server.run_cli, config.resolve, vim.notify, _G.Snacks

require("plenary.busted")

local assert = require("luassert")

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

local TOPIC_JSON = vim.json.encode({
  { discipline_area_code = "FIS", serial_number = 1, name = "Mechanics", id = 10 },
  { discipline_area_code = "FIS", serial_number = 2, name = "Thermodynamics", id = 20 },
})

local function make_notify_recorder()
  local calls = {}
  local orig = vim.notify
  vim.notify = function(msg, level, opts)
    table.insert(calls, { msg = msg, level = level, opts = opts })
  end
  return calls, orig
end

-- ---------------------------------------------------------------------------
-- Suite
-- ---------------------------------------------------------------------------

describe("workflow.picker.topics", function()
  local topics
  local server
  local config_mod

  local orig_run_cli
  local orig_config_resolve
  local orig_notify
  local orig_snacks

  local captured_spec
  local notify_calls

  before_each(function()
    -- Fresh module load on every test (bust the module cache).
    package.loaded["workflow.picker.topics"] = nil
    package.loaded["workflow.server"] = nil
    package.loaded["workflow.config"] = nil

    -- Load real modules so we can stub their fields.
    server = require("workflow.server")
    config_mod = require("workflow.config")

    -- Save originals.
    orig_run_cli = server.run_cli
    orig_config_resolve = config_mod.resolve
    orig_notify = vim.notify
    orig_snacks = _G.Snacks

    -- Default stubs (overridden per-test where needed).
    server.run_cli = function(args, cfg, cb)
      cb(true, TOPIC_JSON)
    end

    config_mod.resolve = function(opts)
      return {}
    end

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

    -- Now load the picker (it caches server/config references at require time,
    -- but the stub replaces the table field so the picker's upvalue still
    -- points to the same server table).
    topics = require("workflow.picker.topics")
  end)

  after_each(function()
    server.run_cli = orig_run_cli
    config_mod.resolve = orig_config_resolve
    vim.notify = orig_notify
    _G.Snacks = orig_snacks

    package.loaded["workflow.picker.topics"] = nil
    package.loaded["workflow.server"] = nil
    package.loaded["workflow.config"] = nil
  end)

  -- -------------------------------------------------------------------------
  -- Case 1: contract — items built correctly from JSON
  -- -------------------------------------------------------------------------
  it("builds items with correct text and item fields from JSON", function()
    topics.pick({})

    assert.is_not_nil(captured_spec, "Snacks.picker should have been called")
    assert.equals(2, #captured_spec.items)

    local item1 = captured_spec.items[1]
    assert.equals("[FIS] #1  Mechanics (id=10)", item1.text)
    assert.equals(10, item1.item.id)
    assert.equals("FIS", item1.item.discipline_area_code)

    local item2 = captured_spec.items[2]
    assert.equals("[FIS] #2  Thermodynamics (id=20)", item2.text)
    assert.equals(20, item2.item.id)
  end)

  -- -------------------------------------------------------------------------
  -- Case 2: insert — confirm() inserts topic id into buffer at cursor
  -- -------------------------------------------------------------------------
  it("confirm() inserts topic id string into current buffer at cursor", function()
    topics.pick({})

    assert.is_not_nil(captured_spec)

    -- Create a scratch buffer. Use a line that ends with a non-space char so
    -- nvim's column clipping doesn't interfere. We insert at col 13 (after
    -- "main_topic:  " — 13 chars, col 13 = one past last byte, valid because
    -- nvim allows cursor at len for insertion).
    -- Simpler: use a line with a trailing sentinel char and insert before it.
    local buf = vim.api.nvim_create_buf(false, true)
    vim.api.nvim_set_current_buf(buf)
    -- "prefix|" — cursor at col 7 (on the '|'), insert replaces nothing there.
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, { "prefix|" })
    vim.api.nvim_win_set_cursor(0, { 1, 6 }) -- col 6 = position of '|'

    local fake_picker = { close = function() end }
    captured_spec.confirm(fake_picker, captured_spec.items[1])

    local line = vim.api.nvim_buf_get_lines(buf, 0, 1, false)[1]
    -- id_str "10" inserted at col 6, so: "prefix" + "10" + "|" = "prefix10|"
    assert.equals("prefix10|", line)

    -- Cleanup
    vim.api.nvim_buf_delete(buf, { force = true })
  end)

  -- -------------------------------------------------------------------------
  -- Case 3: empty — "[]" triggers "No topics found." notify
  -- -------------------------------------------------------------------------
  it("notifies 'No topics found.' when CLI returns empty array", function()
    server.run_cli = function(args, cfg, cb)
      cb(true, "[]")
    end

    topics.pick({})

    assert.is_nil(captured_spec, "Snacks.picker should NOT be called for empty results")

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("No topics found") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'No topics found.' notification")
  end)

  -- -------------------------------------------------------------------------
  -- Case 4: snacks-guard — nil Snacks triggers notify, no error raised
  -- -------------------------------------------------------------------------
  it("notifies 'snacks.nvim picker not loaded' when _G.Snacks is nil", function()
    _G.Snacks = nil

    local ok, err = pcall(function()
      topics.pick({})
    end)

    assert.is_true(ok, "topics.pick() must not raise an error: " .. tostring(err))

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
