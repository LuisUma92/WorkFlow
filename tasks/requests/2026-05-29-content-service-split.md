# Split `workflow.content.service` into CRUD + link-management modules

## Summary

`src/workflow/content/service.py` shipped in v1.11.0 as a focused
CRUD module for the `Content` ORM entity. v1.13.0 doubled its
surface by adding `BibContent` link management
(`link_bib_to_content`, `list_bib_links`, `unlink_bib_from_content`,
`_resolve_bib_entry`). v1.13.1 added another 7 error classes.

Architect review (2026-05-29 reviewer-esquema) flagged this as
**HIGH module-boundary drift**: the file mixes two distinct
concerns (Content CRUD vs. Content↔BibContent linking) and is
positioned to grow further when `Content↔Concept` linking,
`Content↔MainTopicSyllabus` linking, or
`Content↔GeneralProjectContent` linking lands.

## Motivation

- Reporting agent(s): architect-reviewer (2026-05-29)
- Total occurrences: 1 (will recur when the next link type lands)
- Severity: **HIGH** (architectural — file will double if not split)
- Blocks / slows down:
  - Future `Content↔X` link work (every new link type adds 3–4
    functions + 2–3 error classes to a single file)
  - Test discoverability (a single 200+ line test_*_cli.py can't
    mirror the source split)
  - Reuse — concept-link logic could share patterns with bib-link
    logic, but only if both live in dedicated link modules

## Proposed structure

```
src/workflow/content/
    __init__.py
    service.py          # Content CRUD only: add_content, list_contents,
                        # get_content, + ContentServiceError,
                        # TopicNotFound, DuplicateContent, ContentNotFound
    bib_links.py        # BibContent link mgmt: link_bib_to_content,
                        # list_bib_links, unlink_bib_from_content,
                        # _resolve_bib_entry, + BibEntryNotFound,
                        # BibKeyAmbiguous, BibLinkNotFound,
                        # BibLinkAlreadyExists
    formatters.py       # extend with section markers (existing — keep)
    cli.py              # extend with section markers (existing — keep)
```

Re-export from `content/__init__.py` to preserve existing
import paths in `cli.py` and tests (no breaking change).

## Plan

1. Create `src/workflow/content/bib_links.py` with the 3 link
   functions + 4 link-related error classes
2. Add re-exports in `content/__init__.py`:
   `from workflow.content.service import *`
   `from workflow.content.bib_links import *`
3. Update `content/cli.py` imports to point at the right module
   (optional — re-exports keep old imports working)
4. Split tests: `tests/workflow/test_content_cli.py` stays for
   CRUD; `tests/workflow/test_content_bib_cli.py` already exists
   for link mgmt — no test reorg needed
5. Verify `__all__` is consistent across both modules and the
   `__init__`

## Acceptance test

- `from workflow.content.service import add_content` still works
- `from workflow.content.service import link_bib_to_content` still
  works via re-export OR is updated to
  `from workflow.content.bib_links import link_bib_to_content`
- `wc -l src/workflow/content/service.py` returns < 100 (was 177
  pre-split)
- `wc -l src/workflow/content/bib_links.py` returns ~100
- Full pytest stays green (1410+ tests)
- No circular imports between `service.py` and `bib_links.py`
  (both should depend on `db.models`, not on each other)

## Out of scope

- Renaming `BibLinkAlreadyExists` ↔ `DuplicateBibLink` (request
  consistency — defer; see error-class consolidation request below)
- Splitting `cli.py` (single CLI module is fine; Click groups
  serve as namespaces)
- Splitting `formatters.py` (single file is fine while < 100 lines)

## Cross-references

- `2026-05-29` reviewer-esquema synthesis (architect HIGH #2)
- `src/workflow/content/service.py` — current (post-v1.13.1) state
- `2026-05-29-bibliography-service-extraction.md` — sibling
  architectural request; should land in the same patch series
- Related: error class consolidation
  (`ContentServiceError` → `EntityNotFoundError` /
  `UniquenessError` base hierarchy) — separate concern, may file
  a follow-up
