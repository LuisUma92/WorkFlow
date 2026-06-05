# Add filter flags to `workflow graph export-tikz` (`--main-topic`, `--depth`, `--cluster`, layout/color)

**Suggested labels:** `enhancement`, `cli`, `graph`, `tikz`,
`priority:recurring-friction`

## Context

`workflow graph export-tikz` accepts only `--project`, `--output`, and
`--standalone/--no-standalone`. There is no way to scope the rendered graph to
a single `main_topic`, a `discipline_area`, a precomputed cluster, or to limit
depth. Producing one TikZ doc per topic — a routine Zettelkasten use case —
currently requires post-processing the emitted `.tex` file or rebuilding the
graph in user code.

A separate command `workflow graph clusters` already computes cluster
membership, but it does not connect to `export-tikz`, so the cluster output
cannot be consumed as a filter.

This gap depends on `~/Documents/01-U/.claude/gaps/requests/2026-05-03-note-frontmatter-main-topic.md`
(without a `main_topic` field on notes, `--main-topic` cannot resolve nodes).
File this issue but mark `note-frontmatter-main-topic` as a blocker dependency.

## Proposed CLI / schema

```bash
workflow graph export-tikz \
  [--project <DDTTAA-YYPP>] \
  [--main-topic <slug>] \
  [--discipline-area <DDTTAA>] \
  [--cluster <name>] \
  [--depth <N>] \
  [--include-tags tag1,tag2] [--exclude-tags tag3] \
  [--layout <force|radial|hierarchical>] \
  [--color-by <main_topic|tag|type>] \
  -o <out.tex> [--standalone/--no-standalone]
```

Semantics:

- `--main-topic <slug>` selects the induced subgraph of nodes whose
  `main_topic == slug`, expanded by `--depth <N>` neighbours (default 0).
- `--cluster <name>` reuses output of `workflow graph clusters` to pick a
  precomputed community.
- `--main-topic` and `--cluster` are mutually exclusive.
- `--layout` and `--color-by` are pass-throughs to the TikZ renderer.

## Acceptance criteria

- [ ] `workflow graph export-tikz --main-topic <slug>` emits a `.tex` whose
  nodes are exactly the notes with that `main_topic` (plus `--depth` ring).
- [ ] `--cluster <name>` produces the subgraph from `graph clusters` output
  with the same name.
- [ ] `--main-topic` + `--cluster` together → exit 2 with usage error.
- [ ] `--color-by main_topic` colours each node by its `main_topic` slug
  hashed to a stable palette.
- [ ] Tests under `tests/workflow/test_graph_export.py` cover: empty
  `--main-topic`, `--depth 0` vs `--depth 2` node-set diff, `--cluster`
  vs. raw clusters output equality, mutex flag rejection.

## Evidence

- `workflow graph export-tikz --help` → 3 flags only (raw evidence in source
  gap entry).
- `workflow graph clusters` exists upstream but is not wired into
  `export-tikz`.
- Companion issue: `2026-05-03-note-frontmatter-main-topic.md` is a hard
  dependency — without a `main_topic` field on `NoteFrontmatter`, the
  `--main-topic` filter has nothing to match against.

## Source gap entries

- `~/Documents/01-U/.claude/gaps/raw/workflow-runner.md#2026-05-03-21:12`
  (`graph export-tikz` sin filtros)
