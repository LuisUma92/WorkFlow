# PRISMA P2 — Implementation Plan

**Spec:** `docs/superpowers/specs/2026-04-09-prisma-p2-design.md`
**Approach:** TDD, thin CLI + fat service + dedicated modules
**Status:** In progress (started 2026-04-19)

## Dependency Order

1. **Import** — foundation; populates data for later features
2. **Export** — round-trip validates import
3. **Stats** — reads P1 review records
4. **Checklist** — aggregates all prior

## Tasks

### Phase A — `bib import` ✅ DONE (commit 57e4d4c)
- [x] A1. RED: 12 import tests
- [x] A2. GREEN: `importer.py` (ImportResult, import_bib_file, helpers)
- [x] A3. GREEN: `prisma bib import` wired in cli.py
- [x] A4. GREEN: `format_import_result_{table,json}` in formatters.py
- [x] A5. VERIFY: 12/12 pass; full 634/634 workflow tests pass
- [x] A6. Commit: 57e4d4c

### Phase B — `bib export` ✅ DONE
- [x] B1. RED: 12 → 17 tests
- [x] B2. GREEN: `exporter.py` with `export_bib_entries`, `_entry_to_bibtex`, `_join_authors`
- [x] B3. GREEN: `prisma bib export` wired (--keyword-id, --status, --output, --force)
- [x] B4. Reviewer-esquema fixes: model→bib mapping direction, date round-trip, type hints, injection sanitization, overwrite guard
- [x] B5. VERIFY: 17/17 export tests pass; 656 total workflow tests; flake8 clean

### Phase C — `review stats`
- [ ] C1. RED: ~5 stats tests
- [ ] C2. GREEN: `get_review_stats` in `service.py`
- [ ] C3. GREEN: wire `prisma review stats` in `cli.py` + `format_stats_*` formatters
- [ ] C4. VERIFY tests pass
- [ ] C5. Commit: `feat(prisma): add review stats command (P2)`

### Phase D — `checklist show`
- [ ] D1. RED: ~5 checklist tests
- [ ] D2. GREEN: `get_checklist` in `service.py`
- [ ] D3. GREEN: wire `prisma checklist show` subgroup in `cli.py` + formatters
- [ ] D4. VERIFY tests pass
- [ ] D5. Commit: `feat(prisma): add checklist show command (P2)`

### Phase E — Finalize
- [ ] E1. Full test run `pytest` green; flake8 clean
- [ ] E2. Update ADR `docs/ADR/PRISMA-0005.md` with P2 additions
- [ ] E3. Update wiki guide
- [ ] E4. Commit: `docs(prisma): document P2 commands`
- [ ] E5. Update `~/.claude/primer.md` — mark P2 complete

## Notes

- `bibtexparser` already in deps. Reuse author-split idiom from `src/PRISMAreview/addbib/readbib.py:10-37`.
- Dedup pattern: `session.flush()` + `IntegrityError` + savepoint rollback per-item (spec §1.Dedup).
- `@dataclass(frozen=True) ImportResult` per global immutability rule.
- Target: ~28 new tests, total ~78 in `test_prisma_cli.py`.
