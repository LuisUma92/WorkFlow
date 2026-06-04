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

adr_refs: ["PRISMA-0003", "PRISMA-0005", "0019", "0020", "ITEP-0012", "ITEP-0013", "0002", "LZK-0002"]
related_requests:
  - 2026-06-01-literature-note-bib-block-import.md
  - 2026-06-01-bibliography-dialect-biblatex-bibtex-compat.md
duplicates: []
blocked_by: []   # B1 stdin path + A5 shared renderer have both landed (Wave A/B)

assignee: unassigned
target_release:
implementation: []
closed_on:
closed_by:

acceptance_criteria: []
verification: []
---

# Request: Auto-generate literature notes from PRISMA-accepted articles

> **C0 rewrite (2026-06-04):** this request was rewritten against the truth-source audit
> `tasks/audit/2026-06-03-prisma-to-literature-note-audit.md`, which found 4 CRITICAL +
> 4 lesser schema contradictions in the original draft. All 8 are resolved below. Plan:
> `tasks/plans/2026-06-04-wave-c-prisma-to-note-plan.md`.

## Context and motivation

The Zettelkasten and PRISMA subsystems embody opposing epistemological directions:
Zettelkasten is bottom-up (atomic notes surface emergent structure), while PRISMA is
top-down (a research question drives a structured literature search). In practice both
are needed, and the friction between them is concentrated at one specific handoff point:
when a PRISMA screening session **includes** an article (`ReviewRecord.included == 1`),
the investigator must manually create a literature note from that `BibEntry`. This is
the only moment where PRISMA's structured knowledge should flow into the Zettelkasten,
and it is currently entirely manual.

Two additional flows complete the picture:

1. **Free reading** — books/articles read outside any PRISMA context produce a
   literature note directly, without a `prisma_review_record_id`. These notes are
   deliberately "unanchored" (no `main_topic_id` at creation). The system must
   tolerate and represent this state explicitly.

2. **Graph → research question** — clusters of unanchored notes sharing concepts or
   authors signal emergent themes that could be formalized into a PICO question and
   a subsequent PRISMA review. This third flow depends on ITEP-0013 (note relation
   graph, **Accepted** 2026-05-22) and is **out of scope** for this request; it is filed as a
   dependency note below.

## Truth-source schema (verified — see audit)

- **Screening decision** = `class ReviewRecord` (table `review_record`) in
  `src/workflow/db/models/bibliography.py`: `id`, `keyword_id` (FK→`BibKeyword`),
  `bib_entry_id` (FK→`BibEntry`), `included` (SmallInteger, **tri-state** None=unscreened /
  0=excluded / 1=included), `include_rationale` (Text, nullable). UniqueConstraint
  `(keyword_id, bib_entry_id)`. There is **no** standalone `Review` entity (ADR PRISMA-0003).
- **Rationale** — free text on `ReviewRecord.include_rationale`; controlled-vocabulary
  rationales via the join `ReviewRationale(review_record_id, rationale_option_id)` →
  `RationaleOption.label`. `ReviewRationale` has **no `.text`** attribute.
- **Bib entry lookup** — `workflow.bibliography.service.get_bib_entry_by_bibkey` returns
  `None` (0 matches) / the entry (1) / raises `AmbiguousLookupError` (2+, bibkeys are
  non-unique by design — ADR-0019).
- **Bib block renderer** — `workflow.bibliography.render.entry_to_biblatex(entry)` (the A5
  shared foundation renderer, ADR-0020). Reuse it; do **not** write a second renderer.
- **Note `source` collision** — `Note.source` is a relationship (back-pop from `Link.source`);
  `source_format` is a column. Frontmatter therefore uses `origin:`, never `source:`.

## The actual gap — three things

1. **No `workflow prisma bib accept-to-note` command** (or equivalent hook on the
   `included == 1` transition) that generates a populated `.md` file and writes it to
   `<vault_root>/notes/literature/`.

2. **No `prisma_review_record_id` field** in the note frontmatter — the link between a
   literature note and its originating PRISMA screening decision is implicit at best
   (only the `bibkey` is present).

3. **No nvim command** to trigger the generation from within the screening workflow.

## Proposed note structure

A generated literature note must contain:

### Frontmatter

```yaml
---
id: <YYYYMMDD>-lit-<bibkey>
title: "<BibEntry.title>"
type: literature
bibkey: <BibEntry.bibkey>
prisma_review_record_id: <ReviewRecord.id>   # null if generated outside PRISMA (D3)
prisma_keyword_id: <keyword_id>              # null outside PRISMA
main_topic_id: null                          # intentionally unset at creation
concepts: []
tags: []
created: <ISO date>
origin: prisma                               # or: manual  (renamed from `source:`)
---
```

The `main_topic_id` and `concepts` fields are left null/empty at creation.
The investigator anchors the note to the taxonomy later, using the existing
`notes link --main-topic` and `notes link --concept` commands (ITEP-0012).
This is a deliberate design choice: forcing a topic at creation time would
contradict the Zettelkasten principle that structure emerges from the notes.

