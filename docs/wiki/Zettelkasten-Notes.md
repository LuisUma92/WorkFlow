# Zettelkasten Notes

El sistema de notas Zettelkasten permite gestionar conocimiento en Markdown (Obsidian-compatible) con enlaces cruzados, tipos de nota, y conversion bidireccional a LaTeX.

## Conceptos clave

### Cada proyecto = un vault

Cada directorio `MainTopic` (10MC-ClassicalMechanics, 40EM-Electromagnetism, etc.) funciona como:
- Un **GeneralProject** de ITeP (salida LaTeX: papers, compilaciones)
- Un **vault Zettelkasten** (notas Markdown que alimentan los documentos)

Las notas viven en `{proyecto}/notes/` y se registran en `{proyecto}/slipbox.db`.

### Tipos de nota

| Tipo | Proposito | Ejemplo |
|------|-----------|---------|
| **permanent** | Ideas propias, conceptos consolidados | `20260326-gauss-law.md` |
| **literature** | Notas sobre lecturas y articulos | `lit-serway2019.md` |
| **fleeting** | Ideas rapidas, pendientes de procesar | `fleeting-campo-electrico.md` |

### Formato de nota

```markdown
---
id: 20260326-gauss-law
title: "Ley de Gauss"
type: permanent
created: 2026-03-26
tags: [physics, electrostatics]
concepts: []
---

## Resumen

La ley de Gauss relaciona el flujo electrico con la carga encerrada.

## Ideas clave

- El flujo total depende solo de la carga encerrada: $\Phi = Q/\epsilon_0$
- Ver [[20260320-coulomb]] para la relacion con la ley de Coulomb
- Aplicacion en [[lit-serway2019]] capitulo 24

## Conexiones

- [[20260320-coulomb]] — Ley de Coulomb como caso particular
- [[20260401-maxwell-equations]] — Forma integral de las ecuaciones de Maxwell
```

### Referencias cruzadas

| Formato | Donde se usa | Ejemplo |
|---------|-------------|---------|
| `[[id]]` | Markdown (Obsidian) | `[[20260326-gauss-law]]` |
| `[[id\|texto]]` | Markdown con texto custom | `[[20260326-gauss-law\|Ley de Gauss]]` |
| `\zlink{id}` | LaTeX | `\zlink{20260326-gauss-law}` |
| `\excref{id}` | LaTeX (equivalente) | `\excref{20260326-gauss-law}` |

`\zlink` es un alias de `\excref` — son identicos. El pipeline Pandoc convierte `[[id]]` → `\zlink{id}` automaticamente.

---

## Inicializacion del workspace

```bash
workflow notes init ~/Documents/01-U/
```

Esto crea:

```
~/Documents/01-U/
  .workflow/config.yaml              # Marcador de workspace
  00ZZ-Vault/                        # Zona de triage global
    inbox/                           # Notas fugaces sin asignar a un proyecto
    templates/
      permanent.md                   # Template para notas permanentes
      literature.md                  # Template para notas de lectura
      fleeting.md                    # Template para notas fugaces
  10MC-ClassicalMechanics/
    notes/                           # Vault Obsidian del proyecto
    slipbox.db                       # Base de datos local de notas
  40EM-Electromagnetism/
    notes/
    slipbox.db
```

**Idempotente**: seguro de ejecutar multiples veces. Solo crea lo que falta.

**Directorios especiales** (`00AA-`, `00BB-`, `00EE-`, `00II-`, `00ZZ-`) se saltan — no son proyectos de notas.

---

## Modelo de nota en la DB

Cada nota registrada en `slipbox.db` tiene:

| Campo | Tipo | Descripcion |
|-------|------|-------------|
| `filename` | str | Nombre del archivo (unico) |
| `reference` | str | Referencia unica (unica) |
| `zettel_id` | str | ID estable Zettelkasten, ej: `20260326-gauss-law` (unico) |
| `title` | str | Titulo legible |
| `note_type` | str | `permanent`, `literature`, o `fleeting` |
| `source_format` | str | `md` o `tex` |
| `created` | datetime | Fecha de creacion |

Campos adicionales para el grafo:
- **Citation** — `\cite{bibkey}` encontrados en la nota
- **Label** — `\label{name}` definidos en la nota
- **Link** — enlaces a otras notas via `\ref{label}` o `[[wiki-link]]`
- **Tag** — etiquetas M2M

---

## Macros LaTeX para Zettelkasten

Definidos en `shared/latex/sty/SetZettelkasten.sty` ([ADR-0014](../ADR/0014-zettelkasten-implementation.md)):

### `\zlink{id}` — Referencia cruzada

```latex
Ver la derivacion en \zlink{20260326-gauss-law}.
```

