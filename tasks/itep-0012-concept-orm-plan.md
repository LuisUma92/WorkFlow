# Implementation Plan: ITEP-0012 — Concept ORM Surface

**Status: DONE** — all 4 workstreams shipped (2026-05-22).
- ✅ ITEP-0012.1: `service.py` + ADR (TDD) — `22a1267`
- ✅ ITEP-0012.2: CLI `list|show|add|tree|rm|rename` + formatters — `addd929`
- ✅ ITEP-0012.3: `check_concepts_against_db` + `--strict-concepts` — `610c2af` / `f6e57b8`
- ✅ ITEP-0012.4: CLAUDE.md + INDEX.md + plan status lockdown

Cross-ref: `notes link --concept CODE` (Phase A deferred) **MUST** reuse `concept.service.resolve_concepts`.

---

## Overview
Expose the already-shipped `Concept` + `NoteConcept` ORM models (GlobalBase, see `src/workflow/db/models/notes.py:192-223` and migration `src/workflow/db/migrations/global/0005_add_note_tables.py:82-99`) through a new `workflow concept` Click group, a frontmatter `concepts:` resolver, and a `validate notes --strict-concepts` validator. No schema/migration work expected (audit in [UNCLEAR] Q5). Unblocks Phase B.5.

## Requirements
- New CLI group: `workflow concept list|show|add|tree|rm|rename`.
- Pure-service layer (`src/workflow/concept/service.py`) with `resolve_concepts(codes, session, *, strict)` reused by both CLI and validator.
- New validator `check_concepts_against_db(fm, session, *, strict)` in `src/workflow/validation/schemas.py` mirroring `check_main_topic_against_db` (PB.2 template).
- New CLI flag `validate notes --strict-concepts` (additive, orthogonal to `--strict-main-topic`).
- Tests TDD-first; ≥80% coverage on new modules; full suite stays green (currently 978).
- No clash with deferred Phase A `frontmatter_writer.py`; if/when `notes link --concept CODE` lands, it MUST reuse `resolve_concepts`.

## Architecture Changes — File-by-file LOC table

| Path | Action | LOC | Purpose |
|---|---|---|---|
| `src/workflow/concept/__init__.py` | NEW | +5 | Package marker; re-export `concept` Click group. |
| `src/workflow/concept/service.py` | NEW | ~180 | Pure functions: `resolve_concepts`, `list_concepts`, `get_concept`, `add_concept`, `remove_concept`, `rename_concept`, `build_concept_tree`. No Click. |
| `src/workflow/concept/formatters.py` | NEW | ~90 | `format_concept_json`, `format_concept_table`, `format_concepts_list_*`, `format_tree_ascii`, `format_tree_json`. Mirrors `src/workflow/evaluation/formatters.py`. |
| `src/workflow/concept/cli.py` | NEW | ~190 | Click group + 6 subcommands; delegates to service; uses `get_engine_from_ctx` (`src/workflow/db/engine.py`). |
| `src/workflow/cli/__init__.py` or `src/main.py` | EDIT | +2 | Register `concept` group on root `cli`. |
| `src/workflow/validation/schemas.py` | EDIT | +60 | Add `check_concepts_against_db(fm, session, *, strict)`; export. |
| `src/workflow/validation/__init__.py` | EDIT | +2 | Re-export new validator. |
| `src/workflow/cli/validate.py` (or wherever `validate notes` lives) | EDIT | +15 | Add `--strict-concepts` flag; wire validator. |
| `tests/workflow/test_concept_service.py` | NEW | ~180 | resolve_concepts strict/lenient, hierarchy walker, duplicates. |
| `tests/workflow/test_concept_cli.py` | NEW | ~220 | 6 commands × happy + error paths; JSON shape lock. |
| `tests/workflow/test_validation_concepts.py` | NEW | ~140 | Validator: unknown/known/main_topic-mismatch lenient + strict; CLI flag. |
| `docs/ADR/ITEP-0012-concept-orm.md` | NEW | +120 | Status: Accepted. CLI surface, resolution semantics, parent-id within-topic policy. |
| `CLAUDE.md` | EDIT | +3 | Bump CLI surface bullet (concept group). |

Total ~1.2k LOC, ~50 new tests. **No new migration unless [UNCLEAR] Q5 surfaces a missing index.**

## Click Signatures

