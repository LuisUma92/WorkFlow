---
status: completed
---

# Implementation Plan: Phase B — `main_topic` frontmatter FK

## RESOLVED (2026-05-04, user)

- **Q1:** Use `MainTopic.code` (6-char DDTTAA) as the slug surface. No new `slug` column. Frontmatter `main_topic: "FI0006"` resolves via `code` lookup.
- **Q2:** Defer `check_concepts_against_main_topic` to Phase B.5. New ADR: **ITEP-0012 — Concept ORM model** (proposal in §9 below).
- **Q3:** Phase B is **BLOCKED on ITEP-0011** (Vault unification). User mandates: all zettelkasten notes live under `~/Documents/01-U/0000AA-Vault/` as `.md`; `Note` table moves from LocalBase → GlobalBase. LocalBase keeps PRISMA decisions + contextual project notes only. Real SQL `FOREIGN KEY` then becomes enforceable. See §10.
- **Q4:** Inconsistency between `main_topic` and `discipline_area` = **error** (not warning), with interactive recovery menu offering 5 user-intent-preserving options. CI/non-interactive → exit non-zero with options as stderr text. See §11.

## Sequencing

```
ITEP-0011 (vault unification)  ──►  Phase B (this plan, real FK)  ──►  ITEP-0012 (Concept model)  ──►  Phase B.5 (concept validator)
```

Phase B does not start until ITEP-0011 ships. Drop logical-FK fallback; migration uses real `REFERENCES main_topic(id)`.

## CRITICAL FLAGS

- Phase A `test_list_json_shape_matches_sibling`: when Phase A lands, must use minimum-key-set assertion so Phase B growth is additive.
- Vault path constant: hard-code `~/Documents/01-U/0000AA-Vault/` is user-specific. Make it XDG-configurable: `~/.config/workflow/config.yaml: vault_root: <path>` with default fallback. Validate path on startup.

## 1. File-by-file change list

| File | Action | LOC |
|---|---|---|
| `src/workflow/validation/schemas.py` | edit: add `main_topic`, `discipline_area` fields; parse them; add 2 validators | +90 |
| `src/workflow/validation/__init__.py` | edit: re-export new validators | +4 |
| `src/workflow/db/migrations/local/0002_note_main_topic_id.py` | new: forward-only ADD COLUMN | +35 |
| `src/workflow/cli/validate.py` | edit: `--strict-main-topic` flag, wire validators | +25 |
| `src/workflow/notes/cli.py` (Phase A) | edit: extend `notes link` with `--main-topic <slug>`; mutex; rewrite-only-that-key | +40 |
| `src/workflow/notes/frontmatter_writer.py` | new: minimal-diff YAML rewrite for single key | +30 |
| `tests/workflow/test_validation_main_topic.py` | new | +180 |
| `docs/ADR/ITEP-0009-knowledge-lifecycle.md` | edit: append Part II section | +25 |
| `CLAUDE.md` | edit: bump CLI surface bullet | +2 |

Total ~430 LOC; ~180 tests.

## 2. Migration file

**Path:** `src/workflow/db/migrations/local/0002_note_main_topic_id.py`

```python
revision = "0002_note_main_topic_id"
description = "Add nullable note.main_topic_id (logical FK to global main_topic.id)"
def upgrade(connection): ...
```

Up SQL:
```sql
ALTER TABLE note ADD COLUMN main_topic_id INTEGER;
CREATE INDEX IF NOT EXISTS ix_note_main_topic_id ON note(main_topic_id);
```

**Updated post-ITEP-0011:** `note` lives in GlobalBase. Migration moves to `src/workflow/db/migrations/global/0002_note_main_topic_id.py`. Up SQL becomes:

```sql
ALTER TABLE note ADD COLUMN main_topic_id INTEGER REFERENCES main_topic(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_note_main_topic_id ON note(main_topic_id);
```

Real FK now enforceable. `ON DELETE SET NULL` so MainTopic deletion does not cascade-destroy notes. No backfill (nullable). `@with_schema_guard` already on every DB Click command.

## 3. Test list (`tests/workflow/test_validation_main_topic.py`)

