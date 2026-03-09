# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WorkFlow is a Python CLI toolkit for managing LaTeX projects, focused on academic writing (thesis, lectures, exercises). It provides several independent CLI tools built with Click.

## Commands

```bash
# Install (editable)
pip install -e .
# or with uv
uv sync

# Run all tests
pytest

# Run a single test file
pytest tests/test_links_cli.py

# Lint (matches CI)
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

## CLI Entry Points

Defined in `pyproject.toml` under `[project.scripts]`:

| Command    | Module              | Purpose                              |
|------------|---------------------|--------------------------------------|
| `workflow` | `main:cli`          | Main interactive menu                |
| `inittex`  | `itep.create:cli`   | Initialize LaTeX project structure   |
| `relink`   | `itep.links:cli`    | Recreate symlinks from config.yaml   |
| `cleta`    | `lectkit.cleta:cli` | Clean TeX auxiliary files            |
| `crete`    | `lectkit.crete:cli` | Create exercise files from book refs |
| `nofi`     | `lectkit.nofi:cli`  | Split marked notes into LaTeX files  |

## Architecture

### Module Structure

- **`src/itep/`** — Init TeX Project (ITeP). Core module for creating and managing LaTeX project structures. Uses dataclasses in `structure.py` for project models (`ProjectStructure`, `MetaData`, `Admin`, `Topic`, `Book`). Config is stored as `config.yaml` per project. `database.py` has Django ORM models for persistence.

- **`src/lectkit/`** — Lecture utilities. Three standalone scripts: `cleta` (cleanup), `nofi` (notes-to-files using `%>path` / `%>END` markers), `crete` (exercise generation from JSON book metadata).

- **`src/prismar/`** — PRISMA systematic review tools. **Status: on pause** (being developed in another repo).

- **`src/appfunc/`** — Shared utilities: input validation with regex (`FieldSpec` pattern in `iofunc.py`), enum selection (`options.py`), menu interface (`mainmenu.py`).

### Key Patterns

- All CLIs use **Click** with groups and commands
- Project config stored as **YAML** (`config.yaml`), read/written via `itep/utils.py`
- User-level config goes to `~/.config/` via **appdirs**
- Models use Python **dataclasses** with field metadata for validation specs
- Project types: `GeneralProject` and `LectureProject` (see `itep/models.py`)
- Institutions enum: UCR, UFide, UCIMED (Costa Rican universities)

## Build & CI

- Build backend: `uv_build`
- Python: `>=3.10`
- CI: GitHub Actions on push/PR to `master`, tests on Python 3.9/3.10/3.11
- Linter: flake8 (max line length 127, max complexity 10)
- Test framework: pytest (pythonpath configured to `"."`)
