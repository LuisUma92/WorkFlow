# Add nvim-plugin coverage for taxonomy + graph CLI surface

## Summary

The Neovim plugin (`nvim-plugin/`) currently exposes 19 `:Workflow*` user
commands, covering `notes`, `notes edges`, `evaluations`, `item`, `course`,
`prisma`, `validate`, `exercise sync`, and `project promote`.

It does **not** expose any commands for:

- `workflow topic`     — added 2026-05-28 (v1.11.0)
- `workflow content`   — added 2026-05-28 (v1.11.0)
- `workflow concept`   — shipped pre-1.11.0; never wired into plugin
- `workflow graph`     — analysis/export, no Lua surface
- `workflow lectures`  — scan/split/link/build-eval, no Lua surface
- `workflow project`   — `propose-maturation`, `report`, no Lua surface
- `workflow exam`      — `scaffold-xml`, no Lua surface

The taxonomy gap (`topic`/`content`/`concept`) is the most acute: when an
agent or human is editing a `.md` note buffer and wants to set
`main_topic:`, `topic:`, or `concepts:` in the frontmatter, the only path
is to drop to a shell, run `workflow topic list --json`, copy the value,
and paste it back. Every other foreign-key field on a Note already has a
picker (`WorkflowNotePicker`, `WorkflowEvalPicker`, `WorkflowCoursePicker`).

## Motivation

- Reporting agent(s): `workflow-runner`, `note-author`
- Total occurrences: 1 (2026-05-28 review); will recur on every
  authoring session that touches `main_topic` / `topic` / `concepts`
  frontmatter
- Severity: **major** (not blocker — CLI works from shell)
- Blocks / slows down:
  - In-editor frontmatter authoring for the new `topic` / `content` CLI
  - Knowledge-graph exploration (orphans, neighbors, stats) while editing
  - Lecture authoring (`lectures scan`, `lectures link`) from inside a
    `.tex` buffer

## Proposed Lua surface

### Tier 1 — Taxonomy pickers (highest value)

```vim
:WorkflowTopicPicker   [discipline-area=CODE]
:WorkflowContentPicker [topic-id=N]
:WorkflowConceptPicker [main-topic=CODE]
```

All three open a Snacks picker (matching existing
`WorkflowNotePicker` / `WorkflowEvalPicker` pattern):

- backed by `workflow {topic,content,concept} list --json`
- `<CR>` inserts the row's `id` (or `code` for concept) at cursor
- `<C-y>` yanks the id/code to the system clipboard
- `<C-p>` previews the full JSON row in a floating buffer

### Tier 2 — Graph commands

```vim
:WorkflowGraphStats      [--main-topic CODE] [--discipline-area CODE]
:WorkflowGraphOrphans    [--main-topic CODE]
:WorkflowGraphNeighbors  {note-id} [--depth N]
```

- `Stats` / `Orphans` open results in a scratch buffer
- `Neighbors` opens a picker of adjacent notes; `<CR>` jumps to file

### Tier 3 — Lecture commands

```vim
:WorkflowLectureScan
:WorkflowLectureLink
:WorkflowLectureBuildEval {template-id}
```

All three execute against the buffer's current project root
(detected via `config.yaml` walk) and surface stdout in a split.

## Out of scope for this request

The following CLI groups are intentionally **not** plugin-wrapped:

- `workflow db`       — schema/seed admin, run from shell
- `workflow tikz`     — filesystem pipeline, run from shell
- `workflow vault unify` — one-shot migration, run from shell
- `workflow exam scaffold-xml` — one-shot, niche

These have no editor-driven workflow.

## Acceptance test

- `:WorkflowTopicPicker` opens a picker populated from
  `workflow topic list --json`; selecting a row inserts the topic `id`
  at cursor in the current buffer.
- `:WorkflowContentPicker topic-id=7` filters to contents of topic 7.
- `:WorkflowConceptPicker main-topic=FI0001` filters concepts under
  that main topic.
- `:WorkflowGraphStats` runs `workflow graph stats --json` and renders
  it in a scratch buffer; non-zero exit shows the stderr line in the
  command area.
- `:WorkflowGraphNeighbors 42` opens a picker of notes adjacent to
  zettel id 42; `<CR>` opens that note's file at cursor.
- `:WorkflowLectureScan` invokes `workflow lectures scan` against the
  current project root and shows summary in a split.
- New entries appear in `doc/workflow.txt` with `*:WorkflowXxx*` tags
  so `:help WorkflowTopicPicker` resolves.
- Add at least one Lua-test (`tests/plugin/*_spec.lua` if present, else
  smoke-script under `nvim-plugin/scripts/`) per new command covering:
  JSON contract round-trip and stderr propagation.

## Raw entries harvested

- 2026-05-28 plugin-coverage audit — 10 CLI groups have zero plugin
  surface; 3 of those (`topic`, `content`, `concept`) are the natural
  partner pickers for `notes link` frontmatter authoring.

## Cross-references

- `2026-05-23-nvim-plugin-review-hardening.md` — closed; established
  `contracts.lua` and `doc/workflow.txt` infrastructure this request
  builds on.
- `2026-05-28-topic-content-cli-surface.md` — closed (v1.11.0);
  provides the JSON-shape contract for the new pickers.
- `nvim-plugin/lua/workflow/picker/notes.lua` — reference
  implementation for picker pattern.
- `nvim-plugin/lua/workflow/contracts.lua` — must be extended with the
  new JSON shapes (Topic, Content, Concept).
