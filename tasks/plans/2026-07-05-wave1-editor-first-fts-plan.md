# Implementation plan — Wave 1: editor-first capture + vault FTS5 search

Request: none dedicated — sourced from `tasks/roadmap/2026-07-05-post-freeze-implementation-roadmap.md` (Wave 1, items 2–3)
ADR: `docs/ADR/ITEP-0015-editor-first-authoring-tooling.md` (**Proposed** — F0 must flip to Accepted with corrected scope)
      `docs/ADR/0021-vault-full-text-search.md` (**Proposed** — no code written by that ADR; F2 makes it real)
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase, forward-only
migrations (ITEP-0010). Phases ship independently; commit at each GREEN.

---

## Verified anchors (confirmed in code, 2026-07-05)

**★ Re-verification finding (contradicts both ADR ITEP-0015's own status line and the
roadmap's "confirmed by audit: no overlap" claim) — see "Resolved design rules"
below for the corrected scope this produces.** Most of ITEP-0015's "Proposed
Surface" is already shipped, apparently under a "Wave 5 EDITOR keymaps" label
(comment in `nvim-plugin/lua/workflow/keymaps.lua:85`) predating this roadmap's
own wave numbering:

- `workflow notes enums --json` — **shipped**, `src/workflow/notes/cli.py:587-631`
  (`enums_cmd`), emits exactly the schema the ADR's §A specifies (`edge_class`,
  `relation_type.{structural,associative}`, `note_type`, `zettel_id_format`).
- `workflow notes new-id` — **shipped**, `src/workflow/notes/cli.py:636-` (`new_id_cmd`),
  wraps `workflow.notes.ids.generate_zettel_id`.
