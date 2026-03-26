---
adr: "0007"
title: "Capa CRUD centralizada en manager.py"
status: Accepted
date: 2026-03-20
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - architecture
  - CRUD
  - separation-of-concerns
decision_scope: module
supersedes: null
superseded_by: null
related_adrs:
  - "ITEP-0001"
  - "ITEP-0002"
---

## Context

Las operaciones de creación, lectura, actualización y eliminación de entidades estaban dispersas entre `create.py`, `links.py` y código ad-hoc. Se necesita un punto centralizado que encapsule la lógica de acceso a datos.

---

## Decision Drivers

- Separación entre lógica de negocio (CLI) y acceso a datos
- Reutilización de operaciones CRUD entre CLIs (`inittex`, `relink`, futuras)
- Testabilidad

---

## Decision

Crear `itep/manager.py` con funciones CRUD para cada entidad de las 4 capas:

```python
def create_institution(session, short_name, full_name, ...) -> Institution
def create_book(session, name, year, edition) -> Book
def create_topic(session, main_topic_id, name, serial_number) -> Topic
def create_item(session, name, taxonomy_level, taxonomy_domain, ...) -> Item
# ...
```

Cada función recibe una `Session` SQLAlchemy, crea/consulta la entidad y hace `commit`.

---

## Architectural Rules

### MUST

- Operaciones CRUD reutilizables **MUST** ubicarse en `manager.py`.
- `manager.py` **MUST NOT** contener lógica de CLI ni I/O de usuario.

### SHOULD

- Los CLIs **SHOULD** delegar a `manager.py` para crear/modificar entidades.
- Funciones de manager **SHOULD** recibir `Session` como primer argumento.

### MAY

- Lógica CRUD simple e inline **MAY** permanecer en los CLIs si es específica del flujo.

---

## Implementation Notes

- `itep/manager.py`: funciones `create_*` organizadas por capa.
- Cada función acepta valores primitivos y retorna el modelo SQLAlchemy.

---

## Consequences

### Benefits

- Punto único para lógica de acceso a datos
- Facilita testing con sesiones de prueba
- CLIs más limpios y enfocados en flujo de usuario

### Costs

- Una capa adicional de indirección

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-20 | Initial ADR |
