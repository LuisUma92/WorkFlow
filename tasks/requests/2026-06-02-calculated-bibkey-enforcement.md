# Request — Enforce a calculated bibkey format

Date: 2026-06-02
Status: RESOLVED — Implemented (executed via `tasks/plans/2026-06-02-calculated-bibkey-plan.md`;
`workflow prisma bib recompute-keys` CLI shipped, `src/workflow/prisma/cli.py:484`; closure
annotation applied retroactively 2026-07-05 per `tasks/audit/2026-07-05-tasks-adr-completeness-audit.md`
Summary #6)
Related: ADR-0019 (bibliography dialect); supersedes the rejected P2.4 `UNIQUE(bibkey)`
identity change (see `tasks/plans/2026-06-01-bibliography-dialect-plan.md`).

## Background / why

ADR-0019 plan P2.4 proposed `UNIQUE(bibkey)`. That was **rejected** (2026-06-02):
the codebase deliberately supports duplicate bibkeys — the "ambiguous bibkey" feature
(`get_bib_entry_by_bibkey` raises `BibKeyAmbiguous`; exercise sync, content link-bib,
maturation all tolerate it). `tests/workflow/bibliography/test_service.py:47` documents
bibkey as intentionally non-unique at the DB layer.

So instead of a DB uniqueness constraint, we want bibkeys to be **deterministically
calculated** from entry metadata, so two genuinely-distinct entries naturally get
distinct keys and accidental duplicates collide predictably — without forbidding the
ambiguous case at the schema level.

## Desired bibkey format

Lowercase, no spaces. First-author surname + 4-digit year, then type-specific suffix.

- **Book** (`@book`, `@inbook`, `@collection`, …):
  `<firstAuthorLastName:lower><year:04d>[V<volume:02d>]E<edition:02d>`
  - `V<volume:02d>` segment is **optional** — emitted only when `volume` is present.
  - `E<edition:02d>` edition segment included for books.
  - Examples: `knuth1997V03E03`, `goldstein2001E03` (no volume).

- **Article** (`@article`, and journal-like entries):
  `<firstAuthorLastName:lower><year:04d>V<volume:02d>`
  - Examples: `einstein1905V17`.

### Field semantics / edge rules (to settle during design)
- `firstAuthorLastName`: surname of the first author, lowercased, stripped to `[a-z]`
  (drop accents/diacritics → ascii; drop von/jr particles? — DECIDE: likely use
  `name_prefix`-stripped surname, e.g. "van Beethoven" → `beethoven`).
- `year:04d`: zero-padded 4 digits from `year` (derived from `date` per ADR-0019).
  Missing year → fallback token (e.g. `0000`) or `nodate`. DECIDE.
- `volume:02d` / `edition:02d`: zero-padded 2 digits; non-numeric volume/edition
  (e.g. "II", "3rd") → normalize to int where possible, else omit/raise. DECIDE.
- Missing author → fallback (e.g. `anon`). DECIDE.
- **Collision disambiguation**: when the calculated key already exists for a *different*
  entry, append `a`, `b`, … (the ambiguous-bibkey feature still permits true duplicates,
  so disambiguation is for distinct entries that happen to collide).

## Scope

1. A pure helper `calculate_bibkey(entry_fields, *, entry_type) -> str` in
   `src/workflow/bibliography/` (DB-free; reuse `dialect`/author-parsing primitives).
   Needs `firstAuthorLastName`, `year`, `volume`, `edition`, `entry_type`.
2. Importer: when a source `.bib` omits an ID, generate via `calculate_bibkey`
   (replaces the ad-hoc slug). When an ID is present, keep the source ID (verbatim)
   unless a `--recompute-bibkeys` flag is given. DECIDE default.
3. A maintenance command to recompute/normalize bibkeys for existing rows
   (e.g. `workflow prisma bib recompute-keys [--dry-run]`), with a backup +
   collision report. Operates on the configured DB; NEVER the live DB without a copy.
4. Tests: format per type, optional-volume branch, padding, particle stripping,
   collision disambiguation, importer no-ID path.

## Non-goals
- No DB UNIQUE(bibkey) constraint (rejected — see Background).
- No removal of the ambiguous-bibkey feature.

## Dependencies / verify before design
- Confirm `BibEntry` has an `edition` column (and its type). If absent, adding it is a
  prerequisite (additive migration, ITEP-0010).
- Reuse `_split_authors` / `name_prefix` from the importer (ADR-0019 P2a) for surname.
- Decide author-particle handling consistently with P2a von/jr parsing.

## Open questions (resolve in plan)
- Recompute existing keys, or only fill missing? (data-migration risk)
- Behavior when source `.bib` provides an explicit ID that disagrees with the
  calculated key — keep source, warn, or overwrite?
- Fallback tokens for missing year/author/volume.
