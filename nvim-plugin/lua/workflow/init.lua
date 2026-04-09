-- lua/workflow/init.lua
-- WorkFlow Neovim plugin — complements obsidian.nvim with DB sync,
-- validation, promote, and exercise/image integration.
--
-- Uses CLI calls (not JSONL server) for reliability.

local Config = require("workflow.config")

local M = {}

M._config = nil

function M.setup(opts)
  M._config = Config.resolve(opts)

  -- Register autocommands
  require("workflow.autocmds").setup(M._config)

  -- Register user commands
  require("workflow.commands").setup(M)

  -- Register keymaps
  if M._config.keymaps then
    require("workflow.keymaps").setup(M._config.keymap_prefix, M)
  end
end

-- Public actions

function M.sync_current()
  require("workflow.server").sync(M._config)
end

function M.validate_frontmatter()
  require("workflow.frontmatter").validate_buffer(vim.api.nvim_get_current_buf())
end

function M.promote_note()
  local bufnr = vim.api.nvim_get_current_buf()
  local filepath = vim.api.nvim_buf_get_name(bufnr)

  if not filepath or filepath == "" then
    vim.notify("No file open", vim.log.levels.WARN, { title = "workflow" })
    return
  end

  if not M._config or not M._config.workspace_dir then
    vim.notify("No workspace configured", vim.log.levels.WARN, { title = "workflow" })
    return
  end

  local workspace = vim.fn.expand(M._config.workspace_dir)
  local vault = workspace .. "/" .. M._config.vault_dir
  local inbox = vault .. "/inbox"

  -- Check if file is in inbox
  if not vim.startswith(filepath, inbox) then
    vim.notify("Note is not in inbox — already promoted?", vim.log.levels.INFO, { title = "workflow" })
    return
  end

  -- Move file from inbox/ to vault root
  local filename = vim.fn.fnamemodify(filepath, ":t")
  local dest = vault .. "/" .. filename

  if vim.fn.filereadable(dest) == 1 then
    vim.notify("Destination exists: " .. dest, vim.log.levels.ERROR, { title = "workflow" })
    return
  end

  -- Save buffer, close, move file, reopen
  vim.cmd("write")
  vim.cmd("bdelete")
  vim.fn.rename(filepath, dest)

  -- Update type from fleeting to permanent in the moved file
  local lines = vim.fn.readfile(dest)
  for i, line in ipairs(lines) do
    if line:match("^type:%s*fleeting") then
      lines[i] = "type: permanent"
      break
    end
  end
  vim.fn.writefile(lines, dest)

  -- Open the promoted note
  vim.cmd("edit " .. vim.fn.fnameescape(dest))
  vim.notify("Promoted to permanent: " .. filename, vim.log.levels.INFO, { title = "workflow" })
end

-- Snacks pickers (Phase 3)

function M.pick_evaluations(opts)
  require("workflow.picker.evaluations").pick(opts)
end

function M.pick_items(opts)
  require("workflow.picker.items").pick(opts)
end

function M.pick_courses(opts)
  require("workflow.picker.courses").pick(opts)
end

-- Statusline component
function M.statusline()
  return require("workflow.statusline").component()
end

return M
