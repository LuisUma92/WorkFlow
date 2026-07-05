# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WorkFlow is a Python CLI toolkit for managing LaTeX projects and a unified Zettelkasten knowledge system for academic writing (thesis, lectures, exercises). It integrates Markdown note-taking, LaTeX rendering, TikZ diagrams, exercise management, and bibliography across multiple institutions (UCR, UFide, UCIMED).

## Commands

```bash
# Install (editable)
pip install -e .
# or with uv
uv sync

# Run all tests
pytest

# Lint (matches CI)
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

## CLI Entry Points

Defined in `pyproject.toml` under `[project.scripts]`:

| Command    | Module              | Purpose                              |
|------------|---------------------|--------------------------------------|
| `workflow` | `main:cli`          | Main CLI (exercise, lectures, graph, tikz, validate) |
| `inittex`  | `itep.create:cli`   | Initialize LaTeX project structure   |
| `relink`   | `itep.links:cli`    | Recreate symlinks from config.yaml   |
| `cleta`    | `lectkit.cleta:cli` | Clean TeX auxiliary files            |

## Architecture

### Module Structure

- **`src/workflow/db/`** — Unified database module (SQLAlchemy 2.0). Owns ALL ORM models and repository interfaces. Two-base architecture: `GlobalBase` (`~/.local/share/workflow/workflow.db`) and `LocalBase` (`<project>/slipbox.db`). See ADR-0003, ADR-0004, ADR-0007.
  - **`src/workflow/db/models/knowledge.py`** — Knowledge taxonomy reference + master entities: `DisciplineArea`, `MainTopic`, `Topic`, `Content`, `Concept`, `MainTopicSyllabus`. `Topic` is now rooted at `DisciplineArea` (not `MainTopic`); `MainTopicSyllabus(main_topic_id, topic_id, week_no, order_no)` is the join table. Owns `_TAXONOMY_DOMAINS` (`Información`, `Procedimiento Mental`, `Procedimiento Psicomotor`, `Metacognitivo`).
  - **`src/workflow/db/models/academic.py`** — Academic/evaluation entities: `Institution`, `Course`, `CourseContent`, `EvaluationTemplate`, `Item`, `EvaluationItem`, `CourseEvaluation`. Owns `_TAXONOMY_LEVELS`.
  - **`src/workflow/db/models/bibliography.py`** — Bibliography entities including `BibContent` (with `chapter_number`, `section_number`, `first_page`/`last_page` locus columns).
  - **`src/workflow/db/models/notes.py`** — Note entities: `Note`, `Citation`, `Label`, `Link`, `Tag`, `NoteTag`, `NoteConcept`, `NoteEdge`. `Note.main_topic_id` FK → `MainTopic` (nullable, links note to project-context MainTopic). `Concept` is no longer defined here.
  - **`src/workflow/db/models/exercises.py`** — Exercise entities: `Exercise`, `ExerciseOption`, `ExerciseConcept`. No `Exercise.concepts` JSON column; no `Exercise.content_id`; concept links use the `ExerciseConcept` M2M table.

- **`src/workflow/tikz/`** — TikZ standalone asset pipeline. Compiles `.tex` diagrams to PDF/SVG with incremental builds. See ADR-0006.

- **`src/workflow/validation/`** — Frontmatter validation. Validates YAML frontmatter in `.md` notes and commented YAML in `.tex` exercises.

- **`src/workflow/latex/`** — Shared LaTeX parsing utilities. `braces.py` (brace-counting macro extraction), `comments.py` (commented YAML), `normalize.py` (custom macro expansion for Moodle export). See ADR-0011, ADR-0012.

- **`src/workflow/exercise/`** — Exercise bank management. `parser.py` (parse .tex → domain objects), `moodle.py` (Moodle XML export), `generator.py` (placeholder file creation), `selector.py` (exercise selection by taxonomy), `exam_builder.py` (exam assembly), `cli.py` (8 CLI commands). See ADR-0009, ADR-0010, ADR-0011, ADR-0012.

- **`src/workflow/lecture/`** — Lectures integration. `scanner.py` (discover .tex files, register as notes), `note_splitter.py` (split notes at `%>` markers), `linker.py` (extract `\cite`/`\ref`/`\label`, update Link/Citation tables), `eval_builder.py` (bridge EvaluationTemplate to exercise bank), `cli.py` (4 CLI commands: scan, split, link, build-eval).

- **`src/workflow/graph/`** — Knowledge graph analysis and export. `domain.py` (GraphNode, GraphEdge, KnowledgeGraph), `collectors.py` (query global+local DBs), `analysis.py` (orphans, hubs, components, neighbors, stats), `dot_export.py` (Graphviz DOT), `tikz_export.py` (TikZ with spring layout), `clustering.py` (optional networkx communities), `cli.py` (6 CLI commands: orphans, stats, export-dot, export-tikz, clusters, neighbors). Graph commands support `--main-topic`, `--discipline-area`, and `--topic` filter flags (Phase 4E, v1.11.0).

- **`src/workflow/evaluation/`** — Evaluation CLI. `cli.py` (3 Click groups: evaluations, item, course), `service.py` (business logic, validation), `formatters.py` (table + JSON output). Commands: evaluations list|show|add|edit, item list|add, course list|add. Neovim Telescope pickers in nvim-plugin. See ADR-0016.

- **`src/workflow/vault/`** — Vault unification (ITEP-0011, Implemented). `unify.py` reads legacy per-project `slipbox.db` via raw `sqlite3`, snapshots a backup, detects reference/zettel_id collisions, id-remaps notes/labels/citations/tags/links into GlobalBase, moves `.md` files into `<vault_root>/notes/<type>/`, writes `.vault_pointer` marker. `cli.py`: 3 commands (info, validate, unify). `paths.py`: dependency-free `resolve_vault_root()` helper (reads `WORKFLOW_VAULT_ROOT` env, default `~/Documents/01-U/0000AA-Vault`). Reused by `lectures split` default output target.

- **`src/workflow/prisma/`** — PRISMA systematic review CLI. `cli.py` (prisma group: bib, keyword, review subgroups), `service.py` (queries, status constants), `formatters.py` (table + JSON). Commands: prisma bib list|show, keyword list, review list, checklist show, rationale add|list, tag add|list. See ADR PRISMA-0005.

- **`src/itep/`** — Init TeX Project (ITeP). Project scaffolding and management. Uses `workflow.db` for models. Config is `config.yaml` per project (pointer to DB record, see ADR ITEP/0003).

- **`src/latexzettel/`** — Zettelkasten engine. CLI + JSONL/NDJSON RPC server + Neovim Lua client. Uses `workflow.db.models.notes` via compatibility shim in `infra/orm.py`.

- **`src/lectkit/`** — Lecture utilities: `cleta` (cleanup), `nofi` (note splitting), `crete` (exercise generation — **deprecated**, use `workflow exercise create`).

- **`src/PRISMAreview/`** — Django 5.0 PRISMA systematic review web app. Backed by MariaDB. Web interface for BibTeX import. CLI access via `workflow prisma` (see `src/workflow/prisma/`).

- **`src/appfunc/`** — Shared utilities: input validation (`FieldSpec` in `iofunc.py`), enum selection, menus.

- **`shared/latex/sty/`** — 18 LaTeX style files (SetCommands, PartialCommands, SetExercises, VectorPGF, SetZettelkasten, etc.). Symlinked into projects from `~/.local/share/workflow/sty/`.

- **`shared/latex/templates/`** — LaTeX templates for notes, exercises, lectures.

- **`shared/latex/cls/`** — texnote.cls and preamble files (moved from latexzettel/defaults/template/).

- **`shared/latex/pandoc/`** — Pandoc pipeline: filter.lua, template.tex, defaults.yaml, preprocess.py (moved from latexzettel/pandoc/).

### Key Patterns

- All CLIs use **Click** with groups and commands
- **SQLAlchemy 2.0** with `Mapped[]` annotations is the single ORM (ADR-0004)
- Data access goes through **repository Protocol interfaces** (`workflow.db.repos.protocols`)
- **Hybrid DB**: global for reference data + unified vault notes (ADR-0003, ITEP-0011); local per project for PRISMA decisions + project-scoped notes (ITEP-0011 P5)
- XDG layout: paths resolved via `src/workflow/paths.py` (platformdirs; data=`~/.local/share/workflow/`, config=`~/.config/workflow/config.yaml`, cache=`~/.cache/workflow/`). In the live developer setup `~/.local/share/workflow` is a **symlink** to `<repo>/share/` — `paths.py` is symlink-agnostic and works identically either way. `WORKFLOW_DATA_DIR`/`WORKFLOW_VAULT_ROOT` env overrides win; legacy `~/01-U/workflow/workflow.db` kept via fallback resolver until `workflow db migrate-xdg` is run. `workflow.config` reads `~/.config/workflow/config.yaml` (`vault_path`, `default_institution`, `default_timezone`; env > config > default). See ADR-0008 (amended 2026-06-05, note 2026-06-06).
- Exercise macros: extend existing `\question`, `\qpart`, `\pts` — never replace (ADR-0005)
- `.tex` files are **truth source** for exercise content; DB stores metadata index only (ADR-0010)
- Exercise CLI: `workflow exercise parse|list|sync|gc|export-moodle|create|create-range|build-exam`. `workflow exercise sync` supports `--strict-concepts` and writes `ExerciseConcept` M2M rows (no JSON column). `--strict-concepts` exits 1 and lists every dropped concept code (across the whole batch, tagged by file) to stderr — the strict-mode sync is all-or-nothing (rolled back on failure); without the flag, unresolved codes are a warning naming the file + code, sync still succeeds. An invalid explicit `status:` (outside `placeholder|in_progress|complete`) is recorded as a `ParseResult` error (parser never raises, ADR-0011) — `exercise parse`/`exercise sync`/`validate exercises` all exit nonzero for it; an absent `status:` still falls back to `_infer_status` unaffected. `validate_exercise_metadata` (`workflow.validation.schemas`) warns (does not error) on unrecognized frontmatter keys with a difflib closest-match suggestion. `build-exam` supports a taxonomy×concept balance report (`src/workflow/exercise/balance.py`, additive-only — `ExamDocument` unchanged): `--balanceo` prints a table to stderr; `--balanceo-csv PATH` writes the report as CSV to `PATH` (either flag triggers the computation — no optional-value single flag, per Click's lack of clean support for that shape); `--json` (requires `--balanceo`/`--balanceo-csv`) emits `{matrix, concept_coverage, warnings}` as the sole JSON object on stdout, suppressing the `.tex` body there (use `--output` to still capture it); `--fail-under FLOAT` (requires `--balanceo`/`--balanceo-csv`) exits 2 when `concept_coverage.distinct_covered/total_concepts` falls below the threshold — `total_concepts` is scoped to the exercise pool passed to `select_exercises`, not the whole DB. `list --chapter N` resolves chapter via `Exercise.book_id` → `BibContent(chapter_number, first_exercise..last_exercise inclusive)` with trailing-digit suffix parse of the exercise reference (`workflow.exercise.chapter`); unresolvable exercises excluded with single stderr count note; composes with `--concept`/`--json` (JSON stdout stays pure).
- LaTeX normalization: custom macros expanded to standard LaTeX before Moodle export (ADR-0012)
- Exam CLI (`src/workflow/exam/`): `workflow exam scaffold-xml` is dual-mode, detected from which options are supplied — legacy `--cycle --group --label --category --blocks` (unchanged since 2026-05-27) vs weekly `--week --dc <DC.md> --kind comprension|practica [--category-style flat|hierarchical]` (default flat; hierarchical is a documented opt-in). Weekly mode derives categories from the DC.md's `##` headings and encodes the `Practica-N → PC-N → Tema #(N+1)` offset in `workflow.exam.weekly.tema_label_for_practica` — never re-derive it as tribal knowledge. Mixing legacy and weekly options is a `click.UsageError` (exit 2). `workflow exam validate <file.xml> [--strict] [--json]` is a structural Moodle lint (fraction-100/fraction-0/cdata/defaultgrade/penalty/single per multichoice question; `--strict` adds idnumber + category checks); exits 1 on any violation, never silently passes a raw-scan/etree count mismatch.
- Lectures CLI: `workflow lectures scan|split|link|build-eval`
- Graph CLI: `workflow graph orphans|stats|export-dot|export-tikz|clusters|neighbors` — all commands accept `--main-topic CODE`, `--discipline-area CODE`, `--topic NAME` filters (Phase 4E).
- Evaluation CLI: `workflow evaluations list|show|add|edit`, `workflow item list|add`, `workflow course list|add` (ADR-0016)
- PRISMA CLI: `workflow prisma bib list|show`, `workflow prisma bib import <PATH>` (also `--stdin` to read biblatex from stdin; `--recompute-bibkeys` to force calculated keys), `workflow prisma bib export [--dialect biblatex|bibtex] [--resolve-xref]` (default biblatex; bibtex downgrades biblatex-only types + reverse-maps field names; `--resolve-xref` inlines biblatex crossref/xdata field inheritance into each entry and suppresses those pointer fields — ADR-0019 A4), `workflow prisma bib recompute-keys [--dry-run] [--all] [--yes]` (fills missing calculated bibkeys by default; `--all` normalizes every key after confirmation; backs up the DB first — ADR-0019), `workflow prisma keyword list`, `workflow prisma review list`, `workflow prisma checklist show`, `workflow prisma rationale add|list`, `workflow prisma tag add|list` (ADR PRISMA-0005)
- Vault CLI: `workflow vault info|validate|unify` (ITEP-0011, Implemented P0–P7). Migrates per-project `slipbox.db` notes into the global vault; idempotent via `.vault_pointer` marker. `lectures split` defaults output to `<vault_root>/notes/permanent/` (override with `--output-dir`). Vault root resolved by `workflow.vault.paths.resolve_vault_root()` (env `WORKFLOW_VAULT_ROOT`). Per-project note model: `ProjectNote` in `db/models/project_layer.py` (LocalBase, ITEP-0011 P5) — no CLI command yet.
- Concept CLI: `workflow concept list|show|add|tree|rm|rename` (ITEP-0012). Manages the concept taxonomy (code slugs, parent hierarchy, content affiliation). `workflow concept add --code SLUG --label TEXT --content-id INT --domain DOMAIN [--parent CODE] [--description TEXT]`. Valid `--domain` values: `Información`, `Procedimiento Mental`, `Procedimiento Psicomotor`, `Metacognitivo` (from `_TAXONOMY_DOMAINS` in `workflow.db.models.knowledge`). `rm --force` reparents children to grandparent. Concept is now rooted at `Content` (not `MainTopic`); use `concept.main_topic` property for chain traversal. `resolve_concepts(codes, session, *, strict)` in `src/workflow/concept/service.py` is reused by the validator and MUST be reused by any future `notes link --concept` command. ADR: [ITEP-0012](docs/ADR/ITEP-0012-concept-orm.md). `notes link --concept CODE [--remove] [--strict]` materializes `NoteConcept` rows (P1, `dc79b59`). `notes link --main-topic CODE [--remove]` sets `Note.main_topic_id` FK (Phase 4D, v1.11.0). `notes sync` builds `NoteConcept` rows per-note from frontmatter `concepts:` list via Pass 5 `_sync_note_concepts` (`--strict-concepts` flag; P2, `2340d38`). Concept references are slug-only strict everywhere (`Concept.code`); labels are display-only (decision 2026-07-04, ITEP-0012 amendment).
- Notes create CLI: `workflow notes create --type literature --bibkey <key> [--bib-entry-id N] [--origin LABEL] [--vault-root P] [--dry-run] [--json]` (Wave D). Creates a literature note directly from a bibkey with no PRISMA context. Reuses `workflow.prisma.accept_to_note.accept_to_note` (same renderer as Wave C). `--origin` overrides the frontmatter `origin:` field (default `manual`); `--bib-entry-id` disambiguates when a bibkey matches multiple entries. `--json` → `{"note_path","bibkey","created"}`. Idempotent: second run returns `created:false` without overwriting. `--dry-run` computes content without writing.
- Import CLI: `workflow import <FILE.yaml>` bulk-imports a `DisciplineArea → Topic → Content → Concept` hierarchy (`[--discipline-area CODE] [--dry-run] [--json]`). Canonical verb since Wave 3; `workflow topic import` kept as a **deprecation alias** (notice → stderr, stdout JSON contract unchanged). Engine + DTOs live in `src/workflow/importer/` (`engine.py`, `types.py`, `formatters.py`, `cli.py`); the old `workflow.topic.{bulk_import,import_types,import_formatters}` modules are thin re-export shims. Exit codes 0/1/2/3 and the `--json` shape are pinned by [ADR-0018](docs/ADR/0018-bulk-import-contract.md). Concept global-skip: a `code` reused under a different content is silently skipped, not re-linked. Shared lookups `get_topic_by_serial` / `get_content_by_name` (in topic/content services) back both the add-guards and the importer.
- Content bib-link CLI: `workflow content link-bib | bib-links | unlink-bib` (v1.13.0). Links `BibContent` rows (`bib_entry_id`, `content_id`) with locus columns (chapter, section, pages, exercise range). Reuses `_resolve_bib_entry` single-query lookup — soon to move to a dedicated `workflow.bibliography.service` module.
- Validation CLI: `workflow validate notes [--strict-main-topic] [--strict-concepts]` (ITEP-0009 + ITEP-0012, Implemented). Resolves frontmatter `main_topic` against `MainTopic`, enforces `discipline_area` consistency, and optionally validates `concepts:` slugs against the Concept table. `workflow validate exercises` also lints `\si{}`/`\SI{}{}` unit macros against SetUnits.sty declarations ∪ siunitx builtins (warn-only with difflib suggestion, never flips exit code; parser `workflow.latex.units.load_declared_units`, regex `\DeclareSIUnit\<name>{...}` control-sequence form only).
- Disciplines + maturation CLI: `workflow db disciplines list [--json]`, `workflow project propose-maturation [--json] [--area DDTTAA]` (ADR ITEP-0009). Bloom enums: `workflow item taxonomy --levels|--domains [--json]` (ADR ITEP-0006).
- DB migration CLI: `workflow db migrate-xdg [--dry-run/--no-dry-run] [--yes]` — relocate a legacy `~/01-U/workflow/` DB into the XDG data dir (`~/.local/share/workflow/`); dry-run on by default (requires `--no-dry-run` to write); backs up DB before moving; idempotent (no-ops if already in XDG location); never runs automatically.
- Neovim plugin (v1.12.0): Topic + Content CLIs have pickers (`:WorkflowTopicPicker [discipline-area=CODE]`, `:WorkflowContentPicker [topic-id=N]`); Concept CLI has picker (`:WorkflowConceptPicker [main-topic=CODE]`); Graph CLI accessible via `:WorkflowGraphStats` / `:WorkflowGraphOrphans` (both accept filter flags); Lectures CLI accessible via `:WorkflowLectureScan` / `:WorkflowLectureLink`. All insert/display in scratch buffers or splits. See `nvim-plugin/doc/workflow.txt`. PRISMA accept-to-note (Wave C3): `:WorkflowPrismaAcceptToNote` prompts bibkey (single) or keyword-id (bulk), shells to `workflow prisma bib accept-to-note --json`, opens result in a vsplit.
- Shared `get_engine_from_ctx()` in `workflow.db.engine` for all Click commands
- Project types: `GeneralProject` and `LectureProject` (see `itep/models.py`)