```python
@cli.group()
def concept() -> None:
    """Manage Concept entries (GlobalBase)."""

@concept.command(name="list")
@click.option("--main-topic", "main_topic_code", default=None,
              help="Filter to concepts under MainTopic.code (DDTTAA).")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_list(ctx, main_topic_code, as_json): ...

@concept.command(name="show")
@click.argument("code")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_show(ctx, code, as_json): ...
# Output: concept dict + parent (code|null) + child_count.

@concept.command(name="add")
@click.option("--code", required=True)
@click.option("--label", required=True)
@click.option("--main-topic", "main_topic_code", required=True)  # see [UNCLEAR] Q3
@click.option("--parent", "parent_code", default=None)
@click.option("--description", default=None)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_add(ctx, code, label, main_topic_code, parent_code, description, as_json): ...

@concept.command(name="tree")
@click.option("--main-topic", "main_topic_code", default=None)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def cmd_tree(ctx, main_topic_code, as_json): ...

@concept.command(name="rm")
@click.argument("code")
@click.option("--force", is_flag=True,
              help="Cascade-delete NoteConcept rows; SET NULL child concept parent_id.")
@click.pass_context
def cmd_rm(ctx, code, force): ...

@concept.command(name="rename")
@click.argument("old_code")
@click.argument("new_code")
@click.pass_context
def cmd_rename(ctx, old_code, new_code): ...

# validate notes — additive flag
+ @click.option("--strict-concepts", is_flag=True, default=False,
+               help="Treat unknown frontmatter concept codes / main_topic mismatches as errors.")
```

## JSON Shapes (locked)

`concept list --json` (mirrors `course list --json` flat list):
```json
[
  {"code": "newton-2nd", "label": "Newton 2nd Law",
   "main_topic": "FI0006", "parent": "forces",
   "description": null, "id": 17}
]
```

`concept show --json`:
```json
{"code": "newton-2nd", "label": "...", "main_topic": "FI0006",
 "parent": "forces", "description": null, "id": 17,
 "child_count": 3, "created_at": "2026-05-06T12:00:00"}
```

`concept tree --json` (nested):
```json
[{"code": "forces", "label": "...", "children": [
   {"code": "newton-2nd", "label": "...", "children": []}
 ]}]
```

`concept add --json`: same dict shape as `show` (minus `child_count`).

Empty list/tree → `[]` exit 0.

## Implementation Steps

### ITEP-0012.1 — Service + ADR (TDD RED → GREEN)
1. Write `tests/workflow/test_concept_service.py` covering `resolve_concepts` (strict/lenient), `add_concept` duplicate-code rejection, `add_concept` unknown-main_topic rejection, `add_concept` unknown-parent rejection, `build_concept_tree` cycle-safety + depth, `remove_concept` refusal when NoteConcept rows reference and `--force` allow.
2. Implement `src/workflow/concept/service.py` (pure, no Click). Use `Session` from caller; raise `ConceptError` subclasses (`DuplicateCode`, `UnknownCode`, `ParentNotFound`, `MainTopicNotFound`, `HasReferences`).
3. Draft `docs/ADR/ITEP-0012-concept-orm.md` (Status: Accepted). Document: `code` is canonical slug; parent_id within same `main_topic_id` (recommend yes per phaseB §9).

### ITEP-0012.2 — CLI surface
4. `src/workflow/concept/formatters.py` mirroring evaluation pair.
5. `src/workflow/concept/cli.py` — 6 subcommands; sessions via `get_engine_from_ctx` (`src/workflow/db/engine.py`).
6. Register group on root `cli`.
7. Write `tests/workflow/test_concept_cli.py` (CliRunner): list empty → `[]`; list filtered by `--main-topic`; show happy + unknown-code exit !=0; add happy + duplicate exit !=0 + unknown-mt exit !=0 + unknown-parent exit !=0; tree empty + populated ASCII + JSON nested; rm refuse-without-force vs force; rename atomic.
8. **JSON shape lock test**: `test_concept_list_json_shape_matches_sibling` asserts explicit key set so future additions are additive.

### ITEP-0012.3 — Validator + `--strict-concepts`
9. Write `tests/workflow/test_validation_concepts.py`:
   - empty `concepts` list → `[]`.
   - unknown code lenient → 1 warning; strict → 1 error.
   - mt-mismatch (concept.main_topic_id ≠ note.main_topic_id) lenient → warning; strict → error.
   - no `main_topic` on note → mt-mismatch check skipped silently.
   - CLI flag wiring: `validate notes --strict-concepts` exits 1 on bad note.
10. Add `check_concepts_against_db(fm, session, *, strict: bool) -> list[Issue]` in `src/workflow/validation/schemas.py`. Template: copy structure from `check_main_topic_against_db` (PB.2). Reuse `resolve_concepts`.
11. Wire `--strict-concepts` flag in `validate notes` CLI; orthogonal to `--strict-main-topic`.

### ITEP-0012.4 — Docs + lockdown
12. Update `CLAUDE.md` "CLI surface" bullet: add `workflow concept list|show|add|tree|rm|rename` and `validate notes --strict-concepts`.
13. Update `docs/ADR/INDEX.md` with ITEP-0012 row.
14. Append cross-ref note in `tasks/phaseA-notes-crud-plan.md` "Deferred follow-ups": `notes link --concept CODE` MUST reuse `concept.service.resolve_concepts`.

