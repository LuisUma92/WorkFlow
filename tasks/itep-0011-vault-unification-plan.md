# ITEP-0011 — Vault Unification: Implementation Plan

**Companion ADR:** `docs/ADR/ITEP-0011-vault-unification.md` (Status: **Accepted** 2026-05-06)
**Blocks:** Phase B of `tasks/requests/2026-05-04-zettelkasten-main-topic-bundle.md`
**Vault root (default):** `~/Documents/01-U/0000AA-Vault/` (XDG-configurable)

## P0 — ADR review & accept (no code) — **DONE 2026-05-06**

- [x] User reviewed ADR; OQ1–OQ4 resolved + new OQ5 (SqlNoteRepo→global) and OQ6 (migration deferred to P2).
- [x] Status flipped Proposed → Accepted.
- [ ] `mkdir -p ~/Documents/01-U/0000AA-Vault/notes/{permanent,literature,fleeting}` (user task before P3 cutover).
- [ ] Add `vault_root` key to `~/.config/workflow/config.yaml` (defer to P2 alongside `workflow vault info`).

## P1 — Add note tables to GlobalBase (parallel) — **DONE commit `c02d788`**

**Shipped:**
- `src/workflow/db/models/notes.py` — `Note`, `Citation`, `Label`, `Link`, `Tag`, `NoteTag` re-bound `LocalBase` → `GlobalBase`. Added staged `Concept`, `NoteConcept` (ITEP-0012 precondition; tables empty).
- `src/workflow/db/models/academic.py` — `MainTopic.concepts` reciprocal relationship.
- `src/workflow/db/models/__init__.py` — re-export `Concept`, `NoteConcept`.
- 4 test fixtures call `GlobalBase.metadata.create_all` alongside `LocalBase.metadata.create_all`.
- `tests/workflow/lecture/test_cli.py` — 4 lecture CLI tests `xfail`-marked (P3 unblocks them).

**Deviations vs. original plan (locked):**
- **No `_LegacyNote` shadow class** kept. Original plan called for keeping LocalBase definitions to read old slipbox.db. Decision: P2 reads legacy slipboxes via raw SQL (`sqlite3.connect`) or a transient `Table()` reflection — simpler than dual ORM classes that share `__tablename__`.
- **No migration file `0003_add_note_tables.py` shipped in P1.** P1 used `GlobalBase.metadata.create_all`. ITEP-0010 forward-only migration is **deferred to P2** (OQ6).

**Verification (actual):**
```bash
pytest --ignore=tests/test_database.py
# 848 passed, 4 xfailed (P3 placeholders), 1 pre-existing UCR-sty failure unrelated.
```

## P2 — `workflow vault unify` command — **NEXT**

**Files:**
- `src/workflow/vault/cli.py` (new module).
- `src/workflow/vault/unify.py` (new) — migration logic.
- `src/workflow/db/migrations/global/0003_add_note_tables.py` (new) — forward-only `CREATE TABLE` for `note`, `label`, `link`, `citation`, `tag`, `note_tag`, `concept`, `note_concept` (ITEP-0010 / OQ6). Idempotent guard: `CREATE TABLE IF NOT EXISTS` so it composes with the P1 `metadata.create_all` already run on dev DBs.
- Legacy slipbox reader: raw `sqlite3.connect(<project>/slipbox.db)` queries against `note`, `label`, `link`, `citation`, `tag`, `note_tag`. **No `_LegacyNote` ORM class.**

**Surface:**
```bash
workflow vault info
workflow vault validate                    # check vault structure
workflow vault unify [--project DDTTAA-YYPP] [--dry-run] [--backup-dir <path>]
                     [--rename-strategy project-prefix|abort|manual]
                     [--auto-fix=N]         # OQ2 collision handling
```

**Algorithm:**
1. Snapshot every targeted slipbox.db to `<backup_dir>/<project>-<ts>.db`.
2. Read `note`, `link`, `citation`, `tag` from each slipbox.
3. Detect frontmatter-id collisions across projects + global; apply `--rename-strategy`.
4. Insert into GlobalBase (id remap dict per project).
5. Move `<project>/notes/**/*.md` → `<vault_root>/notes/<type>/`.
6. Write `.vault_pointer` marker into project dir.
7. Verify counts: `len(global_after) - len(global_before) == sum(len(slipbox))`.
8. Print report; exit non-zero if any orphan or count mismatch.

**Tests** (`tests/workflow/test_vault_unify.py`, new):
- `test_unify_empty_slipbox` — no rows, no-op, exit 0.
- `test_unify_single_project_round_trip` — copy + verify counts.
- `test_unify_id_collision_with_project_prefix` — rename strategy applied.
- `test_unify_id_collision_abort` — exit non-zero, no writes.
- `test_unify_dry_run_no_writes` — temp dir untouched.
- `test_unify_idempotent` — second run = no-op.
- `test_unify_backup_created` — backup file exists with correct size.
- `test_unify_rewrites_link_fks` — Link.source_note_id remaps correctly.
- `test_unify_moves_md_files` — files relocated, originals gone, .vault_pointer present.
- `test_unify_orphan_link_detection` — Link with missing target → reported, not migrated.

