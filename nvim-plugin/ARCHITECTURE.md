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
    autocmds.lua          -- BufWritePost sync, BufEnter detection, FileType tex includeexpr wrapper
    tex_macros.lua        -- pure LaTeX macro scanning/expansion (no Neovim API)
    tex_paths.lua         -- macro sources (buffer/vimtex main/.sty dirs) + includeexpr wrapper
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

## LaTeX path-macro resolution (`gf` in .tex)

`tex_macros.lua` (pure strings) + `tex_paths.lua` (Neovim glue) + a `FileType
tex` autocmd in `autocmds.lua` let `gf` follow paths written through macros
such as `\input{\EEfolder/ej.tex}`, whose definitions live in the shipped
`.sty` files rather than in the buffer.

Design rules (plan `tasks/plans/2026-08-19-tex-gf-macro-expansion.md`):

- **Wrap `includeexpr`, never remap `gf`.** Every builtin that consults
  `includeexpr` (`gf`, `gF`, `[f`, `<C-w>f`, `:checkpath`, `<C-x><C-i>`) gains
  the feature at once, and vimtex keeps ownership of its keymaps.
- **vimtex stays the fallback.** The previous `includeexpr` is saved per buffer
  and delegated to whenever macro expansion does not yield a readable file, so
  kpsewhich, `$TEXINPUTS`, `.bib` and `\subimport` resolution are unaffected.
- **The wrapper is re-asserted via `vim.schedule()`.** The tex ftplugin
  (vimtex's `setlocal includeexpr=vimtex#include#expr()`, or the runtime one)
  is sourced *after* our `FileType` callback and would otherwise clobber it;
  the scheduled re-assert runs once the whole FileType chain is done. The
  attach is idempotent and never records our own expression as "previous".
- Config keys: `tex_gf` (default `true`), `tex_macro_sty_dirs`
  (default `{ "~/.local/share/workflow/latex/sty", "~/.local/share/workflow/sty" }`).

## Implementation Phases

- **Phase 1**: Core daily workflow (server, gf, sync, templates, validation, statusline)
- **Phase 2**: Search and completion (Telescope, nvim-cmp, exercise/image browsers)
- **Phase 3**: Graph, remaining routes, documentation
