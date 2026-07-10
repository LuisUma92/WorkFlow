---
id: 
parent: Wiki
title: Evaluation CLI
aliases: []
type: permanent
created: 
tags: []
concepts: []
references: []
exercises: []
images: []
---

# Evaluation CLI

Manage evaluation templates, taxonomy items, and courses from the command line.

## Commands

### Evaluations

```bash
# List all evaluation templates
workflow evaluations list
workflow evaluations list --inst UFide          # Filter by institution
workflow evaluations list --full                # Show item breakdown
workflow evaluations list --json                # JSON output (for scripts/nvim)

# Show a single template with full detail
workflow evaluations show 1
workflow evaluations show 1 --json

# Create a new evaluation template
workflow evaluations add --inst UFide --name "Estudio de caso"
workflow evaluations add --inst UCR --name "Parcial 1" --description "Primera evaluacion parcial."

# Edit a template
workflow evaluations edit 1 rename --name "Nuevo nombre"
workflow evaluations edit 1 add-item --item-id 3 --amount 2 --points 5
workflow evaluations edit 1 remove-item --eval-item-id 7
```

### Taxonomy Items

```bash
# List taxonomy items
workflow item list
workflow item list --domain "Informacion"
workflow item list --level "Comprender"
workflow item list --json

# Create a new item
workflow item add --name "SU - Info/Recordar" --level Recordar --domain "Informacion"
workflow item add --name "RC - Proc. Mental/Aplicar" --level "Usar-Aplicar" --domain "Procedimiento Mental" --item-type RC
```

### Courses

```bash
# List courses
workflow course list
workflow course list --inst UCR --json

# Create a course
workflow course add --inst UFide --code FI-201 --name "Fisica II"
workflow course add --inst UCR --code MA-101 --name "Calculo I" --lectures-per-week 4 --hours-per-lecture 1
```

## Neovim Integration

### Telescope Pickers

| Command | Keybinding | Description |
|---------|------------|-------------|
| `:WorkflowEvalPicker` | `<leader>zte` | Browse evaluation templates with preview |
| `:WorkflowItemPicker` | `<leader>zti` | Browse taxonomy items |
| `:WorkflowCoursePicker` | `<leader>ztc` | Browse courses |

Pickers accept optional arguments:

```vim
:WorkflowEvalPicker UFide          " Filter by institution
:WorkflowItemPicker Informacion    " Filter by domain
```

### JSON Output

All list/show commands support `--json` for programmatic use:

```bash
workflow evaluations list --json | jq '.[].name'
workflow evaluations show 1 --json | jq '.items'
```

## Architecture

See [ADR-0016](../ADR/0016-evaluation-cli.md) for the full architecture decision.

```
cli.py        Click commands (thin handlers)
service.py    Business logic (validation, duplicate checks)
formatters.py Table + JSON output
```

Data flows through the repository pattern:
- `SqlEvalTemplateRepo` — evaluation template queries with eager loading
- `SqlItemRepo` — taxonomy item queries with domain/level filters
- `SqlCourseRepo` — course queries with institution filter
