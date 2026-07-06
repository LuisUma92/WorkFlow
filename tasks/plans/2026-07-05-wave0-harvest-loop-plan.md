# Implementation plan — Wave 0: Fleeting-monolith harvest loop (D1-D3)

Request: n/a — sourced directly from `tasks/roadmap/2026-07-05-post-freeze-implementation-roadmap.md`
(Wave 0) and the approved design spec below.
ADR: none new — reuses ITEP-0011, ITEP-0012 (2026-07-04 slug-only amendment), ADR-0018.
Design spec: `docs/superpowers/specs/2026-07-05-fleeting-harvest-design.md` (Status: Approved,
approach B, user-approved 2026-07-05) — authoritative for algorithm/decisions; this plan only
sequences it into TDD phases.
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase, forward-only
migrations (ITEP-0010). Phases ship independently; commit at each GREEN.

---

## Verified anchors (confirmed in code)

- `src/workflow/lecture/note_splitter.py::split_notes_file` (lines 35-133 per spec §5) —
  writes files + computes `\input{}` lines; zero DB interaction. Matches spec citation.
- `src/workflow/lecture/cli.py` — `split` command is the `@lectures.command()` block
  starting at line 73, `def split(...)` at line 90, ending ~line 118 (calls only
  `split_notes_file`, then prints `SplitResult` fields; no `Session`/DB import in this
  command). Spec cites `cli.py:90-119` — confirmed, matches the `def split` body exactly.