Es un alias de `\excref{id}` de `texnote.cls`. Si `texnote.cls` no esta cargado, usa `\hyperlink` directamente.

### `\zlabel{id}` — Ancla ligera

```latex
\zlabel{20260326-gauss-law}
% Crea un hypertarget + label sin entorno visual
```

### `\begin{zettelnote}{id}{Titulo}` — Entorno de nota

```latex
\begin{zettelnote}{20260326-gauss-law}{Ley de Gauss}
  El flujo electrico total a traves de una superficie cerrada
  es proporcional a la carga encerrada.
\end{zettelnote}
```

Crea un hypertarget para `\zlink`, muestra el titulo como `\paragraph`, y anota el ID en el margen.

---

## Pipeline Pandoc (Markdown → LaTeX)

El pipeline en `shared/latex/pandoc/` convierte notas Markdown a LaTeX ([LZK-0002](../ADR/LZK-0002-pandoc-conversion-pipeline.md)):

```
nota.md → preprocess.py → pandoc → filter.lua → nota.tex
```

1. **preprocess.py** — Convierte `[[wiki-links]]` a `\excref{id}` (= `\zlink{id}`)
2. **pandoc** — Conversion Markdown → LaTeX con `defaults.yaml`
3. **filter.lua** — Maneja entornos de teoremas, definiciones, pruebas

### Conversion inversa

```
nota.tex → pandoc --from latex → post-proceso → nota.md
```

`\excref{id}` se convierte de vuelta a `[[id]]`.

---

## Notas de literatura

Las notas de tipo `literature` conectan lecturas con el Zettelkasten:

```markdown
---
id: lit-serway2019
title: "Physics for Scientists and Engineers — Serway"
type: literature
bibkey: serway2019
created: 2026-03-26
tags: [textbook, physics, mechanics]
---

## Ideas clave

- Enfoque basado en resolucion de problemas
- Capitulo 24: Ley de Gauss presentada con simetrias

## Notas por capitulo

### Cap. 24 — Ley de Gauss
- Flujo como integral de superficie → [[20260326-gauss-law]]
- Conductores en equilibrio → [[20260327-conductores-equilibrio]]

## Conexiones
- [[20260326-gauss-law]] — Derivacion detallada
- [[20260320-coulomb]] — Relacion inversa del cuadrado
```

El campo `bibkey: serway2019` conecta con `bib_entry.bibkey` en la DB global. PRISMAreview lee la misma tabla via su SharedDbRouter ([PRISMA-0001](../ADR/PRISMA-0001-dual-database-router.md)).

---

## Flujo de trabajo diario

```
1. Idea rapida          →  Crear nota fleeting en 00ZZ-Vault/inbox/
2. Procesar fleeting    →  Mover a proyecto (10MC/notes/), cambiar type a permanent
3. Leer un articulo     →  Crear nota literature con bibkey
4. Escribir/editar      →  Agregar wiki-links [[id]] a otras notas
5. Registrar en DB      →  workflow lectures scan proyecto/ --project-root proyecto/
6. Construir enlaces    →  workflow lectures link proyecto/ --project-root proyecto/
7. Compilar a LaTeX     →  Pipeline Pandoc (futuro: workflow notes convert)
8. Verificar grafo      →  workflow graph stats --project proyecto/
```

---

## Relacion con otros modulos

| Modulo | Conexion |
|--------|----------|
| `workflow.lecture` | `scan` y `link` registran notas .tex y .md en slipbox.db |
| `workflow.graph` | Visualiza el grafo de notas, citas y ejercicios |
| `workflow.exercise` | Ejercicios referencian conceptos via `concepts` en YAML |
| `workflow.validation` | Valida frontmatter YAML de notas (.md) |
| `latexzettel` | Motor Zettelkasten: servidor JSONL/RPC para Neovim ([LZK-0001](../ADR/LZK-0001-jsonl-rpc-server.md)) |
| PRISMAreview | Lee `bib_entry` para conectar notas de literatura |

## ADRs relacionados

- [ADR-0001](../ADR/0001-Zettelkasten-system.md) — Capa semantica de notas
- [ADR-0002](../ADR/0002-Unified-knowledge.md) — Markdown como capa canonica
- [ADR-0014](../ADR/0014-zettelkasten-implementation.md) — Implementacion: macros, modelo, workspace init
- [LZK-0000](../ADR/LZK-0000-zettelkasten-engine-architecture.md) — Arquitectura del motor
- [LZK-0002](../ADR/LZK-0002-pandoc-conversion-pipeline.md) — Pipeline Pandoc
- [LZK-0003](../ADR/LZK-0003-note-reference-system.md) — Sistema de referencias
