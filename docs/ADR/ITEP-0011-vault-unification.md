---
adr: ITEP-0011
title: "Vault unification — single global Markdown corpus, Note table relocates to GlobalBase"
status: Accepted
date: 2026-05-04
accepted_date: 2026-05-06
authors:
  - Luis Umaña
reviewers:
  - Luis Umaña
tags:
  - database
  - notes
  - zettelkasten
  - vault
  - migration
decision_scope: cross-module
supersedes: null
superseded_by: null
related_adrs:
  - 0001-zettelkasten-note-semantic-layer
  - 0002-markdown-canonical
  - 0003-hybrid-database
  - 0007-shared-db-module
  - ITEP-0009-knowledge-lifecycle
  - ITEP-0010-schema-versioning-and-migrations
---

## Context

The current architecture splits `Note` rows into per-project LocalBase
(`<project>/slipbox.db`) while `MainTopic`, `DisciplineArea`, `Concept`
(forthcoming, ITEP-0012) live in GlobalBase
(`~/.local/share/workflow/workflow.db`). Consequences observed:

- **No real FK from `note` to `main_topic`.** Any cross-DB FK is a logical
  reference; SQLite cannot enforce it. Phase B of the
  `2026-05-04-zettelkasten-main-topic-bundle` request requires real FK
  enforcement, currently impossible.
- **Note discoverability is fragmented.** The same conceptual note may
  exist in multiple slipboxes; the user has no single Markdown corpus to
  query, version, or back up. Cross-project linkage requires manual
  symlink management.
- **Vault-wide search and graph traversal** (request
  `2026-05-03-graph-export-tikz-filters.md`, Phase C) needs a unified
  node set. Stitching N slipboxes plus N project subdirs is fragile.
- **PRISMA workflow already lives in LocalBase** as project-specific
  state. Co-locating PRISMA decisions with global zettelkasten notes
  conflates two lifecycle scopes (project-bounded review state vs.
  long-lived knowledge).

User mandate (2026-05-04): all zettelkasten notes MUST live as `.md`
under a single configurable vault root, default
`~/Documents/01-U/0000AA-Vault/`. LocalBase shrinks to two layers:

1. **PRISMA decisions** — inclusion/exclusion + motive + phase
   (identification → screening → eligibility → included/excluded), per
   project.
2. **Contextual project notes** — ideas, hypotheses, and project-scoped
   connections that explicitly do not belong in the global vault, with
   FK back to global `note.id` for cross-references.

## Decision

1. **Relocate `Note` (and dependent tables: `Label`, `Link`, `Citation`,
   `Tag`, `NoteTag`) from LocalBase to GlobalBase.** Schema otherwise
   unchanged at the column level; ORM imports and repository protocols
   move with it. Additionally, `Concept` and `NoteConcept` (ITEP-0012
   precondition) land on GlobalBase in the same P1 commit; tables are
   created empty pending ITEP-0012 implementation.

2. **Introduce vault root configuration.** Add `vault_root` key to
   `~/.config/workflow/config.yaml` (XDG layout per ADR-0008). Default:
   `~/Documents/01-U/0000AA-Vault/`. CLI surface:
   `workflow vault info`, `workflow vault validate`,
   `workflow vault unify` (one-shot data migration).

3. **`workflow notes new`** writes to `<vault_root>/notes/<type>/<id>.md`
   (ties to Phase A `notes` CRUD plan). LocalBase `note` table is dropped
   in P4.

4. **Introduce LocalBase-only tables** (P5):
   - `prisma_decision (id, article_id, phase, motive, reviewer_id,
     decided_at)` — supersedes the implicit decision rows currently in
     PRISMA web app.
   - `project_note (id, global_note_id, project_id, kind, body, created_at)`
     where `kind ∈ {idea, hypothesis, connection}` and `global_note_id`
     is a logical reference to the GlobalBase `note.id` (cross-DB; Phase
     B-style validator-time enforcement).

5. **Phase B FK becomes real.** After ITEP-0011 P3 lands, Phase B's
   `ALTER TABLE note ADD COLUMN main_topic_id INTEGER REFERENCES
   main_topic(id) ON DELETE SET NULL` is enforceable and filed under
   `migrations/global/`.

6. **Backwards compatibility.** Existing slipbox.db files are not deleted
   in-place; `vault unify` is idempotent, dry-run-by-default, with
   automatic backup. Two-pass: first copy notes + remap FKs, then verify
   counts and orphan detection before committing the LocalBase drop.

7. **Symlinks vs. physical move.** Notes under a project's `notes/`
   subdir are physically moved into `<vault_root>/notes/<type>/`. The
   project dir gets a one-line `.vault_pointer` marker for tooling
   discovery. Rationale: symlink farms break under cross-host sync
   (rclone, git-annex) and double the path-resolution surface.

## Consequences

### Positive