- `src/workflow/notes/sync.py::_sync_note_concepts` — confirmed at **lines 293-320**
  (matches spec's `sync.py:293-320` exactly). Calls
  `resolve_concepts(codes, session, strict=strict)`, upserts `NoteConcept` only for
  `found` concepts via `upsert_note_concept`.
- `src/workflow/notes/sync.py` — Pass 2-5 write loop: `_run_write_passes` (lines
  366-388) + `sync_vault` (lines 391-449). Spec cites the combined range
  `sync.py:366-449` for "the Pass 2-5 orchestration D1 must reuse" — confirmed as a
  two-function span, not a single function; **D1's extraction target is
  `_run_write_passes`**, which already takes `(session, note_data, scope_prefix,
  current_filenames, strict_concepts, rebuild_edges, report)` — this is *already*
  factored out of `sync_vault`'s per-path loop and operates on a `note_data: list[tuple[Note,
  str, dict]]` built from Pass 1. The missing piece per D1 is not extracting
  `_run_write_passes` (done) but building an equivalent Pass-1 note_data list from an
  explicit file list instead of `scan_root.rglob("*.md")` — i.e. `sync_note_files(paths,
  session, ...)` needs to replicate `sync_vault`'s Pass-1 loop (lines ~409-441: `_parse_md`,
  zettel_id guard, `_upsert_note_row`, `_upsert_note_labels`, `_upsert_note_citations`) over
  an explicit `paths` list, then call the existing `_run_write_passes` for Pass 2-5.
  `scope_prefix`/`current_filenames` for the orphan-drop pass (`_drop_orphan_links`) need a
  defined value for the file-list case — **[UNCLEAR]**: the spec does not say whether
  `sync_note_files` should run orphan-drop at all (a partial file list is not "all current
  filenames under scope"); running it naively would drop links for every note NOT in
  `paths` but under the same scope_prefix. Resolved design rule below locks this as
  "orphan-drop pass is skipped entirely in `sync_note_files`" — file-list sync only adds/
  updates, never deletes based on absence.
- `src/workflow/notes/sync.py::_parse_md` — confirmed at line 47 (`def _parse_md(path:
  Path) -> tuple[dict[str, object], str] | None`). Spec's "reuse `_parse_md` or an
  equivalent" for D3 is directly satisfiable by importing this function.
- `src/workflow/concept/service.py::resolve_concepts` — confirmed at **lines 140-169**
  (matches spec exactly). Slug-only: `session.scalars(select(Concept).where(Concept.code
  == code)).first()`, no label fallback anywhere in the function body — confirms the
  2026-07-04 amendment is intact.
- `src/workflow/concept/service.py::add_concept` — confirmed at **lines 201-257** (matches
  spec exactly). Signature: `add_concept(session, *, code, label, content_id, domain,
  parent_code=None, description=None) -> Concept`. Validates via `_validate_slug(code)`
  and `_validate_domain(domain)` before insert — confirms harvest's `domain:
  TODO-REVIEW` placeholder will be rejected by `_validate_domain` at import time, as the
  spec intends (forcing function).
- `src/workflow/concept/cli.py` — existing group has 6 subcommands (`list, show, add,
  tree, rm, rename`), all follow the pattern: `@concept.command(name=...)` → `@click.
  pass_context` → `@with_schema_guard` → `Session(engine)` from `_get_engine(ctx)`. D3's
  `harvest` subcommand does **not** fit this pattern as cleanly — harvest scans notes
  (filesystem), not GlobalBase rows directly for its primary input, but still opens a
  session read-only for the known/unknown partition. New module `src/workflow/concept/
  harvest.py` holds the scan+partition+YAML-emit logic; `cli.py` gets one new thin
  `@concept.command(name="harvest")` wired the same way as the others.
- `src/workflow/importer/engine.py::import_hierarchy` — confirmed present (module
  docstring lines 1-11 lists `import_hierarchy(session, data, *,
  discipline_area_override=None, dry_run=False) -> ImportResult` as the public API);
  `add_concept` (from `concept.service`) is imported and reused inside — confirms ADR-0018
  "single write path" claim; D3 does not need to touch this file (read-only harvest, no
  writes).
- `src/workflow/db/models/knowledge.py::DisciplineArea` — confirmed at line 46, `code:
  Mapped[str] = mapped_column(String(6), unique=True)` — i.e. DDTTAA is a 6-char string;
  trailing 2 chars (`code[-2:]`) is the `AA` letter-pair D3's matching step needs,
  case-insensitive per spec §2 D3 step 5.
- `src/workflow/vault/paths.py::resolve_vault_root` — confirmed at line 19, precedence
  env(`WORKFLOW_VAULT_ROOT`) > `config.yaml` `vault_path` > `DEFAULT_VAULT_ROOT`
  (`~/01-U/0000AA-Vault`) — matches spec's "default (no `--notes`) is the vault root via
  `resolve_vault_root()`" and mirrors `lectures split`'s own `--output-dir` default
  (`cli.py:93-96` per spec, confirmed at cli.py lines 93-96 in the `split` body read above).
- Migration harness: `src/workflow/db/migrations/global/` — **not touched by this wave**;
  D1/D2/D3 are all additive code with zero schema change (confirmed: no new columns/
  tables in the spec's Locked decisions §2; D2 is ops-only against existing schema).

---

## Target / design

End state: the 313-note vault backlog of hand-written `concepts:`/`tags:`/
`relations.derived_from` frontmatter is fully ingested into `NoteConcept`/`Tag`·
`NoteTag`/`NoteEdge` rows, and new concepts born bottom-up in notes (slugs with no
matching `Concept.code` yet) have a mechanical, human-reviewable path into the DB via a
generated skyfolding-delta YAML — without ever weakening the ITEP-0012 slug-only-strict
contract. Three independently-shippable pieces:

- **D1**: `workflow lectures split` gains `--sync/--no-sync` (default on) so newly split
  notes are indexed immediately, via a new `sync_note_files(paths, session, ...)` entry
  point that shares Pass 2-5 (`_run_write_passes`) with `sync_vault`.
- **D2**: one operational run of the existing `workflow notes sync <vault_root>` over the
  whole vault, backfilling everything split before D1 existed. No new code.
- **D3**: new read-only `workflow concept harvest` command that scans notes, partitions
  `concepts:` slugs into known/unknown against the DB, and emits an unknown-only
  skyfolding-delta YAML with `domain: TODO-REVIEW` placeholders, ready for human edit +
  `workflow import`.

### Commands / API surface

```bash
workflow lectures split <source-file> [--output-dir DIR] [--overwrite] [--sync/--no-sync]
workflow notes sync <vault_root>                      # D2 — existing command, ops-only run
workflow concept harvest [--notes DIR|FILE ...] [--out PATH.yaml] [--json]
```

Expected `harvest --json` output shape (per spec §2 D3):

```json
{ "unknown_concepts": 4, "notes_scanned": 27, "out_path": "tasks/harvest/2026-07-05-delta.yaml" }
```

---

## Resolved design rules

- **D1 orphan-drop scope**: `sync_note_files` does **not** run `_drop_orphan_links` —
  file-list sync only ever adds/updates rows for the given files; deletion-by-absence
  stays exclusive to directory-wide `sync_vault`. ★ not in the spec explicitly; flagged
  as an implementation decision, not a locked user decision — confirm before Phase 1 if
  this reading is wrong.
- **D1 file selection**: per spec §2 D1, sync runs over every file in
  `result.files` (`SplitFile`) regardless of `created` flag — both newly-created and
  already-existing-unchanged files get (re-)synced, since sync is idempotent by design.
- **D1 flag semantics**: `--sync` is the default; `--no-sync` restores pre-D1 behavior
  exactly (split-only, zero DB interaction) — verified today's `split` command has no
  DB/Session import at all, so `--no-sync` is simply "do not call the new sync path,"
  no code deletion needed.
- **D1 concept strictness**: `lectures split --sync` never gates on unknown concepts
  (reports via `report.concept_issues`, same shape as `notes sync`'s warnings); D1 does
  not add a `--strict-concepts` flag to `lectures split` — gating remains `notes sync`'s
  job exclusively, per spec §2 D1 explicit statement.
- **D2 precondition**: the `essay` `note_type` enum fix — **already shipped** per
  primer.md (`4283e17`, 2026-07-05, "UNBLOCKED"). D2 has no remaining blocker; it is
  ops-only and may run any time, including during the freeze.
- **D3 write boundary**: harvest never calls `session.add`/`session.commit` — it opens a
  session purely to `select(Concept).where(Concept.code == code)` for the known/unknown
  partition (reusing `resolve_concepts`, not reimplementing the query). Import
  (`workflow import`, `import_hierarchy`) remains the sole concept-creation path.
- **D3 discipline-area matching**: match slug prefix (token before first `-`,
  case-insensitive) against `DisciplineArea.code[-2:]` (trailing `AA` letter pair of the
  6-char DDTTAA code) — per spec §2 D3 step 5 + §6 resolution. Unmatched prefixes go to a
  literal `UNRECOGNIZED-PREFIX` bucket, never silently dropped.
- **D3 domain placeholder**: emitted concept entries always carry `domain: TODO-REVIEW`
  (deliberately invalid against `_TAXONOMY_DOMAINS`) — `add_concept`'s `_validate_domain`
  will reject it at import time until a human fixes it; this is the intended forcing
  function, not a bug to "fix" in implementation.
- **D3 code immutability**: `code:` in the emitted YAML is exactly the slug as found in
  the note, never altered, transliterated, or normalized — it is the join key already
  referenced by every citing note's frontmatter.
- **Fallbacks**: malformed/missing frontmatter on a scanned note → skip file with a
  stderr warning naming the path, continue scanning (mirrors `_parse_md`'s "return
  None → skip" contract); `concepts:` value not a list of strings → same skip-with-
  warning treatment, at file granularity (not per-item, per spec §4 error table).
- **Zero-unknowns case**: no delta file written, exit 0, stdout note "no unknown
  concepts found — nothing to harvest."
- **Collision / disambiguation**: none needed — `--out` explicit path always wins; default
  output path is an implementation choice for Phase 2, MUST NOT default into repo root
  or `data/templates/` (curated/checked-in areas) per spec §2 D3 "`--out`" note. This
  plan locks the default to `tasks/harvest/<timestamp>-delta.yaml` (new `tasks/harvest/`
  subdir, analogous to `tasks/requests/`/`tasks/plans/` but ungoverned by a template
  since it's machine-generated, not human-authored).

---

## Decisions — LOCKED (user, 2026-07-05)

1. Concept referencing stays slug-only strict forever (ITEP-0012 2026-07-04 amendment,
   decision #18 option A) — D3 must not add any label-based resolution path, anywhere.
2. Harvest design approach B is the user-approved shape for D3 (spec header: "Status:
   Approved (approach B, user-approved 2026-07-05)") — this plan implements exactly that
   algorithm, does not re-derive or alternative-propose.
3. D2 has no remaining precondition — runs any time, including during the freeze
   (ops-only exception per the freeze rules in the roadmap's "Durante el freeze se
   permite" section).

---

## Phases

### Phase 1 — D1: `sync_note_files` extraction + `lectures split --sync`

**Goal:** Splitting a monolith immediately indexes its notes (Note/Label/Link/Edge/
Concept rows) without touching `sync_vault`'s directory-wide behavior.

**RED tests** (`tests/workflow/notes/test_sync_note_files.py`,
`tests/workflow/lecture/test_split_sync.py`):

- `sync_note_files([path_a, path_b], session)` on a fixture monolith split into 2+ files
  (one with `relations.derived_from` pointing at the other) → asserts `Note`, `Label`,
  `NoteEdge`, `NoteConcept` rows exist after the call, matching what `sync_vault` would
  produce for the same files.
- Idempotency: call `sync_note_files` twice on the same paths (no re-split) → row counts
  for `NoteConcept`/`NoteEdge`/`Label` unchanged between call 1 and call 2.
- Unknown concept slug in a synced file's `concepts:` → `sync_note_files` returns/reports
  an issue (same shape as `_sync_note_concepts`'s issues), no `NoteConcept` row created for
  that slug, no exception raised.
- `sync_note_files` does NOT drop links for notes outside the given `paths` (regression
  guard for the "orphan-drop skipped" resolved design rule above).
- `lectures split --sync` (default) on a fixture source with 2+ `%>` blocks → after the
  command, `Note`/`NoteConcept`/`NoteEdge` rows exist for the split files (integration,
  via `CliRunner` + a temp DB).
- `lectures split --no-sync` → zero DB rows created; output identical to pre-D1
  (regression test against today's exact stdout format).
- Re-run `split --sync` twice without `--overwrite` → no duplicate rows (idempotency at
  the CLI level, mirrors D1's own idempotency test above but through the command).

**GREEN impl** — files touched:

- `src/workflow/notes/sync.py` (edit) — add `sync_note_files(paths: list[Path], session:
  Session, *, strict_concepts: bool = False, rebuild_edges: bool = False) -> SyncReport`.
  Replicates the Pass-1 loop body (`_parse_md`, zettel_id guard, `_upsert_note_row`,
  `_upsert_note_labels`, `_upsert_note_citations`) over the explicit `paths` list instead
  of `scan_root.rglob("*.md")`, builds the same `note_data` list, then calls
  `_run_write_passes(session, note_data, scope_prefix="", current_filenames=set(),
  strict_concepts, rebuild_edges, report)` with orphan-drop effectively neutralized (see
  resolved design rule) — likely by adding a `skip_orphan_drop: bool` param to
  `_run_write_passes` rather than passing empty sets silently (empty `current_filenames`
  with a real `scope_prefix` would wrongly nuke every note under that prefix; must gate
  explicitly, not rely on empty-set behavior). `sync_vault` itself is unmodified.
- `src/workflow/lecture/cli.py` (edit) — `split` command gains `--sync/--no-sync` flag
  (default `True`); on `--sync`, after `split_notes_file` returns, open a `Session` via
  `init_global_db()` (same pattern as `scan`), call `sync_note_files` on
  `[Path(f.output_path) for f in result.files]`, commit, print a short sync summary line
  (notes synced / concept issues, if any) after the existing split-report output.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P1.

---

### Phase 2 — D3: `workflow concept harvest`

**Goal:** A read-only command turns unresolved concept slugs across a note set into a
human-reviewable, never-DB-writing skyfolding-delta YAML.

**RED tests** (`tests/workflow/concept/test_harvest.py`):

- Fixture: 2 notes referencing `em-foo` (unknown) and `mc-bar` (known, seeded via
  `add_concept` in the test DB). Output YAML contains only `em-foo`, grouped under an
  `EM`-suffixed `DisciplineArea` bucket, with both citing notes listed in a `# cited by:`
  provenance comment; `mc-bar` does not appear anywhere in the output.
