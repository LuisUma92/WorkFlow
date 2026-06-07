# Roadmap — note-graph completion + editor-first tooling (2026-06-06)

> Snapshot. Sequences three open ADRs (ITEP-0013/0014/0015), three 2026-05-03
> requests, and the deferred items from the 2026-06-06 template-gap reviewer-esquema.
> **Every claim below was verified against source on 2026-06-06** — the ADRs and
> requests predate large parts of the implementation and are stale.

## State of the world (code truth, not doc claims)

### ITEP-0013 — note relation graph: ~70% SHIPPED (ADR INDEX still says "Proposed" — stale)

| ADR phase | Claim | Reality (verified) |
|---|---|---|
| P0 migration `note_edge` + indexes | pending | ✅ `0007_add_note_edges.py` |
| NoteEdge ORM model | pending | ✅ `db/models/notes.py`; vocab constants now single-source there (commit `d9c7d39`) |
| P1 frontmatter `relations` DTO | pending | ✅ shipped in template-gap wave — `NoteRelations`/`RelationEdge`/`entry_point` (`209987d`) |
| P2 reindex → `note_edge`, unresolved=NULL | pending | ✅ `sync.py:248 _upsert_note_edges`, `parse_relations_frontmatter`, `edges resolve` (`resolve.py`), `upsert_note_edge` |
| P3 validator | pending | 🟡 PARTIAL — `notes edges check` (cycles only, via `dag.detect_structural_cycles`) + `edges resolve` exist; **no unified `validate notes --graph`** (orphan/unresolved/self/duplicate as warnings) — an ADR **MUST** |
| P4 CLI | pending | ❌ `notes link --relation` absent (link has concept/reference/exercise/main-topic only, `cli.py:566`); `graph trace`/`graph resume` absent; `graph orphans` not lineage-aware |
| `sync --rebuild-edges` (MUST) | pending | ❌ absent — `sync` has no rebuild/force-edges flag; default sync upserts edges incrementally only |
| `notes enums --json` (MUST, single-source) | pending | ❌ absent — the keystone gap |

### ITEP-0015 — editor-first tooling: PARTIALLY in motion, keystone missing
- Depends on ITEP-0013 P2.1 (NoteEdge model) → **landed, unblocked.**
- nvim `picker/edges.lua` **already exists** — but with no `notes enums --json` it can only hard-code the enum lists, which **violates the ITEP-0013 single-source MUST** (same drift class as ADR-0017). Unverified but near-certain.
- ❌ `notes enums --json`, ❌ `notes new-id`, ❌ `note_alias` table + alias resolution, ❌ in-buffer `:WorkflowValidate` on `BufWritePost`.

### ITEP-0014 — incremental sync (`fm_hash`): correctly PARKED
- Status: Proposed placeholder. ADR's own gate: **MUST NOT** begin before (1) a benchmark justifies it, (2) open questions resolved, (3) ITEP-0013 ships. `fm_hash` column absent. Not near-term work — only a benchmark spike belongs on this roadmap.

### The three 2026-05-03 requests
- `notes-crud-subcommands` — ✅ CLOSED/implemented (all CRUD + bonus sync/edges exist).
- `note-frontmatter-main-topic` — ✅ CLOSED/implemented. Residual: concept cross-check is discipline-area-scoped, not exact `Concept.main_topic_id == main_topic`. Micro-follow-up only if exact-match is wanted.
- `graph-export-tikz-filters` — 🟡 OPEN. Shipped: `--main-topic`/`--discipline-area`/`--topic` (`graph/cli.py:109,261`). Missing: `--depth`, `--cluster`, `--include-tags`/`--exclude-tags`, `--layout`, `--color-by`, and the `--main-topic`+`--cluster` mutex.

### Deferred from the 2026-06-06 reviewer-esquema
- `notes enums --json` (HIGH-1 completion — constants consolidated onto the model `d9c7d39`; CLI surfacing is the next step). **→ Wave 1.**
- Validator↔ingest **two-parser** duplication (`schemas._validate_relations` strict vs `edges.parse_relations_frontmatter` lenient). **→ Wave 1 (fold).**
- weight range / list caps, init.py↔live-vault template parity test, `None` vs empty `NoteRelations` normalization. **→ small tasks folded where relevant.**

---

## The invariant everything serves

```
            workflow.db.models.notes  ← SINGLE SOURCE (vocab constants, d9c7d39)
                        │
      ┌─────────────────┼───────────────────────────┐
 notes enums --json   validate notes --graph     ORM CHECK
 (W1, MUST)           (W2, MUST)                  constraints
      │                       │
   nvim pickers          CI / pre-commit
   (W5, ITEP-0015)       (W2)
```

`notes enums --json` is the keystone: an ITEP-0013 MUST, the ITEP-0015 §A foundation,
and the natural completion of last review's constant-consolidation. Everything
human/agent/editor-facing reads the closed sets from there — never re-encodes them.

---

## Wave 1 — Single-source introspection (keystone; unblocks W5 + closes review HIGH-1)

- **`workflow notes enums [--json]`** — emit `edge_class`, `relation_type` (split structural/associative), `note_type`, and the `zettel_id_format` block (per ITEP-0015 §A schema). Derive strictly from `db.models.notes` constants. **Test gate: assert CLI output == ORM CHECK values** (drift guard — ITEP-0015 MUST).
- **`workflow notes new-id`** — emit one fresh NanoID (PyPI `nanoid`; alphabet/len from the same constants). Foundation for `notes new` filename convention + the `<prefix>en` keymap.
- **Fold deferred cleanups:** (a) unify the two relation parsers — one tokenizer in `edges.py`, two policies (lenient-skip for sync, strict-collect for validate) so id/type/weight rules can't drift; (b) optional weight range check; (c) `init.py`↔live-vault template parity test.
- Gate: `notes enums --json` is consumed by at least one consumer (the W2 validator) before W5 rewires the nvim picker onto it.

