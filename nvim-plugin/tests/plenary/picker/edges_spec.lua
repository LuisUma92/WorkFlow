-- nvim-plugin/tests/plenary/picker/edges_spec.lua
-- Plenary busted unit tests for workflow.picker.edges
-- Stubs: server.run_cli, config.resolve, vim.notify, require("snacks")
--
-- NOTE: plenary.busted loads this file via loadfile() which uses the standard
-- Lua require (package.path only, not nvim rtp). We must inject the plugin
-- lua dir into package.path before any require("workflow.*") call.
do
  local spec_dir = debug.getinfo(1, "S").source:sub(2):match("(.*/)")
  -- spec is at nvim-plugin/tests/plenary/picker/ — lua dir is 4 levels up + /lua
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

-- NOTE: edge_class values must match the live vocab (structural/associative),
-- NOT note types like "concept" or "reference" (those were the old drift bug).
local EDGES_JSON = vim.json.encode({
  {
    source_zettel_id = "20230101120000",
    target_zettel_id = "20230102130000",
    edge_class = "structural",
    relation_type = "derived_from",
    id = 5,
    weight = 1.0,
    rationale = "Direct derivation",
  },
  {
    source_zettel_id = "20230103140000",
    target_zettel_id = "20230104150000",
    edge_class = "associative",
    relation_type = "supports",
    id = 7,
  },
})

-- Load dependency modules once at describe level so the rtp loader fires.
local server = require("workflow.server")
local config_mod = require("workflow.config")

-- Enums fixture used in pick_with_class_filter tests.
local ENUMS_JSON = vim.json.encode({
  edge_class = { "structural", "associative" },
  relation_type = {
    structural = { "parent_of", "derived_from" },
    associative = { "supports", "contradicts" },
  },
  note_type = { "permanent", "literature" },
})

-- ---------------------------------------------------------------------------
-- Suite
-- ---------------------------------------------------------------------------

