-- lua/workflow/templates.lua
-- Note creation from templates

local M = {}
local UI = require("workflow.ui")

local TEMPLATES = {
  permanent = {
    "---",
    "id: %s",
    "title: \"%s\"",
    "type: permanent",
    "created: %s",
    "tags: []",
    "concepts: []",
    "exercises: []",
    "images: []",
    "---",
    "",
    "## Summary",
    "",
    "## Key ideas",
    "",
    "## Connections",
  },
  literature = {
    "---",
    "id: %s",
    "title: \"%s\"",
    "type: literature",
    "bibkey: %s",
    "created: %s",
    "tags: []",
    "---",
    "",
    "## Key ideas",
    "",
    "## Chapter notes",
    "",
    "## Questions raised",
    "",
    "## Connections",
  },
  fleeting = {
    "---",
    "id: %s",
    "title: \"%s\"",
    "type: fleeting",
    "created: %s",
    "tags: []",
    "---",
    "",
  },
}

function M.generate_id()
  return os.date("%Y%m%d") .. "-"
end

function M.create_note(note_type, opts, config)
  local template = TEMPLATES[note_type]
  if not template then
    vim.notify("Unknown note type: " .. note_type, vim.log.levels.ERROR, { title = "workflow" })
    return nil
  end

  local id = opts.id or M.generate_id()
  local title = opts.title or ""
  local date = os.date("%Y-%m-%d")
  local bibkey = opts.bibkey or ""

  local lines = {}
  for _, line in ipairs(template) do
    local formatted = line:format(id, title, bibkey, date)
    -- Handle extra %s that don't apply
    formatted = formatted:gsub("%%s", "")
    table.insert(lines, formatted)
  end

  -- Determine output path
  local dir = opts.dir or (config.workspace_dir and (config.workspace_dir .. "/" .. config.vault_dir .. "/inbox"))
  if not dir then
    vim.notify("No workspace directory configured", vim.log.levels.ERROR, { title = "workflow" })
    return nil
  end

  vim.fn.mkdir(dir, "p")
  local filepath = dir .. "/" .. id .. ".md"

  if vim.fn.filereadable(filepath) == 1 then
    vim.notify("File already exists: " .. filepath, vim.log.levels.WARN, { title = "workflow" })
    vim.cmd("edit " .. vim.fn.fnameescape(filepath))
    return filepath
  end

  vim.fn.writefile(lines, filepath)
  vim.cmd("edit " .. vim.fn.fnameescape(filepath))
  -- Place cursor on the id line for immediate editing
  vim.api.nvim_win_set_cursor(0, { 2, 4 })

  return filepath
end

function M.prompt_new_note(note_type, config)
  local fields = {
    { name = "id", label = "ID (YYYYMMDD-topic)", default = M.generate_id() },
    { name = "title", label = "Title", default = "" },
  }

  if note_type == "literature" then
    table.insert(fields, { name = "bibkey", label = "BibTeX key", default = "" })
  end

  -- Ask for project directory
  table.insert(fields, { name = "dir", label = "Directory (empty=inbox)", default = "" })

  UI.prompt_form("New " .. note_type .. " note", fields, function(values)
    local dir = values.dir
    if dir == "" then dir = nil end
    M.create_note(note_type, {
      id = values.id,
      title = values.title,
      bibkey = values.bibkey,
      dir = dir,
    }, config)
  end)
end

return M
