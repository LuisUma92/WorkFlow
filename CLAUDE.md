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
| `workflow` | `main:cli`          | Main CLI (tikz, validate, exercise)  |
| `inittex`  | `itep.create:cli`   | Initialize LaTeX project structure   |
| `relink`   | `itep.links:cli`    | Recreate symlinks from config.yaml   |
| `cleta`    | `lectkit.cleta:cli` | Clean TeX auxiliary files            |
| `crete`    | `lectkit.crete:cli` | Create exercise files (DEPRECATED)   |
| `nofi`     | `lectkit.nofi:cli`  | Split marked notes into LaTeX files  |

## Architecture

### Module Structure

- **`src/workflow/db/`** — Unified database module (SQLAlchemy 2.0). Owns ALL ORM models and repository interfaces. Two-base architecture: `GlobalBase` (`~/.local/share/workflow/workflow.db`) and `LocalBase` (`<project>/slipbox.db`). See ADR-0003, ADR-0004, ADR-0007.

- **`src/workflow/tikz/`** — TikZ standalone asset pipeline. Compiles `.tex` diagrams to PDF/SVG with incremental builds. See ADR-0006.

- **`src/workflow/validation/`** — Frontmatter validation. Validates YAML frontmatter in `.md` notes and commented YAML in `.tex` exercises.

- **`src/workflow/latex/`** — Shared LaTeX parsing utilities. `braces.py` (brace-counting macro extraction), `comments.py` (commented YAML), `normalize.py` (custom macro expansion for Moodle export). See ADR-0011, ADR-0012.

- **`src/workflow/exercise/`** — Exercise bank management. `parser.py` (parse .tex → domain objects), `moodle.py` (Moodle XML export), `generator.py` (placeholder file creation), `selector.py` (exercise selection by taxonomy), `exam_builder.py` (exam assembly), `cli.py` (8 CLI commands). See ADR-0009, ADR-0010, ADR-0011, ADR-0012.

- **`src/workflow/lecture/`** — Lectures integration. `scanner.py` (discover .tex files, register as notes), `note_splitter.py` (split notes at `%>` markers), `linker.py` (extract `\cite`/`\ref`/`\label`, update Link/Citation tables), `eval_builder.py` (bridge EvaluationTemplate to exercise bank), `cli.py` (4 CLI commands: scan, split, link, build-eval).

- **`src/itep/`** — Init TeX Project (ITeP). Project scaffolding and management. Uses `workflow.db` for models. Config is `config.yaml` per project (pointer to DB record, see ADR ITEP/0003).

- **`src/latexzettel/`** — Zettelkasten engine. CLI + JSONL/NDJSON RPC server + Neovim Lua client. Uses `workflow.db.models.notes` via compatibility shim in `infra/orm.py`.

- **`src/lectkit/`** — Lecture utilities: `cleta` (cleanup), `nofi` (note splitting), `crete` (exercise generation — **deprecated**, use `workflow exercise create`).

- **`src/PRISMAreview/`** — Django 5.0 PRISMA systematic review web app. Backed by MariaDB. `shared_db/router.py` enables reading from shared `workflow.db`.

- **`src/appfunc/`** — Shared utilities: input validation (`FieldSpec` in `iofunc.py`), enum selection, menus.

- **`shared/sty/`** — 17 LaTeX style files (SetCommands, PartialCommands, SetExercises, VectorPGF, etc.). Symlinked into projects from `~/.local/share/workflow/sty/`.

- **`shared/templates/`** — LaTeX templates for notes, exercises, lectures.

### Key Patterns

- All CLIs use **Click** with groups and commands
- **SQLAlchemy 2.0** with `Mapped[]` annotations is the single ORM (ADR-0004)
- Data access goes through **repository Protocol interfaces** (`workflow.db.repos.protocols`)
- **Hybrid DB**: global for reference data, local per project (ADR-0003)
- XDG layout: config in `~/.config/workflow/`, data in `~/.local/share/workflow/` (ADR-0008)
- Exercise macros: extend existing `\question`, `\qpart`, `\pts` — never replace (ADR-0005)
- `.tex` files are **truth source** for exercise content; DB stores metadata index only (ADR-0010)
- Exercise CLI: `workflow exercise parse|list|sync|gc|export-moodle|create|create-range|build-exam`
- LaTeX normalization: custom macros expanded to standard LaTeX before Moodle export (ADR-0012)
- Lectures CLI: `workflow lecture scan|split|link|build-eval` (Phase 5)
- Project types: `GeneralProject` and `LectureProject` (see `itep/models.py`)

### ADR Index

Architecture decisions in `docs/ADR/Zettelkasten/`:

| ADR  | Title | Status |
|------|-------|--------|
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

## Build & CI

- Build backend: `uv_build`
- Python: `>=3.10`
- CI: GitHub Actions on push/PR to `master`, tests on Python 3.9/3.10/3.11
- Linter: flake8 (max line length 127, max complexity 10)
- Test framework: pytest (pythonpath configured to `"."`)
- Dependencies: sqlalchemy, click, pyyaml, appdirs, bibtexparser, peewee (legacy, being removed)
