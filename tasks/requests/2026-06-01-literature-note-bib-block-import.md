---
id: 20260601-literature-note-bib-block-import
title: Import biblatex from a literature note's `bib` block via nvim → existing CLI
type: feature
source_agent: user
opened_on: 2026-06-01

status: open
resolution:
priority: P2
severity: recurring-friction

labels:
  - cli
  - nvim
  - docs
components:
  - workflow.prisma          # importer lives here today
  - workflow.bibliography
  - workflow.nvim
  - latexzettel

adr_refs: ["PRISMA-0002"]    # bibtex import pipeline already specified here
related_requests:
  - 2026-05-28-content-bib-link-cli.md
  - 2026-05-29-bibliography-service-extraction.md
  - 2026-05-29-v1.14.0-reviewer-esquema-followups.md   # item 8: neutral-module move + alias
duplicates: []
blocked_by: []

assignee: unassigned
target_release:
implementation: []
closed_on:
closed_by:

acceptance_criteria: []
verification: []
---

# Request: Literature-note `bib` block → biblatex import (nvim → existing CLI)

## Idea (as proposed by user)

> Literature notes should carry a multi-line `bib` block holding the biblatex
> entry. A plugin command grabs that block's text and hands it to the
> bibfile-import CLI.

## Evaluation — verdict: **sound, and most of it already exists**

The import CLI is **already built**: `workflow prisma bib import <PATH>`
(`src/workflow/prisma/cli.py:146`) → `import_bib_file(session, path,
database_name=…)` (`src/workflow/prisma/importer.py`). It already:

- parses `.bib` with `bibtexparser` (`importer.py:16`);
- maps every biblatex field to `BibEntry` columns
  (`TRANSLATED_BIB_KEYS`, `_STRING_BIB_FIELDS`, `_INT_BIB_FIELDS`,
  `_parse_date`) and writes to the **same GlobalBase `BibEntry` table** the
  rest of `workflow` reads — it is *not* PRISMA-siloed at the data layer;
- splits authors incl. corporate names → `Author` + `BibAuthor`
  (`_split_authors`, `_AUTHOR_FIELDS = author/editor/translator`);
- guards size (`MAX_BIB_SIZE_BYTES`) and URL schemes (`_ALLOWED_URL_SCHEMES`);
- returns `ImportResult` with per-entry `statuses` + `errors`, and supports
  `--json` / `--verbose` / `--database-name`.

So the heavy lifting I first assumed was missing is **done**. (Correction
logged in `tasks/lessons.md` — the importer lives under the `prisma` group, so
a `prisma bib`-scoped grep is required before claiming "no bib import exists".)

### The actual gap is small — two things

1. **No stdin path.** `bib_import` takes `click.Path(exists=True)` — a file on
   disk. A literature-note `bib` block is text in an editor buffer. Either:
   - **(a, recommended)** teach `import_bib_file` to accept biblatex **text**
     (add a `--stdin` flag / `-` path convention that reads `sys.stdin`),
     reusing the entire existing parse/map/persist path; or
   - **(b)** nvim writes the block to a tempfile and calls the existing
     command unchanged. Zero CLI change, but leaves temp litter and a cleanup
     burden. Prefer (a).

2. **No nvim command** to extract the block and invoke it.

### Optional, not required for the feature

- **Neutral alias.** The importer is general-purpose but discoverable only
  under `prisma`. A `workflow bib import` alias delegating to the same
  `import_bib_file` would match where a *literature note* (not necessarily a
  systematic review) expects it. This is exactly **item 8** of
  `2026-05-29-v1.14.0-reviewer-esquema-followups.md` (move engine → neutral
  module + deprecation alias) and the `bibliography-service-extraction`
  request. Bundle it only if that consolidation is being done anyway;
  otherwise `workflow prisma bib import` is a fine target.

## Proposal

### Where the biblatex lives in the note

A fenced code block with a `bib` info-string — ```` ```bib … ``` ```` —
machine-extractable, renders harmlessly, survives the pandoc pipeline
(LZK-0002) verbatim. (Markdown has no "comment block type"; HTML comments get
stripped by some renderers and YAML scalars mangle `{}`/`%`.)