| Test | Asserts |
|---|---|
| `test_frontmatter_without_main_topic_validates_clean` | Legacy note → no errors, no warnings |
| `test_frontmatter_with_main_topic_slug_parses` | `main_topic: "PHYS-MECH"` → `fm.main_topic == "PHYS-MECH"` |
| `test_frontmatter_with_main_topic_int_id_parses` | `main_topic: 42` parses |
| `test_main_topic_must_be_string_or_int` | `[1,2]` → error |
| `test_check_main_topic_known_slug_returns_no_warnings` | seed MainTopic(code="X"); fm `main_topic: "X"` → `[]` |
| `test_check_main_topic_unknown_slug_warns` | unknown code → 1 warning |
| `test_check_main_topic_unknown_under_strict_errors` | strict=True → error list |
| `test_check_main_topic_int_id_resolves_first` | "5" present → resolves; absent → warns |
| `test_discipline_area_consistency_when_both_set` | MainTopic.discipline_area_id mismatch → warning |
| `test_discipline_area_consistent_passes` | matching pair → `[]` |
| `test_migration_adds_column_idempotent` | second run = no-op via schema_version |
| `test_validate_notes_cli_strict_flag_propagates` | `--strict-main-topic` on bad note → exit 1 |
| `test_notes_link_main_topic_rewrites_only_that_key` | golden-file diff touches only `main_topic:` line |
| `test_notes_link_main_topic_validates_before_write` | unknown slug + strict → no write, exit !=0 |
| `test_notes_link_main_topic_mutex_with_other_link_targets` | `--main-topic` + `--reference` → exit 2 |

15 tests. `check_concepts_against_main_topic` deferred to Phase B.5.

## 4. Click signature deltas

`workflow validate notes`:
```python
+ @click.option("--strict-main-topic", is_flag=True, default=False,
+               help="Treat unknown main_topic slug/id as error.")
```

`workflow notes link <id>` (Phase A surface, extended):
```python
+ @click.option("--main-topic", "main_topic_slug", default=None, type=str,
+               help="Set/replace note's main_topic frontmatter key.")
```
Mutex: `--main-topic` + any other link target → `click.UsageError` exit 2. Rewrite path: regex single-line replace on `^main_topic:` (avoid ruamel.yaml dep); refuse if folded/multi-line.

## 5. Edge cases

| Case | Handling |
|---|---|
| Slug collision | DB `unique=True` prevents; defensive `first()` |
| Deleted/renamed main_topic post-authoring | Warn / strict-error; no cascading rewrite |
| Logical FK violation (id points nowhere) | Validator catches; no SQL CASCADE possible |
| Both keys set inconsistently | Warn; strict-error if `MainTopic.discipline_area_id != DisciplineArea[da].id` |
| Only `discipline_area` set | Allowed; verifies `DisciplineArea.code` exists |
| `main_topic` int-shaped string ("42") | int cast first → id lookup; fallback → code slug. Codes are `DDTTAA` (6 chars), no numeric collision today. Doc limit. |
| Concept-mismatch validator | Stub returning `[]`; Phase B.5 follow-up |

## 6. Verification commands

```bash
pytest tests/workflow/test_validation_main_topic.py -v

flake8 src/workflow/validation/schemas.py \
       src/workflow/db/migrations/local/0002_note_main_topic_id.py \
       --max-line-length=127 --max-complexity=10

pytest  # full regression

workflow db migrate --base local
workflow db migrate --base local   # idempotent

workflow validate notes path/legacy.md                # pass
workflow validate notes path/unknown-mt.md            # warn
workflow validate notes path/unknown-mt.md --strict-main-topic  # exit 1
workflow notes link <id> --main-topic PHYS-MECH       # writes, re-validates
```

## 7. Risks + open questions

**Risks**

- **R1 (HIGH):** Cross-DB FK is fictional. Concurrent global-DB renames leave dangling `main_topic_id`. Mitigation: validator-time check + future `workflow notes audit`.
- **R2 (MED):** Single-key YAML regex rewrite may corrupt edge cases (multi-line strings, anchors). Mitigation: refuse if `^main_topic:` line is folded/multi-line.
- **R3 (LOW):** Slug-or-id ambiguity if future codes are numeric. Doc-only.
- **R4 (LOW):** Phase A `link` may not exist when B lands solo. Mitigation: gate `--main-topic` behind Phase-A guard, or ship as tiny standalone subcommand.

**Open questions**

- Q1: Confirm `code` is the canonical slug surface (vs adding `slug` column)?
- Q2: Defer `check_concepts_against_main_topic` to Phase B.5?
- Q3: Drop `REFERENCES main_topic(id)` from migration (cross-DB)?
- Q4: `discipline_area` redundancy → hard error or warning?

