---
id: 20260703-convention-engine-batch-transform
title: Convention engine + glob-aware batch transform surface (marco request)
type: feature
source_agent: user
opened_on: 2026-07-03

status: open
resolution:
priority: P3
severity: recurring-friction

labels:
  - cli
  - exercise
  - lecture
  - validation
components:
  - workflow.exercise
  - workflow.lecture
  - latexzettel

adr_refs: []
related_requests:
  - "20260703-exercise-failloud-validators"
  - "20260703-exercise-composability-flags"
  - "20260703-exercise-moodle-validate-scaffold"
  - "2026-06-26-figure-extract-pdf-bbox"
related_gaps:
  - raw/exam-author.md (31 entries)
  - raw/note-curator.md (15 entries)
  - raw/workflow-runner.md (17 entries)
duplicates: []
blocked_by: ["ADR pending (post-candidatura)", "candidatura exam (nov 2026)"]

assignee: unassigned
target_release: post-candidatura
implementation: []
closed_on:
closed_by:

acceptance_criteria:
  - "ADR written: conventions-as-data (naming, fragment layout, ifthenelse guard, exa macro, status enum, category-style) declared in machine-readable form, not prose"
  - "A transform runner applies a named convention over a glob of existing artifacts (SOURCE format A → deterministic mapping → TARGET convention B)"
  - "At least 3 historical transforms reproducible as transforms: reformat-bank (subfiles→guard+question), notes import-tex/export-tex round-trip, lab expand"
  - "The 54-gap corpus from the 2026-07-03 harvest serves as the acceptance-test checklist"
verification:
  - "post-ADR; deliberately unspecified until design is accepted"
---

# Request: Convention engine + batch transform (marco — DO NOT implement pre-candidatura)

## Context

Root formulation from `~/01-U/.claude/gaps/2026-07-03-transversal-gap-analysis.md`:

> WorkFlow models academic *entities* (Exercise, Note, Concept) with one-item
> CRUD, but does NOT model *conventions* nor *batch transformations between
> representations*. Conventions live in prose (CLAUDE.md, memory, the primer's
> "MECÁNICA (no re-derivar)" blocks), so the agent is forced to interpret them
> by hand and the SAME transform re-runs 7–10 times.

The 54 gaps of the 2026-07-03 harvest are one root with three faces:
(1) no transform/pipeline surface (~40 gaps), (2) conventions not SSOT → silent
drift, (3) non-composable interface. Faces 2 and 3 are being shipped piecemeal
in the pre-candidatura window (see related_requests). Face 1 — this request —
is the architecture item and is explicitly **deferred post-candidatura** by
council decision: the CI0006/CI0007 roadmaps that generated the volume are
closed, so there is no calendar pressure, and a half-implemented engine during
freeze is worse than none.

This marco request exists so the next gap harvest does NOT re-mine the same 54
gaps as new findings.

## Proposal

Post-exam, one-page ADR first, deciding:

1. **Conventions-as-data**: where codified conventions live (YAML in
   `data/conventions/`? DB table?), covering at minimum: exercise fragment
   layout + `\ifthenelse` guard, `\exa[área]{id}` format, status enum,
   Moodle category-style, weekly naming offsets, note→tex fragment mapping.
2. **Transform runner**: `workflow transform <convention> --glob <pattern>
   [--dry-run]` or per-domain verbs (`exercise reformat-bank`,
   `notes import-tex/export-tex`, `lectures scaffold`, `lab expand`) sharing
   one engine.
3. Which historical transforms become built-in (candidates and their gap
   anchors are enumerated in the transversal analysis table, Cara 1).

### Commands / API surface

```bash
# indicative only — ADR decides the real surface
workflow transform <name> --glob '<pattern>' [--dry-run] [--json]
```

### Shape of result

- deferred to ADR

## Acceptance criteria

- [ ] ADR accepted (post-candidatura)
- [ ] Conventions-as-data store shipped for ≥3 conventions
- [ ] Transform runner replays ≥3 historical transforms on fixture corpora
- [ ] 54-gap corpus used as acceptance checklist; each Cara-1 gap either covered or explicitly wontfix

## Out of scope

- Anything before nov 2026 exam
- LLM-dependent transforms (PDF extraction pipelines stay in their own request:
  `2026-06-26-figure-extract-pdf-bbox`)

## Evidence / glue replaced

```bash
# the primer's "MECÁNICA (no re-derivar)" blocks — a transform spec written in prose,
# re-executed by an agent 7–10 times per family (reformat-bank: 9 sessions;
# weekly Moodle pair: 10th instance; nota→tex weekly flow: 10 instances)
```

- evidence: `~/01-U/.claude/gaps/2026-07-03-transversal-gap-analysis.md` (full table)
- frequency observed: 54 de-duplicated gaps, 3 agents, apr–jul 2026

## Implementation notes

- Read the transversal analysis + audit BEFORE the ADR; both scoring rules
  (volumen_futuro × implementabilidad, not recurrencia histórica) apply to
  choosing which transforms get built first.
- The validators/flags shipped in the 2026-07 window are prerequisites, not
  substitutes — keep them stable.

## Progress log

- 2026-07-03 — opened by claude as marco request per transversal-analysis recommendation #1; implementation gated post-candidatura

## Closure checklist

When `status: closed` and `resolution: implemented`:

- [ ] All acceptance criteria checked
- [ ] ADR referenced in `closed_by`
- [ ] Cara-1 gap table cross-linked (each row → shipped transform / wontfix)
- [ ] CLAUDE.md and ADR INDEX updated
