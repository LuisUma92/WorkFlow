# Implementation plan — Wave 3: bibliography-dialect remainder + PRISMA P1/P3 closure

Request: `tasks/requests/2026-06-01-bibliography-dialect-biblatex-bibtex-compat.md`
Request: `tasks/requests/2026-06-03-prisma-to-literature-note.md`
ADR: `docs/ADR/0019-bibliography-dialect-biblatex-native-model.md` (**Accepted**)
ADR: `docs/ADR/0020-bibliography-module-boundary.md` (**Accepted**)
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase, forward-only
migrations (ITEP-0010). Phases ship independently; commit at each GREEN.

---

## Verified anchors (confirmed in code)

### Bibliography dialect (2026-06-01 request / ADR-0019)

- `workflow.bibliography.dialect` (`src/workflow/bibliography/dialect.py`) —
  `BIBTEX_TO_BIBLATEX` alias map (L23-46), `to_biblatex()`/`to_bibtex()` (L49-127),
  `classify_entry_type()`/`downgrade_entry_type()` (L128-166). Single alias-translation
  module, as the request requires.
- `workflow.prisma.importer.TRANSLATED_BIB_KEYS` (`src/workflow/prisma/importer.py:118-123`)
  builds itself FROM `_dialect.BIBTEX_TO_BIBLATEX` (no duplicated mapping) — P1 wiring
  confirmed, not re-derived locally.
- `BibEntry` model (`src/workflow/db/models/bibliography.py:107-238`): `date` (String(50),
  L196, verbatim EDTF literal), `chapter` (String(200), L197), `type` (String(100), L202,
  entry subtype), `publication_date`/`year` kept as derived/backward-compat (L172, docstring
  L113-118). `Author.name_prefix`/`name_suffix` (L92-93). All columns landed via migration
  `0012_bib_dialect_columns.py`.
- `bibkey` column: `Mapped[str | None] = mapped_column(String(200), default=None)`
  (`bibliography.py:130`) — **no `unique=True`, no `NOT NULL`, no reconciliation migration**.
  Grep across `src/workflow/db/migrations/global/*.py` for `unique.*bibkey`/`reconcile`
  returns nothing. This is the one genuinely open acceptance box.
- Exporter: `workflow.prisma.exporter.export_bib_entries` (`src/workflow/prisma/exporter.py:93`)
  dispatches `_entry_to_biblatex`/`_entry_to_bibtex` (aliased from `render.py:353,379`) by
  `--dialect`; `dialect.downgrade_entry_type` used for bibtex-only-type downgrades
  (`@online→@misc`, etc., covered by `tests/workflow/prisma/test_bib_export_dialect.py`
  L192-197 `test_online_becomes_misc`/`test_online_gets_howpublished`).
- Round-trip tests already exist and green: `tests/workflow/bibliography/test_dialect.py:348-395`
  (`test_bibtex_roundtrip`, `test_biblatex_roundtrip`, `+_new_aliases` variants) and
  `tests/workflow/prisma/test_bib_export_dialect.py:364-382` (`test_*_survives_round_trip`).
- `docs/ADR/0019-*.md` frontmatter: `status: Accepted` (already flipped — not pending).
- CLAUDE.md Module Structure section (`/home/luis/02-Projects/WorkFlow/CLAUDE.md`) has
  **no bullet** for `src/workflow/bibliography/` (dialect.py/render.py/inheritance.py) —
  only a `BibContent` locus-column mention under `db/models/bibliography.py` (L43) and a
  PRISMA-CLI-surface bullet (L98) that documents the `--dialect`/`--resolve-xref` flags but
  not the module itself. This is the tracked doc-lag the roadmap flagged.
- Migration harness: `src/workflow/db/migrations/global/`; latest = `0016_exercise_type_normalize_legacy_codes.py`
  → next = `0017_`.

### PRISMA C0 (2026-06-03 request) — P1 and P3

- `workflow.prisma.accept_to_note` (`src/workflow/prisma/accept_to_note.py`) — single
  (`accept_to_note`, `accept_to_note_json`) + bulk (`accept_all_to_note`,
  `accept_all_to_note_json`) entry points. Reuses `workflow.bibliography.render.entry_to_biblatex`
  (A5 renderer) — no second renderer written.
