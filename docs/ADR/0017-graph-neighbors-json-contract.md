# 0017 — `graph neighbors --json` output contract

- **Status:** Accepted
- **Date:** 2026-05-30
- **Domain:** Graph / CLI
- **Depends on:** [0003](0003-hybrid-db.md) (hybrid DB), ITEP-0011 (vault layout)

## Context

`workflow graph neighbors NODE_ID --json` (v1.16.0) emits a machine-readable
adjacency object consumed by **three independent surfaces** that each encode the
shape with no shared source of truth:

1. the CLI emitter — `src/workflow/graph/cli.py::neighbors_cmd`,
2. the Python contract test — `tests/workflow/graph/test_neighbors_json.py`,
3. the Neovim picker + its plenary stub — `nvim-plugin/lua/workflow/picker/graph_neighbors.lua` and `…/tests/plenary/picker/graph_neighbors_spec.lua`.

Because the plenary spec **stubs** the JSON, a CLI field rename passes the Lua
tests while breaking the live picker (stub drift). Pinning the contract here is
the guard.

The originating request (`tasks/requests/2026-05-28-graph-neighbors-json.md`)
assumed a richer domain than exists: at the time of writing, `GraphNode` had
only `node_id/node_type/label` (no `path`), and `GraphEdge` has `edge_type/label`
— **not** the NoteEdge subsystem's `edge_class/relation_type`. The decisions
below reconcile that. (Note: as of Phase 5, 2026-07-04, `GraphNode` also
carries `tags: frozenset[str]` and `main_topic: str|None`; the `neighbors`
`title` contract below is unaffected.)

## Decision

### Envelope (pinned)

```json
{
  "source":   {"id": "<node_id>", "title": "<str>", "path": "<abs str|null>"},
  "neighbors": [
    {"id": "<node_id>", "title": "<str>", "path": "<abs str|null>",
     "edge_class": null, "edge_type": "<str|null>", "depth": <int>}
  ]
}
```

### Field rules

- **`id`** — the graph node_id verbatim, including the type prefix (`note:42`,
  `concept:3`). Never stripped.
- **`path`** — for **note** nodes only, the absolute file path derived as
  `resolve_vault_root() / "notes" / (note.note_type or "permanent") / note.filename`.
  All non-note node types (`concept`, `topic`, `exercise`, `bib`, `content`,
  `course`) → `null`. Enrichment happens **at the CLI layer** (re-query `Note`),
  not in the graph domain — `GraphNode` stays path-free so the exporters
  (`export-dot`, `export-tikz`, `clusters`) are not forced to carry a field they
  do not use.
- **`title`** — best-effort human label: note nodes use `note.title or
  note.filename`; other nodes use `GraphNode.label`.
- **`edge_class`** — always `null`. The knowledge graph has no edge-class concept.
- **`edge_type`** — the connecting edge's `GraphEdge.edge_type` (e.g. `link`,
  `citation`, `note_concept`), best-effort `null`. Renamed from `relation_type`
  (2026-06-03, see Amendment) precisely so it cannot be conflated with the NoteEdge
  semantic relation (`supports`/`contradicts`) emitted by `notes edges`. These are
  two distinct vocabularies.
- **`depth`** — BFS hop distance from the source (int ≥ 1). The `source` object
  carries no depth.

### Errors

Unknown `NODE_ID` → `click.ClickException` → exit 1, message on stderr (same for
text and `--json`).

## Consequences

- The contract is now versioned. Any field rename/removal is a breaking change to
  the picker and MUST update all three surfaces + this ADR.
- The `note:<int>` id convention is currently parsed in several spots in
  `graph/cli.py`. **Follow-up:** extract a `workflow.graph.node_ids` helper
  (`is_note`, `parse_note_id`) before a third consumer appears.
- ✅ `relation_type = edge_type` was a deliberate best-effort overload. **Resolved**
  (2026-06-03, Amendment): the key is renamed to `edge_type`, removing the
  NoteEdge-vocabulary trap.
- Path enrichment lives in the presentation layer; if a second consumer needs
  node paths, lift it into `graph/collectors.py` at that point (not before).

## Amendment (2026-06-03 — Wave 4 reviewer-followup #7)

**BREAKING:** the neighbor key `relation_type` is renamed to **`edge_type`** (its value
was always `GraphEdge.edge_type`). This removes the overload with the NoteEdge semantic
`relation_type` (`supports`/`contradicts`) emitted by `notes edges`. All three surfaces
were updated in one commit: the CLI emitter (`graph/cli.py`), the Python contract test
(`test_neighbors_json.py`), and the Neovim picker + plenary stub
(`graph_neighbors.lua` / `graph_neighbors_spec.lua`). `edge_class` remains always `null`.
