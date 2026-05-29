# Add `--json` to `workflow graph neighbors`

## Summary

`workflow graph stats` and `workflow graph orphans` both accept `--json` and
emit a machine-readable shape consumed by the Neovim plugin. The sibling
command `workflow graph neighbors NODE_ID` accepts `--depth`, `--topic`,
`--discipline-area`, and `--main-topic` filters, but has **no `--json`
flag** and only emits human-readable text.

This blocks `:WorkflowGraphNeighbors {note-id}` in the Neovim plugin —
a picker that needs to list adjacent notes and let the user jump to a
file path on `<CR>`.

## Motivation

- Reporting agent(s): `workflow-runner`, plugin coverage audit
- Total occurrences: 1 (2026-05-28); will recur on every plugin
  integration that wants to traverse the graph from a note buffer
- Severity: **major** (blocks `:WorkflowGraphNeighbors`)
- Blocks / slows down:
  - Plugin coverage request
    (`2026-05-28-nvim-plugin-taxonomy-coverage.md`) Tier 2
  - Any tooling that wants to render neighbor adjacency for a note
    without parsing the human table

## Proposed CLI

```bash
workflow graph neighbors NODE_ID --json [--depth N] [--topic ...] [--discipline-area ...] [--main-topic ...]
```

## Expected JSON shape

```json
{
  "source": {"id": "abc123def", "title": "Newton's second law", "path": "/vault/notes/permanent/abc123def-newton.md"},
  "neighbors": [
    {
      "id": "xyz789",
      "title": "Free body diagrams",
      "path": "/vault/notes/permanent/xyz789-fbd.md",
      "edge_class": "structural",
      "relation_type": "supports",
      "depth": 1
    }
  ]
}
```

Each neighbor row MUST include `id`, `path`, and `depth`. `title`,
`edge_class`, `relation_type` are best-effort (may be null).

## Acceptance test

- `workflow graph neighbors <valid-id> --json` exits 0 and emits an
  object with `source` and `neighbors` keys.
- `neighbors` is a list; each entry has `id`, `path` (str), `depth` (int).
- `workflow graph neighbors <unknown-id> --json` exits 1 with an error
  message on stderr.
- `--depth 2 --json` returns at least one row with `depth: 2` when the
  graph has 2-hop neighbors.
- Add tests to `tests/workflow/graph/test_neighbors_json.py` covering:
  success-path JSON shape, unknown id exit code, `--depth` honored,
  filter flags (`--topic`, `--discipline-area`, `--main-topic`) honored.

## Cross-references

- `2026-05-28-nvim-plugin-taxonomy-coverage.md` — Tier 2 request that
  this unblocks.
- `src/workflow/graph/cli.py` — existing `neighbors` command (currently
  text-only).
- `src/workflow/graph/analysis.py` — `neighbors()` returns the domain
  data; CLI just needs a `--json` branch parallel to `stats` / `orphans`.
