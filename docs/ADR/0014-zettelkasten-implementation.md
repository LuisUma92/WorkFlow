---
adr: 0014
title: "Zettelkasten Implementation: Macros, Note Model, Workspace Init, Markdown Pipeline"
status: Proposed
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
---

## Context

ADR-0001 (Zettelkasten semantic layer) and ADR-0002 (Markdown as canonical knowledge) were accepted on 2026-03-24 but never implemented. A gap analysis reveals:

1. **`\zlink{id}` macro**: Required by ADR-0001 but does not exist in any `.sty` file. The closest equivalents are `\excref` and `\exhyperref` in `texnote.cls`, which serve a similar role but are not aligned with the Zettelkasten ID system.

2. **`\begin{zettelnote}` environment**: Required by ADR-0001 but not defined. Notes are currently plain `.tex` files with no semantic wrapper.

3. **Markdown as source of truth**: ADR-0002 declares Markdown canonical, but LaTeX is still the de facto primary format. `inittex` creates only `tex/` directories — no `notes/md/` directories. The `sync_md()` API exists in `latexzettel/api/markdown.py` but uses Peewee ORM calls (32 occurrences) against SQLAlchemy models — it crashes at runtime.

4. **Directory structure**: GeneralProject tree templates create `tex/` subdirectories only. There is no standard location for Markdown notes, literature notes, or reading annotations.

5. **Literature notes**: No workflow exists for taking notes on paper readings (PRISMAreview or otherwise). The bibliography system (`bib_entry`) exists but has no connection to a note-taking flow.

6. **Workspace initialization**: `inittex` creates individual projects but there is no command to initialize the full workspace (`~/Documents/01-U/`) with shared infrastructure (workflow.db, sty symlinks, vault directories).

### User's vision

Each ITeP MainTopic directory (10MC-ClassicalMechanics, 40EM-Electromagnetism, etc.) functions as both:
- A **GeneralProject** (LaTeX output: papers, summaries, compilations)
- A **Zettelkasten vault** (Markdown notes: permanent, literature, fleeting)

The notes feed the LaTeX outputs. Lectures draw from the same knowledge base. Exercises connect to topics. The knowledge graph ties everything together.

---

## Decision Drivers

- **ADR compliance**: Implement what 0001 and 0002 promised
- **Obsidian compatibility**: Notes must work in Obsidian without modification
- **Existing infrastructure**: Reuse workflow.db, workflow.lecture.scanner/linker, workflow.graph
- **Minimal disruption**: Don't break existing LaTeX workflows — add Markdown alongside
- **Literature workflow**: Physics research requires systematic reading notes

---

## Decision

Implement the Zettelkasten system in 5 sub-phases. Each is independently deployable.

### Phase 7a: LaTeX Macros for Zettelkasten

Create `shared/sty/SetZettelkasten.sty` with:

```latex
% \zlink{id} — semantic cross-reference to another note
% Renders as hyperlink with auto-resolved title
\newcommand{\zlink}[1]{\hyperlink{zk:#1}{\textit{→ #1}}}

% \begin{zettelnote}{id}{Title} — semantic note wrapper
% Sets hypertarget for \zlink, displays title, optional margin note
\newenvironment{zettelnote}[2]{%
  \hypertarget{zk:#1}{}%
  \paragraph{#2}\label{zk:#1}%
  \marginpar{\tiny\texttt{#1}}%
}{%
  \par\medskip
}

% \zlabel{id} — lightweight anchor (for notes that don't need the full environment)
\newcommand{\zlabel}[1]{\hypertarget{zk:#1}{}\label{zk:#1}}
```

This fulfills ADR-0001's requirement for `\zlink` and a dedicated note macro.

### Phase 7b: Extended Note Model

Extend `workflow.db.models.notes.Note` (LocalBase):

```python
class Note(LocalBase):
    # Existing fields
    id, filename, reference, last_build_date_html, last_build_date_pdf, last_edit_date, created

    # New fields
    title: Mapped[str | None]           # Human-readable title from frontmatter
    note_type: Mapped[str | None]       # "permanent" | "literature" | "fleeting"
    source_format: Mapped[str | None]   # "md" | "tex"
    zettel_id: Mapped[str | None]       # Stable Zettelkasten ID (e.g., "20260326-gauss-law")
```