## 8. ADR ITEP-0009 Part II — text stub

```
## Part II — Note frontmatter `main_topic` linkage (Phase B)

Notes MAY declare `main_topic: <code|id>` and `discipline_area: <DDTTAA>`
in YAML frontmatter. The DB carries a nullable `note.main_topic_id`
column (logical FK; cross-database, so no SQL `REFERENCES`). Validation
resolves integer-id-first, falling back to `MainTopic.code` lookup.
Unknown values warn by default, error under `--strict-main-topic`. When
both `main_topic` and `discipline_area` are set, validator enforces
consistency against `MainTopic.discipline_area_id`. Concept-level
enforcement is deferred to Phase B.5 pending a `Concept` ORM model.
Backwards compatibility: legacy notes without these keys validate clean.
```

## 9. ITEP-0012 — Concept ORM model (proposal, ships before Phase B.5)

**Location:** GlobalBase (alongside MainTopic).

```python
class Concept(GlobalBase):
    __tablename__ = "concept"
    id:              Mapped[int]          = mapped_column(primary_key=True)
    main_topic_id:   Mapped[int]          = mapped_column(
                          ForeignKey("main_topic.id", ondelete="RESTRICT"), nullable=False)
    code:            Mapped[str]          = mapped_column(String(32), unique=True)
    label:           Mapped[str]          = mapped_column(String(255))
    description:     Mapped[str | None]   = mapped_column(Text)
    parent_id:       Mapped[int | None]   = mapped_column(
                          ForeignKey("concept.id", ondelete="SET NULL"))
    created_at:      Mapped[datetime]     = mapped_column(default=func.now())

    main_topic: Mapped["MainTopic"]       = relationship(back_populates="concepts")
    parent:     Mapped["Concept | None"]  = relationship(remote_side="Concept.id")

# Composite uniqueness:
__table_args__ = (UniqueConstraint("main_topic_id", "code"),)
```

**Resolution semantics for frontmatter `concepts: [c1, c2]`:**
- Resolve each string against `Concept.code`.
- If `fm.main_topic` set, enforce `Concept.main_topic_id == fm.main_topic.id`.
- Unknown code → warn / strict-error symmetric.
- Hierarchy via `parent_id` for taxonomic refinement (e.g. `forces` → `gravity`).

**CLI surface (Phase B.5):**
```bash
workflow concept list [--main-topic <code>] [--json]
workflow concept add  --code <slug> --main-topic <code> --label <txt> [--parent <code>]
workflow concept tree [--main-topic <code>]      # render hierarchy
```