### ADR Index

Architecture decisions in `docs/ADR/` (see [INDEX.md](docs/ADR/INDEX.md) for full cross-referenced index):

| ADR  | Title | Status |
|------|-------|--------|
| ITEP-0000 | ITeP project structure conventions | Accepted |
| ITEP-0001 | SQLAlchemy as persistence layer | Accepted |
| ITEP-0002 | Four-layer database schema | Accepted |
| ITEP-0003 | config.yaml as minimal DB pointer | Accepted |
| ITEP-0004 | Two project types: Lecture & General | Accepted |
| ITEP-0005 | Symlink-based shared resource distribution | Accepted |
| ITEP-0006 | Bloom taxonomy enums | Accepted |
| ITEP-0007 | CRUD manager abstraction | Accepted |
| ITEP-0008 | General project nomenclature (DDTTAA-YYPP-title) | Implemented |
| ITEP-0009 | Knowledge lifecycle and AI agent conventions | Implemented |
| ITEP-0010 | Schema versioning and forward-only migrations | Implemented |
| ITEP-0011 | Vault unification: notes layer → GlobalBase; per-project `.md` under `<vault_root>` | Implemented |
| ITEP-0012 | Concept ORM surface: CLI + validator + note↔concept DB linking | Implemented (amended 2026-05-27 for Topic re-root) |
| STY-0000..0011 | LaTeX style file ADRs (12 total) | Accepted |
| 0001 | Zettelkasten note semantic layer | Accepted |
| 0002 | Markdown as canonical knowledge layer | Accepted |
| 0003 | Hybrid DB (global + local) | Accepted |
| 0004 | SQLAlchemy 2.0 as single ORM | Accepted |
| 0005 | Exercise DSL extends existing macros | Accepted |
| 0006 | TikZ standalone asset pipeline | Accepted |
| 0007 | Shared DB module with repository API | Accepted |
| 0008 | XDG directory layout | Accepted (amended 2026-06-05) |
| 0009 | Exercise module boundary + shared LaTeX parsing | Accepted |
| 0010 | Exercise persistence: file as truth, DB as index | Accepted |
| 0011 | LaTeX parser: brace-counting extractor | Accepted |
| 0012 | Moodle XML export with LaTeX normalization | Accepted |
| 0013 | Codebase consolidation: sessions, decoupling, CLI split | Accepted |
| 0014 | Zettelkasten implementation: macros, note model, workspace init | Accepted |
| 0015 | Zettelkasten daily work: notes, demos, images, exercises | Accepted |
| LZK-0000 | LaTeXZettel 7-layer engine architecture | Accepted |
| LZK-0001 | JSONL/NDJSON RPC server for Neovim (24 routes) | Accepted |
| LZK-0002 | Pandoc pipeline: Markdown ↔ LaTeX with wiki-links | Accepted |
| LZK-0003 | Note reference system: IDs, regex, cross-refs | Accepted |
| LZK-0004 | Dependency injection and Peewee → SQLAlchemy shim | Implemented |
| PRISMA-0000 | Systematic review architecture (Django, dual-DB) | Accepted |
| PRISMA-0001 | Dual-database router: MariaDB + shared SQLite | Accepted |
| PRISMA-0002 | Bibliography import pipeline (BibTeX → structured data) | Accepted |
| PRISMA-0003 | Article screening and review workflow | Accepted |
| PRISMA-0004 | Data model: 30+ Django models for systematic review | Accepted |
| PRISMA-0005 | PRISMA CLI: SQLAlchemy migration and unified workflow.db | Accepted |
| 0016 | Evaluation CLI: Template, Item, and Course Management | Accepted |
| 0017 | `graph neighbors --json` output contract | Accepted |
| 0018 | Bulk-import contract (`workflow import`; `topic import` alias) | Accepted (amended 2026-06-03) |
| 0019 | Bibliography dialect: biblatex-native model + bibtex compat layer | Accepted |
| 0020 | Bibliography module boundary: foundation layer + 0/1/2+ lookup contract | Accepted |

