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

# Zettelkasten Notes

El sistema de notas Zettelkasten permite gestionar conocimiento en Markdown (Obsidian-compatible) con enlaces cruzados, tipos de nota, y conversion bidireccional a LaTeX.

## Conceptos clave

### Vault unificado (ITEP-0011)

Todas las notas viven en el vault global bajo `WORKFLOW_VAULT_ROOT` (default `~/01-U/0000AA-Vault/`):

```
<vault_root>/
├── notes/
│   ├── permanent/      ← notas permanentes
│   ├── literature/     ← notas de literatura
│   └── fleeting/       ← notas efimeras
└── .vault_pointer      ← marcador de vault unificado
```

La base de datos global (`WORKFLOW_DATA_DIR/workflow.db`) indexa todas las notas.  
Los proyectos legacy con `slipbox.db` propios se migran via `workflow vault unify`.

### Tipos de nota

| Tipo | Proposito | Ejemplo |
|------|-----------|---------|
| **permanent** | Ideas propias, conceptos consolidados | `20260326-gauss-law.md` |
| **literature** | Notas sobre lecturas y articulos | `lit-serway2019.md` |
| **fleeting** | Ideas rapidas, pendientes de procesar | `fleeting-campo-electrico.md` |

### Identificadores de nota (ITEP-0015)

El `zettel_id` es un **NanoID** con las siguientes reglas:

- Regex: `^[A-Za-z0-9_-]{8,21}$`, longitud default 12.
- Libreria PyPI: `nanoid`.
- **Nombre de archivo**: `<zettel_id>-<slug>.md` (compatible con Obsidian).
- `workflow notes new` auto-popula `aliases: [<id>-<slug>, <slug>, <id>]`.
- Resolucion de wikilinks: `zettel_id` → `alias` → `reference` (legacy).

Ejemplo de nombre de archivo: `VTr3k8pLmnQ4-gauss-law.md`.

### Formato de nota

```markdown
---
id: VTr3k8pLmnQ4
title: "Ley de Gauss"
type: permanent
created: 2026-03-26
tags: [physics, electrostatics]
concepts: []
aliases: [VTr3k8pLmnQ4-gauss-law, gauss-law, VTr3k8pLmnQ4]
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
  0000AA-Vault/                      # Zona de triage global
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

## workflow notes sync — Sincronizar vault con la DB

`workflow notes sync` escanea todos los archivos `.md` del vault y actualiza las tablas `Note`, `Label` y `Link` en la DB global. Implementa el principio **file-as-truth, DB-as-index** (ADR-0001).

### Uso

```bash
# Sincronizar todo el vault
workflow notes sync

# Ver qué cambiaria sin escribir nada
workflow notes sync --dry-run

