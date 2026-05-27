---
status: completed
---

# Wiki Update Brief — Ground Truth for Subagents (do not edit during update wave)

**Generated:** 2026-05-23, post-v1.5.0 tag (commit 1c17c99).
**Scope:** ITEP-0013 Phase 2 + ITEP-0015 NanoID lock. Subagents update only the file assigned to them.

---

## 1. New CLI surface — `workflow notes edges`

```
workflow notes edges list [--source ZETTEL_ID] [--edge-class structural|associative] [--relation-type TYPE] [--json]
workflow notes edges show EDGE_ID [--json]
workflow notes edges check [--json]                # exits 1 if cycles in structural subgraph
workflow notes edges resolve [--dry-run] [--json]  # target_zettel_id → target_id FK
```

- Listed as a subgroup of `workflow notes`.
- All four commands accept `--json`.
- `relation_type` choices: `continuation, refines, branches, synthesis, rebuttal, supports, contradicts, expands, see_also`.

## 2. NoteEdge data model (ADR ITEP-0013)

Table `note_edge` (GlobalBase, migration `0007_add_note_edges`):

| Column            | Type        | Notes |
|-------------------|-------------|-------|
| `id`              | INTEGER PK  | |
| `source_id`       | FK→note.id  | NOT NULL, ondelete CASCADE |
| `target_id`       | FK→note.id  | nullable; SET NULL on delete |
| `target_zettel_id`| String(21)  | NOT NULL, the stable string ref |
| `edge_class`      | String(16)  | CHECK in (`structural`, `associative`) |
| `relation_type`   | String(24)  | CHECK in 9 values (see above) |
| `weight`          | Float       | default 1.0 |
| `rationale`       | Text        | nullable |
| `created_at`      | DateTime    | server_default `CURRENT_TIMESTAMP` |

Constraints: `UNIQUE (source_id, target_zettel_id, relation_type)`; indexes on source, target, unresolved.

## 3. `relations:` frontmatter block (ITEP-0013 P2.2)

Notes may declare a `relations:` list in their YAML frontmatter:

```yaml
---
id: <zettel_id>
title: ...
relations:
  - target: <target_zettel_id>      # NanoID, ^[A-Za-z0-9_-]{8,21}$
    class: structural               # or associative
    type: refines                   # one of 9 relation_types
    weight: 1.0                     # optional, default 1.0; non-finite → 1.0
    rationale: optional one-line text
---
```

`workflow notes sync` parses each note (Pass 4) and calls `upsert_note_edge()` — idempotent.
Reports a new `edges_created` count alongside notes/labels/links/citations.

## 4. ITEP-0015 — locked identifier specs

- **zettel_id**: NanoID. Regex `^[A-Za-z0-9_-]{8,21}$`. Default length 12. Library: PyPI `nanoid`.
- **Filename**: `<zettel_id>-<slug>.md` (Obsidian-compatible).
- **aliases** auto-populated by `notes new`: `[<id>-<slug>, <slug>, <id>]`.
- **Wikilink resolution order**: `zettel_id` → `alias` → `reference` (legacy).
- **Multi-editor strategy**: extend LZK-0001 JSONL RPC server. LSP rejected.

## 5. Knowledge graph extension (ITEP-0013 P2.6)

`workflow.graph.collectors.collect_note_edges()` adds resolved NoteEdges to `build_knowledge_graph()`.

- New `GraphEdge.edge_type` values: `"note_edge:structural"`, `"note_edge:associative"`
- `GraphEdge.label` = the NoteEdge `relation_type` (e.g. `"refines"`)
- Only edges with `target_id IS NOT NULL` are included. Unresolved edges are excluded (use `notes edges resolve` first).
- No new node types — endpoints reuse existing `note:` GraphNodes from `collect_notes`.
- `graph stats`, `graph export-dot`, `graph export-tikz` all pick up the new edges automatically.

## 6. New source modules (Architecture page)

| Path | Purpose |
|---|---|
| `src/workflow/notes/edges.py`         | `RelationEntry` + `parse_relations_frontmatter()` |
| `src/workflow/notes/edges_service.py` | `list_edges()`, `get_edge()` query helpers |
| `src/workflow/notes/dag.py`           | iterative DFS cycle detection (`detect_structural_cycles`) |
| `src/workflow/notes/resolve.py`       | `ResolveReport`, `resolve_edge_targets()` |
| `src/workflow/notes/linker_ops.py`    | adds `upsert_note_edge()` |
| `src/workflow/db/models/notes.py`     | adds `NoteEdge` model |
| `src/workflow/db/migrations/global/0007_add_note_edges.py` | forward-only migration |

## 7. ADR table additions

| ADR | Title | Status |
|------|-------|--------|
| ITEP-0013 | Note relation graph | **Implemented** (2026-05-23) |
| ITEP-0014 | fm_hash incremental sync | Proposed (deferred) |
| ITEP-0015 | Editor-first authoring tooling | Proposed (LSP rejected; NanoID locked) |

## 8. Test counts (for any wiki claim about coverage)

- 1127 tests / 0 failed (as of `v1.5.0` / commit 1c17c99).
- Run with: `pytest --ignore=tests/test_database.py` (one pre-existing import error).

## 9. Subagent rules

- **Only edit your assigned file.** Do not touch other wiki pages.
- **Do not rewrite voice or restructure.** Add/correct content; preserve tone and headings.
- **No new files.** No emojis unless already used in the file.
- **Cite specifics:** use the exact CLI strings, column names, and ADR IDs in this brief.
- **If no drift:** leave the file unchanged and report `no-change-needed`.
- **Report under 200 words:** what changed, why, with file:line anchors.