- Zero-unknowns case: no file written, exit 0, stdout "no unknown concepts found —
  nothing to harvest."
- Malformed frontmatter (unparseable YAML / missing `id:`): file skipped with a per-file
  stderr warning; run still completes (exit 0) over the remaining well-formed notes.
- `concepts:` value not a list of strings on a note: same skip-with-warning treatment,
  at file granularity.
- Slug prefix matching no known `DisciplineArea` trailing-AA pair → grouped under literal
  `UNRECOGNIZED-PREFIX` bucket, still emitted with full provenance.
- Round-trip: harvest → hand-edit `label`/`domain`/`content` in the delta → `workflow
  import` the delta → re-run harvest on the same notes → the previously-unknown slug no
  longer appears in the new delta.
- `--json`: assert exact key set `{"unknown_concepts", "notes_scanned", "out_path"}`.
- `--out PATH.yaml`: writes to the given path exactly, no default-path fallback file
  also written.
- Default `--notes` (omitted): resolves via `resolve_vault_root()` (mock/monkeypatch the
  vault root to a fixture dir, matching the pattern D1's `--output-dir` default test
  would use).
- No DB write assertion: after a `harvest` run with unknowns present, `Concept` table row
  count is unchanged (regression guard for the "harvest never writes" invariant).

**GREEN impl** — files touched:

- `src/workflow/concept/harvest.py` (new) — `scan_notes(paths: list[Path]) ->
  list[tuple[Path, dict]]` (reuses `workflow.notes.sync._parse_md`, skip-with-warning on
  parse failure or malformed `concepts:`); `partition_concepts(slugs, session) ->
  tuple[set[str], set[str]]` (known/unknown, built on top of `resolve_concepts` or a
  direct equivalent query — no reimplementation of the slug lookup); `match_discipline_
  area(prefix: str, session) -> str` (trailing-AA match against `DisciplineArea.code`,
  case-insensitive, `UNRECOGNIZED-PREFIX` fallback); `build_delta_yaml(unknown_slugs,
  provenance: dict[str, list[str]], buckets: dict[str, str]) -> str` (emits the
  skyfolding shape: `content: {name: "<TODO: assign real Content>"}` placeholder per
  bucket, `domain: TODO-REVIEW`, `label:` de-slugified + `# REVIEW` comment, `# cited by:`
  comment per entry); `harvest(notes: list[Path] | None, out: Path | None, session:
  Session) -> HarvestResult` (top-level orchestration, dataclass result with
  `unknown_concepts`, `notes_scanned`, `out_path`).
- `src/workflow/concept/cli.py` (edit) — new `@concept.command(name="harvest")` with
  `--notes` (multiple, dir-or-file), `--out`, `--json` options, following the existing
  6-command pattern (`_get_engine(ctx)`, `Session(engine)`, `with_schema_guard`); notably
  does NOT commit (read-only).
