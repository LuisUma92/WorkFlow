---
id: ITEP-0013
title: "Note relation graph — directed lineage + associative edges over the unified vault"
aliases:
  - ADR-ITEP-0013
status: Accepted
date: 2026-05-22
implemented_date: null
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - notes
  - zettelkasten
  - graph
  - traversal
  - migration
decision_scope: cross-module
supersedes: null
superseded_by: null
related_adrs:
  - 0001-zettelkasten-note-semantic-layer
  - 0002-markdown-canonical
  - 0010-exercise-persistence-model
  - LZK-0003-note-reference-system
  - ITEP-0009-knowledge-lifecycle
  - ITEP-0010-schema-versioning-and-migrations
  - ITEP-0011-vault-unification
---

## Context

The unified vault (ITEP-0011) stores notes as Markdown files with YAML frontmatter,
canonical on disk, indexed into `GlobalBase`. The only inter-note relation modelled
today is the **wiki-link**: the `Link` table records `note → label` edges
(LZK-0003), which resolve Markdown `[[...]]` references through the `Label` table.

This is an _associative_ layer only. It expresses "note A mentions a labelled
anchor in note B" but it does **not** model:

- **provenance** — which note(s) a note evolved out of;
- **continuation** — which notes carry a line of reasoning forward;
- **branching** — divergent argumentations growing from one note;
- **epistemic lineage** — the directed history of a thought.

Without these, the system cannot support resumable exploration, reasoning
continuation, or lineage tracking — the stated goals for evolving the vault into
an agentic knowledge graph robust under automated note generation.

A request (`.claude/requests/2026-05-21-resuming.md`) proposed adding:

```yaml
relations:
  parent: note-id # singular provenance
  next: [note-id, note-id] # plural continuations
```

plus a later `links:` family (`supports`, `contradicts`, `expands`).

This ADR critically evaluates that proposal and specifies the schema, traversal,
validation, and migration design. **A decision is required now** because two
in-flight workstreams (Phase A `notes` CRUD, ITEP-0012 Concept ORM) are actively
extending the note model; the edge model should be fixed before `notes link`
grows a relation surface.

> **Path note:** the live vault is `~/01-U/0000AA-Vault/` and the live index
> DB is `~/01-U/workflow/workflow.db` (confirmed on disk). These diverge from
> the XDG layout in ADR-0008 and the `~/Documents/01-U` default cited in
> ITEP-0011 — a pre-existing inconsistency to reconcile separately. It does not
> affect this ADR's edge model, which is path-agnostic.

---

## Decision Drivers

- **Append-only creation** — automated agents must create a note by writing
  _one_ file, never editing prior notes. This is the dominant driver.
- **Source-of-truth discipline** — Markdown stays canonical (0002, 0010);
  SQLite must remain a fully rebuildable derived index.
- **Expressiveness** — the model must represent merges (synthesis of multiple
  lines) and branches, not just a linear or strictly-tree history.
- **Robustness** — invalid/stale references must surface, never crash or
  silently vanish.
- **Long-term maintainability over short-term simplicity** (explicit constraint).
- **Scalability** — tens of thousands of notes, concurrent agent access,
  future embeddings/RAG.
- **Zettelkasten spirit** — a branching idea network, not a rigid task pipeline.

---

## Decision

### Summary of evaluation of the proposed model

| Proposed primitive       | Verdict                    | Reason                                                              |
| ------------------------ | -------------------------- | ------------------------------------------------------------------- |
| `parent` singular        | **Reject as canonical**    | Forbids _merge nodes_.                                              |
|                          |                            | A synthesis note legitimately derives from two or more lines;       |
|                          |                            | a reasoning DAG has convergence points.                             |
|                          |                            | Singular parent collapses the graph to a tree.                      |
| `next` plural            | **Keep the intent,**       | Branching continuation is correct.                                  |
|                          | **change the storage**     | But storing `next` in the _parent_ file means                       |
|                          |                            | every new continuation **mutates an old file**                      |
|                          |                            | — breaks append-only creation,                                      |
|                          |                            | creates write contention and merge conflicts.                       |
| directed reasoning graph | **Adopt**                  | Correct target model.                                               |
| strict DAG               | **Adopt for lineage only** | Lineage must be acyclic.                                            |
|                          |                            | Associative edges (`contradicts`) may cycle and that is meaningful. |

