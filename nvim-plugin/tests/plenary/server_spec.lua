-- nvim-plugin/tests/plenary/server_spec.lua
-- Plenary busted unit tests for workflow.server.run_cli basename allowlist (v1.13.1).
-- minimal_init.lua centralizes package.path, so no per-spec bootstrap is needed.

require("plenary.busted")

local assert = require("luassert")
local server = require("workflow.server")

describe("workflow.server.run_cli basename allowlist", function()
  local captured_cmd
  local notify_calls
  local orig_jobstart
  local orig_notify

  before_each(function()
    captured_cmd = nil
    notify_calls = {}
    orig_jobstart = vim.fn.jobstart
    orig_notify = vim.notify
    -- shadow vim.fn.jobstart (rawset key wins over the __index dispatcher)
    vim.fn.jobstart = function(cmd, _opts)
      captured_cmd = cmd
      return 1
    end
    vim.notify = function(msg, level, _opts)
      table.insert(notify_calls, { msg = msg, level = level })
    end
  end)

  after_each(function()
    vim.fn.jobstart = orig_jobstart
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

  it("rejects a workflow_cmd whose basename is not 'workflow' and does not spawn", function()
    server.run_cli({ "topic", "list" }, { workflow_cmd = "/tmp/evil" })
    assert.is_true(notified("basename must be 'workflow'"))
    assert.is_nil(captured_cmd)
  end)

  it("spawns when the basename is 'workflow', appending args in order", function()
    server.run_cli({ "topic", "list", "--json" }, { workflow_cmd = "/usr/local/bin/workflow" })
    assert.is_not_nil(captured_cmd)
    assert.are.equal("/usr/local/bin/workflow", captured_cmd[1])
    assert.are.equal("topic", captured_cmd[2])
    assert.are.equal("list", captured_cmd[3])
    assert.are.equal("--json", captured_cmd[4])
  end)

  it("falls back to the default ~/.local/bin/workflow (basename passes)", function()
    server.run_cli({ "graph", "stats" }, {})
    assert.is_not_nil(captured_cmd)
    assert.is_true(captured_cmd[1]:match("/workflow$") ~= nil)
  end)
end)