## Wave 2 — `validate notes --graph` (completes ITEP-0013 P3 MUST)

- Add `--graph` to `validate notes`: report **cycles** (reuse `dag.detect_structural_cycles`), **unresolved** targets (reuse `resolve.py`), **orphans** (no structural edge & not `entry_point: true`), **self-edges**, **duplicate edges** — errors for cycles, warnings for the rest (per ADR Failure-Mode table).
- This is the CLI-equivalent surface the ADR mandates for CI/pre-commit and the W5 in-buffer check. `notes edges check` stays as the focused cycle-only command.

## Wave 3 — Rebuild + traversal CLI (completes ITEP-0013 P4 + rebuild MUST)

- **`sync --rebuild-edges`** (MUST) — drop `note_edge` in scope, full re-import; `--force` bypasses any future hash gate. Per-file atomic delete-by-`source_id`.
- **`notes link --relation <type> --target <zettel_id>`** — append a `derived_from`/`links` entry to frontmatter (edge_class inferred from type via W1 enums); re-validate before write.
- **`graph trace <zettel_id>`** (DFS-to-root lineage) and **`graph resume <zettel_id>`** (bounded forward BFS) — both take `--max-depth`/`--node-budget` per ADR traversal pseudocode; reuse `graph/analysis.py` BFS. Extend `graph orphans` to flag lineage roots distinctly.

## Wave 4 — `graph export-tikz` filters (the open request; independent — can parallel W2/W3)

- Add `--depth <N>` (neighbour ring; reuse the `graph neighbors` BFS), `--cluster <name>` (consume `graph clusters` output), `--include-tags`/`--exclude-tags`, `--layout <force|radial|hierarchical>`, `--color-by <main_topic|tag|type>`, and the `--main-topic`+`--cluster` **mutex (exit 2)**. Acceptance criteria already enumerated in the request file.

## Wave 5 — ITEP-0015 editor tooling (after W1 + W2)

- Rewire nvim `picker/edges.lua` + new `enums.lua` to read `notes enums --json` (kills the hard-coded-enum drift). Pickers: relation_type, edge_class, note-id, bibkey, concept — all insert/yank modes, session-cached, `:WorkflowReloadEnums`.
- `:WorkflowValidate` on `BufWritePost` → `validate notes --graph <buffer>` as Neovim diagnostics (reuses W2).
- `note_alias` table (`note_id` FK + `alias UNIQUE`) + sync alias-resolution order (zettel_id → alias → reference); `notes new` auto-populates 3 alias forms. Migration `0016` (next free slot).
- `<prefix>en` → `notes new-id` paste; YAML snippet expansions for `derived_from:`/`links:`.

## Parked / out of scope

- **ITEP-0014 incremental sync** — gated. Only deliverable now: a one-off **benchmark spike** of `sync_vault()` on a realistic corpus to decide if/when it's justified. No `fm_hash` code until that + ITEP-0013 fully ships.
- **main_topic exact-match** (`Concept.main_topic_id == main_topic`) — micro-task; file only if discipline-area scoping proves insufficient.

## Doc hygiene (do alongside the waves)

- Flip ADR INDEX: ITEP-0013 `Proposed → Accepted`, set `implemented_date` once W2+W3 MUSTs land.
- **ITEP-0014 and ITEP-0015 are absent from `docs/ADR/INDEX.md`** — add both rows.

---

## Sequencing rationale

1. **W1 is the keystone** — it's a MUST for *two* ADRs and the completion of the last
   review's consolidation. Cheap (constants already exist on the model). Everything
   editor/CI-facing depends on it.
2. **W2 before W5** — the in-buffer validator is just the CLI `--graph` surface wrapped
   in diagnostics; build the CLI truth first.
3. **W3 completes the remaining ITEP-0013 MUSTs** (`--rebuild-edges`) + the P4 traversal
   surface; depends on nothing but the existing edge tables.
4. **W4 is orthogonal** (graph rendering) — parallelizable; only needed the already-shipped
   `main_topic` field.
5. **W5 is the human-payoff layer** — gated on W1 (enums) + W2 (validate).
6. **ITEP-0014 stays parked** by its own ADR gate — benchmark first.

## Verified anchors (2026-06-06)

- `notes/cli.py`: init 53, new 77, create 148, list 216, show 287, tag 314, sync 351, edges group 428 (list 433 / show 481 / check 505 / resolve 535), link 566. **No enums/new-id.**
- `notes/sync.py:248 _upsert_note_edges`; `parse_relations_frontmatter` consumed at 398/421. **No --rebuild-edges.**
- `notes/dag.py::detect_structural_cycles`; `notes/resolve.py::resolve_edge_targets`.
- `graph/cli.py`: `_filter_options` 106, export-tikz 261 (only project/output/standalone/main-topic/discipline-area/topic), neighbors 366 (`--depth` 368, BFS). **No trace/resume.**
- `validation/cli.py`: **no `--graph`** on `validate notes`.
- Schema: **no `note_alias`, no `fm_hash`**. Latest global migration = `0015_bib_relation` → next = `0016`.
- nvim `picker/edges.lua` exists (likely hard-codes enums — confirm in W5).
- ADR INDEX lists ITEP-0013 as Proposed; ITEP-0014/0015 not listed.
