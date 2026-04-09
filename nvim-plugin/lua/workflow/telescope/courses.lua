-- lua/workflow/telescope/courses.lua
-- Telescope picker for courses

local pickers = require("telescope.pickers")
local finders = require("telescope.finders")
local conf = require("telescope.config").values
local actions = require("telescope.actions")
local action_state = require("telescope.actions.state")
local server = require("workflow.server")

local M = {}

--- Build display line for a course
---@param entry table decoded JSON entry
---@return string
local function make_display(entry)
  return string.format(
    "[%s] %-10s  %s  (%dlpw %dhpl)",
    entry.institution,
    entry.code,
    entry.name,
    entry.lectures_per_week,
    entry.hours_per_lecture
  )
end

--- Fetch courses via CLI and open Telescope picker
---@param opts table|nil Telescope opts (plus optional `inst` filter)
function M.picker(opts)
  opts = opts or {}
  local config = require("workflow.config").resolve(opts)

  local args = { "course", "list", "--json" }
  if opts.inst then
    table.insert(args, "--inst")
    table.insert(args, opts.inst)
  end

  server.run_cli(args, config, function(ok, output)
    if not ok then
      vim.notify("Failed to list courses:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
      return
    end

    local ok_json, decoded = pcall(vim.json.decode, output)
    if not ok_json or not decoded or #decoded == 0 then
      if not ok_json then
        vim.notify("Invalid response from CLI", vim.log.levels.ERROR, { title = "workflow" })
      else
        vim.notify("No courses found.", vim.log.levels.INFO, { title = "workflow" })
      end
      return
    end

    pickers.new(opts, {
      prompt_title = "Courses",
      finder = finders.new_table({
        results = decoded,
        entry_maker = function(entry)
          return {
            value = entry,
            display = make_display(entry),
            ordinal = entry.institution .. " " .. entry.code .. " " .. entry.name,
            id = entry.id,
          }
        end,
      }),
      sorter = conf.generic_sorter(opts),
      attach_mappings = function(prompt_bufnr)
        actions.select_default:replace(function()
          actions.close(prompt_bufnr)
          local selection = action_state.get_selected_entry()
          if selection then
            vim.notify(
              string.format("Selected: [%s] %s — %s (id=%d)",
                selection.value.institution,
                selection.value.code,
                selection.value.name,
                selection.value.id
              ),
              vim.log.levels.INFO,
              { title = "workflow" }
            )
          end
        end)
        return true
      end,
    }):find()
  end)
end

return M