Add `NoteRepo.find_by_zettel_id()` and `NoteRepo.find_by_type()` to protocols.

### Phase 7c: Workspace Init Command

Add `workflow init` command that scaffolds the complete workspace:

```bash
workflow init ~/Documents/01-U/
```

Creates:

```
~/Documents/01-U/
  .workflow/                          # Workspace marker
    config.yaml                       # Workspace config (pointers to DBs)
  00AA-Lectures/                      # Lecture instances (existing)
  00BB-Library/                       # Bibliography (existing)
  00EE-ExamplesExercises/             # Exercise bank (existing)
  00II-ImagesFigures/                 # Shared images (existing)
  00ZZ-Vault/                         # Global Zettelkasten vault
    inbox/                            # Fleeting notes landing zone
    templates/                        # Note templates (.md)
      permanent.md
      literature.md
      fleeting.md
  10MC-ClassicalMechanics/            # GeneralProject + per-topic vault
    config.yaml
    slipbox.db
    notes/                            # Markdown notes (Obsidian vault)
      .obsidian/                      # Obsidian config (gitignored)
    tex/                              # LaTeX output (existing)
    bib/ img/                         # Resources (existing)
  40EM-Electromagnetism/              # Same structure
    config.yaml
    slipbox.db
    notes/
    tex/
  ...
```

**Key decisions**:
- Each GeneralProject gets its own `notes/` directory = Obsidian vault
- `00ZZ-Vault/inbox/` is a global inbox for fleeting notes not yet assigned to a topic
- `slipbox.db` per project stores that project's notes, links, citations
- The init command is **idempotent** — safe to run on existing workspace, only creates missing pieces
- Does NOT move or rename existing directories

### Phase 7d: Markdown Note Pipeline

Create `workflow.notes` module (replaces broken `latexzettel.api`):

```python
# workflow/notes/scanner.py
def scan_markdown_notes(notes_dir: Path, session: Session) -> ScanResult:
    """Discover .md files, parse frontmatter, register in slipbox.db."""

# workflow/notes/linker.py
def link_markdown_notes(notes_dir: Path, session: Session) -> LinkResult:
    """Parse wiki-links [[id]] and \cite{}, update Link/Citation tables."""

# workflow/notes/converter.py
def md_to_tex(md_path: Path, output_dir: Path) -> Path:
    """Convert Markdown note to LaTeX via Pandoc. Returns output path."""

def tex_to_md(tex_path: Path, output_dir: Path) -> Path:
    """Convert LaTeX note to Markdown. Returns output path."""
```

CLI commands:

```bash
workflow notes scan notes/           # Register .md notes in slipbox.db
workflow notes link notes/           # Build wiki-link graph
workflow notes convert note.md -o tex/  # Markdown → LaTeX via Pandoc
workflow notes new "Gauss's Law" --type permanent --project 10MC
```

### Phase 7e: Literature Notes Workflow

Literature notes connect PRISMAreview readings to the Zettelkasten:

```bash
# Create a literature note from a bibliography entry
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
tags: [textbook, physics, mechanics]
---

## Key ideas

## Chapter notes

## Questions raised

## Connections
- [[20260326-gauss-law]] — Gauss's law derivation from ch. 24
```

The note links to permanent notes via wiki-links, and the `bibkey` field connects to `bib_entry` in the global DB. When scanned, the Citation table is populated automatically.

---

## Architectural Rules

### MUST

- Knowledge notes **MUST** be authored in Markdown (`.md`) with YAML frontmatter — fulfilling ADR-0002.
- Each note **MUST** have a `zettel_id` in frontmatter — fulfilling ADR-0001.
- Inter-note references in Markdown **MUST** use wiki-links `[[zettel_id]]`.
- Inter-note references in LaTeX **MUST** use `\zlink{zettel_id}`.
- LaTeX output **MUST** be treated as derived artifact, not source of truth.
- `workflow init` **MUST** be idempotent — safe to run on existing workspace.

### SHOULD

- Each GeneralProject **SHOULD** have a `notes/` directory serving as its Obsidian vault.
- Literature notes **SHOULD** reference their `bibkey` in frontmatter.
- The Pandoc pipeline **SHOULD** convert `[[id]]` wiki-links to `\zlink{id}` in LaTeX output.
- Notes **SHOULD** be assigned to a MainTopic project, not floating.

