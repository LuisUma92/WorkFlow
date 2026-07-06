---
id:
title:
aliases: []
type: permanent
created:
tags: []
concepts: []
references: []
exercises: []
images: []
---

# Exam Workflow

Flujo de produccion de examenes: generar el esqueleto XML de Moodle
(`workflow exam scaffold-xml`), validarlo estructuralmente
(`workflow exam validate`) y, cuando el examen se ensambla desde el banco de
ejercicios en vez de a mano, ensamblarlo con `workflow exercise build-exam`
(reporte de balance taxonomia x concepto) antes de exportar a Moodle con
`workflow exercise export-moodle`.

## Comandos

### exam scaffold-xml — Esqueleto Moodle XML

Genera un XML de Moodle con placeholders `CDATA[TODO]` para cada pregunta —
util para reservar la estructura de categorias/preguntas antes de escribir el
contenido real. Dos modos, mutuamente excluyentes, detectados por que
opciones se pasan:

- **legacy**: `--cycle --group --label --category --blocks` (todos requeridos
  juntos)
- **weekly**: `--week --dc --kind` (todos requeridos juntos)

Mezclar opciones de ambos modos es un error (`click.UsageError`, exit 2).

#### Modo legacy

```bash
workflow exam scaffold-xml \
  --course FS0211 \
  --cycle 2026C1 --group 001 --label PC04 \
  --category "FS0211/2026C1/001/PC04" \
  --blocks "Recordar:4,Comprender:4" \
  -o pc04-skeleton.xml
```

- `--blocks` es una lista `Nombre:count` separada por comas — una categoria
  Moodle por bloque, con `count` preguntas placeholder cada uno.
- `--question-prefix`, `--penalty` (default `0.25`) y `--grade` (default `1`)
  son opcionales, solo aplican a este modo.

#### Modo weekly

```bash
workflow exam scaffold-xml \
  --course CI0007 \
  --week 11 --dc semana11/DC.md --kind comprension \
  -o semana11-comprension.xml
```

- `--dc FILE` — ruta al `DC.md` de la semana; las categorias Moodle se derivan
  de los encabezados `##` de ese archivo.
- `--kind comprension|practica` — tipo de quiz semanal.
- `--category-style flat|hierarchical` (default `flat`) — empaquetado de
  categorias Moodle; `hierarchical` es opt-in documentado, no el default.
- **Offset Practica-N -> PC-N -> Tema #(N+1)**: en `--kind practica`, la
  practica N de la semana se etiqueta como "Tema #(N+1)" internamente
  (`workflow.exam.weekly.tema_label_for_practica`) — **no re-derivar este
  offset a mano**, siempre reusar esa funcion si se necesita en otro lado.
- Idnumbers generados en formato **WWCCNN** (semana-categoria-numero, con
  guardas de overflow 1..99 por categoria).
- `--json` (ambos modos) emite un resumen JSON en vez de prosa.

### exam validate — Lint estructural

```bash
workflow exam validate semana11-comprension.xml
workflow exam validate semana11-comprension.xml --strict
workflow exam validate semana11-comprension.xml --json
```

Exit 1 si hay cualquier violacion; nunca deja pasar en silencio un mismatch
raw-scan/etree (loudness guard).

| Regla | Alcance | `--strict` |
|---|---|---|
| `fraction=100` presente en la opcion correcta (multichoice) | siempre | |
| `fraction=0` en distractores | siempre | |
| CDATA bien formado (tolerante a orden/comillas de atributos) | siempre | |
| `defaultgrade` presente | siempre | |
| `penalty` presente | siempre | |
| `single` presente (multichoice) | siempre | |
| `idnumber` presente por pregunta | | si |
| `category` presente por pregunta | | si |

`--json` emite el reporte estructurado en vez de prosa (violaciones por
pregunta).

## Ejemplo completo: semana UCIMED CI0007

Flujo tipico de una semana de curso, del `DC.md` al XML validado:

```bash
# 1. Redactar el DC.md de la semana con encabezados ## por tema
#    (semana11/DC.md)

# 2. Generar el esqueleto weekly para el quiz de comprension
workflow exam scaffold-xml \
  --course CI0007 --week 11 --dc semana11/DC.md --kind comprension \
  -o semana11/comprension.xml

# 3. Generar el esqueleto weekly para la practica (offset Tema #(N+1) aplicado)
workflow exam scaffold-xml \
  --course CI0007 --week 11 --dc semana11/DC.md --kind practica \
  -o semana11/practica.xml

# 4. Reemplazar los CDATA[TODO] con las preguntas reales
#    (editar el XML o generarlo desde el banco de ejercicios, ver abajo)

# 5. Validar antes de subir a Moodle
workflow exam validate semana11/comprension.xml --strict
workflow exam validate semana11/practica.xml --strict
```

## Ensamblar desde el banco de ejercicios (alternativa a editar CDATA a mano)

Cuando el examen se arma seleccionando ejercicios ya existentes en el banco
(no escribiendo preguntas nuevas dentro del XML), usar
`workflow exercise build-exam` y despues `export-moodle` — ver
[Exercise Workflow](Exercise-Workflow.md#construir-un-examen) para el flujo
completo del banco.

```bash
workflow exercise build-exam \
  -l "Usar-Aplicar" -l "Recordar" \
  -n 5 -p 10 \
  --title "Semana 11 - Comprension" \
  --balanceo --json --fail-under 0.7 \
  -o semana11-comprension.tex
```

### Reporte de balance (`--balanceo`)

`--balanceo` (o `--balanceo-csv PATH`) computa una matriz taxonomia x
concepto sobre la seleccion ensamblada:

- Sin `--json`: imprime la tabla a **stderr** (el `.tex` sigue yendo a
  stdout/`--output` sin contaminarse).
- Con `--json`: emite `{matrix, concept_coverage, warnings}` como **el unico**
  objeto JSON en stdout — el cuerpo `.tex` deja de imprimirse ahi (usar
  `--output` para capturarlo tambien).
- `--balanceo-csv PATH` escribe el mismo reporte como CSV en `PATH`
  (cualquiera de las dos flags dispara el computo).
- `--fail-under FLOAT` exige `--balanceo`/`--balanceo-csv` y sale con
  **exit 2** si `concept_coverage.distinct_covered/total_concepts` cae bajo
  el umbral. `total_concepts` esta acotado al pool de ejercicios pasado a
  `select_exercises`, no a toda la DB.

```bash
# Solo tabla de balance a stderr, .tex a stdout
workflow exercise build-exam -l "Recordar" -n 10 -p 5 -o examen.tex --balanceo

# Reporte CSV + exigir 70% de cobertura de conceptos
workflow exercise build-exam -l "Recordar" -n 10 -p 5 -o examen.tex \
  --balanceo-csv reporte.csv --fail-under 0.7
```

Luego exportar a Moodle con `workflow exercise export-moodle` (ver
[Exercise Workflow](Exercise-Workflow.md#exportar-a-moodle-xml)) y validar el
resultado con `workflow exam validate`.

---

## Arquitectura

- `src/workflow/exam/` — CLI + engine dual-mode (`weekly.py` para el modo
  semanal, incluyendo `tema_label_for_practica`).
- `src/workflow/exercise/balance.py` — reporte de balance, aditivo sobre
  `ExamDocument` (no lo modifica).
- Ver [Exercise Workflow](Exercise-Workflow.md) para el ciclo de vida completo
  del banco de ejercicios que alimenta `build-exam`.
