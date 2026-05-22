# Post-ITEP-0011 Route Map — three-phase roadmap

## Context

ITEP-0011 closed at `6cb2086` / `v1.3.0`. A gap audit surfaced concrete
unfinished work in `Accepted`/`Implemented` ADRs. This plan sequences the
top three workstreams in priority order set by the user:

1. **ADR-0001** — `notes link` semantic layer: notes link in frontmatter only;
   DB `Link`/`Label` tables are never written by user-facing CLI.
2. **ITEP-0013** — Note relation graph: `note_edge` table directed lineage +
   associative edges. ADR is **Proposed** (must be accepted before code).
3. **(deferred)** — Either close the ITEP-0012 forward-dependency
   (`notes link --concept` must reuse `resolve_concepts` and materialize
   `note_concept` rows), or tackle LZK-0004 (migrate 7 `latexzettel/api/`
   modules off the shim onto `workflow.notes` direct SQLAlchemy access).
   Decision deferred — re-evaluate at the end of Phase 2.

After all three phases the toolkit's note layer is end-to-end DB-backed,
queryable, and graph-traversable.

## Methodology (applies to every phase)

### TDD discipline
Follow the `tdd-workflow` / `superpowers:test-driven-development` skill.
Per phase and per sub-feature:
1. **RED** — write failing tests against the public surface first
   (CLI invocation via `CliRunner`, service-layer signatures, repo methods).
2. **GREEN** — minimal implementation to pass.
3. **REFACTOR** — clean up; coverage ≥ 80% for new modules.
Tests live under `tests/workflow/<module>/`. Use the existing
`tests/conftest.py` `global_session`/`local_session` fixtures (SQLAlchemy
in-memory) — **not** the buggy `_isolated_global_db` lecture fixture
(known: sets `XDG_DATA_HOME` but the engine reads `WORKFLOW_DATA_DIR`;
do not propagate this pattern). If a phase needs CLI tests that hit the
global engine, override `WORKFLOW_DATA_DIR` via `monkeypatch.setenv` to
a `tmp_path` directory.

### Reviewer-esquema (4-reviewer parallel)
After each phase implementation is green, run the 4-reviewer parallel
schema (per `~/.claude/projects/-home-luis-02-Projects-WorkFlow/memory/feedback_review_schema.md`):
- `python-reviewer` — PEP 8, type hints, idioms, error handling.
- `security-reviewer` — OWASP, path/SQL injection, secrets, FS safety.
- `tdd-guide` — coverage gaps, brittle/contaminated tests, missing edge cases.
- `architect` (or a fourth opinion when code-reviewer is unavailable) —
  API consistency, layering, reusability, deviation from existing patterns.
Synthesize findings, fix CRITICAL/HIGH inline, document LOW. Commit fixes
under `fix(<scope>):` separate from feature commit.

### Per-phase plan files
Each phase gets its own `tasks/<phase>-plan.md` at execution time, not now.
Naming: `tasks/adr-0001-notes-sync-plan.md`,
`tasks/itep-0013-note-relation-graph-plan.md`. Status field tracked
explicitly (`proposed` / `in-progress` / `done`). This route map stays
short and links out.

### Commit + primer cadence
- Commit at every logical checkpoint (per `feedback_phased_feature_shipping`).
- Tag at end of each phase: `v1.4.0` (phase 1), `v1.5.0` (phase 2), TBD (phase 3).
- Update `~/.claude/primer.md` after each phase commit with new resume state.
- Push policy unchanged: GitHub `public` primary; LAN `origin` on `inm` only.
- 12 commits currently ahead of origin — push before starting phase 1 if
  on `inm` LAN, otherwise carry the backlog forward.

---

## Phase 1 — ADR-0001 closure: `notes sync` command

**Goal:** Make the DB `Link` / `Label` / `Citation` tables a queryable
index of what the Markdown files actually contain. File-as-truth,
DB-as-index — consistent with ADR-0010 (exercises) and the
`lectures scan` / `lectures link` pattern already shipped.

**Approach (chosen by user):** bulk sync command. **Not** write-through
on `notes link` — that would couple the CLI to DB writes and let
out-of-band file edits drift.

### Scope