**Open Q for ITEP-0012:** is `parent_id` strictly within same `main_topic_id`? Recommend yes (cross-topic concept reuse handled via Note's `concepts: [a, b]` where a, b come from different topics — explicit at note level).

## 10. ITEP-0011 — Vault unification (BLOCKER for Phase B, separate plan needed)

**Decision (user, 2026-05-04):**
- All zettelkasten notes MUST live under a single global vault: `~/Documents/01-U/0000AA-Vault/` (path configurable).
- `Note` table relocates LocalBase → GlobalBase. Schema otherwise unchanged.
- LocalBase becomes **project-contextual only**:
  - **PRISMA layer:** `prisma_decision` rows (article_id, phase ∈ {identification, screening, eligibility, included, excluded}, motive, reviewer_id, ts).
  - **Contextual-notes layer:** project-scoped ideas/hypotheses/connections that DO NOT belong in the vault. New table `project_note` with FK to global `note.id` for cross-references.

**Migration challenges:**
- Existing slipbox.db files have `note` rows. Need data-migration script: read each project's `slipbox.db.note`, copy into GlobalBase `note`, rewrite per-project FKs (Link, Citation tables) to point at GlobalBase ids. Conflict resolution: id collision → reassign + remap.
- Existing `.md` files scattered across project dirs need to be moved/symlinked into vault. Or: vault becomes a virtual aggregator (symlink farm). Recommend physical move with backup.
- Tests under `tests/workflow/test_*` and `tests/itep/test_*` assume LocalBase-resident `note`. Audit + rewrite needed.

**Phase plan for ITEP-0011 (separate file):**
```
P0: ADR draft + user review
P1: Add `note` to GlobalBase (parallel; do not drop from LocalBase yet)
P2: Data-migration command `workflow vault unify` (idempotent, dry-run, backup)
P3: Switch all repositories to GlobalBase `note`; deprecate LocalBase `note`
P4: Drop LocalBase `note` table (forward-only migration)
P5: New LocalBase tables: `prisma_decision`, `project_note`
P6: Update CLI: `workflow notes new` writes to `<vault>/notes/<type>/`; `workflow project-note new` writes to LocalBase + project subdir
P7: ADR flip → Implemented; CLAUDE.md update
```

**Suggested next session:** open separate plan file `tasks/itep-0011-vault-unification-plan.md` and brainstorm P0–P7 in depth. Phase B remains pending until at least ITEP-0011 P3 lands (so `note` is real in GlobalBase).

## 11. Q4 inconsistency UX (interactive recovery)

When `validate notes` or `notes link --main-topic` detects mismatch between `main_topic` and `discipline_area`:

```
ERROR: my-note.md frontmatter inconsistency
  main_topic:      "FI0006"  → discipline_area FI (Física)
  discipline_area: "MA"       → Matemática

This note declares both keys but they disagree. Choose how to resolve:

  [1] Drop discipline_area  (trust main_topic; FI inferred from FI0006)
  [2] Update discipline_area → "FI"  (match main_topic)
  [3] Update main_topic     → pick from MA topics: MA0250, MA1004, ...
  [4] Drop main_topic       (keep discipline_area only, weaker linkage)
  [5] Abort (no change)

Choose [1-5]:
```

**Implementation:**
- Add `workflow.notes.recovery.resolve_main_topic_conflict(fm, session)` returning a `ResolutionMenu` dataclass (5 options + metadata).
- Click commands prompt via `click.prompt` when `sys.stdin.isatty()`; else exit non-zero with the menu printed to stderr.
- `--auto-fix=<1|2|3|4|5>` flag for non-interactive use.
- `--auto-fix=1` is the safest default (drop redundant key, trust main_topic).
- Option 3 ("update main_topic") shows top-N candidates from same `discipline_area`; if user wants different selection, abort and run `workflow db disciplines list --area MA` first.

**Tests added:**
| Test | Asserts |
|---|---|
| `test_inconsistency_emits_5_option_menu` | `ResolutionMenu` returned with all 5 options |
| `test_inconsistency_auto_fix_1_drops_discipline_area` | After flag, frontmatter has `main_topic` only |
| `test_inconsistency_auto_fix_2_updates_discipline_area` | discipline_area rewritten to match main_topic |
| `test_inconsistency_non_interactive_no_flag_exits_nonzero` | CI-mode: stderr lists options, exit 2 |

## Status
`in-progress` (core shipped) — ITEP-0011 P3 unblocked Phase B 2026-05-06.

**Shipped 2026-05-06:**
- PB.1 `79455b7` — global migration `0006_note_main_topic_id` (slot
  bumped from plan's 0002 → 0006), `Note.main_topic_id` ORM column +
  relationship, frontmatter `main_topic` + `discipline_area` schema
  fields. 11 tests.
- PB.2 `c0b5e34` — `check_main_topic_against_db` (id-first, code
  fallback) + `check_discipline_area_consistency`. 11 tests.
- PB.3 `27c30be` — `validate notes --strict-main-topic` CLI flag.
  Warnings by default, errors when strict; DA inconsistency is always
  an error (Q4). Exit 1 on errors. 6 tests.

**Suite:** 895 pass (+28 from PB), 0 xfail, 1 pre-existing UCR-sty unrelated.

**Deferred until Phase A ships** (no surface today):
- `notes link --main-topic` + `frontmatter_writer.py` minimal-diff
  rewriter — `notes` group only has `init` today.
- Interactive recovery menu (Q4 UX, §11). The validator already emits
  the inconsistency error; the menu is presentation-layer work that
  belongs alongside `notes link`.

**Not blocking ITEP-0012 / Phase B.5** — Concept ORM + concept validator
work is independent and can proceed when the user wants.

## Next session

1. Draft `tasks/itep-0011-vault-unification-plan.md` (Phase B blocker).
2. Draft `docs/ADR/ITEP-0011-vault-unification.md` (Status: Proposed).
3. Once P0–P3 of ITEP-0011 ship, return here to start Phase B RED tests.