## Build & CI

- Build backend: `uv_build`
- Python: `>=3.12`
- CI: GitHub Actions on push/PR to `master`, tests on Python 3.12/3.13/3.14
- Linter: flake8 (max line length 127, max complexity 10)
- Test framework: pytest (pythonpath configured to `"."`)
- Dependencies: sqlalchemy, click, pyyaml, appdirs, bibtexparser

## Testing conventions

- **All test-generated output files MUST be written under `tests/outputs/`.** Any artifact a test produces (exported `.tex`/`.bib`/Moodle XML, generated fixtures, snapshots, DOT/TikZ dumps) goes there — never the cwd, repo root, or an ad-hoc path. Prefer a `tests/outputs/` subdir per area. Database/`WORKFLOW_DATA_DIR` isolation is unchanged: the autouse fixture in `tests/conftest.py` still routes the live DB to a per-test tmp dir.

## `tasks/` directory conventions

Working docs live in `tasks/<kind>/`. **Every new doc MUST be started from its template in `data/templates/`** — copy the template, fill the placeholders, do not invent ad-hoc structure. Filenames are date-prefixed: `YYYY-MM-DD-<slug>[-<kind>].md`.

| Subdir | Purpose | Template |
|--------|---------|----------|
| `tasks/requests/` | Feature/bug/gap requests (GitHub-issue style, with lifecycle frontmatter) | `data/templates/request-template.md` |
| `tasks/plans/` | Implementation plans (TDD phases, verified anchors, locked decisions) | `data/templates/plan-template.md` |
| `tasks/audit/` | Audits verifying an artifact against code truth-sources (verdict tables) | `data/templates/audit-template.md` |
| `tasks/security/` | Security reviews (findings by OWASP severity, fixes) | `data/templates/security-template.md` |

