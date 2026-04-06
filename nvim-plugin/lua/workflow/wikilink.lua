-- lua/workflow/wikilink.lua
-- Wiki-link parsing and navigation

local M = {}

-- Pattern: [[id]] or [[id|display]]
local WIKILINK_PATTERN = "%[%[([^%]|]+)|?([^%]]-)%]%]"

function M.parse_under_cursor()
  local line = vim.api.nvim_get_current_line()
  local col = vim.api.nvim_win_get_cursor(0)[2] + 1 -- 1-indexed

  for id, display in line:gmatch(WIKILINK_PATTERN) do
    local start_pos = line:find("%[%[" .. vim.pesc(id))
    if start_pos then
      local end_pos = line:find("%]%]", start_pos) + 1
      if col >= start_pos and col <= end_pos then
        return {
          id = vim.trim(id),
          display = (display ~= "" and vim.trim(display) or nil),
        }
      end
    end
  end
  return nil
end

function M.parse_buffer(bufnr)
  local lines = vim.api.nvim_buf_get_lines(bufnr, 0, -1, false)
  local links = {}
  for lnum, line in ipairs(lines) do
    for id, display in line:gmatch(WIKILINK_PATTERN) do
      table.insert(links, {
        id = vim.trim(id),
        display = (display ~= "" and vim.trim(display) or nil),
        lnum = lnum,
      })
    end
  end
  return links
end

function M.goto_note(id, config)
  if not config or not config.workspace_dir then
    vim.notify("No workspace detected", vim.log.levels.WARN, { title = "workflow" })
    return
  end

  -- Search for the note file in all project notes/ directories
  local workspace = config.workspace_dir
  local patterns = {
    workspace .. "/**/notes/" .. id .. ".md",
    workspace .. "/**/notes/" .. id .. ".tex",
    workspace .. "/**/" .. id .. ".md",
    workspace .. "/**/" .. id .. ".tex",
  }

  for _, pattern in ipairs(patterns) do
    local matches = vim.fn.glob(pattern, false, true)
    if #matches > 0 then
      vim.cmd("edit " .. vim.fn.fnameescape(matches[1]))
      return
    end
  end

  vim.notify("Note not found: " .. id, vim.log.levels.WARN, { title = "workflow" })
end

function M.setup_conceal(bufnr)
  -- Use matchadd for wiki-link concealment
  -- [[id|display]] shows only display, [[id]] shows id
  vim.wo.conceallevel = 2
  vim.wo.concealcursor = "nc"
end

return M
