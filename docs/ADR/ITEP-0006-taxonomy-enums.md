---
id: ITEP-0006
title: "Taxonomía de Bloom para evaluaciones"
aliases:
  - ADR-ITEP-0006
status: Accepted
date: 2026-03-20
authors:
  - Luis Fernando Umaña Castro
reviewers: []
tags:
  - domain-model
  - taxonomy
  - evaluation
decision_scope: component
supersedes: null
superseded_by: null
related_adrs:
  - "ITEP-0002"
---

## Context

Las evaluaciones académicas requieren clasificar cada ítem según su nivel cognitivo y dominio de conocimiento. Se adopta una taxonomía basada en Bloom revisada, adaptada al contexto de enseñanza en ciencias.

---

## Decision Drivers

- Clasificación pedagógica estandarizada
- Validación a nivel de base de datos
- Consistencia entre instituciones

---

## Decision

Definir dos enums `StrEnum` en `itep/structure.py`:

```python
class TaxonomyLevel(StrEnum, metaclass=FriendlyEnumMeta):
    RECORDAR = "Recordar"
    COMPRENDER = "Comprender"
    ANALISIS = "Análisis"
    USAR_APLICAR = "Usar-Aplicar"
    USAR_EVALUAR = "Usar-Evaluar"
    USAR_CREAR = "Usar-Crear"
    METACOGNITIVO = "Metacognitivo"
    SISTEMA_INTERNO = "Sistema interno"

class TaxonomyDomain(StrEnum, metaclass=FriendlyEnumMeta):
    INFORMACION = "Información"
    PROCEDIMIENTO_MENTAL = "Procedimiento Mental"
    PROCEDIMIENTO_PSICOMOTOR = "Procedimiento Psicomotor"
    METACOGNITIVO = "Metacognitivo"
```

La tabla `item` incluye `CheckConstraint` que restringe los valores almacenados a los valores válidos de cada enum.

El modelo `Item` (capa 3) almacena `taxonomy_level` y `taxonomy_domain` como strings validados.

---

## Architectural Rules

### MUST

- Todo `Item` de evaluación **MUST** tener `taxonomy_level` y `taxonomy_domain` válidos.
- Las restricciones **MUST** aplicarse como `CheckConstraint` en la tabla `item`.

### SHOULD

- `FriendlyEnumMeta` **SHOULD** usarse para enums que necesiten mensajes de error legibles.
- `manager.create_item()` **SHOULD** aceptar tanto el enum como el string y almacenar `.value`.

---

## Implementation Notes

- `itep/structure.py`: definición de `TaxonomyLevel`, `TaxonomyDomain`, `FriendlyEnumMeta`.
- `itep/database.py`: tabla `item` con `CheckConstraint`.
- `itep/manager.py`: `create_item()` convierte enums a valores string.
- CLI canónica: `workflow item taxonomy --levels|--domains [--json]`
  expone los valores Bloom para agentes y scripts. La superficie
  paralela `workflow db disciplines list` (ADR ITEP-0009 Part I) cubre
  el catálogo de disciplinas DD; los dos no comparten nombre para
  evitar colisión de "taxonomy".

---

## Consequences

### Benefits

- Clasificación pedagógica explícita y validada
- Facilita reportes y análisis de cobertura taxonómica por curso

### Costs

- Modificar la taxonomía requiere actualizar enum + constraint + posible migración

---

## Status

**Accepted**

---

## Change Log

| Date       | Change      |
| ---------- | ----------- |
| 2026-03-20 | Initial ADR |
