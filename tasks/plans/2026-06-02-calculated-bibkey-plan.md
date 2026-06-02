# Implementation plan — Calculated bibkey enforcement

Request: `tasks/requests/2026-06-02-calculated-bibkey-enforcement.md`
Related: ADR-0019 (supersedes rejected P2.4 `UNIQUE(bibkey)`).
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase, forward-only
migrations (ITEP-0010) — though NO migration is expected (all columns already exist).

## Verified anchors (confirmed in code)

- `BibEntry.edition: Mapped[int|None]` (SmallInteger) — **exists**, no migration needed.
- `BibEntry.volume: Mapped[str|None]` (String(20)) — STRING; may be non-numeric
  ("II", "3rd") → must normalize to int for `V<NN>`.
- `BibEntry.bibkey: Mapped[str|None]` nullable, NON-unique (Option A — keep).
- `BibEntry.entry_type: Mapped[str|None]` — drives book vs article classification.
- `Author.last_name` / `name_prefix` (von) — surname source.
- `BibAuthor.first_author: bool` flag marks the first `author`-type link.
- Importer: `bibkey` currently = source `.bib` `ID` verbatim (`TRANSLATED_BIB_KEYS`
  `bibkey→ID`); `_split_authors(author_string)` returns ordered
  `(first,last,prefix,suffix)`; `_process_authors` sets `first_author=(idx==0)`.
- Entry-type knowledge already centralized in `workflow.bibliography.dialect`
  (`downgrade_entry_type`, `BIBLATEX_TO_BIBTEX_TYPES`) — extend there, single source.

## Target format (from request)

- **Book** (book-like types): `<surname:lc><year:04d>[V<volume:02d>]E<edition:02d>`
  (`V…` only when volume present). e.g. `knuth1997V03E03`, `goldstein2001E03`.
- **Article** (article-like types): `<surname:lc><year:04d>V<volume:02d>`.
  e.g. `einstein1905V17`.

## Resolved design rules (defaults — confirm the ★ ones with user)

- **Surname**: first author's `last_name`, drop `name_prefix` (von), strip accents→
  ascii, keep `[a-z]` only, lowercased. "van Beethoven" → `beethoven`.
- **year**: `year:04d`. ★Missing year → token `0000`.
- **volume**: numeric-coerce (`int(re.sub(r"\D","",volume))`); non-numeric/empty →
  treat as absent (book) / ★`V00` (article). Pad `02d`.
- **edition (books)**: `E<edition:02d>`; ★missing edition → `E01` (assume 1st ed).
- **Article missing volume**: ★`V00` (keeps the `V` segment mandatory per format).
- **author missing**: ★token `anon`.
- **Type classification** (in `dialect`): book-like = {book, inbook, incollection,
  collection, mvbook, bookinbook, suppbook, manual, proceedings, inproceedings}?
  ★ — at minimum {book, inbook, incollection, collection}. Article-like = {article,
  periodical, suppperiodical}. ★Other/unknown types → article form w/o forcing V
  (`<surname><year>[V<vol>]`).
- **Collision disambiguation**: if the calculated key already exists for a row with a
  DIFFERENT identity `(title,year,volume)`, append `a`,`b`,… The ambiguous-bibkey
  feature still permits true duplicates (same identity) — disambiguation only fires
  for distinct works that collide.

## Decisions — LOCKED (user, 2026-06-02)

1. **Importer default**: KEEP source `ID` verbatim; calculate ONLY when the `.bib`
   omits/empties the ID. Add `--recompute-bibkeys` flag to force recompute.
2. **Recompute-keys (P3) default**: FILL-MISSING-ONLY (never overwrite existing
   keys); `--all` flag to force full normalize.
3. **Fallbacks/format LOCKED**: missing year→`0000`, missing author→`anon`, book
   missing edition→`E01`, article missing volume→`V00`; surname strips von-particle +
   accents→ascii, `[a-z]` lowercased. Book-types = {book, inbook, incollection,
   collection}; all other types → article form (`<surname><year>[V<vol>]`, V only if
   volume present).

## Phase 1 — pure `calculate_bibkey` (NO DB, NO migration)

P1.1 `src/workflow/bibliography/bibkey.py` (new):
   - `calculate_bibkey(*, surname, year, volume, edition, entry_type) -> str` —
     pure, reuses `dialect` for book/article classification. Internal helpers:
     `_normalize_surname`, `_coerce_int`, `_classify(entry_type)->{"book","article","other"}`.
   - Add `is_book_type`/`is_article_type` (or `classify_entry_type`) to
     `workflow.bibliography.dialect` (single source of type knowledge).
P1.2 Tests `tests/workflow/bibliography/test_bibkey.py`: each type form, optional-vol
   branch, padding (`V03`,`E03`), particle strip ("van Beethoven"→beethoven), accents,
   non-numeric volume, all fallbacks, unknown type.
P1.3 flake8 + suite green. → commit, reviewer-esquema.

## Phase 2 — importer integration

P2.1 Importer: a `generate_bibkey_for_entry(...)` that pulls first author's surname
   (from the parsed `_split_authors` list[0]) + year/volume/edition/entry_type and
   calls `calculate_bibkey`. Wire per Decision ★1 (default: only when source `ID`
   missing/empty; flag `--recompute-bibkeys` to force; warn-on-disagree if chosen).
P2.2 Collision disambiguation against existing + in-batch keys (reuse a SELECT-based
   helper; do NOT add a DB constraint).
P2.3 Tests: no-ID `.bib` → calculated key; explicit-ID path per decision; disambig of
   two distinct works colliding; ambiguous-but-same-identity still allowed.

## Phase 3 — maintenance CLI

P3.1 `workflow prisma bib recompute-keys [--dry-run] [--fill-missing|--all]`:
   backup the DB first, report a collision/changes table, apply per Decision ★2.
   NEVER touch live DB without a copy; respect `WORKFLOW_DATA_DIR`.
P3.2 Tests (isolated `WORKFLOW_DATA_DIR`): dry-run reports without writing; fill-missing
   vs all; backup created; idempotent on second run.
P3.3 Update CLAUDE.md prisma row + ADR-0019 note (calculated bibkey landed).

## Sequencing / risk
- P1 pure + safe; ship first. P2 changes import behavior (gate on Decision ★1).
- P3 mutates existing data (gate on backup + dry-run + Decision ★2).
- No schema migration (edition/volume/bibkey all present).

## Verification (each phase)
- `WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py`
  (isolation fixture now also enforces this — `b9f4091`).
- `uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10`
- P3: real CLI dry-run on a COPY of the live DB; diff before/after.