**Core decision:** there is exactly **one canonical, directed, typed edge**,
stored **once**, in the **frontmatter of the note that the edge originates from**
(the newer / dependent note). `parent` and `next` are not two stored fields —
they are the two _directions of one edge_. The forward (`next`) direction is
**never stored in Markdown**; it is a reverse index materialised only in SQLite.

This inverts the request's proposal (store backward, not forward) and makes the
parent side **plural** — which is strictly more expressive (merges allowed) at no
cost.

### Two edge families

| Family                     | Frontmatter key | `edge_class`  | DAG-constrained | Cycles    |
| -------------------------- | --------------- | ------------- | --------------- | --------- |
| **Lineage**                | `derived_from`  | `structural`  | yes             | forbidden |
| (the traversal spine)      |                 |               |                 |           |
| **Associative** (semantic) | `links`         | `associative` | no              | allowed   |

Both families share one uniform item shape and one SQLite table. The lineage
family _is_ the canonical traversal primitive; associative edges are
cross-cutting and do not participate in lineage traversal unless explicitly
requested.

### Identifier alignment with Phase 1

The `zettel_id` referenced throughout this ADR is the **`id:`** field of note
frontmatter — the canonical Zettelkasten identifier already established by note
templates (`workflow notes init`), the validation schema, and the notes service.
At the SQL level this maps to `Note.zettel_id`.

Phase 1 `notes sync` (v1.4.0) initially read a non-conventional `reference:`
field; the P1.5 hotfix (v1.4.1) aligns sync to read `id:` and populate both
`Note.zettel_id` and the legacy `Note.reference` column with the same value.
This ADR depends on that alignment — `note_edge.target_zettel_id` resolves
against `Note.zettel_id`.

No new identifier is introduced. `Note.zettel_id` becomes the single canonical
key for edge resolution; `Note.reference` is kept for backward compatibility
with the `latexzettel` shim (LZK-0004 will eventually remove it).

The `zettel_id` format is locked to **NanoID** per ITEP-0015: alphabet
`A-Za-z0-9_-`, length 8–21 (default 12), regex `^[A-Za-z0-9_-]{8,21}$`.
Legacy Obsidian-style identifiers (`YYYYMMDD-slug`) match this regex and
continue to validate — no migration burden. New notes via
`workflow notes new` generate a fresh NanoID via the `nanoid` library and
use the filename convention `<zettel_id>-<slug>.md` with auto-populated
`aliases:` for wiki-link robustness.

### Canonical YAML schema

```yaml
# In the frontmatter of note 202605221430 (a refinement of an earlier note)
relations:
  derived_from:
    - id: 202605211200 # zettel_id of the ancestor — REQUIRED, stable
      type: refines # continuation|refines|branches|synthesis|rebuttal
      weight: 0.9 # OPTIONAL — confidence, default unweighted
      note: "tightened the error bound" # OPTIONAL — rationale for the edge
    - id: 202604300900 # second ancestor → this note is a synthesis/merge
      type: synthesis
  links:
    - id: 202604010900
      type: supports # supports|contradicts|expands|see_also
    - id: 202604020900
      type: contradicts
entry_point:
  true # OPTIONAL — declares an intentional root,
  # suppresses the orphan warning
```

- `derived_from` and `links` are both **lists of `{id, type, weight?, note?}`**.
- Absent `relations:` ⇒ the note is a lineage root. Fully backward compatible.
- `id` is always a **`zettel_id`** (stable string), never a filename, never a
  DB integer.

### SQLite schema

`note_edge` is a new table. It does **not** replace `Link` (wiki-link
`note → label` edges stay as-is, LZK-0003). `note_edge` is `note → note`.

