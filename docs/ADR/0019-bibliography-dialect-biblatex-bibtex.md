---
id: 0019
title: "Bibliography dialect: biblatex-native model + bibtex compatibility layer"
aliases:
  - ADR-0019
status: Accepted
date: 2026-06-01
authors:
  - Luis Fernando Umaña Castro
reviewers:
  - Luis Fernando Umaña Castro
tags:
  - architecture
  - domain
  - bibliography
decision_scope: module
supersedes: null
superseded_by: null
related_adrs: ["PRISMA-0002", "PRISMA-0005", "0007"]
---

## Context

`BibEntry` (`src/workflow/db/models/bibliography.py:104`) was introduced by the
PRISMA pipeline (PRISMA-0002) and is now the single bibliography table shared by
PRISMA review, `workflow content link-bib`, and the literature-note
`:WorkflowBibImport` flow. Its docstring claims "Full BibLaTeX entry," and its
column names are indeed biblatex spellings (`journaltitle`, `location`,
`eventdate`, `urldate`, `pubstate`, `pagination`, `eprinttype`, `addendum`,
`shorthand`, `booktitle`/`maintitle`/`indextitle`/…).

An audit (2026-06-01) found the model is **biblatex in naming but not in depth**,
and is **not a bibtex schema either** (bibtex field names `journal`, `address`,
`school`, `chapter`, `type`, `crossref` are renamed or absent). The importer
(`workflow.prisma.importer`) reads `.bib` syntax via `bibtexparser` and bridges a
few names (`journal → journaltitle`) through `TRANSLATED_BIB_KEYS`, but several
gaps remain. A decision is needed now because two consumers (notes import + PRISMA)
and a planned exporter all depend on what "compliant" means here.

### Audit findings (gaps vs true biblatex)

1. **Date model is bibtex-era.** biblatex's canonical identity field is `date`
   (EDTF: ranges `2010/2015`, partial `2010-04`, `forthcoming`, seasons, open
   ranges). The model splits into `year SmallInteger` + `month String` +
   `publication_date Date` (`:153-155`); `_parse_date` handles only
   `YYYY[-MM[-DD]]`. A `SmallInteger` year cannot represent ranges, `n.d.`, or
   BCE. **This is the only hard, non-aliasable incompatibility.**
2. **Names lose biblatex structure.** `Author(first_name, last_name)` +
   `BibAuthor.AuthorType` captures roles (author/editor/translator) but drops the
   4-part name model (given/family/prefix(von)/suffix(jr)), `editortype`, and the
   `and others` → et-al marker. `_split_authors` is heuristic.
3. **No inheritance.** biblatex `crossref`/`xdata`/`related`+`relatedtype` absent.
4. **Missing fields:** `chapter`, `type` (entry subtype — why a techreport `type`
   field silently dropped), `origdate`/`origtitle`, `langid` (only `language`).
5. **Non-standard identity.** Unique on `(title, year, volume)` (`:111`); `bibkey`
   is nullable and not unique. Both bibtex and biblatex identify entries by the
   **citation key**. The current key can false-merge distinct works or
   false-split one work on volume formatting.
   > **Note (2026-06-02):** Replacing `UNIQUE(title,year,volume)` with `UNIQUE(bibkey)`
   > (Plan P2.4) was **rejected**. Duplicate bibkeys are an intentional, tested feature —
   > `get_bib_entry_by_bibkey` raises `BibKeyAmbiguous` and consumers (exercise sync,
   > content link-bib, maturation) tolerate ambiguity by design. A calculated-bibkey
   > enforcement approach is tracked separately in
   > `tasks/requests/2026-06-02-calculated-bibkey-enforcement.md`.
   >
   > **Update (2026-06-02): calculated bibkey landed.** Pure `calculate_bibkey`
   > (`src/workflow/bibliography/bibkey.py`) derives keys as book
   > `<surname:lc><year:04d>[V<vol:02d>]E<ed:02d>` / article
   > `<surname:lc><year:04d>[V<vol:02d>]` (fallbacks `0000`/`anon`/`E01`,
   > von-particle + accent fold). The importer keeps the source `.bib` ID by
   > default and only calculates when it is missing (`--recompute-bibkeys`
   > forces it); collisions across distinct works get a bijective base-26
   > suffix. `workflow prisma bib recompute-keys [--dry-run] [--all]` backfills
   > missing keys (or normalizes all, after confirmation + DB backup). Bibkeys
   > remain **non-unique** by design — this enforces a *format*, not uniqueness.
6. **Folded identifiers (acceptable):** isbn/issn/ismn unified into `isn` +
   `isn_type` FK — representationally fine, but needs reverse-mapping on export.

## Decision Drivers

- One bibliography table must serve both systematic-review imports and
  literature-note authoring without a second schema.
- bibtex is a strict subset of biblatex and shares `.bib` syntax → bidirectional
  support is *aliasing + one date change*, not a rewrite.
- Lossless round-trip (import → store → export) is the real correctness bar; the
  biggest current loss is date semantics.
