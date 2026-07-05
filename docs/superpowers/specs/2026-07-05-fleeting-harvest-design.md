# Design: Fleeting-monolith ingestion + concept harvest loop

- Status: Approved (approach B, user-approved 2026-07-05)
- Date: 2026-07-05
- Scope: `workflow lectures split`, `workflow notes sync` (existing), new `workflow concept harvest`
- Depends on: ITEP-0011 (vault unification), ITEP-0012 (concept ORM + 2026-07-04 slug-only amendment), ADR-0018 (bulk-import contract)
- Out of scope (post-freeze, separate ADRs in parallel): FTS search, `ResearchQuestion` entity, `workflow synth`

## 1. Problem

Since June, fleeting notes carry full semantic frontmatter (`concepts:`, `tags:`,
`relations.derived_from`, `main_topic`) written by hand inside monolith files such
as `~/01-U/0000AV-Vault/inbox/semana05-propiedades-magneticas-2.md`. But the DB
index shows **0 `NoteConcept` rows, 0 `Tag`/`NoteTag` rows, 0 `NoteEdge` rows** for
these notes. Two independent gaps cause this:

1. **`workflow lectures split` never syncs.** `split_notes_file`
   (`src/workflow/lecture/note_splitter.py:35-133`) only writes files and computes
   `\input{}` lines — it has no DB interaction at all. The CLI command
   `lectures split` (`src/workflow/lecture/cli.py:90-119`) calls it and prints a
   report; it never calls `sync_vault` or any of the Pass 2–5 helpers in
   `src/workflow/notes/sync.py`. Frontmatter that was hand-written into a `%>`
   block sits on disk, unindexed, until someone separately runs a sync that
   targets that path.
2. **New concepts born bottom-up in notes are rejected.** `resolve_concepts()`
   (`src/workflow/concept/service.py:140-169`) only resolves against existing
   `Concept.code` rows; unknown codes become a `warning` (or `error` under
   `--strict`) — see `_sync_note_concepts` in `src/workflow/notes/sync.py:293-320`,
   which calls `resolve_concepts(codes, session, strict=strict)` and only
   upserts `NoteConcept` for `found` concepts. A concept slug typed into a note's
   `concepts:` list (e.g. `em-magnetizacion` in
   `20260618-Magnetizacion.md`, embedded in the semana05 monolith) must **already
   exist** via a skyfolding import (`workflow import <skyfolding>.yml`, engine at
   `src/workflow/importer/engine.py`) before any note referencing it can pass sync
   without a warning. There is currently no path from "concept slug appears in a
   note" to "concept exists in the DB" other than a human manually authoring a
   skyfolding YAML entry.

Per ITEP-0012's 2026-07-04 amendment (decision #18, option A), concept references
are **slug-only, strict, forever** — `resolve_concepts()` must never gain a
label-based fallback. Any fix here must work within that constraint, not around it.

## 2. Locked decisions

### D1 — `lectures split` gains `--sync/--no-sync` (default `--sync`)

`workflow lectures split <source> [--output-dir DIR] [--overwrite] [--sync/--no-sync]`

- Default is `--sync` (on). After `split_notes_file` returns its `SplitResult`,
  the command runs the equivalent of the notes-sync write passes
  (`_upsert_note_row`, `_upsert_note_labels`, `_upsert_note_citations`,
  `_upsert_note_links`, `_upsert_note_edges`/`_rebuild_note_edges`,
  `_sync_note_concepts` — all in `src/workflow/notes/sync.py`) **scoped to
  exactly the files in `result.files`**, not a directory rglob. This requires a
  small new entry point (e.g. `sync_note_files(paths, session, ...)`) that
  factors the per-note passes out of `sync_vault`'s `md_paths` loop so both the
  directory-wide sync and the file-list sync share the same Pass 1–5 logic —
  `sync_vault` itself is not touched; the passes are extracted into functions it
  and the new entry point both call. Only files where `SplitFile.created is True`
  **or** already existed on disk (both are real files with frontmatter) are fed
  in — a file that was `skipped` because it already existed and is unchanged
  should still be (re-)synced, since sync is idempotent by design (Note upsert
  keys on `filename`/`zettel_id`, links/edges/concepts are upsert-not-duplicate).
- `--no-sync` restores today's behavior exactly (split-only), for anyone who
  wants to review the emitted files before they hit the DB.
- Idempotent: re-running `split --sync` on the same monolith with `--overwrite`
  off just re-syncs already-registered notes; NoteConcept/NoteEdge/Link upserts
  are all guarded by existing-row lookups (see `upsert_note_concept`,
  `upsert_note_edge`, `upsert_link` in `workflow.notes.linker_ops`).
