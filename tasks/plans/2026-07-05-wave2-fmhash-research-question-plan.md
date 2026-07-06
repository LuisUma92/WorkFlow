# Implementation plan — Wave 2: fm_hash spike + ResearchQuestion entity

Request: none (roadmap-derived — `tasks/roadmap/2026-07-05-post-freeze-implementation-roadmap.md`, Wave 2, items 4-5)
ADR: `docs/ADR/ITEP-0014-incremental-sync-via-content-hash.md` (**Proposed — placeholder, benchmark-gated**); `docs/ADR/0022-research-question-entity.md` (**Proposed**)
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase, forward-only
migrations (ITEP-0010). Phases ship independently; commit at each GREEN.

---

## Verified anchors (confirmed in code)

- `Note` model — `src/workflow/db/models/notes.py:88-131` (`GlobalBase`, `note` table).
  No `fm_hash` column exists today; ITEP-0014's proposed `ALTER TABLE note ADD COLUMN
  fm_hash TEXT` would live here, alongside the existing `zettel_id`/`main_topic_id`
  Phase 7b/B additions (same nullable-for-backward-compat pattern).
- Migration harness: `src/workflow/db/migrations/global/`; latest = `0016_exercise_type_normalize_legacy_codes.py`
  → next = `0017_`. (Verified via directory listing 2026-07-05: 0001 baseline through
  0016 exist, no gaps.)
- Sync engine: `src/workflow/notes/sync.py`. `sync_vault()` (line 391) does a full
  rescan of every `.md` under scope on every call — no hash/skip-gate exists yet.
  Pass structure (as it stands today, pre-Wave-0 D1 extraction):
  - Pass 1 (`sync_vault` body, ~line 415): parse + upsert `Note`/`Label` per file.
  - Passes 2-5 live in `_run_write_passes()` (line 366): links (`_upsert_note_links`),
    orphan drop (`_drop_orphan_links`, line 323), edges (`_upsert_note_edges` /
    `_rebuild_note_edges`, line ~280), concepts (`_sync_note_concepts`, line 293).
  - `_sync_note_concepts(session, note, fm, *, strict=False)` (line 293) is the
    template pass this plan's F4 clones: reads `fm.get("concepts")` list, calls
    `resolve_concepts`, upserts `NoteConcept` rows, returns `(upserted_count, issues)`
    where each issue is `{"severity": "warning"|"error", "message": str}`.
  - **[UNCLEAR / cross-wave note]**: Wave 0 D1 (`sync_note_files` extraction) and
    Wave 1's FTS write-hook both plan to touch this same pass loop before Wave 2
    starts. This plan's F1/F2/F4 phases assume the pass loop still looks like the
    anchors above at the time of implementation — **re-verify `sync.py` line numbers
    and pass structure against master before starting F1/F2/F4** if Wave 0/1 have
    landed in between (wait-gate 3 below exists precisely for this).
- `resolve_concepts(codes, session, *, strict=False)` — `src/workflow/concept/service.py:140-165`.
  Returns `(found_concepts, issues)`; loops `Concept.code == code` per slug (no batch
  query). This is the **pattern to clone, not reuse directly** for RQs (ADR-0022 is
  explicit: RQs get their own resolver, `resolve_research_questions`, mirroring this
  shape but querying `ResearchQuestion.code`).
- `Concept` model — `src/workflow/db/models/knowledge.py:166-186`. `code: Mapped[str]
  = mapped_column(String(32), unique=True)` — the slug column shape `ResearchQuestion.code`
  should mirror (String length TBD in Resolved design rules below).
- `NoteConcept` model — `src/workflow/db/models/notes.py:260-270`. Pure M2M, composite
  PK (`note_id`, `concept_id`), both `ondelete="CASCADE"`. `NoteResearchQuestion` mirrors
  this shape but is **not** a pure M2M — it adds a `stance` column, so it needs a
  surrogate `id` PK or a composite PK plus `stance` as a non-key column (composite PK
  is consistent with `NoteConcept`; decided in Resolved design rules below).
- ITEP-0012 slug-only amendment — `docs/ADR/ITEP-0012-concept-orm.md:315-336`
  (2026-07-04). MUST rule: every concept-referencing surface validates against
  `Concept.code` strict, no label fallback, ever. ADR-0022 explicitly extends this
  discipline to `ResearchQuestion.code` — this plan's F3/F4 follow it: no
  `ResearchQuestion.label`-as-lookup-key path is ever introduced.
- ITEP-0014's own gate (`docs/ADR/ITEP-0014-incremental-sync-via-content-hash.md:108-118`):
  implementation **MUST NOT begin** before (1) vault size justifies the optimization —
  benchmark required, (2) the 4 Open Questions are resolved, (3) ITEP-0013 ships. Gate 3
  is satisfied (ITEP-0013 Implemented per 2026-07-05 audit). Gates 1-2 are what F1 (spike)
  exists to resolve — **F1's benchmark verdict is the actual gate for F2**, not a formality.
- ADR-0022 hard dependencies (`docs/ADR/0022-research-question-entity.md:6`): ITEP-0012
  (slug-only — satisfied), ITEP-0013 (note relation graph — Implemented), 0003 (hybrid
  DB), PRISMA-0005. No blocking gaps found against current code state.

---

## Target / design

**F1 (spike, always runs)**: a benchmark harness copies the real vault (`~/01-U/0000AA-Vault`
or `WORKFLOW_VAULT_ROOT`) into a tmp dir, runs `sync_vault()` cold (full rescan) and warm
(re-run, no file changes) N times, records wall-clock + per-pass breakdown, and produces a
verdict artifact (`tasks/audit/2026-07-05-fm-hash-spike-benchmark.md` or similar, opus-authored)
answering ITEP-0014's own gates 1-2 directly: is current full-rescan cost material at real
vault size, and are the 4 Open Questions resolved enough to implement safely. **GO** unlocks F2;
**NO-GO** is a valid, complete outcome — it closes ITEP-0014 as `Rejected-with-evidence` (Status
line rewritten, Change Log entry appended, no further Wave 2 fm_hash work scheduled).

**F2 (only if F1 = GO)**: `Note.fm_hash` column (migration 0017 or later per sequencing rule
below), hash computed as `sha256(frontmatter_yaml_raw || "\n---\n" || body)` per ITEP-0014's
own formula, skip-gate inserted into `sync_vault()`'s per-file loop — unchanged-hash notes skip
parse+upsert entirely. `sync --force` / `sync --rebuild-edges` bypass the gate unconditionally
(existing flags, extended semantics only).

**F3 (independent of F1/F2)**: `ResearchQuestion` GlobalBase entity + `NoteResearchQuestion` M2M
(with `stance`) + migration + `workflow notes question add|list|link` CLI (Click group +
service + formatter split, following `workflow.evaluation`/`workflow.concept` precedent).

**F4 (depends on F3 committed)**: frontmatter `questions:` list ingestion — a new sync pass
`_sync_note_research_questions` cloned from `_sync_note_concepts`'s shape, wired into
`_run_write_passes()`; `validate notes` gains an RQ-slug check mirroring the existing
concept-slug check.

Appendix (NOT a phase, no TDD): `workflow synth` — explicitly out of scope per ADR-0022's own
Consequences section and the fleeting-harvest spec's own scope line. One page of entry
criteria only: gated on Waves 0-2 populating real concept/RQ/note data; do not design here.

### Commands / API surface

```bash
# F1 — spike harness (throwaway script, not a shipped CLI command)
uv run python scripts/bench/fm_hash_spike.py --vault-copy /tmp/vault-bench --runs 5 --json