- Neovim pickers — **shipped**: `nvim-plugin/lua/workflow/picker/enums.lua`
  (`pick_relation_type`, `pick_edge_class`, `pick_note_type`, session-cached,
  insert-at-cursor **and** yank-to-register modes, matching the ADR's MUST rule),
  `picker/edges.lua`, `picker/notes.lua`, `picker/concepts.lua` (all `M.pick(opts)`).
- Keymaps — **shipped**: `<prefix>en` (new-id insert), `<prefix>er` (relation_type
  pick), `<prefix>ec` (edge_class pick), `<prefix>eg` (graph-validate current
  buffer) — `nvim-plugin/lua/workflow/keymaps.lua:85-105`.
- In-buffer validation (ADR §D) — **shipped**: `nvim-plugin/lua/workflow/validate.lua`
  (`_parse_diagnostics`, dedicated diagnostic namespace), wired via
  `autocmds.lua` (`auto_validate_on_save`, `auto_graph_validate_on_save`,
  both `BufWritePost` on `*.md`), plus `:WorkflowValidate`, `:WorkflowValidateGraph`,
  `:WorkflowReloadEnums` user commands (`commands.lua:11,325,381`).
- `:WorkflowReloadEnums` cache-invalidation command — **shipped** (`commands.lua:325`).

**Genuinely NOT shipped (the real remaining ITEP-0015 scope):**

- `note_alias` table (ADR §F) — **absent**. `grep -ri alias src/workflow/db/models/notes.py`
  returns nothing; no migration touches aliases. Latest migration is
  `src/workflow/db/migrations/global/0016_exercise_type_normalize_legacy_codes.py`
  → next = `0017_`.
- `<prefix>ei` (pick note, insert zettel_id), `<prefix>eI` (pick note, insert full
  YAML `- id: … / type: …` item), `<prefix>eb` (pick bibkey, insert), `<prefix>ek`
  (pick concept code, insert) — **not bound**. `keymaps.lua` only has
  `en/er/ec/eg`. The backing pickers (`picker/notes.lua`, `picker/concepts.lua`)
  already exist with `M.pick(opts)` — this is a wiring gap (bind + confirm
  insert-at-cursor callback), not a new picker.
- `workflow notes capture` — **absent**. No `capture` command anywhere in
  `src/workflow/notes/cli.py`. This is genuinely new (F1), not in ITEP-0015's
  text at all — it is this roadmap wave's own framing ("capturar una nota con
  conceptos... en UN gesto").
- Literature→permanent DB-level promotion — **absent** as a CLI verb.
  `nvim-plugin/lua/workflow/init.lua:50` defines `M.promote_note()` but it is a
  pure file-move (fleeting inbox → permanent dir, no DB write, no `note_type`
  check) — a different, older feature. No `workflow notes promote` command
  exists to flip `Note.note_type` from `literature` to `permanent` and relocate
  the note under `<vault_root>/notes/permanent/` (mirroring
  `workflow.vault.paths.resolve_vault_root()`, reused by `lectures split`'s
  default output target per CLAUDE.md).
- Open Questions Q3 (pre-commit exit-code parity), Q4 (multi-vault picker scope),
  Q5 (snippet ownership) — still open per the ADR text; F0 must resolve or
  explicitly re-defer them.

**0021 FTS5 — confirmed still fully unbuilt** (consistent with its own "Proposed...
no code is written by this ADR" line):

- No `note_fts` virtual table anywhere (`grep -ri "fts5\|note_fts" src/workflow/db/`
  → no hits found during this plan's research).
- No `workflow notes search` command in `src/workflow/notes/cli.py`.
- No `nvim-plugin/lua/workflow/picker/search.lua` or `:WorkflowNoteSearch` command.

**Wave 0 hard dependency (`docs/superpowers/specs/2026-07-05-fleeting-harvest-design.md`,
D1) — confirmed NOT yet shipped:**

- `src/workflow/lecture/cli.py:90-119` (`lectures split`) still calls only
  `split_notes_file` (`src/workflow/lecture/note_splitter.py:35-133`) — zero DB
  interaction, no `--sync/--no-sync` flag.
- `src/workflow/notes/sync.py` has no extracted `sync_note_files(paths, session, ...)`
  entry point yet — Pass 1–5 logic lives only inside `sync_vault`
  (`sync.py:391-`, `_sync_note_concepts` at `sync.py:293-320`, `_parse_md` at
  `sync.py:47-`). **F2 (FTS index pass) is designed to hook into this extracted
  entry point once Wave 0 D1 ships — F2 cannot start before that lands** (see
  Phase 2 below and the roadmap's own stated coupling in ADR-0021's Consequences).

**Other anchors:**

- `Note` model: `src/workflow/db/models/notes.py` — `filename` (unique, non-null),
  `note_type` (nullable, CHECK `IN ('permanent','literature','fleeting')`,
  `ck_note_type_valid`), `zettel_id` (nullable). No `body`/full-text column today
  — FTS5 external-content design (F2) must decide whether to re-read `.md` files
  at index time (file-as-truth, ADR-0010) rather than duplicate body text in
  `Note` itself.
- `workflow.vault.paths.resolve_vault_root()` — reused by `lectures split`'s
  default output dir; F1's `notes capture`/`notes promote` MUST reuse this same
  resolver, not reimplement vault-root discovery.
- `resolve_concepts(codes, session, *, strict)` (`src/workflow/concept/service.py:140-169`)
  — slug-only, strict-forever per ITEP-0012's 2026-07-04 amendment (decision #18).
  `notes capture --concepts` MUST call this exact function, never a label
  resolver or a fork of it.
- LZK-0001 (`src/latexzettel`) JSONL/RPC server exists but
  `nvim-plugin/lua/workflow/server.lua` bridges pickers via CLI subprocess
  (`run_cli`), not the RPC protocol, for every picker inspected in this plan.
  [UNCLEAR] whether F2's `:WorkflowNoteSearch` should follow the same
  CLI-subprocess pattern (consistent with every existing picker) or use the RPC
  server (lower latency, per-keystroke live search) — ITEP-0015's own Open
  Question 1 rejected per-keystroke DB roundtrips for pickers in general, which
  argues for the CLI-subprocess pattern here too, but F0 should confirm this
  explicitly for the search case specifically (search is more roundtrip-prone
  than a static enum pick).

---

## Target / design

End state: a user can, from Neovim, capture a fleeting/literature note with
concepts attached in one gesture (`workflow notes capture`, bound to a new
keymap), promote a literature note to permanent via `workflow notes promote`,
insert a note reference or full YAML link item via completed `<prefix>ei`/`eI`
pickers, insert a bibkey/concept via completed `<prefix>eb`/`ek` pickers, and
full-text search the vault's 313+ notes by title/alias/body via
`workflow notes search <query> [--json]` ranked with FTS5 `bm25()`, surfaced as
`:WorkflowNoteSearch`. The FTS index is derived-only (rebuildable from `.md`
files, ADR-0010 invariant) and refreshed inside the same per-note sync pass
Wave 0's `sync_note_files` extraction introduces — no second top-level writer.

### Commands / API surface

```bash
workflow notes capture --title TEXT [--type fleeting|literature] [--tags a,b] \
  [--concepts em-foo,mc-bar] [--bibkey KEY] [--vault-root PATH] [--json]

workflow notes promote <note_id> [--to permanent] [--vault-root PATH] [--json]

workflow notes search <query> [--limit N] [--json]

workflow notes enums --json   # unchanged, already shipped — no new work
```

Expected `notes search --json` shape (mirrors `graph neighbors --json`,
ADR-0017, where practical):

```json
{
  "query": "gauss law",
  "results": [
    {"note_id": 42, "zettel_id": "K3f5G7HEy_q2", "title": "Gauss's Law",
     "path": "notes/permanent/K3f5G7HEy_q2-gauss-law.md", "snippet": "...<b>Gauss</b> law states...", "rank": -3.21}
  ]
}
```

`notes capture --json` / `notes promote --json` follow the existing
`{"note_path", "bibkey"|null, "created"|"promoted"}`-style contract established
by `notes create --json` (`src/workflow/notes/cli.py:170-`) — exact key set
locked in Phase 1, not here (Decisions section below covers only what's
locked already).

---

## Resolved design rules

- **F0 must correct ITEP-0015's own scope before anything else ships**: the ADR
  currently claims "Proposed... zero code shipped"; that is false against live
  code (see Verified anchors). Flipping it to Accepted requires first amending
  its body to reflect what already exists, then scoping F1/F3 of *this* plan to
  only the genuine gap (`note_alias`, `ei/eI/eb/ek` wiring, Q3–Q5). ★ Requires
  user confirmation — this is a correction to an existing ADR's own status
  narrative, not just a routine flip.
- **`notes capture` is new scope, not in ITEP-0015's text** — it is this wave's
  own framing. F0 must decide its exact flag surface (type default? required
  fields?) before F1 writes tests. ★ user decision.
- **`notes promote` is new scope, distinct from the existing Lua `promote_note`**
  (pure file-move) — the new command does a DB-level `note_type` flip
  (`literature` → `permanent`) plus optional file relocation under
  `resolve_vault_root()`'s `notes/permanent/`. Naming collision with the
  existing Lua function is intentional to converge (Lua wrapper should
  eventually call the new CLI verb instead of hand-rolling the move) but F0
  must confirm whether F3 rewires the Lua side in this wave or defers it.
  ★ user decision.
- **Fallbacks**: `notes capture` with no `--concepts` → note created with zero
  `NoteConcept` rows (same as `notes create` today — no error). Unknown concept
  slugs → warning via `resolve_concepts(strict=False)` unless `--strict` passed,
  matching `notes sync`'s existing convention (never silently drop, never
  auto-create — ITEP-0012 decision #18).
- **Collision / disambiguation**: `notes promote <note_id>` resolves `note_id`
  the same way `notes show`/`notes edges show` already do (zettel_id or
  filename) — reuse the existing lookup helper, do not fork it.
- **FTS external-content vs contentless**: LOCKED to **external-content**
  (`content='note'`-style shadow, not a fully denormalized `body` column) —
  rationale: `Note` has no `body` column today and ADR-0010 treats `.md` as
  truth; adding a duplicated body column to `Note` itself would create a second
  authority. External-content FTS5 needs the source rowid stable — `Note.id`
  already is. ★ still needs F0 confirmation since ADR-0021 explicitly left this
  open ("exact contentless/external-content tradeoff is an implementation-time
  decision, not pinned there").
- **FTS refresh trigger**: locked by ADR-0021's own Consequences section —
  every `notes sync` invocation that re-parses a note must re-index its FTS
  row; an unchanged note is neither re-parsed nor re-indexed (this ADR does not
  require ITEP-0014's `fm_hash` as a precondition, only notes the coupling —
  today, with no `fm_hash`, this means FTS re-indexes exactly the notes
  `sync_vault`/`sync_note_files` already re-parses, i.e. currently all of them
  every run, until ITEP-0014 lands as a separate optimization).
- **Rebuild story**: a `--rebuild-index` flag (or equivalent) on `notes sync` is
  required before F2 ships, per ADR-0021's Consequences — this is a hard
  acceptance criterion, not optional polish.

---

## Decisions — LOCKED (user, pending — none locked yet)

<!-- No items have been confirmed by the user for this specific plan as of
     2026-07-05. All ★ items above remain open. F0's own phase output is
     "flip ITEP-0015 Proposed→Accepted + record these decisions here" — this
     section is intentionally empty until that gate closes. -->

1. _(pending F0 gate)_
2. _(pending F0 gate)_
3. _(pending F0 gate)_

---

## Phases

### Phase 0 — Design gate: ITEP-0015 re-scope + UX decisions

**Goal:** Correct ITEP-0015's status narrative against live code, flip
Proposed→Accepted with the corrected (much narrower) remaining scope, and lock
the ★ decisions above with the user before any implementation phase starts.

**Owner:** opus (architect role) produces the corrected ADR text and a decision
memo; **★ GATE DE USUARIO** — no F1/F2/F3 work starts until the user confirms
the decision list in "Decisions — LOCKED" above is complete.

**Deliverables** (docs only, no code):

- `docs/ADR/ITEP-0015-editor-first-authoring-tooling.md` — amend Status,
  correct the "Proposed Surface" section to mark A/B/C(partial)/D as shipped,
  narrow "What remains" to: `note_alias` table+migration, `ei/eI/eb/ek`
  keymap wiring, Q3–Q5 resolutions. Add a Change Log entry dated 2026-07-05.
- `docs/ADR/0021-vault-full-text-search.md` — resolve the external-content vs
  contentless decision (recommend: external-content, per Resolved design rules
  above) and the CLI-vs-RPC picker question; flip Status to Accepted once user
  confirms.
- This plan's own "Decisions — LOCKED" section filled in with numbered
  decisions, replacing the placeholders.

**Commit point:** none — ADR edits are the "commit point" for this phase, gated
on user sign-off before Phase 1 begins (docs-only commit, separate from this
plan-writing task per this task's own instruction: no commit in this session).

---

### Phase 1 — `notes capture` + `notes promote` (python, track-python)

**Goal:** One CLI gesture creates a note (fleeting or literature) with tags,
concepts, and optional bibkey in a single command; a second command promotes a
literature note to permanent with a DB `note_type` flip + optional relocation.

**RED tests** (`tests/workflow/notes/test_capture.py`, `tests/workflow/notes/test_promote.py`):

- `capture` with `--title` only → note row created, `note_type` defaults per
  Phase 0's locked decision, zero `NoteConcept`/`Tag` rows.
- `capture --tags a,b --concepts em-foo` (concept pre-seeded) → `NoteTag` and
  `NoteConcept` rows created, matching `notes tag`/`notes sync`'s existing
  upsert behavior.
- `capture --concepts unknown-slug` (no `--strict`) → warning printed, note
  still created, no `NoteConcept` row for the unknown slug.
- `capture --concepts unknown-slug --strict` → exit 1, no note created
  (transactional — mirrors `sync --strict-concepts`'s all-or-nothing rule).
- `capture --json` → exact key set assertion.
- `promote <note_id>` on a `literature` note → `note_type` becomes
  `permanent`, file relocated under `resolve_vault_root()/notes/permanent/`
  (or in-place per Phase 0's decision), idempotent on re-run (second promote of
  an already-permanent note is a no-op or explicit error — Phase 0 locks which).
- `promote <note_id>` on a note that is already `permanent` → explicit error
  message (never silently no-ops without telling the user), unless Phase 0
  locks idempotent-no-op instead.
- `promote --json` → key set assertion.

**GREEN impl** — files touched:

- `src/workflow/notes/cli.py` (edit) — new `capture_cmd`, `promote_cmd` under
  the existing `notes` Click group; reuses `get_engine_from_ctx`,
  `resolve_concepts`, `resolve_vault_root()`, the existing note-lookup helper
  used by `notes show`.
- `src/workflow/notes/service.py` or a new `src/workflow/notes/capture.py` /
  `promote.py` (new) — business logic split from CLI per existing
  `evaluation`/`concept` module precedent (CLI thin, service does the work).
- `CLAUDE.md` — update the "Notes create CLI" bullet with the two new verbs.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P1.

---

### Phase 2 — FTS5 index + `notes search` (python, track-python — waits on Wave 0 D1)

**Goal:** `note_fts` virtual table exists, refreshed by the same per-note sync
pass Wave 0's `sync_note_files` extraction introduces; `workflow notes search
<query> [--json]` ranks results via `bm25()`.

**Wait-gate:** does not start until Wave 0's `sync_note_files(paths, session, ...)`
extraction (D1) is committed — this phase hooks its FTS-refresh call into that
extracted entry point rather than forking `sync_vault`'s loop a second time
(per the fleeting-harvest spec's own anchor at `sync.py:366-449`). If Wave 0 is
not yet landed when this phase is picked up, re-verify its status before
starting rather than assuming.

**RED tests** (`tests/workflow/notes/test_search.py`, migration idempotency test):

- Migration `0017_note_fts.py` — up/down round-trip idempotency test (standard
  ITEP-0010 migration test shape).
- `sync_note_files([note_path], session)` (or `sync_vault`, whichever the Wave 0
  extraction lands as) populates/updates the matching `note_fts` row for that
  note; re-running is a no-op on row count (upsert, not insert-duplicate).
- `search "gauss"` on a seeded vault → returns the matching note with a
  non-null `snippet`, ranked (`rank` field present, ordered ascending per
  SQLite's `bm25()` convention — lower is more relevant).
- `search "nonexistent-term-xyz"` → empty `results` list, exit 0 (not an
  error).
- `--rebuild-index` (on `notes sync`, per ADR-0021's Consequences requirement)
  — full rebuild from `.md` files reproduces the same `note_fts` row count as
  incremental sync, proving the index is fully derivable (ADR-0010 invariant).
- `search --json` → exact key set `{"query", "results"}`, each result
  `{"note_id","zettel_id","title","path","snippet","rank"}`.

**GREEN impl** — files touched:

- `src/workflow/db/migrations/global/0017_note_fts.py` (new migration) —
  create `note_fts` FTS5 virtual table (external-content, per Phase 0's locked
  decision), triggers or explicit sync-time upsert (decide per Phase 0 —
  triggers are usually simpler for external-content FTS5 but couple schema to
  SQLite specifics; explicit upsert in Python keeps DB-portability if that ever
  matters — flag for Phase 0 if not already resolved there).
- `src/workflow/notes/sync.py` (edit) — hook FTS upsert into the extracted
  Wave 0 entry point; add `--rebuild-index` to `notes sync`.
- `src/workflow/notes/search.py` (new) — query/ranking logic, `bm25()` call,
  snippet extraction.
- `src/workflow/notes/cli.py` (edit) — new `search_cmd`.
- `CLAUDE.md` — new command-table row; note the migration number.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P2.

---

### Phase 3 — nvim surface: keymap wiring + search picker + docs (track-lua)

**Goal:** Wire the four missing keymaps onto already-existing pickers, add a
capture keymap, add the new search picker, update plugin docs.

**RED tests** (`nvim-plugin/tests/plenary/`):

- `picker/search_spec.lua` (new) — mirrors the shape of
  `picker/notes_spec.lua`/`picker/edges_spec.lua`: mocks `server.run_cli`
  returning a fixture `notes search --json` payload, asserts the picker
  formats/opens correctly and the `<CR>` action inserts/opens as configured.
- `commands_spec.lua` (edit) — assert `:WorkflowNoteSearch` user command is
  registered.
- Keymap wiring itself is not independently unit-testable in plenary in the
  way business logic is — the acceptance gate for `ei/eI/eb/ek` is the manual
  smoke-test in Verification below, not a plenary spec (consistent with how
  `en/er/ec/eg` were verified originally, per the absence of dedicated keymap
  spec files in the existing suite).

**GREEN impl** — files touched:

- `nvim-plugin/lua/workflow/keymaps.lua` (edit) — add `<prefix>ei` (calls
  existing `picker/notes.lua` `M.pick` in insert-zettel_id mode), `<prefix>eI`
  (same picker, full-YAML-item insert mode — may need a small `M.pick` option
  addition in `picker/notes.lua` rather than a new file), `<prefix>eb` (bibkey
  picker — reuse `picker/prisma_bib.lua` or `content_bib.lua`, whichever
  already lists bibkeys with insert mode — confirm exact source file at
  implementation time), `<prefix>ek` (calls existing `picker/concepts.lua`
  `M.pick`), and a capture keymap (e.g. `<prefix>nc` — confirm no collision
  with the existing `<prefix>nc` = "check note edge cycles"! **[UNCLEAR]**
  flag: `keymaps.lua:78` already binds `prefix.."nc"` to `edges_check()` —
  Phase 0/3 must pick an unused prefix, do not silently overload).
- `nvim-plugin/lua/workflow/picker/search.lua` (new) — thin picker over
  `notes search --json`, following `picker/notes.lua`'s existing shape.
- `nvim-plugin/lua/workflow/commands.lua` (edit) — register `:WorkflowNoteSearch`.
- `nvim-plugin/lua/workflow/init.lua` (edit) — expose `M.pick_note_search`,
  `M.capture_note` wrapper functions the keymaps call, matching the existing
  `M.pick_notes`/`M.promote_note` pattern.
- `nvim-plugin/doc/workflow.txt` (edit) — document the 5 new/wired keymaps and
  `:WorkflowNoteSearch`.
- `nvim-plugin/docs/cli-contracts.md` (edit) — add `notes capture`,
  `notes promote`, `notes search` JSON contracts.

**Commit point:** suite green (plenary) + flake8 0 (python side unaffected) →
commit + reviewer-esquema P3 + **manual smoke-test gate** (see Verification).

---

## Orquestación (modelo × proceso)

| Rol | Modelo | Responsabilidad |
|---|---|---|
| Director | (parent session) | Ordena fases, corre la suite integrada post-merge, decide cuándo Wave 0 D1 está lo bastante estable para destrabar F2. |
| Architect / reviewer-esquema | opus | F0 (diseño UX + corrección de scope de ITEP-0015), reviewer-esquema pre-commit en cada fase (P1/P2/P3). |
| Implementación | sonnet | F1 (python capture/promote), F2 (python FTS + search), F3-python side (ninguno esperado, track-lua es puro Lua). |
| Lua / nvim | sonnet | F3 (keymaps, picker, docs) — árbol disjunto de F1/F2. |
| Git-ops / dumps de texto | haiku | Commits mecánicos, actualización de CLAUDE.md/doc tables una vez el contenido está decidido por sonnet/opus. |

**Mapa de paralelización:**

- `track-python` (`src/workflow/notes/**`, `src/workflow/db/migrations/global/0017_*`,
  `tests/workflow/notes/**`) ‖ `track-lua` (`nvim-plugin/**`) — árboles de
  archivos disjuntos, pueden correr simultáneos **desde F1** (F3 no depende de
  F1's exact implementation details beyond the CLI JSON contract, which Phase 0
  should pin before F1/F3 start in parallel).
- **F2-FTS ‖ F1-capture**: solo en paralelo si tocan archivos distintos —
  frontera explícita: `capture`/`promote` viven en `cli.py` (nuevas funciones)
  + un módulo de servicio nuevo (`capture.py`/`promote.py`); FTS toca
  `sync.py` (el mismo archivo que la extracción de Wave 0 D1 ya está tocando)
  + un módulo `search.py` nuevo + una migración nueva. FTS **no** debe tocar
  `cli.py`'s capture/promote functions hasta el wiring final del director
  (mismo patrón de frontera usado en waves anteriores).

**Wait-gates:**

1. **Toda la wave espera Wave 0 D1 commiteado** — `sync_note_files` es la base
   del pass de FTS (Phase 2); no duplicar el loop de sync una segunda vez.
   Wave 0 D2 (backfill) y D3 (`concept harvest`) no son gates para esta wave,
   solo D1.
2. **F0 (diseño + ★ gate de usuario) antes de F1/F2/F3** — ninguna fase de
   implementación empieza sin las "Decisions — LOCKED" llenas.
3. **Migración**: `note_fts` (0017) se numera secuencial tras la última en
   `master` en el momento de implementar, nunca en paralelo con otra migración
   (regla global de todas las waves — ver ADR-0010).
4. **Reviewer-esquema opus pre-commit** en cada fase (P1, P2, P3).
5. **Director corre la suite integrada post-merge** de cada fase antes de dar
   luz verde a la siguiente.
6. **Smoke-test manual en nvim real = gate humano final de F3** — `luac -p`
   (syntax-only) no es suficiente para aceptar los keymaps nuevos; requiere
   abrir un buffer real en el vault y confirmar inserción/yank de cada picker
   nuevo/wireado (`ei`, `eI`, `eb`, `ek`, capture keymap, `:WorkflowNoteSearch`).

---

## Risks / out of scope

- **In scope:** `notes capture`, `notes promote`, `note_fts` + `notes search`,
  the 4 missing keymap wirings + search picker, doc updates.
- **Out of scope:** re-implementing anything already shipped (enums, new-id,
  existing pickers, BufWritePost validation) — F0 must not re-litigate working
  code; ITEP-0014 (`fm_hash`) — explicitly an optimization for FTS re-index,
  not a precondition (per ADR-0021); ADR-0022 (`ResearchQuestion`) — Wave 2,
  not touched here; rewiring the existing Lua `promote_note` (fleeting→permanent
  file-move) to call the new `notes promote` CLI verb — flagged as a Phase 0
  decision point, may be deferred to a follow-up wave.
- **Risk:** F0's ADR-status correction is itself a nontrivial documentation
  change to an existing Accepted-adjacent ADR — must not silently rewrite
  history; use a dated Change Log entry, not a silent edit.
- **Risk:** Phase 2 is hard-blocked on a different wave's phase (Wave 0 D1) —
  if that work stalls, this plan's Phase 2 (and Phase 3's search picker,
  though not its keymap-wiring sub-scope) stalls with it. Phases 1 and the
  keymap-wiring part of Phase 3 are NOT blocked by Wave 0 and can proceed
  independently.
- **Risk:** `<prefix>nc` keymap collision flagged above (edges_check already
  owns it) — any new capture keymap must pick an unused prefix; verify against
  the full existing table in `keymaps.lua` before binding, not just the
  Wave-5-editor block.
- No destructive schema migration expected — `note_fts` is additive; `promote`
  updates `note_type` in place (existing nullable CHECK-constrained column, no
  column addition needed) unless Phase 0 locks a file-relocation requirement
  that also touches `Note.filename` (also already-nullable-safe, unique
  constraint already enforced).

---

## Verification (each phase)

```bash
# Isolated suite — never touches live DB
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py

# Lint
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10

# Lua suite (F3)
cd nvim-plugin && make test   # or nvim --headless -c "PlenaryBustedDirectory tests/plenary"

# P3 manual smoke-test gate (human, not automatable per this plan's own rule)
# open a real vault note in nvim, exercise ei/eI/eb/ek, the new capture keymap,
# and :WorkflowNoteSearch against the live 313-note vault; confirm insertion
# and yank-to-register both work before considering F3 done.

# P2 live dry-run (on a COPY of the live DB, never the original)
# cp ~/.local/share/workflow/workflow.db /tmp/workflow-test.db
# WORKFLOW_DATA_DIR=/tmp workflow notes sync <vault_root> --rebuild-index --dry-run
```
