# Implement full CRUD on `workflow notes` (currently only `init` exists)

**Suggested labels:** `enhancement`, `cli`, `notes`, `zettelkasten`, `priority:recurring-friction`

## Context

`workflow notes --help` advertises a "Zettelkasten note management" group but
exposes a single subcommand, `init`, which only scaffolds an empty workspace.
Every operation a user actually performs on a note (create, list, show, tag,
link) is currently hand-rolled: write a `.md` file with YAML frontmatter,
then run `validate notes` after the fact. This forces every agent in
`~/Documents/01-U/.claude/agents/` (note-curator, exam-author, workflow-runner)
to manage frontmatter manually, and it makes the group a discoverability cliff
for new users — the label promises CRUD that does not exist.

The schema is already defined upstream in
`~/Projects/WorkFlow/src/workflow/validation/schemas.py:40-51`
(`NoteFrontmatter` accepts `id, title, tags, created, concepts, references,
exercises, images, type∈{permanent,literature,fleeting}, candidate_project=DDTTAA-YYPP`).
The CLI just doesn't wire it.

This issue covers the CRUD layer only. Two companion issues address the
schema gap (`main_topic` field) and the consumer gap (`graph export-tikz`
filters) that together unlock filtered Zettelkasten visualisation.

## Proposed CLI / schema

```bash
workflow notes new   --id <slug> --title <txt> --type <permanent|literature|fleeting> \
                     --tags tag1,tag2 --concepts c1,c2 \
                     --candidate-project DDTTAA-YYPP [--dir <path>] [--json]
workflow notes list  [--tag <x>] [--concept <y>] [--candidate-project DDTTAA-YYPP] \
                     [--type <kind>] [--json]
workflow notes show  <id> [--json]
workflow notes tag   <id> --add tag1 --remove tag2 [--json]
workflow notes link  <id> (--concept <name> | --reference <id> | --exercise <id>) [--json]
```

Behaviour:

- `notes new` writes a fresh `.md` with valid frontmatter; emits `{path, id}` on
  `--json`; refuses to overwrite (use `--force` if needed later).
- `notes list --json` returns
  `[{id, title, tags, concepts, candidate_project, type, path}, ...]`.
- All mutating commands re-validate against `NoteFrontmatter` schema before
  writing; exit non-zero on validation failure.

## Acceptance criteria

- [ ] `workflow notes --help` lists at minimum `init`, `new`, `list`, `show`,
  `tag`, `link`.
- [ ] `notes new` round-trips through `validate notes` without warnings.
- [ ] `notes list --json` matches sibling JSON shapes (e.g. `course list --json`).
- [ ] Empty result on `notes list` filters returns `[]` with exit 0.
- [ ] Tests under `tests/workflow/test_notes.py` cover: create + list + show
  round-trip, tag add/remove, link to concept/reference/exercise, schema
  rejection on invalid `candidate_project`.

## Evidence

- `~/Projects/WorkFlow/src/workflow/validation/schemas.py:40-51` — full
  `NoteFrontmatter` dataclass (already implemented).
- `workflow notes --help` — only `init` listed (raw evidence in source gap
  entry).
- `~/Documents/01-U/.claude/gaps/raw/workflow-runner.md` — entry
  `2026-04-19 14:48` flagged the same group as a "near-empty stub" earlier
  this cycle; entry `2026-05-03 21:10` re-raises after concrete usage.

## Source gap entries

- `~/Documents/01-U/.claude/gaps/raw/workflow-runner.md#2026-05-03-21:10`
  (`notes` group missing CRUD; only `init` exists)
- `~/Documents/01-U/.claude/gaps/raw/workflow-runner.md#2026-04-19-14:48`
  (earlier observation: `notes` is a near-empty stub)
