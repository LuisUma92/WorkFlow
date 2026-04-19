-- lua/workflow/picker/prisma_keywords.lua
-- Snacks.picker for PRISMA search keywords.
-- Preview shows `review stats --keyword-id <id>` live counts.
-- Confirm opens the review picker scoped to the selected keyword.

local server = require("workflow.server")

local M = {}

-- Module-level stats cache keyed by keyword id.
-- Snacks may copy the item table between re-renders so mutating
-- ctx.item is unreliable; caching here survives across renders.
--   _stats_cache[id] = false        -- fetch in flight
--   _stats_cache[id] = stats table  -- loaded
--   _stats_cache[id] = "error"      -- CLI failed
local _stats_cache = {}

local function fetch_stats_async(kw_id, config)
  if _stats_cache[kw_id] ~= nil then return end
  _stats_cache[kw_id] = false
  server.run_cli(
    { "prisma", "review", "stats", "--keyword-id", tostring(kw_id), "--json" },
    config,
    function(ok, output)
      if not ok then
        _stats_cache[kw_id] = "error"
        return
      end
      local ok_json, decoded = pcall(vim.json.decode, output)
      _stats_cache[kw_id] = (ok_json and decoded) or "error"
    end
  )
end

function M.pick(opts)
  opts = opts or {}
  local config = require("workflow.config").resolve(opts)

  server.run_cli({ "prisma", "keyword", "list", "--json" }, config, function(ok, output)
    if not ok then
      vim.notify("Failed to list keywords:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
      return
    end

    local ok_json, decoded = pcall(vim.json.decode, output)
    if not ok_json then
      vim.notify("Invalid JSON from CLI", vim.log.levels.ERROR, { title = "workflow" })
      return
    end
    if not decoded or #decoded == 0 then
      vim.notify("No keywords defined.", vim.log.levels.INFO, { title = "workflow" })
      return
    end

    local items = {}
    for _, kw in ipairs(decoded) do
      table.insert(items, {
        text = string.format("%-4d  %s", kw.id, kw.keyword_list or ""),
        item = kw,
      })
    end

    Snacks.picker({
      title = "PRISMA Keywords",
      items = items,
      format = function(item) return { { item.text } } end,
      preview = function(ctx)
        local kw = ctx.item.item
        local lines = {
          string.format("Keyword: %s (id=%d)", kw.keyword_list or "", kw.id),
          "",
        }
        fetch_stats_async(kw.id, config)
        local s = _stats_cache[kw.id]
        if type(s) == "table" then
          table.insert(lines, string.format("Included: %d", s.included))
          table.insert(lines, string.format("Excluded: %d", s.excluded))
          table.insert(lines, string.format("Pending:  %d", s.pending))
          table.insert(lines, string.format("Total:    %d", s.total))
        elseif s == "error" then
          table.insert(lines, "(stats unavailable)")
        else
          table.insert(lines, "Loading stats...")
        end
        return lines
      end,
      confirm = function(picker, item)
        picker:close()
        if item and item.item then
          require("workflow.picker.prisma_reviews").pick({
            keyword_id = item.item.id,
            config = config,
          })
        end
      end,
    })
  end)
end

return M