# F2 — existing commands, extended semantics only (no new flags beyond ITEP-0014's own spec)
workflow notes sync <vault_root>              # now skip-gated by fm_hash
workflow notes sync <vault_root> --force      # bypasses hash gate (existing flag)
workflow notes sync <vault_root> --rebuild-edges   # bypasses hash gate (existing flag)

# F3
workflow notes question add --code <slug> --text "<question_text>" [--main-topic CODE]
workflow notes question list [--status open|active|answered|abandoned] [--json]
workflow notes question link --note <zettel_id|filename> --code <slug> --stance supports|contradicts|contextualizes [--remove]

# F4 — frontmatter (ingested by `notes sync`, no new CLI flag)
---
questions:
  - some-rq-slug
---
```

Expected output / JSON shape (F1 spike verdict, illustrative):

```json
{
  "vault_note_count": 313,
  "cold_sync_ms": 0,
  "warm_sync_ms": 0,
  "verdict": "GO|NO-GO",
  "open_questions_resolved": {"scope": "content-only", "split_hashes": false, "dry_run": "no-op", "concurrency": "documented, not solved"}
}
```

```json
// workflow notes question list --json
{"research_questions": [{"code": "str", "question_text": "str", "status": "str", "main_topic_id": "int|null"}]}
```

---

## Resolved design rules

- **F1 spike is mandatory, not skippable**: ITEP-0014's own Status section makes
  implementation without the benchmark a contract violation, not a shortcut. ★ none —
  this is already locked by the ADR text itself, no user confirmation needed.
- **NO-GO is a first-class, complete outcome**: if F1 concludes optimization isn't
  justified at current vault size, F2 is skipped, ITEP-0014's Status is rewritten to
  `Rejected-with-evidence` with the benchmark numbers as the rejection rationale, and
  this plan's F2 phase is marked "not executed — see spike verdict." No re-litigation
  without a new benchmark.
- **Hash formula fixed by ITEP-0014's own text**: `sha256(frontmatter_yaml_raw ||
  "\n---\n" || body)`, content-only (no mtime). F2 does not re-derive this — it is
  already the ADR's Proposed Direction, F1 only validates it's still sound after
  answering the Open Questions.
- **Migration sequencing (global rule, restated for this plan)**: migration numbers
  are assigned at implementation time, sequential after whatever is latest in master
  at that moment — never pre-assigned in this document. As of 2026-07-05, next is
  `0017`; if F3 (RQ) merges before F2 (fm_hash) — the expected order per the
  Orquestación section below — F2's migration takes whatever number follows F3's.
  **Never two migrations developed concurrently against the same base number.**
- **`ResearchQuestion.code` column shape**: `String(32), unique=True, nullable=False`
  — mirrors `Concept.code` exactly (`knowledge.py:184-186`) for consistency; no
  rationale to diverge found in ADR-0022 or ITEP-0012.
- **`NoteResearchQuestion` PK shape**: composite PK `(note_id, research_question_id)`
  matching `NoteConcept`'s shape, with `stance` as a non-key `String` column
  constrained by `CheckConstraint` to `supports|contradicts|contextualizes` (mirrors
  `Concept.domain`'s `_TAXONOMY_DOMAINS` CheckConstraint pattern in `knowledge.py:170-176`).
  A note may only take one stance per RQ (composite PK enforces this) — re-linking
  with a different stance is an update, not a new row. ★ confirm this "one stance per
  note-RQ pair" constraint is the intended semantic (vs. allowing multiple stance rows
  per pair) before F3 GREEN.
- **RQ resolver is new, not reused**: `resolve_research_questions(codes, session, *,
  strict=False)` in a new `src/workflow/research_question/service.py`, same
  `(found, issues)` return shape as `resolve_concepts`, but a distinct function per
  ADR-0022's explicit instruction ("template to follow, not to reuse directly").
- **Slug-only strict, no exceptions**: `ResearchQuestion.code` follows the ITEP-0012
  2026-07-04 amendment exactly — CLI `--code` flags and frontmatter `questions:` entries
  are the only accepted keys; no question-text-based lookup path, ever, matching the
  MUST rule already in force for `Concept.code`.
- **Fallbacks**: unknown RQ code → warning (lenient) or error (`--strict`), same
  difflib-suggestion UX as `resolve_concepts`'s unknown-concept path.
- **Status lifecycle**: `open → active → answered|abandoned` is enum-enforced via
  CheckConstraint on `ResearchQuestion.status` (mirrors the `note_type`/`domain`
  CheckConstraint pattern already used twice in this codebase — `notes.py:124-127`,
  `knowledge.py:170-176`). No state-machine transition validation in F3 (e.g. no
  guard against `answered → active`) — out of scope, flagged in Risks.

---

## Decisions — LOCKED (user, 2026-07-05)

1. F1's spike is a hard prerequisite for F2 — no fm_hash schema/code work begins
   before the benchmark verdict, per ITEP-0014's own Status gate (not a new decision,
   restated from the ADR).
2. NO-GO closes ITEP-0014 as `Rejected-with-evidence`; this is a valid terminal state
   for this plan, not a blocker to re-open later without new evidence.
3. F3 (ResearchQuestion) and F1 (spike) run in parallel — they are schema/module
   disjoint (spike touches `scripts/bench/` + a tmp vault copy only; RQ touches
   `db/models/`, `db/migrations/`, a new `research_question/` module). F2 (if GO)
   never runs concurrently with F3 per the global migrations rule; if both are ready
   at once, F3 migrates first (RQ is a feature; fm_hash is an optimization).

---

## Phases

### Phase 1 — fm_hash benchmark spike (resolves ITEP-0014 gates 1-2)

**Goal:** Produce a GO/NO-GO verdict, backed by real numbers on the actual vault, for
whether `fm_hash` incremental sync is worth building — and answer ITEP-0014's 4 Open
Questions concretely enough to implement (if GO) without re-deriving them mid-F2.

**RED tests** (`tests/workflow/notes/test_fm_hash_spike.py`):

- Benchmark harness function `run_sync_benchmark(vault_copy_path, runs=5)` returns a
  dict with cold/warm timings and per-pass breakdown — test against a small synthetic
  fixture vault (not the real one) asserting the shape of the returned dict.
- Hash function `compute_fm_hash(frontmatter_raw, body)` — deterministic, same input
  → same output; different body → different hash; matches ITEP-0014's own formula
  (`sha256(frontmatter_yaml_raw + "\n---\n" + body)`) byte-for-byte, verified against
  a hand-computed fixture hash.
- Verdict function `evaluate_spike(benchmark_result, thresholds) -> {"verdict": "GO"|"NO-GO", "reasons": [...]}`
  — pure function, no I/O, testable with synthetic timing inputs at both sides of
  whatever threshold is chosen.

**GREEN impl** — files touched:

- `scripts/bench/fm_hash_spike.py` (new) — CLI-invocable benchmark harness: copies
  vault to tmp (`shutil.copytree`), instruments `sync_vault()` cold + warm, prints
  JSON verdict.
- `src/workflow/notes/hashing.py` (new) — `compute_fm_hash()` pure function, reused
  unconditionally by F2 if GO (kept separate from the harness so F2 doesn't duplicate
  the hash formula).
- Verdict artifact (opus-authored, human-reviewed): `tasks/audit/2026-07-05-fm-hash-spike-benchmark.md`
  — records the real numbers, the GO/NO-GO call, and explicit answers to ITEP-0014's
  4 Open Questions (scope of hash, split hashes, dry-run contract, concurrent-write
  races) regardless of verdict direction.
- `docs/ADR/ITEP-0014-incremental-sync-via-content-hash.md` (edit) — Status line and
  Change Log updated with the verdict; if NO-GO, Status becomes `Rejected-with-evidence`
  and this closes the ADR (no further phases in this plan touch it).

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P1. This commit
happens **regardless of GO/NO-GO** — the spike + verdict is the deliverable either way.

---

### Phase 2 — fm_hash schema + skip-gate (ONLY if Phase 1 verdict = GO)

**Goal:** Implement the `fm_hash` column and sync skip-gate exactly as ITEP-0014
specifies, using Phase 1's answers to the 4 Open Questions as the concrete design
(not re-derived here).

**RED tests:**

- Migration adds `note.fm_hash` (nullable `TEXT`), idempotent (re-running the
  migration is a no-op on an already-migrated DB) — standard ITEP-0010 migration
  idempotency test pattern.
- `sync_vault()` on an unchanged file (same hash) skips parse+upsert — verified by
  a spy/counter on the parse function, not just by absence of DB writes (protects
  against accidental silent no-op paths dragging in a false-positive skip).
- `sync_vault(..., force=True)` bypasses the skip-gate even when hash matches.
  Existing `--force`/`--rebuild-edges` flags — extended semantics only, not new flags.
- `sync_vault(..., dry_run=True)` never writes `fm_hash` (per Phase 1's answer to
  Open Question 3 — dry-run stays read-only).
- Existing notes with `fm_hash IS NULL` (pre-migration data) always take the full
  parse+upsert path on first post-migration sync — migration test, not just unit test.

**GREEN impl** — files touched:

- `src/workflow/db/migrations/global/<NNNN>_note_fm_hash.py` (new migration — number
  assigned at implementation time per the sequencing rule; ≥0017, and after F3's
  migration if F3 lands first).
- `src/workflow/db/models/notes.py` (edit) — `Note.fm_hash: Mapped[str | None]`
  column, nullable, no unique constraint (identical content across notes is legal
  — e.g. two empty stub notes).
- `src/workflow/notes/sync.py` (edit) — skip-gate inserted into the Pass 1 per-file
  loop (line ~415 as of 2026-07-05 — **re-verify against master**, see the
  cross-wave note in Verified anchors); reuses `compute_fm_hash()` from Phase 1's
  `hashing.py`.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P2.

---

### Phase 3 — ResearchQuestion schema + CLI

**Goal:** `ResearchQuestion` and `NoteResearchQuestion` exist as first-class DB
entities with a working `notes question add|list|link` CLI, independent of F1/F2.

**RED tests** (`tests/workflow/research_question/test_service.py`, `test_cli.py`):

- `ResearchQuestion` create/list round-trip via the service layer; `code` uniqueness
  enforced (duplicate `--code` on `add` fails loud).
- `status` CheckConstraint rejects an out-of-enum value at the DB layer (matches the
  existing `note_type`/`domain` constraint test pattern).
- `resolve_research_questions(codes, session, strict=...)` — unknown code → warning
  (lenient) / error (strict), with difflib suggestion — mirrors `resolve_concepts`
  test shape exactly.
- `notes question link --note <ref> --code <slug> --stance supports` creates a
  `NoteResearchQuestion` row; re-linking same (note, RQ) pair with a different
  `--stance` updates in place (composite-PK semantics, not a duplicate row);
  `--remove` deletes it.
- `notes question list --json` output shape test (contract test, since this is a
  new JSON surface with no ADR pinning it — treat the test itself as the initial
  contract, flag for a future ADR if the surface grows).

**GREEN impl** — files touched:

- `src/workflow/db/migrations/global/<NNNN>_research_question.py` (new migration —
  number assigned at implementation time; this is the migration expected to land
  *first* among F2/F3 per the Decisions section above).
- `src/workflow/db/models/knowledge.py` or a new `db/models/research_question.py`
  (new) — `ResearchQuestion` entity (id, code, question_text, status, created_date,
  closed_date, main_topic_id FK nullable). ★ confirm which models module houses it —
  `knowledge.py` (alongside `Concept`/`MainTopic`) is the precedent-consistent choice
  since ADR-0022 frames it as "parallel in spirit to Concept."
- `src/workflow/db/models/notes.py` (edit) — `NoteResearchQuestion` M2M class, added
  near `NoteConcept` (line 260) for locality.
- `src/workflow/research_question/service.py` (new) — CRUD + `resolve_research_questions`.
- `src/workflow/research_question/cli.py` (new) — `notes question` Click group:
  `add|list|link`, following `workflow.evaluation`/`workflow.concept` CLI split
  (service/formatter/cli separation).
- `src/workflow/research_question/formatters.py` (new) — table + JSON output.
- `CLAUDE.md` — new command-table row + Key Patterns bullet (mirrors the existing
  Concept CLI bullet's structure).

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P3.

---

### Phase 4 — frontmatter `questions:` ingestion (depends on Phase 3 committed)

**Goal:** `notes sync` ingests a note's `questions:` frontmatter list into
`NoteResearchQuestion` rows, the same way `_sync_note_concepts` does for `concepts:`.

**RED tests:**

- `_sync_note_research_questions(session, note, fm, *, strict=False)` — same
  `(upserted_count, issues)` return shape as `_sync_note_concepts`; empty/missing
  `questions:` key → `(0, [])`.
- `sync_vault()` end-to-end: a note with `questions: [some-rq-slug]` in frontmatter
  produces a `NoteResearchQuestion` row after sync (no explicit `--stance` in
  frontmatter — default stance is `contextualizes`, the most neutral of the three;
  ★ confirm this default with the user, ADR-0022 doesn't specify one).
- `validate notes --strict-questions` (new flag, mirrors `--strict-concepts`) exits
  nonzero on an unresolvable RQ slug.
- Wait-gate regression test: this pass composes correctly whether it runs before or
  after Wave 0/1's own sync-pass changes land (i.e., the test targets
  `_sync_note_research_questions` in isolation, not a specific line position in
  `_run_write_passes`, so it survives the refactor Wave 0/1 may have already done).

**GREEN impl** — files touched:

- `src/workflow/notes/sync.py` (edit) — new `_sync_note_research_questions()`
  function cloned from `_sync_note_concepts` (line 293) shape; wired into
  `_run_write_passes()` (line 366) alongside the existing concept pass.
- `src/workflow/validation/schemas.py` (edit) — `--strict-questions` validation path,
  mirrors the existing `--strict-concepts` check.
- `CLAUDE.md` — update the `notes sync` / `validate notes` bullets to mention the
  new pass and flag.

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P4.

---

## Risks / out of scope

- **In scope:** F1 spike + verdict (always), F2 fm_hash impl (only if GO), F3
  ResearchQuestion schema + CLI, F4 frontmatter ingestion + validator support.
- **Out of scope:** `workflow synth` (explicitly deferred by ADR-0022 itself and the
  fleeting-harvest spec — no design work here, appendix note only, not a phase);
  RQ status state-machine transition validation (any status → any status allowed at
  DB layer, no guard rails); split hashes (frontmatter vs body) unless Phase 1's
  benchmark specifically finds ITEP-0013's edge-rebuild pass is the dominant cost
  (Open Question 2 — resolved by the spike, not pre-decided here); concurrent sync
  process hash-write races (Open Question 4 — Phase 1 must document a chosen
  mitigation or explicitly accept the race as a known limitation, not silently
  ignore it).
- **Risk:** F1's spike runs against a **copy** of the real vault, never the live one
  — gate on `shutil.copytree` to a tmp dir before any benchmark write path executes;
  never point `WORKFLOW_VAULT_ROOT` at the real vault during the benchmark.
- **Risk:** cross-wave line-number drift — Wave 0 (D1 `sync_note_files` extraction)
  and Wave 1 (FTS write-hook) both plan to touch `sync.py`'s pass loop before this
  plan's F2/F4 phases start. Gate: re-verify `sync.py` anchors against master
  immediately before starting F2 or F4 (see wait-gate 3 in Orquestación below);
  whoever starts second rebases onto the other's landed refactor.
- **Risk:** NO-GO on F1 is not a failure state and must not be treated as blocking
  this plan's completion — Phase 1's commit point is reached either way.
- **Risk:** `ResearchQuestion.main_topic_id` is nullable per ADR-0022's own
  Consequences section, deferring the "should it be required" question to when
  `synth` exists — do not pre-decide that here; F3 implements nullable as specified.
- No schema migration expected for F1 (spike is code + docs only, no DB changes).

---

## Orquestación

| Role | Model | Responsibility |
|---|---|---|
| Director | (human/parent) | Sequences phases, resolves wait-gates, confirms ★ items, runs final integrated suite |
| Implementer | sonnet | RED tests + GREEN impl for each phase; reads/writes code |
| Reviewer | opus | reviewer-esquema per phase; **also** authors the F1 verdict artifact and GO/NO-GO call (deepest-reasoning task in this plan) |
| Git-ops | haiku | Commits at each phase's GREEN, tags reviewer-esquema pass/fail in commit trailer |

**Parallelization**: F1-spike ‖ F3-RQ run concurrently — they are schema/module
disjoint (F1 lives in `scripts/bench/` + a tmp vault copy + `notes/hashing.py`; F3
lives in `db/models/`, `db/migrations/`, a new `research_question/` module). Launch
both as soon as this plan is confirmed; no ordering dependency between them.

**F2 exclusivity rule (REGLA GLOBAL DE MIGRACIONES)**: never two migrations developed
concurrently. F2 (if GO) never runs in parallel with F3 — migration numbers are
assigned sequentially at implementation time, immediately after whatever is latest in
master. If F1's GO verdict and F3's completion land at the same time, **F3 migrates
first** (RQ is a feature; fm_hash is an optimization — director's explicit tie-break
rule, restated from the roadmap synthesis).

**Wait-gates:**

1. **F4 waits on F3 committed** — the frontmatter sync pass needs `ResearchQuestion`/
   `NoteResearchQuestion` to exist and `resolve_research_questions` to be stable
   before cloning `_sync_note_concepts`'s shape against it.
2. **F2 waits on F1's opus verdict** — GO/NO-GO is the literal gate; do not start F2
   speculatively "in case" F1 comes back GO.
3. **F4's new sync pass waits on Wave 1's FTS pass being merged, if both touch
   `sync_note_files`/`_run_write_passes`** — coordinate with whoever is running Wave 1
   at implementation time; whoever lands second rebases onto the first's refactor of
   the shared pass loop. This is a real risk given Wave 0/1 both plan changes to the
   same function before Wave 2 starts (see Verified anchors cross-wave note).
4. **reviewer-esquema runs pre-commit for every phase** — no phase's GREEN commit
   lands without it, per this repo's standing convention (not new to this plan).
5. **Director runs the full integrated suite post-merge** of each phase — the
   per-phase "suite green" in each Commit point is the implementer's own local run;
   the director's post-merge run is the integration checkpoint that catches
   cross-phase interaction (e.g., F2's skip-gate interacting badly with F4's new
   sync pass if both touch the per-file loop).

---

## Verification (each phase)

```bash
# Isolated suite — never touches live DB
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py

# Lint
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10

# F1 spike — runs against a COPY of the real vault, never the original
# cp -r ~/01-U/0000AA-Vault /tmp/vault-bench
# uv run python scripts/bench/fm_hash_spike.py --vault-copy /tmp/vault-bench --runs 5 --json

# F2/F3/F4 live dry-run (on a COPY of the live DB, never the original)
# cp ~/.local/share/workflow/workflow.db /tmp/workflow-test.db
# WORKFLOW_DATA_DIR=/tmp workflow notes sync <vault_root> --dry-run
```
