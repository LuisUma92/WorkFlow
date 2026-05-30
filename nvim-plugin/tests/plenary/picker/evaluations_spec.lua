-- nvim-plugin/tests/plenary/picker/evaluations_spec.lua
-- Plenary busted unit tests for workflow.picker.evaluations
-- Stubs: server.run_cli, config.resolve, vim.notify, require("snacks")
--
-- NOTE: plenary.busted loads this file via loadfile() which uses the standard
-- Lua require (package.path only, not nvim rtp). We must inject the plugin
-- lua dir into package.path before any require("workflow.*") call.
do
  local spec_dir = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
  local lua_dir = vim.fn.fnamemodify(spec_dir .. "../../../../nvim-plugin/lua", ":p"):gsub("/$", "")
  local entry = lua_dir .. "/?.lua;" .. lua_dir .. "/?/init.lua"
  if not package.path:find(lua_dir, 1, true) then
    package.path = entry .. ";" .. package.path
  end
end

require("plenary.busted")

local assert = require("luassert")

-- ---------------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------------

local EVALS_JSON = vim.json.encode({
  {
    id = 1,
    institution = "UCR",
    name = "Midterm Exam",
    total_points = 100,
    item_count = 5,
    description = "First midterm",
    items = {
      {
        item_name = "Q1",
        taxonomy_domain = "Procedimiento Mental",
        taxonomy_level = "Application",
        amount = 3,
        points_per_item = 10,
      },
    },
  },
  {
    id = 2,
    institution = "UFide",
    name = "Final Exam",
    total_points = 200,
    item_count = 8,
    description = "",
    items = {},
  },
})

-- Load dependency modules once at describe level so the rtp loader fires.
local server = require("workflow.server")
local config_mod = require("workflow.config")

-- ---------------------------------------------------------------------------
-- Suite
-- ---------------------------------------------------------------------------

describe("workflow.picker.evaluations", function()
  local evaluations

  local orig_run_cli
  local orig_config_resolve
  local orig_notify
  local orig_snacks_pkg

  local captured_spec
  local notify_calls
  local captured_args

  before_each(function()
    -- Only bust the picker cache so it re-reads the (now stubbed) server/config fields.
    package.loaded["workflow.picker.evaluations"] = nil

    -- Save originals.
    orig_run_cli = server.run_cli
    orig_config_resolve = config_mod.resolve
    orig_notify = vim.notify
    orig_snacks_pkg = package.loaded["snacks"]

    -- Default stubs.
    captured_args = nil
    server.run_cli = function(args, cfg, cb)
      captured_args = args
      cb(true, EVALS_JSON)
    end

    config_mod.resolve = function(opts)
      return {}
    end

    captured_spec = nil
    -- Stub snacks via package.loaded so pcall(require, "snacks") succeeds.
    package.loaded["snacks"] = {
      picker = function(spec)
        captured_spec = spec
      end,
    }

    notify_calls = {}
    vim.notify = function(msg, level, opts)
      table.insert(notify_calls, { msg = msg, level = level, opts = opts })
    end

    -- Load the picker fresh (it sees the already-stubbed server/config tables).
    evaluations = require("workflow.picker.evaluations")
  end)

  after_each(function()
    server.run_cli = orig_run_cli
    config_mod.resolve = orig_config_resolve
    vim.notify = orig_notify
    package.loaded["snacks"] = orig_snacks_pkg
    package.loaded["workflow.picker.evaluations"] = nil
  end)

  -- -------------------------------------------------------------------------
  -- Case 1: contract — items built correctly from JSON
  -- -------------------------------------------------------------------------
  it("builds items with correct text and item fields from JSON", function()
    evaluations.pick({})

    assert.is_not_nil(captured_spec, "Snacks.picker should have been called")
    assert.equals(2, #captured_spec.items)

    local item1 = captured_spec.items[1]
    assert.equals("[UCR] Midterm Exam (100 pts, 5 items)", item1.text)
    assert.equals(1, item1.item.id)
    assert.equals("UCR", item1.item.institution)
    assert.equals("Midterm Exam", item1.item.name)

    local item2 = captured_spec.items[2]
    assert.equals("[UFide] Final Exam (200 pts, 8 items)", item2.text)
    assert.equals(2, item2.item.id)
  end)

  -- -------------------------------------------------------------------------
  -- Case 2: inst filter opt forwarded into CLI args
  -- -------------------------------------------------------------------------
  it("forwards inst opt into CLI args", function()
    evaluations.pick({ inst = "UCR" })

    assert.is_not_nil(captured_args)

    local args_str = table.concat(captured_args, " ")
    assert.is_truthy(args_str:find("--inst"), "expected --inst in args")
    assert.is_truthy(args_str:find("UCR"), "expected inst value in args")
  end)

  -- -------------------------------------------------------------------------
  -- Case 3: confirm — copies formatted message to register + notifies
  -- -------------------------------------------------------------------------
  it("confirm() notifies selected evaluation and copies to register", function()
    evaluations.pick({})

    assert.is_not_nil(captured_spec)

    local setreg_calls = {}
    local orig_setreg = vim.fn.setreg
    vim.fn.setreg = function(reg, val)
      table.insert(setreg_calls, { reg = reg, val = val })
    end

    local fake_picker = { close = function() end }
    captured_spec.confirm(fake_picker, captured_spec.items[1])

    vim.fn.setreg = orig_setreg

    -- Should notify with "Selected: [UCR] Midterm Exam (id=1)".
    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("Selected") and call.msg:find("Midterm Exam") and call.msg:find("id=1") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'Selected: [UCR] Midterm Exam (id=1)' notification")

    -- Should have written to both default and clipboard registers.
    assert.is_true(#setreg_calls >= 2, "Expected at least 2 setreg calls")
  end)

  -- -------------------------------------------------------------------------
  -- Case 4: empty — "[]" triggers "No evaluation templates found." notify
  -- -------------------------------------------------------------------------
  it("notifies 'No evaluation templates found.' when CLI returns empty array", function()
    server.run_cli = function(args, cfg, cb)
      cb(true, "[]")
    end

    evaluations.pick({})

    assert.is_nil(captured_spec, "Snacks.picker should NOT be called for empty results")

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("No evaluation templates found") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'No evaluation templates found.' notification")
  end)

  -- -------------------------------------------------------------------------
  -- Case 5: snacks-guard — broken snacks triggers notify, no error raised
  -- -------------------------------------------------------------------------
  it("notifies 'snacks.nvim is required' when snacks cannot be loaded", function()
    package.loaded["snacks"] = nil
    local orig_preload = package.preload["snacks"]
    package.preload["snacks"] = function()
      error("snacks not installed")
    end

    local ok, err = pcall(function()
      evaluations.pick({})
    end)

    if orig_preload then
      package.preload["snacks"] = orig_preload
    else
      package.preload["snacks"] = nil
    end

    assert.is_true(ok, "evaluations.pick() must not raise an error: " .. tostring(err))

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("snacks.nvim is required") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'snacks.nvim is required' notification")
  end)
end)
