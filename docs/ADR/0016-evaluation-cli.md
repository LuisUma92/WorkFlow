---
adr: "0016"
title: "Evaluation CLI: Template, Item, and Course Management"
status: Accepted
date: 2026-04-09
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - cli
  - evaluation
  - taxonomy
decision_scope: module
supersedes: null
superseded_by: null
related_adrs:
  - "ITEP-0002"
  - "ITEP-0006"
  - "0007"
  - "0013"
---

## Context

The database schema (ADR ITEP-0002) defines evaluation templates, taxonomy items, and their links (`EvaluationTemplate`, `Item`, `EvaluationItem`), but no CLI existed to manage them. The only way to populate or query these tables was through ad-hoc scripts or direct SQLAlchemy calls.

Researchers need to:

- List and inspect evaluation templates per institution
- Create taxonomy items with Bloom-level/domain classification
- Compose evaluation templates by linking items with point values
- Query from Neovim without leaving the editor (Telescope pickers)

A decision was required to define the CLI architecture, command grouping, and Neovim integration strategy.

---

## Decision Drivers

- Consistency with existing Click CLI patterns (`workflow exercise`, `workflow lectures`)
- `--json` output for programmatic consumers (Neovim, scripts)
- Repository pattern (ADR-0007) for data access
- TDD with 80%+ coverage
- Neovim plugin integration via CLI one-shot calls (not JSONL server)

---

## Decision

### CLI Structure

Three Click groups wired into the main `workflow` CLI:

```
workflow evaluations list [--inst] [--full] [--json]
workflow evaluations show <id> [--json]
workflow evaluations add --inst --name [--description]
workflow evaluations edit <id> rename --name
workflow evaluations edit <id> add-item --item-id --amount --points
workflow evaluations edit <id> remove-item --eval-item-id
workflow item list [--domain] [--level] [--json]
workflow item add --name --level --domain [--item-type]
workflow course list [--inst] [--json]
workflow course add --inst --code --name [--lectures-per-week] [--hours-per-lecture]
```

### Architecture Layers

```
cli.py        Click commands (thin handlers)
    |
service.py    Business logic (validation, duplicate checks, ownership)
    |
repos/        SqlEvalTemplateRepo, SqlItemRepo, SqlCourseRepo
    |
models/       EvaluationTemplate, Item, EvaluationItem, Course
```

### Schema Additions

- `Item.item_type: str | None` — classification (SU, RC, Desarrollo)
- `EvaluationTemplate.description: str` — rules/instructions text
- `EvaluationTemplate.total_points` — computed property (`sum(amount * points_per_item)`)

### Neovim Integration (Phase 3)

Telescope pickers in `nvim-plugin/lua/workflow/telescope/`:

- `evaluations.lua` — picker with preview showing item breakdown
- `items.lua` — taxonomy item picker with domain/level display
- `courses.lua` — course picker with institution/schedule info

Each picker calls `workflow ... list --json` via `server.run_cli()` and parses JSON into Telescope entries. `pcall(vim.json.decode)` guards against malformed output.

Vim commands: `:WorkflowEvalPicker`, `:WorkflowItemPicker`, `:WorkflowCoursePicker`
Keybindings: `<leader>zte`, `<leader>zti`, `<leader>ztc`

### Formatters

Dual output in `formatters.py`:

- **Table mode**: Human-readable aligned columns for terminal use
- **JSON mode**: Structured output for Neovim and scripting

`_eval_to_dict()` includes `description` field and guards `ei.item` against `None`.

---

## Architectural Rules

### MUST

- All list commands **MUST** support `--json` output for Neovim integration.
- Evaluation templates **MUST** validate ownership before removing items (prevent cross-template deletion).
- Duplicate detection **MUST** be scoped to institution (same name allowed across institutions).
- Taxonomy level and domain **MUST** be validated against `_TAXONOMY_LEVELS` and `_TAXONOMY_DOMAINS` sets.
- `--item-type` **MUST** use `click.Choice` for input validation.

### SHOULD

- CLI handlers **SHOULD** delegate all logic to service functions.
- Formatters **SHOULD** access relationships only inside the session context (selectinload).
- Telescope pickers **SHOULD** guard `vim.json.decode` with `pcall`.

### MUST NOT

- CLI handlers **MUST NOT** contain raw SQLAlchemy queries — use service/repo layer.
- Formatters **MUST NOT** access lazy-loaded relationships outside session scope.

---

## Implementation Notes

- Package location: `src/workflow/evaluation/` (cli.py, formatters.py, service.py)
- Repos: `SqlEvalTemplateRepo`, `SqlItemRepo`, `SqlCourseRepo` in `workflow.db.repos.sqlalchemy`
- Protocols: `EvalTemplateRepo`, `ItemRepo`, `CourseRepo` in `workflow.db.repos.protocols`
- Telescope pickers: `nvim-plugin/lua/workflow/telescope/{evaluations,items,courses}.lua`
- Shared engine helper: `get_engine_from_ctx()` in `workflow.db.engine`
- Tests: `tests/workflow/test_evaluation_cli.py`, `test_eval_repos.py`, `test_eval_service.py`

### Phased Implementation

| Phase | Commands | Focus |
|-------|----------|-------|
| P0 | list (evaluations, item, course) | Read-only, --json output |
| P1 | add (evaluations, item) | Creation with validation |
| P2 | edit (rename, add-item, remove-item), course add | Mutation, ownership validation |
| P3 | evaluations show, Telescope pickers | Single-item detail, Neovim integration |

---

## Impact on AI Coding Agents

- New evaluation commands follow the pattern in `cli.py` → `service.py` → repo.
- Always add `--json` flag to new list/show commands.
- Use `selectinload()` for any relationship accessed in formatters.
- New Telescope pickers follow the pattern in `telescope/evaluations.lua`.
- Test with `CliRunner` + in-memory SQLite engine injected via `obj={"engine": engine}`.

---

## Consequences

### Benefits

- Evaluation data manageable from terminal and Neovim
- `--json` enables scripting and plugin integration
- Service layer makes business rules testable in isolation
- Ownership validation prevents accidental cross-template mutations

### Costs

- 3 new Click groups add to CLI surface area
- Telescope pickers require telescope.nvim as optional dependency
- Eager loading adds complexity but prevents DetachedInstanceError

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-04-09 | Initial ADR — documents P0-P3 evaluation CLI |
