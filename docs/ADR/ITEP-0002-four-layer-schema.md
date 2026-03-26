---
adr: "0002"
title: "Esquema de base de datos en 4 capas"
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

| Capa | Nombre | Modelos | Descripción |
|------|--------|---------|-------------|
| 1 | Reference data | `Institution`, `MainTopic` | Datos estables, sembrados al inicio |
| 2 | Master entities | `Author`, `Book`, `BookAuthor`, `Topic`, `Content`, `BookContent` | Entidades reutilizables entre cursos |
| 3 | Course templates | `Course`, `CourseContent`, `EvaluationTemplate`, `Item`, `EvaluationItem`, `CourseEvaluation` | Estructura académica |
| 4 | Project instances | `LectureInstance`, `GeneralProject`, `GeneralProjectBook`, `GeneralProjectTopic` | Instancias concretas en filesystem |

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

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-20 | Initial ADR |