```sql
CREATE TABLE note_edge (
    id               INTEGER PRIMARY KEY,
    source_id        INTEGER NOT NULL REFERENCES note(id) ON DELETE CASCADE,
    target_id        INTEGER          REFERENCES note(id) ON DELETE SET NULL,
    target_zettel_id TEXT    NOT NULL,   -- frontmatter `id:` value; format: ^[A-Za-z0-9_-]{8,21}$ (NanoID, ITEP-0015)
    edge_class       TEXT    NOT NULL,   -- 'structural' | 'associative'
    relation_type    TEXT    NOT NULL,   -- continuation|refines|branches|synthesis
                                         -- |rebuttal|supports|contradicts|expands|see_also
    weight           REAL,               -- nullable
    rationale        TEXT,               -- nullable; the YAML `note`
    created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (edge_class IN ('structural','associative')),
    CHECK (source_id != target_id),
    UNIQUE (source_id, target_zettel_id, relation_type)
);

CREATE INDEX ix_note_edge_source     ON note_edge (source_id, edge_class, relation_type);
CREATE INDEX ix_note_edge_target     ON note_edge (target_id, edge_class, relation_type);
CREATE INDEX ix_note_edge_unresolved ON note_edge (target_zettel_id) WHERE target_id IS NULL;
```

**Edge direction invariant:** `source_id` is _always_ the note whose `.md`
frontmatter declared the edge. For a lineage edge, `source` derives from
`target`. This makes per-file reindex atomic: `DELETE FROM note_edge WHERE
source_id = :n` then re-insert from that one file — no cross-file coordination.

**`target_id` resolution:** the frontmatter only carries `target_zettel_id`.
The reindexer resolves it to `target_id`. An unresolved reference is stored as a
row with `target_id = NULL` — **never dropped**. `validate notes` reports it.

**Reverse index:** "what evolved from X" =
`SELECT source_id FROM note_edge WHERE target_id = X AND edge_class='structural'`.
The `next` direction is this query — no Markdown, no generated reverse files.

### Bidirectional materialization — decision

- Markdown stores the edge **once**, backward (`derived_from`, in the child).
- SQLite materialises **both directions implicitly** via the two indexes
  (`ix_note_edge_source`, `ix_note_edge_target`). No second row, no reverse file.
- This **eliminates the doubly-linked-list desync failure class entirely** —
  there is no second copy that can drift.

### `next` attributes — decision

| Asked                             | Decision                                                                                                                                  |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| ordering                          | **No canonical order.** Branches are parallel argumentations. Optional display `rank` MAY be added later; not stored now.                 |
| weights / priorities / confidence | **Optional `weight REAL`**, nullable, default unweighted. Enables confidence-weighted traversal; agents populate lazily.                  |
| timestamps                        | **`created_at` on the edge.** Cheap; enables "latest continuation".                                                                       |
| reasoning classification          | **Modelled as `relation_type`**, not a sub-field. The classification _is_ the edge type (`refines`, `branches`, `synthesis`, `rebuttal`). |

### Traversal strategies (pseudocode)

All traversals are **bounded**: `visited` set (cycle/DAG safety), `max_depth`,
and a `node_budget` (context-window awareness). Lineage traversal filters
`edge_class='structural'`.

```text
# Resumable exploration — bounded forward BFS over lineage
function resume_exploration(start_zid, max_depth, node_budget):
    frontier = queue([(start_zid, 0)])
    visited  = {start_zid}
    result   = []
    while frontier and len(result) < node_budget:
        (zid, depth) = frontier.pop_left()
        result.append(zid)
        if depth >= max_depth: continue
        for child in db.forward_lineage(zid):        # WHERE target = zid, structural
            if child not in visited:
                visited.add(child)
                frontier.push((child, depth + 1))
    return result            # breadth-first wavefront of continuations

# Epistemic lineage — DFS backward to roots
function trace_lineage(zid, visited=set()):
    if zid in visited: return []        # guards a malformed cycle defensively
    visited.add(zid)
    parents = db.backward_lineage(zid)  # WHERE source = zid, structural
    if not parents: return [[zid]]      # reached a root
    paths = []
    for p in parents:
        for path in trace_lineage(p, visited):
            paths.append(path + [zid])
    return paths                        # all ancestral paths (a DAG ⇒ may be many)

# Confidence-weighted best-first — heuristic / semantic-ranked traversal
function weighted_explore(start_zid, node_budget, score):
    # score(zid, edge) MAY combine edge.weight, recency, embedding similarity
    heap = max_heap([(score(start_zid, None), start_zid)])
    visited = set(); result = []
    while heap and len(result) < node_budget:
        (_, zid) = heap.pop_max()
        if zid in visited: continue
        visited.add(zid); result.append(zid)
        for (child, edge) in db.forward_lineage_edges(zid):
            if child not in visited:
                heap.push((score(child, edge), child))
    return result            # ranked continuation, context-window-aware
```