## TDD Test List

| Test | Asserts |
|---|---|
| `test_resolve_concepts_lenient_unknown_returns_warning` | Issue list len=1, severity=warning. |
| `test_resolve_concepts_strict_unknown_returns_error` | severity=error. |
| `test_resolve_concepts_known_returns_objects` | Returned list of `Concept` ORM objs in same order. |
| `test_resolve_concepts_empty_input_returns_empty` | `[]` no DB hits. |
| `test_add_concept_duplicate_code_raises` | `DuplicateCode`. |
| `test_add_concept_unknown_main_topic_raises` | `MainTopicNotFound`. |
| `test_add_concept_unknown_parent_raises` | `ParentNotFound`. |
| `test_add_concept_parent_in_different_main_topic_raises` | Policy: parent within same main_topic. |
| `test_build_concept_tree_filters_by_main_topic` | Only nodes under given MT. |
| `test_build_concept_tree_orphan_parent_outside_filter` | Orphan promoted to root. |
| `test_remove_concept_refuses_when_note_concept_rows` | `HasReferences` raised. |
| `test_remove_concept_force_cascades_note_concept` | NoteConcept rows gone. |
| `test_remove_concept_force_reparents_children_to_grandparent` | Child concepts' `parent_id` == removed.parent_id (may be None if removed was root). |
| `test_rename_concept_atomic` | Old code 404, new code resolves to same id. |
| `test_rename_concept_collides_with_existing_raises` | DuplicateCode. |
| `test_cli_list_empty_returns_empty_json` | exit 0, stdout `[]`. |
| `test_cli_list_filtered_by_main_topic` | Only matching concepts. |
| `test_cli_show_unknown_exits_nonzero` | exit !=0, error names code. |
| `test_cli_show_json_shape_locked` | Explicit key set. |
| `test_cli_add_happy_path` | Row inserted; JSON output matches `show`. |
| `test_cli_add_duplicate_exits_nonzero` | exit !=0. |
| `test_cli_add_unknown_main_topic_exits_nonzero` | exit !=0. |
| `test_cli_tree_ascii_renders_hierarchy` | Indented tree includes child codes. |
| `test_cli_tree_json_nested_shape` | Top-level list of dicts with `children`. |
| `test_cli_rm_refuses_without_force_when_referenced` | exit !=0. |
| `test_cli_rm_force_succeeds` | Concept gone. |
| `test_cli_rename_atomic` | Old absent, new present. |
| `test_validate_concepts_no_concepts_field_clean` | `[]`. |
| `test_validate_concepts_unknown_code_warns` | severity=warning. |
| `test_validate_concepts_unknown_code_strict_errors` | severity=error. |
| `test_validate_concepts_main_topic_mismatch_strict_errors` | error message names both topics. |
| `test_validate_notes_cli_strict_concepts_propagates` | exit 1 on bad note. |
| `test_strict_concepts_orthogonal_to_strict_main_topic` | Independent exit semantics, both flags set. |
| `test_concept_list_json_shape_matches_sibling` | Locked key set vs `course list --json`. |

≈33 new tests across 3 files.

## Edge Cases / Failure Modes

| Case | Handling |
|---|---|
| `concepts:` mixed list of code+label | Out of scope; resolver expects code only ([UNCLEAR] Q1). |
| Frontmatter lists child code without parent | Explicit-only ([UNCLEAR] Q2); parent NOT auto-attached. |
| Concept references MT under deletion | `ondelete="RESTRICT"` already prevents at DB level. |
| `parent_id` cycle | `build_concept_tree` keeps visited set; refuse cycle on `add` (parent walk hits self). |
| `rm --force` where children exist | Children's `parent_id` reparented to grandparent (= removed concept's own `parent_id`); becomes NULL only if removed was root. Service-side explicit update overrides schema `SET NULL`. |
| `rename` to existing code | Raise DuplicateCode (unique index). |
| Empty `concepts:` list in fm | Validator returns `[]` immediately (no DB hits). |
| Concept code with whitespace / non-slug | Reject in `add_concept`: `^[a-z0-9][a-z0-9-]{0,31}$`. |
| `--main-topic` filter on `list` resolves unknown code | exit !=0 with clear error. |
| `concept tree` over very deep hierarchy | Document soft cap; cycle-safe. |
| `validate notes --strict-concepts` with no DB session available | Reuse `get_engine_from_ctx` pattern; same fail mode as `--strict-main-topic`. |

## Verification Commands