# Restringir a un subdirectorio del vault
workflow notes sync --project 0001AA-proj1
```

### Qué hace

1. **Descubre** todos los `.md` bajo `WORKFLOW_VAULT_ROOT` (o el subdir del `--project`)
2. **Parsea** el frontmatter YAML de cada archivo:
   - `id:` → identificador único de la nota / zettel_id (requerido)
   - `title:`, `type:` → metadatos de la nota
   - `anchors:` → lista de anclas de sección → filas `Label` en la DB
   - `references:` → lista de bibkeys → filas `Citation` en la DB (ej: `[serway2019, griffiths2017]`)
   - `relations:` → lista de relaciones entre notas → filas `NoteEdge` en la DB (ver sección siguiente)
3. **Upserta** filas `Note` (por `zettel_id`) y `Label` (una sintética `__note__` por nota + las de `anchors:`)
4. **Registra citas**: procesa `references:` → filas `Citation` vinculadas a la nota
5. **Parsea wikilinks** del cuerpo: `[[ref]]`, `[[ref#anchor]]`, `[[ref|texto]]`, `[[ref#anchor|texto]]` → filas `Link`
6. **Registra relaciones** (Pass 4): procesa `relations:` → llama `upsert_note_edge()` (idempotente) → filas `NoteEdge`
7. **Limpia huerfanos**: elimina filas `Link` cuyo archivo fuente ya no existe en disco
8. Reporta: `N notes scanned, M labels registered, K links created, C citations registered, J orphans dropped, E edges created`

### Cuándo ejecutar

```
Despues de:
- Crear o editar notas .md
- Cambiar frontmatter (anchors, reference, title)
- Agregar wiki-links [[...]] en el cuerpo
- Mover o renombrar archivos

Antes de:
- workflow graph stats / export-dot  (usa las filas Link)
- workflow validate notes            (usa filas Note)
```

### Seguridad

- Las anclas de frontmatter se validan con `^[A-Za-z0-9._:-]+$` — se rechazan valores como `../../etc/passwd`
- `--project` valida que el subdirectorio esté contenido dentro del vault
- Los symlinks que apunten fuera del vault son ignorados

---

## Relaciones entre notas (ITEP-0013)

### Bloque `relations:` en frontmatter

Las notas pueden declarar relaciones tipadas hacia otras notas mediante un bloque `relations:` en su frontmatter YAML:

```yaml
---
id: VTr3k8pLmnQ4
title: ...
relations:
  - target: Ab9Xk2mPqR7w      # NanoID del destino, ^[A-Za-z0-9_-]{8,21}$
    class: structural          # o associative
    type: refines              # continuation | refines | branches | synthesis | rebuttal | supports | contradicts | expands | see_also
    weight: 1.0                # opcional, default 1.0; valores no-finitos → 1.0
    rationale: optional one-line text
---
```

`workflow notes sync` parsea este bloque en Pass 4 y persiste cada entrada como una fila `NoteEdge` (tabla `note_edge`, migración `0007_add_note_edges`). La operacion es idempotente (insert-or-skip).

Clases de arista:

| `class` | Uso |
|---------|-----|
| `structural` | Dependencia conceptual directa; participa en la deteccion de ciclos DAG |
| `associative` | Enlace tematico libre; no participa en ciclos |

### workflow notes edges — Consulta y mantenimiento

```bash
# Listar aristas (filtros opcionales)
workflow notes edges list [--source ZETTEL_ID] [--edge-class structural|associative] [--relation-type TYPE] [--json]

# Mostrar detalle de una arista
workflow notes edges show EDGE_ID [--json]

# Verificar ciclos en el subgrafo estructural (exit 1 si hay ciclos)
workflow notes edges check [--json]

# Resolver target_zettel_id → FK target_id (ejecutar despues de sync)
workflow notes edges resolve [--dry-run] [--json]
```

Todos los comandos aceptan `--json`. `edges check` sale con codigo 1 si detecta ciclos en el subgrafo `structural`.

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

## Creacion de notas (fleeting / permanent / literature)

**Decision de diseno:** Ni el CLI `workflow notes` ni el plugin `nvim-plugin/workflow` exponen un comando para *crear* notas nuevas. Esto es intencional, no un bug.

### Responsabilidades

| Herramienta | Crea notas | Rol |
|-------------|-----------|-----|
| `obsidian.nvim` (externo) | SI | Creacion de notas fleeting/permanent/literature en `0000AA-Vault/inbox/` o raiz del vault. Usa `:ObsidianNew`. |
| `workflow notes init` | NO | Scaffold del workspace y plantillas (`templates/fleeting.md`, `permanent.md`, `literature.md`). |
| `nvim-plugin/workflow` | NO | **Complementa** obsidian.nvim: sync DB, validacion frontmatter, promote fleeting→permanent, pickers. |

### Keymaps disponibles en `nvim-plugin/workflow`

Prefijo configurable (default `<leader>w`):

| Keymap | Accion | Funcion |
|--------|--------|---------|
| `<prefix>s` | Sync DB | `workflow.sync_current()` |
| `<prefix>v` | Validar frontmatter | `workflow.validate_frontmatter()` |
| `<prefix>p` | Promote fleeting→permanent | `workflow.promote_note()` — mueve de `inbox/` a raiz del vault y cambia `type:` |
| `<prefix>te/ti/tc` | Pickers Snacks (evaluations/items/courses) | |
| `<prefix>tb/tk/tr` | Pickers PRISMA (bib/keywords/reviews) | |

### Flujo recomendado para crear una fleeting

1. `:ObsidianNew fleeting-<tema>` — obsidian.nvim aplica plantilla y abre buffer en `0000AA-Vault/inbox/`
2. Escribir la idea
3. `<prefix>v` — validar frontmatter contra `workflow.validation`
4. Cuando este madura: `<prefix>p` — mueve a raiz del vault + cambia `type: permanent`
5. `<prefix>s` — indexa en `slipbox.db`

### Por que no un `workflow notes new`?

- **Separacion de responsabilidades:** obsidian.nvim ya resuelve creacion con plantillas, autocompletado de wiki-links y UI. Duplicarlo seria trabajo redundante.
- **WorkFlow se enfoca en el pipeline DB/LaTeX/exercises** — lo que obsidian.nvim no hace.
- Si no usas obsidian.nvim, las plantillas en `0000AA-Vault/templates/` son copiables manualmente con cualquier editor.

Si en el futuro se requiere independencia de obsidian.nvim, se podria agregar `workflow notes new --type fleeting <titulo>` que renderice la plantilla con `id` generado + timestamp. Ver backlog.

---

## Flujo de trabajo diario

```
1. Idea rapida          →  :ObsidianNew fleeting-* en 0000AA-Vault/inbox/
2. Procesar fleeting    →  <prefix>p: promote a raiz del vault, type → permanent
3. Leer un articulo     →  Crear nota literature con bibkey
4. Escribir/editar      →  Agregar wiki-links [[id]] a otras notas
5. Registrar en DB      →  workflow notes sync          (para notas .md del vault)
                           workflow lectures scan/link   (para notas .tex de cursos)
6. Construir grafo      →  workflow graph stats --project proyecto/
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

- [ADR-0001](../ADR/0001-Zettelkasten-system.md) — Capa semantica: file-as-truth, DB-as-index (`notes sync`)
- [ADR-0002](../ADR/0002-Unified-knowledge.md) — Markdown como capa canonica
- [ADR-0014](../ADR/0014-zettelkasten-implementation.md) — Implementacion: macros, modelo, workspace init
- [LZK-0000](../ADR/LZK-0000-zettelkasten-engine-architecture.md) — Arquitectura del motor
- [LZK-0002](../ADR/LZK-0002-pandoc-conversion-pipeline.md) — Pipeline Pandoc
- [LZK-0003](../ADR/LZK-0003-note-reference-system.md) — Sistema de referencias
- [ITEP-0013](../ADR/ITEP-0013-note-relation-graph.md) — Grafo de relaciones: NoteEdge model, `relations:` frontmatter, `notes edges` CLI (Implemented)
- [ITEP-0015](../ADR/ITEP-0015-editor-first-authoring.md) — NanoID como zettel_id; filename `<id>-<slug>.md`; LSP rechazado (Proposed)
