# Add CLI surface for `BibContent` (Content ↔ BibEntry link) under `workflow content`

## Summary

`BibContent` exists as a fully-defined ORM table
(`src/workflow/db/models/bibliography.py:322`) with composite PK
`(bib_entry_id, content_id)` and locus columns `chapter_number`,
`section_number`, `first_page`, `last_page`, `first_exercise`,
`last_exercise`. The relationships `BibEntry.content_links` and
`Content.bib_links` are wired, and `graph/collectors.py` already
reads the rows. Migration `0009_normalize_models.py` shipped the
schema.

**No CLI writes to `bib_content`.** To attach a book chapter to a
Content row today, the only path is a Python REPL with
`session.add(BibContent(...))`. Both `workflow content` (add | list
| show) and `workflow prisma bib` (export | import | list | search |
show) are read- or insert-on-self-only; neither can create the M2M
link.

This forces every agent that wants to materialise the "Content X
lives in chapter Y of book Z, pages A–B" relationship into Python
glue, same gap pattern as the just-closed `2026-05-28-topic-content-cli-surface.md`.

## Motivation

- Reporting agent(s): `workflow-runner`, course-setup automation
- Total occurrences: 1 (2026-05-28); will recur every time a
  Content row is paired with its source-of-truth book chapter
- Severity: **major** (blocker for any agent doing bibliography
  → content mapping; not blocker for note-authoring)
- Blocks / slows down:
  - Autonomous "import this textbook's TOC into Content rows" workflows
  - `workflow exercise create-range --first-page N --last-page M`
    style flows that derive locus from `BibContent`
  - Any future `workflow content show --with-source` reporting

## Proposed CLI

All under the existing `workflow content` group (no new top-level group):

```bash
workflow content link-bib    --content-id <id> --bib-entry <citekey> \
                             --chapter <int> --section <int> \
                             --first-page <int> --last-page <int> \
                             [--first-exercise <int>] [--last-exercise <int>] \
                             [--json]

workflow content bib-links   --content-id <id> [--json]

workflow content unlink-bib  --content-id <id> --bib-entry <citekey>
```

Flag details:

- `--bib-entry <citekey>`: human-readable BibTeX citekey
  (`BibEntry.citekey`), not the numeric id. Looked up via existing
  `prisma bib` lookup helper. Reuse — do not duplicate.
- `--chapter`, `--section`, `--first-page`, `--last-page`: required
  (matches NOT NULL columns).
- `--first-exercise`, `--last-exercise`: optional (nullable columns).
- `--json`: emit JSON to stdout; default human-readable line.

## Example

```bash
$ workflow content link-bib --content-id 42 --bib-entry hibbeler2016 \
    --chapter 12 --section 2 --first-page 552 --last-page 580 \
    --first-exercise 12.1 --last-exercise 12.45 --json
{"content_id": 42, "bib_entry_id": 7, "bib_entry_citekey": "hibbeler2016",
 "chapter_number": 12, "section_number": 2,
 "first_page": 552, "last_page": 580,
 "first_exercise": 12, "last_exercise": 45}

$ workflow content bib-links --content-id 42 --json
[
  {"bib_entry_citekey": "hibbeler2016", "chapter_number": 12,
   "section_number": 2, "first_page": 552, "last_page": 580,
   "first_exercise": 12, "last_exercise": 45}
]

$ workflow content unlink-bib --content-id 42 --bib-entry hibbeler2016
Removed bib link: content_id=42 ↔ hibbeler2016
```

## Expected output shape

```json
// link-bib / single row in bib-links
{
  "content_id": 42,
  "bib_entry_id": 7,
  "bib_entry_citekey": "hibbeler2016",
  "chapter_number": 12,
  "section_number": 2,
  "first_page": 552,
  "last_page": 580,
  "first_exercise": 12,
  "last_exercise": 45
}

// bib-links list
[{ ... }, ...]
```

Exit codes:
- 0 on success
- 1 on FK violation (unknown content-id or unknown citekey)
- 2 on duplicate `(bib_entry_id, content_id)` pair (composite PK collision)

## Acceptance test

- `workflow content link-bib --content-id <valid> --bib-entry <valid> --chapter 1 --section 1 --first-page 1 --last-page 10 --json`
  emits JSON with `content_id` and `bib_entry_citekey` keys; exit 0.
- `workflow content link-bib --content-id 99999 --bib-entry <valid> ...`
  exits 1 with stderr referencing the unknown content id.
- `workflow content link-bib --content-id <valid> --bib-entry NOPE ...`
  exits 1 with stderr referencing the unknown citekey.
- Re-running the same `link-bib` with identical PK pair exits 2.
- `workflow content bib-links --content-id <valid> --json` returns a
  JSON array; each element has `bib_entry_citekey`, `chapter_number`,
  `section_number`, `first_page`, `last_page`.
