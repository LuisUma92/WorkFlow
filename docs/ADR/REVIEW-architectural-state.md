# Architectural Review: Current State of the Zettelkasten/Knowledge System

**Date**: 2026-03-24
**Reviewer**: Claude Code (code review session)
**Purpose**: Document the inhomogeneous current state so the architect agent can load it for decision-making.

---

## 1. Components Under Review

### 1.1 `src/latexzettel/` — LaTeX Zettelkasten System (NEW, untracked)

**Architecture**: Layered, well-structured:
- `domain/` — models, types, errors, templates (no I/O)
- `config/` — defaults + settings assembly (frozen dataclasses)
- `infra/` — ORM (Peewee/SQLite), filesystem, processes, regexes
- `api/` — business logic (notes, render, sync, export, analysis, markdown, workflows)
- `cli/` — Click commands delegating to api/
- `server/` — JSONL/NDJSON RPC server (stdin/stdout) for Neovim integration
- `lua/` — Neovim plugin client (client.lua, ui.lua, init.lua)
- `pandoc/` — filter, template, defaults for md<->tex conversion
- `defaults/` — template files, slipbox.db, make4ht config

**Maturity**: MVP-complete. All layers wired. Server protocol is versioned with handshake, cancel support, and clean error handling.

### 1.2 `src/PRISMAreview/` — PRISMA Systematic Review (NEW, untracked)

**Architecture**: Django 5.0 + MariaDB monolith with:
- `prismadb/` — core models (Bib_entries, Author, Abstract, PRISMA2020Checklist, etc.)
- `addbib/` — BibTeX import via WebSocket (Django Channels)
- `review/` — systematic review interface
- `inspectdatabase/` — DB browser
- `home/` — landing page

**Maturity**: Working prototype. Multiple migrations applied. Has real .bib data files.

### 1.3 `src/prismar/` — Old PRISMA scripts (DELETED in working tree)

8 Python files deleted. These were standalone scripts (bib2yaml, mergebib, nori, etc.) being replaced by PRISMAreview.

### 1.4 ADRs (NEW, untracked)

- **ADR-0001**: Zettelkasten-based LaTeX system with TikZ visualization. Macro-based semantic layer (`\zettelnote`, `\zlink`). Status: Proposed.
- **ADR-0002**: Unified Knowledge System. Extends ADR-0001 with: Markdown as canonical knowledge layer, TikZ as external asset model, Exercise DSL in LaTeX, CLI orchestration, Moodle XML export. Status: Proposed.

---

## 2. Structural Inhomogeneities Found

### 2.1 CRITICAL: Duplicated Code Between server/main.py and server/routers.py

`server/main.py` (873 lines) contains a **complete duplicate** of all handlers that also exist in `server/routers.py` (539 lines). Both files:
- Define `ServerContext` (duplicated dataclass)
- Import the same API functions
- Implement identical handlers (handle_notes_new, handle_render_note, etc.)
- Define identical `ROUTES` dictionaries

**Impact**: Any handler change must be made in two places. Bug risk is high.
**Recommendation**: `main.py` should import handlers and ROUTES from `routers.py`, not redefine them.

### 2.2 CRITICAL: Duplicated `RenderFormat` Enum

- `domain/models.py:17` defines `RenderFormat(str, Enum)` with PDF/HTML
- `domain/types.py:52` defines an **identical** `RenderFormat(str, Enum)` with PDF/HTML

