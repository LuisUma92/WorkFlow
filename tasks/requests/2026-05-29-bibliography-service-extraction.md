# Extract `workflow.bibliography.service` from `workflow.prisma.service`

## Summary

`src/workflow/content/service.py` (v1.13.0+, after v1.13.1 patch) currently
imports `get_bib_entry_by_bibkey` from `workflow.prisma.service` to look up
`BibEntry` rows by bibkey. Architect review (2026-05-29 reviewer-esquema)
flagged this as a cross-domain dependency: **bibliography lookup is not a
PRISMA-systematic-review concern.** PRISMA is a *consumer* of bibliography,
not its owner.

The v1.13.1 patch collapsed `_resolve_bib_entry` to a single-select query
that bypasses the prisma helper entirely (the cross-import was actually
removed). But the underlying lookup `get_bib_entry_by_bibkey` still lives
in `workflow.prisma.service` and will be re-needed by:

- A future `workflow bib show <bibkey>` command outside the PRISMA flow
- The nvim picker plan (`2026-05-28-content-bib-link-cli.md` plugin section)
- Any tool that wants citekey → `BibEntry.id` resolution

## Motivation

- Reporting agent(s): architect-reviewer (2026-05-29)
- Total occurrences: 1 (consensus across the 4-reviewer schema)
- Severity: **HIGH** (architectural — locks future bibliography work
  into the PRISMA module if not addressed)
- Blocks / slows down:
  - Any new `workflow bib*` CLI subcommand (would need to import from
    `prisma.service` which makes no semantic sense outside review flows)
  - Future bibliography auto-import from BibTeX outside PRISMA context
  - Clean module dependency graph (PRISMA should depend on bibliography,
    not the other way around)

## Proposed module

```
src/workflow/bibliography/
    __init__.py
    service.py      # ← move here: get_bib_entry_by_bibkey, _bib_entry_options
                    # plus future: get_bib_entry_by_id, search_by_doi
    formatters.py   # ← future: shared formatters for BibEntry display
```

## Plan

1. Create `src/workflow/bibliography/` package
2. Move `get_bib_entry_by_bibkey` and `_bib_entry_options` from
   `src/workflow/prisma/service.py` to `src/workflow/bibliography/service.py`
3. Add a deprecation re-export in `prisma/service.py` for backward
   compat: `from workflow.bibliography.service import get_bib_entry_by_bibkey`
4. Update `prisma/cli.py` and any other prisma consumers to import
   from the new location directly
5. Update `content/service.py` to import from the new location
   (the single-select pattern from v1.13.1 stays — but if a future
   refactor reintroduces the helper, it imports from `bibliography`)
6. Add `tests/workflow/bibliography/test_service.py` exercising the
   moved functions
7. ADR amendment or new ADR documenting the bibliography module
   boundary

## Acceptance test

- `from workflow.bibliography.service import get_bib_entry_by_bibkey`
  works; identical behavior to the previous prisma-located function.
- `from workflow.prisma.service import get_bib_entry_by_bibkey` still
  works (deprecation re-export) but emits a DeprecationWarning.
- Full pytest suite stays green.
- `grep -rn "from workflow.prisma" src/workflow/content/` returns
  zero matches after refactor.
- New tests in `tests/workflow/bibliography/` cover the relocated
  functions.

## Out of scope

- Moving `BibEntry` ORM model (it correctly lives in
  `db/models/bibliography.py`)
- Renaming `bibkey` ↔ `citekey` (separate concern)
- Bulk bibliography commands (future work)

## Cross-references

- `2026-05-29` reviewer-esquema synthesis (architect HIGH #1)
- `src/workflow/prisma/service.py:174` — `get_bib_entry_by_bibkey`
- `src/workflow/content/service.py` — current consumer
- `2026-05-28-content-bib-link-cli.md` — closed v1.13.0/v1.13.1
- `docs/ADR/PRISMA-0005.md` — would need amendment to clarify
  boundary (or new ADR `BIB-0000`)