| Surface | Action |
|---|---|
| `workflow notes sync` | NEW CLI command. Scan `<vault_root>/notes/**/*.md`, parse frontmatter + `[[wikilink]]` body refs, upsert `Note` / `Label` / `Link` rows. Report counts (notes scanned, labels registered, links created, orphans dropped). Idempotent. |
| `workflow notes sync --dry-run` | Report what would change without writing. |
| `workflow notes sync --project <DDTTAA-YYPP>` | Restrict to one project subtree of the vault (forward-compat with ITEP-0011 P5 `ProjectNote`). |

### Critical files

- **NEW** `src/workflow/notes/sync.py` — `sync_vault(vault_root, session, *, dry_run, project_filter) -> SyncReport`. Mirror `link_lecture_files` from `src/workflow/lecture/linker.py:282-332`.
- `src/workflow/notes/cli.py:44` — add `sync` subcommand to the existing notes group.
- `src/workflow/lecture/linker.py` — **reuse** `_upsert_label`/`_upsert_cite`/`_upsert_link` (lines 159, 174, 187). Extract to `src/workflow/notes/linker_ops.py` if necessary, do NOT duplicate. See ADR-0009 (shared parsing) — this is the same pattern.
- `src/workflow/db/repos/sqlalchemy.py:185-203` — reuse `SqlLinkRepo.create`.
- `src/workflow/notes/service.py:220-248` — reuse `_build_id_index` and `read_note` for note discovery.
- Wikilink regex: lift from `src/latexzettel/api/markdown.py` (Pandoc filter) — **search for existing regex first**, do not re-invent.

### Tests (RED first)

`tests/workflow/notes/test_sync.py` (new file):
- `test_sync_empty_vault_noop`
- `test_sync_creates_note_rows_from_md`
- `test_sync_creates_label_rows_from_frontmatter_anchors`
- `test_sync_creates_link_rows_from_wikilinks`
- `test_sync_idempotent_second_run_no_changes`
- `test_sync_dry_run_writes_nothing`
- `test_sync_orphan_link_dropped_and_reported`
- `test_sync_project_filter_scopes_to_subtree`
- `test_sync_path_traversal_in_frontmatter_blocked` (security)

`tests/workflow/notes/test_cli_sync.py`:
- CLI smoke test via `CliRunner` against `tmp_path` vault with `WORKFLOW_VAULT_ROOT` + `WORKFLOW_DATA_DIR` overridden.

Use `tests/conftest.py:17-46` `global_session` fixture.

### Verification

1. `pytest tests/workflow/notes/ -q` — all new tests green; coverage ≥ 80%.
2. `pytest -q --ignore=tests/test_database.py` — no regressions vs the pre-existing baseline (49 failed / 984 passed at master).
3. Smoke against the live vault:
   `WORKFLOW_VAULT_ROOT=/tmp/vault WORKFLOW_DATA_DIR=/tmp/wfdata workflow notes sync --dry-run`
   then without `--dry-run`; verify counts.
4. Re-run on the same vault — second-run delta = 0 (idempotent).
5. 4-reviewer pass on the green branch; fix CRITICAL/HIGH; commit fixes.
6. Tag `v1.4.0`.

### Risks
- **R1 (MED):** wikilink regex divergence between Pandoc filter and new
  sync. Mitigation: extract one regex module, reuse on both sides.
- **R2 (LOW):** schema mismatch — `Link.target_id` is FK to `label.id`,
  not `note.id`. Wikilinks like `[[note-id]]` (no anchor) need a synthetic
  label per note (`label.name = "__note__"`) or a schema extension.
  Resolve in design pass before coding.

---

## Phase 2 — ITEP-0013: Note relation graph (`note_edge` table)

**Goal:** Store directed, typed relations between notes. Lineage edges
(`derived_from`: continuation, refines, branches, synthesis, rebuttal) are
DAG-constrained. Associative edges (`links`: supports, contradicts,
expands, see_also) may cycle.

**Gate before any code:** ITEP-0013 ADR is currently **Proposed**.
P2.0 = user review + accept, status flipped to Accepted, OQs resolved.
Do not write code until this gate clears.

### Phased breakdown (mirror the ITEP-0011 phasing pattern)

