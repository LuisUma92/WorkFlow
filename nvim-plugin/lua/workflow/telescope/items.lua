-- lua/workflow/telescope/items.lua
-- Telescope picker for taxonomy items

local pickers = require("telescope.pickers")
local finders = require("telescope.finders")
local conf = require("telescope.config").values
local actions = require("telescope.actions")
local action_state = require("telescope.actions.state")
local server = require("workflow.server")

local M = {}

--- Build display line for a taxonomy item
---@param entry table decoded JSON entry
---@return string
local function make_display(entry)
  return string.format(
    "%4d  %-40s  %s / %s",
    entry.id,
    entry.name,
    entry.taxonomy_domain,
    entry.taxonomy_level
  )
end

--- Fetch items via CLI and open Telescope picker
---@param opts table|nil Telescope opts (plus optional `domain`, `level` filters)
function M.picker(opts)
  opts = opts or {}
  local config = require("workflow.config").resolve(opts)

  local args = { "item", "list", "--json" }
  if opts.domain then
    table.insert(args, "--domain")
    table.insert(args, opts.domain)
  end
  if opts.level then
    table.insert(args, "--level")
    table.insert(args, opts.level)
  end

  server.run_cli(args, config, function(ok, output)
    if not ok then
      vim.notify("Failed to list items:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
      return
    end

    local ok_json, decoded = pcall(vim.json.decode, output)
    if not ok_json or not decoded or #decoded == 0 then
      if not ok_json then
        vim.notify("Invalid response from CLI", vim.log.levels.ERROR, { title = "workflow" })
      else
        vim.notify("No taxonomy items found.", vim.log.levels.INFO, { title = "workflow" })
      end
      return
    end

    pickers.new(opts, {
      prompt_title = "Taxonomy Items",
      finder = finders.new_table({
        results = decoded,
        entry_maker = function(entry)
          return {
            value = entry,
            display = make_display(entry),
            ordinal = entry.name .. " " .. entry.taxonomy_domain .. " " .. entry.taxonomy_level,
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
              string.format("Selected: %s (id=%d)", selection.value.name, selection.value.id),
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
