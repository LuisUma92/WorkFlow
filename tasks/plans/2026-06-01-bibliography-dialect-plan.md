# Implementation plan — BibEntry biblatex/bibtex dual-dialect (ADR-0019)

Request: `tasks/requests/2026-06-01-bibliography-dialect-biblatex-bibtex-compat.md`
ADR: `docs/ADR/0019-bibliography-dialect-biblatex-bibtex.md` (**Accepted**)
Methodology: TDD (RED→GREEN→REFACTOR), forward-only migrations (ITEP-0010),
reviewer-esquema at each phase end. Phases ship independently.

## Verified anchors

- Migration harness: `src/workflow/db/migrations/global/NNNN_*.py`; latest is
  `0007_add_note_edges.py` → **next = `0008_`**. Driver: `workflow.db.migrations`
  `upgrade()`; stamps `schema_version`. CLI: `workflow db migrate`.
- Importer single parse + map site: `workflow.prisma.importer`
  (`TRANSLATED_BIB_KEYS`, `_parse_fields`, `import_bib_text`).
- Exporter: `workflow.prisma.exporter` — `_entry_to_bibtex(entry)` /
  `export_bib_entries()` (currently bibtex-ish, dialect-unaware, no type downgrade).
- Model: `workflow.db.models.bibliography.BibEntry` (unique `(title,year,volume)`,
  `bibkey` nullable) + `Author(first_name,last_name)`.

## Phase 1 — shared dialect module (NO schema change)

P1.1 New `src/workflow/bibliography/dialect.py`:
   - `BIBTEX_TO_BIBLATEX: dict[str,str]` = `{journal→journaltitle, address→location,
     school→institution, annote→annotation, note→notes}` (+ keep existing bridges).
   - `to_biblatex(fields: dict) -> dict` (alias bibtex→biblatex keys, last-writer
     loses on collision with a warning) and inverse `to_bibtex(fields) -> dict`.
   - Pure functions, no DB. This is the ONE place name translation lives (ADR MUST).
P1.2 Wire importer: route each parsed raw entry through `to_biblatex` BEFORE
   `_parse_fields`, OR fold the map into `TRANSLATED_BIB_KEYS`. Keep `journal→
   journaltitle` behaviour identical; add the 4 new aliases.
P1.3 Tests `tests/workflow/bibliography/test_dialect.py` + importer test: a `.bib`
   using bibtex spellings (`journal`, `address`, `school`, `annote`, `note`)
   populates `journaltitle`/`location`/`institution`/`annotation`/`notes`.
P1.4 No migration. flake8 + full suite green. → commit, reviewer-esquema.

## Phase 2 — schema: close hard gaps (migration `0008`, ITEP-0010)

P2.1 Model `BibEntry`: add `date: Mapped[str|None]` (verbatim biblatex EDTF
   literal), `chapter: str|None`, `type: str|None` (entry subtype). `Author`: add
   `name_prefix: str|None`, `name_suffix: str|None`.
P2.2 Importer: store raw `date` literal when present; still derive `year`/`month`
   from it (extend `_parse_date` to accept ranges by taking the first component
   for `year`, storing the full literal in `date`). Map `chapter`/`type` direct.
   `_split_authors` → populate prefix/suffix (von/jr) when detectable.
P2.3 Migration `0008_bib_dialect_columns.py`: `ALTER TABLE bib_entry ADD date,
   chapter, type`; `author ADD name_prefix, name_suffix`; backfill
   `date = year[-month]` for existing rows.
P2.4 ~~Identity change~~: **REJECTED 2026-06-02.** `UNIQUE(bibkey)` conflicts with
   the intentional ambiguous-bibkey feature. Tracked in
   `tasks/requests/2026-06-02-calculated-bibkey-enforcement.md`.
P2.5 Tests: `date={2010/2015}` round-trips (stored verbatim, year derived);
   `chapter`/`type` persist; migration idempotency; bibkey-uniqueness post-migrate;
   PRISMA dedup still works on the new helper.

## Phase 3 — exporter (biblatex canonical + bibtex downgrade)

P3.1 `exporter.py`: add `_entry_to_biblatex(entry)` (canonical field names via
   `dialect.to_bibtex`-inverse = identity for biblatex) and make `_entry_to_bibtex`
   reverse-map (`journaltitle→journal`, `location→address`, `isn_type→isbn/issn/
   ismn`) + downgrade biblatex-only entry types (`@online→@misc`+howpublished,
   `@report→@techreport`, `@thesis→@phdthesis`/`@mastersthesis`).
P3.2 CLI: extend `prisma bib export` with `--dialect biblatex|bibtex` (default
   biblatex). Optionally surface neutral `workflow bib export` (ties to followups
   item 8 — out of scope unless doing that move).
P3.3 Round-trip test: biblatex `.bib` → import → `export --dialect biblatex` is
   field-equivalent (modulo brace/whitespace). bibtex export validates under a
   real `bibtex`/`biber` dry run if available, else structural assertion.

## Sequencing / risk

- P1 is safe and immediately useful (stops common bibtex-name drops); ship first.
- P2 is the risky one (live-DB migration + identity change) — gate on a backup +
  schema-copy test; split columns (`0008`) from identity (`0009`) so a bad
  identity migration doesn't block the column adds.
- P3 depends only on P1 (dialect map); can land before P2's identity change.
- Move ADR-0019 references in docs to reflect landed phases; flip nothing else.

## Verification (each phase)

- `uv run pytest -q --ignore=tests/test_database.py`
- `uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10`
- P2/P3: real CLI — import a biblatex sample, `workflow db migrate`, export both
  dialects, diff round-trip.
