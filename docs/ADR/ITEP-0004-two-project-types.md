---
adr: "0004"
title: "Dos tipos de proyecto: Lecture y General"
status: Accepted
date: 2026-03-20
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - domain-model
  - project-types
decision_scope: module
supersedes: null
superseded_by: null
related_adrs:
  - "ITEP/0002"
  - "ITEP/0005"
---

## Context

Los proyectos LaTeX académicos tienen dos naturalezas distintas:

- **Proyectos generales**: un tema principal con sus libros y subtemas (e.g., "Mecánica Clásica").
- **Proyectos de curso (lecture)**: una instancia de un curso en una institución, con ciclo, año, y contenidos semanales.

Cada tipo requiere una estructura de directorios diferente y diferentes relaciones en la DB.

---

## Decision Drivers

- Reflejar fielmente el dominio académico
- Estructura de directorios diferenciada
- Reutilización de cursos entre ciclos lectivos

---

## Decision

Dos modelos de proyecto en capa 4:

**`GeneralProject`**: vinculado 1:1 con un `MainTopic`. Estructura plana con `tex/`, `bib/`, `img/`, `config/`.

**`LectureInstance`**: vinculado a un `Course` (capa 3). Incluye subdirectorios `eval/`, `lect/` con symlinks a contenidos de múltiples temas. Soporta clonación entre ciclos (`clone_cycle`).

```python
class GeneralProject(Base):
    main_topic_id: Mapped[int]  # 1:1 con MainTopic
    # ...

class LectureInstance(Base):
    course_id: Mapped[int]      # N:1 con Course
    year: Mapped[int]
    cycle: Mapped[int]
    first_monday: Mapped[date]
    # ...
```

El CLI `inittex` ofrece la selección entre ambos tipos. El CLI `relink` despacha según `isinstance()`.

---

## Architectural Rules

### MUST

- Todo proyecto **MUST** ser `GeneralProject` o `LectureInstance`.
- El dispatch en `relink` y `create` **MUST** cubrir ambos tipos.

### SHOULD

- `LectureInstance` **SHOULD** derivar `root_dir` del código de institución + curso.
- `GeneralProject` **SHOULD** derivar `root_dir` del código del `MainTopic`.

---

## Implementation Notes

- `itep/models.py`: define `LectureProject` y `GeneralProject` como templates con árboles de directorios.
- `itep/create.py`: `create_lecture()` y `create_general()` como workflows independientes.
- `itep/links.py`: `relink_lecture()` y `relink_general()`.

---

## Consequences

### Benefits

- Cada tipo de proyecto tiene la estructura óptima para su caso de uso
- Cursos pueden clonarse entre ciclos preservando contenido

### Costs

- Lógica duplicada parcialmente entre los dos flujos (create, relink)

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-20 | Initial ADR |