**Impact**: Import confusion. Some modules may import from one, some from the other.
**Recommendation**: Keep only one (in `types.py` since it's the canonical types module). Remove from `models.py`.

### 2.3 HIGH: Domain Layer Depends on Infrastructure

`domain/types.py:31` imports `from latexzettel.infra.orm import Note`. This violates hexagonal architecture — the domain layer must not depend on infrastructure.

**Impact**: Circular dependency risk. Domain is coupled to Peewee ORM.
**Recommendation**: The `DbModule` protocol in types.py should reference an abstract `Note` protocol, not the concrete ORM model.

### 2.4 HIGH: `_require_not_cancelled` vs `require_not_cancelled` in main.py

`handle_cancel` in `main.py:270` calls `_require_not_cancelled(token)` (private, undefined in main.py). All other handlers call `require_not_cancelled(token)` (imported from routers). This will crash at runtime if cancel is invoked.

### 2.5 HIGH: `JsonScalar` Used But Not Imported in main.py

`main.py:103` uses `JsonScalar` in type hints but only imports `JsonObject` and `ProtocolError` from protocols. `JsonScalar` is undefined in main.py scope.

### 2.6 MEDIUM: Debug Print Left in CLI Entry Point

`cli/main.py:79` has `print("hola")` — debug artifact in the main entry point.

### 2.7 MEDIUM: `__pycache__` Directories in Source Tree

Multiple `__pycache__/` directories are present in the untracked `src/latexzettel/` tree. These should be gitignored before committing.

### 2.8 MEDIUM: `contentReference[oaicite:N]` Artifacts

Several files contain LLM-generated artifacts like `:contentReference[oaicite:0]{index=0}` in docstrings/comments:
- `infra/db.py` (lines 8, 20, 98)
- `infra/orm.py` (lines 10, 22, 36)
- `infra/regexes.py` (lines 8-13)
- `infra/processes.py` (lines 6-9, 131, 152, 174, 199)
- `domain/types.py` (lines 14, 129)

**Impact**: Confusing to readers; not valid references.
**Recommendation**: Remove all `contentReference` strings.

### 2.9 MEDIUM: PRISMAreview Has Hardcoded DB Credentials

`src/PRISMAreview/pprsite/settings.py` contains hardcoded MariaDB credentials (per its CLAUDE.md). This is acceptable for dev-only but should be flagged if committing.

### 2.10 MEDIUM: Two Completely Separate DB Systems

- latexzettel uses **Peewee + SQLite** (slipbox.db)
- PRISMAreview uses **Django ORM + MariaDB**

ADR-0002 envisions a unified knowledge system, but the current state has two independent data stores with no shared schema or bridge.

### 2.11 LOW: Typo in `infra/plataform.py` Filename

Should be `platform.py`. Spanish "plataforma" leaked into the English filename.

### 2.12 LOW: `Url_list.__str__` Uses Wrong f-string

`PRISMAreview/prismadb/models.py:235`: `"\n{self.url_string}"` is missing the `f` prefix. Will print literal `{self.url_string}`.

### 2.13 LOW: `Reviewed.reatrive_rationale` Typo

Should be `retrieve_rationale`. This is a DB column name so changing it requires a migration.

---

## 3. Architectural Gaps vs ADR Vision

| ADR-0002 Requirement | Current State | Gap |
|---|---|---|
| Markdown as canonical knowledge layer | latexzettel supports md notes, sync_md, tex_to_md | Partially implemented; no frontmatter schema validation |
| TikZ as external asset (standalone .tex -> PDF/SVG) | No standalone TikZ compilation pipeline exists | **Not implemented** |
| Exercise DSL (\qstem, \qoption, etc.) | No exercise parsing or DSL macros exist | **Not implemented** |
| Moodle XML export | Not implemented | **Not implemented** |
| CLI orchestration (validate, parse, export-moodle, build-pdf, index) | CLI has notes/render/sync/export/analysis | Partially; no validate, no exercise parse, no moodle export |
| Centralized bibliography DB | PRISMAreview has rich bib models in MariaDB; latexzettel has Citation in SQLite | **Split across two systems** |
| Neovim plugin integration | Lua client + JSONL server working | Implemented |
| Integration with ~/Documents/01-U/00-Fisica/00AA-Lectures | Not started | **Not implemented** |
| Bidirectional linking | Wiki-link regex parsing exists; DB has Link model | Partially implemented |
| Metadata validation | No schema validation for YAML frontmatter or commented YAML in .tex | **Not implemented** |

---

## 4. Security Issues

| Severity | Location | Issue |
|---|---|---|
| MEDIUM | PRISMAreview/pprsite/settings.py | Hardcoded DB credentials (MariaDB user/password) |
| LOW | latexzettel/infra/processes.py | subprocess.run with user-provided filenames — currently safe (no shell=True) but should validate filenames |
| LOW | latexzettel/server/main.py | Debug mode controlled by env var LATEXZETTEL_SERVER_DEBUG exposes stack traces — acceptable for dev |

---

## 5. Recommendations for Architect Session

1. **Resolve the main.py/routers.py duplication first** — it's the highest-risk structural issue
2. **Fix the domain -> infra dependency** (types.py importing orm.py) before it calcifies
3. **Decide on bibliography unification strategy**: bridge PRISMAreview's MariaDB bib data into latexzettel's SQLite, or create a shared abstraction layer
4. **Define the TikZ asset pipeline** before implementing exercises — diagrams are a dependency for both exercises and notes
5. **Design the Exercise DSL macros** (\qstem, \qoption, etc.) alongside the CLI parser, not separately
6. **Plan the Lectures integration** (~/Documents/01-U/00-Fisica/00AA-Lectures) — define what data moves where
7. **Add .gitignore rules** for __pycache__, slipbox.db, and .pyc files before first commit
8. **Clean up all contentReference artifacts** before committing
