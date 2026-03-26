---
adr: 0014
title: "Zettelkasten Implementation: Macros, Note Model, Workspace Init"
status: Accepted
date: 2026-03-26
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - knowledge-management
  - zettelkasten
  - markdown
  - latex
decision_scope: system
supersedes: null
superseded_by: null
related_adrs:
  - "0001"
  - "0002"
  - "0003"
  - "0007"
  - "0008"
  - "ITEP-0000"
  - "ITEP-0004"
  - "LZK-0000"
  - "LZK-0001"
  - "LZK-0002"
  - "LZK-0003"
  - "LZK-0004"
  - "PRISMA-0000"
  - "PRISMA-0001"
---

## Context

ADR-0001 (Zettelkasten semantic layer) and ADR-0002 (Markdown as canonical knowledge) were accepted but not fully implemented. A gap analysis against the LZK-* ADRs reveals:

### What exists and works (per LZK-0000..0004)

- **`\excref{id}`** macro in `texnote.cls` (LZK-0003) — serves the exact purpose ADR-0001 described for `\zlink`
- **Pandoc pipeline** (LZK-0002) — `preprocess.py` converts `[[wiki-links]]` → `\excref{id}`, `filter.lua` handles theorems
- **10+ regex patterns** (LZK-0003) — centralized in `infra/regexes.py` for `\excref`, `\cite`, `\label`, `\ref`, `[[wiki-links]]`
- **JSONL RPC server** (LZK-0001) — 24 routes for Neovim integration
- **7-layer architecture** (LZK-0000) — clean separation CLI → Server → API → Domain → Infra
- **DB shim** (LZK-0004) — `infra/orm.py` re-exports SQLAlchemy models, `infra/db.py` provides sessions

### What is broken

- **35 Peewee-pattern calls** in 5 API files (`api/notes.py`, `api/sync.py`, `api/markdown.py`, `api/analysis.py`, `api/workflows.py`) use `.get()`, `.select()`, `.create()`, `.DoesNotExist` — methods that don't exist on SQLAlchemy models. The `db_session()` context manager in `infra/db.py` IS correctly implemented for SQLAlchemy; the API code never adopted it.

### What is missing

- **`notes/` directories** in GeneralProject tree template — `inittex` creates only `tex/`
- **Note model extensions** — `Note` lacks `title`, `note_type`, `source_format`, `zettel_id`
- **Workspace init command** — no way to scaffold the full `~/Documents/01-U/` workspace
- **Literature notes workflow** — no connection between PRISMAreview readings and the Zettelkasten
- **`\zlink` macro** — ADR-0001 requires it; `\excref` exists but under a different name

---

## Decision Drivers

- **Rehabilitate, don't replace**: LaTeXZettel has 33 working files, a clean architecture (LZK-0000), and 24 RPC routes (LZK-0001). Replacing it would waste proven infrastructure.
- **35 Peewee calls is a small fix**: Porting `.get()` → `session.query().filter_by().first()` across 5 files is ~170 lines of changes, not a rewrite.
- **`\excref` already IS `\zlink`**: Adding `\let\zlink\excref` in a .sty file satisfies ADR-0001 without breaking anything.
- **Existing scanners generalize**: `workflow.lecture.scanner` and `workflow.lecture.linker` patterns can handle Markdown notes with minor extensions.

---

## Decision

Implement the Zettelkasten system in 5 sub-phases. Strategy: **rehabilitate latexzettel, don't replace it.**

### Phase 7a: LaTeX Macro Alias + Note Environment

Create `shared/latex/sty/SetZettelkasten.sty`:

```latex
% \zlink{id} — alias for \excref (satisfies ADR-0001)
\let\zlink\excref

% \zlabel{id} — lightweight anchor
\newcommand{\zlabel}[1]{\hypertarget{zk:#1}{}\label{zk:#1}}

% \begin{zettelnote}{id}{Title} — semantic note wrapper (ADR-0001)
\newenvironment{zettelnote}[2]{%
  \hypertarget{zk:#1}{}%
  \paragraph{#2}\label{zk:#1}%
  \marginpar{\tiny\texttt{#1}}%
}{\par\medskip}
```

**Key decision**: `\zlink` is defined as `\let\zlink\excref`, not a new implementation. This means:
- All existing `\excref` references continue working
- The Pandoc preprocessor (LZK-0002) already converts `[[id]]` → `\excref{id}`, which now equals `\zlink{id}`
- The regex library (LZK-0003) already extracts `\excref` — no new patterns needed
- New code can use either name; they are identical

### Phase 7b: Extended Note Model

Add fields to `workflow.db.models.notes.Note` (LocalBase):

