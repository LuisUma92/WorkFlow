# PRISMA P2 — Import, Stats, Export, Checklist

**Date:** 2026-04-09
**Status:** Approved
**Scope:** `src/workflow/prisma/` — new files: `importer.py`, `exporter.py`; updates to `cli.py`, `service.py`, `formatters.py`

---

## Overview

Phase 2 adds four capabilities to the PRISMA CLI:

1. **`prisma bib import`** — parse `.bib` files and insert into `workflow.db`
2. **`prisma review stats`** — per-keyword screening counts
3. **`prisma bib export`** — filtered BibTeX export from DB
4. **`prisma checklist show`** — PRISMA compliance checklist from DB state

Architecture: Approach A (thin CLI, fat service, dedicated importer/exporter modules).

---

## Architecture

```
cli.py          Click commands (thin handlers)
    |
service.py      Business logic (stats, checklist)
    |
importer.py     BibTeX → DB (bibtexparser, author splitting, dedup)
exporter.py     DB → BibTeX (reverse field mapping, author joining)
formatters.py   Table + JSON output (stats, checklist, import result)
    |
models/         BibEntry, Author, BibAuthor, BibUrl, etc. (bibliography.py)
```

---

## 1. `prisma bib import <file.bib>`

### CLI Interface

```
workflow prisma bib import <file> [--database-name TEXT] [--verbose] [--json]
```

- `<file>`: path to `.bib` file (required positional argument)
- `--database-name`: source database label (e.g., "PubMed", "Scopus"); extracted from filename prefix if omitted
- `--verbose`: print per-entry status (created/skipped/error)
- `--json`: structured output of import result

### Module: `importer.py`

**Constants:**

```python
TRANSLATED_BIB_KEYS = {
    "entry_type": "ENTRYTYPE",
    "bibkey": "ID",
    "journaltitle": "journal",
    "publication_date": "date",
    "notes": "note",
    "volume": "volume",
    "number": "number",
    "file_path": "file",
}
```

Fields not in the translation dict are mapped 1:1 by name (title, abstract_text, publisher, year, pages, doi, etc.).

**Functions:**

- `import_bib_file(session, path, database_name=None) -> ImportResult`
  - Opens file, calls `bibtexparser.load()`
  - Iterates entries, calling `_process_entry()` for each
  - Returns `ImportResult(created, skipped, errors)`

- `_process_entry(session, raw_entry, database_name) -> str`
  - Maps BibTeX fields to BibEntry column dict via `_parse_fields()`
  - Calls `_upsert_bib_entry()` — insert, skip on IntegrityError (title/year/volume dupe)
  - Calls `_process_authors()` for each author-type field (author, editor, translator)
  - Calls `_process_url()` if url field present
  - Returns status: "created", "skipped", or "error: {msg}"

- `_parse_fields(raw_entry) -> dict`
  - Applies TRANSLATED_BIB_KEYS mapping
  - Converts year to int (if present)
  - Strips braces from values

- `_split_authors(author_string) -> list[tuple[str, str]]`
  - Splits on `" and "`
  - Handles formats: "Last, First", "First Last", "First. Last", "{Corporate Name}"
  - Returns list of (first_name, last_name) tuples

- `_upsert_bib_entry(session, fields) -> BibEntry | None`
  - Insert BibEntry; catch IntegrityError for dupe, return None if skipped

- `_upsert_author(session, first_name, last_name) -> Author`
  - Insert or get existing Author by unique (first_name, last_name)

- `_process_authors(session, bib_entry, author_string, author_type_name) -> None`
  - Split authors, upsert each, create BibAuthor junction
  - First author in list gets `first_author=True`

- `_process_url(session, bib_entry, url_string, database_name) -> None`
  - Get or create ReferencedDatabase by name
  - Create BibUrl (skip on dupe)

**Data class:**

```python
@dataclass(frozen=True)
class ImportResult:
    created: int
    skipped: int
    errors: list[str]
```

### Deduplication Strategy

- BibEntry: unique constraint on (title, year, volume) — IntegrityError → skip
- Author: unique constraint on (first_name, last_name) — IntegrityError → get existing
- BibAuthor: unique constraint on (author_id, bib_entry_id, author_type_id) — IntegrityError → skip
- BibUrl: unique constraint on (bib_entry_id, database_id) — IntegrityError → skip

All dedup uses `session.flush()` + `try/except IntegrityError` + `session.rollback()` per-item (savepoint pattern), not whole-transaction rollback.

---

## 2. `prisma review stats --keyword-id <id>`

### CLI Interface

```
workflow prisma review stats --keyword-id <id> [--json]
```

### Service Function

```python
def get_review_stats(session, keyword_id) -> dict:
    """Per-keyword screening counts. Raises ValueError if keyword not found."""
    # Validate keyword exists
    # COUNT(review_record) grouped by included status
    # Return {"keyword": text, "keyword_id": id,
    #         "included": N, "excluded": N, "pending": N, "total": N}
```

### Formatter

- `format_stats_table(stats)` — tabular display with counts
- `format_stats_json(stats)` — JSON dict

---

## 3. `prisma bib export [--keyword-id] [--status] [--output file.bib]`

