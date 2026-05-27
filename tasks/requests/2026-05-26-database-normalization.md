---
id: 20260526-database-normalization
title: Main database normalization
type: enhancement
source_agent: None
opened_on: None

status: open
resolution:
priority: P1
severity: bad-design

labels:
  - sqlite
  - zettelkasten

components:
  - workflow.db.models

adr_refs: []
related_requests: []
related_gaps: []
duplicates: []
blocked_by: []

assignee: unassigned
target_release: v1.8.1
implementation: []
closed_on:
closed_by:

acceptance_criteria:
  -

verification:
  -
---

# Request: Review database models changes

## Context

The state of the database @~/01-U/workflow/workflow.db
at commit `5f02e75`
has inspected by my self and I found inconsistencies at database level.
The result of the audit is at @~/01-U/workflow/workflow_audit_20260523.txt
For this reason I modified the models.

This imply that I added relations, added tables, change relations, so that the
models became normalized.
But I didn't change integrations nor make a migration.

This request is to evaluate new models normalization.
Design a migration.
And, evaluate integration whit the rest of the code.

## Proposal

### Commands / API surface

- @./src/workflow/db/models/knowledge.py
- @./src/workflow/db/models/academic.py
- @./src/workflow/db/models/notes.py
- @./src/workflow/db/models/exercises.py

### Shape of result

## Acceptance criteria

## Out of scope

## Evidence / glue replaced

## Implementation notes

## Progress log

- 2026-05-26 — opened by Luis Fernando Umaña Castro after inspecting the current database `a693f1b`

## Closure checklist

When `status: closed` and `resolution: implemented`:

-
