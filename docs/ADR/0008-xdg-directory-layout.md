---
id: 0008
title: "XDG Directory Layout for Shared Data and Configuration"
aliases:
  - ADR-0008
status: Accepted
date: 2026-03-25
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - infrastructure
  - xdg
  - filesystem
decision_scope: system
supersedes: null
superseded_by: null
related_adrs:
  - "0003"
  - "0006"
---

## Context

The WorkFlow system distributes files across the user's home directory without a coherent strategy. ITEP uses `~/.config/mytex` for `.sty` files and templates — a misuse of the XDG config directory, which is reserved for configuration files only. The global database path has also been placed under `~/.config/workflow/`, violating XDG semantics.

The XDG Base Directory Specification defines:

- `~/.config/` — user-specific configuration files (small, human-editable)
- `~/.local/share/` — user-specific data files (assets, databases, templates)
- `~/.cache/` — non-essential, regenerable cache files

A clear directory layout is required to comply with XDG semantics and avoid future confusion.

---

## Decision

### `~/.config/workflow/config.yaml` — single config file

Contains only:

```yaml
vault_path: ~/Documents/01-U
default_institution: UCR
default_timezone: America/Costa_Rica
```

No databases, no assets, no templates.

### `~/.local/share/workflow/` — all shared user data

```
~/.local/share/workflow/
├── workflow.db          # Global SQLite database (all projects)
├── sty/                 # 16 shared LaTeX .sty files
├── templates/           # LaTeX document templates
└── img/                 # Institutional logos
```

### `~/.cache/workflow/` — regenerable cache

```
~/.cache/workflow/
└── tikz/                # TikZ compilation cache (future, per ADR-0006)
```

### Vault root (unchanged)

`~/Documents/01-U/` is the Obsidian vault root. Internal structure:

```
~/Documents/01-U
├── notes/
│   ├── permanent/       # Evergreen Zettelkasten notes (tracked in global DB)
│   ├── literature/      # Literature notes (tracked in global DB)
│   └── fleeting/        # Inbox notes (tracked in global DB)
├── assets/
│   ├── tikz/            # TikZ source files (per ADR-0006)
│   └── figures/         # Compiled figures (per ADR-0006)
└── 00XX-*/              # Existing subject directories (unchanged)
```

Each ITEP project directory contains its own `slipbox.db` (local DB, per ADR-0003).

---

## Architectural Rules

### MUST

- Global DB (`workflow.db`) **MUST live in `~/.local/share/workflow/`**, not `~/.config/`.
- `.sty` files, templates, and institutional images **MUST live in `~/.local/share/workflow/`**, not `~/.config/`.
- `~/.config/workflow/config.yaml` **MUST contain only** vault path and user defaults — no paths to assets.
- Code **MUST use `appdirs.user_data_dir("workflow", "LuisUmana")`** for data paths.
- Code **MUST use `appdirs.user_config_dir("workflow", "LuisUmana")`** for config paths.

### SHOULD

- `~/.cache/workflow/` **SHOULD be used** for any file that can be regenerated (TikZ output, render hashes).
- Paths **SHOULD be resolved at runtime** via `appdirs`, not hardcoded.

### MAY

- A `workflow init` command **MAY scaffold** `~/.local/share/workflow/` on first run.

---

## Implementation Notes

- `src/workflow/db/engine.py`: use `user_data_dir` for `workflow.db` path.
- `src/itep/defaults.py`: `DEF_ABS_SRC_DIR` resolves via `user_data_dir("workflow", "LuisUmana")`.
- `appdirs` is already a declared dependency — no new dependency required.

---

## Consequences

### Benefits

- Complies with XDG Base Directory Specification
- Clean separation: config is small/editable, data is large/managed, cache is disposable
- Backup strategies can target `~/.local/share/workflow/` for assets without including cache

### Costs

- One-time migration of existing files from `~/.config/mytex` to `~/.local/share/workflow/`
- Any hardcoded `~/.config/` paths must be updated in code and documentation

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-25 | Initial ADR |
| 2026-06-05 | Wave E amendment — see below |
| 2026-06-06 | Production symlink note — see below |

---

## Amendment — 2026-06-05 (Wave E)

- **Vault path correction**: the canonical vault root is `~/01-U/0000AV-Vault` (renamed 0000AA→0000AV, 2026-07-06), not `~/Documents/01-U` as stated in the original Decision section. The vault is intentionally NON-XDG (it is hand-edited documents, not app data). Override at runtime via `WORKFLOW_VAULT_ROOT` env var.
- **`WORKFLOW_DATA_DIR` env override**: this is the canonical escape hatch for the global DB path and always wins over any computed default.
- **Global DB back-compat resolver** (order of precedence, highest first):
  1. `$WORKFLOW_DATA_DIR` env var — wins unconditionally.
  2. XDG data dir (`~/.local/share/workflow/workflow.db`) — used if the file already exists there.
  3. Legacy path (`~/01-U/workflow/workflow.db`) — used if the file already exists there (back-compat).
  4. XDG default (`~/.local/share/workflow/workflow.db`) — final fallback for new installs.
  Relocation from legacy to XDG is performed only by the explicit `workflow db migrate-xdg` command (dry-run by default; never auto-runs).
- **`platformdirs` replaces `appdirs`**: the data root is `platformdirs.user_data_dir("workflow")` (= `~/.local/share/workflow/` on Linux). The `appdirs` dependency is replaced by `platformdirs`.

---

## Note — 2026-06-06 (Production symlink setup)

In the live developer setup, `~/.local/share/workflow` is a **symlink** pointing to `<repo>/share/` (i.e. `~/02-Projects/WorkFlow/share/`). This means the shared LaTeX styles, templates, and other application data under `share/` in the repository tree are served through the standard XDG data path.

`paths.py` and `platformdirs` are fully symlink-agnostic: `Path.exists()` follows symlinks, so `global_db_path()` precedence resolution works correctly whether the XDG data directory is a real directory or a symlink. No code changes are required to support this setup.