### CLI Interface

```
workflow prisma bib export [--keyword-id INT] [--status included|excluded|pending] [--output PATH]
```

- No filters: exports all BibEntries
- `--keyword-id`: only entries linked via ReviewRecord to that keyword
- `--status`: further filter by review status (requires `--keyword-id`)
- `--output`: write to file instead of stdout

### Module: `exporter.py`

**Constants:**

```python
REVERSED_BIB_KEYS = {v: k for k, v in TRANSLATED_BIB_KEYS.items()}
# Plus manual overrides for fields that don't round-trip cleanly
```

**Functions:**

- `export_bib_entries(session, keyword_id=None, status=None) -> str`
  - Query BibEntries (with optional keyword/status filter via ReviewRecord join)
  - For each entry: `_entry_to_bibtex()` builds bibtex string
  - Returns concatenated .bib content

- `_entry_to_bibtex(entry: BibEntry) -> str`
  - Reverse-map DB columns to BibTeX field names
  - Join authors back to `"Last, First and Last, First"` format per author type
  - Build `@type{key, field = {value}, ...}` string
  - Skip None/empty fields

- `_join_authors(bib_entry, author_type_name) -> str | None`
  - Filter author_links by type, format as `"Last, First"`, join with `" and "`

### Validation

- `--status` without `--keyword-id` raises ClickException (status is per-keyword)

---

## 4. `prisma checklist show [--keyword-id]`

### CLI Interface

```
workflow prisma checklist show [--keyword-id INT] [--json]
```

### Service Function

```python
def get_checklist(session, keyword_id=None) -> list[dict]:
    """PRISMA compliance checklist from DB state."""
    # Returns list of {"item": str, "satisfied": bool, "detail": str}
```

**Checklist items:**

| Item | Check | Detail |
|------|-------|--------|
| Search keywords defined | `COUNT(bib_keyword) > 0` | "N keywords" |
| Bibliography imported | `COUNT(bib_entry) > 0` | "N entries" |
| Screening criteria defined | `COUNT(rationale_option) > 0` | "N rationale options" |
| Articles retrieved | `COUNT(review_record) > 0` for keyword | "N records" |
| Screening in progress | `COUNT(rr WHERE included IS NOT NULL) > 0` for keyword | "N decided" |
| All articles decided | `COUNT(rr WHERE included IS NULL) == 0` for keyword | "N pending" or "complete" |

When `--keyword-id` is omitted, keyword-specific items show aggregate across all keywords.

### Formatter

- `format_checklist_table(items)` — `[x]` / `[ ]` per item with detail
- `format_checklist_json(items)` — JSON list of dicts

---

## 5. Tests

File: `tests/workflow/test_prisma_cli.py` (extend existing 50 tests)

### Import Tests (~12)

- Valid .bib file with 2 entries → 2 created
- Duplicate entry → skipped (IntegrityError)
- Author splitting: "Last, First" format
- Author splitting: "First Last" format
- Author splitting: braces "{Corporate}"
- Multiple author types (author + editor)
- Missing year field → still imports
- Empty .bib file → 0 created, 0 errors
- `--verbose` flag shows per-entry output
- `--json` flag returns structured ImportResult
- URL extraction creates BibUrl
- `--database-name` sets ReferencedDatabase

### Stats Tests (~5)

- Correct counts for mixed statuses
- All pending → included=0, excluded=0
- Nonexistent keyword → ValueError
- `--json` output structure
- Empty keyword (no review records) → all zeros

### Export Tests (~6)

- Export all entries → valid .bib format
- Filter by keyword → only linked entries
- Filter by status → correct subset
- `--status` without `--keyword-id` → error
- Round-trip: import → export → verify fields match
- Author joining: "Last, First and Last, First" format

### Checklist Tests (~5)

- Empty DB → all unchecked
- Partial state → mixed checks
- All complete → all checked
- With keyword-id filter
- `--json` output structure

**Total: ~28 new tests, ~78 total in file.**

---

## 6. CLI Command Summary (after P2)

```
workflow prisma bib list [--year] [--type] [--json]              # P0
workflow prisma bib show <id> [--json]                           # P0
workflow prisma bib search [--title] [--author] [--year] [--json] # P1
workflow prisma bib import <file> [--database-name] [--verbose] [--json]  # P2
workflow prisma bib export [--keyword-id] [--status] [--output]  # P2
workflow prisma keyword list [--json]                            # P0
workflow prisma keyword add --text TEXT                          # P1
workflow prisma tag list [--json]                                # P1
workflow prisma tag add --text TEXT                               # P1
workflow prisma rationale list [--json]                           # P1
workflow prisma rationale add --text TEXT                         # P1
workflow prisma review list --keyword-id ID [--status] [--json]  # P0
workflow prisma review screen BIB_ID --keyword-id ID --include/--exclude [--rationale]  # P1
workflow prisma review stats --keyword-id ID [--json]            # P2
workflow prisma checklist show [--keyword-id] [--json]           # P2
```

---

## Dependencies

- `bibtexparser` — already in project dependencies (used by Django pipeline)
- No new dependencies required