### MUST NOT

- `workflow notes` module **MUST NOT** use Peewee ORM calls — all DB access via SQLAlchemy sessions.
- `workflow init` **MUST NOT** move, rename, or delete existing directories.
- Literature notes **MUST NOT** duplicate bibliography metadata — they reference `bib_entry` via `bibkey`.

---

## Implementation Notes

### Dependency graph

```
7a (macros)     ──┐
                  ├──→ 7c (init command) ──→ 7e (literature notes)
7b (note model) ──┤
                  └──→ 7d (markdown pipeline)
```

7a and 7b are independent. 7c needs 7b (creates slipbox.db with new fields). 7d needs 7b (registers notes with extended model). 7e needs 7c+7d.

### What to reuse

| Existing module | Reuse in Phase 7 |
|-----------------|-----------------|
| `workflow.lecture.scanner` | Pattern for `workflow.notes.scanner` |
| `workflow.lecture.linker` | Pattern for `workflow.notes.linker` (add wiki-link parsing) |
| `workflow.validation.schemas` | `NoteFrontmatter` already validated |
| `workflow.validation.parsers` | `parse_md_frontmatter` already works |
| `workflow.graph.collectors` | `collect_notes` already reads Note/Link/Citation |
| `latexzettel/pandoc/` | Pandoc filter + template (reuse as-is) |

### What NOT to reuse

| Module | Why not |
|--------|---------|
| `latexzettel/api/*.py` | 32 Peewee ORM calls — completely broken against SQLAlchemy |
| `latexzettel/cli/main.py` | Tied to broken API layer |
| `latexzettel/infra/db.py` | Overly complex for what `workflow.db.engine` already provides |

The `latexzettel` package should be treated as legacy. Its Pandoc infrastructure (`pandoc/`) is reusable, but its API and CLI layers need replacement by `workflow.notes`.

---

## Consequences

### Benefits

- ADR-0001 and ADR-0002 finally implemented after 7 phases of other work
- Obsidian-compatible note workflow alongside LaTeX compilation
- Literature notes connect readings to the knowledge graph
- Single `workflow init` command sets up entire workspace
- Knowledge graph (Phase 6) becomes useful — notes are the primary graph nodes

### Costs

- New module (`workflow.notes`) — ~500 lines estimated
- `SetZettelkasten.sty` — new .sty file to maintain
- Pandoc becomes a runtime dependency for conversion
- `latexzettel` API layer effectively deprecated (replaced by `workflow.notes`)

### What stays unchanged

- All 18 existing CLI commands continue working
- Exercise workflow unchanged
- Lecture workflow unchanged (but benefits from richer note graph)
- Graph module unchanged (but sees more data from Markdown notes)
- `inittex` still works for creating individual projects

---

## Alternatives Considered

### Alternative A: Fix latexzettel API instead of replacing

Rewrite the 32 Peewee calls in `latexzettel/api/` to use SQLAlchemy.

**Rejected**: The latexzettel API layer has deep coupling to Peewee patterns (`.get()`, `.DoesNotExist`, `.select().where()`). Rewriting 5 files to SQLAlchemy is more work than creating a clean `workflow.notes` module that follows the established patterns from `workflow.exercise` and `workflow.lecture`.

### Alternative B: Single global vault instead of per-project

Put all notes in `00ZZ-Vault/` instead of per-project `notes/` directories.

**Rejected**: This breaks the project-as-context model. A physics topic (10MC) should have its notes co-located. The `00ZZ-Vault/inbox/` serves as a triage zone for unassigned notes.

### Alternative C: Skip Markdown, keep LaTeX-only notes

Continue using LaTeX as the note format, add `\zettelnote` and `\zlink` only.

**Rejected**: Violates ADR-0002 which was accepted. Markdown provides superior editing experience, Obsidian compatibility, and separation between content and rendering.

---

## Compatibility / Migration

- **Non-breaking**: All existing projects continue working without changes
- **Incremental**: `workflow init` adds `notes/` directories to existing projects without moving files
- **Migration path**: Existing `.tex` notes can be converted to `.md` via `workflow notes convert --reverse`
- **latexzettel**: Continues to work for its JSONL server (Neovim client) but API layer is deprecated

---

## Status

**Proposed** — awaiting review

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-26 | Initial ADR |
