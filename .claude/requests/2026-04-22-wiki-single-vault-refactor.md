# [docs] Refactor Zettelkasten-Notes wiki to single-vault model

**Priority:** Low
**Scope:** Documentation only (no code)
**Labels:** docs, wiki, tech-debt
**Opened:** 2026-04-22
**Opened-by:** Claude Code session (deferred from note-creation-boundary commit)

## Context

In session 2026-04-22, `docs/wiki/Zettelkasten-Notes.md` was edited to add a
"Creacion de notas" section documenting the CLI/obsidian.nvim boundary
(lines ~205-250 in current HEAD). During that edit, stale content was
detected but left untouched to keep the PR scope tight.

**Stale block:** `docs/wiki/Zettelkasten-Notes.md:70-87` shows the old
multi-vault directory tree:
- `00ZZ-Vault/` (old name)
- `10MC-ClassicalMechanics/notes/` + `slipbox.db` per project
- `40EM-Electromagnetism/notes/` + `slipbox.db` per project

**Actual code (source of truth):**
- `src/workflow/notes/init.py:19` — `VAULT_NAME = "0000AA-Vault"`
- `src/workflow/notes/init.py::init_workspace()` — single `slipbox.db` at
  workspace root, no per-project DBs, no per-project `notes/` directories
- Project directories (`0010MC-*`, `0040EM-*`) are LaTeX output only

## Problem

The wiki misleads new users about the filesystem layout. They may:
- Expect `notes/` inside each project dir (doesn't exist)
- Look for per-project `slipbox.db` (doesn't exist)
- Use the deprecated `00ZZ-Vault` name

## Acceptance criteria

- [ ] `rg -n '00ZZ-Vault' docs/` returns 0 matches
- [ ] `rg -n 'per-project slipbox' docs/` returns 0 matches
- [ ] Directory tree example in `Zettelkasten-Notes.md` reflects single-vault:
  `.workflow/`, `0000AA-Vault/{inbox,templates}/`, `slipbox.db` at root,
  project dirs as LaTeX-only output
- [ ] `docs/wiki/Getting-Started.md` cross-checked for same staleness
- [ ] `docs/wiki/Architecture.md` cross-checked
- [ ] `docs/ADR/0014-zettelkasten-implementation.md` cross-checked (update
  only if its Current-State section claims the old layout)
- [ ] `docs/ADR/ITEP-0008-general-project-nomenclature.md` cross-checked —
  this ADR is IN PROGRESS and introduces `DDTTAA-YYPP-title/` layout; ensure
  wiki does not conflict with it

## Out of scope

- Code changes (layout is already single-vault in code)
- Schema changes
- Renaming `0000AA-Vault` (locked per `notes/init.py`)
- Writing new ADRs

## Workflow

1. `/plan` — list every file to touch and diff strategy
2. Use `search-first` skill to find all stale refs: `rg -n '00ZZ-Vault|per-project|notes/slipbox'`
3. Apply minimal edits (no rewriting unrelated sections)
4. `/verify` — run the 3 `rg` checks above + `markdownlint docs/wiki/`
5. Commit: `docs(wiki): align Zettelkasten docs with single-vault model`

## Don't touch

- The "Creacion de notas" section added 2026-04-22 (already correct)
- `Home.md` row for Zettelkasten (already updated 2026-04-22)
- Any `.py` source file

## Recommended model

Sonnet 4.6 (LOW scope, pure docs).

## References

- Current session commit: `docs(wiki): document note-creation boundary with obsidian.nvim`
- Primary file: `docs/wiki/Zettelkasten-Notes.md`
- Source of truth: `src/workflow/notes/init.py`