- CLI: `workflow prisma bib accept-to-note` fully wired
  (`src/workflow/prisma/cli.py:392-465`) — positional `BIBKEY`, `--bib-entry-id`,
  `--keyword-id`, `--review-record-id`, `--vault-root`, `--dry-run`, `--json`,
  `--all-accepted` (mutex-guarded against positional `bibkey`, requires `--keyword-id`,
  L440-447). `BibKeyAmbiguous` caught and surfaced (L464).
- `validate_note_frontmatter` schema extended: `prisma_review_record_id`,
  `prisma_keyword_id`, `origin` all present (`src/workflow/validation/schemas.py:124-126,
  349-353`).
- Tests: `tests/workflow/prisma/test_accept_to_note.py` (single/dry-run/idempotency/
  ambiguous-bibkey/no-record fallback) + `tests/workflow/prisma/test_accept_to_note_bulk.py`
  (bulk path) both exist.
- nvim P3: `nvim-plugin/lua/workflow/prisma_note.lua` + registration in
  `nvim-plugin/lua/workflow/commands.lua:316-320` (`WorkflowPrismaAcceptToNote` user
  command) + spec `nvim-plugin/tests/plenary/prisma_note_spec.lua`.
- Docs: CLAUDE.md L101 (`workflow notes create` Wave D bullet, references
  `accept_to_note.accept_to_note`) and L107 (nvim plugin bullet, `:WorkflowPrismaAcceptToNote`
  Wave C3); `nvim-plugin/doc/workflow.txt:295-318` (`workflow-prisma-accept-note` section).
- **Conclusion: P1 and P3 of the 2026-06-03 request are fully shipped, tested, and
  documented.** The roadmap's Wave 3 item 7 framing ("PRISMA P1/P3 pending") is stale —
  confirmed by direct code read, not by re-trusting the roadmap's own flagged contradiction
  (roadmap already flagged the C0-rewrite-vs-implementation confusion; this plan additionally
  confirms the *implementation* itself, not just the rewrite, is done).
- P2 (screening-transition hook) remains explicitly deferred by the request itself
  ("Defer until the interactive screening CLI matures") — out of scope for this wave, not
  a gap.

---

## SHIPPED / PENDING table (per acceptance box)

| # | Source | Box | Status | Evidence |
|---|--------|-----|--------|----------|
| 1 | bib-dialect P1 | bibtex spellings populate biblatex columns, tested | **SHIPPED** | `dialect.py:23-46`, `importer.py:118-123`, `tests/workflow/bibliography/test_dialect.py` |
| 2 | bib-dialect P2 | `date` EDTF verbatim round-trip; `chapter`/`type` persist | **SHIPPED** | `bibliography.py:196-202`; migration `0012_bib_dialect_columns.py`; `test_bib_export_dialect.py:86-97` |
| 3 | bib-dialect P2 | `bibkey` unique/non-null post-migration, existing rows reconciled | **PENDING** | no `unique=True` on `bibliography.py:130`; no reconciliation migration found |
| 4 | bib-dialect P3 | import→export biblatex field-equivalent round-trip; bibtex downgrade + validates | **SHIPPED** | `exporter.py`; `test_dialect.py:348-395`; `test_bib_export_dialect.py:364-382,192-197` |
| 5 | bib-dialect | alias translation in exactly one module | **SHIPPED** | `dialect.py` sole source; consumed by importer + render |
| 6 | bib-dialect | Docs: CLAUDE.md bullet + ADR-0019 Proposed→Accepted | **PARTIAL** — ADR **SHIPPED** (already Accepted); CLAUDE.md module bullet **PENDING** (no `src/workflow/bibliography/` Module Structure entry) |
| 7 | PRISMA C0 | P1 CLI `accept-to-note` (single + bulk + guards) | **SHIPPED** | `cli.py:392-465`; `accept_to_note.py`; both test files present |
| 8 | PRISMA C0 | Validator schema extended (bibkey/prisma_*/origin) | **SHIPPED** | `schemas.py:124-126,349-353` |
| 9 | PRISMA C0 | P3 nvim `:WorkflowPrismaAcceptToNote` | **SHIPPED** | `commands.lua:316-320`; `prisma_note.lua`; `prisma_note_spec.lua`; `workflow.txt:295-318` |
| 10 | PRISMA C0 | Docs: CLAUDE.md + `workflow.txt` | **SHIPPED** | `CLAUDE.md:101,107`; `workflow.txt:295-318` |
| 11 | PRISMA C0 | P2 screening-transition hook | **OUT OF SCOPE (deferred by request itself)** | request text: "Defer until the interactive screening CLI matures" |