```bash
pytest tests/workflow/test_concept_service.py -v
pytest tests/workflow/test_concept_cli.py -v
pytest tests/workflow/test_validation_concepts.py -v
pytest --cov=src/workflow/concept --cov-report=term-missing tests/workflow/test_concept_*.py

flake8 src/workflow/concept tests/workflow/test_concept_*.py \
       tests/workflow/test_validation_concepts.py \
       --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 src/workflow/concept tests/workflow/test_concept_*.py \
       --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

pytest  # full regression — must remain green (currently 978 pass)

# smoke
workflow concept --help
workflow concept list --json
workflow concept add --code newton-2nd --label "Newton 2nd Law" --main-topic FI0006
workflow concept tree --main-topic FI0006
workflow validate notes --strict-concepts <path>
```

## Risks & Mitigations

- **R1 (MED):** Cross-DB FK fiction (frontmatter `concepts:` → GlobalBase concept; notes file path unknown to DB). Validator-time resolution is the only enforcement. Mitigation: same as PB — strict flag + future `workflow notes audit`.
- **R2 (MED):** `parent_id` cycle if user `add`s with a parent whose chain loops. Mitigation: walk parent chain on add; refuse on self-encounter.
- **R3 (LOW):** Frontmatter `concepts:` shape drift — string vs dict. Mitigation: schema in `validation/schemas.py:49,69` already locks list-of-str. Document in ADR.
- **R4 (LOW):** Phase A's deferred `frontmatter_writer.py` may ship later with subtly different API; `notes link --concept` then has to reuse `resolve_concepts`. Mitigation: shape `frontmatter_writer.set(key, value)` generic; document forward dependency.
- **R5 (LOW):** Performance — `concept tree` materializes all rows. Mitigation: filter by `--main-topic` reduces working set; soft-cap depth in render.

## Resolved Decisions (2026-05-06)

- **Q1 — fm `concepts:` shape:** `Concept.code` slugs only. Resolver looks up `Concept.code`; label/mixed forms rejected.
- **Q2 — parent auto-attach:** No. Explicit-only. User lists every concept they want attached; resolver does NOT walk parent chain.
- **Q3 — `concept add --main-topic` required:** Yes (schema NOT NULL). No orphan-concept support.
- **Q4 — `rm --force` with child concepts:** **Reparent to grandparent** (deviates from default). Implementation: in `remove_concept(code, force=True)`, before delete, set every child `Concept.parent_id` to the removed concept's own `parent_id` (which may be None — children become roots if parent was root). Override the schema's `ON DELETE SET NULL` semantics with explicit pre-delete update in service. Add test `test_remove_concept_force_reparents_children_to_grandparent`. Update Edge Cases table accordingly.
- **Q5 — migration slot 0007:** No. Tables empty today; SQLite handles small tables without extra indexes. Add `ix_concept_main_topic_id` / `ix_concept_parent_id` later if `tree` or `list --main-topic` slows. Plan stays migration-free.

## Pattern References (cite file:line)

- `src/workflow/evaluation/cli.py` — Click group + service delegation pattern.
- `src/workflow/evaluation/formatters.py` — JSON/table formatter pair.
- `src/workflow/validation/schemas.py:check_main_topic_against_db` (PB.2) — strict-vs-lenient validator template.
- `src/workflow/validation/schemas.py:check_discipline_area_consistency` (PB.2) — consistency-check template for mt-mismatch.
- `src/workflow/db/engine.py:get_engine_from_ctx` — Click session source.
- `src/workflow/db/models/notes.py:192-223` — Concept + NoteConcept ORM (already exists).
- `src/workflow/db/migrations/global/0005_add_note_tables.py:82-99` — DDL (already shipped).
- `src/workflow/validation/schemas.py:49,69` — `NoteFrontmatter.concepts` field.

## Cross-plan coordination

- **Phase A**: ITEP-0012 does NOT depend on Phase A's `frontmatter_writer.py`. If/when `notes link --concept CODE` lands later (Phase A follow-up), it reuses `concept.service.resolve_concepts`. Forward dependency only.
- **Phase B**: PB.1–PB.3 already shipped. `--strict-main-topic` + `--strict-concepts` are orthogonal additive flags — no clash.
- **Migration slots**: PB took `global/0006`. ITEP-0012 needs slot `global/0007` only if Q5 audit surfaces a missing index. P5 takes `local/0004`. No collisions.

## Status
`DONE` — all workstreams shipped (2026-05-22), review passes cleared, ready for merge.

### Commit log
- `22a1267` — ITEP-0012.1: service + TDD tests (15 tests, all green)
- `addd929` — ITEP-0012.2: CLI surface (list|show|add|tree|rm|rename, 6 subcommands, 18 tests)
- `610c2af` — ITEP-0012.3: validator + `--strict-concepts` (10 tests)
- `f6e57b8` — ITEP-0012.3 (follow-up): typo fixes in validator
- `${THIS_COMMIT}` — ITEP-0012.4: docs lockdown (CLAUDE.md, INDEX.md, plan status=done)
