---
adr: PRISMA-0005
title: "PRISMA CLI: SQLAlchemy Migration and Unified workflow.db"
status: Accepted
date: 2026-04-09
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - prisma
  - cli
  - database
  - migration
decision_scope: module
supersedes: "PRISMA-0001"
superseded_by: null
related_adrs:
  - "PRISMA-0000"
  - "PRISMA-0004"
  - "0004"
  - "0007"
  - "0016"
---

## Context

PRISMAreview was originally a standalone Django web application backed by MariaDB (ADR PRISMA-0000), with a dual-database router (ADR PRISMA-0001) that read bibliography data from the shared `workflow.db` SQLite while writing review data to MariaDB.

This architecture caused three problems:

1. **No CLI interface** — managing reviews required running the Django web server. No terminal or Neovim integration was possible.
2. **Dual-DB complexity** — the `SharedDbRouter` required Django Channels, MariaDB running, and careful routing rules. Bibliography data existed in both databases.
3. **ORM inconsistency** — PRISMAreview used Django ORM while the rest of WorkFlow uses SQLAlchemy 2.0 (ADR-0004). Bridging them required a lazy `django.setup()` call or a parallel model set.

A decision was required to eliminate the dual-DB split and provide CLI access to PRISMA review functionality.

---

## Decision Drivers

- Consistency with the unified ORM strategy (ADR-0004: SQLAlchemy 2.0 as single ORM)
- CLI pattern consistency with the evaluation CLI (ADR-0016)
- Eliminate MariaDB dependency for review management
- Enable Neovim Telescope picker integration via `--json` output
- Service layer pattern for testability

---

## Decision

### Consolidate all PRISMA data into `workflow.db` (SQLite)

All review-related models are migrated to SQLAlchemy 2.0 and stored in the global `workflow.db`. MariaDB is no longer required for review management. The Django web app remains for the import pipeline (BibTeX upload via WebSocket) but is no longer the primary interface.

### New SQLAlchemy Models

Added to `src/workflow/db/models/bibliography.py`:

```
ReviewRecord (review_record)
    ├── keyword_id → bib_keyword.id
    ├── bib_entry_id → bib_entry.id
    ├── retrieved: int | None  (default=None)
    ├── included: int | None   (1=included, 0=excluded, None=pending)
    ├── include_rationale: str | None
    ├── retrieve_rationale: str | None
    └── unique: (keyword_id, bib_entry_id)

RationaleOption (rationale_option)
    ├── rationale_argument: str | None
    └── timestamps

ReviewRationale (review_rationale)
    ├── review_record_id → review_record.id
    ├── rationale_option_id → rationale_option.id
    └── unique: (review_record_id, rationale_option_id)
```

Relationships added to existing models:

- `BibEntry.review_records` → `ReviewRecord` (back_populates)
- `BibKeyword.review_records` → `ReviewRecord` (back_populates)
- `ReviewRecord.rationale_links` → `ReviewRationale`

### CLI Structure

New Click group `prisma` with subgroups `bib`, `keyword`, `tag`, `rationale`, `review`, `checklist`:

```
# P0 — read-only
workflow prisma bib list [--year] [--type] [--json]
workflow prisma bib show <id> [--json]
workflow prisma keyword list [--json]
workflow prisma review list --keyword-id <id> [--status included|excluded|pending] [--json]

# P1 — CRUD + screening
workflow prisma bib search [--title] [--author] [--year] [--json]
workflow prisma keyword add --text TEXT
workflow prisma tag list [--json]
workflow prisma tag add --text TEXT
workflow prisma rationale list [--json]
workflow prisma rationale add --text TEXT
workflow prisma review screen <bib_id> --keyword-id <id> --include/--exclude [--rationale]

# P2 — import, stats, export, checklist
workflow prisma bib import <file.bib> [--database-name TEXT] [--verbose] [--json]
workflow prisma bib export [--keyword-id INT] [--status ...] [--output PATH] [--force]
workflow prisma review stats --keyword-id <id> [--json]
workflow prisma checklist show [--keyword-id INT] [--json]
```

### Architecture Layers

```
cli.py          Click commands (thin handlers)
    |
service.py      Business logic: list/get/search, create_*, screen_article,
    |            get_review_stats (-> ReviewStats TypedDict),
    |            get_checklist (-> list[ChecklistItem])
    |
importer.py     BibTeX -> DB: bibtexparser parse, per-item savepoint
    |            dedup, author-string splitter, URL scheme allowlist,
    |            file-size cap (MAX_BIB_SIZE_BYTES), ImportResult dataclass
    |
exporter.py     DB -> BibTeX: model-column -> bibtex-field mapping,
    |            author join "Last, First and Last, First", brace
    |            sanitization on all field values, keyword + status filters
    |
formatters.py   Table + JSON formatters (bib, keyword, review, tag,
    |            rationale, import result, stats, checklist)
    |
models/         BibEntry, BibKeyword, ReviewRecord, RationaleOption,
                ReviewRationale, BibTag, BibEntryTag (bibliography.py)
```

### Status Constants

Shared constants in `service.py` eliminate duplicated magic numbers:

```python
REVIEW_STATUS = {"included": 1, "excluded": 0, "pending": None}
REVIEW_STATUS_LABELS = {1: "included", 0: "excluded", None: "pending"}
```

### Shared Engine Helper

