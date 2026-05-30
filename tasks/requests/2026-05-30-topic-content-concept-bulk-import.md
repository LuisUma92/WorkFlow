# Bulk import for `DisciplineArea → Topic → Content → Concept` from YAML

> **Status: RESOLVED — v1.17.0 (2026-05-30).** `workflow topic import <file.yaml>
> [--discipline-area CODE] [--dry-run] [--json]` ships. Engine reuses
> `add_topic`/`add_content`/`add_concept`; idempotent skip; exit codes 0/1/2/3 per
> **ADR-0018** (which also pins the JSON shape + partial-failure/transaction semantics).
> 43 tests (engine 23 incl. DB-abort path, formatters 12, CLI 8). External template
> `~/01-U/.claude/templates/topic-content-concept.yaml` corrected (Bloom labels →
> `_TAXONOMY_DOMAINS`). Follow-ups (module rename, shared lookups, global-skip doc) filed
> in `2026-05-29-v1.14.0-reviewer-esquema-followups.md` (items 8–10).

## Summary

The CLI has per-entity add commands (`workflow topic add`, `workflow content add`,
`workflow concept add`) but no way to seed the full knowledge hierarchy from a
single structured file. A course with 10 topics × 5 contents × 15 concepts requires
~200 sequential CLI calls. The only practical workaround today is an orchestrator
(Claude or custom script) that drives those calls in order.

## Motivation

- Reporting agent(s): `workflow-runner`
- Total occurrences: 1 (2026-05-30); will recur every time a new course is
  bootstrapped or an existing one is revised wholesale
- Severity: **MEDIUM** — not a blocker for reading/linking, but a major friction
  point for new course setup
- Blocks / slows down: autonomous knowledge-graph population; teaching-team
  onboarding workflows; any agent workflow that uses the YAML template at
  `.claude/templates/topic-content-concept.yaml`

## Proposed CLI

```bash
workflow topic import <file.yaml> [--discipline-area <code>] [--dry-run] [--json]
```

Flag details:

- `<file.yaml>` — path to YAML file following the nested schema below
- `--discipline-area <code>` — override the `discipline_area_code` key in the file
- `--dry-run` — print what would be inserted without writing; exits 0 if schema valid
- `--json` — emit a JSON summary of created/skipped rows; default is human-readable table

### YAML schema

```yaml
discipline_area_code: FS01 # code of pre-existing DisciplineArea

topics:
  - name: Cinemática
    serial: 1
    contents:
      - name: Posición y desplazamiento
        concepts:
          - code: FS01-KIN-001
            label: Vector posición
            domain: Información # Bloom level
            description: ""
            parent_code: null # optional: code of parent concept
```

Concept `domain` must be one of: `Información`, `Procedimiento Mental`, `Procedimiento Psicomotor`, `Metacognitivo`

`parent_code` may reference a concept defined earlier in the same file
(resolved in insertion order) or one already in the DB.

## Example

```bash
$ workflow topic import course_fs01.yaml --dry-run
[DRY-RUN] Would create 2 topics, 4 contents, 18 concepts (0 skipped)

$ workflow topic import course_fs01.yaml --json
{"created": {"topics": 2, "contents": 4, "concepts": 18}, "skipped": 0, "errors": []}
```

## Expected output shape (`--json`)

```json
{
  "created": { "topics": 2, "contents": 4, "concepts": 18 },
  "skipped": 0,
  "errors": []
}
```

On partial failure, `errors` is a list of `{entity, row, reason}` objects;
already-created rows are NOT rolled back (idempotent: skip duplicate
`code`/`name` within the same parent).

Exit codes: 0 on full success, 1 on schema validation error (before any write),
2 on FK violation (unknown `discipline_area_code`), 3 on partial failure
(some rows written, some failed — see `errors` array).

## Acceptance tests

- `workflow topic import valid.yaml --dry-run` exits 0, prints summary, writes nothing.
- `workflow topic import valid.yaml --json` inserts rows, emits JSON with correct counts.
- Re-running the same file skips duplicates and exits 0 (idempotent).
- `workflow topic import bad_area.yaml` exits 2 with message naming the unknown code.
- `workflow topic import malformed.yaml` exits 1 with YAML parse error before any write.
- Add tests to `tests/workflow/test_topic_import.py` covering: success path,
  dry-run, idempotency, FK violation, malformed YAML, `--json` shape.

## Upstream template

A reference YAML template lives at:
`~/01-U/.claude/templates/topic-content-concept.yaml`

This template should be kept in sync with the accepted schema.

## Raw entries harvested

- `raw/workflow-runner.md#2026-05-30` — no `--from-file` / bulk-import on
  topic/content/concept commands

## Cross-references

- `2026-05-28-topic-content-cli-surface.md` — per-entity add/list (prerequisite,
  already implemented)
- `2026-05-27-topic-reroot-discipline-area.md` — schema normalization that
  provides the FK this command targets
- `workflow concept add` is the downstream leaf consumer; this command
  supersedes manual orchestration of the add sequence