**Counts:** 6 SHIPPED, 1 PARTIAL (doc-only), 1 PENDING (real code), 1 deferred/out-of-scope
(not counted as a gap), across bibliography (6 boxes) + PRISMA (4 boxes + 1 deferred).

---

## Target / design

End state: (1) the bibliography-dialect request's tracking is honest — either every box is
checked with evidence, or the one genuinely open box (`bibkey` unique identity) ships via a
real migration with null/dup reconciliation; (2) the PRISMA C0 request is formally closed
(`status: closed`, `closed_on`, all acceptance boxes checked) since P1/P3 are proven shipped
— no new PRISMA code is written by this wave.

### Commands / API surface

No new CLI surface for PRISMA (already complete). Bibliography: no new command; the only
runtime change is a schema constraint tightening on `BibEntry.bibkey`.

```bash
# unchanged surface — verifying existing behaviour under the new constraint
workflow prisma bib recompute-keys --dry-run
workflow prisma bib recompute-keys --all --yes
```

Expected output / JSON shape: unchanged (no CLI-visible contract change from F1).

---

## Resolved design rules

- **F0 is audit-only**: F0 produces the SHIPPED/PENDING table above and updates the two
  request files' frontmatter/checkboxes/progress logs. No `src/` edits in F0.
- **F1 scope is exactly box #3** (bibkey unique identity) — everything else in the
  bib-dialect request is already shipped; F1 does **not** re-implement P1/P2/P3.
- **Reconciliation strategy for dup/null bibkeys**: reuse
  `workflow.bibliography.bibkey.calculate_bibkey` (`src/workflow/bibliography/bibkey.py:125`)
  — the same deterministic algorithm `workflow prisma bib recompute-keys` already uses — to
  backfill null bibkeys before the constraint lands; for surviving duplicates after
  recomputation, append a disambiguating suffix (`-2`, `-3`, …) in deterministic `id` order
  (never silently drop rows). ★ confirm with user: is a numeric-suffix fallback acceptable,
  or should duplicate-after-recompute abort the migration for manual review?
- **Migration idempotency**: follow the `PRAGMA table_info` probe pattern already used in
  `0012_bib_dialect_columns.py`/`0014_bib_promoted_columns.py` — check for the unique index
  by name before creating it (`sqlite_master` probe), not just column existence.
- **F1 becomes closure-only if F0 finds otherwise**: if further F0 re-verification surfaces
  that box #3 also already has a migration this plan missed, F1 is a no-op closure of the
  request only — this must be stated explicitly in the phase's commit message, not silently
  skipped.
