---
id: 
title: Wiki
nav_order: 2
has_children: true
aliases: []
type: permanent
created: 
tags: []
concepts: []
references: []
exercises: []
images: []
---

# WorkFlow Wiki

WorkFlow es un toolkit CLI en Python para gestionar proyectos LaTeX y un sistema unificado de Zettelkasten para escritura academica. Integra notas, ejercicios, diagramas TikZ, exportacion a Moodle y un grafo de conocimiento.

## Guias

### Empezar

| Guia | Descripcion |
|------|-------------|
| [Getting Started](Getting-Started.md) | Instalacion, los 18 grupos de comandos, primer proyecto, quickstart de notas |

### Notas & Zettelkasten

| Guia | Descripcion |
|------|-------------|
| [Zettelkasten Notes](Zettelkasten-Notes.md) | Vault unificado (ITEP-0011): `notes capture/new/create/promote/search/sync/link/tag`, frontmatter, relaciones `NoteEdge` (ITEP-0013) |
| [Fleeting Monolith Flow](Fleeting-Monolith-Flow.md) | Flujo de notas grandes de curso: `lectures split --sync` → `concept harvest` → `import` |
| [Concept Skyfolding](Concept-Skyfolding.md) | Ciclo de vida de conceptos: taxonomia slug-only (ITEP-0012), `concept harvest`, `import` YAML |
| [Knowledge Graph](Knowledge-Graph.md) | Analisis de conexiones: stats/orphans/export-dot/export-tikz/clusters/neighbors/resume/trace, filtros de taxonomia y tags |
| [Neovim Plugin](Neovim-Plugin.md) | Pickers y keymaps `<leader>z*`: captura, sync, promote, pickers de evaluations/concept/PRISMA |

### Docencia

| Guia | Descripcion |
|------|-------------|
| [Lectures Workflow](Lectures-Workflow.md) | Escaneo de cursos, enlaces cruzados, split de notas |
| [Exercise Workflow](Exercise-Workflow.md) | Crear, parsear, sincronizar y exportar ejercicios; balance de taxonomia |
| [Exam Workflow](Exam-Workflow.md) | Scaffolding de examenes Moodle XML (legacy + weekly) y `exam validate` |
| [Evaluation CLI](Evaluation-CLI.md) | Plantillas de evaluacion, items taxonomicos, cursos y practicas |
| [LaTeX Macros](LaTeX-Macros.md) | Referencia de macros personalizados y normalizacion |

### Investigacion

| Guia | Descripcion |
|------|-------------|
| [PRISMA Review](PRISMA-Review.md) | Bibliografia, keywords, screening sistematico, accept-to-note |

### Sistema

| Guia | Descripcion |
|------|-------------|
| [Architecture](Architecture.md) | Modulos, base de datos, patrones de diseno |

## Referencia rapida

```bash
# Notas Zettelkasten (vault unificado, ITEP-0011/0012/0013/0015)
workflow notes    init|new|capture|create|promote|search|list|show|tag|link|sync|new-id|enums
workflow notes edges  list | show | check | resolve  # ITEP-0013 nota relation graph
workflow vault    info|validate|unify  # ITEP-0011 vault unification
workflow concept  list|show|add|tree|rm|rename|harvest  # ITEP-0012 taxonomia slug-only
workflow import   <archivo.yaml>  # bulk DisciplineArea → Topic → Content → Concept
workflow topic    add|list|show
workflow content  add|list|show|link-bib|bib-links|unlink-bib

# Ejercicios y examenes
workflow exercise parse|list|sync|gc|export-moodle|create|create-range|build-exam|register|register-batch
workflow exam     scaffold-xml|validate  # legacy + weekly, Moodle XML lint
workflow lectures scan|split|link|build-eval

# Grafo de conocimiento
workflow graph    orphans|stats|export-dot|export-tikz|clusters|neighbors|resume|trace

# TikZ y validacion
workflow tikz     build|list|clean
workflow validate notes|exercises [--strict-main-topic] [--strict-concepts]

# Base de datos global, migraciones y taxonomia (ITEP-0008 / ITEP-0009 / ITEP-0010)
workflow db migrate           [--base global|local|all] [--to REV] [--dry-run] [--json]
workflow db migrate status    [--base global|local|all] [--json]
workflow db import-codes      [--csv PATH | --all] [--data-dir PATH]
workflow db disciplines list  [--json] [--data-dir PATH]
workflow project propose-maturation [--json] [--area DDTTAA]

# Evaluaciones y PRISMA
workflow evaluations list|show|add|edit
workflow item         list|add|taxonomy
workflow course       list|add|add-practice|practices
workflow prisma bib       list|show
workflow prisma keyword   list
workflow prisma review    list
workflow prisma checklist show
workflow prisma rationale add|list
workflow prisma tag       add|list

# Utilidades independientes
inittex [--force-no-maturation]   # Crear proyecto LaTeX (general usa DDTTAA-YYPP-title)
relink                             # Recrear symlinks
cleta                              # Limpiar archivos auxiliares TeX
```

