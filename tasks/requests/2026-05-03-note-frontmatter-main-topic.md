# Add `main_topic` field to note frontmatter (FK-validated against `main_topic` table)

**Suggested labels:** `enhancement`, `schema`, `notes`, `validation`,
`priority:blocker`, `adr-itep-0009`

## Context

The `NoteFrontmatter` dataclass at
`~/Projects/WorkFlow/src/workflow/validation/schemas.py:40-51` lets a note
declare `tags`, `concepts`, `references`, `exercises`, and `candidate_project`
(forward-ref to a `DisciplineArea`), but it has **no field that ties the note
to a specific `MainTopic`**. The relation today is implicit and unreliable:

1. `candidate_project: DDTTAA-YYPP` — points at a `DisciplineArea`, NOT a
   `MainTopic`. Validator `check_candidate_project_against_db` at
   `schemas.py:222-245` only verifies the discipline area exists.
2. `concepts: [str]` — free-form strings. They are not validated against the
   `Concept` table, and concepts are linked to `MainTopic` only via DB rows the
   user can't reach from frontmatter.
3. `tags: [str]` — free-form, no namespacing by topic.

This blocks any consumer that wants to slice the Zettelkasten by topic — most
immediately the user's request to export a TikZ graph filtered to a single
`main_topic` (see companion issue `2026-05-03-graph-export-tikz-filters.md`).
Without a foreign-keyed `main_topic` field, there is no way to compute the
induced subgraph cleanly.

## Proposed CLI / schema

Frontmatter extension:

```yaml
# ---  YAML frontmatter ---
id: my-note-id
title: ...
type: permanent
main_topic: <slug-or-id>      # NEW — FK to main_topic table
discipline_area: DDTTAA       # OPTIONAL, redundant with main_topic.discipline_area_id
concepts: [c1, c2]            # validated against Concept.main_topic_id == main_topic
candidate_project: DDTTAA-YYPP
```

Validation rules:

- `main_topic` absent → warning (MAY rule, current behaviour preserved).
- `main_topic` present but unknown in DB → error iff `--strict-main-topic`.
- `concepts[]` whose `main_topic_id` does not match the note's `main_topic` →
  warning under default mode, error under `--strict-main-topic`.

CLI surface:

```bash
workflow validate notes <path> [--strict-main-topic]
workflow notes link <id> --main-topic <slug>     # rewrites frontmatter in place
```

## Acceptance criteria

- [ ] `NoteFrontmatter` adds optional `main_topic: str | None` and
  optional `discipline_area: str | None`.
- [ ] New validator `check_main_topic_against_db` resolves slug-or-id against
  `main_topic` table; emits warning/error per `--strict-main-topic`.
- [ ] When `main_topic` is set, `check_concepts_against_main_topic` enforces
  `Concept.main_topic_id == main_topic`.
- [ ] `workflow notes link <id> --main-topic <slug>` rewrites only the
  frontmatter `main_topic` key, preserves all other fields and body.
- [ ] Tests under `tests/workflow/test_validation_main_topic.py` cover:
  unknown slug warn vs. strict-error, concept/topic mismatch warn vs. strict,
  round-trip via `notes link --main-topic`.
- [ ] Existing notes with no `main_topic` continue to validate (backwards
  compatible).

## Evidence

- `~/Projects/WorkFlow/src/workflow/validation/schemas.py:40-51` — current
  `NoteFrontmatter` fields.
- `~/Projects/WorkFlow/src/workflow/validation/schemas.py:222-245` —
  `check_candidate_project_against_db` only checks `DisciplineArea`.
- `~/Projects/WorkFlow/src/workflow/db/models/academic.py` —
  `MainTopic.discipline_area_id NOT NULL` (per `~/.claude/primer.md` key
  context section: "MainTopic.discipline_area_id NOT NULL at ORM level").
- ADR `ITEP-0009` (Part I — discipline catalog, Part II — main_topic linkage)
  per primer history.

## Source gap entries

- `~/Documents/01-U/.claude/gaps/raw/workflow-runner.md#2026-05-03-21:11`
  (frontmatter no tiene `main_topic` directo)
