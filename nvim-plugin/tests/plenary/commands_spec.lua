-- nvim-plugin/tests/plenary/commands_spec.lua
-- Plenary busted unit tests for workflow.commands kv-arg parsing.
-- minimal_init.lua centralizes package.path, so no per-spec bootstrap is needed.
--
-- Strategy: setup() the command table with a metatable-backed `workflow` stub
-- that records every method call, then drive the user commands via vim.cmd and
-- assert on the parsed opts each picker/handler received.

require("plenary.busted")

local assert = require("luassert")

describe("workflow.commands kv-arg parsing", function()
  local calls
  local notify_calls
  local orig_notify

  before_each(function()
    calls = {}
    notify_calls = {}
    orig_notify = vim.notify
    vim.notify = function(msg, level, _opts)
      table.insert(notify_calls, { msg = msg, level = level })
    end

    local workflow = setmetatable({}, {
      __index = function(_, name)
        return function(...)
          calls[name] = { ... }
        end
      end,
    })
    -- fresh require each time so setup() re-registers against this stub
    package.loaded["workflow.commands"] = nil
    require("workflow.commands").setup(workflow)
  end)

  after_each(function()
    vim.notify = orig_notify
  end)

  local function notified(needle)
    for _, c in ipairs(notify_calls) do
      if c.msg:find(needle, 1, true) then
        return true
      end
    end
    return false
  end

  it("parses a hyphenated key into the underscored opt", function()
    vim.cmd("WorkflowTopicPicker discipline-area=FI0001")
    assert.are.same({ discipline_area = "FI0001" }, calls.pick_topics[1])
  end)

  it("coerces a numeric kv value with tonumber", function()
    vim.cmd("WorkflowContentPicker topic-id=5")
    assert.are.equal(5, calls.pick_contents[1].topic_id)
  end)

  it("yields nil when a numeric kv value is non-numeric", function()
    vim.cmd("WorkflowContentPicker topic-id=abc")
    assert.is_nil(calls.pick_contents[1].topic_id)
  end)

  it("parses multiple kv args, leaving unset filters nil", function()
    vim.cmd("WorkflowGraphStats main-topic=X topic=Y")
    assert.are.same({ main_topic = "X", topic = "Y" }, calls.graph_stats[1])
  end)

  it("parses a simple key and drops a malformed bareword", function()
    vim.cmd("WorkflowNotePicker tag=foo")
    assert.are.equal("foo", calls.pick_notes[1].tag)
    calls.pick_notes = nil
    vim.cmd("WorkflowNotePicker bareword")
    assert.are.same({}, calls.pick_notes[1])
  end)

  it("splits +tag/-tag tokens and treats bare tokens as additions", function()
    vim.cmd("WorkflowNoteTag id1 +a -b c")
    assert.are.same({ "id1", { "a", "c" }, { "b" }, {} }, calls.tag_note)
  end)

  it("guards arity: too few args notify a usage message and do not call the handler", function()
    vim.cmd("WorkflowContentUnlinkBib onlyone")
    assert.is_true(notified("Usage:"))
    assert.is_nil(calls.content_unlink_bib)
  end)
end)
