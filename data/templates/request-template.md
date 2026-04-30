---
# Required identity fields
id: YYYYMMDD-short-slug          # filename stem; immutable once assigned
title: <one-line human title>
type: feature | bug | enhancement | gap | chore
source_agent: <agent name from ~/Documents/01-U/.claude/gaps/raw/*.md or "user">
opened_on: YYYY-MM-DD

# Lifecycle (mirrors GitHub issue states)
status: open | in_progress | blocked | closed | wontfix | duplicate
resolution:                      # set when status=closed
  # implemented | wontfix | duplicate | obsolete | superseded
priority: P0 | P1 | P2 | P3
severity: blocker | recurring-friction | polish

# Scoping (GitHub-issue style labels)
labels:
  - cli
  - db
  - nvim
  - docs
  - validation
  - exercise
  - lecture
  - graph
  - prisma
components:                      # WorkFlow modules touched (subset of CLAUDE.md)
  - workflow.evaluation
  - workflow.db
  - workflow.exercise
  - itep
  - latexzettel
  - workflow.nvim

# Linkage
adr_refs: []                     # e.g. ["ITEP-0009", "ADR-0016"]
related_requests: []             # other tasks/requests/*.md ids
related_gaps: []                 # raw/<agent>.md#<anchor>
duplicates: []                   # ids this request supersedes
blocked_by: []                   # request ids or external blockers

# Implementation tracking
assignee:                        # claude | <human> | unassigned
target_release:                  # milestone tag, optional
implementation: []               # paths / CLI strings shipped (filled on close)
closed_on:                       # YYYY-MM-DD
closed_by:                       # commit sha, PR url, or ADR id

# Acceptance
acceptance_criteria: []          # bullet list, each item must be checkable
verification: []                 # commands or tests proving criteria met
---

# Request: <Title>

## Context

<What's the situation today? What gap or friction prompted this? Cite file
paths, ADRs, or gap log entries with line refs where possible.>

## Proposal

<Concrete change requested. Keep separate from rationale.>

### Commands / API surface

```bash
workflow <group> <subcommand> [--flags]
```

Expected output / JSON shape:

```json
{ "...": "..." }
```

### Shape of result

- stdout: <text | JSON keys | exit code>
- exit code 0 iff <condition>
- `--json` emits: `{…}` or `[{…}, …]`

## Acceptance criteria

- [ ] <criterion 1 — must be objectively checkable>
- [ ] <criterion 2>
- [ ] Tests added under `tests/workflow/...` covering <case>
- [ ] Docs updated: CLAUDE.md command table, ADR if behavior changes
- [ ] `--json` flag parity with sibling commands (if applicable)

## Out of scope

<List explicitly excluded items so reviewers don't expand the request.>

## Evidence / glue replaced

```bash
# paste the ad-hoc glue this request would obsolete
```

- evidence: `<path:line>`
- frequency observed: <count>
- DB row / artifact ids, if relevant

## Implementation notes

<Optional. Hints, prior art, ADRs to read, gotchas. Not a design doc.>

## Progress log

- YYYY-MM-DD — opened by <agent>
- YYYY-MM-DD — <status change / commit sha / blocker found>

## Closure checklist

When `status: closed` and `resolution: implemented`:

- [ ] All acceptance criteria checked
- [ ] `verification` commands pass on master
- [ ] `implementation` frontmatter list filled with shipped paths/commands
- [ ] `closed_by` references commit/PR/ADR
- [ ] CLAUDE.md and ADR INDEX updated if architecture changed
- [ ] Related gap log entries cross-linked back to this request id
