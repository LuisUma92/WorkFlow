-- nvim-plugin/tests/plenary/bib_import_spec.lua
-- Plenary busted unit tests for workflow.bib_import
-- Tests: block extraction pure function, no-block guard, CLI invocation contract.

require("plenary.busted")

local assert = require("luassert")

-- Ensure the plugin lua dir is on package.path so require() finds workflow.*
-- modules even when run via plenary's loadfile() in a headless context.
do
  local script = debug.getinfo(1, "S").source:sub(2)
  local spec_dir = script:match("(.*/)")
  local lua_dir = vim.fn.fnamemodify(spec_dir .. "../../lua", ":p"):gsub("/$", "")
  local entry = lua_dir .. "/?.lua;" .. lua_dir .. "/?/init.lua"
  if not package.path:find(lua_dir, 1, true) then
    package.path = entry .. ";" .. package.path
  end
end

-- ---------------------------------------------------------------------------
-- Suite
-- ---------------------------------------------------------------------------

describe("workflow.bib_import", function()
  local bib_import
  local server
  local config_mod

  local orig_run_cli
  local orig_config_resolve
  local orig_notify
  local orig_buf_get_lines

  local cli_calls
  local notify_calls

  before_each(function()
    -- Bust module caches.
    package.loaded["workflow.bib_import"] = nil
    package.loaded["workflow.server"]     = nil
    package.loaded["workflow.config"]     = nil

    server     = require("workflow.server")
    config_mod = require("workflow.config")

    orig_run_cli        = server.run_cli
    orig_config_resolve = config_mod.resolve
    orig_notify         = vim.notify
    orig_buf_get_lines  = vim.api.nvim_buf_get_lines

    cli_calls    = {}
    notify_calls = {}

    -- Default stubs.
    server.run_cli = function(args, cfg, cb)
      table.insert(cli_calls, { args = args, cfg = cfg })
      if cb then cb(true, '{"created":1,"skipped":0,"errors":[],"statuses":[]}') end
    end

    config_mod.resolve = function(_) return {} end

    vim.notify = function(msg, level, opts)
      table.insert(notify_calls, { msg = msg, level = level, opts = opts })
    end

    bib_import = require("workflow.bib_import")
  end)

  after_each(function()
    server.run_cli              = orig_run_cli
    config_mod.resolve          = orig_config_resolve
    vim.notify                  = orig_notify
    vim.api.nvim_buf_get_lines  = orig_buf_get_lines

    package.loaded["workflow.bib_import"] = nil
    package.loaded["workflow.server"]     = nil
    package.loaded["workflow.config"]     = nil
  end)

  -- -------------------------------------------------------------------------
  -- Block extraction: pure function tests (no vim side-effects needed)
  -- -------------------------------------------------------------------------

  describe("_extract_bib_block", function()
    it("returns inner text of a backtick bib block", function()
      local lines = {
        "# My note",
        "```bib",
        "@article{Smith2020,",
        "  author = {Smith},",
        "}",
        "```",
        "trailing text",
      }
      local result = bib_import._extract_bib_block(lines)
      assert.is_not_nil(result)
      assert.equals("@article{Smith2020,\n  author = {Smith},\n}", result)
    end)

    it("returns inner text of a tilde bib block", function()
      local lines = {
        "~~~bib",
        "@book{Jones2019}",
        "~~~",
      }
      local result = bib_import._extract_bib_block(lines)
      assert.is_not_nil(result)
      assert.equals("@book{Jones2019}", result)
    end)

    it("returns nil when no bib block is present", function()
      local lines = {
        "# Just text",
        "```python",
        "x = 1",
        "```",
      }
      local result = bib_import._extract_bib_block(lines)
      assert.is_nil(result)
    end)

    it("returns nil for an empty buffer", function()
      local result = bib_import._extract_bib_block({})
      assert.is_nil(result)
    end)

    it("returns only the FIRST bib block when multiple are present", function()
      local lines = {
        "```bib",
        "@article{First}",
        "```",
        "```bib",
        "@article{Second}",
        "```",
      }
      local result = bib_import._extract_bib_block(lines)
      assert.equals("@article{First}", result)
    end)

    it("returns an empty string for an empty bib block", function()
      local lines = { "```bib", "```" }
      local result = bib_import._extract_bib_block(lines)
      assert.equals("", result)
    end)
  end)

  -- -------------------------------------------------------------------------
  -- import_current_buffer: no bib block → run_cli NOT called
  -- -------------------------------------------------------------------------

  it("does NOT call run_cli when no bib block is found in buffer", function()
    vim.api.nvim_buf_get_lines = function(_, _, _, _)
      return { "# Just a note", "No bib block here." }
    end

    bib_import.import_current_buffer({})

    assert.equals(0, #cli_calls, "run_cli must not be called when no bib block exists")

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("no `bib` block found") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected INFO notification about missing bib block")
  end)

  it("does NOT call run_cli for an empty buffer", function()
    vim.api.nvim_buf_get_lines = function(_, _, _, _)
      return {}
    end

    bib_import.import_current_buffer({})

    assert.equals(0, #cli_calls, "run_cli must not be called for empty buffer")
  end)

  -- -------------------------------------------------------------------------
  -- import_current_buffer: bib block found → run_cli called with correct args
  -- -------------------------------------------------------------------------

  it("calls run_cli with args {'prisma','bib','import','--stdin','--json'} when block found", function()
    vim.api.nvim_buf_get_lines = function(_, _, _, _)
      return {
        "```bib",
        "@article{Test2024}",
        "```",
      }
    end

    bib_import.import_current_buffer({})

    assert.equals(1, #cli_calls, "run_cli should be called exactly once")
    local captured = cli_calls[1]
    assert.same(
      { "prisma", "bib", "import", "--stdin", "--json" },
      captured.args
    )
  end)

  it("passes the bib block text as config.stdin to run_cli", function()
    local bib_content = "@article{Test2024,\n  author = {Test},\n}"
    vim.api.nvim_buf_get_lines = function(_, _, _, _)
      return {
        "```bib",
        "@article{Test2024,",
        "  author = {Test},",
        "}",
        "```",
      }
    end

    bib_import.import_current_buffer({})

    assert.equals(1, #cli_calls)
    local cfg = cli_calls[1].cfg
    -- config.stdin should be the block text with trailing newline
    assert.equals(bib_content .. "\n", cfg.stdin)
  end)

  -- -------------------------------------------------------------------------
  -- on_done: success path notifies counts
  -- -------------------------------------------------------------------------

  it("notifies created/skipped/error counts on success", function()
    vim.api.nvim_buf_get_lines = function(_, _, _, _)
      return { "```bib", "@article{X}", "```" }
    end

    server.run_cli = function(args, cfg, cb)
      table.insert(cli_calls, { args = args, cfg = cfg })
      if cb then cb(true, '{"created":2,"skipped":1,"errors":[{"bibkey":"bad","reason":"x"}],"statuses":[]}') end
    end

    bib_import.import_current_buffer({})

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("2 created") and call.msg:find("1 skipped") and call.msg:find("1 error") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected summary notification with counts incl. error list length")
  end)

  it("notifies error count from a JSON errors LIST on success", function()
    vim.api.nvim_buf_get_lines = function(_, _, _, _)
      return { "```bib", "@article{X}", "```" }
    end

    -- Real CLI emits `errors` as a JSON list, not a number. The notify must
    -- format `#errors` (regression: a list passed to %d crashed the callback).
    server.run_cli = function(args, cfg, cb)
      table.insert(cli_calls, { args = args, cfg = cfg })
      if cb then cb(true, '{"created":3,"skipped":0,"errors":[],"statuses":[]}') end
    end

    bib_import.import_current_buffer({})

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.msg:find("3 created") and call.msg:find("0 error") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected INFO notification (no crash) with 0 errors from an empty list")
  end)

  -- -------------------------------------------------------------------------
  -- on_done: error path notifies with ERROR level
  -- -------------------------------------------------------------------------

  it("notifies at ERROR level when run_cli returns ok=false", function()
    vim.api.nvim_buf_get_lines = function(_, _, _, _)
      return { "```bib", "@article{X}", "```" }
    end

    server.run_cli = function(args, cfg, cb)
      table.insert(cli_calls, { args = args, cfg = cfg })
      if cb then cb(false, "import failed: DB locked") end
    end

    bib_import.import_current_buffer({})

    local found = false
    for _, call in ipairs(notify_calls) do
      if call.level == vim.log.levels.ERROR and call.msg:find("import failed") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected ERROR notification on CLI failure")
  end)
end)
