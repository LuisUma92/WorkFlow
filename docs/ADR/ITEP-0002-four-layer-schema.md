---
id: ITEP-0002
nav_order: 25
parent: ADRs
title: "Esquema de base de datos en 4 capas"
aliases:
  - ADR-ITEP-0002
status: Accepted
date: 2026-03-20
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - database
  - schema
  - architecture
decision_scope: module
supersedes: null
superseded_by: null
related_adrs:
  - "ITEP-0001"
---

## Context

La base de datos relacional necesita una organización que refleje las dependencias naturales del dominio: datos de referencia estables, entidades maestras reutilizables, plantillas de cursos, e instancias concretas de proyectos.

---

## Decision Drivers

- Separación clara de responsabilidades
- Dependencias unidireccionales (capas superiores dependen de inferiores)
- Facilitar seed data para datos de referencia

---

## Decision

Organizar los modelos en 4 capas jerárquicas:

| Capa | Nombre            | Modelos                                                                                                                                                   | Descripción                          |
| ---- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| 1    | Reference data    | `Institution`, `MainTopic`                                                                                                                                | Datos estables, sembrados al inicio  |
| 2    | Master entities   | `Author`, `Book`, `BookAuthor`, `DisciplineArea`, `Topic`, `Content`, `BookContent`, `BibContent`, `Concept`, `MainTopicSyllabus`, `_TAXONOMY_DOMAINS`    | Entidades reutilizables entre cursos |
| 3    | Course templates  | `Course`, `CourseContent`, `EvaluationTemplate`, `Item`, `EvaluationItem`, `CourseEvaluation`, `_TAXONOMY_LEVELS`                                         | Estructura académica                 |
| 4    | Project instances | `LectureInstance`, `GeneralProject`, `GeneralProjectBook`, `GeneralProjectTopic`                                                                          | Instancias concretas en filesystem   |

### Module ownership (post-normalization, migration 0009)

| Module                            | Owns                                                                                                                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `workflow.db.models.knowledge`    | `DisciplineArea`, `MainTopic`, `Topic`, `Content`, `Concept`, `MainTopicSyllabus`, `_TAXONOMY_DOMAINS`                                                                          |
| `workflow.db.models.academic`     | `Institution`, `Course`, `CourseContent`, `EvaluationTemplate`, `Item`, `EvaluationItem`, `CourseEvaluation`, `_TAXONOMY_LEVELS` (imports `_TAXONOMY_DOMAINS` from `knowledge`) |
| `workflow.db.models.bibliography` | `BibEntry`, `BibContent` (gains `chapter_number`, `section_number`, `first_page`, `last_page`, `first_exercise`, `last_exercise`)                                               |
| `workflow.db.models.notes`        | `Note`, `Citation`, `Label`, `Link`, `Tag`, `NoteTag`, `NoteConcept`, `NoteEdge` — `Concept` no longer defined here                                                             |
| `workflow.db.models.exercises`    | `Exercise`, `ExerciseConcept` M2M (composite PK `(exercise_id, concept_id)`, `ON DELETE CASCADE` both FKs) — `Exercise.content_id` and `Exercise.concepts` JSON dropped         |

### Migration 0011 — Topic re-root (Phase 4B, 2026-05-27)

Migration `src/workflow/db/migrations/global/0011_topic_root_discipline_area.py`
ships as part of Phase 4B (`v1.11.0`). Forward-only per ITEP-0010.

**Schema change:** `Topic.main_topic_id` (FK→`MainTopic`) is replaced by
`Topic.discipline_area_id` (FK→`DisciplineArea`, NOT NULL, `ON DELETE RESTRICT`).
A `UNIQUE(discipline_area_id, serial_number)` constraint makes `serial_number`
the canonical chapter index within each area.

**New join table:** `MainTopicSyllabus(main_topic_id, topic_id, week_no, order_no)`
with composite PK `(main_topic_id, topic_id)`. Both FKs use `ON DELETE CASCADE`.
`week_no INTEGER NULL`; `order_no INTEGER NOT NULL`. This table holds
per-project-iteration syllabus ordering — concerns that were previously encoded
in the direct `Topic.main_topic_id` FK.

**Four-layer mapping update:** `Topic` moves conceptually from "constrained to a
single project instance" to a **fully canonical master entity** (Layer 2).
`MainTopicSyllabus` also lives in Layer 2 as a join between Layer-1 `MainTopic`
and Layer-2 `Topic`; the join is structural knowledge, not project state.

**Live DB context:** Live DB has 0 `topic` rows at migration time. Migration drops
and recreates the `topic` table cleanly (structural-only change; no data migration
required). `main_topic_syllabus` is created empty.

Full spec: `tasks/requests/2026-05-27-topic-reroot-discipline-area.md`.

---

## Architectural Rules

### MUST

- Las dependencias entre capas **MUST** ser descendentes: capa N solo referencia capas < N.
- Capa 1 **MUST NOT** tener foreign keys a otras capas.

### SHOULD

- Nuevas entidades **SHOULD** ubicarse en la capa correspondiente a su nivel de abstracción.
- Los datos de capa 1 **SHOULD** sembrarse en `seed_reference_data()`.

---

## Implementation Notes

Las capas están delimitadas con comentarios en `database.py`:

```python
# ── Layer 1: Reference data ──
# ── Layer 2: Master entities ──
# ── Layer 3: Course templates ──
# ── Layer 4: Project instances ──
```

---

## Impact on AI Coding Agents

- Al agregar un nuevo modelo, identificar la capa correcta antes de escribir código.
- No crear foreign keys de capas inferiores hacia superiores.

---

## Consequences

### Benefits

- Arquitectura legible y predecible
- Seed data aislada en capa 1
- Proyectos (capa 4) son instancias concretas que referencian templates (capa 3)

### Costs

- Requiere disciplina al agregar nuevos modelos

---

## Status

**Accepted** (module layout updated — see Change Log)

---

## Change Log

| Date       | Change                                                                                                                                                                                                                                                |
| ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-03-20 | Initial ADR                                                                                                                                                                                                                                           |
| 2026-05-27 | Updated module ownership table to reflect DB normalization landed in migration 0009 (`78472a3`). `Concept` moved to `knowledge` module; `ExerciseConcept` M2M added; `BibContent` extended; `_TAXONOMY_DOMAINS` moved from `academic` to `knowledge`. |
| 2026-05-27 | Phase 4B amendment: `Topic` re-rooted at `DisciplineArea` (migration 0011). `MainTopicSyllabus` join added to Layer 2 + `knowledge` module. Four-layer mapping updated; `Topic` now a fully canonical master entity. |