`get_engine_from_ctx()` extracted to `workflow.db.engine` — used by both evaluation and PRISMA CLIs, eliminating the duplicated `_get_engine()` pattern.

---

## Architectural Rules

### MUST

- All PRISMA review models **MUST** use SQLAlchemy 2.0 `Mapped[]` annotations on `GlobalBase`.
- `ReviewRecord.included` **MUST** use `default=None` (pending), not `default=0`.
- `review list` **MUST** validate that `--keyword-id` exists before querying — raise `ClickException` if not found.
- All list commands **MUST** support `--json` output for Neovim integration.
- `bib list` and `bib show` **MUST** eagerly load `author_links` → `author` + `author_type`.
- Per-entry `bib import` errors **MUST NOT** abort the batch; each entry **MUST** be wrapped in a savepoint so one failure does not discard prior inserts.
- `bib export` **MUST** sanitize field values (strip raw `{` / `}`) to prevent BibTeX injection when rendering DB content to file.
- Service functions returning composite data (`get_review_stats`, `get_checklist`) **MUST** use `TypedDict` return types, not bare `dict`.

### SHOULD

- Status filtering **SHOULD** use shared `REVIEW_STATUS` constants, not inline magic numbers.
- CLI handlers **SHOULD** delegate all queries to service functions.
- The `pending` status filter **SHOULD** use `is_(None)` (not `== None`).

### MUST NOT

- PRISMA CLI **MUST NOT** require Django or MariaDB to function.
- CLI handlers **MUST NOT** contain raw SQLAlchemy queries — use service layer.
- `ReviewRecord.included` default **MUST NOT** be `0` (would conflate excluded with pending).

---

## Implementation Notes

- Package location: `src/workflow/prisma/` (cli.py, formatters.py, service.py)
- Models: `ReviewRecord`, `RationaleOption`, `ReviewRationale` in `workflow.db.models.bibliography`
- Engine: shared `get_engine_from_ctx()` in `workflow.db.engine`
- Tests: `tests/workflow/test_prisma_cli.py` (95 tests as of P2)
- Wired in `src/main.py` as `cli.add_command(prisma)`

### Phased Implementation

| Phase | Commands | Focus |
|-------|----------|-------|
| P0 | bib list/show, keyword list, review list | Read-only, service layer, --json |
| P1 | bib search, review screen, keyword/tag/rationale add | Core CRUD, screening workflow |
| P2 | bib import, stats, export-bib, checklist show | Import pipeline, PRISMA compliance |
| P3 | Telescope pickers (reuse --json from P0-P2) | Neovim integration |

### Migration from Django

The Django web app (`src/PRISMAreview/`) is preserved for the BibTeX import pipeline (WebSocket-based progress tracking). Over time, `prisma bib import` (P2) will provide CLI-based import, reducing Django dependency further.

Existing Django models in `prismadb/models.py` remain for the web interface. The SQLAlchemy models in `bibliography.py` are the canonical data source for CLI operations.

---

## Impact on AI Coding Agents

- New PRISMA CLI commands follow the same pattern as evaluation CLI (ADR-0016).
- Use `REVIEW_STATUS` / `REVIEW_STATUS_LABELS` from `service.py` — never hardcode `0/1/None`.
- Always validate keyword existence before querying reviews.
- Use `selectinload()` for `author_links` on all `BibEntry` queries.
- Test with in-memory SQLite + `seeded_engine` fixture pattern.

---

## Consequences

### Benefits

- No MariaDB dependency for review management
- Unified CLI for all WorkFlow operations
- `--json` enables Neovim Telescope integration
- Service layer with shared constants eliminates duplicated logic
- Consistent architecture with evaluation CLI

### Costs

- Two parallel model sets (Django + SQLAlchemy) during transition
- Django web app still required for BibTeX import (until P2)
- Review data must be migrated from MariaDB to workflow.db for existing projects

---

## Alternatives Considered

### Alternative A: Django ORM bridge with lazy `django.setup()`

Use Django ORM directly in Click commands via a lazy `django.setup()` call.

#### Advantages

- Reuse 14 existing Django models without rewriting
- No parallel model sets

#### Disadvantages

- `sys.path` manipulation and import ordering fragility
- Inconsistent with rest of WorkFlow (SQLAlchemy)
- Django startup cost on every CLI invocation
- Cross-DB joins impossible without manual Python-level joins

### Alternative B: Standalone `prisma` CLI entry point

Separate CLI binary instead of `workflow prisma` subgroup.

#### Advantages

- Clean separation of concerns

#### Disadvantages

- Loses unified CLI experience
- Cannot share engine/session management
- Users must learn two CLI tools

---

## Compatibility / Migration

- **Breaking change** for users with existing MariaDB review data — requires manual migration to workflow.db.
- The Django web app continues to function independently.
- No changes to existing `workflow` CLI commands.

---

## Status

**Accepted** — supersedes PRISMA-0001 (dual-database router) for CLI operations.

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-04-09 | Initial ADR — documents PRISMA P0 CLI migration |
| 2026-04-18 | P1 delivered: bib search, keyword/tag/rationale add, review screen (50 tests) |
| 2026-04-19 | P2 delivered: bib import / bib export / review stats / checklist show (95 tests). Adds importer.py, exporter.py, ReviewStats + ChecklistItem TypedDicts. Per-entry savepoints, BibTeX-injection sanitization, file-size cap, URL-scheme allowlist, --output overwrite guard. |
