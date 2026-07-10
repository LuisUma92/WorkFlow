---
title: Concept Skyfolding
parent: Wiki
---
# Concept Skyfolding

> Nota de ubicación: junto a las demás páginas prácticas en `docs/wiki/`
> (ver `Fleeting-Monolith-Flow.md`, `Lectures-Workflow.md`, `Zettelkasten-Notes.md`
> en el mismo directorio).

Un **skyfolding** es un archivo YAML que siembra, de arriba hacia abajo
("top-down"), una jerarquía completa `DisciplineArea → Topic → Content →
Concept` para un área o curso, ANTES de que existan notas que la referencien.
Es la fuente única de verdad para esa jerarquía — `workflow import` es el
único camino de escritura (ADR-0018).

## Dónde viven

Hoy existen 5 en el vault, en `~/01-U/0000AV-Vault/templates/`:

```
0010MC-contents-skyfolding.yml   # Mecánica Clásica
0040EM-contents-skyfolding.yml   # Electromagnetismo
0030MO-contents-skyfolding.yml   # Óptica (extraída de 0040EM 2026-06-30)
...
```

## Convención de nombre

`<DDTTAA>-contents-skyfolding.yml`

- `DD` — dígitos de disciplina (p. ej. `00` = Física).
- `TTAA` — código de main-topic (`data/00-PhysicsCodes.csv`, ITEP-0008),
  p. ej. `10MC` (Mecánica Clásica).
- `DD` + `TTAA` = `DDTTAA`, p. ej. `00` + `10MC` = `0010MC`.

`data/00-PhysicsCodes.csv` lista el nivel `TTAA`; el skyfolding usa el nivel
completo `DDTTAA`. Son dos niveles de la misma nomenclatura ITEP-0008, no dos
convenciones distintas (resuelto en el diseño de harvest, 2026-07-05).

## Plantilla

`data/templates/concept-skyfolding-template.yml` — placeholders entre
`<ángulos>`, comentarios inline por campo, un ejemplo mínimo relleno (1 topic,
1 content, 2 concepts) y el esqueleto completo debajo. Copiar de ahí, no
inventar estructura ad hoc.

## Referencia de esquema (campos)

| Campo | Nivel | Obligatorio | Descripción |
|---|---|---|---|
| `discipline_area_code` | raíz | sí | `DDTTAA` completo |
| `discipline_area_name` | raíz | sí | Nombre visible del área |
| `dewey` | raíz | sí | Clasificación Dewey (string) |
| `books[].cite` / `.bibkey` | raíz | no | Referencias bibliográficas citadas por `contents[].book` |
| `topics[].name` | topic | sí | Nombre del topic |
| `topics[].serial` | topic | sí | Único por `discipline_area_code` |
| `topics[].unit` | topic | no | Etiqueta de unidad docente, libre |
| `contents[].name` | content | sí | Nombre del content |
| `contents[].cnnsmm` | content | no | Enlace a `admin/MapeoUnidadCapitulo.md` |
| `contents[].book` | content | no | Rango de secciones del libro citado |
| `concepts[].code` | concept | sí | Slug único global, `^[a-z0-9][a-z0-9-]{0,31}$`, prefijo por área (`mc-`, `em-`, ...) |
| `concepts[].label` | concept | sí | Nombre visible (display-only) |
| `concepts[].domain` | concept | sí | Marzano: `Información\|Procedimiento Mental\|Procedimiento Psicomotor\|Metacognitivo` |
| `concepts[].parent_code` | concept | no | `code` de un concepto ancestro |
| `concepts[].description` | concept | no | Texto libre |

## Dos ciclos de vida (ver Fleeting-Monolith-Flow.md §3)

1. **Skyfolding-first** (caso normal): el skyfolding se importa antes de
   escribir notas del tema; las notas solo referencian slugs ya existentes.
2. **Harvest-later**: un slug nuevo nace dentro de una nota (p. ej. un
   concepto "puente" entre temas) antes de que exista en ningún skyfolding.
   `workflow concept harvest` (diseño 2026-07-05,
   `docs/superpowers/specs/2026-07-05-fleeting-harvest-design.md`) escanea
   notas, detecta slugs desconocidos y emite un **delta** en este mismo
   formato de skyfolding — nunca escribe a la DB directamente. El humano
   completa `label`/`domain`/`content` (harvest los deja con marcadores
   `TODO-REVIEW`/`# REVIEW` a propósito) y corre `workflow import delta.yaml`
   como con cualquier skyfolding.

## Semántica de import a tener en cuenta (ADR-0018)

- Exit codes: `0` éxito/`--dry-run` limpio, `1` error de schema/YAML (antes de
  escribir), `2` `discipline_area_code` desconocido (antes de escribir),
  `3` fallo parcial (algunas filas creadas, otras con error de fila).
- **Idempotente**: re-importar el mismo archivo salta duplicados (exit 0).
  Claves de salto: topic `(discipline_area_id, serial_number)`, content
  `(topic_id, name)`, concept `code` (global).
- **Concept global-skip**: un `code` reutilizado bajo un `content` distinto
  se salta silenciosamente — NO se re-enlaza al nuevo content. Si un
  skyfolding define un concepto que ya existe en otra parte del árbol, ese
  concepto queda donde estaba la primera vez.

## Slugs: slug-only estricto (ITEP-0012, decisión #18)

`Concept.code` es la ÚNICA clave de referencia, para siempre — nunca hay
resolución por `label`. `resolve_concepts()` (`src/workflow/concept/service.py`)
nunca gana un fallback por nombre visible. `label` es puramente de
presentación; cambiarlo no afecta ningún enlace.

## Ver también

- `docs/wiki/Fleeting-Monolith-Flow.md` — flujo semanal de notas fleeting y
  los dos ciclos de vida de conceptos en contexto de uso real.
- `docs/superpowers/specs/2026-07-05-fleeting-harvest-design.md` — diseño
  técnico de `workflow concept harvest`.
- `docs/ADR/ITEP-0012-concept-orm.md` — contrato slug-only (decisión #18).
- `docs/ADR/0018-bulk-import-contract.md` — contrato de `workflow import`.
- `data/templates/concept-skyfolding-template.yml` — plantilla para empezar
  un skyfolding nuevo.
