-- nvim-plugin/tests/plenary/prisma_note_spec.lua
-- Plenary busted unit tests for workflow.prisma_note (Wave C3).
-- Tests: single-mode arg vector, created=false path opens, bulk empty guard, error path.

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

describe("workflow.prisma_note", function()
  local prisma_note
  local server
  local config_mod

  local orig_run_cli
  local orig_config_resolve
  local orig_notify
  local orig_ui_input
  local orig_cmd

  local cli_calls
  local notify_calls

  before_each(function()
    -- Bust module caches.
    package.loaded["workflow.prisma_note"] = nil
    package.loaded["workflow.server"]      = nil
    package.loaded["workflow.config"]      = nil

    server     = require("workflow.server")
    config_mod = require("workflow.config")

    orig_run_cli        = server.run_cli
    orig_config_resolve = config_mod.resolve
    orig_notify         = vim.notify
    orig_ui_input       = vim.ui.input
    orig_cmd            = vim.cmd

    cli_calls    = {}
    notify_calls = {}

    -- Default stubs.
    server.run_cli = function(args, cfg, cb)
      table.insert(cli_calls, { args = args, cfg = cfg, cb = cb })
    end

    config_mod.resolve = function(_) return {} end

    vim.notify = function(msg, level, _)
      table.insert(notify_calls, { msg = msg, level = level })
    end

    -- Suppress vsplit side-effects by default.
    vim.cmd = function(_) end

    prisma_note = require("workflow.prisma_note")
  end)

  after_each(function()
    server.run_cli      = orig_run_cli
    config_mod.resolve  = orig_config_resolve
    vim.notify          = orig_notify
    vim.ui.input        = orig_ui_input
    vim.cmd             = orig_cmd

    package.loaded["workflow.prisma_note"] = nil
    package.loaded["workflow.server"]      = nil
    package.loaded["workflow.config"]      = nil
  end)

  -- ── 1. bibkey prompt → correct single arg shape ──────────────────────────

  it("builds correct single CLI arg vector when user provides a bibkey", function()
    vim.ui.input = function(_, cb) cb("Smith2020") end

    prisma_note.accept_to_note({})

    assert.equals(1, #cli_calls, "run_cli should be called exactly once")
    assert.same(
      { "prisma", "bib", "accept-to-note", "Smith2020", "--json" },
      cli_calls[1].args
    )
  end)

  -- ── 2. created:false → opens existing note path ──────────────────────────

  it("opens the note path and notifies 'Already exists' when created is false", function()
    local opened_paths = {}
    vim.cmd = function(cmd_str)
      table.insert(opened_paths, cmd_str)
    end

    vim.ui.input = function(_, cb) cb("Jones2019") end

    server.run_cli = function(args, _, cb)
      table.insert(cli_calls, { args = args })
      if cb then
        cb(
          true,
          '{"note_path":"/vault/notes/literature/20260101-lit-Jones2019.md","bibkey":"Jones2019","created":false}'
        )
      end
    end

    prisma_note.accept_to_note({})

    assert.equals(1, #opened_paths, "vsplit should be called for existing note")
    assert.is_true(
      opened_paths[1]:find("Jones2019") ~= nil,
      "vsplit path should contain the note filename"
    )

    local found_exists = false
    for _, n in ipairs(notify_calls) do
      if n.msg:find("Already exists") then
        found_exists = true
        break
      end
    end
    assert.is_true(found_exists, "Expected 'Already exists' notification for created=false")
  end)

  -- ── 3. bulk empty-result → notify warn + open nothing ────────────────────

  it("notifies warn and opens nothing when bulk result has an empty notes list", function()
    local opened = {}
    vim.cmd = function(s) table.insert(opened, s) end

    -- First prompt: blank bibkey → trigger bulk path.
    -- Second prompt: keyword-id.
    local prompt_count = 0
    vim.ui.input = function(_, cb)
      prompt_count = prompt_count + 1
      if prompt_count == 1 then
        cb("") -- blank → bulk
      else
        cb("42") -- keyword-id
      end
    end

    server.run_cli = function(args, _, cb)
      table.insert(cli_calls, { args = args })
      if cb then
        cb(true, '{"created":0,"skipped":3,"notes":[]}')
      end
    end

    prisma_note.accept_to_note({})

    assert.equals(0, #opened, "vsplit must NOT be called when notes list is empty")

    -- CLI should receive --all-accepted and --keyword-id 42
    assert.equals(1, #cli_calls)
    local argv = cli_calls[1].args
    local has_all_accepted = false
    local has_kw_id = false
    for i, v in ipairs(argv) do
      if v == "--all-accepted" then has_all_accepted = true end
      if v == "--keyword-id" and argv[i + 1] == "42" then has_kw_id = true end
    end
    assert.is_true(has_all_accepted, "bulk args must include --all-accepted")
    assert.is_true(has_kw_id, "bulk args must include --keyword-id 42")

    local found_warn = false
    for _, n in ipairs(notify_calls) do
      if n.msg:find("no notes generated") then
        found_warn = true
        break
      end
    end
    assert.is_true(found_warn, "Expected WARN notification about empty notes list")
  end)

  -- ── 4. CLI error → vim.notify ERROR with verbatim message ────────────────

  it("notifies at ERROR level with verbatim CLI error message on non-zero exit", function()
    vim.ui.input = function(_, cb) cb("BadKey") end

    server.run_cli = function(args, _, cb)
      table.insert(cli_calls, { args = args })
      if cb then
        cb(false, "Error: No BibEntry found with bibkey='BadKey'")
      end
    end

    prisma_note.accept_to_note({})

    local found = false
    for _, n in ipairs(notify_calls) do
      if n.level == vim.log.levels.ERROR
         and n.msg:find("No BibEntry found") then
        found = true
        break
      end
    end
    assert.is_true(found, "Expected verbatim ERROR notification on CLI failure")
  end)
end)
