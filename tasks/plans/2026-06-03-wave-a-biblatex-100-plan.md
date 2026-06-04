# Implementation plan — Wave A: biblatex → 100% (lossless storage)

Request: `tasks/requests/2026-06-01-bibliography-dialect-biblatex-bibtex-compat.md`
Roadmap: `tasks/roadmap/2026-06-03-bibliography-and-two-workflow-roadmap.md`
ADR: `docs/ADR/0019-bibliography-dialect-biblatex-bibtex.md` (**Accepted**) · ADR-0020 (boundary)
Security: `tasks/security/2026-06-03-roadmap-new-surfaces.md` (finding 3 = EAV whitelist)
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase, forward-only
migrations (ITEP-0010). Sub-agents write tests + impl; **parent runs the suite**.

---

## Verified anchors (confirmed in code 2026-06-03)

- `workflow.db.models.bibliography.BibEntry` (`__tablename__ = "bib_entry"`) — ~70 scalar cols
  already (titles, dates, `date` raw EDTF, `chapter`, `type`, `eprint`/`eprinttype`, `isn`+`isn_type`).
  Relationships: `author_links`, `urls`, `tag_links`, `content_links`, `review_records`.
- `workflow.bibliography.dialect.BIBTEX_TO_BIBLATEX` = 5 aliases
  (`journal,address,school,annote,note`). Pure module, no DB. `to_biblatex`/`to_bibtex` consume it.
- Importer `workflow.prisma.importer`: `_parse_fields` (line 352) maps via `TRANSLATED_BIB_KEYS`;
  recognised-field set built line 250 from `{ENTRYTYPE,ID,url,raw-date,authors,*TRANSLATED.values()}`.
  Fields outside that set are currently **dropped**. `import_bib_text` already exists (line 644).
- Exporter `workflow.prisma.exporter`: `_biblatex_field_pairs` (165), `_bibtex_field_pairs` (191),
  `_entry_to_biblatex` (229), `_entry_to_bibtex` (253), `export_bib_entries` (301).
- Migration harness `src/workflow/db/migrations/global/`; latest = `0012_bib_dialect_columns.py`
  → **next = `0013_`**. Driver stamps `schema_version`.
- Field catalog (whitelist source): `tasks/biblatex-fields-catalog.md` (293 fields, 9 aliases, 45 types).

---

## Target / design

100% **lossless** biblatex storage without 200+ dead columns (Decision D1). Any biblatex field
or alias with no first-class `BibEntry` column is persisted in a normalized overflow table
`bib_extra_field(bib_entry_id, field, value)` and re-emitted verbatim on export. Common bibtex
spellings stop dropping via 5 new aliases. First-class column promotion (A3) and cross-reference
inheritance (A4) are **separate serial phases** — they edit the same model file + migration
sequence and cannot run concurrently with A1.

---

## Decisions — LOCKED (user, 2026-06-03)

1. **D1** — overflow table `BibExtraField` is the 100% mechanism. No per-field column sprawl.
2. **D2** — `BibRelation` (A4) stores relations only; inheritance is opt-in `--resolve-xref` at export.
3. **D3** — (notes side, Wave C) provenance key `prisma_review_record_id`.

---

## Parallelization (conflict analysis)

| Item | Files touched | Parallel-safe with |
|------|---------------|--------------------|
| **A1** core overflow | `models/bibliography.py`, mig `0013`, `prisma/importer.py`, `prisma/exporter.py`, tests | **A2** (disjoint) |
| **A2** aliases | `bibliography/dialect.py` + its test ONLY | **A1** (disjoint) |
| A5 renderer relocate | `prisma/exporter.py` → `bibliography/render.py` | ⚠️ conflicts A1 exporter → **serial after A1** |
| A3 first-class cols | `models/bibliography.py` + mig `0014` + dialect + importer | ⚠️ conflicts A1+A2 → **serial** |
| A4 BibRelation | `models/bibliography.py` + mig `0015` + importer + exporter | ⚠️ conflicts A1 → **serial** |

**Launch now in parallel: A1 ‖ A2.** Then serial wave: A5 → A3 → A4.

---

## Phase A1 — `BibExtraField` overflow (core)

