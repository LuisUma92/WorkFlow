-- nvim-plugin/tests/plenary/picker/graph_neighbors_spec.lua
-- Plenary busted unit tests for workflow.picker.graph_neighbors
-- minimal_init.lua centralizes package.path; bootstrap block mirrors edges_spec.
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

local CONTRACT_JSON = vim.json.encode({
	source = {
		id = "note:42",
		title = "Newton's law",
		path = "/abs/vault/notes/permanent/foo.md",
	},
	neighbors = {
		{
			id = "note:7",
			title = "FBD",
			path = "/abs/vault/notes/permanent/fbd.md",
			edge_class = nil,
			relation_type = "link",
			depth = 1,
		},
		{
			id = "concept:3",
			title = "Force",
			path = nil, -- non-note neighbor: no file
			edge_class = "concept",
			relation_type = nil,
			depth = 2,
		},
	},
})

local EMPTY_JSON = vim.json.encode({
	source = { id = "note:42", title = "Newton's law", path = "/abs/vault/notes/permanent/foo.md" },
	neighbors = {},
})

-- Load dependency modules once so the rtp loader fires.
local server = require("workflow.server")
local config_mod = require("workflow.config")

-- ---------------------------------------------------------------------------
-- Suite
-- ---------------------------------------------------------------------------

describe("workflow.picker.graph_neighbors", function()
	local gn

	local orig_run_cli
	local orig_config_resolve
	local orig_notify
	local orig_snacks_pkg
	local orig_vim_cmd

	local captured_spec
	local notify_calls
	local captured_args
	local vim_cmd_calls

	before_each(function()
		-- Bust the picker cache so it re-reads stubbed server/config.
		package.loaded["workflow.picker.graph_neighbors"] = nil

		-- Save originals.
		orig_run_cli = server.run_cli
		orig_config_resolve = config_mod.resolve
		orig_notify = vim.notify
		orig_snacks_pkg = package.loaded["snacks"]
		orig_vim_cmd = vim.cmd

		-- Default stubs.
		captured_args = nil
		server.run_cli = function(args, cfg, cb)
			captured_args = args
			cb(true, CONTRACT_JSON)
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

		notify_calls = {}
		vim.notify = function(msg, level, opts)
			table.insert(notify_calls, { msg = msg, level = level, opts = opts })
		end

		vim_cmd_calls = {}
		vim.cmd = function(cmd)
			table.insert(vim_cmd_calls, cmd)
		end

		gn = require("workflow.picker.graph_neighbors")
	end)

	after_each(function()
		server.run_cli = orig_run_cli
		config_mod.resolve = orig_config_resolve
		vim.notify = orig_notify
		package.loaded["snacks"] = orig_snacks_pkg
		vim.cmd = orig_vim_cmd
		package.loaded["workflow.picker.graph_neighbors"] = nil
	end)

	-- -------------------------------------------------------------------------
	-- Case 1: contract — items built correctly from JSON
	-- -------------------------------------------------------------------------
	it("builds 2 items with correct text and item fields from contract JSON", function()
		gn.pick({ node_id = "note:42" })

		assert.is_not_nil(captured_spec, "Snacks.picker should have been called")
		assert.equals(2, #captured_spec.items)

		local item1 = captured_spec.items[1]
		-- depth=1, title="FBD", relation_type="link"
		assert.equals("[d1] FBD  (link)", item1.text)
		assert.equals(1, item1.item.depth)
		assert.equals("/abs/vault/notes/permanent/fbd.md", item1.item.path)

		local item2 = captured_spec.items[2]
		-- depth=2, title="Force", edge_class="concept", relation_type=nil → fallback to edge_class
		assert.equals("[d2] Force  (concept)", item2.text)
		assert.equals(2, item2.item.depth)
		-- path is JSON null → vim.NIL or nil after decode (nvim version-dependent)
		assert.is_true(item2.item.path == vim.NIL or item2.item.path == nil,
			"expected path to be nil or vim.NIL for JSON null")
	end)

	-- -------------------------------------------------------------------------
	-- Case 2: confirm opens a non-null path
	-- -------------------------------------------------------------------------
	it("confirm() opens file when path is non-null", function()
		gn.pick({ node_id = "note:42" })

		assert.is_not_nil(captured_spec)

		local fake_picker = { close = function() end }
		captured_spec.confirm(fake_picker, captured_spec.items[1])

		assert.equals(1, #vim_cmd_calls, "expected exactly one vim.cmd call")
		assert.is_truthy(vim_cmd_calls[1]:find("edit"), "expected 'edit' in vim.cmd call")
		assert.is_truthy(vim_cmd_calls[1]:find("fbd%.md"), "expected fbd.md in vim.cmd call")
	end)

	-- -------------------------------------------------------------------------
	-- Case 3: confirm on null-path neighbor → warn, no vim.cmd
	-- -------------------------------------------------------------------------
	it("confirm() warns and does NOT open file when path is vim.NIL", function()
		gn.pick({ node_id = "note:42" })

		assert.is_not_nil(captured_spec)

		local fake_picker = { close = function() end }
		-- items[2] has path = vim.NIL (decoded from JSON null)
		captured_spec.confirm(fake_picker, captured_spec.items[2])

		assert.equals(0, #vim_cmd_calls, "vim.cmd must NOT be called for null-path node")

		local found = false
		for _, call in ipairs(notify_calls) do
			if call.msg:find("No file for this node") then
				found = true
				break
			end
		end
		assert.is_true(found, "Expected 'No file for this node' notification")
	end)

	-- -------------------------------------------------------------------------
	-- Case 4: empty neighbors → notify "No neighbors found."
	-- -------------------------------------------------------------------------
	it("notifies 'No neighbors found.' when neighbors array is empty", function()
		server.run_cli = function(args, cfg, cb)
			captured_args = args
			cb(true, EMPTY_JSON)
		end

		gn.pick({ node_id = "note:42" })

		assert.is_nil(captured_spec, "Snacks.picker should NOT be called for empty results")

		local found = false
		for _, call in ipairs(notify_calls) do
			if call.msg:find("No neighbors found") then
				found = true
				break
			end
		end
		assert.is_true(found, "Expected 'No neighbors found.' notification")
	end)

	-- -------------------------------------------------------------------------
	-- Case 5: snacks-guard — no error, notify about snacks requirement
	-- -------------------------------------------------------------------------
	it("notifies 'snacks.nvim is required' when snacks cannot be loaded", function()
		package.loaded["snacks"] = nil
		local orig_preload = package.preload["snacks"]
		package.preload["snacks"] = function()
			error("snacks not installed")
		end

		local ok, err = pcall(function()
			gn.pick({ node_id = "note:42" })
		end)

		if orig_preload then
			package.preload["snacks"] = orig_preload
		else
			package.preload["snacks"] = nil
		end

		assert.is_true(ok, "pick() must not raise an error: " .. tostring(err))

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
	-- Case 6: depth opt forwarded into CLI args
	-- -------------------------------------------------------------------------
	it("forwards --depth N into CLI args when opts.depth is set", function()
		gn.pick({ node_id = "note:1", depth = 2 })

		assert.is_not_nil(captured_args, "expected run_cli to be called")

		local found_depth_flag = false
		local found_depth_value = false
		for i, v in ipairs(captured_args) do
			if v == "--depth" then
				found_depth_flag = true
				if captured_args[i + 1] == "2" then
					found_depth_value = true
				end
			end
		end
		assert.is_true(found_depth_flag, "expected '--depth' in args")
		assert.is_true(found_depth_value, "expected '2' after '--depth' in args")
	end)
end)
