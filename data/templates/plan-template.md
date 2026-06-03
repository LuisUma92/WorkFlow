# Implementation plan — <Feature title>

Request: `tasks/requests/<YYYYMMDD-slug>.md`
ADR: `docs/ADR/<id>-<slug>.md` (**<Accepted | Supersedes XYZ>**)  <!-- omit line if no ADR yet -->
Methodology: TDD (RED→GREEN→REFACTOR), reviewer-esquema each phase, forward-only
migrations (ITEP-0010). Phases ship independently; commit at each GREEN.

---

## Verified anchors (confirmed in code)

<!-- Read the relevant source files BEFORE writing this section.
     List exact file paths, class/function names, column types, migration numbers,
     and any invariants that MUST be preserved. Flag anything uncertain with [UNCLEAR]. -->

- `<module.Class.field>` — <type + current behaviour>
- Migration harness: `src/workflow/db/migrations/global/`; latest = `<NNNN_name>.py` → next = `<NNNN+1>_`.
- <CLI entry point>: `<module.path>` — <relevant behaviour>
- <Other anchor …>

---

## Target / design

<!-- One-paragraph description of the end state: what CLI commands exist, what DB
     schema looks like, what invariants hold. Enough for a reviewer to judge scope. -->

<End-state description.>

### Commands / API surface

```bash
workflow <group> <subcommand> [--flags]
```

Expected output / JSON shape:

```json
{ "<key>": "<value>" }
```

---

## Resolved design rules

<!-- List every non-obvious design choice with its rationale.
     Mark items still requiring user confirmation with ★ -->

- **<Rule name>**: <decision + rationale>. ★ <optional confirm item>
- **Fallbacks**: <missing-field → token>; <edge-case → behaviour>.
- **Collision / disambiguation**: <strategy>.
- **Type classification** (if applicable): <type sets + fallback>.

---

## Decisions — LOCKED (user, <YYYY-MM-DD>)

<!-- Promote ★ items here once the user confirms. Keep numbered for back-reference. -->

1. <Decision 1 — e.g. default behaviour of flag>
2. <Decision 2 — e.g. fallback tokens>
3. <Decision 3 — e.g. scope of --all vs fill-missing>

---

## Phases

### Phase 1 — <short label, e.g. "pure function / no DB">

**Goal:** <One sentence: what this phase proves works.>

**RED tests** (`tests/workflow/<module>/test_<slug>.py`):

- <test case 1 — input → expected output>
- <test case 2 — edge / fallback>
- <test case 3 — …>

**GREEN impl** — files touched:

- `src/workflow/<module>/<file>.py` (new | edit) — <what it adds>
- `src/workflow/<module>/<other>.py` (edit) — <what changes>

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P1.

---

### Phase 2 — <short label, e.g. "schema migration + integration">

**Goal:** <One sentence.>

**RED tests:**

- <test case>
- Migration idempotency test.
- <…>

**GREEN impl** — files touched:

- `src/workflow/db/migrations/global/<NNNN>_<slug>.py` (new migration)
- `src/workflow/db/models/<model>.py` (edit) — <new columns/relations>
- `src/workflow/<module>/<file>.py` (edit) — <integration point>

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P2.

---

### Phase 3 — <short label, e.g. "CLI command + docs">

**Goal:** <One sentence.>

**RED tests:**

- <test case — dry-run, idempotency, backup, …>
- <…>

**GREEN impl** — files touched:

- `src/workflow/<module>/cli.py` (edit) — <new command/flag>
- `src/workflow/<module>/<service>.py` (new | edit)
- `CLAUDE.md` — update command table row
- `docs/ADR/<id>-<slug>.md` — update "landed" note  <!-- if applicable -->

**Commit point:** suite green + flake8 0 → commit + reviewer-esquema P3.

---

## Risks / out of scope

<!-- Be explicit so reviewers don't silently expand scope. -->

- **In scope:** <…>
- **Out of scope:** <…>
- **Risk:** <e.g. mutates existing data — gate on backup + dry-run>.
- **Risk:** <e.g. breaking change — gate on Decision N>.
- No schema migration expected (all columns already exist).  <!-- delete if inapplicable -->

---

## Verification (each phase)

```bash
# Isolated suite — never touches live DB
WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py

# Lint
uv run flake8 src/ tests/ --max-line-length=127 --max-complexity=10

# P3 live dry-run (on a COPY of the live DB, never the original)
# cp ~/01-U/workflow/workflow.db /tmp/workflow-test.db
# WORKFLOW_DATA_DIR=/tmp workflow <group> <command> --dry-run
```
