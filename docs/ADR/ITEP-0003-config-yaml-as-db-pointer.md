---
adr: "0003"
title: "config.yaml como puntero a la base de datos"
status: Accepted
date: 2026-03-20
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - configuration
  - YAML
  - persistence
decision_scope: module
supersedes: null
superseded_by: null
related_adrs:
  - "ITEP-0001"
---

## Context

Anteriormente, `config.yaml` contenía toda la configuración del proyecto (metadatos, temas, libros, evaluaciones). Con la migración a SQLAlchemy, esta información reside en la DB.

Se necesita un mecanismo para vincular un directorio de proyecto en disco con su registro en la base de datos.

---

## Decision Drivers

- Evitar duplicación de datos entre DB y YAML
- Mantener un archivo legible en cada proyecto
- Simplicidad máxima

---

## Decision

`config.yaml` se reduce a un puntero con dos campos:

```yaml
project_type: lecture   # o "general"
project_id: 42
```

El módulo `itep/ioconfig.py` provee:

- `save_config(project_type, project_id, path)` — escribe el puntero.
- `load_config(file)` — lee el puntero y resuelve la entidad desde la DB.
- `read_pointer(file)` — lee el dict crudo sin resolver.

---

## Architectural Rules

### MUST

- `config.yaml` **MUST** contener solo `project_type` y `project_id`.
- `load_config` **MUST** resolver el proyecto vía `session.get()`.

### MUST NOT

- `config.yaml` **MUST NOT** contener datos de dominio (temas, libros, evaluaciones).

### SHOULD

- Toda operación sobre un proyecto existente **SHOULD** iniciar leyendo `config.yaml` para obtener el ID.

---

## Implementation Notes

- `itep/ioconfig.py`: lectura/escritura del puntero.
- `itep/utils.py`: funciones `load_yaml` / `write_yaml` de bajo nivel.
- Tanto `relink` como `inittex` usan este patrón.

---

## Impact on AI Coding Agents

- No escribir datos adicionales en `config.yaml`.
- Para acceder a datos del proyecto, usar `load_config()` que retorna el modelo SQLAlchemy completo.

---

## Consequences

### Benefits

- Single source of truth en la DB
- `config.yaml` trivial y sin riesgo de desincronización

### Costs

- Requiere acceso a la DB para cualquier operación sobre el proyecto

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-20 | Initial ADR |