## Vault layout (ITEP-0011)

El vault unificado vive bajo `WORKFLOW_VAULT_ROOT` (default `~/01-U/0000AV-Vault`):

```
<vault_root>/
├── notes/
│   ├── permanent/      ← notas permanentes (.md); destino default de `lectures split`
│   ├── literature/     ← notas de literatura (.md)
│   └── fleeting/       ← notas efimeras (.md)
└── .vault_pointer      ← marcador de proyecto unificado (escrito por `workflow vault unify`)
```

Bases de datos:
- **GlobalBase** (`~/.local/share/workflow/workflow.db` o `$WORKFLOW_DATA_DIR/workflow.db`) — notas, citas, etiquetas, conceptos, ejercicios, referencias.
- **LocalBase** (`<project>/slipbox.db`) — `ProjectNote` (ideas/hipotesis por proyecto, P5), `PrismaDecision` (PRISMA).

Env vars relevantes:
| Variable | Descripcion | Default |
|---|---|---|
| `WORKFLOW_VAULT_ROOT` | Raiz del vault unificado | `~/01-U/0000AV-Vault` |
| `WORKFLOW_DATA_DIR` | Directorio del GlobalBase | `~/01-U/workflow` |

## Decisiones de arquitectura

Todas las decisiones estan documentadas en [docs/ADR/INDEX.md](../ADR/INDEX.md):

- **ITEP-0000..0007** — Estructura de proyectos, esquema de DB, taxonomia Bloom
- **ITEP-0008** — Nomenclatura `DDTTAA-YYPP-title` (area + proyecto), `MainTopic.parent_id`, `DisciplineArea` (Implemented)
- **ITEP-0009** — Ciclo de vida del conocimiento Zettelkasten → ITeP, taxonomia 00–09, primitivas de maturation, `candidate_project` frontmatter (Implemented partial; Parte III en `~/Documents/01-U/.claude/`)
- **ITEP-0010** — Versionado de esquema + migraciones forward-only (`schema_version`, runner `workflow db migrate`, `@with_schema_guard`); FK `MainTopic.discipline_area_id → DisciplineArea.id` (Accepted)
- **ITEP-0011** — Vault unificado: tablas de notas (`note`, `citation`, `label`, `link`, `tag`, `note_tag`, `concept`, `note_concept`) viven en GlobalBase; archivos `.md` bajo `<vault_root>/notes/{permanent,literature,fleeting}`. CLI `workflow vault {info,validate,unify}`; FK real `note.main_topic_id → main_topic.id` (Phase B). **Implemented** (P0–P7 complete, 2026-05-22)
- **ITEP-0013** — Grafo de relaciones entre notas: modelo `NoteEdge` (GlobalBase, migration `0007`), frontmatter con 9 claves planas `derived_from_*`/`links_*` (LEGACY: `relations:` anidado, aun soportado por el parser), `workflow notes sync` Pass 4 (`edges_created`), CLI `workflow notes edges {list,show,check,resolve}`, `workflow notes migrate-relations`. **Implemented** (Phase 2 complete, tag `v1.5.0`, 2026-05-23; frontmatter aplanado 2026-07-09)
- **ITEP-0014** — fm_hash incremental sync. Proposed (deferred).
- **ITEP-0015** — Editor-first authoring tooling: NanoID `zettel_id` (`^[A-Za-z0-9_-]{8,21}$`), filename `<zettel_id>-<slug>.md`, aliases auto-set por `notes new`, wikilink resolution `zettel_id → alias → reference`. LSP rechazado; extiende LZK-0001 JSONL RPC. Proposed.
- **STY-0000..0011** — Archivos de estilo LaTeX (macros, formatos, colores)
- **0001..0016** — Sistema Zettelkasten, ejercicios, exportacion Moodle, grafo, evaluaciones
- **PRISMA-0000..0005** — Revision sistematica, modelo de datos, CLI SQLAlchemy

## Enlaces

- [README.md](../../README.md) — Documentacion principal del proyecto
- [CLAUDE.md](../../CLAUDE.md) — Guia para agentes de codigo
- [ADR Index](../ADR/INDEX.md) — Indice de decisiones de arquitectura
