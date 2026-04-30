# Gap Log Entry Template

Copy this block into your raw log (`~/Documents/01-U/.claude/gaps/raw/<your-agent>.md`)
every time you hit something the WorkFlow CLI or Neovim plugin should have handled
for you. Append-only — never overwrite prior entries.

---

## [AGENT-NAME] YYYY-MM-DD HH:MM — <short title>

**While doing:** <the single task you were executing, in one line>

**Friction:** <what was missing, awkward, or hand-rolled — be specific>

**Glue I wrote:** <the bash / Python / logic you stitched together instead of calling a single CLI command>

```bash
# paste the glue here, minimised — enough to make the gap concrete
```

**Proposed CLI:**

```bash
workflow <group> <subcommand> [--flag value ...]
```

**Shape of result I wanted:**

- stdout: <text | JSON keys | exit code>
- exit code 0 iff <condition>
- `--json` emits: `{…}` or `[{…}, …]`

**Severity:** blocker | recurring-friction | polish

**Frequency so far:** <count of times I've hit this in this session>

**Evidence:**

- `<file:line>` or full path
- command trace:

  ```
  $ workflow …
  <actual output>
  ```

- DB row id / bib key / course slug, if relevant

**Cross-references:** related raw entries (e.g. `raw/exam-author.md#2026-04-19-1432-…`)

---

## Severity guide

- **blocker** — had to abandon or ship a worse result because the CLI can't express it.
- **recurring-friction** — CLI gets there, but the same 3+ call dance repeats across tasks; should collapse into one command.
- **polish** — help text missing examples, confusing error message, JSON key inconsistent with sibling commands, no `--json` on a command whose group has it.

## When to log

- BEFORE writing glue code that isn't an obvious one-liner.
- AFTER a CLI call that produced the right answer but felt awkward.
- WHENEVER you catch yourself copy-pasting the same invocation with small tweaks.
- NEVER skip "because the task succeeded" — succeeded-with-friction is still a gap.

## When NOT to log

- Genuinely one-off user preferences ("I want this title in bold today").
- Known upstream TODOs already listed in `~/Projects/WorkFlow/tasks/todo.md` — reference them instead.
- Bugs in content (a wrong answer key in an exercise) — those go in course-level notes, not CLI gaps.
