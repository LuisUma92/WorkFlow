---
adr: LZK-0000
title: "LaTeXZettel Engine Architecture: 7-Layer Note Management System"
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - zettelkasten
  - latexzettel
  - notes
decision_scope: module
supersedes: null
superseded_by: null
related_adrs:
  - "0001"
  - "0002"
  - "0003"
  - "0004"
---

## Context

The Zettelkasten method requires a note management engine that can:

1. Create and organize atomic notes with unique references
2. Track cross-references between notes (`\excref`, `\cite`, `\label`)
3. Render notes to PDF and HTML
4. Synchronize between Markdown and LaTeX formats
5. Expose functionality to editors (Neovim) via RPC
6. Manage note databases per project (slipbox.db)

A clean architecture separates these concerns to enable both CLI usage and editor integration without coupling.

---

## Decision

**LaTeXZettel is a 7-layer engine** with strict dependency rules: each layer depends only on layers below it.

### Layer Structure

```
┌─────────────────────────────────────────┐
│  CLI (cli/main.py)                      │  ← Click commands, user interaction
├─────────────────────────────────────────┤
│  Server (server/main.py, routers.py)    │  ← JSONL/NDJSON RPC for Neovim
├─────────────────────────────────────────┤
│  API (api/*.py)                         │  ← Business logic, 7 modules
├─────────────────────────────────────────┤
│  Domain (domain/types.py, models.py)    │  ← Protocols, contracts, types
├─────────────────────────────────────────┤
│  Infrastructure (infra/*.py)            │  ← DB, filesystem, processes, regex
├─────────────────────────────────────────┤
│  Config (config/settings.py)            │  ← Layered configuration
├─────────────────────────────────────────┤
│  Utilities (util/*.py)                  │  ← Text, I/O, time, templates
└─────────────────────────────────────────┘
```

### Components

| Layer | Files | Responsibility |
|-------|-------|----------------|
| **CLI** | `cli/main.py` | 5 Click command groups: notes, render, sync, export, analysis |
| **Server** | `server/main.py`, `server/routers.py` | JSONL RPC server with 24 routes, cancel token support |
| **API** | `api/notes.py`, `api/render.py`, `api/sync.py`, `api/markdown.py`, `api/export.py`, `api/analysis.py`, `api/workflows.py` | Pure business logic, accepts `db` module as parameter |
| **Domain** | `domain/types.py`, `domain/models.py`, `domain/errors.py`, `domain/templates.py` | Protocol-based contracts (`DbModule`, `FileFinder`, `NoteRecord`) |
| **Infra** | `infra/orm.py`, `infra/db.py`, `infra/regexes.py`, `infra/fs.py`, `infra/platform.py`, `infra/processes.py` | Database access, file operations, regex patterns, LaTeX compilation |
| **Config** | `config/settings.py`, `config/defaults.py` | Layered config: defaults → project config → user overrides |
| **Util** | `util/text.py`, `util/io.py`, `util/time.py`, `util/fs.py`, `util/templates.py` | Pure utility functions |

### Dependency Injection

All API functions accept a `db` module parameter instead of importing ORM directly:

```python
def create_note(db, reference: str, filename: str, ...) -> NoteRecord:
    """Create a new note. `db` provides session and model access."""
```

This enables:
- Testing with mock databases
- Swapping ORM implementations (Peewee → SQLAlchemy via shim)
- Library reuse outside CLI/Server context

### Templates & Defaults

```
defaults/
  template/
    texnote.cls        # LaTeX document class for notes
    documents.tex      # Main document template
    preamble.tex       # Standard preamble
    preamble_html.tex  # HTML-specific preamble swap
  config/
    latexzettel.yaml   # Default configuration
  projects/
    *.yaml             # Per-project config templates
```

---

## Architectural Rules

### MUST

- API functions **MUST** accept `db` as a parameter — never import ORM directly.
- CLI commands **MUST NOT** contain business logic — delegate to API layer.
- Server handlers **MUST NOT** import Click — enable headless operation.
- Each layer **MUST** depend only on layers below it in the stack.

### SHOULD

- Domain types **SHOULD** use `@runtime_checkable` Protocol for contracts.
- Error types **SHOULD** extend a common base (`ZettelError`).
- Configuration **SHOULD** support layered overrides (defaults → project → user).

### MUST NOT

- Infrastructure **MUST NOT** import from API or CLI layers.
- Utilities **MUST NOT** import from any other latexzettel layer.

---

## Consequences

### Benefits

- Editor-agnostic: CLI and Neovim use the same API
- Testable: dependency injection enables mock testing
- Extensible: new API modules can be added without touching other layers
- ORM-agnostic: shim pattern survived Peewee → SQLAlchemy migration

### Costs

- 33 files across 7 layers is a complex package for a personal tool
- The `db` parameter threading adds verbosity
- Two config systems coexist (latexzettel YAML + workflow XDG)

---

## Status

**Accepted** — documents existing architecture

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR |
