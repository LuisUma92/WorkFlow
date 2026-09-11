---
id: 20260910-c901-complexity-refactors
title: Reduce C901 complexity of the 14 functions over the max-complexity=10 limit
type: chore
source_agent: user
opened_on: 2026-09-10

status: open
resolution:
priority: P3
severity: polish

labels:
  - cli
  - db
components:
  - workflow.db
  - workflow.vault
  - workflow.graph
  - workflow.validation
  - latexzettel

adr_refs: []
related_requests: []
related_gaps: []
duplicates: []
blocked_by: []

assignee: unassigned
target_release:
implementation: []
closed_on:
closed_by:

acceptance_criteria:
  - "Each function below is ≤ 10 under `flake8 --max-complexity=10`, or carries a justified `# noqa: C901` (one-shot migration code only)."
  - "Every refactored function has characterization tests written BEFORE the refactor (behaviour pinned first)."
  - "Suite stays green at the then-current baseline; no CLI output/exit-code change."
verification:
  - "uv run flake8 src/ --select=C901 --max-complexity=10 --exclude=src/PRISMAreview"
  - "WORKFLOW_DATA_DIR=$(mktemp -d) uv run pytest -q --ignore=tests/test_database.py"
---

# Request: Reduce C901 complexity of the 14 over-limit functions

## Context

After the 2026-09-10 strict-lint cleanup (`tasks/plans/2026-09-10-flake8-strict-cleanup-plan.md`),
C901 is the only remaining strict-run finding. Deliberately left out of that batch: these are
behavioural refactors, several of large, lightly-tested functions, and deserve TDD + review.

| Complexity | Function | File |
|-----------:|----------|------|
| 50 | `migrate_itep_db` | `src/workflow/db/migrate.py:80` |
| 38 | `unify` | `src/workflow/vault/unify.py` |
| 23 | `main` | `src/latexzettel/server/main.py:219` |
| 21 | `force_synchronize` | `src/latexzettel/api/sync.py:295` |
| 16 | `resolve_taxonomy_filter` | `src/workflow/graph/collectors.py` |
| 15 | `validate_exercise_metadata` | `src/workflow/validation/schemas.py:500` |
| 14 | `render_note` | `src/latexzettel/api/render.py:177` |
| 14 | `render_updates` | `src/latexzettel/api/render.py:410` |
| 13 | `walk_note_files` | `src/workflow/notes/discovery.py:40` |
| 13 | `choose_many` | `src/latexzettel/util/io.py:156` |
| 12 | `rename_reference` | `src/latexzettel/api/notes.py:170` |
| 11 | `split_notes_file` | `src/workflow/lecture/note_splitter.py:35` |
| 11 | `parse_md_frontmatter` | `src/workflow/validation/parsers.py:14` |
| 11 | `choose_one` | `src/latexzettel/util/io.py:110` |

Line numbers as of 2026-09-10 (they drift).

## Proposal

Triage before refactoring:
- **One-shot migration code** (`migrate_itep_db`, likely `unify`): consider `# noqa: C901` with a
  reason instead of refactoring code that runs once per install — [UNCLEAR] Luis decides.
- **Live paths** (`validate_exercise_metadata`, `walk_note_files`, `resolve_taxonomy_filter`,
  `parse_md_frontmatter`, `split_notes_file`): extract-helper refactors, one function per commit.
- **latexzettel legacy** (`render_*`, `force_synchronize`, `server.main`, `util/io`): lowest priority.

## Out of scope

- Any behaviour change. Refactor only.

## Progress log

- 2026-09-10 — opened from the flake8 strict-run cleanup (C901 deferred by design).
- 2026-09-10 — triage run (Luis: "procede"). Per-function coverage measured with pytest-cov:
  `migrate_itep_db` 0%, `unify` 91% → `# noqa: C901` (one-shot migrations), commit `99417c9`.
  Live `workflow` paths (`resolve_taxonomy_filter` 88%, `validate_exercise_metadata` 75%,
  `walk_note_files` 75%, `split_notes_file` 98%, `parse_md_frontmatter` 68%) → characterization
  tests then extract-helper refactor, one commit each. **latexzettel group deferred**: coverage
  `main` 0%, `choose_one`/`choose_many` 0%, `force_synchronize` 1%, `render_note`/`render_updates`
  2%, `rename_reference` 3% — they shell out to pdflatex/pandoc or prompt interactively, so a
  test harness (subprocess + prompt fakes) must exist before any refactor. Stays open for that.
- 2026-09-11 — **workflow group done** (5/5), one commit each, every diff reviewed by hand:
  `52d112a` resolve_taxonomy_filter 16→4 (+4 tests) · `b99962d` parse_md_frontmatter 11→≤10 (+25) ·
  `44a6a97` split_notes_file 11→≤10 (+1; traversal guard kept, resolved-`output_dir` precondition
  documented; `lectures split` output byte-identical) · `71877ef` walk_note_files 13→3 (+11) ·
  `ba9918c` validate_exercise_metadata 15→≤10 (+13; `validate exercises` output byte-identical).
  Suite 2629 → **2683 passed, 3 skipped**. Strict lint now = the **7 latexzettel C901 only**.
  Remaining scope of this request: the latexzettel group (needs a test harness first).
