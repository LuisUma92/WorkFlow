---
adr: "0001"
title: "Migración de dataclasses a SQLAlchemy ORM"
status: Accepted
date: 2026-03-20
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - persistence
  - database
  - SQLAlchemy
decision_scope: module
supersedes: null
superseded_by: null
related_adrs:
  - "ITEP/0002"
  - "ITEP/0003"
---

## Context

El módulo itep usaba dataclasses (`Admin`, `Book`, `Topic`, `MetaData`, `Evaluation`, `ProjectStructure`) serializadas a YAML como mecanismo de persistencia. Esto generaba duplicación de datos entre proyectos, imposibilidad de consultar relaciones cruzadas y ausencia de integridad referencial.

Se requiere un almacenamiento relacional que permita reutilizar entidades (autores, libros, temas) entre proyectos y cursos.

---

## Decision Drivers

- Integridad referencial entre entidades
- Reutilización de datos maestros (autores, libros, instituciones)
- Consultas relacionales (contenidos por curso, libros por tema)
- Simplicidad operativa (SQLite, sin servidor)

---

## Decision

Reemplazar las dataclasses de persistencia por modelos SQLAlchemy ORM con SQLite como backend. La base de datos se almacena en `~/.local/share/itep/itep.db` (vía `appdirs`).

Los dataclasses remanentes en `structure.py` cumplen roles no persistentes: enums, helpers de filesystem y templates de estructura de directorios.

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Institution(Base):
    __tablename__ = "institution"
    id: Mapped[int] = mapped_column(primary_key=True)
    short_name: Mapped[str] = mapped_column(String(10), unique=True)
    # ...
```

---

## Architectural Rules

### MUST

- Toda entidad persistente **MUST** ser un modelo SQLAlchemy en `itep/database.py`.
- Las foreign keys **MUST** estar habilitadas vía `PRAGMA foreign_keys=ON` (listener en `get_engine`).

### SHOULD

- Los modelos **SHOULD** usar `Mapped` type hints (estilo SQLAlchemy 2.0).
- Las relaciones **SHOULD** declarar `back_populates` explícitamente.

### MAY

- Dataclasses **MAY** usarse para estructuras transitorias no persistentes (templates, helpers).

---

## Implementation Notes

- `itep/database.py`: todos los modelos ORM.
- `itep/defaults.py`: ruta de la DB (`DB_PATH`).
- `init_db()` crea todas las tablas; `seed_reference_data()` inserta datos de referencia.
- `get_session()` retorna una sesión SQLAlchemy lista para usar.

---

## Impact on AI Coding Agents

- Nuevas entidades persistentes deben crearse como modelos en `database.py`, nunca como dataclasses.
- Usar `get_session()` para obtener sesiones; no crear engines manuales.
- Respetar las capas del esquema (ver ADR 0002).

---

## Consequences

### Benefits

- Integridad referencial automática
- Consultas relacionales sin duplicación
- Migraciones posibles vía Alembic a futuro

### Costs

- Dependencia en SQLAlchemy
- Mayor complejidad inicial vs YAML plano

---

## Alternatives Considered

### YAML con referencias cruzadas

Mantener YAML añadiendo IDs manuales y referencias entre archivos.

#### Disadvantages

- Sin integridad referencial real
- Consultas manuales con código ad-hoc

---

## Compatibility / Migration

Cambio no retrocompatible. Los proyectos existentes con `config.yaml` completo deben recrearse o migrarse manualmente al nuevo esquema DB + pointer.

---

## References

- SQLAlchemy 2.0 — Mapped Column Declarations
- appdirs — User data directory conventions

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-20 | Initial ADR |
