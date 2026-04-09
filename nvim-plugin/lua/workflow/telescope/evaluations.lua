-- lua/workflow/telescope/evaluations.lua
-- Telescope picker for evaluation templates

local pickers = require("telescope.pickers")
local finders = require("telescope.finders")
local conf = require("telescope.config").values
local actions = require("telescope.actions")
local action_state = require("telescope.actions.state")
local previewers = require("telescope.previewers")
local server = require("workflow.server")

local M = {}

--- Build display line for an evaluation template
---@param entry table decoded JSON entry
---@return string
local function make_display(entry)
  return string.format(
    "[%s] %s (%d pts, %d items)",
    entry.institution,
    entry.name,
    entry.total_points,
    entry.item_count
  )
end

--- Fetch evaluations via CLI and open Telescope picker
---@param opts table|nil Telescope opts (plus optional `inst` filter)
function M.picker(opts)
  opts = opts or {}
  local config = require("workflow.config").resolve(opts)

  local args = { "evaluations", "list", "--json", "--full" }
  if opts.inst then
    table.insert(args, "--inst")
    table.insert(args, opts.inst)
  end

  server.run_cli(args, config, function(ok, output)
    if not ok then
      vim.notify("Failed to list evaluations:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
      return
    end

    local ok_json, decoded = pcall(vim.json.decode, output)
    if not ok_json or not decoded or #decoded == 0 then
      if not ok_json then
        vim.notify("Invalid response from CLI", vim.log.levels.ERROR, { title = "workflow" })
      else
        vim.notify("No evaluation templates found.", vim.log.levels.INFO, { title = "workflow" })
      end
      return
    end

    pickers.new(opts, {
      prompt_title = "Evaluation Templates",
      finder = finders.new_table({
        results = decoded,
        entry_maker = function(entry)
          return {
            value = entry,
            display = make_display(entry),
            ordinal = entry.institution .. " " .. entry.name,
            id = entry.id,
          }
        end,
      }),
      sorter = conf.generic_sorter(opts),
      previewer = previewers.new_buffer_previewer({
        title = "Template Detail",
        define_preview = function(self, entry)
          local val = entry.value
          local lines = {
            string.format("[%s] %s", val.institution, val.name),
            string.format("Total: %d pts  |  Items: %d", val.total_points, val.item_count),
            "",
          }
          if val.description and val.description ~= "" then
            table.insert(lines, "Description: " .. val.description)
            table.insert(lines, "")
          end
          if val.items then
            for i, it in ipairs(val.items) do
              table.insert(lines, string.format(
                "  %d. %s — %s / %s  %d × %d pts",
                i, it.item_name, it.taxonomy_domain, it.taxonomy_level,
                it.amount, it.points_per_item
              ))
            end
          end
          vim.api.nvim_buf_set_lines(self.state.bufnr, 0, -1, false, lines)
        end,
      }),
      attach_mappings = function(prompt_bufnr, map)
        actions.select_default:replace(function()
          actions.close(prompt_bufnr)
          local selection = action_state.get_selected_entry()
          if selection then
            vim.notify(
              string.format("Selected: [%s] %s (id=%d)",
                selection.value.institution,
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