## P3 — Repository switch + Phase-B-unblock gate

**Decision (OQ5):** `SqlNoteRepo` locks to a GlobalBase session — no dual-engine support. Project-scoped note queries route through the future `ProjectNoteRepo` (P5) once `project_note` table lands.

**Files:**
- `src/workflow/db/repos/sqlalchemy.py::SqlNoteRepo` — session arg becomes the global session; remove any LocalBase fallbacks.
- `src/workflow/lecture/cli.py` — `_get_local_engine` → `init_global_db()` for `scan`, `link`, `build-eval` note ops.
- `src/workflow/lecture/scanner.py`, `src/workflow/lecture/linker.py` — session arg = global.
- `src/workflow/graph/collectors.py` — `collect_notes(global_session)`; remove the LocalBase note-query branch.
- `src/latexzettel/infra/orm.py` + `infra/db.py` — shim points at GlobalBase session factory.
- `src/workflow/notes/cli.py` (Phase A) — `notes new` writes to `<vault_root>/notes/<type>/`.
- `src/workflow/notes/discovery.py` (Phase A) — root resolution checks `vault_root` first.
- Feature flag: `WORKFLOW_VAULT_MODE=unified` env / config key. Default off until P4.

**Tests:**
- Remove the 4 `xfail` marks on `tests/workflow/lecture/test_cli.py::{test_scan_command_finds_tex_files, test_scan_empty_dir_message, test_scan_registers_notes_in_db, test_link_command_processes_tex_files}`.
- Update `tests/workflow/graph/test_collectors.py` `local_session` fixture: rename to `global_session_with_notes` (or fold into existing `global_session`).

**Verification:** full `pytest` green; `workflow notes new` smoke test writes to vault; `workflow graph stats` reads from GlobalBase.

**Gate:** at end of P3, Phase B of the bundle request can begin (real FK migration is now possible).

## P4 — Drop LocalBase note tables (irreversible)

**File:** `src/workflow/db/migrations/local/0003_drop_note_tables.py` — DROP `note`, `label`, `link`, `citation`, `tag`, `note_tag` from LocalBase schema. Bump LocalBase schema version.

**Pre-flight check:** abort migration if any LocalBase has non-zero `note` rows AND `WORKFLOW_VAULT_MODE != unified`.

## P5 — New LocalBase tables

**Files:**
- `src/workflow/db/models/project_layer.py` — new. `PrismaDecision`, `ProjectNote` (Enum kind: `idea | hypothesis | connection`).
- `src/workflow/db/migrations/local/0004_add_project_layer.py` — CREATE TABLE.
- Data migration for PRISMA decisions: `workflow prisma migrate-decisions` reads existing PRISMA web-app rows, writes into `prisma_decision`.

**CLI surface (Phase 5.5, separate plan if needed):**
```bash
workflow project-note new --kind idea|hypothesis|connection --body <txt> [--global-note <id>]
workflow project-note list [--kind <k>]
workflow prisma decision list|add|edit
```

## P6 — Downstream consumer updates

| Consumer | Change |
|---|---|
| `src/latexzettel/infra/orm.py` | Switch shim's session factory from LocalBase to GlobalBase. |
| `src/latexzettel/server/*.py` | RPC routes that touched `Note`/`Link`/`Citation` now resolve via vault root. |
| `nvim-plugin` (`~/.config/nvim/lua/workflow/*`) | Update note picker root to `vault_root`. |
| `src/lectkit/nofi.py` | Output target = `<vault_root>/notes/permanent/`. |
| `src/workflow/lecture/scanner.py` | Register scanned `.tex` notes against GlobalBase. |
| `src/workflow/graph/collectors.py` | Drop the LocalBase query branch for notes; consolidate. |

## P7 — Close-out

- [ ] ADR ITEP-0011 status → Implemented.
- [ ] CLAUDE.md updated: vault_root section, project-note CLI bullet.
- [ ] `docs/wiki/Home.md` — vault layout diagram.
- [ ] Test count check: regressions = 0, vault tests added.
- [ ] Tag `v?.?.0` (vault-unified release).

## Risks

- **R1 (HIGH):** Data loss during `vault unify`. Mitigation: mandatory backup, dry-run-by-default, count verification, idempotency tests.
- **R2 (MED):** Stale paths in `latexzettel` Pandoc filter and TikZ link-resolver. Mitigation: P6 inventory pass with grep for `slipbox.db`.
- **R3 (MED):** User has 8 slipboxes; per-project opt-in (OQ1) means partial-vault state is normal for weeks. Tests must cover mixed-mode (some projects unified, some not).
- **R4 (LOW):** Vault grows large; git status slow. Mitigation: vault git is optional (OQ3), out of scope.

## Sequencing (revised 2026-05-06)

```
Session 2026-05-04: P0 + P1 — DONE (P0 accept 2026-05-06, P1 commit c02d788)
Session N+1:        P2 (the heavy one — vault unify CLI + 0003 migration)
Session N+2:        P3 → Phase B unblocked
Session N+3:        P4 + P5
Session N+4:        P6 + P7
```

## Status
`in-progress` — P0 accepted, P1 shipped. **Next: P2.**