- **BFS** — default for "show me where this thought can resume."
- **DFS-to-root** — `trace_lineage` for provenance / lineage audit.
- **Best-first** — agent traversal; `score` plugs in `weight`, recency, or
  (future) embedding cosine similarity for semantic ranking.
- **Context-window-aware** — every traversal takes a `node_budget`; the caller
  sizes it to the model's remaining context.

### Filesystem vs database vs hybrid — decision

**Hybrid, with a sharpened contract.** Markdown is the source of truth for
edges _and_ content; SQLite is a **pure derived index — disposable and
rebuildable**. The new law extends 0002/0010 to edges:

> No lineage or associative edge exists _only_ in SQLite. Every edge is
> reconstructable by re-reading frontmatter. The sole DB-only artefacts are the
> computed reverse direction (an index, not a row) and `target_id=NULL`
> unresolved-edge bookkeeping.

`workflow notes sync --rebuild-edges` MUST be able to drop and rebuild `note_edge` entirely
from the `.md` corpus. The flag drops all `note_edge` rows in scope (or globally if no
`--project`) then runs the full edge re-import pass. Default sync (without the flag) does
incremental upsert + orphan cleanup.

---

## Architectural Rules

### MUST

- Edge references in frontmatter **MUST** use `zettel_id`, never filename or DB
  integer id.
- Every graph-participating note **MUST** have a non-null, unique `zettel_id`.
- A lineage edge **MUST** be stored exactly once, in the `derived_from` of the
  _originating_ (newer) note. The `next`/forward direction **MUST NOT** appear
  in any Markdown file.
- The lineage subgraph (`edge_class='structural'`) **MUST** remain acyclic.
  Validation **MUST** reject a frontmatter change that introduces a lineage
  cycle.
- An unresolved edge target **MUST** be persisted (`target_id=NULL`), never
  silently dropped.
- `note_edge` **MUST** be fully rebuildable from frontmatter by `sync --rebuild-edges`.
- Per-file sync **MUST** be atomic: delete-by-`source_id` then re-insert.
- Every closed-set value in the edge model (`edge_class`, `relation_type`)
  **MUST** be exposed via a stable CLI introspection endpoint
  (`workflow notes enums --json` or equivalent, per ITEP-0015) so editors and
  pre-commit hooks build pickers and validators from a single source of truth.
  Hard-coding the enum lists in the editor plugin or in validators is
  forbidden — the runtime CLI is authoritative.

### SHOULD

- New continuation notes **SHOULD** be created append-only — one new file, no
  edit of any ancestor.
- `validate notes --graph` **SHOULD** run in CI and report unresolved edges,
  orphans, self-edges, and duplicate edges as warnings.
- Intentional lineage roots **SHOULD** be marked `entry_point: true` to suppress
  the orphan warning.
- SQLite **SHOULD** run in WAL mode for concurrent agent access.

### MAY

- An edge **MAY** carry `weight` and a free-text `rationale`.
- Traversal callers **MAY** supply a `score` function for heuristic/semantic
  ranking.
- A future `note_embedding` table **MAY** be added for semantic similarity;
  the edge graph and embeddings compose (graph = lineage, embeddings =
  similarity) and are independent.
- A heuristic pass **MAY** _propose_ `derives` edges from existing wiki-links,
  but **MUST NOT** auto-create them — lineage stays human/agent-curated.

---

## Implementation Notes

- ORM model `NoteEdge` → `src/workflow/db/models/notes.py` (next to `Note`,
  `Link`, `Concept`).
- Migration → new `GlobalBase` slot, forward-only (ITEP-0010). Adds `note_edge`
  - indexes only. No change to `note`, `link`, `label`.
- Frontmatter schema → extend `NoteFrontmatter` in
  `src/workflow/validation/schemas.py`: optional `relations` block parsed into
  typed edge dataclasses; mirror the `concepts:` validation pattern.
- **Entry point** → extend `src/workflow/notes/sync.py::sync_vault()` with a
  4th pass that parses `relations:` from frontmatter and upserts `note_edge`
  rows. Per-file atomicity: `DELETE FROM note_edge WHERE source_id = :n` then
  re-insert (a different pattern than Phase 1's upsert for labels/links — edge
  authority is per-file scope, so full per-file replacement is correct).