### P1 — stdin support on the existing importer

```bash
workflow prisma bib import -  --stdin   [--database-name X] [--json] [--verbose]
# or:  cat entry.bib | workflow prisma bib import --stdin
```

- Add a `--stdin` flag (or accept `-` as PATH) on `bib_import`
  (`prisma/cli.py:146`); when set, read biblatex text from `sys.stdin` and pass
  it to `import_bib_file` via a new text entry point (e.g.
  `import_bib_text(session, text, database_name=…)` that the existing
  `import_bib_file` also calls after reading the file). **No change** to field
  mapping, author split, dedup, size/URL guards, or `ImportResult`.

### P2 — nvim `:WorkflowBibImport`

New `nvim-plugin/lua/workflow/bib_import.lua`, registered in `commands.lua` /
`plugin/workflow.lua`:

1. Scan the current buffer for the first ```` ```bib ```` fenced block.
2. Pipe its inner lines to `workflow prisma bib import --stdin --json` via
   `server.run_cli` — exact pattern of `content_bib.lua:38`.
3. `vim.notify` the created/skipped/error counts; on non-zero exit show CLI
   stderr verbatim (same as the link-bib wrapper).
4. No `bib` block → INFO notify "no `bib` block found", no CLI call.

### Literature-note template

Add a stub ```` ```bib ```` block to the literature-note markdown template
(confirm exact filename under `shared/latex/templates/` at implementation
time — the dir is currently `.tex`-heavy).

## Acceptance

- [ ] `cat entry.bib | workflow prisma bib import --stdin --json` creates the
      `BibEntry` (+ `Author`/`BibAuthor`), identical result to passing the file
      path — proven by a test asserting both paths produce the same rows.
- [ ] Existing `workflow prisma bib import <PATH>` behaviour unchanged
      (regression test stays green).
- [ ] Empty / malformed stdin → same exit + `ImportResult.errors` semantics as
      the file path today (no new error contract).
- [ ] `:WorkflowBibImport` on a note with a ```` ```bib ```` block imports it
      and notifies counts; on a note without one, notifies and makes no CLI call.
- [ ] Tests: extend `tests/workflow/prisma/test_importer*.py` (stdin path,
      file==stdin parity, empty stdin) and add
      `nvim-plugin/tests/plenary/bib_import_spec.lua` (block extraction,
      empty-buffer guard) — mirror `content_bib_spec.lua`.
- [ ] Docs: CLAUDE.md prisma command row notes `--stdin`;
      `nvim-plugin/doc/workflow.txt` documents `:WorkflowBibImport`.

## Out of scope

- Re-implementing any bibtex parsing / field mapping — it exists; reuse it.
- The neutral `workflow bib import` alias / module move (separate follow-up,
  item 8 of the v1.14.0 followups — bundle only if doing that work anyway).
- Auto-linking the imported `BibEntry` to a `Content` — that is the shipped
  `content link-bib`; keep import and link separate.

## Evidence / glue replaced

Today, importing a reference held in a literature note means saving a `.bib`
file to disk and running `workflow prisma bib import <path>` by hand, then
deleting the file. The note already contains the biblatex; the round-trip
through a temp file and a second terminal is the friction this removes.

## Implementation notes

- Read first: `src/workflow/prisma/importer.py` (the whole parse/map/persist
  path to reuse), `prisma/cli.py:146` (Click signature to extend),
  `content_bib.lua:38` (`server.run_cli` pattern to copy), PRISMA-0002 (the
  bibtex import pipeline ADR this extends).
- The cleanest split: factor `import_bib_file` into `read file → text` +
  `import_bib_text(session, text, …)`; `--stdin` skips the read step. One new
  parameter path, zero new parsing code.
- `bibtexparser` is already a declared dependency.

## Progress log

- 2026-06-01 — opened by user. First draft wrongly claimed no bib-import CLL
  existed; user corrected (`workflow prisma bib import`). Re-scoped to the real
  gap: stdin support + nvim command (parser already exists). Lesson logged.
