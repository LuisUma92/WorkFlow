---
id: 20260603-prisma-to-literature-note
title: Auto-generate literature notes from PRISMA-accepted articles
type: feature
source_agent: user
opened_on: 2026-06-03

status: open
resolution:
priority: P2
severity: recurring-friction

labels:
  - cli
  - nvim
  - notes
  - prisma
components:
  - workflow.prisma
  - workflow.notes
  - workflow.vault
  - workflow.nvim

adr_refs: ["PRISMA-0003", "PRISMA-0005", "0015", "0002", "LZK-0002"]
related_requests:
  - 2026-06-01-literature-note-bib-block-import.md
  - 2026-06-01-bibliography-dialect-biblatex-bibtex-compat.md
duplicates: []
blocked_by:
  - 2026-06-01-literature-note-bib-block-import.md   # P1 stdin path is a prerequisite for P3

assignee: unassigned
target_release:
implementation: []
closed_on:
closed_by:

acceptance_criteria: []
verification: []
---

# Request: Auto-generate literature notes from PRISMA-accepted articles

## Context and motivation

The Zettelkasten and PRISMA subsystems embody opposing epistemological directions:
Zettelkasten is bottom-up (atomic notes surface emergent structure), while PRISMA is
top-down (a research question drives a structured literature search). In practice both
are needed, and the friction between them is concentrated at one specific handoff point:
when a PRISMA screening session accepts an article (`included = True` in `Reviewed`),
the investigator must manually create a literature note from that `BibEntry`. This is
the only moment where PRISMA's structured knowledge should flow into the Zettelkasten,
and it is currently entirely manual.

Two additional flows complete the picture:

1. **Free reading** — books/articles read outside any PRISMA context produce a
   literature note directly, without a `prisma_review_id`. These notes are
   deliberately "unanchored" (no `main_topic_id` at creation). The system must
   tolerate and represent this state explicitly.

2. **Graph → research question** — clusters of unanchored notes sharing concepts or
   authors signal emergent themes that could be formalized into a PICO question and
   a subsequent PRISMA review. This third flow depends on ITEP-0013 (note relation
   graph, Proposed) and is **out of scope** for this request; it is filed as a
   dependency note below.

## The actual gap — three things

1. **No `workflow prisma bib accept-to-note` command** (or equivalent hook on
   the `included = True` transition) that generates a populated `.md` file and
   writes it to `<vault_root>/notes/literature/`.

2. **No `prisma_review_id` field** in the note frontmatter — the link between a
   literature note and its originating PRISMA project is implicit at best (only
   the `bibkey` is present).

3. **No nvim command** to trigger the generation from within the screening
   workflow.

## Proposed note structure

A generated literature note must contain:

### Frontmatter

```yaml
---
id: <YYYYMMDD>-lit-<bibkey>
title: "<BibEntry.title>"
type: literature
bibkey: <BibEntry.bibkey>
prisma_review_id: <Review.id>        # null if generated outside PRISMA
main_topic_id: null                  # intentionally unset at creation
concepts: []
tags: []
created: <ISO date>
source: prisma                       # or: manual
---
```

The `main_topic_id` and `concepts` fields are left null/empty at creation.
The investigator anchors the note to the taxonomy later, using the existing
`notes link --main-topic` and `notes link --concept` commands (ITEP-0012).
This is a deliberate design choice: forcing a topic at creation time would
contradict the Zettelkasten principle that structure emerges from the notes.

### Body sections

```markdown
# <BibEntry.title>

## Metadata

- **Authors**: <comma-separated author surnames, year>
- **Journal/Source**: <BibEntry.journaltitle or booktitle>
- **DOI**: <https://doi.org/BibEntry.doi>
- **Year**: <BibEntry.year>

## PRISMA rationale

> Review: <Review.id> — <associated keyword(s)>

<!-- Inclusion rationale(s) copied verbatim from Review_rationale -->
- <rationale_1.text>
- <rationale_2.text>  (if multiple)

## Notes

<!-- Your reading notes here -->

## Bib block

```bib
<BibEntry rendered as a valid biblatex entry>
```
```