- Unknown concept slugs surfaced during this sync are reported exactly as
  `_sync_note_concepts` already reports them (`report.concept_issues`, printed
  as warnings unless `--strict-concepts` is later added to this command too —
  not in scope for D1; today `lectures split` has no strict flag, and D1 does
  not add one. It reports; it does not gate. Gating is `notes sync`'s job).

### D2 — One-time backfill via existing `notes sync`

No new code. `workflow notes sync <vault_root>` (existing command, engine in
`src/workflow/notes/sync.py`, entry `sync_vault`) is run once over the whole
vault to retroactively index every note that was split *before* D1 shipped
(i.e., every monolith already split under the old sync-less `lectures split`).
Precondition, tracked separately and in progress in parallel: the `essay`
`note_type` enum fix must land first, or the backfill will choke on/miscount
notes using that type. This design does not touch that fix; it only names it as
a blocking precondition for running D2.

### D3 — `workflow concept harvest`

`workflow concept harvest [--notes DIR|FILE ...] [--out PATH.yaml] [--json]`

Purpose: close the loop from "concept slug appears in a note but isn't in the
DB" to "human-reviewable skyfolding delta YAML" — **without** ever writing to
the DB directly. Import remains the only write path (ADR-0018's
`import_hierarchy` / `add_concept` in `src/workflow/concept/service.py:201-257`
is the single source of truth for concept creation).

**Algorithm:**
1. Resolve the note set: `--notes` accepts one or more directories (rglob
   `*.md`) or explicit files; default (no `--notes`) is the vault root via
   `workflow.vault.paths.resolve_vault_root()`, matching the resolution
   convention already used by `lectures split`'s `--output-dir` default
   (`src/workflow/lecture/cli.py:93-96`).
2. For each note, parse frontmatter the same way `notes/sync.py::_parse_md`
   does (reuse that parser, or an equivalent, rather than re-implementing
   frontmatter extraction — do not fork the YAML-boundary-finding logic).
3. Collect every string in `concepts:` across all scanned notes.
4. Open a session against the same DB `resolve_concepts()` would use, and
   partition collected slugs into known (already a `Concept.code`) vs unknown.
   Known slugs are dropped silently (already resolvable — nothing to harvest).
5. For each unknown slug, infer a discipline-area grouping from its slug prefix
   (the token before the first `-`, e.g. `em-magnetizacion` → `em`, `mc-torque`
   → `mc`). This prefix is a **living convention**, not a schema-enforced field.
   Code semantics (clarified by user 2026-07-05, per ITEP-0008 `DDTTAA`):
   `data/00-PhysicsCodes.csv` lists **main-topic codes `TTAA`** (e.g.
   `Mecánica Clásica,10MC`), while a skyfolding `discipline_area_code` is the
   full `DDTTAA` — discipline digits `DD` prepended (e.g. `00` + `10MC` =
   `0010MC`). They are two levels of the same nomenclature, not two conventions.
   **Harvest matches on the trailing letter pair (`AA`, e.g. `MC`/`EM`) of
   `discipline_area_code`, case-insensitively against the slug prefix**, which
   is well-defined at both levels. If a slug's prefix
   matches no known `DisciplineArea` by this scheme, the entry is grouped under
   a literal `UNRECOGNIZED-PREFIX` bucket in the output YAML — it still gets a
   full entry, just an unresolved grouping key, so nothing observed is silently
   dropped.
6. Emit one **skyfolding-delta YAML** (same shape as
   `templates/0010MC-contents-skyfolding.yml` /
   `0040EM-contents-skyfolding.yml`, i.e. valid input to
   `workflow import`), containing only the harvested (unknown) concepts, grouped
   under their inferred `discipline_area_code`/bucket. Each concept entry:
   - `code:` — exactly the slug as found in the note (never altered — code is
     the join key; changing it here would desync it from every note that
     already references it).
   - `label:` — a de-slugified placeholder (`em-magnetizacion` → `Magnetizacion`,
     naive hyphen→space + capitalize; no accent restoration attempted) with a
     trailing ` # REVIEW` comment marking it as a placeholder pending human
     correction of accents/casing/wording.
   - `domain:` — literal string `TODO-REVIEW` (not a valid `_TAXONOMY_DOMAINS`
     value on purpose — `workflow import` will reject it at `add_concept`'s
     `_validate_domain` check until a human fixes it, which is the intended
     forcing function: harvest output is never import-ready as-is).
   - A `# cited by: <note1>, <note2>, ...` provenance comment above each entry,
     listing every scanned note (by `id`/filename) whose `concepts:` list
     contained that slug.
   - Under each inferred discipline-area bucket, concepts also need a `content:`
     parent per the skyfolding schema (`Concept.content_id` is required,
     non-null, per `add_concept`'s signature). Harvest emits a single synthetic
     placeholder content node per bucket — `name: "<TODO: assign real Content>"`
     — that the human is expected to replace by moving each concept under the
     correct real `Content` (or leaving the placeholder content as a real,
     renamed one) before running `workflow import`. Harvest does not attempt to
     guess `Content`/`Topic` placement; that requires domain judgment the
     tool doesn't have.
7. Human edits the delta file: fixes `label`, sets `domain` to a valid
   `_TAXONOMY_DOMAINS` value, resolves `content:` placement (possibly splitting
   across multiple real contents), removes the `# REVIEW` markers.
8. Human runs `workflow import delta.yaml` (existing command/engine,
   `src/workflow/importer/engine.py` + `docs/ADR/0018-bulk-import-contract.md`).
   Global concept-code-skip semantics apply unchanged: if a harvested code was
   *also* added independently under a different content in the interim, import
   silently skips it (ADR-0018 "Idempotency" section, `concept code (global)`
   skip key) — harvest does not special-case this; it is existing, documented
   import behavior.
9. After import, unknown-concept warnings for those slugs disappear the next
   time `notes sync` / `lectures split --sync` runs, because `resolve_concepts`
   now finds them. No note file needs to change — the slug in frontmatter was
   correct all along; only the DB was missing the row.

**`--out PATH.yaml`** — write the delta to a specific path (default: a
timestamped path under `tasks/` — exact default path is an implementation
choice for whoever builds this, not locked here, but it MUST NOT default into
repo root or `data/templates/` since those are curated/checked-in areas).

**`--json`** — emit `{"unknown_concepts": N, "notes_scanned": N, "out_path": str|null}`
on stdout instead of the human table; suppresses the "wrote delta to ..." line
duplication (same pattern as other `--json` flags in this codebase, e.g.
`build-exam --json`).

**Harvest never writes to the DB.** It opens a read-only-in-spirit session
(no `session.add`, no `session.commit`) purely to query existing `Concept.code`
values for the known/unknown partition. This preserves the single-write-path
invariant ADR-0018 establishes for concept creation.

### D4 — Flow documentation becomes canonical convention

The monolith structure (STAGING zone + `%>id.md ... %>END` NOTES zone) as seen
in `~/01-U/0000AV-Vault/inbox/semana05-propiedades-magneticas-2.md` and the
skyfolding-first / harvest-later concept lifecycle are documented in the
companion guide (`docs/wiki/Fleeting-Monolith-Flow.md`) and template
(`data/templates/fleeting-monolith-template.md`). These are the canonical
references going forward — new weekly monoliths should be started from the
template, not copied ad hoc from a previous week's file.

## 3. Testing sketch

### D1 (`lectures split --sync`)
- Unit: `split_notes_file` output feeds a new `sync_note_files(paths, session)`
  (or equivalent) — assert `Note`, `Label`, `NoteConcept`, `NoteEdge` rows exist
  after a split of a fixture monolith with 2+ `%>` blocks, one with
  `relations.derived_from` pointing at the other.
- Idempotency: run `split --sync` twice on the same source (no `--overwrite`);
  second run must not duplicate any `NoteConcept`/`NoteEdge`/`Label` row (assert
  row counts unchanged between run 1 and run 2).
- Unknown concept: a `%>` block with a `concepts:` slug not in the DB → split
  succeeds (exit 0), a warning is printed listing the file + slug, no
  `NoteConcept` row is created for that slug.
- `--no-sync`: assert zero DB rows created; behavior identical to pre-D1.

### D2 (backfill via `notes sync`)
- Not new code — existing `notes sync` test suite already covers this path.
  Acceptance here is operational: run once against the real vault after the
  `essay` enum fix lands, confirm `note_concepts`/`tags`/`edges` counts go from
  0 to a plausible nonzero number, no crash on any existing note file.

### D3 (`concept harvest`)
- Fixture: 2 notes referencing `em-foo` (unknown) and `mc-bar` (known, seeded).
  Assert output YAML contains only `em-foo`, under an `EM`-prefixed bucket, with
  both citing notes listed in the provenance comment; `mc-bar` does not appear
  anywhere in the output.
- Zero-unknowns case (see §4 below): assert no file written, exit 0, a stdout
  note like "no unknown concepts found — nothing to harvest".
- Malformed frontmatter (unparseable YAML or missing `id:`): assert the file is
  skipped with a per-file warning to stderr, and the run still completes (exit
  0) covering the remaining well-formed notes — mirrors `_parse_md`'s existing
  "return None → skip" contract in `notes/sync.py`.
- Round-trip: harvest → hand-fix `label`/`domain`/`content` → `workflow import`
  the delta → re-run harvest on the same notes → assert the previously-unknown
  slug no longer appears in the new delta (it now resolves).
- `--json` output: assert exact key set `{"unknown_concepts", "notes_scanned", "out_path"}`.

## 4. Error handling

| Condition | Behavior |
|---|---|
| `harvest` finds zero unknown concepts | No delta file written; exit 0; stdout note "no unknown concepts found". |
| A scanned note has malformed/missing frontmatter | Skip that file with a stderr warning naming the path; continue scanning the rest; does not affect exit code. |
| A scanned note's `concepts:` value is not a list of strings | Same skip-with-warning treatment as malformed frontmatter (defensive — mirrors `_sync_note_concepts`'s `isinstance(c, str)` filtering in `notes/sync.py:307`, but at the file level for harvest since a bad shape here is a frontmatter authoring error, not a per-item filter case). |
| Slug prefix doesn't match any known `DisciplineArea` letter-suffix | Grouped under `UNRECOGNIZED-PREFIX` bucket; still emitted with full provenance — never silently dropped. |
| `lectures split --sync` hits an unknown concept slug | Warned (same shape as `notes sync`'s `concept_issues`); split still succeeds; no exit-code change (`lectures split` today has no strict/gating flag and D1 does not add one). |
| `lectures split --sync` re-run on unchanged files | Idempotent no-op on already-synced rows (upsert guards). |
| `notes sync` backfill (D2) run before the `essay` enum fix lands | Out of scope for this design to fix; documented precondition, not handled defensively here. |

## 5. Ground-truth anchors (file:line as read 2026-07-05)

- `src/workflow/lecture/note_splitter.py:35-133` — `split_notes_file`, no DB interaction.
- `src/workflow/lecture/cli.py:90-119` — `lectures split` command, calls only `split_notes_file`.
- `src/workflow/notes/sync.py:293-320` — `_sync_note_concepts`, calls `resolve_concepts(codes, session, strict=strict)`.
- `src/workflow/notes/sync.py:366-449` — `_run_write_passes` / `sync_vault`, the Pass 2–5 orchestration D1 must reuse (not fork).
- `src/workflow/concept/service.py:140-169` — `resolve_concepts`, slug-only, no label fallback (per amendment, must stay that way).
- `src/workflow/concept/service.py:201-257` — `add_concept`, the only concept-creation path; validates domain via `_validate_domain`/`_TAXONOMY_DOMAINS`.
- `src/workflow/importer/engine.py`, `src/workflow/importer/types.py` — bulk import engine + `ImportResult`/`RowError` contract (ADR-0018).
- `docs/ADR/0018-bulk-import-contract.md` — exit codes 0/1/2/3, `--json` shape, idempotency/skip semantics harvest's output must be compatible with.
- `docs/ADR/ITEP-0012-concept-orm.md` (amendment 2026-07-04, "Amendment 2026-07-04 — Concept referencing contract: slug-only strict (gap #18)") — locks slug-only forever; `resolve_concepts()` must never gain a label path.
- `~/01-U/0000AV-Vault/inbox/semana05-propiedades-magneticas-2.md` — monolith exemplar: STAGING zone (mapa de contenidos + deck skeleton) before the first `%>`, three `%>id.md ... %>END` blocks each with full frontmatter, one with `relations.derived_from` type `continuation`.
- `~/01-U/0000AV-Vault/templates/0010MC-contents-skyfolding.yml`, `0040EM-contents-skyfolding.yml` — skyfolding YAML shape harvest's delta output must match (importable by `workflow import` as-is once human-edited).
- `data/00-PhysicsCodes.csv` — branch name → main-topic code (`TTAA`) table; a skyfolding `discipline_area_code` is `DD`+`TTAA` (ITEP-0008), e.g. `00`+`10MC`=`0010MC` (resolved — see §2 D3 step 5 and §6).

## 6. Contradictions / open flags against the locked design

- ~~**[FLAG]** CSV codes (`10MC`) vs skyfolding `discipline_area_code`
  (`0010MC`) look like two conventions with no authoritative mapping.~~
  **RESOLVED 2026-07-05 (user):** they are two levels of the ITEP-0008
  `DDTTAA` nomenclature — `data/00-PhysicsCodes.csv` lists main-topic codes
  (`TTAA`, e.g. `10MC` = Mecánica Clásica), and `discipline_area_code`
  prepends the discipline digits `DD` (e.g. `00`+`10MC` = `0010MC`). The
  harvester therefore matches slug prefixes against the trailing `AA` letter
  pair of live `DisciplineArea.code` rows (DB as source; CSV is reference
  documentation of the `TTAA` level). No open flag remains here.
- No other anchor read during this design contradicted the locked decisions.