- `workflow content unlink-bib --content-id <valid> --bib-entry <valid>`
  exits 0; subsequent `bib-links` does not include that pair.
- `workflow content unlink-bib` against a non-existent pair exits 1.
- Add tests in `tests/workflow/test_content_bib_cli.py` covering:
  success path, FK-violation error (both ends), duplicate error,
  `--json` shape for both `link-bib` and `bib-links`, idempotent
  unlink semantics.

## Neovim plugin integration

Once the CLI lands, the `nvim-plugin/` must gain matching
`:Workflow*` user commands so the link can be authored from inside
the same `.md`/`.tex` buffer where the user is reading the chapter.

### Proposed Lua surface

```vim
:WorkflowContentBibPicker  [content-id=N]
:WorkflowContentLinkBib    {content-id} {citekey} {chapter} {section} {first-page} {last-page} [first-exercise] [last-exercise]
:WorkflowContentUnlinkBib  {content-id} {citekey}
```

- `:WorkflowContentBibPicker` — Snacks picker backed by
  `workflow content bib-links --content-id N --json`. `<CR>` inserts
  the citekey at cursor (parallel to `WorkflowConceptPicker` which
  inserts the concept code). If `content-id` is omitted, falls back
  to reading `content_id:` from the current buffer's frontmatter
  via `workflow.frontmatter` helper (already in plugin).
- `:WorkflowContentLinkBib` — positional-arg wrapper around
  `workflow content link-bib`. Stdout in floating notify; failure
  shows stderr.
- `:WorkflowContentUnlinkBib` — positional-arg wrapper.

### Files to touch (plugin side)

| File | Change |
|------|--------|
| `nvim-plugin/lua/workflow/picker/content_bib.lua` | new — picker |
| `nvim-plugin/lua/workflow/content_bib.lua` | new — link / unlink wrappers |
| `nvim-plugin/lua/workflow/init.lua` | add `M.pick_content_bib`, `M.link_content_bib`, `M.unlink_content_bib` |
| `nvim-plugin/lua/workflow/commands.lua` | register the 3 `:Workflow*` commands |
| `nvim-plugin/lua/workflow/contracts.lua` | add `WorkflowBibLinkJSON` EmmyLua class |
| `nvim-plugin/doc/workflow.txt` | 3 new `*:WorkflowContentXxx*` blocks |
| `nvim-plugin/scripts/smoke_taxonomy.sh` | extend with the 3 new CLI invocations |

### Acceptance test (plugin)

- `:WorkflowContentBibPicker content-id=42` opens a Snacks picker
  with rows formatted as
  `[<citekey>] ch.<chapter> §<section> pp.<first>-<last>`.
  `<CR>` inserts the citekey at cursor in the active buffer.
- `:WorkflowContentLinkBib 42 hibbeler2016 12 2 552 580` shells out
  to `workflow content link-bib ...`, surfaces the success
  notification, and a subsequent `:WorkflowContentBibPicker
  content-id=42` shows the new row.
- `:WorkflowContentUnlinkBib 42 hibbeler2016` removes the row and a
  follow-up picker invocation no longer shows it.
- `nvim --headless --noplugin -u nvim-plugin/plugin/workflow.lua -c
  "qa"` exits 0 after the new modules are added (no Lua syntax
  errors).
- `scripts/smoke_taxonomy.sh` exits 0 with PASS lines for the 3 new
  CLI commands.

### Sequencing

1. Land the Python CLI per the spec above. Tag as `v1.13.0`.
2. After CLI ships, implement the plugin integration in a separate
   commit/PR. Tag the plugin bump as `v1.13.0` plugin-side (matching
   CLI minor) once contracts.lua is in sync.

The CLI must ship first because the plugin smoke script invokes the
CLI directly to validate the JSON contract.

## Out of scope

- Bulk import (CSV / YAML of `chapter→content` pairs). Defer to a
  follow-up request once single-row CLI is in place.
- Auto-derivation of `first_exercise`/`last_exercise` from a `.tex`
  exercise file. Out of scope; explicit flags only.
- Editing locus columns of an existing link. Use `unlink-bib` +
  `link-bib` for v1; an `edit-bib` command can come later if usage
  warrants.

## Raw entries harvested

- 2026-05-28 CLI audit — `BibContent` table has zero CLI write path;
  data model present since migration 0009 but unreachable from shell.

## Cross-references

- `2026-05-28-topic-content-cli-surface.md` — closed v1.11.0;
  established the pattern this request extends (`content` group
  ownership).
- `src/workflow/db/models/bibliography.py:322` — `BibContent` model.
- `src/workflow/db/models/knowledge.py` — `Content.bib_links`
  relationship.
- `src/workflow/graph/collectors.py` — read-only consumer of
  `BibContent`; will benefit immediately once writes are possible.
- `src/workflow/prisma/cli.py` — existing `prisma bib` subcommands;
  must expose a `citekey → BibEntry.id` lookup helper for reuse (do
  not duplicate the query).