The `## PRISMA rationale` section is **only emitted when `prisma_review_id` is
non-null**. For notes generated outside PRISMA (free reading), this section is
omitted entirely.

The ```` ```bib ```` block is the biblatex representation of the `BibEntry`,
ready to be imported via `:WorkflowBibImport` (see
`2026-06-01-literature-note-bib-block-import.md`) into any project that does not
yet have this entry in its local bibliography. It also serves as a self-contained
archive in case the entry is later modified in the DB.

## Proposal

### P1 — CLI: `workflow prisma bib accept-to-note`

```bash
workflow prisma bib accept-to-note <BIBKEY> \
    [--review-id <id>] \
    [--vault-root <path>] \
    [--dry-run] \
    [--json]
```

- Looks up `BibEntry` by `bibkey` (reuses `get_bib_entry_by_bibkey`).
- If `--review-id` is given: fetches `Reviewed` record + `Review_rationale`
  entries for that `(bib_entry_id, review_id)` pair and emits the
  `## PRISMA rationale` section.
- Renders the `.md` file following the structure above.
- Writes to `<vault_root>/notes/literature/<id>-lit-<bibkey>.md`.
  `vault_root` resolved via `workflow.vault.paths.resolve_vault_root()`.
- If the file already exists: exits non-zero with a message; no overwrite
  (idempotent by file presence, same contract as `workflow exercise create`).
- `--dry-run`: prints the rendered content to stdout, writes nothing.
- `--json`: emits `{"note_path": "...", "bibkey": "...", "created": true/false}`.

A bulk variant should also be supported:

```bash
workflow prisma bib accept-to-note --review-id <id> --all-accepted \
    [--vault-root <path>] [--dry-run] [--json]
```

Generates one note per accepted article in the review. Already-existing notes
are skipped (idempotent). `--json` emits a list of per-entry results.

### P2 — Hook on the screening transition (optional, deferred)

When a screening decision flips to `included = True` in the CLI workflow
(`workflow prisma review accept <bib_entry_id> --review-id <id>`), automatically
call the note-generation logic without a separate command. This is a UX convenience;
P1 is the authoritative path. Defer until the interactive screening CLI matures.

### P3 — nvim: `:WorkflowPrismaAcceptToNote`

New `nvim-plugin/lua/workflow/prisma_note.lua`, registered in `commands.lua` /
`plugin/workflow.lua`:

1. Prompt (via `vim.ui.input`) for `bibkey` and optional `review_id`.
2. Call `workflow prisma bib accept-to-note <bibkey> [--review-id <id>] --json`
   via `server.run_cli` — exact pattern of `content_bib.lua:38`.
3. On success: open the generated note in a new split/buffer.
4. On `created: false` (note already exists): notify and open the existing file.
5. On error: notify with CLI stderr verbatim.

P3 depends on P1 and on the `--stdin` path from
`2026-06-01-literature-note-bib-block-import.md` (P1 of that request), which
makes the ```` ```bib ```` block in the generated note immediately importable
from within nvim.

## Note lifecycle and the "unanchored" state

The generated note is intentionally incomplete at creation. Its lifecycle is:

```
generated (source: prisma, main_topic_id: null)
    ↓  [investigator reads and annotates]
enriched  (notes added, wiki-links added)
    ↓  [workflow notes link --main-topic CODE]
anchored  (main_topic_id set)
    ↓  [workflow notes link --concept CODE ...]
