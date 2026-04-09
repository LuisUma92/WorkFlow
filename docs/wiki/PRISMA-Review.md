# PRISMA Systematic Review CLI

Manage bibliography entries, search keywords, and review screening from the command line.

## Commands

### Bibliography

```bash
# List all bibliography entries
workflow prisma bib list
workflow prisma bib list --year 2023            # Filter by year
workflow prisma bib list --type article          # Filter by entry type
workflow prisma bib list --json                  # JSON output

# Show a single entry with full detail
workflow prisma bib show 42
workflow prisma bib show 42 --json
```

### Keywords

```bash
# List search keywords used for systematic reviews
workflow prisma keyword list
workflow prisma keyword list --json
```

### Review Records

```bash
# List review records for a specific keyword
workflow prisma review list --keyword-id 1
workflow prisma review list --keyword-id 1 --status included
workflow prisma review list --keyword-id 1 --status excluded
workflow prisma review list --keyword-id 1 --status pending
workflow prisma review list --keyword-id 1 --json
```

## Review Status Values

| Status | Value | Meaning |
|--------|-------|---------|
| `included` | 1 | Article meets inclusion criteria |
| `excluded` | 0 | Article does not meet criteria |
| `pending` | NULL | Not yet screened |

## Data Model

### New SQLAlchemy Models (in workflow.db)

| Model | Table | Purpose |
|-------|-------|---------|
| `ReviewRecord` | `review_record` | Screening decision per (keyword, article) pair |
| `RationaleOption` | `rationale_option` | Pre-defined include/exclude rationales |
| `ReviewRationale` | `review_rationale` | Links rationale to review record |

These models live in `src/workflow/db/models/bibliography.py` alongside `BibEntry`, `Author`, `BibKeyword`, etc.

### Existing Models Used

| Model | Purpose |
|-------|---------|
| `BibEntry` | Full BibLaTeX bibliography record (40+ fields) |
| `Author` | Author name (first_name, last_name) |
| `BibAuthor` | Junction: author + entry + role |
| `BibKeyword` | Search keyword for systematic review |

## Architecture

See [ADR PRISMA-0005](../ADR/PRISMA-0005-cli-sqlalchemy-migration.md) for the full architecture decision.

```
cli.py        Click commands (thin handlers)
service.py    Business logic (list_bib_entries, list_reviews, etc.)
formatters.py Table + JSON output
```

Key design decisions:
- All data stored in unified `workflow.db` (SQLite) — no MariaDB dependency
- Service layer validates keyword existence before querying reviews
- Shared `REVIEW_STATUS` / `REVIEW_STATUS_LABELS` constants eliminate magic numbers
- `selectinload()` for author relationships prevents N+1 queries

## Relationship to Django Web App

The Django web app (`src/PRISMAreview/`) is preserved for BibTeX import (WebSocket-based progress tracking). The CLI provides terminal access to the same data via SQLAlchemy models.

## Planned Phases

| Phase | Status | Commands |
|-------|--------|----------|
| P0 | Done | bib list/show, keyword list, review list |
| P1 | Planned | bib search, review screen, keyword/tag/rationale add |
| P2 | Planned | bib import, stats, export-bib, checklist show |
| P3 | Planned | Telescope pickers for Neovim |