Other `tasks/` paths: `tasks/roadmap/` (dated roadmap snapshots), plus the root logs `tasks/todo.md` and `tasks/lessons.md` (no template — append-only). Gap-mining input uses `data/templates/raw-gap-log.md`.

You have context-mode MCP tools available. These rules are NOT optional — they protect your context window from flooding. A single unrouted command can dump 56 KB into context and waste the entire session.

## BLOCKED commands — do NOT attempt these

### curl / wget — BLOCKED
Any Bash command containing `curl` or `wget` is intercepted and replaced with an error message. Do NOT retry.
Instead use:
- `ctx_fetch_and_index(url, source)` to fetch and index web pages
- `ctx_execute(language: "javascript", code: "const r = await fetch(...)")` to run HTTP calls in sandbox

### Inline HTTP — BLOCKED
Any Bash command containing `fetch('http`, `requests.get(`, `requests.post(`, `http.get(`, or `http.request(` is intercepted and replaced with an error message. Do NOT retry with Bash.
Instead use:
- `ctx_execute(language, code)` to run HTTP calls in sandbox — only stdout enters context

### WebFetch — BLOCKED
WebFetch calls are denied entirely. The URL is extracted and you are told to use `ctx_fetch_and_index` instead.
Instead use:
- `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` to query the indexed content

