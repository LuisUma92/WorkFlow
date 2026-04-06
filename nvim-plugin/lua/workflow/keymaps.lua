-- lua/workflow/keymaps.lua
local M = {}

function M.setup(prefix, workflow)
  local opts = { noremap = true, silent = true }

  -- P0: Core
  vim.keymap.set("n", prefix .. "n", function() workflow.new_note("permanent") end,
    vim.tbl_extend("force", opts, { desc = "workflow: new permanent note" }))
  vim.keymap.set("n", prefix .. "l", function() workflow.new_note("literature") end,
    vim.tbl_extend("force", opts, { desc = "workflow: new literature note" }))
  vim.keymap.set("n", prefix .. "f", function() workflow.new_note("fleeting") end,
    vim.tbl_extend("force", opts, { desc = "workflow: new fleeting note" }))
  vim.keymap.set("n", prefix .. "s", function() workflow.sync_current() end,
    vim.tbl_extend("force", opts, { desc = "workflow: sync current buffer" }))
  vim.keymap.set("n", prefix .. "v", function() workflow.validate_frontmatter() end,
    vim.tbl_extend("force", opts, { desc = "workflow: validate frontmatter" }))
  vim.keymap.set("n", prefix .. "r", function() workflow.list_recent() end,
    vim.tbl_extend("force", opts, { desc = "workflow: recent notes" }))

  -- Server management
  vim.keymap.set("n", prefix .. "!", function() workflow.server_restart() end,
    vim.tbl_extend("force", opts, { desc = "workflow: restart server" }))
end

-- Buffer-local gf override for wiki-links
function M.setup_buffer_gf(bufnr, config)
  vim.keymap.set("n", "gf", function()
    local wikilink = require("workflow.wikilink")
    local link = wikilink.parse_under_cursor()
    if link then
      wikilink.goto_note(link.id, config)
    else
      -- Fall back to default gf
      vim.cmd("normal! gF")
    end
  end, { buffer = bufnr, noremap = true, silent = true, desc = "workflow: go to wiki-link" })
end

return M