| Sub-phase | Deliverable |
|---|---|
| P2.0 | ADR review + accept (Proposed → Accepted). No code. |
| P2.1 | `NoteEdge` model in `db/models/notes.py`; migration `global/0006_add_note_edge.py`; CHECK constraints on `edge_class` / `relation_type`. Tests: model + migration round-trip. |
| P2.2 | `notes sync` (from Phase 1) extended to parse `derived_from:` + `links:` frontmatter sections and upsert `note_edge` rows. Reuses sync infrastructure. |
| P2.3 | `workflow notes graph` CLI: `lineage <NOTE_ID>` (ancestors/descendants), `related <NOTE_ID>` (associative neighbors). Reuses `workflow.graph` collectors where possible. |
| P2.4 | DAG cycle detection on lineage upsert; reject with clear error. |
| P2.5 | Reverse-index query helpers (no stored reverse rows — derived per ADR). |
| P2.6 | Close-out: ADR Implemented, CLAUDE.md, wiki update, tag `v1.5.0`. |

### Critical files (preliminary — finalize at execution)
- **NEW** `src/workflow/db/models/notes.py::NoteEdge` (extend existing file).
- **NEW** `src/workflow/db/migrations/global/0006_add_note_edge.py`.
- `src/workflow/notes/sync.py` — extend with edge parsing.
- **NEW** `src/workflow/notes/graph.py` — DAG validation + traversal helpers.
- `src/workflow/notes/cli.py` — add `graph lineage` / `graph related` subgroup.
- `src/workflow/graph/collectors.py` — extend `KnowledgeGraph` to include edges.
- `docs/ADR/ITEP-0013-note-relation-graph.md` — status flip + implemented_date.

### Tests
RED-first per sub-phase. Coverage focus: cycle detection, idempotent
upsert, frontmatter parsing edge cases (missing target, malformed type),
reverse-query correctness.

### Verification
Per sub-phase pytest gate; 4-reviewer pass after P2.5; smoke against
live vault for lineage/related queries; tag `v1.5.0` at P2.6.

### Risks
- **R1 (HIGH):** schema design under-specified in ADR (Proposed). P2.0 must
  resolve all OQs before any code lands.
- **R2 (MED):** cycle detection cost on large vaults. Mitigation: cycle
  check is per-insert (single new edge), not full graph walk — O(depth)
  not O(N).
- **R3 (MED):** frontmatter migration burden — existing notes will not
  carry `derived_from:` / `links:`. Sync must treat absence as empty.

---

## Phase 3 — Deferred decision point

After Phase 2 closes, re-evaluate priorities. The two candidates:

### Option A — ITEP-0012 forward-dependency closure
- `notes link --concept CODE` (exists at `notes/cli.py:287`) wires
  `resolve_concepts` for code validation; rejects unknown codes
  (strict mode); materializes `note_concept` rows alongside frontmatter
  append.
- Reuses `src/workflow/concept/service.py:91-120` `resolve_concepts`.
- Small (~1 commit) but high daily-use value.

### Option B — LZK-0004 / ADR-0014 closure
- Migrate the 7 `src/latexzettel/api/` modules from shim-dependent code
  to direct `workflow.notes` SQLAlchemy access. ~32 DB call sites.
- Drop the `infra/orm.py` shim once nothing depends on it.
- Removes legacy surface but no new user-facing capability.

Pick at the gate. Do not pre-plan Phase 3 now.

---

## Cross-phase guidelines

### Plan files
- This route map: `/home/luis/.claude/plans/idempotent-conjuring-whisper.md`
  (kept short, links to per-phase plans).
- Per-phase: `tasks/<phase>-plan.md`, status-tracked, written at the
  start of each phase via `EnterPlanMode`.
- Plan history (closed plans) stays in `tasks/` for reference; do not
  delete after completion.

### When something goes wrong mid-phase
Stop and re-plan. Update the per-phase plan with the deviation, do not
silently work around it. Capture the lesson in `tasks/lessons.md` per
the global self-learning rule.

### Primer.md update protocol
After every phase commit + tag:
1. Overwrite `~/.claude/primer.md` with current branch, commits ahead,
   last commit, last tag, resume instruction.
2. Keep under 100 lines.
3. Reference this route map by path so future sessions resume cleanly.

### Verification gate before each phase declares done
- [ ] All new tests green; coverage ≥ 80% for new modules.
- [ ] Full suite regression delta = 0 vs pre-phase baseline.
- [ ] 4-reviewer pass complete; CRITICAL/HIGH addressed.
- [ ] ADR status updated if applicable.
- [ ] CLAUDE.md + wiki updated.
- [ ] Tag created.
- [ ] Primer updated.
- [ ] This route map's phase section marked `done`.