- **Shared upsert** → add `upsert_note_edge(session, source_id, target_zettel_id,
edge_class, relation_type, weight, rationale) -> bool` to
  `src/workflow/notes/linker_ops.py` (extends the public upsert API established
  in Phase 1).
- **Reporting** → extend `SyncReport` with `edges_created: int = 0` and
  `edges_unresolved: int = 0` fields. CLI output adds two columns.
- **Resolution** → `target_zettel_id` resolved against `Note.zettel_id` lookup.
  Unresolved entries persisted with `target_id = NULL` per Failure Mode Analysis.
- Validators → add `check_graph_against_db` alongside
  `check_main_topic_against_db` / `check_concepts_against_db`. Cycle detection
  via recursive CTE:

  ```sql
  WITH RECURSIVE anc(n) AS (
      SELECT target_id FROM note_edge
        WHERE source_id = :start AND edge_class='structural'
      UNION
      SELECT e.target_id FROM note_edge e JOIN anc ON e.source_id = anc.n
        WHERE e.edge_class='structural'
  )
  SELECT 1 FROM anc WHERE n = :start;   -- non-empty ⇒ cycle
  ```

- CLI surface (later ADR/plan, out of scope here): `notes link --relation`,
  `graph trace`, `graph resume`, extend `graph orphans`.
- Reuse: `graph/` already has BFS/component analysis (`analysis.py`) and DOT
  export — lineage edges get a distinct edge style there.

---

## Impact on Human Authors (primary use case)

The note graph is designed for direct human authoring first. Agentic generation
is a secondary consumer that reuses the same primitives — agents earn no
special-cased CLI or schema surface.

### Authoring ergonomics required

To make `derived_from:` and `links:` blocks practical to write by hand, the
toolkit must surface every closed-set value and every existing identifier as a
discoverable, picker-friendly list. The targeted surface is the editor (Neovim
via `nvim-plugin/workflow`, Snacks pickers); but CLI users get the same data
through `--json` output.

| Field | Picker source |
|---|---|
| `derived_from[].id`, `links[].id` | existing notes in vault (zettel_id + title) |
| `derived_from[].type` (structural) | `continuation` \| `refines` \| `branches` \| `synthesis` \| `rebuttal` |
| `links[].type` (associative) | `supports` \| `contradicts` \| `expands` \| `see_also` |
| `edge_class` (implicit per block) | `structural` (derived_from) \| `associative` (links) |
| `references[]` (separate field, ADR-0001) | `bib_entry.bibkey` rows |
| `concepts[]` | `concept.code` rows (ITEP-0012) |

### Validation surface

Editor-side validation should flag, in-buffer:

- Unknown `id` references in `derived_from:` or `links:` — both target notes
  not in the vault and malformed identifier strings.
- Invalid `relation_type` values (typos against the closed set).
- Lineage cycles introduced by a newly added `derived_from:` entry
  (best-effort pre-check; authoritative check still runs in
  `validate notes --graph`).

These checks **MUST** be available outside the editor too — via
`workflow validate notes --graph` — so CI and pre-commit hooks share the
same validation.

### Why human-first

Direct authoring of the graph by humans is the foundational use case. Every
operation an automated agent performs is a subset of what a human can do
manually with the editor pickers. By optimizing for the human authoring
experience, the toolkit:

- Stays usable without any AI in the loop (offline, on-network failure, etc.)
- Makes the graph self-documenting (a human's hand-written lineage is the
  spec for any future automated generator)
- Avoids accumulating an "agent-only" surface that drifts from the human one
- Keeps the source of truth (Markdown files) editable in any text editor

The detailed design of editor tooling (CLI introspection contract, picker
keymaps, in-buffer validation, auto-fill) is the scope of **ITEP-0015**
(separate ADR). This ADR only establishes the principle and the primitives.

---

## Impact on AI Coding Agents

Agentic note generation is a secondary use case. Agents reuse the same
primitives as human authors — there is no agent-specific CLI, schema, or
edge type.

When an agent extends a line of reasoning:
- It **creates one new note** with `derived_from:` pointing at the
  ancestor(s); it does NOT edit the ancestor (append-only invariant from
  Decision Drivers).
- It **discovers valid `relation_type` values via the same CLI introspection
  endpoint humans use** (`workflow notes enums --json`); enum values are not
  hard-coded in agent prompts.
