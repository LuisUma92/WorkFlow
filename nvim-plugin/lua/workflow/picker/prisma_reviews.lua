-- lua/workflow/picker/prisma_reviews.lua
-- Snacks.picker for PRISMA review records (keyword-scoped).

local server = require("workflow.server")

local M = {}

local VALID_STATUS = { included = true, excluded = true, pending = true }

local STATUS_LABEL = {
  [1] = "[+]",
  [0] = "[-]",
}

local function is_missing(v)
  return v == nil or v == vim.NIL
end

local function status_marker(included)
  if is_missing(included) then return "[ ]" end
  return STATUS_LABEL[included] or "[?]"
end

---@param opts table must include `keyword_id`; optional `status`, `config`
function M.pick(opts)
  opts = opts or {}
  local config = opts.config or require("workflow.config").resolve(opts)

  if not opts.keyword_id then
    vim.notify("keyword_id is required for review picker", vim.log.levels.ERROR, { title = "workflow" })
    return
  end

  if opts.status and not VALID_STATUS[opts.status] then
    vim.notify(
      "Invalid status: " .. tostring(opts.status) .. " (expected included|excluded|pending)",
      vim.log.levels.ERROR,
      { title = "workflow" }
    )
    return
  end

  local args = { "prisma", "review", "list", "--keyword-id", tostring(opts.keyword_id), "--json" }
  if opts.status then
    table.insert(args, "--status")
    table.insert(args, opts.status)
  end

  server.run_cli(args, config, function(ok, output)
    if not ok then
      vim.notify("Failed to list reviews:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
      return
    end

    local ok_json, decoded = pcall(vim.json.decode, output)
    if not ok_json then
      vim.notify("Invalid JSON from CLI", vim.log.levels.ERROR, { title = "workflow" })
      return
    end
    if not decoded or #decoded == 0 then
      vim.notify("No review records for this keyword.", vim.log.levels.INFO, { title = "workflow" })
      return
    end

    local items = {}
    for _, rec in ipairs(decoded) do
      local year = rec.year and tostring(rec.year) or "?"
      local title = rec.title or "(no title)"
      if #title > 60 then title = title:sub(1, 57) .. "..." end
      table.insert(items, {
        text = string.format("%s %4d  (%s)  %s", status_marker(rec.included), rec.id, year, title),
        item = rec,
      })
    end

    Snacks.picker({
      title = string.format("PRISMA Reviews (keyword id=%d)", opts.keyword_id),
      items = items,
      format = function(item) return { { item.text } } end,
      preview = function(ctx)
        local r = ctx.item.item
        local status
        if is_missing(r.included) then
          status = "pending"
        elseif r.included == 1 then
          status = "included"
        elseif r.included == 0 then
          status = "excluded"
        else
          status = "?"
        end
        local lines = {
          string.format("Review id=%d  status=%s", r.id, status),
          string.format("Bib id=%d  key=%s  year=%s",
            r.bib_entry_id, r.bibkey or "?", tostring(r.year or "?")),
          "",
          "Title:",
          "  " .. (r.title or "(no title)"),
        }
        if r.include_rationale then
          table.insert(lines, "")
          table.insert(lines, "Include rationale:")
          table.insert(lines, "  " .. r.include_rationale)
        end
        if r.retrieve_rationale then
          table.insert(lines, "")
          table.insert(lines, "Retrieve rationale:")
          table.insert(lines, "  " .. r.retrieve_rationale)
        end
        return lines
      end,
      confirm = function(picker, item)
        picker:close()
        if item and item.item then
          vim.fn.setreg("+", tostring(item.item.bib_entry_id))
          vim.notify(
            string.format("Yanked bib_entry_id: %d (review id=%d)",
              item.item.bib_entry_id, item.item.id),
            vim.log.levels.INFO,
            { title = "workflow" }
          )
        end
      end,
    })
  end)
end

return M
