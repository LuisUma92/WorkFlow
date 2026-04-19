-- lua/workflow/picker/prisma_bib.lua
-- Snacks.picker for PRISMA bibliography entries.

local server = require("workflow.server")

local M = {}

local function fmt_authors(authors)
  if not authors or #authors == 0 then return "" end
  local parts = {}
  for _, a in ipairs(authors) do
    if a.first_author then
      table.insert(parts, 1, a.last_name or "")
    else
      table.insert(parts, a.last_name or "")
    end
  end
  return table.concat(parts, ", ")
end

---@param opts table|nil picker opts (plus optional `year`, `type`, `config`)
function M.pick(opts)
  opts = opts or {}
  local config = opts.config or require("workflow.config").resolve(opts)

  local args = { "prisma", "bib", "list", "--json" }
  if opts.year then
    local y = tonumber(opts.year)
    if not y then
      vim.notify(
        "year must be numeric, got: " .. tostring(opts.year),
        vim.log.levels.ERROR,
        { title = "workflow" }
      )
      return
    end
    table.insert(args, "--year")
    table.insert(args, tostring(y))
  end
  if opts.type then
    table.insert(args, "--type")
    table.insert(args, tostring(opts.type))
  end

  server.run_cli(args, config, function(ok, output)
    if not ok then
      vim.notify("Failed to list bib entries:\n" .. output, vim.log.levels.ERROR, { title = "workflow" })
      return
    end

    local ok_json, decoded = pcall(vim.json.decode, output)
    if not ok_json then
      vim.notify("Invalid JSON from CLI", vim.log.levels.ERROR, { title = "workflow" })
      return
    end
    if not decoded or #decoded == 0 then
      vim.notify("No bibliography entries found.", vim.log.levels.INFO, { title = "workflow" })
      return
    end

    local items = {}
    for _, entry in ipairs(decoded) do
      local year = entry.year and tostring(entry.year) or "?"
      local authors = fmt_authors(entry.authors)
      local title = entry.title or "(no title)"
      table.insert(items, {
        text = string.format("[%s] %s — %s (%s)", entry.bibkey or "?", title, authors, year),
        item = entry,
      })
    end

    Snacks.picker({
      title = "PRISMA Bibliography",
      items = items,
      format = function(item) return { { item.text } } end,
      preview = function(ctx)
        local e = ctx.item.item
        local lines = {
          string.format("[%s] %s", e.entry_type or "?", e.title or "(no title)"),
          string.format("Year: %s   Key: %s", tostring(e.year or "?"), e.bibkey or "?"),
        }
        if e.journaltitle then table.insert(lines, "Journal: " .. e.journaltitle) end
        if e.doi then table.insert(lines, "DOI: " .. e.doi) end
        if e.authors and #e.authors > 0 then
          local full = {}
          for _, a in ipairs(e.authors) do
            table.insert(full, string.format("%s, %s", a.last_name or "", a.first_name or ""))
          end
          table.insert(lines, "Authors: " .. table.concat(full, "; "))
        end
        if e.abstract_text and e.abstract_text ~= "" then
          table.insert(lines, "")
          table.insert(lines, "Abstract:")
          for line in e.abstract_text:gmatch("[^\r\n]+") do
            table.insert(lines, "  " .. line)
          end
        end
        return lines
      end,
      confirm = function(picker, item)
        picker:close()
        if item and item.item and item.item.bibkey then
          vim.fn.setreg("+", item.item.bibkey)
          vim.notify(
            string.format("Yanked bibkey: %s (id=%d)", item.item.bibkey, item.item.id),
            vim.log.levels.INFO,
            { title = "workflow" }
          )
        end
      end,
    })
  end)
end

return M
