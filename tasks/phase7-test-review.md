# Phase 7 Test Review

## Summary

| File | Tests | Verdict |
|------|-------|---------|
| `tests/workflow/test_note_model_extended.py` | 8 | Good with issues |
| `tests/workflow/notes/test_init.py` | 17 | Good |
| latexzettel/api/{notes,sync,markdown,analysis}.py | 0 | Coverage gap |

---

## test_note_model_extended.py (Phase 7b)

### What is tested
- New Zettelkasten fields on Note model (zettel_id, title, note_type, source_format)
- Uniqueness constraint on zettel_id
- Backward compatibility (nullable fields)
- note_type value acceptance
- SqlNoteRepo.find_by_zettel_id and find_by_type

### Issues

**MEDIUM: No validation of invalid note_type values.**
The model accepts any string for `note_type` (no CHECK constraint or enum). A test should verify whether arbitrary strings like `"invalid"` are accepted or rejected, and if accepted, document it as a known limitation.

**MEDIUM: No test for source_format uniqueness/values.**
Only `"md"` and `"tex"` are documented as valid values for `source_format`. No test verifies behavior with invalid values or that valid values roundtrip correctly in isolation.

**LOW: Missing edge cases for zettel_id.**
No tests for empty string `""` vs `None`, or special characters in zettel_id. SQLite treats `""` and `NULL` differently for unique constraints.

**LOW: No test for Note.tags relationship.**
The model defines a `tags` M2M relationship. No test verifies it works with the new fields.

---

## tests/workflow/notes/test_init.py (Phase 7d)

### What is tested
- Workspace marker creation (.workflow/config.yaml)
- Vault directory structure (inbox, templates)
- Note template files (permanent.md, literature.md, fleeting.md)
- Project directory detection and initialization
- Special directory skipping (00AA, 00BB, 00EE, 00II, 00ZZ)
- Non-project directory skipping (.git, no-digit-prefix)
- Idempotency (rerun safety)
- slipbox.db creation
- InitResult tracking (created, existed, projects)
- CLI integration (init command, help, error paths)
- Files in workspace don't cause crashes

### Issues

**LOW: test_init_default_current_dir mutates global state.**
Uses `os.chdir()` which can leak if the test fails before the `finally` block runs in some pytest configurations. Consider using `monkeypatch.chdir()` instead.

**LOW: No test for permission errors.**
No test for read-only directories or permission-denied scenarios.

---

## Ported latexzettel API — Coverage Gap

### CRITICAL: No tests exist for ported API modules

The following files have zero test coverage:
- `src/latexzettel/api/notes.py` (307 lines) — create, rename, delete notes
- `src/latexzettel/api/sync.py` (448 lines) — incremental and force sync
- `src/latexzettel/api/markdown.py` (378 lines) — wikilink conversion, pandoc sync
- `src/latexzettel/api/analysis.py` (196 lines) — adjacency matrix, unreferenced notes

The stated rationale ("relies on existing tests still passing") is invalid: there are no existing latexzettel test files in `tests/`. These 1,329 lines of business logic have zero automated coverage.

### Risk assessment

These modules contain:
- File I/O (create, rename, delete .tex files)
- Database mutations (CRUD on Note, Label, Citation, Link)
- Regex-based parsing of LaTeX commands
- External process execution (pandoc)
- Complex wikilink <-> LaTeX bidirectional conversion

Without tests, regressions in the ported code are undetectable.

### Recommended action

At minimum, add unit tests for:
1. `_convert_wikilinks_to_latex` and `_convert_exrefs_to_wikilinks` (pure-ish functions, high value)
2. `create_note` / `remove_note` with in-memory DB (CRUD correctness)
3. `calculate_adjacency_matrix` with in-memory DB (graph logic)
4. `_get_labels_from_file`, `_get_citation_keys_from_file`, `_get_links_from_file` (regex parsing)

---

## Overall Rating

| Category | Rating |
|----------|--------|
| test_note_model_extended.py | **Good** — covers core model + repo, minor gaps |
| test_init.py | **Good** — thorough, 17 tests, covers idempotency and CLI |
| latexzettel API coverage | **CRITICAL** — 1,329 lines with 0 tests, no existing test suite to fall back on |