- Minimise churn to PRISMA-0002's existing importer and the shipped
  `content link-bib` / `:WorkflowBibImport` consumers.

## Decision

Adopt a **biblatex-native data model with an explicit bibtex compatibility
layer**. The schema stores biblatex field names as the canonical form; an alias
table maps bibtex spellings on the way in and reverses them on the way out. The
single non-aliasable gap (dates) is closed by storing the **raw biblatex `date`
literal** alongside the derived integer `year`.

Concretely:

- **Identity** = citation key. `bibkey` becomes the dedup key; `(title, year,
  volume)` is demoted to a fuzzy-match hint only.
- **Dates**: add a `date: String` column holding the verbatim biblatex EDTF
  literal. `year`/`month`/`publication_date` become *derived* views of it for
  bibtex export and sorting. No EDTF normalisation library required at rest.
- **Field aliasing** lives in `workflow.bibliography` (the module
  `2026-05-29-bibliography-service-extraction.md` already grows), shared by both
  importer and the future exporter — never duplicated per consumer.
- **Entry types** stay a free `String` (already accepts biblatex types since the
  `ignore_nonstandard_types=False` fix, 2026-06-01). bibtex export downgrades
  unknown types (`@online→@misc`+howpublished, `@report→@techreport`,
  `@thesis→@phdthesis`/`@mastersthesis`).

## Architectural Rules

### MUST

- The canonical stored field names **MUST** be biblatex spellings.
- A single alias map (`BIBTEX_TO_BIBLATEX`) **MUST** live in
  `workflow.bibliography` and be the only place bibtex↔biblatex name translation
  occurs; importer and exporter **MUST** both consume it. No per-consumer aliasing.
- The raw biblatex `date` literal **MUST** be preserved verbatim when present;
  `year`/`month` **MUST NOT** be the sole date storage.
- Export **MUST** round-trip: a biblatex entry imported then exported as biblatex
  **MUST** be field-equivalent (modulo whitespace/brace normalisation).

### SHOULD

- `bibkey` **SHOULD** be the unique identity; `(title, year, volume)` **SHOULD**
  be demoted to a non-unique dedup heuristic.
- New columns `chapter`, `type` (entry subtype), and structured name parts
  (prefix/suffix) **SHOULD** be added so common biblatex/bibtex fields stop
  dropping.
- bibtex export **SHOULD** downgrade biblatex-only entry types to the nearest
  bibtex type rather than emitting invalid bibtex.

### MAY

- biblatex inheritance (`crossref`/`xdata`/`related`) **MAY** be modelled later;
  it is out of scope for the first compatibility pass.
- EDTF range parsing into structured columns **MAY** be added; storing the raw
  literal is sufficient for round-trip.

## Implementation Notes

- Alias map and the import/export dialect functions belong in
  `workflow.bibliography.service` (or a sibling `dialect.py`).
- The importer (`workflow.prisma.importer`) already bridges
  `journal→journaltitle`; extend `TRANSLATED_BIB_KEYS` with `address→location`,
  `school→institution`, `annote→annotation`, `note→notes`, plus `chapter`,
  `type`.
- A forward-only migration (ITEP-0010) adds `date`, `chapter`, `type`, and name
  parts; backfill `date` from existing `year`/`month`.
- This ADR does **not** require touching the shipped `--stdin` import behaviour;
  it is the schema-direction decision that work deferred to.

## Amendment — A4 inter-entry relations (2026-06-04)

Wave A phase A4 adds inter-entry relation support without breaking the
single-table model:

- **Storage:** a new `bib_relation(child_id, parent_bibkey, parent_id NULL,
  kind)` table (migration `0015`) holds `crossref`/`xref`/`xdata`/`related`.
  `parent_bibkey` preserves the raw target verbatim, so forward references and
  missing targets stay lossless; `parent_id` is resolved (best-effort, bibkeys
  are non-unique) in a second import pass once every entry is inserted. These
  fields are **no longer** routed to `bib_extra_field` overflow.
- **Default export:** relation fields round-trip verbatim from `bib_relation`.
- **`--resolve-xref` (decision D2):** opt-in at export; resolves biblatex
  crossref field inheritance (the `\DeclareDataInheritance` default map — e.g.
  a `@book` parent's `title` → child `@inbook` `booktitle`) and xdata verbatim
  copy, child-wins, suppressing the resolved pointer fields. `xref`/`related`
  do not trigger inheritance and are preserved as pointers. Inheritance is one
  level deep; the map lives in `workflow.bibliography.inheritance` (foundation
  layer — ADR-0020).

## Consequences

- **Positive:** one table serves both dialects; lossless biblatex round-trip;
  the "is it compliant?" question has a documented answer; the techreport/online
  field drops found in review get root-caused, not patched per-snippet.
- **Negative / cost:** a schema migration + backfill; exporter must implement
  type downgrade; `bibkey`-as-identity requires reconciling existing rows whose
  `bibkey` is null/duplicated.
- **Risk:** changing the unique constraint touches PRISMA dedup behaviour — must
  be migrated and tested against the live `workflow.db`.
