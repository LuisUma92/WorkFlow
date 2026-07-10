---
title: 0022 — ResearchQuestion as a first-class entity
nav_order: 22
parent: ADRs
---
# 0022 — ResearchQuestion as a first-class entity

- **Status:** Proposed
- **Date:** 2026-07-05
- **Domain:** Knowledge Layer / Zettelkasten
- **Depends on:** ITEP-0012 (concept ORM, slug-only referencing), ITEP-0013 (note relation graph), 0003 (hybrid DB), PRISMA-0005 (PRISMA CLI/SQLAlchemy migration)

## Context

The user's stated vision for this toolkit is a pipeline: **reading → notes →
research questions → theoretical frameworks**. Today, research questions
(RQs) have no schema home. `workflow prisma keyword` tracks PRISMA review
keywords, which are protocol-scoped search terms for a systematic review —
not a personal research-question backlog that a note can support, contradict,
or contextualize. The 2026-07-05 council evaluation identified this as one of
only **two** true schema-level gaps in the current design (the other being
vault search, ADR-0021) — everything else the vision calls for already has a
DB home (concepts, topics, notes, graph edges).

Without a home, RQs either get folded into tags (losing status/lifecycle) or
never get tracked at all, breaking the reading → framework pipeline at its
second step.

## Decision (Proposed)

Add `ResearchQuestion` as a GlobalBase entity, parallel in spirit to
`Concept` (ITEP-0012) and `MainTopic`:

- **`ResearchQuestion`**: `id`, `code` (slug, unique — same slug-only
  reference discipline as `Concept.code` per the 2026-07-04 ITEP-0012
  amendment), `question_text`, `status` (`open|active|answered|abandoned`),
  `created_date`, `closed_date` (nullable), `main_topic_id` (FK, nullable).
- **`NoteResearchQuestion`** (M2M, mirrors `NoteConcept`): `note_id`,
  `research_question_id`, `stance` (`supports|contradicts|contextualizes`).
- **CLI**: `workflow notes question add|list|link`, following the
  established Click group + service + formatter split (`workflow.evaluation`,
  `workflow.concept` as precedent).
- **Frontmatter**: new key `questions:` (list of RQ slug codes), ingested by
  `notes sync` as an additional pass alongside the existing concept-sync pass
  (`_sync_note_concepts`) — reusing the same resolve-by-slug, strict-mode
  pattern (`resolve_concepts` in `workflow.concept.service` is the template
  to follow, not to reuse directly: RQs are a distinct entity with their own
  resolver).

## Alternatives Considered

| Alternative | Reason Rejected (briefly) |
|---|---|
| RQs as tagged notes (`Tag`/`NoteTag`) | Tags have no `stance` relation and no status lifecycle (open/active/answered/abandoned); overloading tags would require ad hoc conventions the schema can't enforce |
| RQs inside the PRISMA module | PRISMA (`PRISMA-0000`..`PRISMA-0005`) is scoped to a single systematic-review protocol; personal RQs are cross-cutting across projects/reviews and outlive any one review's lifecycle |
| No dedicated entity — infer RQs from note content/graph | Defeats the purpose: the vision requires explicitly tracking open questions and their answer status, which is not recoverable from unstructured note text |

## Consequences

- Feeds a future `workflow synth` command (not yet designed): a theoretical
  framework becomes a query over `Concept` + `ResearchQuestion` + their note
  linkage — this ADR does not design `synth`, only ensures the RQ substrate
  it needs will exist.
- Slug-only referencing (per the ITEP-0012 amendment) extends to
  `ResearchQuestion.code`: `questions:` frontmatter never resolves by label,
  matching the existing concept-reference discipline — one less inconsistent
  surface for future contributors to trip on.
- New M2M table (`NoteResearchQuestion`) is additive; no existing table
  changes shape.
- `main_topic_id` FK on `ResearchQuestion` is optional at this stage — open
  question for implementation is whether it should be required once the
  `synth` command exists.

## Status

**Proposed.** Implementation deferred to post-freeze (target: November 2026).
Originates from the 2026-07-05 council evaluation. No code is written by this
ADR.

## Change Log

| Date       | Change                                                       |
| ---------- | --------------------------------------------------------------- |
| 2026-07-05 | Initial placeholder — register ResearchQuestion entity proposal. |
