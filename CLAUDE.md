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

- **`src/workflow/tikz/`** — TikZ standalone asset pipeline. Compiles `.tex` diagrams to PDF/SVG with incremental builds. See ADR-0006.

- **`src/workflow/validation/`** — Frontmatter validation. Validates YAML frontmatter in `.md` notes and commented YAML in `.tex` exercises.

- **`src/workflow/latex/`** — Shared LaTeX parsing utilities. `braces.py` (brace-counting macro extraction), `comments.py` (commented YAML), `normalize.py` (custom macro expansion for Moodle export). See ADR-0011, ADR-0012.

- **`src/workflow/exercise/`** — Exercise bank management. `parser.py` (parse .tex → domain objects), `moodle.py` (Moodle XML export), `generator.py` (placeholder file creation), `selector.py` (exercise selection by taxonomy), `exam_builder.py` (exam assembly), `cli.py` (8 CLI commands). See ADR-0009, ADR-0010, ADR-0011, ADR-0012.

- **`src/workflow/lecture/`** — Lectures integration. `scanner.py` (discover .tex files, register as notes), `note_splitter.py` (split notes at `%>` markers), `linker.py` (extract `\cite`/`\ref`/`\label`, update Link/Citation tables), `eval_builder.py` (bridge EvaluationTemplate to exercise bank), `cli.py` (4 CLI commands: scan, split, link, build-eval).

- **`src/workflow/graph/`** — Knowledge graph analysis and export. `domain.py` (GraphNode, GraphEdge, KnowledgeGraph), `collectors.py` (query global+local DBs), `analysis.py` (orphans, hubs, components, neighbors, stats), `dot_export.py` (Graphviz DOT), `tikz_export.py` (TikZ with spring layout), `clustering.py` (optional networkx communities), `cli.py` (6 CLI commands: orphans, stats, export-dot, export-tikz, clusters, neighbors).

- **`src/workflow/evaluation/`** — Evaluation CLI. `cli.py` (3 Click groups: evaluations, item, course), `service.py` (business logic, validation), `formatters.py` (table + JSON output). Commands: evaluations list|show|add|edit, item list|add, course list|add. Neovim Telescope pickers in nvim-plugin. See ADR-0016.

- **`src/workflow/vault/`** — Vault unification (ITEP-0011). `unify.py` reads legacy per-project `slipbox.db` via raw `sqlite3`, snapshots a backup, detects reference/zettel_id collisions, id-remaps notes/labels/citations/tags/links into GlobalBase, moves `.md` files into `<vault_root>/notes/<type>/`, writes `.vault_pointer` marker. `cli.py`: 3 commands (info, validate, unify). Vault root via `WORKFLOW_VAULT_ROOT` env (default `~/Documents/01-U/0000AA-Vault`).

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
- XDG layout: config in `~/.config/workflow/`, data in `~/.local/share/workflow/` (ADR-0008)
- Exercise macros: extend existing `\question`, `\qpart`, `\pts` — never replace (ADR-0005)
- `.tex` files are **truth source** for exercise content; DB stores metadata index only (ADR-0010)
- Exercise CLI: `workflow exercise parse|list|sync|gc|export-moodle|create|create-range|build-exam`
- LaTeX normalization: custom macros expanded to standard LaTeX before Moodle export (ADR-0012)
- Lectures CLI: `workflow lectures scan|split|link|build-eval`
- Graph CLI: `workflow graph orphans|stats|export-dot|export-tikz|clusters|neighbors`
- Evaluation CLI: `workflow evaluations list|show|add|edit`, `workflow item list|add`, `workflow course list|add` (ADR-0016)
- PRISMA CLI: `workflow prisma bib list|show`, `workflow prisma keyword list`, `workflow prisma review list`, `workflow prisma checklist show`, `workflow prisma rationale add|list`, `workflow prisma tag add|list` (ADR PRISMA-0005)
- Vault CLI: `workflow vault info|validate|unify` (ITEP-0011). Migrates per-project `slipbox.db` notes into the global vault; idempotent via `.vault_pointer` marker.
- Validation CLI: `workflow validate notes [--strict-main-topic]` (Phase B / ITEP-0009 Part II) — resolves frontmatter `main_topic` against `MainTopic` and enforces `discipline_area` consistency.
- Disciplines + maturation CLI: `workflow db disciplines list [--json]`, `workflow project propose-maturation [--json] [--area DDTTAA]` (ADR ITEP-0009). Bloom enums: `workflow item taxonomy --levels|--domains [--json]` (ADR ITEP-0006).
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
| ITEP-0009 | Knowledge lifecycle and AI agent conventions | Implemented (partial) |
| ITEP-0010 | Schema versioning and forward-only migrations | Implemented |
| ITEP-0011 | Vault unification: notes layer → GlobalBase; per-project `.md` under `<vault_root>` | Accepted (P0–P3 shipped) |
| STY-0000..0011 | LaTeX style file ADRs (12 total) | Accepted |
| 0001 | Zettelkasten note semantic layer | Accepted |
| 0002 | Markdown as canonical knowledge layer | Accepted |
| 0003 | Hybrid DB (global + local) | Accepted |
| 0004 | SQLAlchemy 2.0 as single ORM | Accepted |
| 0005 | Exercise DSL extends existing macros | Accepted |
| 0006 | TikZ standalone asset pipeline | Accepted |
| 0007 | Shared DB module with repository API | Accepted |
| 0008 | XDG directory layout | Accepted |
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
| LZK-0004 | Dependency injection and Peewee → SQLAlchemy shim | Accepted |
| PRISMA-0000 | Systematic review architecture (Django, dual-DB) | Accepted |
| PRISMA-0001 | Dual-database router: MariaDB + shared SQLite | Accepted |
| PRISMA-0002 | Bibliography import pipeline (BibTeX → structured data) | Accepted |
| PRISMA-0003 | Article screening and review workflow | Accepted |
| PRISMA-0004 | Data model: 30+ Django models for systematic review | Accepted |
| PRISMA-0005 | PRISMA CLI: SQLAlchemy migration and unified workflow.db | Accepted |
| 0016 | Evaluation CLI: Template, Item, and Course Management | Accepted |

## Build & CI

- Build backend: `uv_build`
- Python: `>=3.12`
- CI: GitHub Actions on push/PR to `master`, tests on Python 3.12/3.13/3.14
- Linter: flake8 (max line length 127, max complexity 10)
- Test framework: pytest (pythonpath configured to `"."`)
- Dependencies: sqlalchemy, click, pyyaml, appdirs, bibtexparser, peewee (legacy, being removed)

# context-mode — MANDATORY routing rules

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