describe("workflow.picker.edges", function()
  local edges

  local orig_run_cli
  local orig_config_resolve
  local orig_config_is_in_workspace
  local orig_notify
  local orig_snacks_pkg

  local captured_spec
  local notify_calls
  local captured_args

  before_each(function()
    -- Bust both picker caches so they re-read the (now stubbed) dependencies.
    package.loaded["workflow.picker.edges"] = nil
    package.loaded["workflow.picker.enums"] = nil

    -- Save originals.
    orig_run_cli = server.run_cli
    orig_config_resolve = config_mod.resolve
    orig_config_is_in_workspace = config_mod.is_in_workspace
    orig_notify = vim.notify
    orig_snacks_pkg = package.loaded["snacks"]

    -- Default stubs: serve edges JSON for "notes edges list" calls and
    -- enums JSON for "notes enums" calls.
    captured_args = nil
    server.run_cli = function(args, cfg, cb)
      captured_args = args
      local cmd = table.concat(args, " ")
      if cmd:find("enums") then
        cb(true, ENUMS_JSON)
      else
        cb(true, EDGES_JSON)
      end
    end

    config_mod.resolve = function(opts)
      return {}
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
    edges = require("workflow.picker.edges")
  end)

  after_each(function()
    server.run_cli = orig_run_cli
    config_mod.resolve = orig_config_resolve
    config_mod.is_in_workspace = orig_config_is_in_workspace
    vim.notify = orig_notify
    package.loaded["snacks"] = orig_snacks_pkg
    package.loaded["workflow.picker.edges"] = nil
    package.loaded["workflow.picker.enums"] = nil
  end)

  -- -------------------------------------------------------------------------
  -- Case 1: contract — items built correctly from JSON
  -- -------------------------------------------------------------------------
  it("builds items with correct text and item fields from JSON", function()
    edges.pick({})

    assert.is_not_nil(captured_spec, "Snacks.picker should have been called")
    assert.equals(2, #captured_spec.items)

    local item1 = captured_spec.items[1]
    -- edge_class is now "structural" (live vocab), not "concept" (old drift)
    assert.equals("[structural] 20230101120000 → 20230102130000 (derived_from)", item1.text)
    assert.equals(5, item1.item.id)
    assert.equals("structural", item1.item.edge_class)
    assert.equals("20230101120000", item1.item.source_zettel_id)

    local item2 = captured_spec.items[2]
    assert.equals("[associative] 20230103140000 → 20230104150000 (supports)", item2.text)
    assert.equals(7, item2.item.id)
  end)

  -- -------------------------------------------------------------------------
  -- Case 2: filter opts forwarded into CLI args
  -- -------------------------------------------------------------------------
  it("forwards source, edge_class, relation_type opts into CLI args", function()
    edges.pick({ source = "20230101120000", edge_class = "concept", relation_type = "supports" })

    assert.is_not_nil(captured_args)

    local args_str = table.concat(captured_args, " ")
    assert.is_truthy(args_str:find("--source"), "expected --source in args")
    assert.is_truthy(args_str:find("20230101120000"), "expected source value in args")
    assert.is_truthy(args_str:find("--edge%-class"), "expected --edge-class in args")
    assert.is_truthy(args_str:find("--relation%-type"), "expected --relation-type in args")
  end)

  -- -------------------------------------------------------------------------
  -- Case 3: confirm — resolves source note via second run_cli and opens file
  -- -------------------------------------------------------------------------
  it("confirm() triggers a notes show call and opens file on success", function()
    edges.pick({})

    assert.is_not_nil(captured_spec)

    local show_args_captured = nil
    local fake_note_path = "/tmp/fake_note.md"

    -- The confirm() calls server.run_cli a second time for "notes show".
    server.run_cli = function(args, cfg, cb)
      show_args_captured = args
      cb(true, vim.json.encode({ path = fake_note_path }))
    end

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

    -- Second run_cli should be "notes show <src_id> --json".
    assert.is_not_nil(show_args_captured, "expected second run_cli call for notes show")
    local show_str = table.concat(show_args_captured, " ")
    assert.is_truthy(show_str:find("notes"), "expected 'notes' in show args")
    assert.is_truthy(show_str:find("show"), "expected 'show' in show args")
    assert.is_truthy(show_str:find("20230101120000"), "expected source zettel_id in show args")

    -- vim.cmd should have been called with an edit command containing the path.
    assert.equals(1, #vim_cmd_calls, "expected exactly one vim.cmd call")
    assert.is_truthy(vim_cmd_calls[1]:find("edit"), "expected 'edit' in vim.cmd call")
  end)

  -- -------------------------------------------------------------------------
  -- Case 4: empty — "[]" triggers "No note edges found." notify
  -- -------------------------------------------------------------------------
  it("notifies 'No note edges found.' when CLI returns empty array", function()
    server.run_cli = function(args, cfg, cb)
      cb(true, "[]")
    end

    edges.pick({})

    assert.is_nil(captured_spec, "Snacks.picker should NOT be called for empty results")

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("No note edges found") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'No note edges found.' notification")
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
      edges.pick({})
    end)

    if orig_preload then
      package.preload["snacks"] = orig_preload
    else
      package.preload["snacks"] = nil
    end

    assert.is_true(ok, "edges.pick() must not raise an error: " .. tostring(err))

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("snacks.nvim is required") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected 'snacks.nvim is required' notification")
  end)

  -- -------------------------------------------------------------------------
  -- Case 6: pick_with_class_filter — opens class picker sourced from enums
  -- -------------------------------------------------------------------------
  it("pick_with_class_filter opens a class picker with values from live enums", function()
    edges.pick_with_class_filter({})

    -- First call: Snacks.picker is invoked for the class selection step.
    assert.is_not_nil(captured_spec, "class selection picker must open")
    local class_title = captured_spec.title or ""
    assert.is_truthy(
      class_title:lower():find("class") or class_title:lower():find("edge"),
      "picker title should mention 'class' or 'edge', got: " .. class_title
    )

    -- Items must come from the live enums, not any hard-coded list.
    assert.equals(2, #captured_spec.items, "expected 2 edge classes from ENUMS_JSON")
    local texts = {}
    for _, item in ipairs(captured_spec.items) do
      table.insert(texts, item.text)
    end
    assert.is_truthy(vim.tbl_contains(texts, "structural"), "expected 'structural' from live enums")
    assert.is_truthy(vim.tbl_contains(texts, "associative"), "expected 'associative' from live enums")
  end)

  -- -------------------------------------------------------------------------
  -- Case 7: pick_with_class_filter — confirm opens filtered edges picker
  -- -------------------------------------------------------------------------
  it("pick_with_class_filter confirm re-opens edges picker with selected class", function()
    local picker_calls = {}
    package.loaded["snacks"] = {
      picker = function(spec)
        table.insert(picker_calls, spec)
        -- auto-capture last spec
        captured_spec = spec
      end,
    }

    edges.pick_with_class_filter({})

    -- First picker: class selection.
    assert.equals(1, #picker_calls, "expected exactly one picker open so far")

    -- Simulate confirming "structural".
    local fake_picker = { close = function() end }
    captured_spec.confirm(fake_picker, captured_spec.items[1])

    -- Second picker: edges list filtered by structural.
    assert.equals(2, #picker_calls, "expected second picker after class confirm")
    local edge_spec = picker_calls[2]
    assert.is_not_nil(edge_spec.items, "edges picker must have items")
    assert.equals(2, #edge_spec.items, "should see both edges from EDGES_JSON")
  end)
end)