```python
# New columns (nullable for backward compatibility)
title: Mapped[str | None] = mapped_column(String, nullable=True)
note_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # "permanent" | "literature" | "fleeting"
source_format: Mapped[str | None] = mapped_column(String(5), nullable=True)
    # "md" | "tex"
zettel_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    # Stable Zettelkasten ID (e.g., "20260326-gauss-law")
```

Extend `NoteRepo` protocol:
```python
def find_by_zettel_id(self, zettel_id: str) -> Note | None: ...
def find_by_type(self, note_type: str) -> list[Note]: ...
```

### Phase 7c: LaTeXZettel API Rehabilitation

Port 35 Peewee-pattern calls in 5 files to use `db_session()` from `infra/db.py`:

```python
# BEFORE (Peewee pattern — broken):
note = db.Note.get(db.Note.reference == reference)

# AFTER (SQLAlchemy via db_session):
with db_session(db) as session:
    note = session.query(db.Note).filter_by(reference=reference).first()
```

Files to port:
| File | Peewee calls | Lines changed |
|------|-------------|---------------|
| `api/notes.py` | 8 | ~30 |
| `api/sync.py` | 10 | ~40 |
| `api/markdown.py` | 7 | ~30 |
| `api/analysis.py` | 5 | ~20 |
| `api/workflows.py` | 5 | ~20 |

After porting, the full latexzettel system (CLI, server, API) becomes functional against SQLAlchemy. This restores:
- `sync_md()` — Markdown note sync
- `tex_to_md()` — LaTeX → Markdown conversion
- `force_synchronize()` — full DB resync
- All 24 RPC server routes

### Phase 7d: Workspace Init + CLI Bridge

**`workflow init` command** scaffolds the workspace:

```bash
workflow init ~/Documents/01-U/
```

Creates:
```
~/Documents/01-U/
  .workflow/config.yaml              # Workspace marker
  00ZZ-Vault/                        # Global triage zone
    inbox/                           # Fleeting notes landing
    templates/                       # Note templates (.md)
  10MC-ClassicalMechanics/
    notes/                           # Markdown notes (Obsidian vault)
    slipbox.db                       # Per-project note DB
  40EM-Electromagnetism/
    notes/
    slipbox.db
  ...
```

**`workflow notes` CLI bridge** — thin wrapper delegating to rehabilitated latexzettel API:

```python
# workflow/notes/cli.py (~150 lines)
@click.group()
def notes(): ...

@notes.command()
def scan(path, project_root):
    """Scan .md + .tex notes and register in slipbox.db."""
    # Delegates to latexzettel.api.sync.force_synchronize()

@notes.command()
def link(path, project_root):
    """Extract references and update Link/Citation tables."""
    # Reuses workflow.lecture.linker patterns + latexzettel.infra.regexes

@notes.command()
def convert(source, output_dir, reverse):
    """Convert Markdown ↔ LaTeX via Pandoc."""
    # Delegates to latexzettel.api.markdown.sync_md() / tex_to_md()

@notes.command()
def new(title, note_type, project):
    """Create a new note from template."""
    # Delegates to latexzettel.api.notes.create_note()
```

### Phase 7e: Literature Notes

```bash
workflow notes new-lit serway2019 --project 10MC
```

Creates `10MC-ClassicalMechanics/notes/lit-serway2019.md`:

```markdown
---
id: lit-serway2019
title: "Physics for Scientists and Engineers — Serway"
type: literature
bibkey: serway2019
created: 2026-03-26
tags: [textbook, physics]
---

## Key ideas

## Chapter notes

## Connections
```

The `bibkey` field connects to `bib_entry.bibkey` in the global DB. PRISMAreview already reads `bib_entry` via the SharedDbRouter (PRISMA-0001). When scanned, the Citation table is populated via the `bibkey` reference — no new PRISMAreview code needed.

---

## Architectural Rules

### MUST

- `\zlink` **MUST** be defined as `\let\zlink\excref` — alias, not replacement.
- Knowledge notes **MUST** be authored in Markdown with YAML frontmatter (ADR-0002).
- `workflow init` **MUST** be idempotent — safe on existing workspace.
- LaTeXZettel API rehabilitation **MUST** use `db_session()` from `infra/db.py` — no new session patterns.
- Literature notes **MUST** reference `bibkey` in frontmatter for bibliography linkage.

### SHOULD

- Each GeneralProject **SHOULD** have a `notes/` directory as its Obsidian vault.
- The Pandoc pipeline (LZK-0002) **SHOULD** convert `[[id]]` → `\zlink{id}` (which equals `\excref{id}`).
- `workflow.notes` CLI **SHOULD** delegate to latexzettel API, not reimplement logic.
- `workflow.lecture.linker` **SHOULD** be extended to parse wiki-links from .md files.

