# Consolidated Architecture Plan: Unified Knowledge System

**Date**: 2026-03-24 | **Author**: Architect Agent (revised with ITEP/lectkit integration)
**Scope**: Full WorkFlow monorepo — itep + lectkit + latexzettel + PRISMAreview convergence toward ADR-0002

---

## Existing Systems Inventory

Before planning, these are the four systems already in the repo and what each owns:

| System | ORM | DB | Owns |
|--------|-----|----|------|
| **itep** | SQLAlchemy 2.0 | SQLite (`~/.config/itep/itep.db`) | Institution, Course, EvaluationTemplate, Item (Bloom taxonomy), Book, Author, Topic, Content, LectureInstance, GeneralProject |
| **latexzettel** | Peewee | SQLite (`slipbox.db` per project) | Note, Citation, Label, Link, Tag — plus JSONL server + Neovim client |
| **PRISMAreview** | Django ORM | MariaDB (`prisma`) | Bib_entries (40+ BibLaTeX fields), Author, Abstract, PRISMA2020Checklist, Reviewed, Keyword |
| **lectkit** | None | None | cleta (cleanup), nofi (note splitting), crete (exercise file generation from book JSON) |

**Key observation**: ITEP's schema is the most mature and already models the academic domain (institutions, courses, books, topics, taxonomy, evaluations). It is the natural backbone for the unified system. latexzettel provides the Zettelkasten engine. PRISMAreview provides the bibliography richness. lectkit provides utilities that should wire into the unified CLI.

---

## Phase 0: Stabilization (Complexity: Low, 1-2 sessions)

Fix CRITICAL/HIGH issues from the review before any feature work.

**0a. Eliminate server duplication.** Delete all handler definitions and `ServerContext` from `server/main.py`. Import `ROUTES`, `ServerContext`, `CancelToken`, `CancelledError`, `require_not_cancelled` from `server/routers.py`. This fixes the `_require_not_cancelled` crash and `JsonScalar` undefined errors simultaneously.

**0b. Fix domain-to-infra dependency.** `domain/types.py:31` imports `from latexzettel.infra.orm import Note`. Replace with a `NoteRecord` Protocol defined in `domain/types.py`. The ORM Note satisfies it structurally — no runtime import needed.

**0c. Deduplicate `RenderFormat`.** Keep only in `domain/types.py`. Remove from `domain/models.py`. Update all imports.

**0d. Hygiene pass.**
- Remove all `contentReference[oaicite:*]` strings (~15 occurrences in infra/ and domain/)
- Remove `print("hola")` from `cli/main.py:79`
- Rename `infra/plataform.py` -> `infra/platform.py`
- Fix `Url_list.__str__` missing f-prefix in PRISMAreview
- Add `__pycache__/`, `*.pyc`, `slipbox.db`, `*.db` to `.gitignore`

**0e. First commit.** Commit latexzettel, PRISMAreview, and Zettelkasten ADRs as clean baseline.

---

## Phase 1: ORM Unification — SQLAlchemy as Single DB Layer (Complexity: Medium, 2-3 sessions)

### Decision: Adopt SQLAlchemy (already used by itep) as the single ORM for all systems

**Rationale:**
- ITEP already uses SQLAlchemy 2.0 with modern `Mapped[]` annotations, a 4-layer schema, and FK enforcement. It is the most mature DB code in the repo.
- latexzettel uses Peewee — a different ORM for no architectural reason. Migration to SQLAlchemy eliminates a dependency and unifies the stack.
- PRISMAreview uses Django ORM + MariaDB — acceptable for the web UI, but the bibliography data should be extractable to SQLite for local-first use.
- **One ORM (SQLAlchemy), one DB engine (SQLite), one schema** — all tools read/write the same database.

### Steps:

**1a. Migrate latexzettel from Peewee to SQLAlchemy.**
- Rewrite `infra/orm.py`: Note, Citation, Label, Link, Tag, NoteTag using SQLAlchemy `Mapped[]` style (matching itep's conventions).
- Update `infra/db.py`: replace Peewee-specific connect/close/schema_exists with SQLAlchemy engine/session pattern (reuse itep's `get_engine`/`get_session` helpers).
- Update all API modules that reference `db.Note.select()` etc. to use SQLAlchemy queries.
- Preserve the `DbModule` protocol contract so the server and CLI don't need major changes.

**1b. Promote bibliography into the shared schema.**
- Add bibliography tables to ITEP's `database.py` (or a new `src/shared/bibliography.py`): `BibEntry`, `BibAuthor`, `BibKeyword`, `BibUrl`, `BibAbstract`. Schema derived from PRISMAreview's Bib_entries (the most complete).
- ITEP's existing `Book` and `Author` become the canonical book/author tables. BibEntry references Book where applicable (journal articles don't have a Book FK).
- Write a one-time migration script that reads PRISMAreview's MariaDB and imports into the unified SQLite.

**1c. Cross-reference notes and bibliography.**
- latexzettel's Citation model gets a FK to the new BibEntry table (replacing the current bare `citationkey` string).
- This enables queries like "which notes cite this paper?" and "which papers are cited by notes in topic X?"

**1d. Wire `crete` (lectkit) into the shared DB.**
- Currently `crete` reads book metadata from a JSON file (`books.json`). Replace this with queries to ITEP's `Book`/`Content` tables, which already store chapter/section/page/exercise ranges.
- This eliminates the duplicate book metadata in JSON and makes `crete` consistent with `inittex`.

### Key decision needed from user:
**PRISMAreview web UI**: Keep Django for the review workflow (reading/screening papers), but have it read bibliography from the shared SQLite via a Django database router? Or sunset the web UI and move PRISMA review to CLI? **Recommendation**: Keep Django for now — the review UI is valuable for screening papers. Add a DB router to point `prismadb` at the shared SQLite for bibliography reads.

---

## Phase 2: TikZ Asset Pipeline (Complexity: Medium, 1-2 sessions)

### Context from existing systems:
- ITEP's `LectureProject` already has `lect/svg/` and `lect/img/` directories in its tree template.
- ITEP's `GeneralProject` has `img/` with symlinks to a central image directory.
- latexzettel has `render` and `processes.py` infrastructure for running pdflatex/make4ht.

### Steps:
1. Define `assets/tikz/` directory convention per ADR-0002. Each `.tex` is a `\documentclass[tikz]{standalone}` file.
2. Add a `tikz` CLI command group to the unified CLI:
   - `tikz build` — find all `assets/tikz/*.tex`, compile to PDF via `latexmk -pdf`, convert to SVG via `dvisvgm` or `pdf2svg`.
   - `tikz watch` — incremental rebuild (hash-based, stored in DB).
   - `tikz list` — index of all diagram assets with tags from commented YAML frontmatter.
3. Wire TikZ outputs into ITEP's symlink system: `lect/svg/` and `img/` can symlink to compiled TikZ assets.
4. Markdown notes reference rendered figures, not TikZ source (per ADR-0002 rule).

---

## Phase 3: Frontmatter Validation and Metadata Schema (Complexity: Low-Medium, 1 session)

1. Define Pydantic models (or JSON Schema) for:
   - Note frontmatter (`.md`): `id`, `title`, `tags`, `created`, `concepts`, `references`
   - Exercise commented YAML (`.tex`): `id`, `type`, `difficulty`, `tags`, `concepts`, `taxonomy_level`, `taxonomy_domain`
   - The exercise metadata MUST align with ITEP's `Item.taxonomy_level` and `Item.taxonomy_domain` enums (Bloom's taxonomy from `structure.py`).
2. Add a `validate` CLI command that scans all notes and exercises.
3. Wire validation into the Neovim JSONL server as a `validate` RPC method.

---

## Phase 4: Exercise DSL and Parser (Complexity: High, 3-4 sessions)

### Context from existing systems:
- `crete` (lectkit) already generates exercise `.tex` files with `\exe[ch]{idx}` macros and `\cite{book}` references. Its template system is functional but minimal.
- ITEP's `EvaluationTemplate` + `Item` + `EvaluationItem` already model exam structure, point allocation, and Bloom's taxonomy levels.
- ITEP's `CourseContent` maps Content (chapter/section/page/exercise ranges) to Course weeks.

