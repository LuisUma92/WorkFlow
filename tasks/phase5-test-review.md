# Phase 5 Test Review

## Summary

5 test files reviewed against 5 source files. Overall quality is solid but several coverage gaps exist.

---

## CRITICAL

### 1. `test_scanner.py` — `register_notes()` has ZERO tests
The function `register_notes()` (scanner.py:58-101) handles DB registration with Note model interaction, idempotency (already_registered), and ScanResult construction. It is 44 lines of untested code including a DB session flush.

**Add tests:**
```
- test_register_notes_creates_notes_in_db
- test_register_notes_idempotent (run twice, no duplicates)
- test_register_notes_returns_scan_result_with_counts
- test_register_notes_empty_dir_returns_empty_result
- test_register_notes_already_registered_note_skipped
```

### 2. `test_scanner.py` — `ScanResult` dataclass untested
No test verifies ScanResult is frozen or that its fields are populated correctly.

---

## HIGH

### 3. `test_eval_builder.py` — No input validation tests
`evaluation_template_to_slots()` receives `list[dict]` with no validation. Missing tests:
```
- test_template_item_missing_key_raises (e.g., missing "taxonomy_level")
- test_template_item_wrong_type_raises (e.g., total_amount="three")
- test_negative_total_amount
- test_zero_points_per_item
```

### 4. `test_linker.py` — `_strip_comment()` only tested indirectly
`_strip_comment()` handles escaped `%` characters (`\%`). No direct test for:
```
- test_escaped_percent_not_stripped (e.g., "Cost is 50\% of total")
- test_multiple_percent_signs
- test_line_with_only_percent
```

### 5. `test_linker.py` — `_process_labels_and_citations()` and `_process_refs()` untested
These are private but contain significant logic (OSError handling, two-pass algorithm). The integration via `link_lecture_files` partially covers them, but the OSError path (line 213) is never tested.

**Add test:**
```
- test_link_unreadable_file_produces_warning (make file unreadable or mock OSError)
```

### 6. `test_cli.py` — `build-eval` coverage is shallow
`build_eval` command (cli.py:149-221) has 5 tests but none verify:
- Multiple `--taxonomy-level` flags (the zip logic on line 186-193)
- Content of the output .tex file
- Content of the Moodle .xml file (currently writes empty `exercises_to_quiz_xml([])`)

---

## MEDIUM

### 7. `test_note_splitter.py` — Missing edge cases
```
- test_split_empty_file (file exists but is empty)
- test_split_marker_with_leading_whitespace (indented "%>path")
- test_split_unicode_content (content with accented chars, math symbols)
- test_split_consecutive_markers_no_content (two markers back-to-back)
- test_split_nonexistent_source_file_raises
```

### 8. `test_scanner.py` — Missing edge cases
```
- test_scan_with_symlinks (symlinked .tex files)
- test_generate_note_reference_with_special_chars_in_filename
- test_generate_note_reference_filepath_not_relative_to_lecture_dir_raises
```

### 9. `test_linker.py` — `\input{}` references never verified in DB integration
`extract_references` parses `\input{}` but `link_lecture_files` ignores them (no DB action for type "input"). Tests should document this intentional behavior:
```
- test_input_refs_not_stored_in_db (explicit documentation test)
```

### 10. `test_cli.py` — No error path tests
```
- test_scan_nonexistent_dir_exits_nonzero
- test_split_nonexistent_source_exits_nonzero
- test_link_shows_warnings_on_stderr
```

---

## LOW

### 11. `test_eval_builder.py` — No test for `EvalSpec.__all__` exports
Minor, but verifying `__all__` matches public API prevents import regressions.

### 12. `test_linker.py` — No test for `\autocite{}` or `\textcite{}`
The regex `_CITE_RE` only matches `\cite{}`. If biblatex-style citations are expected, this is a functional gap. If not, document it.

### 13. `test_note_splitter.py` — `warnings` field never populated
The `SplitResult.warnings` field exists but `split_notes_file()` never appends to it. Either remove the field or add logic + tests for warning conditions.

---

## Test Quality Issues

| Issue | Severity | Location |
|-------|----------|----------|
| Weak assertion: `"1" in result.output` matches any line with "1" | MEDIUM | test_cli.py:31 |
| Weak assertion: `"0" in result.output` matches any line with "0" | MEDIUM | test_cli.py:40,91 |
| No `conftest.py` for shared fixtures (db session, tmp_path helpers) | LOW | all files |
| `test_build_eval_with_empty_bank` relies on empty pool, not on actual DB | MEDIUM | test_cli.py:180 |

---

## Estimated Coverage Gaps

| Module | Estimated Line Coverage | Target |
|--------|------------------------|--------|
| scanner.py | ~55% (register_notes untested) | 80%+ |
| note_splitter.py | ~90% | OK |
| linker.py | ~75% (_strip_comment, OSError paths) | 80%+ |
| eval_builder.py | ~95% | OK |
| cli.py | ~70% (build-eval shallow) | 80%+ |

**Priority action:** Write tests for `register_notes()` (CRITICAL) and the OSError/validation paths (HIGH).
