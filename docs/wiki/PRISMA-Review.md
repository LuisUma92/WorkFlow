---
id: 
parent: Wiki
title: PRISMA Systematic Review CLI
aliases: []
type: permanent
created: 
tags: []
concepts: []
references: []
exercises: []
images: []
---

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
workflow prisma keyword add --text "machine learning"
```

### Tags

```bash
workflow prisma tag list [--json]
workflow prisma tag add --text "meta-analysis"
```

### Rationales

```bash
workflow prisma rationale list [--json]
workflow prisma rationale add --text "off topic"
```

### Bibliography Search (P1)

```bash
workflow prisma bib search --title "education"
workflow prisma bib search --author "smith"
workflow prisma bib search --year 2023 [--json]
```

### Bibliography Import (P2)

```bash
# Import a .bib file. --database-name tags the source; inferred from
# a filename prefix like "PubMed-export.bib" when omitted.
workflow prisma bib import refs.bib
workflow prisma bib import refs.bib --database-name PubMed --verbose
workflow prisma bib import refs.bib --json

# Read biblatex from stdin instead of a file
cat refs.bib | workflow prisma bib import --stdin --database-name Scopus

# Force bibkey recalculation for every imported entry (default: keep source
# IDs verbatim, only calculate missing/empty ones)
workflow prisma bib import refs.bib --recompute-bibkeys
```

Dedup is automatic: duplicate (title, year, volume) triples are skipped.
Per-entry errors are isolated by savepoint and reported in the result.
Max file size: 50 MB.

### Bibliography Export (P2)

```bash
# Export all entries, or scope to a keyword / status.
workflow prisma bib export                                        # stdout
workflow prisma bib export --output refs.bib                       # to file
workflow prisma bib export --output refs.bib --force               # overwrite
workflow prisma bib export --keyword-id 1
workflow prisma bib export --keyword-id 1 --status included

# Dialect: default is biblatex (canonical fields, no type downgrade).
# --dialect bibtex downgrades biblatex-only entry types and reverse-maps
# field names (journaltitle -> journal, etc).
workflow prisma bib export --dialect bibtex --output refs.bib

# Inline crossref/xdata inheritance into each entry instead of round-tripping
# the pointer fields verbatim (ADR-0019 A4).
workflow prisma bib export --resolve-xref --output refs.bib
```

`--status` requires `--keyword-id`. `--output` refuses to overwrite
existing files unless `--force` is passed.

### Recompute Bibkeys (ADR-0019)

```bash
# Fill only entries with a missing/empty bibkey (default, safe)
workflow prisma bib recompute-keys --dry-run
workflow prisma bib recompute-keys

# Normalize every key, including already-populated ones (requires confirmation)
workflow prisma bib recompute-keys --all
workflow prisma bib recompute-keys --all --yes --json   # --yes required with --json --all
```

The DB is backed up before any write. `--dry-run` previews the diff without
writing or backing up.

### Accept-to-Note (Wave C)

Generates a literature note from a PRISMA-accepted (`included == 1`)
bibliography entry, writing to
`<vault_root>/notes/literature/<YYYYMMDD>-lit-<bibkey>.md`.

```bash
# Single entry, resolved by bibkey (embeds screening rationale if a
# keyword/review-record context is given)
workflow prisma bib accept-to-note serway2018 --keyword-id 1
workflow prisma bib accept-to-note serway2018 --dry-run          # preview only
workflow prisma bib accept-to-note --bib-entry-id 42 --json      # disambiguate

# Bulk: one note per included==1 review record for a keyword
workflow prisma bib accept-to-note --all-accepted --keyword-id 1 --json
```

PRISMA context (`--keyword-id`/`--review-record-id`) is optional in single
mode — without it, `origin` is written as `manual`. In bulk mode
(`--all-accepted`), ambiguous/unsafe entries and already-existing notes are
skipped (not fatal), and skip counts are included in the result. `--json`
emits `{note_path, bibkey, created}` (single) or the bulk shape.

Neovim: `:WorkflowPrismaAcceptToNote` prompts for a bibkey (single) or
keyword-id (bulk), shells out with `--json`, and opens the result in a
vsplit.

### Manual Literature Note (no PRISMA context)

When a bibkey needs a literature note outside of any PRISMA screening
workflow, `workflow notes create` reuses the same renderer as
`accept-to-note`:

```bash
workflow notes create --type literature --bibkey serway2018
workflow notes create --type literature --bibkey serway2018 --origin import --json
workflow notes create --type literature --bibkey serway2018 --bib-entry-id 42
```

Idempotent: a second run reports `created: false` without overwriting the
existing note. `--dry-run` computes the content without writing.

### Review Records

```bash
# List review records for a specific keyword
workflow prisma review list --keyword-id 1
workflow prisma review list --keyword-id 1 --status included
workflow prisma review list --keyword-id 1 --status excluded
workflow prisma review list --keyword-id 1 --status pending
workflow prisma review list --keyword-id 1 --json

# Screen a single article (P1)
workflow prisma review screen <bib_id> --keyword-id 1 --include
workflow prisma review screen <bib_id> --keyword-id 1 --exclude --rationale "off topic"

# Screening counts for a keyword (P2)
workflow prisma review stats --keyword-id 1 [--json]
```

### Checklist (P2)

```bash
# PRISMA compliance checklist from DB state.
workflow prisma checklist show                      # global aggregate
workflow prisma checklist show --keyword-id 1       # scope review rows
workflow prisma checklist show --json
```

Items 1-3 (keywords defined, bibliography imported, screening criteria
defined) always reflect global counts. Items 4-6 (articles retrieved,
screening in progress, all articles decided) scope to `--keyword-id`
when given, else aggregate across keywords.

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
service.py    Business logic (list/get/search, create_*, screen_article,
              get_review_stats, get_checklist)
importer.py   BibTeX -> DB (P2)
exporter.py   DB -> BibTeX (P2)
formatters.py Table + JSON output (includes import result, stats, checklist)
```

Key design decisions:
- All data stored in unified `workflow.db` (SQLite) — no MariaDB dependency
- Service layer validates keyword existence before querying reviews
- Shared `REVIEW_STATUS` / `REVIEW_STATUS_LABELS` constants eliminate magic numbers
- `selectinload()` for author relationships prevents N+1 queries
- Composite service returns (`ReviewStats`, `ChecklistItem`) are `TypedDict`, not bare dict
- `bib import` wraps each entry in a savepoint so partial failure does not discard prior inserts
- `bib export` strips raw `{` / `}` from DB values to prevent BibTeX injection

## Relationship to Django Web App

The Django web app (`src/PRISMAreview/`) is preserved for BibTeX import (WebSocket-based progress tracking). The CLI provides terminal access to the same data via SQLAlchemy models.

## Phases

| Phase | Status | Commands |
|-------|--------|----------|
| P0 | Done | bib list/show, keyword list, review list |
| P1 | Done | bib search, review screen, keyword/tag/rationale add |
| P2 | Done | bib import (+ `--stdin`, `--recompute-bibkeys`), bib export (+ `--dialect`, `--resolve-xref`), bib recompute-keys, review stats, checklist show |
| P3 | Done | Telescope pickers for Neovim |
| Wave C | Done | `bib accept-to-note` (single + bulk), `notes create --bibkey` (manual literature note, no PRISMA context) |

See [ADR-0019](../ADR/0019-bibliography-dialect-biblatex-bibtex.md) (biblatex-native
model + bibtex compat) and [ADR-0020](../ADR/0020-bibliography-module-boundary.md)
(foundation layer + 0/1/2+ lookup contract) for the dialect/export work.