classified (concepts populated)
```

The graph module (`workflow graph orphans --type note`) already surfaces
unanchored notes. No schema changes are needed for this lifecycle; it is entirely
represented by the nullable `Note.main_topic_id` and the `source` tag.

## Free-reading notes (outside PRISMA)

A literature note generated outside any PRISMA context (e.g. a book read by
interest) follows the same template but with `prisma_review_id: null` and
`source: manual`. The `## PRISMA rationale` section is omitted. The note is
created directly via `:WorkflowPrismaAcceptToNote` with no `--review-id`, or via
a simpler `workflow notes create --type literature --bibkey <key>` command (out of
scope for this request — file separately if needed).

## Graph → research question (out of scope, dependency note)

Clusters of unanchored literature notes with co-occurring `concepts` or shared
authors could signal emergent research themes. Detecting these clusters and
proposing a PICO question requires:

- ITEP-0013 (note relation graph, currently Proposed) — prerequisite.
- A `workflow graph suggest-review` command analyzing note clusters by concept
  co-occurrence.

This flow is deferred until ITEP-0013 is implemented.

## Acceptance criteria

- [ ] `workflow prisma bib accept-to-note <bibkey>` creates a `.md` file at the
      correct vault path with the specified frontmatter and body structure.
- [ ] When `--review-id` is given, the `## PRISMA rationale` section contains the
      inclusion rationale(s) copied from `Review_rationale`. When absent, the
      section is omitted.
- [ ] The ```` ```bib ```` block contains a valid biblatex entry that round-trips
      through `workflow prisma bib import --stdin` without error.
- [ ] Running the command twice on the same bibkey exits non-zero and does not
      overwrite the existing note.
- [ ] `--all-accepted --review-id <id>` generates one note per accepted article;
      already-existing notes are skipped and counted in the report.
- [ ] `--dry-run` prints to stdout and writes nothing.
- [ ] `Note.main_topic_id` is null at creation; `Note.source` tag is `prisma` or
      `manual` accordingly.
- [ ] `workflow graph orphans --type note` includes newly generated notes.
- [ ] `:WorkflowPrismaAcceptToNote` calls the CLI, opens the note, and notifies
      counts; errors show CLI stderr.
- [ ] Tests: `tests/workflow/prisma/test_accept_to_note.py` — single note, bulk,
      idempotency, dry-run, missing bibkey, missing review-id graceful fallback.
- [ ] `nvim-plugin/tests/plenary/prisma_note_spec.lua` — block extraction,
      empty-result guard, already-exists path.
- [ ] Docs: CLAUDE.md prisma command row notes the new subcommand;
      `nvim-plugin/doc/workflow.txt` documents `:WorkflowPrismaAcceptToNote`.

## Out of scope

- Forcing `main_topic_id` or `concepts` at note creation time.
- Auto-linking the note to a `Content` record (use `content link-bib` after anchoring).
- The graph → research question flow (depends on ITEP-0013).
- Modifying the PRISMA screening UI (P2 hook deferred).
- Re-implementing biblatex rendering (reuse `BibEntry` field map from ADR-0019 /
  `workflow.bibliography`).

## Implementation notes

- Read first: `src/workflow/prisma/importer.py` (BibEntry field map to reverse for
  the ```` ```bib ```` block), `PRISMA-0003` (Reviewed + Review_rationale schema),
  `workflow.vault.paths.resolve_vault_root()` (vault path resolution),
  `2026-06-01-literature-note-bib-block-import.md` (stdin import — prerequisite
  for `:WorkflowBibImport` to work on the generated note).
- The biblatex renderer is the inverse of the importer's `TRANSLATED_BIB_KEYS` map.
  If ADR-0019 P3 (`workflow bib export`) lands first, reuse that exporter. Otherwise
  write a minimal `render_biblatex(bib_entry) -> str` in `workflow.bibliography`.
- Frontmatter `id` collision: use `YYYYMMDD` of creation + `-lit-` + bibkey slug.
  If that file already exists, abort (do not append a suffix automatically).

## Progress log

- 2026-06-03 — opened by user. Motivated by the epistemological tension between
  Zettelkasten (bottom-up) and PRISMA (top-down), and the need for an explicit,
  low-friction handoff at the `included = True` transition point.
