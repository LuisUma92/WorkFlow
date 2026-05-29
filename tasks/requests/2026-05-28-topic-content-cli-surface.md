# Add CLI surface for `workflow topic` and `workflow content`

## Summary

`Topic` and `Content` models exist in `src/workflow/db/models/knowledge.py`
(lines 100 and 151) with full FK constraints (`Topic.discipline_area_id`,
`Content.topic_id`), but neither model has any CLI subcommands. The only path
to populate or query them today is a Python REPL with direct `get_session()`
access. `Concept` — the child of `Content` — already has a complete CLI via
`workflow concept`, making the gap in the parent tiers all the more visible.

Without this surface, agents cannot autonomously populate the
`DisciplineArea → Topic → Content → Concept` hierarchy, forcing hand-rolled
Python glue on every course-setup session.

## Motivation

- Reporting agent(s): `workflow-runner`
- Total occurrences: 1 (2026-05-28); will recur every time a new
  DisciplineArea needs its Topic/Content rows seeded
- Severity: **blocker**
- Blocks / slows down: autonomous course-knowledge-graph population;
  any agent workflow that relies on `workflow concept add` (which requires
  a valid `Content` parent row) but has no way to create that parent row
  without dropping into Python

## Proposed CLI

```bash
workflow topic add  --discipline-area <code> --name <str> --serial <int> [--json]
workflow topic list [--discipline-area <code>] [--json]
workflow topic show <id|serial> [--json]

workflow content add  --topic-id <id> --name <str> [--json]
workflow content list [--topic-id <id>] [--json]
workflow content show <id> [--json]
```

Flag details:

- `--discipline-area <code>` : DisciplineArea code string (e.g. `0001MM`)
- `--serial <int>` : `Topic.serial_number` — ordering within the area
- `--topic-id <id>` : integer PK of the parent Topic row
- `--json` : emit JSON to stdout; default is human-readable table

## Example

```bash
$ workflow topic add --discipline-area 0001MM --name "Cinemática" --serial 3 --json
{"id": 7, "discipline_area_code": "0001MM", "name": "Cinemática", "serial_number": 3}

$ workflow content add --topic-id 7 --name "MRU" --json
{"id": 42, "topic_id": 7, "name": "MRU"}

$ workflow topic list --discipline-area 0001MM --json
[
  {"id": 5, "name": "Fundamentos", "serial_number": 1},
  {"id": 6, "name": "Vectores",    "serial_number": 2},
  {"id": 7, "name": "Cinemática",  "serial_number": 3}
]
```

## Expected output shape

```json
// topic add / show
{"id": 7, "discipline_area_code": "0001MM", "name": "Cinemática", "serial_number": 3}

// content add / show
{"id": 42, "topic_id": 7, "name": "MRU"}

// topic list / content list
[{ ... }, ...]
```

Exit codes: 0 on success, 1 on FK violation (unknown discipline-area code or
topic-id), 2 on duplicate name within same parent.

## Acceptance test

- `workflow topic add --discipline-area <valid> --name X --serial 1 --json`
  emits JSON with `id` key; exit 0.
- `workflow topic add --discipline-area <invalid> --name X --serial 1`
  exits 1 with message referencing the unknown code.
- `workflow content add --topic-id <valid> --name Y --json` emits JSON
  with `topic_id` matching the supplied value; exit 0.
- `workflow content add --topic-id 99999 --name Y` exits 1.
- `workflow topic list --json` returns a JSON array; each element has
  keys `id`, `name`, `serial_number`, `discipline_area_code`.
- `workflow content list --topic-id <id> --json` returns only rows
  whose `topic_id` matches.
- Add at least one test per subcommand to
  `tests/workflow/test_topic_cli.py` and `tests/workflow/test_content_cli.py`,
  covering: success path, FK-violation error, `--json` shape, and list
  filters.

## Raw entries harvested

- `raw/workflow-runner.md#2026-05-28` — missing `workflow topic` / `workflow content` CLI surface

## Cross-references

- `workflow concept` CLI is the downstream consumer; this closes the gap
  one tier above it.
- `src/workflow/db/models/knowledge.py` lines 100 (`Topic`) and 151
  (`Content`) — models already present, no schema change needed.
- Related request: `2026-05-27-topic-reroot-discipline-area.md` (schema
  normalization, already implemented — provides the FK this CLI will target).