- Real SQL FK from `note.main_topic_id` to `main_topic.id` (closes Phase B
  blocker).
- Single Markdown corpus enables atomic backup, vault-wide grep, and
  cross-project graph traversal without DB stitching.
- LocalBase scope tightens to genuinely project-bounded state (PRISMA +
  contextual). Easier to reason about lifecycle and retention.
- Clean split for future ITEP-0012 (`Concept` in GlobalBase,
  Concept-Note linkage as real FK).
- Aligns with ADR-0002 (Markdown as canonical knowledge layer): a vault
  is the natural physical realisation.

### Negative

- One-time migration cost: 8 live slipboxes need note copy + FK remap +
  file move. Risk of orphaned references if any project tooling holds
  hard-coded paths.
- LocalBase `Citation` and `Link` tables move too, breaking any external
  consumer that opens a project slipbox directly. Inventory pass needed:
  `latexzettel`, `nvim-plugin`, `lectkit`.
- `nvim-plugin` and `latexzettel` RPC server must learn vault root
  resolution. The current `infra/orm.py` shim assumes LocalBase. Update
  needed.
- Two CLI commands (`workflow notes ...` and forthcoming `workflow
  project-note ...`) sit at adjacent surfaces; risk of UX confusion.
  Mitigation: clear `--help` text and `workflow notes --help` cross-link.
- `0000AA-Vault` does not yet exist on disk; user must `mkdir` it (or
  `workflow vault init`) before running `vault unify`.

### Neutral

- Schema-version bump (per ITEP-0010) for both bases: GlobalBase gains
  three tables, LocalBase loses one and gains two.
- ADR-0003 (Hybrid DB) is refined, not superseded: hybrid still applies,
  but the boundary moves. Update ADR-0003 status note to reference
  ITEP-0011 as a clarifying refinement.

## Migration plan (forward-only)

| Phase | Action | Status | Reversibility |
|---|---|---|---|
| P0 | Draft this ADR; user review; Status → Accepted | **Done** 2026-05-06 | n/a |
| P1 | Add `note`, `label`, `link`, `citation`, `tag`, `note_tag`, `concept`, `note_concept` to GlobalBase models (parallel; LocalBase note tables not yet dropped — old slipbox.db files keep them until P4) | **Done** commit `c02d788` | reversible |
| P2 | Implement `workflow vault unify` + author migration `migrations/global/0003_add_note_tables.py`. Dry-run + backup mandatory; idempotent. Tests cover: empty slipbox, slipbox with N notes, id collision, orphan detection | next | reversible |
| P3 | Switch `SqlNoteRepo` to GlobalBase session (locked, OQ5). CLI commands route writes to vault. Remove the 4 `xfail` marks on lecture CLI tests added in P1. Tests + integration green | pending | reversible (flag-gated) |
| P4 | Forward-only LocalBase migration: drop `note`, `label`, `link`, `citation`, `tag`, `note_tag` tables. Bumps LocalBase schema version | pending | irreversible (manual restore from backup only) |
| P5 | Add LocalBase tables `prisma_decision`, `project_note`. Migrate PRISMA web-app data into `prisma_decision` | pending | reversible |
| P6 | Update `latexzettel` RPC server, nvim-plugin, lectkit to use vault root + GlobalBase notes | pending | reversible |
| P7 | ADR flip → Implemented; CLAUDE.md update; close ITEP-0011 | pending | n/a |

P3 is the gate for Phase B of the bundle request to start.

## Resolved questions (locked 2026-05-06)

- **OQ1 → Accepted:** opt-in per project. CLI:
  `workflow vault unify --project <DDTTAA-YYPP>`.
- **OQ2 → Accepted:** `vault unify` reports id collisions and refuses
  to proceed without explicit `--rename-strategy {project-prefix,
  abort, manual}`. Default: `abort`.
- **OQ3 → Accepted (out of scope):** vault-as-git is the user's call;
  not enforced by ITEP-0011.
- **OQ4 → Accepted:** `project_note.kind` is a Python `Enum`
  (`idea | hypothesis | connection`), validated at the ORM layer.
- **OQ5 (new) → Accepted:** `SqlNoteRepo` locks to a GlobalBase session
  in P3. No dual-engine support; project-scoped note queries go through
  the future `ProjectNoteRepo` (P5).
- **OQ6 (new) → Deferred to P2:** the forward-only migration
  `migrations/global/0003_add_note_tables.py` (ITEP-0010) was not
  shipped in P1 — P1 relied on `GlobalBase.metadata.create_all`. P2
  authors the migration before the first `vault unify` run on a
  populated DB.

## Related

- Plan: `tasks/itep-0011-vault-unification-plan.md` (P0–P7 detailed).
- Bundle blocker for: `tasks/phaseB-main-topic-fk-plan.md`.
- Precondition for: ITEP-0012 (Concept ORM model, user-implemented).
