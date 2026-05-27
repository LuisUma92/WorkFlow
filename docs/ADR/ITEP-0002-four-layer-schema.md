---
id: ITEP-0002
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

| Capa | Nombre            | Modelos                                                                                                                        | Descripción                          |
| ---- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------ |
| 1    | Reference data    | `Institution`, `MainTopic`                                                                                                     | Datos estables, sembrados al inicio  |
| 2    | Master entities   | `Author`, `Book`, `BookAuthor`, `Topic`, `Content`, `BookContent`, `BibContent`, `Concept`, `DisciplineArea`, `_TAXONOMY_DOMAINS` | Entidades reutilizables entre cursos |
| 3    | Course templates  | `Course`, `CourseContent`, `EvaluationTemplate`, `Item`, `EvaluationItem`, `CourseEvaluation`, `_TAXONOMY_LEVELS`              | Estructura académica                 |
| 4    | Project instances | `LectureInstance`, `GeneralProject`, `GeneralProjectBook`, `GeneralProjectTopic`                                               | Instancias concretas en filesystem   |

### Module ownership (post-normalization, migration 0009)

| Module                          | Owns                                                                                                          |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `workflow.db.models.knowledge`  | `DisciplineArea`, `MainTopic`, `Topic`, `Content`, `Concept`, `_TAXONOMY_DOMAINS`                            |
| `workflow.db.models.academic`   | `Institution`, `Course`, `CourseContent`, `EvaluationTemplate`, `Item`, `EvaluationItem`, `CourseEvaluation`, `_TAXONOMY_LEVELS` (imports `_TAXONOMY_DOMAINS` from `knowledge`) |
| `workflow.db.models.bibliography` | `BibEntry`, `BibContent` (gains `chapter_number`, `section_number`, `first_page`, `last_page`, `first_exercise`, `last_exercise`) |
| `workflow.db.models.notes`      | `Note`, `Citation`, `Label`, `Link`, `Tag`, `NoteTag`, `NoteConcept`, `NoteEdge` — `Concept` no longer defined here |
| `workflow.db.models.exercises`  | `Exercise`, `ExerciseConcept` M2M (composite PK `(exercise_id, concept_id)`, `ON DELETE CASCADE` both FKs) — `Exercise.content_id` and `Exercise.concepts` JSON dropped |

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

| Date       | Change                                                                                   |
| ---------- | ---------------------------------------------------------------------------------------- |
| 2026-03-20 | Initial ADR                                                                              |
| 2026-05-27 | Updated module ownership table to reflect DB normalization landed in migration 0009 (`78472a3`). `Concept` moved to `knowledge` module; `ExerciseConcept` M2M added; `BibContent` extended; `_TAXONOMY_DOMAINS` moved from `academic` to `knowledge`. |
