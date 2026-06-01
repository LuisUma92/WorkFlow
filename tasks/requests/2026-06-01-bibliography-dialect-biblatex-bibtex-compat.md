---
id: 20260601-bibliography-dialect-biblatex-bibtex-compat
title: BibEntry biblatex/bibtex dual-dialect compatibility layer
type: enhancement
source_agent: user
opened_on: 2026-06-01

status: open
resolution:
priority: P2
severity: recurring-friction

labels:
  - db
  - cli
  - docs
components:
  - workflow.bibliography
  - workflow.db
  - workflow.prisma

adr_refs: ["0019", "PRISMA-0002", "ITEP-0010"]
related_requests:
  - 2026-06-01-literature-note-bib-block-import.md
  - 2026-05-29-bibliography-service-extraction.md
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

# Request: make `BibEntry` genuinely biblatex-native + bibtex-compatible

## Context

Audit (2026-06-01, recorded in **ADR-0019**) of `BibEntry`
(`src/workflow/db/models/bibliography.py:104`): the model is **biblatex in field
naming** (`journaltitle`, `location`, `eventdate`, `urldate`, `pubstate`, …) but
**not fully biblatex-compliant**, and **not a bibtex schema** either (bibtex
`journal`/`address`/`school`/`chapter`/`type`/`crossref` are renamed or missing).
The importer bridges only `journal→journaltitle`. The literature-note import work
(`2026-06-01-literature-note-bib-block-import.md`) surfaced two concrete drops
(`techreport.type`, biblatex-only `@online` entry type — the latter already fixed
via `ignore_nonstandard_types=False`).

ADR-0019 decides: **biblatex-native model + a single bibtex compatibility
(alias) layer + a raw `date` column** for lossless round-trip. This request is the
implementation work for that ADR.

## Proposal

Implement ADR-0019 in phases (each independently shippable):

### P1 — shared dialect module (no schema change)

- Add `BIBTEX_TO_BIBLATEX` alias map + `to_biblatex()/to_bibtex()` field
  translators in `workflow.bibliography` (the module
  `2026-05-29-bibliography-service-extraction.md` already grows).
- Extend importer `TRANSLATED_BIB_KEYS` via that map: `address→location`,
  `school→institution`, `annote→annotation`, `note→notes` (in addition to the
  existing `journal→journaltitle`).
- No new columns yet; unknown fields still drop but the *common* bibtex names
  stop dropping.

### P2 — schema: close the hard gaps (forward-only migration, ITEP-0010)

- Add columns: `date String` (verbatim biblatex EDTF literal), `chapter`,
  `type` (entry subtype), and structured name parts (`name_prefix`,
  `name_suffix`) on `Author`.
- Backfill `date` from existing `year`/`month`; keep `year` as a *derived* int.
- Make `bibkey` the unique identity; demote `(title, year, volume)` to a
  non-unique fuzzy-dedup hint. **Migration must reconcile existing null/dup
  bibkeys** before applying the constraint.

### P3 — exporter (`workflow bib export` / extend `prisma bib export`)

- Emit biblatex (canonical) and bibtex (downgraded): reverse-map field names,
  `isn_type→isbn/issn/ismn`, and downgrade biblatex-only entry types
  (`@online→@misc`+howpublished, `@report→@techreport`,
  `@thesis→@phdthesis`/`@mastersthesis`).
- Round-trip test: biblatex import → export biblatex is field-equivalent.

## Acceptance criteria

- [ ] P1: importing a `.bib` using bibtex spellings (`journal`, `address`,
      `school`, `annote`, `note`) populates the biblatex columns; covered by tests.
- [ ] P2: a biblatex `date = {2010/2015}` round-trips (stored verbatim, not lost
      to `SmallInteger year`); `chapter` and `type` persist.
- [ ] P2: `bibkey` is unique/non-null post-migration; existing rows reconciled;
      migration tested against a copy of the live schema.
- [ ] P3: `import → export biblatex` is field-equivalent (round-trip test); bibtex
      export downgrades biblatex-only types and validates under a real bibtex run.
- [ ] Alias translation exists in exactly one module, consumed by both
      importer and exporter (no per-consumer duplication).
- [ ] Docs: CLAUDE.md bibliography bullet + ADR-0019 moved Proposed→Accepted on
      P1+P2 landing.

## Out of scope

- biblatex inheritance (`crossref`/`xdata`/`related`) — ADR-0019 defers (MAY).
- Full EDTF range *parsing* into structured columns — storing the raw literal is
  enough for round-trip.
- Migrating PRISMAreview's Django bib path.

## Implementation notes

- Read ADR-0019 first; it holds the MUST/SHOULD/MAY rules.
- The hard part is dates: `_parse_date` in `workflow.prisma.importer` only does
  `YYYY[-MM[-DD]]`; P2 stores the raw `date` and derives `year`.
- Identity change touches PRISMA dedup — coordinate with PRISMA-0005.

## Progress log

- 2026-06-01 — opened by user after compliance evaluation; ADR-0019 drafted
  (Proposed). Importer already accepts biblatex entry types
  (`ignore_nonstandard_types=False`) and wires `urldate` (done in the
  literature-note-bib-import work).