- `CLAUDE.md` — new bullet under "Concept CLI" documenting `concept harvest` alongside
  the existing `concept list|show|add|tree|rm|rename` line.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P2.

---

### Phase 3 — D2: operational backfill + verification

**Goal:** The 313-note vault backlog is retroactively indexed via one `notes sync` run;
counts move from 0 to nonzero, verified with exact SQL.

**RED tests:** none — D2 is zero new code (existing `notes sync` test suite already
covers the sync path per spec §3 D2). This phase is operational, not TDD.

**GREEN impl** — steps, not files:

1. Confirm precondition already satisfied: `essay` enum fix shipped (`4283e17`,
   verified in primer.md as "UNBLOCKED" and "live vault verified — `graph stats` exits
   0").
2. Run: `workflow notes sync <vault_root>` against the real vault (no `--dry-run`).
3. Verify counts moved off zero with these exact SQL queries against
   `~/.local/share/workflow/workflow.db` (or the resolved GlobalBase path):

   ```sql
   SELECT COUNT(*) FROM note_concept;
   SELECT COUNT(*) FROM note_tag;
   SELECT COUNT(*) FROM tag;
   SELECT COUNT(*) FROM note_edge;
   ```

   Expect all four `> 0` post-run (pre-run baseline per the design spec §1 is `0` for
   `NoteConcept`/`Tag`·`NoteTag`/`NoteEdge`).
4. Confirm no crash on any existing note file (`notes sync` exit code 0, no unhandled
   exception in stderr).
5. Record the before/after counts and the run's own reported `report.concept_issues`
   (unknown-slug warnings — expected non-empty until Phase 2's harvest output is
   imported) in this plan's own progress log (append a `## Results` section after
   running, per this repo's plan convention).

**Commit point:** none — ops-only, no code change to commit. If step 3 reveals a crash
or an unexpected zero, stop and re-plan (this becomes a bug, handled outside this plan).

---

## Risks / out of scope

- **In scope:** D1 (`sync_note_files` + `lectures split --sync/--no-sync`), D2 (one
  operational backfill run + count verification), D3 (`concept harvest`, read-only).
- **Out of scope:** D4 (flow documentation — already exists per the spec, no action
  needed here); FTS search (ADR-0021), `ResearchQuestion` entity (ADR-0022), `workflow
  synth` — all explicitly out of scope per the spec's own header.
- **Risk:** D1's orphan-drop-skip behavior in `sync_note_files` is an implementation
  decision, not explicitly locked in the spec — reviewer-esquema P1 should specifically
  confirm this reading doesn't silently break directory-wide `sync_vault`'s orphan
  cleanup (it shouldn't, since `sync_vault` keeps calling `_run_write_passes` with real
  `scope_prefix`/`current_filenames`, unaffected by the new `skip_orphan_drop` param
  defaulting to `False` there).
- **Risk:** D3's `UNRECOGNIZED-PREFIX` bucket could mask a typo'd discipline prefix as
  "unrecognized" rather than surfacing it as a likely error — accepted per spec §4 error
  table ("never silently dropped," not "never ambiguous").
- **Risk:** D2 backfill running against the live vault DB — no `--dry-run` step is
  listed in the spec's own D2 acceptance criteria (it explicitly says "operational...
  run once"); this plan's Phase 3 does not add a dry-run gate beyond what `notes sync`
  itself already exposes (`--dry-run` flag exists on the command per `sync_vault`'s
  `dry_run` param) — running with `--dry-run` first as a sanity check before the real
  run is recommended but not separately gated here.
- No schema migration expected — D1/D2/D3 are all additive code or ops-only; zero new
  columns/tables (confirmed against `src/workflow/db/migrations/global/` — latest
  migration untouched by this wave).

---

## Verification (each phase)

```bash
# Isolated suite — never touches live DB
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py

# Lint
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10

# Phase 3 (D2) — live backfill, ops-only, run against the real vault DB
# (no throwaway copy — this IS the intended write; back up first if uneasy)
# cp ~/.local/share/workflow/workflow.db /tmp/workflow-pre-d2-backup.db
workflow notes sync ~/01-U/0000AA-Vault

# Phase 3 (D2) — verification SELECTs (sqlite3 against the resolved GlobalBase path)
sqlite3 ~/.local/share/workflow/workflow.db "SELECT COUNT(*) FROM note_concept;"
sqlite3 ~/.local/share/workflow/workflow.db "SELECT COUNT(*) FROM note_tag;"
sqlite3 ~/.local/share/workflow/workflow.db "SELECT COUNT(*) FROM tag;"
sqlite3 ~/.local/share/workflow/workflow.db "SELECT COUNT(*) FROM note_edge;"
```

---

## Orquestación (modelo × proceso)

- Role table: Director(parent)=lanza agentes/corre suite integrada+flake8/decide fixes;
  opus=reviewer-esquema pre-commit + design review; sonnet=TDD impl/docs; haiku=git-ops
  staging explícito sin push.

### Mapa de paralelización

D1 ‖ D3 con fronteras de archivos: track-D1 posee `src/workflow/notes/sync.py` +
`src/workflow/lecture/cli.py` + sus tests; track-D3 posee `src/workflow/concept/
harvest.py` (nuevo) + `src/workflow/concept/cli.py` + sus tests. Ningún track toca
archivos del otro; CLAUDE.md lo edita el director al final.

### Wait-gates

1. D2 espera D1 commiteado (usa sync existente si se corre antes, pero la verificación
   de conteos asume Pass 2-5 completos).
2. D2 es ops-only y PUEDE correr durante el freeze.
3. reviewer-esquema opus antes de CADA commit.
4. el director corre la suite completa post-merge de tracks paralelos (greens de
   agentes son locales).
5. regla global: ninguna migración en esta wave (no schema change — declararlo).
