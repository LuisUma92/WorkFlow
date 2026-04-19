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

### Phase A — `bib import`
- [ ] A1. RED: write ~12 import tests in `tests/workflow/test_prisma_cli.py`
- [ ] A2. GREEN: create `src/workflow/prisma/importer.py` with `ImportResult`, `import_bib_file`, helpers
- [ ] A3. GREEN: wire `prisma bib import` command in `cli.py`
- [ ] A4. GREEN: `format_import_result_table/json` in `formatters.py`
- [ ] A5. VERIFY: `pytest tests/workflow/test_prisma_cli.py -k import`
- [ ] A6. Commit: `feat(prisma): add bib import command (P2)`

### Phase B — `bib export`
- [ ] B1. RED: ~6 export tests (including import→export round-trip)
- [ ] B2. GREEN: create `src/workflow/prisma/exporter.py` with `export_bib_entries`, `_entry_to_bibtex`, `_join_authors`
- [ ] B3. GREEN: wire `prisma bib export` in `cli.py` (validate --status requires --keyword-id)
- [ ] B4. VERIFY tests pass
- [ ] B5. Commit: `feat(prisma): add bib export command (P2)`

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