**Goal:** any catalog-known biblatex field without a first-class column round-trips losslessly.

**RED tests** (`tests/workflow/bibliography/test_extra_fields.py`, `tests/workflow/prisma/test_importer_extra.py`):
- import `.bib` with `subtitle`, `origtitle`, `langid`, `eprintclass` → rows in `bib_extra_field`.
- export `--dialect biblatex` re-emits those fields (round-trip field-equivalent).
- **whitelist (security #3):** a junk field `notabiblatexfield` is dropped, NOT stored.
- value-length cap enforced; rows-per-entry cap enforced.
- migration `0013` idempotency (run twice = no-op); table created with `UNIQUE(bib_entry_id, field)`.

**GREEN impl** — files touched (A1 OWNS these):
- `src/workflow/db/models/bibliography.py` — new `class BibExtraField(GlobalBase)`
  (`id` PK, `bib_entry_id` FK→`bib_entry.id`, `field` String(100), `value` Text,
  `UniqueConstraint(bib_entry_id, field)`); add `extra_fields` relationship on `BibEntry`.
- `src/workflow/db/migrations/global/0013_bib_extra_fields.py` — mirror `0012`'s structure exactly
  (read it first); create `bib_extra_field`; idempotent; stamp `schema_version`.
- `src/workflow/prisma/importer.py` — after `to_biblatex`, route catalog-known fields lacking a
  column to `BibExtraField` rows. New `_BIBLATEX_FIELD_CATALOG: frozenset[str]` from the catalog doc.
  Cap value length + rows/entry. Unknown-to-catalog fields keep current drop behaviour.
- `src/workflow/prisma/exporter.py` — `_biblatex_field_pairs` (+ bibtex path) append
  `entry.extra_fields` (field,value) so export re-emits.

**Commit point (parent):** suite green + flake8 0 → reviewer-esquema (python + architect).

---

## Phase A2 — 5 missing aliases (parallel with A1)

**Goal:** common bibtex/arXiv/JabRef spellings translate instead of dropping.

**RED tests** (`tests/workflow/bibliography/test_dialect.py`, extend):
- `to_biblatex` maps `archiveprefix→eprinttype`, `primaryclass→eprintclass`,
  `hyphenation→langid`, `pdf→file`, `key→sortkey`.
- inverse `to_bibtex` round-trips; existing collision-warning unchanged.

**GREEN impl** — files touched (A2 OWNS these, NOTHING else):
- `src/workflow/bibliography/dialect.py` — add the 5 entries to `BIBTEX_TO_BIBLATEX`.
  (Targets `eprintclass`/`langid`/`file`/`sortkey` may lack columns — fine, A1 overflow catches them.)

**Commit point (parent):** folds into the A1 commit or a sibling commit; reviewer-esquema.

---

## Serial follow-up phases (NOT launched now)

- **A5** — relocate `_entry_to_biblatex`/`_biblatex_field_pairs` → public `workflow.bibliography.render`
  (ADR-0020); re-export shim in `prisma/exporter.py`. After A1 (shares exporter).
- **A3** — promote high-value queryable fields to first-class columns (`subtitle`/`titleaddon`
  family, `origdate`/`origlocation`/`origpublisher`, `pubmedid`/`urlraw`); migration `0014`;
  read-both during transition (column OR overflow). After A1.
- **A4** — `BibRelation(child_id, parent_id, kind)` for `crossref/xref/xdata/related`; migration
  `0015`; `--resolve-xref` export flag (D2). After A1.

---

## Risks / out of scope

- **In scope (now):** A1 overflow + A2 aliases. Lossless storage + alias coverage.
- **Out of scope (now):** A3/A4/A5 (serial), all of Waves B–E.
- **Risk — EAV abuse (security #3):** MUST whitelist `field` against the biblatex catalog, cap value
  length + rows/entry. No arbitrary keys.
- **Risk — migration sequence collision:** A1=`0013` only. A3/A4 numbers reserved (`0014`/`0015`)
  but NOT created until their serial phase — prevents parallel collision.
- **Never** run `workflow db migrate` against the live DB; tests use isolated `WORKFLOW_DATA_DIR`.

---

## Verification (parent runs)

```bash
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10
```
