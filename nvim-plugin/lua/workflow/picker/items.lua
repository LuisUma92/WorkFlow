-- lua/workflow/picker/items.lua
-- Snacks.picker for taxonomy items

local server = require("workflow.server")

local M = {}

---@param opts table|nil picker opts (plus optional `domain`, `level` filters)
function M.pick(opts)
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

    local items = {}
    for _, entry in ipairs(decoded) do
      table.insert(items, {
        text = string.format("%4d  %-40s  %s / %s",
          entry.id, entry.name, entry.taxonomy_domain, entry.taxonomy_level),
        item = entry,
      })
    end

    Snacks.picker({
      title = "Taxonomy Items",
      items = items,
      format = function(item)
        return {
          { item.text },
        }
      end,
      confirm = function(picker, item)
        picker:close()
        if item then
          vim.notify(
            string.format("Selected: %s (id=%d)", item.item.name, item.item.id),
            vim.log.levels.INFO,
            { title = "workflow" }
          )
        end
      end,
    })
  end)
end

return M
