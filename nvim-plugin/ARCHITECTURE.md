# workflow.nvim — Neovim Plugin Architecture

## Overview

Neovim plugin for the WorkFlow Zettelkasten system. Provides wiki-link navigation, note creation from templates, auto-sync on save, frontmatter validation, Telescope pickers, and integration with the latexzettel JSONL RPC server (24 routes).

## Directory Structure

```
nvim-plugin/
  lua/workflow/
    init.lua              -- setup(), public API, lazy server start
    client.lua            -- JSONL stdio client (forked from latexzettel)
    config.lua            -- user config schema, defaults, workspace detection
    server.lua            -- server lifecycle, auto-start, health
    wikilink.lua          -- [[id]] parsing, gf navigation, concealment
    completion.lua        -- nvim-cmp source for [[id]] completion
    autocmds.lua          -- BufWritePost sync, BufEnter detection
    keymaps.lua           -- <leader>z namespace
    commands.lua          -- :Workflow* user commands
    statusline.lua        -- lualine component
    frontmatter.lua       -- YAML frontmatter parse + validation
    templates.lua         -- note creation (permanent/literature/fleeting)
    ui.lua                -- floating windows (forked from latexzettel)
    telescope/
      init.lua            -- Telescope extension registration
      notes.lua           -- note picker
      exercises.lua       -- exercise picker
      images.lua          -- TikZ image picker
      graph.lua           -- graph neighbors picker
  plugin/workflow.lua     -- bootstrap
  doc/workflow.txt        -- vimdoc
```

## Keybindings (<leader>z)

| Key | Action | Phase |
|-----|--------|-------|
| `<leader>zn` | New permanent note | 1 |
| `<leader>zl` | New literature note | 1 |
| `<leader>zf` | New fleeting note | 1 |
| `<leader>zs` | Sync current buffer | 1 |
| `<leader>zv` | Validate frontmatter | 1 |
| `<leader>zr` | Recent notes | 1 |
| `gf` | Go to wiki-link under cursor | 1 |
| `<leader>zp` | Telescope note picker | 2 |
| `<leader>ze` | Telescope exercise picker | 2 |
| `<leader>zi` | Telescope image picker | 2 |
| `<leader>zw` | Insert wiki-link | 2 |
| `<leader>zu` | Render current note | 2 |
| `<leader>zg` | Graph neighbors | 3 |
| `<leader>zo` | Orphaned notes | 3 |
| `<leader>z!` | Server restart | 1 |

## Implementation Phases

- **Phase 1**: Core daily workflow (server, gf, sync, templates, validation, statusline)
- **Phase 2**: Search and completion (Telescope, nvim-cmp, exercise/image browsers)
- **Phase 3**: Graph, remaining routes, documentation
