# WorkFlow

[![Python package](https://github.com/LuisUma92/WorkFlow/actions/workflows/python-package.yml/badge.svg)](https://github.com/LuisUma92/WorkFlow/actions/workflows/python-package.yml)

Python CLI toolkit for managing LaTeX projects and a unified Zettelkasten knowledge system for academic writing (thesis, lectures, exercises). Integrates Markdown note-taking, LaTeX rendering, TikZ diagrams, exercise management, Moodle export, and bibliography management across multiple institutions (UCR, UFide, UCIMED).

**Wiki**: [Getting Started](docs/wiki/Getting-Started.md) | [Zettelkasten](docs/wiki/Zettelkasten-Notes.md) | [Exercises](docs/wiki/Exercise-Workflow.md) | [Lectures](docs/wiki/Lectures-Workflow.md) | [Graph](docs/wiki/Knowledge-Graph.md) | [Macros](docs/wiki/LaTeX-Macros.md) | [Architecture](docs/wiki/Architecture.md)

## Installation

```bash
# Recommended: install as a uv tool (editable, CLI available globally)
uv tool install -e .

# Or as a project virtual environment
uv sync

# Or with pip (editable)
pip install -e .
```

### Dependencies

`appdirs`, `bibtexparser`, `click`, `pyyaml`, `sqlalchemy`

Optional: `networkx` (for knowledge graph clustering)

Python >= 3.12

## Overview

WorkFlow organizes academic work around six pillars:

1. **Zettelkasten** (`workflow notes`) — Markdown notes (Obsidian-compatible), workspace initialization, wiki-links
2. **LaTeX Projects** (`inittex`, `relink`) — Scaffolding and directory management for courses and theses
3. **Exercise Bank** (`workflow exercise`) — Parsing, indexing, generation, selection, and export of exercises
4. **Course Management** (`workflow lectures`) — File scanning, cross-linking, evaluation building
5. **Knowledge Graph** (`workflow graph`) — Analysis of connections between notes, exercises, bibliography, and courses
6. **TikZ Pipeline** (`workflow tikz`) — Incremental compilation of standalone diagrams to PDF/SVG

## Architecture

### Hybrid Database

WorkFlow uses a two-database SQLite architecture:

- **Global** (`~/.local/share/workflow/workflow.db`) — Reference data: institutions, courses, books, exercises, evaluations, bibliography
- **Local** (`<project>/slipbox.db`) — Notes, links, tags, and citations per project

SQLAlchemy 2.0 with `Mapped[]` is the single ORM. Data access goes through Protocol interfaces (`workflow.db.repos.protocols`).

### Key Principles

- **File as source of truth**: `.tex` files contain exercise and note content. The DB stores only metadata and indexes (ADR-0010)
- **Markdown as canonical layer**: Notes are written in Markdown with YAML frontmatter; LaTeX is a derived format (ADR-0002)
- **Extend, never replace**: Exercise macros (`\question`, `\qpart`, `\pts`) extend existing ones in `shared/latex/sty/` (ADR-0005). `\zlink` is an alias for `\excref` (ADR-0014)
- **LaTeX normalization**: Custom macros are expanded to standard LaTeX before Moodle export (ADR-0012)
- **XDG layout**: Configuration in `~/.config/workflow/`, data in `~/.local/share/workflow/` (ADR-0008)
- **Immutability**: All domain types use `@dataclass(frozen=True)` with `tuple` instead of `list`

## CLI Commands

### Direct Entry Points

| Command    | Module              | Description                                                        |
| ---------- | ------------------- | ------------------------------------------------------------------ |
| `workflow` | `main:cli`          | Main CLI (notes, exercise, lectures, graph, tikz, validate, import, concept, evaluations, prisma, vault) |
| `inittex`  | `itep.create:cli`   | Create or clone a LaTeX project                                    |
| `relink`   | `itep.links:cli`    | Recreate symlinks from the database                                |
| `cleta`    | `lectkit.cleta:cli` | Clean TeX auxiliary files                                          |

### workflow notes — Zettelkasten

Workspace initialization and Markdown note management (Obsidian-compatible).

```bash
# Initialize workspace with per-project note directories
workflow notes init ~/Documents/01-U/
```

Creates the structure:

```
~/Documents/01-U/
  .workflow/config.yaml              # Workspace marker
  00ZZ-Vault/                        # Global triage zone
    inbox/                           # Unassigned fleeting notes
    templates/                       # Templates: permanent.md, literature.md, fleeting.md
  10MC-ClassicalMechanics/
    notes/                           # Obsidian vault per project
    slipbox.db                       # Local note DB
  40EM-Electromagnetism/
    notes/
    slipbox.db
```

Each `MainTopic` (10MC, 40EM, 50MQ) functions as:

- A **GeneralProject** in ITeP (LaTeX output)
- A **Zettelkasten vault** (Markdown notes that feed the documents)

#### Zettelkasten Macros

| Macro                            | File                | Usage                                               |
| -------------------------------- | ------------------- | --------------------------------------------------- |
| `\zlink{id}`                     | SetZettelkasten.sty | Cross-reference between notes (alias of `\excref`)  |
| `\zlabel{id}`                    | SetZettelkasten.sty | Lightweight anchor for a reference point            |
| `\begin{zettelnote}{id}{Title}`  | SetZettelkasten.sty | Semantic note environment                           |

In Markdown, references use wiki-links: `[[20260326-gauss-law]]` or `[[id|text]]`.
The Pandoc pipeline converts `[[id]]` → `\zlink{id}` when compiling to LaTeX.

#### Note Types

| Type         | Usage                                    | Frontmatter format                       |
| ------------ | ---------------------------------------- | ---------------------------------------- |
| `permanent`  | Own ideas, consolidated concepts         | `type: permanent`                        |
| `literature` | Reading notes and article summaries      | `type: literature`, `bibkey: serway2019` |
| `fleeting`   | Quick ideas, pending processing          | `type: fleeting`                         |

### workflow exercise — Exercise Bank

Full exercise bank management: parsing `.tex` files, syncing with the DB, generating placeholders, selecting by taxonomy, building exams, and exporting to Moodle XML.

```bash
# Parse .tex files and display structure
workflow exercise parse path/to/exercises/

# List exercises in the DB with filters
workflow exercise list --status complete --difficulty medium --type multichoice

# Sync .tex files with the DB (create/update records)
workflow exercise sync path/to/exercises/

# Remove orphaned records (deleted files)
workflow exercise gc --yes

# Export to Moodle XML
workflow exercise export-moodle path/ --output quiz.xml --status complete --tag physics

# Create a placeholder exercise file
workflow exercise create my-exercise-001 -d path/output/ --type multichoice --tag physics

# Create multiple placeholders from a book range
workflow exercise create-range -d path/output/ --book serway --chapter 1 --first 1 --last 20

# Build an exam by selecting from the bank
workflow exercise build-exam -l "Usar-Aplicar" -n 5 -p 10 --title "Parcial 1" -o exam.tex
```

#### Typical Exercise Workflow

```
1. Create placeholders     →  workflow exercise create-range ...
2. Edit .tex files         →  (text editor / Neovim)
3. Sync with DB            →  workflow exercise sync path/
4. Check status            →  workflow exercise list --status complete
5. Build exam              →  workflow exercise build-exam ...
6. Export to Moodle        →  workflow exercise export-moodle path/ -o quiz.xml
```

#### Exercise File Format

Each exercise is a `.tex` file with YAML metadata in comments:

```latex
% ---
% id: phys-gauss-001
% type: multichoice
% difficulty: medium
% taxonomy_level: Usar-Aplicar
% taxonomy_domain: Procedimiento Mental
% tags: [physics, electrostatics]
% status: complete
% ---
\ifthenelse{\boolean{main}}{
  \exa[1]{5} % \cite{serway}
}{
}
\question{
  Given an electric field $\vec{E}$, calculate the flux.
  \begin{enumerate}[a)]
    \qpart{\rightoption \pts{5} Correct option}{
      Detailed solution here.
    }
    \qpart{\pts{5} Incorrect option}{
      Why this option is wrong.
    }
  \end{enumerate}
}{
  General exercise solution.
}
\qfeedback{Feedback shown after answering.}
```

#### Moodle XML Export

The export automatically normalizes custom macros:

- `\vc{E}` expands to `\vec{\mathbf{E}}`
- `\scrp{enc}` expands to `_{\mbox{\scriptsize{enc}}}`
- `$...$` converts to `\(...\)` (MathJax compatible)
- Colors (`\textcolor{red}{text}`) are stripped, preserving content
- Images are base64-encoded and embedded in the XML

This ensures the XML works on **any** Moodle instance, without relying on institutional MathJax configuration.

### workflow lectures — Course Management

Tools for integrating course projects with the note system and exercise bank.

```bash
# Scan course directory and register .tex files as notes
workflow lectures scan path/to/course/ --project-root .

# Split a notes file into sub-files (using %> markers)
workflow lectures split file.tex --output-dir tex/

# Scan references (\cite, \ref, \label) and update links in DB
workflow lectures link path/to/course/ --project-root .

# Build an evaluation from the exercise bank
workflow lectures build-eval -l "Usar-Aplicar" -n 5 -p 10 --title "Parcial 1" -o exam.tex --moodle
```

#### Typical Course Workflow

```
1. Create project          →  inittex (select lecture, institution, course)
2. Write notes/lectures    →  Edit .tex files in lect/tex/
3. Register notes          →  workflow lectures scan path/
4. Build links             →  workflow lectures link path/
5. Prepare evaluation      →  workflow lectures build-eval ...
6. Export to Moodle        →  workflow exercise export-moodle ...
```

### workflow graph — Knowledge Graph

Analyzes connections between all system elements: notes, exercises, bibliography, content, and courses. All commands accept `--main-topic CODE`, `--discipline-area CODE`, and `--topic NAME` filter flags.

```bash
# View graph statistics
workflow graph stats --project .

# Find orphan nodes (no connections)
workflow graph orphans --type note --project .

# Export to Graphviz DOT
workflow graph export-dot --project . -o graph.dot --highlight-orphans

# Export to TikZ for LaTeX
workflow graph export-tikz --project . -o graph.tex --standalone

# View thematic clusters (requires networkx)
workflow graph clusters --project .

# View neighbors of a specific node
workflow graph neighbors note:42 --depth 2 --project .
```

#### Graph Sources

The graph unifies data from both databases:

| Source                      | Node type          | Edge type                           |
| --------------------------- | ------------------ | ----------------------------------- |
| Notes (slipbox.db)          | `note`             | `link` (note→note via Label)        |
| Citations (slipbox.db)      | —                  | `citation` (note→bib_entry)         |
| Exercises (workflow.db)     | `exercise`         | `exercise_content`, `exercise_book` |
| Content (workflow.db)       | `content`, `topic` | `bib_content`, `course_content`     |
| Bibliography (workflow.db)  | `bib_entry`        | —                                   |
| Courses (workflow.db)       | `course`           | —                                   |

### workflow tikz — Diagram Pipeline

Incremental compilation of standalone TikZ diagrams to PDF and SVG.

```bash
# Compile all diagrams in assets/tikz/
workflow tikz build --assets-dir assets/tikz --output-dir assets/figures

# List TikZ sources
workflow tikz list --assets-dir assets/tikz

# Clean compiled artifacts
workflow tikz clean --output-dir assets/figures
```

### workflow validate — Metadata Validation

Validates YAML frontmatter structure in Markdown notes and LaTeX exercises.

```bash
# Validate notes (with optional strict checks)
workflow validate notes path/to/notes/
workflow validate notes path/to/notes/ --strict-main-topic --strict-concepts

# Validate exercises
workflow validate exercises path/to/exercises/
```

### workflow import — Bulk Hierarchy Import

Bulk-imports a `DisciplineArea → Topic → Content → Concept` hierarchy from a YAML file.

```bash
# Import hierarchy (dry run first)
workflow import file.yaml --dry-run
workflow import file.yaml --discipline-area CODE --json

# Note: `workflow topic import` is a deprecated alias (notice sent to stderr)
```

### workflow concept — Concept Taxonomy

Manages the concept taxonomy (code slugs, parent hierarchy, content affiliation).

```bash
workflow concept list
workflow concept show SLUG
workflow concept add --code SLUG --label TEXT --content-id INT --domain DOMAIN [--parent CODE]
workflow concept tree
workflow concept rename OLD NEW
workflow concept rm SLUG [--force]
```

Valid `--domain` values: `Información`, `Procedimiento Mental`, `Procedimiento Psicomotor`, `Metacognitivo`.

### workflow evaluations / item / course

Manage evaluation templates, items (with Bloom taxonomy), and courses.

```bash
workflow evaluations list
workflow evaluations show ID
workflow evaluations add --title TEXT --course-id INT
workflow evaluations edit ID

workflow item list
workflow item add --description TEXT --taxonomy-level LEVEL

workflow course list
workflow course add --name TEXT --institution-id INT
```

### workflow prisma — PRISMA Systematic Review

CLI for managing a systematic literature review workflow backed by the global database.

```bash
# Bibliography
workflow prisma bib list
workflow prisma bib show ID
workflow prisma bib import path/to/file.bib
workflow prisma bib import path/to/file.bib --recompute-bibkeys
workflow prisma bib export [--dialect biblatex|bibtex]
workflow prisma bib recompute-keys [--dry-run] [--all] [--yes]

# Keywords and review
workflow prisma keyword list
workflow prisma review list
workflow prisma checklist show
workflow prisma rationale add|list
workflow prisma tag add|list
```

The `bib export` command defaults to biblatex dialect; `--dialect bibtex` downgrades biblatex-only types and reverse-maps field names (ADR-0019). `recompute-keys` fills missing calculated bibkeys by default; `--all` normalizes every key after confirmation and backs up the DB first.

### workflow content — Content Bib-Links

Links bibliography entries to content nodes with locus information.

```bash
workflow content link-bib --content-id INT --bib-id INT [--chapter N] [--section N]
workflow content bib-links --content-id INT
workflow content unlink-bib --content-id INT --bib-id INT
```

### workflow vault — Vault Unification

Migrates per-project `slipbox.db` notes into the unified global vault.

```bash
workflow vault info
workflow vault validate
workflow vault unify
```

Vault root resolved from `WORKFLOW_VAULT_ROOT` env (default `~/Documents/01-U/0000AA-Vault`). Migration is idempotent via `.vault_pointer` marker.

## ITeP — Init TeX Project

Module for creating and managing LaTeX projects. Uses the global database as the source of truth for institutions, courses, topics, and evaluations.

```bash
# Create a new project (interactive)
inittex

# Clone an existing cycle
inittex --clone 42

# Recreate symlinks
relink
```

### Lecture Project Structure

```
UCR-FS0121/
  config.yaml          # DB pointer: {project_type: lecture, project_id: 42}
  admin/               # Administrative documents
  eval/                # Evaluations
    config/ img/ tex/
      001-Cinematica/
  lect/                # Lecture material
    bib/ config/ img/ svg/
    tex/
      001-Cinematica/
```

### General Project Structure

```
10MC-MecanicaClasica/
  config.yaml
  bib/ config/ img/ projects/
  tex/
    000-0-Glossaries/
    000-1-Summaries/
    001-Cinematica/
```

## Database Schema

### Global database (workflow.db) — 4 layers

**Layer 1 — Reference data:**

- `institution` — UCR (18 sem), UFide (15 cuatri), UCIMED (24 sem)
- `main_topic` — Main topics with Dewey code

**Layer 2 — Master entities:**

- `bib_entry`, `bib_author` — Full bibliography (40+ BibLaTeX fields)
- `topic`, `content`, `bib_content` — Academic content
- `concept` — Concept taxonomy (code slugs, domain, parent hierarchy)

**Layer 3 — Course templates:**

- `course`, `course_content` — Courses with weekly content
- `evaluation_template`, `item`, `evaluation_item` — Evaluations with Bloom taxonomy
- `exercise`, `exercise_option`, `exercise_concept` — Exercise bank metadata index

**Layer 4 — Instances:**

- `lecture_instance` — Course in a specific cycle/year
- `general_project` — Project associated with a main topic

### Local database (slipbox.db) — per project

- `note` — Registered file with unique reference
- `citation` — Bibliographic citations in notes
- `label`, `link` — Labels and links between notes
- `tag`, `note_tag` — M2M tag system

## LaTeX Macros

Exercise macros are defined in `shared/latex/sty/`:

| Macro                           | File                | Usage                           |
| ------------------------------- | ------------------- | ------------------------------- |
| `\question{stem}{solution}`     | SetCommands.sty     | Question with stem and solution |
| `\qpart{instruction}{solution}` | SetCommands.sty     | Question part                   |
| `\pts{n}`                       | PartialCommands.sty | Assigned points                 |
| `\rightoption`                  | PartialCommands.sty | Marks the correct option        |
| `\exa[ch]{num}`                 | SetCommands.sty     | Reference to a book exercise    |
| `\qfeedback{text}`              | SetExercises.sty    | Feedback (for Moodle)           |
| `\qdiagram{id}`                 | SetExercises.sty    | Reference to a TikZ diagram     |

### Normalization for Moodle

Custom macros are expanded to standard LaTeX before export:

| Original                 | Expanded                     |
| ------------------------ | ---------------------------- |
| `\vc{E}`                 | `\vec{\mathbf{E}}`           |
| `\scrp{enc}`             | `_{\mbox{\scriptsize{enc}}}` |
| `\ncm{2}{H}`             | `^{2}\text{H}`               |
| `\pts{5}`                | `(5 pts.)`                   |
| `\textcolor{red}{text}`  | `text`                       |
| `$x^2$`                  | `\(x^2\)`                    |

## Architecture Decisions (ADRs)

Documented in `docs/ADR/` (see [INDEX.md](docs/ADR/INDEX.md)):

| ADR               | Title                                                                  | Status      |
| ----------------- | ---------------------------------------------------------------------- | ----------- |
| 0001              | Zettelkasten note semantic layer                                        | Accepted    |
| 0002              | Markdown as canonical knowledge layer                                   | Accepted    |
| 0003              | Hybrid database (global + local)                                        | Accepted    |
| 0004              | SQLAlchemy 2.0 as single ORM                                            | Accepted    |
| 0005              | Exercise DSL extends existing macros                                    | Accepted    |
| 0006              | TikZ standalone asset pipeline                                          | Accepted    |
| 0007              | Shared DB module with repository API                                    | Accepted    |
| 0008              | XDG directory layout                                                    | Accepted    |
| 0009              | Exercise module boundary + shared LaTeX parsing                         | Accepted    |
| 0010              | Persistence: file as truth, DB as index                                 | Accepted    |
| 0011              | LaTeX parser: brace-counting extractor                                  | Accepted    |
| 0012              | Moodle XML export with LaTeX normalization                              | Accepted    |
| 0013              | Consolidation: sessions, decoupling, CLI split                          | Accepted    |
| 0014              | Zettelkasten implementation: macros, note model, workspace init         | Accepted    |
| 0015              | Zettelkasten daily work: notes, demos, images, exercises                | Accepted    |
| 0016              | Evaluation CLI: Template, Item, and Course Management                   | Accepted    |
| 0017              | `graph neighbors --json` output contract                                | Accepted    |
| 0018              | Bulk-import contract (`workflow import`; `topic import` alias)          | Accepted    |
| 0019              | Bibliography dialect: biblatex-native model + bibtex compat layer       | Accepted    |
| 0020              | Bibliography module boundary: foundation layer + lookup contract        | Accepted    |
| LZK-0000..0004    | LaTeXZettel engine (5 ADRs: architecture, RPC, Pandoc, refs, DI)        | Accepted    |
| PRISMA-0000..0004 | PRISMAreview (5 ADRs: architecture, router, import, screening, model)   | Accepted    |
| ITEP-0000..0012   | ITeP project structure, DB, config, types, symlinks, schema, vault, concepts | Accepted/Implemented |

## Module Structure

```
src/
  workflow/
    db/           # Unified database (SQLAlchemy 2.0, Protocol repos)
    notes/        # Zettelkasten: workspace init, note management
    exercise/     # Exercise bank (parser, moodle, generator, selector, exam_builder, service)
    lecture/      # Course integration (scanner, splitter, linker, eval_builder)
    graph/        # Knowledge graph (domain, collectors, analysis, DOT, TikZ, clustering)
    latex/        # Shared parsing (braces, comments, normalization)
    tikz/         # TikZ diagram pipeline
    validation/   # Frontmatter validation
    importer/     # Bulk hierarchy import engine (engine, types, formatters, cli)
    concept/      # Concept taxonomy CLI and service
    evaluation/   # Evaluation CLI (evaluations, item, course)
    prisma/       # PRISMA systematic review CLI
    vault/        # Vault unification (unify, paths, cli)
  itep/           # LaTeX project scaffolding
  latexzettel/    # Zettelkasten engine + JSONL/RPC server (24 routes) + Neovim client
  lectkit/        # Utilities (cleta)
  PRISMAreview/   # Django web app for PRISMA systematic review
  appfunc/        # Shared utilities
shared/
  latex/
    sty/          # 18 LaTeX style files (incl. SetZettelkasten.sty)
    cls/          # texnote.cls and preambles
    templates/    # Templates for notes, exercises, lectures
    pandoc/       # Pandoc pipeline: filter.lua, template.tex, preprocess.py
```

## Tests

```bash
# All tests
uv run pytest

# Single module
uv run pytest tests/workflow/exercise/
uv run pytest tests/workflow/graph/
uv run pytest tests/workflow/lecture/
uv run pytest tests/workflow/notes/

# With coverage
uv run pytest --cov=src/workflow --cov-report=term-missing
```

## Lint

```bash
# Critical errors (CI gate)
uv run flake8 src/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics

# Full (informational)
uv run flake8 src/ tests/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

## CI

GitHub Actions on push/PR to `master`. Tests on Python 3.12, 3.13, 3.14.
