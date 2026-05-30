-- nvim-plugin/tests/plenary/picker/notes_spec.lua
-- Plenary busted unit tests for workflow.picker.notes
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

local NOTES_JSON = vim.json.encode({
  {
    id = "20230101120000",
    title = "Mechanics overview",
    type = "permanent",
    tags = { "physics", "mechanics" },
    concepts = { "kinematics" },
    path = "/tmp/fake_note_1.md",
  },
  {
    id = "20230102130000",
    title = "Thermodynamics basics",
    type = "literature",
    tags = {},
    concepts = {},
    path = "/tmp/fake_note_2.md",
  },
})

-- Load dependency modules once at describe level so the rtp loader fires.
local server = require("workflow.server")
local config_mod = require("workflow.config")

-- ---------------------------------------------------------------------------
-- Suite
-- ---------------------------------------------------------------------------

describe("workflow.picker.notes", function()
  local notes

  local orig_run_cli
  local orig_config_resolve
  local orig_config_is_in_workspace
  local orig_notify
  local orig_snacks_pkg

  local captured_spec
  local notify_calls
  local captured_args

  before_each(function()
    -- Only bust the picker cache so it re-reads the (now stubbed) server/config fields.
    package.loaded["workflow.picker.notes"] = nil

    -- Save originals.
    orig_run_cli = server.run_cli
    orig_config_resolve = config_mod.resolve
    orig_config_is_in_workspace = config_mod.is_in_workspace
    orig_notify = vim.notify
    orig_snacks_pkg = package.loaded["snacks"]

    -- Default stubs.
    captured_args = nil
    server.run_cli = function(args, cfg, cb)
      captured_args = args
      cb(true, NOTES_JSON)
    end

    config_mod.resolve = function(opts)
      return { vault_root = nil, workspace_dir = nil }
    end

    config_mod.is_in_workspace = function(path, root)
      return true
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
    notes = require("workflow.picker.notes")
  end)

  after_each(function()
    server.run_cli = orig_run_cli
    config_mod.resolve = orig_config_resolve
    config_mod.is_in_workspace = orig_config_is_in_workspace
    vim.notify = orig_notify
    package.loaded["snacks"] = orig_snacks_pkg
    package.loaded["workflow.picker.notes"] = nil
  end)

  -- -------------------------------------------------------------------------
  -- Case 1: contract — items built correctly from JSON
  -- -------------------------------------------------------------------------
  it("builds items with correct text and item fields from JSON", function()
    notes.pick({})

    assert.is_not_nil(captured_spec, "Snacks.picker should have been called")
    assert.equals(2, #captured_spec.items)

    local item1 = captured_spec.items[1]
    assert.equals("[20230101120000] Mechanics overview — permanent", item1.text)
    assert.equals("20230101120000", item1.item.id)
    assert.equals("Mechanics overview", item1.item.title)
    assert.equals("permanent", item1.item.type)

    local item2 = captured_spec.items[2]
    assert.equals("[20230102130000] Thermodynamics basics — literature", item2.text)
    assert.equals("20230102130000", item2.item.id)
  end)

  -- -------------------------------------------------------------------------
  -- Case 2: filter opts forwarded into CLI args
  -- -------------------------------------------------------------------------
  it("forwards tag, concept, note_type opts into CLI args", function()
    notes.pick({ tag = "physics", concept = "kinematics", note_type = "permanent" })

    assert.is_not_nil(captured_args)

    local args_str = table.concat(captured_args, " ")
    assert.is_truthy(args_str:find("--tag"), "expected --tag in args")
    assert.is_truthy(args_str:find("physics"), "expected tag value in args")
    assert.is_truthy(args_str:find("--concept"), "expected --concept in args")
    assert.is_truthy(args_str:find("kinematics"), "expected concept value in args")
    assert.is_truthy(args_str:find("--note%-type"), "expected --note-type in args")
    assert.is_truthy(args_str:find("permanent"), "expected note_type value in args")
  end)

  -- -------------------------------------------------------------------------
  -- Case 3: confirm — opens note file via vim.cmd edit
  -- -------------------------------------------------------------------------
  it("confirm() opens the note file via vim.cmd edit", function()
    notes.pick({})

    assert.is_not_nil(captured_spec)

    local vim_cmd_calls = {}
    local orig_vim_cmd = vim.cmd
    vim.cmd = function(cmd)
      table.insert(vim_cmd_calls, cmd)
    end

    local orig_expand = vim.fn.expand
    vim.fn.expand = function(p) return p end

    local fake_picker = { close = function() end }
    captured_spec.confirm(fake_picker, captured_spec.items[1])

    vim.cmd = orig_vim_cmd
    vim.fn.expand = orig_expand

    assert.equals(1, #vim_cmd_calls, "expected exactly one vim.cmd call")
    assert.is_truthy(vim_cmd_calls[1]:find("edit"), "expected 'edit' in vim.cmd call")
    assert.is_truthy(
      vim_cmd_calls[1]:find("fake_note_1", 1, true),
      "expected note path in vim.cmd call"
    )
  end)

  -- -------------------------------------------------------------------------
  -- Case 4: empty — "[]" triggers "No notes found." notify
  -- -------------------------------------------------------------------------
  it("notifies 'No notes found.' when CLI returns empty array", function()
    server.run_cli = function(args, cfg, cb)
      cb(true, "[]")
    end

    notes.pick({})

    assert.is_nil(captured_spec, "Snacks.picker should NOT be called for empty results")

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("No notes found") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'No notes found.' notification")
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
      notes.pick({})
    end)

    if orig_preload then
      package.preload["snacks"] = orig_preload
    else
      package.preload["snacks"] = nil
    end

    assert.is_true(ok, "notes.pick() must not raise an error: " .. tostring(err))

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