- It **resolves target identifiers via `workflow notes list --json`**, the
  same source the Neovim picker reads. Speculative or guessed identifiers
  are forbidden — the agent must verify the target exists before writing
  the frontmatter.
- It **MUST NOT** introduce a lineage cycle; pre-check the target is not a
  descendant before adding `derived_from:`. The authoritative cycle check
  runs in `validate notes --graph`.
- It **MUST NOT** write to `note_edge` directly; the table is derived.
  Mutate Markdown frontmatter, then `notes sync`.
- It **MUST** pass a `node_budget` matched to remaining context on every
  traversal.

Consult ITEP-0009 (knowledge lifecycle) and ITEP-0011 (vault) before bulk
note generation.

---

## Consequences

### Benefits

- Branching, merging reasoning graph — supports synthesis nodes a tree cannot.
- Append-only creation — no write contention, no merge conflicts on ancestors;
  ideal for automated generation and concurrent agents.
- The doubly-linked-list desync failure class is **structurally impossible** —
  the edge has no second stored copy.
- One uniform edge table for lineage _and_ semantic links — no parallel
  subsystems.
- SQLite stays a disposable cache — `sync --rebuild-edges` is the single recovery path.
- Bounded traversals are context-window-safe by construction.

### Costs

- A new table, migration, ORM model, frontmatter schema, validator, reindex
  path — upfront design and code effort.
- Forward (`next`) lineage is _only_ a DB query — a vault inspected with plain
  Markdown tooling shows provenance but not continuations. Acceptable: the DB
  is the traversal layer by design.
- Cycle validation adds a recursive CTE to the validate path.

---

## Alternatives Considered

### Alternative A — store `parent` (singular) + `next` (plural), as proposed

Each note stores a single `parent` and a list of `next`.

**Advantages:** forward traversal readable directly from Markdown; matches the
request's intuition.