> **Validator:** these keys (`bibkey`, `prisma_review_record_id`, `prisma_keyword_id`,
> `origin`, `created`) are **not** currently known to `validate_note_frontmatter`. The
> original "no schema changes needed" claim was false (audit #6). Extending the validator
> schema to accept them is **in scope** for C1.

### Body sections

```markdown
# <BibEntry.title>

## Metadata

- **Authors**: <comma-separated author surnames, year>
- **Journal/Source**: <BibEntry.journaltitle or booktitle>
- **DOI**: <https://doi.org/BibEntry.doi>
- **Year**: <BibEntry.year>

## PRISMA rationale

> Keyword: <keyword label> — review record <ReviewRecord.id>

<!-- Free-text rationale from ReviewRecord.include_rationale (if present) -->
<ReviewRecord.include_rationale>

<!-- Controlled-vocabulary labels via ReviewRationale → RationaleOption.label -->
- <RationaleOption.label> (one bullet per linked option)

## Notes

<!-- Your reading notes here -->

## Bib block

```bib
<BibEntry rendered via workflow.bibliography.render.entry_to_biblatex>
```
```

The `## PRISMA rationale` section is **only emitted when a `ReviewRecord` resolves**
(i.e. `--keyword-id` or `--review-record-id` was given and a matching record exists).
For notes generated outside PRISMA (free reading), this section is omitted entirely.

The ```` ```bib ```` block is the biblatex representation of the `BibEntry`,
ready to be imported via `:WorkflowBibImport` (Wave B2, shipped) into any project that
does not yet have this entry in its local bibliography. It also serves as a self-contained
archive in case the entry is later modified in the DB.

## Proposal

### P1 — CLI: `workflow prisma bib accept-to-note`

```bash
workflow prisma bib accept-to-note <BIBKEY> \
    [--bib-entry-id <id>] \
    [--keyword-id <id>] \
    [--review-record-id <id>] \
    [--vault-root <path>] \
    [--dry-run] \
    [--json]
```

- Resolves the `BibEntry`: positional `<BIBKEY>` (reuses `get_bib_entry_by_bibkey`), or
  `--bib-entry-id` for the unambiguous case. On a non-unique bibkey, catch
  `AmbiguousLookupError` and emit a helpful error listing the conflicting `bib_entry_id`s,
  instructing the user to re-run with `--bib-entry-id`.
- PRISMA context (optional): `--keyword-id` resolves the `ReviewRecord` via the
  `(keyword_id, bib_entry_id)` UniqueConstraint; or pass `--review-record-id` directly.
  When a record resolves, emit the `## PRISMA rationale` section from
  `ReviewRecord.include_rationale` + `ReviewRationale → RationaleOption.label`, and record
  `prisma_review_record_id` / `prisma_keyword_id` in the frontmatter.
- Renders the `.md` via the existing literature template + `render.entry_to_biblatex`.
- Writes to `<vault_root>/notes/literature/<id>-lit-<bibkey>.md`.
  `vault_root` resolved via `workflow.vault.paths.resolve_vault_root()`.
- If the file already exists: exits non-zero with a message; no overwrite
  (idempotent by file presence, same contract as `workflow exercise create`).
- `--dry-run`: prints the rendered content to stdout, writes nothing.
- `--json`: emits `{"note_path": "...", "bibkey": "...", "created": true|false}`.

A bulk variant:

```bash
workflow prisma bib accept-to-note --all-accepted --keyword-id <id> \
    [--vault-root <path>] [--dry-run] [--json]
```

Generates one note per `ReviewRecord.included == 1` for that keyword. Already-existing
notes are skipped (idempotent). `--json` emits `{"created": N, "skipped": N, "notes": [...]}`.

### P2 — Hook on the screening transition (optional, deferred)

When a screening decision flips to `included == 1` in the CLI workflow, automatically
call the note-generation logic without a separate command. This is a UX convenience;
P1 is the authoritative path. Defer until the interactive screening CLI matures.

### P3 — nvim: `:WorkflowPrismaAcceptToNote`

New `nvim-plugin/lua/workflow/prisma_note.lua`, registered in `commands.lua` /
`plugin/workflow.lua`:

1. Prompt (via `vim.ui.input`) for `bibkey` and optional `keyword_id`.
2. Call `workflow prisma bib accept-to-note <bibkey> [--keyword-id <id>] --json`
   via `server.run_cli` — exact pattern of `content_bib.lua:38`.
3. On success: open the generated note in a new split/buffer.
4. On `created: false` (note already exists): notify and open the existing file.
5. On error: notify with CLI stderr verbatim.

P3 depends on P1 and on the `--stdin` path (B1, shipped), which makes the
```` ```bib ```` block in the generated note immediately importable from within nvim.

## Note lifecycle and the "unanchored" state

The generated note is intentionally incomplete at creation. Its lifecycle is:

```
generated (origin: prisma, main_topic_id: null)
    ↓  [investigator reads and annotates]
enriched  (notes added, wiki-links added)
    ↓  [workflow notes link --main-topic CODE]
anchored  (main_topic_id set)
    ↓  [workflow notes link --concept CODE ...]
classified (concepts populated)
```

The graph module (`workflow graph orphans --type note`) already surfaces unanchored notes.
No DB schema change is needed for this lifecycle; it is represented by the nullable
`Note.main_topic_id` and the `origin` frontmatter tag. (The validator schema, a separate
concern, does need the new keys — see above.)

## Free-reading notes (outside PRISMA)

A literature note generated outside any PRISMA context follows the same template but with
`prisma_review_record_id: null`, `prisma_keyword_id: null`, and `origin: manual`. The
`## PRISMA rationale` section is omitted. Created via `:WorkflowPrismaAcceptToNote` with no
keyword, or via a simpler `workflow notes create --type literature --bibkey <key>` command
(**Wave D** — falls out of C1 with the PRISMA section omitted; tracked in the roadmap).

## Graph → research question (out of scope, dependency note)

Clusters of unanchored literature notes with co-occurring `concepts` or shared authors
could signal emergent research themes. Detecting these and proposing a PICO question
requires ITEP-0013 (note relation graph, **Accepted**) plus a `workflow graph suggest-review`
command. Deferred until that graph work is built out.

## Acceptance criteria

- [ ] `workflow prisma bib accept-to-note <bibkey>` creates a `.md` at the correct vault
      path with the specified frontmatter (`origin`, `prisma_review_record_id`,
      `main_topic_id: null`) and body structure.
- [ ] With `--keyword-id` (or `--review-record-id`), the `## PRISMA rationale` section
      renders `ReviewRecord.include_rationale` + the `RationaleOption.label`s. Without a
      resolvable record, the section is omitted.
- [ ] The ```` ```bib ```` block round-trips through `workflow prisma bib import --stdin`
      without error.
- [ ] Running the command twice on the same bibkey exits non-zero and does not overwrite.
- [ ] `--all-accepted --keyword-id <id>` generates one note per `included == 1` record;
      existing notes are skipped and counted.
- [ ] `--dry-run` prints to stdout and writes nothing.
- [ ] An ambiguous bibkey (2+ entries) yields a helpful error naming the `bib_entry_id`s;
      `--bib-entry-id` disambiguates.
- [ ] `validate_note_frontmatter` accepts the new keys (schema extended).
- [ ] `Note.main_topic_id` is null at creation; `origin` is `prisma` or `manual`.
- [ ] `workflow graph orphans --type note` includes newly generated notes.
- [ ] `:WorkflowPrismaAcceptToNote` calls the CLI, opens the note, notifies counts; errors
      show CLI stderr.
- [ ] Tests: `tests/workflow/prisma/test_accept_to_note.py` — single, bulk, idempotency,
      dry-run, missing bibkey, ambiguous bibkey, no-record fallback.
- [ ] `nvim-plugin/tests/plenary/prisma_note_spec.lua` — block extraction, empty-result
      guard, already-exists path.
- [ ] Docs: CLAUDE.md prisma row; `nvim-plugin/doc/workflow.txt` documents the command.

## Out of scope

- Forcing `main_topic_id` or `concepts` at note creation time.
- Auto-linking the note to a `Content` record (use `content link-bib` after anchoring).
- The graph → research question flow (depends on ITEP-0013).
- Modifying the PRISMA screening UI (P2 hook deferred).
- Re-implementing biblatex rendering — reuse `workflow.bibliography.render.entry_to_biblatex`
  (A5 shared renderer, ADR-0020).

## Implementation notes

- Read first: `workflow.bibliography.render` (A5 bib-block renderer — the inverse of the
  importer is already solved there), `PRISMA-0003` (ReviewRecord/ReviewRationale schema),
  `workflow.vault.paths.resolve_vault_root()`, the literature note template +
  `validate_note_frontmatter` (must learn the new keys).
- Bib block: `render.entry_to_biblatex(entry)` — already lossless (Wave A). No new renderer.
- Frontmatter `id`: `YYYYMMDD` of creation + `-lit-` + bibkey slug. If the file already
  exists, abort (do not auto-suffix).

## Progress log

- 2026-06-03 — opened by user. Motivated by the epistemological tension between
  Zettelkasten (bottom-up) and PRISMA (top-down), and the need for an explicit,
  low-friction handoff at the `included == 1` transition point.
- 2026-06-04 — **C0 rewrite.** Reconciled against `tasks/audit/2026-06-03-prisma-to-literature-note-audit.md`:
  `Review`/`prisma_review_id`→`ReviewRecord`/`prisma_review_record_id` (D3); rationale via
  `include_rationale` + `RationaleOption.label`; `included == 1` (tri-state); `source:`→`origin:`;
  reuse A5 `render.entry_to_biblatex`; validator-schema extension moved in-scope; `--bib-entry-id`
  fallback + `AmbiguousLookupError` handling; ITEP-0013 marked Accepted; `adr_refs` updated.
  Implementation-ready. Plan: `tasks/plans/2026-06-04-wave-c-prisma-to-note-plan.md`.