### MUST NOT

- ADR-0014 **MUST NOT** duplicate infrastructure that exists in latexzettel (LZK-0000..0004).
- `workflow.notes` **MUST NOT** bypass the latexzettel API layer — it is a CLI bridge, not a replacement.
- `workflow init` **MUST NOT** move, rename, or delete existing directories.

---

## Implementation Notes

### Dependency graph

```
7a (macros)     ──┐
                  ├──→ 7d (init + CLI bridge) ──→ 7e (literature notes)
7b (note model) ──┤
                  └──→ 7c (API rehabilitation)
```

7a and 7b are independent. 7c needs 7b (extended Note model). 7d needs 7b+7c (working API + new fields). 7e needs 7d (workspace + note creation).

### What to reuse (not rebuild)

| Existing | Reuse for |
|----------|-----------|
| `\excref{id}` (texnote.cls) | `\zlink` via alias |
| `infra/regexes.py` (10+ patterns) | Reference extraction in notes |
| `pandoc/preprocess.py` | Wiki-link → LaTeX conversion |
| `pandoc/filter.lua` | Theorem environment handling |
| `infra/db.py:db_session()` | Session management for rehabilitated API |
| `workflow.lecture.scanner` | Pattern for note scanning |
| `workflow.lecture.linker` | Pattern for reference linking |
| `workflow.validation.schemas.NoteFrontmatter` | Frontmatter validation |
| PRISMA SharedDbRouter (PRISMA-0001) | Literature note → bib_entry linkage |

### Effort estimate

| Phase | New files | Modified files | Lines |
|-------|-----------|---------------|-------|
| 7a | 1 (.sty) | 0 | ~20 |
| 7b | 0 | 2 (notes.py, protocols.py) | ~30 |
| 7c | 0 | 5 (latexzettel API) | ~170 |
| 7d | 3 (cli.py, init.py, templates) | 2 (main.py, models.py) | ~250 |
| 7e | 1 (lit template) | 1 (cli.py) | ~50 |
| **Total** | **5** | **10** | **~520** |

---

## Consequences

### Benefits

- ADR-0001 and ADR-0002 fulfilled without rebuilding latexzettel
- 24 RPC server routes restored (Neovim integration works again)
- Obsidian-compatible note workflow per project
- Literature notes connect readings to knowledge graph
- ~520 lines vs ~800+ for a replacement approach

### Costs

- LaTeXZettel API rehabilitation requires understanding 5 API files
- Two CLI systems coexist temporarily (latexzettel CLI + workflow notes CLI)
- `\zlink` and `\excref` are aliases — users see two names for the same thing

### What stays unchanged

- All 18 existing CLI commands
- All 24 JSONL RPC server routes (once API is rehabilitated)
- Pandoc pipeline (filter.lua, preprocess.py, template.tex)
- Exercise, lecture, graph, tikz, validation modules

---

## Alternatives Considered

### Alternative A: Replace latexzettel with workflow.notes (original ADR-0014 v1)

Create a new `workflow.notes` module with its own scanner, linker, converter.

**Rejected (rev 2)**: Duplicates LZK-0002 (Pandoc pipeline), LZK-0003 (regex library), and LZK-0000 (7-layer architecture). 33 working files would be abandoned. The 35 broken Peewee calls are a smaller fix (~170 lines) than building a replacement module (~800+ lines).

### Alternative B: Define `\zlink` as a new macro independent of `\excref`

**Rejected**: `\excref` already does exactly what `\zlink` needs. The regex library extracts it. The Pandoc preprocessor converts wiki-links to it. Creating a parallel macro would split the reference ecosystem.

### Alternative C: Skip workspace init, let users create directories manually

**Rejected**: The workspace structure (`notes/`, `slipbox.db`, symlinks) has enough pieces that manual setup is error-prone. An idempotent `workflow init` is worth the ~100 lines.

---

## Compatibility / Migration

- **Non-breaking**: All existing projects continue working
- **Incremental**: `workflow init` adds `notes/` to existing projects without moving files
- **Backward compatible**: `\excref` continues to work; `\zlink` is an alias
- **LaTeXZettel**: Server and CLI restored to full function after API rehabilitation

---

## Status

**Accepted** — revision 2 (incorporates LZK-* ADR analysis, changes strategy from replacement to rehabilitation)

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR (v1) — proposed workflow.notes replacement |
| 2026-03-26 | Revision 2 — changed to rehabilitation strategy after LZK-* ADR review |