**Disadvantages:** singular `parent` forbids merge/synthesis nodes; storing
`next` in the parent mutates old files on every continuation (breaks
append-only, causes contention); the edge is stored **twice** (parent's `next`
and child's `parent`) — a guaranteed desync source. **Rejected.**

### Alternative B — store the edge forward only (`next` in the parent)

Single copy, but in the parent.

**Advantages:** no duplication; forward traversal readable from Markdown.

**Disadvantages:** still mutates the ancestor on every new continuation —
violates the append-only driver. **Rejected.**

### Alternative C — separate tables for lineage vs semantic links

A `lineage_edge` table and a distinct `semantic_link` table.

**Advantages:** narrower per-table schema.

**Disadvantages:** two near-identical subsystems, two reindex paths, two
validators; `edge_class` discriminator on one table is simpler and keeps
traversal code uniform. **Rejected.**

### Alternative D — graph-only in SQLite, frontmatter carries no edges

Edges authored via CLI, stored only in the DB.

**Advantages:** no frontmatter parsing.

**Disadvantages:** violates Markdown-as-canonical (0002, 0010); the vault is no
longer self-describing; loses git-diffable provenance. **Rejected.**

---

## Failure Mode Analysis

| Failure                                | Handling                                                        |
| -------------------------------------- | --------------------------------------------------------------- |
| **Lineage cycle**                      | Validation error (recursive CTE). Frontmatter change rejected.  |
|                                        | The only edge problem treated as an error, not a warning.       |
| **Associative cycle**                  | Allowed and meaningful. Not flagged.                            |
| (`A contradicts B`, `B contradicts A`) |                                                                 |
| **Orphan note**                        | Warning, not error. A note with no structural                   |
|                                        | edges that is not `entry_point: true`.                          |
|                                        | Distinguishes intentional roots from dangling notes.            |
| **Invalid / stale reference**          | Edge persisted with `target_id=NULL`;                           |
|                                        | `validate notes --graph` reports it.                            |
|                                        | Never crashes, never dropped.                                   |
| **Ambiguous traversal**                | Bounded by `visited` + `max_depth` + `node_budget`;             |
|                                        | a DAG yields multiple ancestral paths —                         |
|                                        | `trace_lineage` returns all, caller chooses.                    |
| **Graph explosion**                    | `node_budget` caps every traversal;                             |
|                                        | best-first prioritises under the cap.                           |
| **Recursive traversal cost**           | Indexed recursive CTEs;                                         |
|                                        | `(source_id,…)` and `(target_id,…)`                             |
|                                        | indexes keep each hop O(log n).                                 |
| **Markdown ↔ SQLite desync**           | SQLite is derived;                                              |
|                                        | `sync --rebuild-edges` fully rebuilds.                          |
|                                        | No edge lives only in the DB.                                   |
|                                        | Incremental change detection                                    |
|                                        | (per-note frontmatter/body hashing)                             |
|                                        | is **out of scope for this ADR**                                |
|                                        | — see ITEP-0014 (proposed) for incremental sync.                |
| **Renamed file**                       | Edges key on `zettel_id`, not filename — rename is transparent. |
| **Rebuilt DB / integer-id churn**      | Edges key on `zettel_id`;                                       |
|                                        | integer `id`s are re-resolved on reindex.                       |
| **Concurrent agent writes**            | Per-file Markdown creation = low contention;                    |
|                                        | SQLite WAL; reindex is idempotent and per-file atomic.          |

---

## Scalability Notes

- SQLite handles 10k–100k notes and edges comfortably with the three indexes.
- Concurrent agents: WAL mode; Markdown creation is append-only per file.
- Automated generation: append-only model is the enabling property here.
- Visualization: `graph export-dot` / `export-tikz` extend to render lineage
  edges distinctly from associative/wiki edges.
- Semantic embeddings + RAG: a future `note_embedding` table is orthogonal —
  lineage graph answers "how did this thought evolve," embeddings answer "what
  is similar." Best-first traversal's `score` hook is the integration point.

---

## Compatibility / Migration

Backward compatible. Notes without a `relations:` block are valid lineage roots.
No existing data is rewritten; `Link` (wiki-links) is untouched.

```
Phase 0  Migration: add note_edge table + 3 indexes (GlobalBase, forward-only).
Phase 1  Frontmatter schema: optional `relations.derived_from` / `relations.links`.
Phase 2  Reindex: build note_edge from frontmatter; record unresolved as NULL.
Phase 3  Validator: `validate notes --graph` (cycles, orphans, unresolved).
Phase 4  CLI: `notes link --relation`, `graph trace|resume`, extend `orphans`.
```

No backfill of sequential data is required (none exists). Wiki-links are **not**
auto-promoted to lineage edges — lineage is curated. Each phase is independently
shippable behind the optional frontmatter field.

---

## References

- Niklas Luhmann — Zettelkasten method (branching note networks)
- ADR 0002 — Markdown as canonical knowledge layer
- ADR 0010 — File as truth, DB as index
- ADR LZK-0003 — Note reference system (wiki-links, IDs)
- ADR ITEP-0009 — Knowledge lifecycle and AI agent conventions
- ADR ITEP-0011 — Vault unification
- SQLite — recursive common table expressions; WAL mode

---

## Status

**Accepted** (2026-05-22). Implementation begins with P2.1 (NoteEdge model
+ migration). Human-first authoring tooling — CLI introspection, Neovim
pickers, in-buffer validation — is the scope of ITEP-0015, drafted in
parallel with this acceptance.

---

## Change Log

| Date       | Change                                                                                                                                                                                                                                                                          |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-05-22 | Initial ADR — directed note relation graph design                                                                                                                                                                                                                               |
| 2026-05-22 | Revision pre-approval: align identifier with `id:` frontmatter (Phase 1 P1.5 hotfix dependency); rename `notes reindex` → `notes sync --rebuild-edges`; concretize entry point in `sync.py`+`linker_ops.py`; scope `fm_hash` out (defer to ITEP-0014). Status remains Proposed. |
| 2026-05-22 | Human-first reframing: added "Impact on Human Authors" primary section; new architectural rule requiring CLI introspection of closed-set values; "Impact on AI Coding Agents" reframed as secondary consumer reusing human primitives; ITEP-0015 (editor tooling) drafted in parallel as scope-spinoff. Status: Proposed → **Accepted**. |
| 2026-05-22 | Locked `zettel_id` format (NanoID per ITEP-0015): regex `^[A-Za-z0-9_-]{8,21}$` enforced on `target_zettel_id` column. Filename convention and alias resolution covered by ITEP-0015 (data model unchanged by this lock; only the validation regex is added). |