- **CLAUDE.md doc-lag (box #6)**: fold into F1 — add the missing `src/workflow/bibliography/`
  Module Structure bullet (dialect.py/render.py/inheritance.py/bibkey.py/service.py) alongside
  the migration, since both are "close the tracked gap" work on the same request.
- **PRISMA closure (F2+F3 merge)**: because both P1 and P3 are independently verified shipped
  by F0, F2 ("PRISMA P1") and F3 ("PRISMA P3") collapse into a single closure phase — there is
  no implementation work to split across two phases. This plan keeps them as separate labeled
  phases per the template's structure but flags both as doc-only.

---

## Decisions — LOCKED (user, 2026-07-05)

1. F0 is doc-only reconciliation against live code — no code changes, only request-file
   status/checkbox/progress-log updates (per director's task framing).
2. F1 scope is bounded to whatever F0's table marks PENDING — if the table shows all-shipped,
   F1 becomes a documentation-closure phase and must say so explicitly, not silently expand.
3. Module-boundary parallelization: track-bibliography (`src/workflow/bibliography/**`) and
   track-prisma (`src/workflow/prisma/**`) may run in parallel; read-only cross-reads of
   `BibEntry`/`bib_entry_id` are fine; no concurrent writes to either module's files.

---

## Phases

### Phase 0 — Reconciliación doc-lag (sonnet, no code)

**Goal:** Close the tracking gap the roadmap flagged — the bib-dialect request's checkboxes
are stale relative to shipped code; the PRISMA C0 request's P1/P3 are shipped but the request
is still `status: open`.

**Work (no RED/GREEN — this phase edits `tasks/requests/*.md` only):**

- `tasks/requests/2026-06-01-bibliography-dialect-biblatex-bibtex-compat.md`: check boxes
  #1, #2, #4, #5 (SHIPPED, evidence above); leave #3 (bibkey unique) unchecked — that is F1's
  job; add a progress-log entry dated 2026-07-05 citing this plan and the SHIPPED/PENDING
  table; do **not** flip `status` to closed yet (F1 still open).
- `tasks/requests/2026-06-03-prisma-to-literature-note.md`: check all P1/P3-related
  acceptance boxes (evidence above); flip `status: closed`, `closed_on: 2026-07-05`,
  `closed_by: <this session>`; P2 box stays explicitly marked "deferred by request, not a
  gap" rather than checked or silently dropped.
- Update `docs/ADR/0019-*.md` "landed" note if it doesn't already reflect P1/P2(partial)/P3
  shipped state (ADR status already Accepted — verify its body text, not just frontmatter,
  matches reality).

**Commit point:** doc-only commit; no reviewer-esquema (no code); director eyeballs the
table before F1 starts (wait-gate 1).

---

### Phase 1 — Bibliography remainder: `bibkey` unique identity (track-bibliography)

**Goal:** The one real PENDING box — make `bibkey` the unique, non-null identity column,
reconciling existing null/duplicate values first (forward-only, ITEP-0010).

**RED tests** (`tests/workflow/bibliography/test_bibkey_unique_migration.py`):

- Seed a copy-of-schema DB with: one `BibEntry` with `bibkey IS NULL`, two `BibEntry` rows
  sharing the same non-null `bibkey`, one already-unique row — assert pre-migration state.
- Run migration `0017_bibkey_unique_identity.py` — assert every row has a non-null bibkey
  post-migration (null rows backfilled via `calculate_bibkey`).
- Assert no two rows share a bibkey post-migration (duplicates get a deterministic numeric
  suffix in `id` order).
- Assert a fresh `INSERT` with a colliding bibkey now raises `IntegrityError` (unique
  constraint enforced at the DB level).
- Migration idempotency test: running the migration twice is a no-op the second time
  (`PRAGMA index_list` probe finds the unique index already present).

**GREEN impl** — files touched:

- `src/workflow/db/migrations/global/0017_bibkey_unique_identity.py` (new migration) —
  backfill nulls via `workflow.bibliography.bibkey.calculate_bibkey`, disambiguate surviving
  duplicates, then `CREATE UNIQUE INDEX` on `bib_entry.bibkey`.
- `src/workflow/db/models/bibliography.py` (edit) — `bibkey` gains `unique=True`
  (nullable stays `False` if the migration guarantees no nulls survive; confirm against ★
  decision above).
- `CLAUDE.md` (edit) — add the missing `src/workflow/bibliography/` Module Structure bullet
  (box #6) alongside noting the migration.
- `tasks/requests/2026-06-01-*.md` (edit) — check box #3, flip `status: closed`.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P1.

---

### Phase 2 — PRISMA P1 closure (documentation only, track-prisma)

**Goal:** Confirm, in writing, that `workflow prisma bib accept-to-note` (single + bulk) is
production-complete — no code changes expected; this phase exists to make the closure
auditable per-phase rather than folded silently into F0.

**Verification tasks** (not RED/GREEN — no new tests expected; run existing suite as proof):

- Run `tests/workflow/prisma/test_accept_to_note.py` and
  `tests/workflow/prisma/test_accept_to_note_bulk.py` explicitly and record pass counts in
  the phase's commit message.
- Spot-check the CLI help text (`workflow prisma bib accept-to-note --help`) matches the
  request's documented flag surface exactly (bibkey, `--bib-entry-id`, `--keyword-id`,
  `--review-record-id`, `--vault-root`, `--dry-run`, `--json`, `--all-accepted`).
- **If this spot-check finds any gap**, this phase stops being doc-only and a RED/GREEN
  sub-phase is added — do not silently patch.

**Commit point:** if no gap found, a doc-only commit noting "P1 verified shipped, no code
change" — no reviewer-esquema needed (no code diff). If a gap is found, treat as a new
Phase 2b with full TDD + reviewer-esquema.

---

### Phase 3 — PRISMA P3 closure (documentation only, track-prisma)

**Goal:** Same as Phase 2, for the nvim `:WorkflowPrismaAcceptToNote` command.

**Verification tasks:**

- Run `nvim-plugin/tests/plenary/prisma_note_spec.lua` explicitly, record pass/fail.
- Confirm `nvim-plugin/doc/workflow.txt:295-318` and `CLAUDE.md:107` both describe the
  command's actual behavior (single vs bulk prompt, error-on-stderr, open-on-success).
- **If this spot-check finds any gap**, same escalation rule as Phase 2.

**Commit point:** doc-only commit (or escalate to full TDD phase if a gap surfaces).

---

## Risks / out of scope

- **In scope:** bibkey unique-identity migration (F1); doc-reconciliation of both requests
  (F0); verification (not re-implementation) of PRISMA P1/P3 (F2/F3).
- **Out of scope:** PRISMA P2 (screening-transition hook) — explicitly deferred by the
  request itself; PRISMA-0005 dedup logic changes beyond what the bibkey-unique migration
  forces; nvim/PRISMAreview-Django UI changes (not required by the C0 request text — no ★
  gate needed since F0 confirms no such requirement).
- **Risk:** the bibkey-unique migration mutates existing data (backfill + dedup-suffixing)
  — gate on a dry-run mode and a DB backup step before `--yes`, mirroring
  `workflow prisma bib recompute-keys`'s existing `--dry-run`/`--all`/`--yes` pattern.
  ★ confirm the numeric-suffix-on-duplicate fallback (see Resolved design rules) before
  writing the migration.
- **Risk:** if F0's re-verification (director checkpoint before F1) disagrees with this
  plan's table, F1 must be re-scoped before implementation — do not proceed on stale
  assumptions (this is exactly the failure mode Wave 3 exists to close out).
- No schema migration expected for F2/F3 (doc-only phases).

---

## Orquestación

| Role | Assignment |
|------|------------|
| sonnet | F0 audit/doc edits; F1 impl (migration + model + CLAUDE.md); F2/F3 verification write-ups |
| opus | Review gate on F1's migration (data-mutating — highest risk phase this wave) |
| haiku | git-ops: commits per phase, `git status` hygiene |
| parent (director) | Runs the isolated suite post-F1; approves F0's table before F1 starts (wait-gate 1); confirms ★ decision (numeric-suffix fallback) before migration is written |

**Paralelización:** track-bibliography (`src/workflow/bibliography/**`, F1) ‖ track-prisma
(`src/workflow/prisma/**`, F2/F3) — clean module boundary; read-only shared reads of
`BibEntry`/`bib_entry_id` are fine in both tracks; no concurrent writes to either module's
files.

**Wait-gates:**

1. F1 waits on F0 — do not plan/implement against stale tracking; director reviews F0's
   table before F1 starts.
2. No dependency on Wave 0–2 — this wave may run ahead if another wave blocks (stated
   explicitly per the roadmap's own note that Wave 3 has "no upstream Wave gate").
3. Migrations: global rule — never two migrations concurrently in flight; this wave's
   migration is `0017_` at write time; re-check `ls src/workflow/db/migrations/global/`
   immediately before writing the file in case another wave landed `0017_` first.
4. reviewer-esquema pre-commit on F1 (data-mutating phase); F2/F3 skip reviewer-esquema
   unless they escalate to a code phase.
5. Director runs the full isolated suite (`WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q
   --ignore=tests/test_database.py`) post-merge of F1.

---

## Verification (each phase)

```bash
# Isolated suite — never touches live DB
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py

# Lint
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10

# F1 live dry-run (on a COPY of the live DB, never the original)
# cp ~/.local/share/workflow/workflow.db /tmp/workflow-test.db
# WORKFLOW_DATA_DIR=/tmp workflow db migrate-xdg --dry-run  # sanity check location only
# then run the new migration against /tmp copy via the standard migration harness,
# never the live DB directly

# F2/F3 targeted verification
uv run pytest -q tests/workflow/prisma/test_accept_to_note.py tests/workflow/prisma/test_accept_to_note_bulk.py
# (nvim) cd nvim-plugin && make test  # or plenary runner per nvim-plugin/README
```