### Steps:

**4a. Define LaTeX exercise macros** in a `.sty` file (extend or replace crete's `\exe` macro):
- `\qstem{...}` — question stem
- `\qoption[correct]{...}` — answer option (flag marks correct)
- `\qgeneralfeedback{...}` — general feedback
- `\qsolution{...}` — detailed solution
- `\qpenalty{value}` — penalty for wrong answer
- `\qdiagram{tikz-asset-id}` — reference to TikZ diagram (from Phase 2)
- Keep macros parseable by regex AND compilable by LaTeX.

**4b. Build the parser** in `src/latexzettel/api/exercises.py`:
- Parse `.tex` exercise files: extract commented YAML metadata + macro content into `Exercise` domain objects.
- Map `Exercise.taxonomy_level` and `Exercise.taxonomy_domain` to ITEP's enums.
- Store parsed exercises in the unified DB (new `Exercise` table, FK to Content/Topic).

**4c. Evolve `crete`**:
- `crete` currently generates exercise skeletons from book JSON. Upgrade it to:
  1. Read from ITEP's DB (Book + Content tables) instead of JSON
  2. Generate exercise files using the new DSL macros (not just `\exe`)
  3. Register generated exercises in the unified DB

**4d. Add exercise CLI commands**:
- `exercise parse` — validate structure of all exercise files
- `exercise list` — index by tag/concept/difficulty/taxonomy
- `exercise export-moodle` — generate Moodle XML from `Exercise` objects (use `xml.etree.ElementTree`)
- `exercise build-exam` — assemble an exam from ITEP's `EvaluationTemplate` + selected exercises

**4e. Connect exercises to evaluations**:
- ITEP's `EvaluationItem` says "exam X needs N items of type Y at taxonomy level Z". The exercise bank provides the pool. `exercise build-exam` selects from the pool to satisfy the template.

---

## Phase 5: Lectures Integration (Complexity: Medium, 2 sessions)

### Context from existing systems:
- ITEP already manages `~/Documents/01-U/00-Fisica/00AA-Lectures` via `LectureInstance` (course_id, year, cycle, first_monday, directory paths).
- `inittex` scaffolds lecture project directories with symlinks to central resources.
- `relink` recreates symlinks from config.yaml.
- The directory structure (`lect/tex/{topic}`, `eval/tex/{topic}`) is already defined in `LectureProject.tree`.

### Steps:

**5a. Bridge ITEP's LectureInstance to latexzettel's note system.**
- Each lecture `.tex` file inside `lect/tex/` should be indexable as a latexzettel Note (registered in slipbox.db/unified DB).
- Add a `lectures scan` command that discovers `.tex` files in lecture instances and optionally registers them as notes with auto-generated frontmatter.

**5b. Bidirectional linking between lectures and Zettelkasten.**
- Lecture notes reference Zettelkasten notes via `\excref` / `\zlink` macros.
- `lectures link` command: scan lecture files for references, update the Link table in the DB.
- This closes the loop: knowledge graph includes lecture-to-note edges.

**5c. Evaluation integration.**
- `lectures build-eval` command: given a LectureInstance + EvaluationTemplate, select exercises from the bank (Phase 4), assemble exam PDF, export to Moodle XML.
- Uses ITEP's `CourseEvaluation` (which maps evaluation to course week) + the exercise bank.

**5d. `nofi` integration.**
- `nofi` (note splitting with `%>path` / `%>END` markers) is useful during lecture prep. Wire it into the unified CLI and have it auto-register split files as notes in the DB.

---

## Phase 6: Knowledge Graph and Analysis (Complexity: Medium, 2 sessions)

Build a unified graph across all systems.

1. **Graph data sources**:
   - Note-to-note links (latexzettel's Link table)
   - Note-to-citation links (Citation table -> BibEntry)
   - Exercise-to-concept links (Exercise -> Content/Topic)
   - Lecture-to-note links (from Phase 5b)
   - Book-to-content links (ITEP's BookContent)
   - Course-to-content links (ITEP's CourseContent)

2. **CLI commands**:
   - `graph orphans` — notes with no incoming or outgoing links
   - `graph clusters` — topic groupings via community detection
   - `graph export-dot` — Graphviz DOT output
   - `graph export-tikz` — TikZ graph visualization (closing ADR-0001's vision)

3. **Neovim integration**: `graph.neighbors` RPC method — given current note, show linked notes/citations/exercises in a floating window.

---

## Dependency Graph

```
Phase 0 (Stabilization)
    |
    v
Phase 1 (ORM Unification — SQLAlchemy + Bibliography + crete DB wiring)
    |
    +------------------+------------------+
    |                  |                  |
    v                  v                  v
Phase 2            Phase 3            (parallel)
(TikZ Pipeline)    (Validation)
    |                  |
    +------------------+
    |
    v
Phase 4 (Exercise DSL + Parser + Moodle export)
    |
    v
Phase 5 (Lectures Integration — LectureInstance bridge, eval assembly)
    |
    v
Phase 6 (Knowledge Graph)
```

**Note**: Phase 1 is now a prerequisite for Phases 2 and 3 because the TikZ build state and validation schema need to write to the unified DB. Phases 2 and 3 can still proceed in parallel after Phase 1.

---

## Recommended Execution Order

1. **Phase 0** — Mechanical cleanup. Unblocks first commit.
2. **Phase 1** — ORM unification. This is the foundation. Without a single DB layer, every subsequent phase duplicates infrastructure.
3. **Phase 2 + Phase 3** (parallel) — TikZ pipeline + validation. Both are self-contained and immediately useful.
4. **Phase 4** — Exercise DSL. The largest and most impactful feature. Depends on TikZ (for diagram references) and validation (for metadata).
5. **Phase 5** — Lectures. Wires everything together with the existing ITEP project structure.
6. **Phase 6** — Knowledge graph. Capstone that makes the unified system queryable and visualizable.

---

## Unified CLI Vision

After all phases, the `workflow` command should expose a coherent command tree:

```
workflow
├── notes          (latexzettel: create, list, rename, remove, sync)
├── render         (latexzettel: pdf, html, updates)
├── tikz           (Phase 2: build, watch, list)
├── exercise       (Phase 4: parse, list, export-moodle, build-exam)
├── validate       (Phase 3: notes, exercises, frontmatter)
├── graph          (Phase 6: orphans, clusters, export-dot, export-tikz)
├── lectures       (Phase 5: scan, link, build-eval)
├── project        (itep: create, relink)
├── bib            (Phase 1: import, search, export-bib)
├── clean          (lectkit/cleta)
└── split          (lectkit/nofi)
```

Entry points in `pyproject.toml` remain as shortcuts: `inittex`, `relink`, `cleta`, `crete`, `nofi` — but all also accessible under the unified `workflow` tree.

---

## Open Questions Requiring User Input

1. **PRISMAreview web UI**: Keep Django for paper screening, or move to CLI-only? Recommendation: keep Django, add DB router to shared SQLite.
2. **SQLAlchemy version alignment**: ITEP uses SQLAlchemy 2.0 with `Mapped[]`. Confirm this is the target for all new DB code (vs. adding Peewee or raw sqlite3).
3. **Exercise macro naming**: Confirm `\qstem`, `\qoption`, `\qgeneralfeedback`, `\qsolution`, `\qpenalty`, `\qdiagram` before implementing — changing after content exists is painful.
4. **Neovim scope**: Should the plugin grow to support exercise editing/preview, or stay focused on Zettelkasten notes?
5. **Unified DB location**: Single `~/.config/workflow/workflow.db` (global), or per-project `slipbox.db` files? ITEP uses a global DB; latexzettel uses per-project. Recommendation: global for reference data (books, authors, institutions, courses), per-project for notes/links/exercises.
6. **`crete` evolution**: Fully subsume `crete` into the `exercise` command group, or keep it as a lightweight standalone? Recommendation: subsume — the Exercise DSL replaces crete's template system.
