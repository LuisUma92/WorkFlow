---
id: 0020
nav_order: 20
parent: ADRs
title: "Bibliography module boundary: foundation layer + 0/1/2+ lookup contract"
aliases:
  - ADR-0020
status: Accepted
date: 2026-06-02
authors:
  - Luis Fernando Umaña Castro
reviewers:
  - Luis Fernando Umaña Castro
tags:
  - architecture
  - domain
  - bibliography
  - module-boundary
decision_scope: module
supersedes: null
superseded_by: null
related_adrs: ["0007", "0019", "PRISMA-0005"]
---

## Context

`workflow.bibliography` was extracted (v1.14.0) as a peer module alongside
`content`, `exercise`, and `prisma`. It is a **foundation/lookup layer**: other
feature modules depend on it; it depends on none of them. Its current public
surface includes `get_bib_entry_by_bibkey` (hardened single-entry lookup) and
`BibKeyAmbiguous` (raised on 2+ matches, renamed `AmbiguousLookupError` per
followups #1/#5, commit `07979b5`).

Because bibkeys are intentionally **non-unique** (ADR-0019 §Audit finding 5 —
rejected `UNIQUE(bibkey)`), callers cannot assume a bibkey resolves to exactly
one row. The module must communicate that possibility through a documented,
contractual API.

A re-export of `get_bib_entry_by_bibkey` still lives in `prisma.service`
(historical coupling); this ADR initiates its deprecation path.

## Decision Drivers

- A one-directional dependency graph prevents import cycles and keeps the
  module testable in isolation.
- Callers must not silently ignore ambiguity; the lookup contract must be typed
  and documented.
- A clean deprecation path for the `prisma.service` re-export avoids a hard
  cut-over that would break existing callers before they can migrate.

## Decision

Three things are codified simultaneously:

1. **Foundation-layer designation.** `workflow.bibliography` is a foundation
   layer. Allowed dependents: `content`, `exercise`, `prisma`, CLI surfaces.
   Forbidden: `workflow.bibliography` importing upward from any of those.

2. **0/1/2+ lookup contract.** `get_bib_entry_by_bibkey(bibkey, session)`
   returns:
   - `None` — no matching row.
   - `BibEntry` — exactly one match.
   - raises `BibKeyAmbiguous` (a.k.a. `AmbiguousLookupError`) — two or more
     matches. Consumers **MUST** handle all three branches.

3. **Deprecation of the `prisma.service` re-export.** The re-export is a
   transitional shim; new code MUST import from `workflow.bibliography`
   directly. Removal is tracked in backlog item #3.

## Architectural Rules

### MUST

- `workflow.bibliography` **MUST NOT** import from `workflow.content`,
  `workflow.exercise`, or `workflow.prisma`. Dependency runs one way only.
- Callers of `get_bib_entry_by_bibkey` **MUST** handle the `None`, single-
  entry, and `BibKeyAmbiguous` branches explicitly — no bare attribute access
  on an unguarded return value.
- `BibKeyAmbiguous` / `AmbiguousLookupError` **MUST** be imported from
  `workflow.bibliography` (or `workflow.db.errors` once graduated per ADR-0007
  amendment 2026-06-02), not from `workflow.prisma.service`.

### SHOULD

- New code **SHOULD** import `get_bib_entry_by_bibkey` from
  `workflow.bibliography`, not from the `prisma.service` re-export.
- The `prisma.service` re-export **SHOULD** emit a `DeprecationWarning` until
  removed (backlog #3).

### MAY

- Read-heavy CLI surfaces **MAY** bypass the repository Protocol interfaces
  and query the ORM directly (e.g. single-row lookups in the bibliography or
  `content link-bib` commands); the repo-protocol requirement (ADR-0007)
  applies to write paths and complex queries.

## Consequences

- **Positive:** Clean one-directional layering; `AmbiguousLookupError` is a
  shared, reusable base; callers are forced to handle ambiguity explicitly.
- **Negative / cost:** One more module boundary to enforce in reviews; the
  `prisma.service` re-export must remain until all callers migrate (backlog #3).