## REDIRECTED tools — use sandbox equivalents

### Bash (>20 lines output)
Bash is ONLY for: `git`, `mkdir`, `rm`, `mv`, `cd`, `ls`, `npm install`, `pip install`, and other short-output commands.
For everything else, use:
- `ctx_batch_execute(commands, queries)` — run multiple commands + search in ONE call
- `ctx_execute(language: "shell", code: "...")` — run in sandbox, only stdout enters context

### Read (for analysis)
If you are reading a file to **Edit** it → Read is correct (Edit needs content in context).
If you are reading to **analyze, explore, or summarize** → use `ctx_execute_file(path, language, code)` instead. Only your printed summary enters context. The raw file content stays in the sandbox.

### Grep (large results)
Grep results can flood context. Use `ctx_execute(language: "shell", code: "grep ...")` to run searches in sandbox. Only your printed summary enters context.

## Tool selection hierarchy

1. **GATHER**: `ctx_batch_execute(commands, queries)` — Primary tool. Runs all commands, auto-indexes output, returns search results. ONE call replaces 30+ individual calls.
2. **FOLLOW-UP**: `ctx_search(queries: ["q1", "q2", ...])` — Query indexed content. Pass ALL questions as array in ONE call.
3. **PROCESSING**: `ctx_execute(language, code)` | `ctx_execute_file(path, language, code)` — Sandbox execution. Only stdout enters context.
4. **WEB**: `ctx_fetch_and_index(url, source)` then `ctx_search(queries)` — Fetch, chunk, index, query. Raw HTML never enters context.
5. **INDEX**: `ctx_index(content, source)` — Store content in FTS5 knowledge base for later search.

## Subagent routing

When spawning subagents (Agent/Task tool), the routing block is automatically injected into their prompt. Bash-type subagents are upgraded to general-purpose so they have access to MCP tools. You do NOT need to manually instruct subagents about context-mode.

## Output constraints

- Keep responses under 500 words.
- Write artifacts (code, configs, PRDs) to FILES — never return them as inline text. Return only: file path + 1-line description.
- When indexing content, use descriptive source labels so others can `ctx_search(source: "label")` later.

## ctx commands

| Command | Action |
|---------|--------|
| `ctx stats` | Call the `ctx_stats` MCP tool and display the full output verbatim |
| `ctx doctor` | Call the `ctx_doctor` MCP tool, run the returned shell command, display as checklist |
| `ctx upgrade` | Call the `ctx_upgrade` MCP tool, run the returned shell command, display as checklist |
