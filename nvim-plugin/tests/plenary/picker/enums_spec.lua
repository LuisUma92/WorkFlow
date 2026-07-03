-- nvim-plugin/tests/plenary/picker/enums_spec.lua
-- Plenary busted unit tests for workflow.picker.enums
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
-- Fixtures
-- ---------------------------------------------------------------------------

local ENUMS_JSON = vim.json.encode({
  edge_class = { "structural", "associative" },
  relation_type = {
    structural = { "parent_of", "part_of", "derived_from" },
    associative = { "supports", "contradicts", "extends" },
  },
  note_type = { "fleeting", "permanent", "literature" },
  zettel_id_format = {
    library = "nanoid",
    alphabet = "A-Za-z0-9_-",
    default_length = 12,
    min_length = 8,
    max_length = 21,
    validation_regex = "^[A-Za-z0-9_-]{8,21}$",
    filename_convention = "<zettel_id>-<slug>.md",
    alias_template = { "<zettel_id>-<slug>", "<slug>", "<zettel_id>" },
  },
})

-- Load shared dependencies once so rtp loader fires before stubs are set.
local server  = require("workflow.server")
local config_mod = require("workflow.config")

-- ---------------------------------------------------------------------------
-- Suite
-- ---------------------------------------------------------------------------

describe("workflow.picker.enums", function()
  local enums_mod

  local orig_run_cli
  local orig_config_resolve
  local orig_notify
  local orig_snacks_pkg

  local notify_calls
  local captured_spec
  local captured_args

  before_each(function()
    -- Bust enums module cache to reset the internal _cache variable.
    package.loaded["workflow.picker.enums"] = nil

    orig_run_cli = server.run_cli
    orig_config_resolve = config_mod.resolve
    orig_notify = vim.notify
    orig_snacks_pkg = package.loaded["snacks"]

    notify_calls = {}
    vim.notify = function(msg, level, opts)
      table.insert(notify_calls, { msg = msg, level = level, opts = opts })
    end

    captured_args = nil
    server.run_cli = function(args, cfg, cb)
      captured_args = args
      cb(true, ENUMS_JSON)
    end

    config_mod.resolve = function(opts)
      return {}
    end

    captured_spec = nil
    package.loaded["snacks"] = {
      picker = function(spec)
        captured_spec = spec
      end,
    }

    enums_mod = require("workflow.picker.enums")
  end)

  after_each(function()
    server.run_cli = orig_run_cli
    config_mod.resolve = orig_config_resolve
    vim.notify = orig_notify
    package.loaded["snacks"] = orig_snacks_pkg
    package.loaded["workflow.picker.enums"] = nil
  end)

  -- -------------------------------------------------------------------------
  -- Case 1: get_enums fetches from CLI and caches
  -- -------------------------------------------------------------------------
  it("get_enums fetches from CLI and caches result", function()
    local call_count = 0
    server.run_cli = function(args, cfg, cb)
      call_count = call_count + 1
      captured_args = args
      cb(true, ENUMS_JSON)
    end
    enums_mod = require("workflow.picker.enums")

    local result1 = nil
    enums_mod.get_enums({}, function(ok, enums)
      result1 = enums
    end)
    -- Second call must use cache — no second run_cli call.
    enums_mod.get_enums({}, function(ok, enums) end)

    assert.equals(1, call_count, "run_cli should be called exactly once (cache hit on 2nd)")
    assert.is_not_nil(result1)
    assert.is_not_nil(result1.edge_class)
    assert.equals(2, #result1.edge_class)

    -- CLI args must be "notes enums --json"
    local args_str = table.concat(captured_args, " ")
    assert.is_truthy(args_str:find("notes"), "expected 'notes' in args")
    assert.is_truthy(args_str:find("enums"), "expected 'enums' in args")
    assert.is_truthy(args_str:find("%-%-json"), "expected '--json' in args")
  end)

  -- -------------------------------------------------------------------------
  -- Case 2: reload() clears cache so next call re-fetches
  -- -------------------------------------------------------------------------
  it("reload() clears the cache and notifies", function()
    local call_count = 0
    server.run_cli = function(args, cfg, cb)
      call_count = call_count + 1
      cb(true, ENUMS_JSON)
    end
    enums_mod = require("workflow.picker.enums")

    enums_mod.get_enums({}, function() end) -- populates cache
    assert.equals(1, call_count)

    enums_mod.reload()

    -- After reload the cache notifies.
    local found_notify = false
    for _, n in ipairs(notify_calls) do
      if n.msg:find("cleared") then
        found_notify = true
        break
      end
    end
    assert.is_true(found_notify, "Expected 'cleared' notification after reload()")

    enums_mod.get_enums({}, function() end) -- should re-fetch
    assert.equals(2, call_count, "expected re-fetch after reload()")
  end)

  -- -------------------------------------------------------------------------
  -- Case 3: pick_edge_class opens Snacks picker with live values
  -- -------------------------------------------------------------------------
  it("pick_edge_class opens Snacks picker with values from CLI JSON", function()
    enums_mod.pick_edge_class({ mode = "insert" })

    assert.is_not_nil(captured_spec, "Snacks.picker should be called")
    assert.equals(2, #captured_spec.items)

    local texts = {}
    for _, item in ipairs(captured_spec.items) do
      table.insert(texts, item.text)
    end
    -- Must contain the values from ENUMS_JSON, NOT hard-coded strings.
    assert.is_truthy(vim.tbl_contains(texts, "structural"), "expected 'structural'")
    assert.is_truthy(vim.tbl_contains(texts, "associative"), "expected 'associative'")
  end)

  -- -------------------------------------------------------------------------
  -- Case 4: pick_relation_type with edge_class filter
  -- -------------------------------------------------------------------------
  it("pick_relation_type filters by edge_class when provided", function()
    enums_mod.pick_relation_type({ edge_class = "structural", mode = "insert" })

    assert.is_not_nil(captured_spec)
    -- Should only show structural relation types.
    assert.equals(3, #captured_spec.items)
    local texts = {}
    for _, item in ipairs(captured_spec.items) do
      table.insert(texts, item.text)
    end
    assert.is_truthy(vim.tbl_contains(texts, "parent_of"), "expected 'parent_of'")
    assert.is_truthy(vim.tbl_contains(texts, "derived_from"), "expected 'derived_from'")
    -- Should NOT include associative types.
    assert.is_falsy(vim.tbl_contains(texts, "supports"), "unexpected 'supports'")
  end)

  -- -------------------------------------------------------------------------
  -- Case 5: pick_relation_type without filter returns all types merged
  -- -------------------------------------------------------------------------
  it("pick_relation_type without filter returns all relation types", function()
    enums_mod.pick_relation_type({ mode = "yank" })

    assert.is_not_nil(captured_spec)
    -- structural has 3, associative has 3 → total 6 (no duplicates in fixture)
    assert.equals(6, #captured_spec.items)
  end)

  -- -------------------------------------------------------------------------
  -- Case 6: pick_note_type opens picker with note_type values
  -- -------------------------------------------------------------------------
  it("pick_note_type opens Snacks picker with note_type values", function()
    enums_mod.pick_note_type({ mode = "yank" })

    assert.is_not_nil(captured_spec)
    assert.equals(3, #captured_spec.items)
    local texts = {}
    for _, item in ipairs(captured_spec.items) do
      table.insert(texts, item.text)
    end
    assert.is_truthy(vim.tbl_contains(texts, "permanent"), "expected 'permanent'")
    assert.is_truthy(vim.tbl_contains(texts, "literature"), "expected 'literature'")
  end)

  -- -------------------------------------------------------------------------
  -- Case 7: yank mode — confirm calls setreg, not buf_set_text
  -- -------------------------------------------------------------------------
  it("yank mode: confirm calls setreg, not nvim_buf_set_text", function()
    local setreg_calls = {}
    local orig_setreg = vim.fn.setreg
    vim.fn.setreg = function(reg, val)
      table.insert(setreg_calls, { reg = reg, val = val })
    end

    local buf_set_calls = {}
    local orig_buf_set = vim.api.nvim_buf_set_text
    vim.api.nvim_buf_set_text = function(...)
      table.insert(buf_set_calls, { ... })
    end

    enums_mod.pick_edge_class({ mode = "yank" })

    assert.is_not_nil(captured_spec)
    local fake_picker = { close = function() end }
    captured_spec.confirm(fake_picker, captured_spec.items[1])

    vim.fn.setreg = orig_setreg
    vim.api.nvim_buf_set_text = orig_buf_set

    assert.is_true(#setreg_calls > 0, "expected setreg to be called in yank mode")
    assert.equals(0, #buf_set_calls, "nvim_buf_set_text must NOT be called in yank mode")
  end)

  -- -------------------------------------------------------------------------
  -- Case 8: CLI error propagates as notify without raising
  -- -------------------------------------------------------------------------
  it("CLI error triggers notify without raising an error", function()
    server.run_cli = function(args, cfg, cb)
      cb(false, "workflow: command not found")
    end
    enums_mod = require("workflow.picker.enums")

    local ok, err = pcall(function()
      enums_mod.pick_edge_class({})
    end)
    assert.is_true(ok, "pick_edge_class must not raise: " .. tostring(err))

    local found = false
    for _, n in ipairs(notify_calls) do
      if n.msg:find("Failed to load enums") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'Failed to load enums' notification")
  end)

  -- -------------------------------------------------------------------------
  -- Case 9: missing snacks triggers notify
  -- -------------------------------------------------------------------------
  it("notifies 'snacks.nvim is required' when snacks cannot be loaded", function()
    package.loaded["snacks"] = nil
    local orig_preload = package.preload["snacks"]
    package.preload["snacks"] = function() error("snacks not installed") end

    local ok, err = pcall(function()
      enums_mod.pick_edge_class({})
    end)

    if orig_preload then
      package.preload["snacks"] = orig_preload
    else
      package.preload["snacks"] = nil
    end

    assert.is_true(ok, "pick_edge_class must not raise: " .. tostring(err))

    local found = false
    for _, n in ipairs(notify_calls) do
      if n.msg:find("snacks.nvim is required") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'snacks.nvim is required' notification")
  end)
end)
