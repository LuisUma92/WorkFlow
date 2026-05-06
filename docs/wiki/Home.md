# WorkFlow Wiki

WorkFlow es un toolkit CLI en Python para gestionar proyectos LaTeX y un sistema unificado de Zettelkasten para escritura academica. Integra notas, ejercicios, diagramas TikZ, exportacion a Moodle y un grafo de conocimiento.

## Guias

| Guia | Descripcion |
|------|-------------|
| [Getting Started](Getting-Started.md) | Instalacion, primer proyecto, primeras notas |
| [Zettelkasten Notes](Zettelkasten-Notes.md) | Vault unificado (ITEP-0011), tipos de nota, wiki-links, Pandoc. Creacion via obsidian.nvim; migracion de slipbox legacy via `workflow vault unify`. |
| [Exercise Workflow](Exercise-Workflow.md) | Crear, parsear, sincronizar y exportar ejercicios |
| [Lectures Workflow](Lectures-Workflow.md) | Escaneo de cursos, enlaces cruzados, evaluaciones |
| [Knowledge Graph](Knowledge-Graph.md) | Analisis de conexiones, exportacion DOT/TikZ |
| [LaTeX Macros](LaTeX-Macros.md) | Referencia de macros personalizados y normalizacion |
| [Evaluation CLI](Evaluation-CLI.md) | Plantillas de evaluacion, items taxonomicos, cursos |
| [PRISMA Review](PRISMA-Review.md) | Bibliografia, keywords, screening sistematico |
| [Architecture](Architecture.md) | Modulos, base de datos, patrones de diseno |

## Referencia rapida

```bash
# Comandos principales
workflow notes    init
workflow exercise parse|list|sync|gc|export-moodle|create|create-range|build-exam
workflow lectures scan|split|link|build-eval
workflow graph    orphans|stats|export-dot|export-tikz|clusters|neighbors
workflow tikz     build|list|clean
workflow validate notes|exercises [--strict-main-topic]
workflow vault    info|validate|unify  # ITEP-0011 vault unification

# Base de datos global, migraciones y taxonomia (ITEP-0008 / ITEP-0009 / ITEP-0010)
workflow db migrate           [--base global|local|all] [--to REV] [--dry-run] [--json]
workflow db migrate status    [--base global|local|all] [--json]
workflow db import-codes      [--csv PATH | --all] [--data-dir PATH]
workflow db disciplines list  [--json] [--data-dir PATH]
workflow project propose-maturation [--json] [--area DDTTAA]

# Evaluaciones y PRISMA
workflow evaluations list|show|add|edit
workflow item         list|add|taxonomy
workflow course       list|add
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

## Decisiones de arquitectura

Todas las decisiones estan documentadas en [docs/ADR/INDEX.md](../ADR/INDEX.md):

- **ITEP-0000..0007** — Estructura de proyectos, esquema de DB, taxonomia Bloom
- **ITEP-0008** — Nomenclatura `DDTTAA-YYPP-title` (area + proyecto), `MainTopic.parent_id`, `DisciplineArea` (Implemented)
- **ITEP-0009** — Ciclo de vida del conocimiento Zettelkasten → ITeP, taxonomia 00–09, primitivas de maturation, `candidate_project` frontmatter (Implemented partial; Parte III en `~/Documents/01-U/.claude/`)
- **ITEP-0010** — Versionado de esquema + migraciones forward-only (`schema_version`, runner `workflow db migrate`, `@with_schema_guard`); FK `MainTopic.discipline_area_id → DisciplineArea.id` (Accepted)
- **ITEP-0011** — Vault unificado: tablas de notas (`note`, `citation`, `label`, `link`, `tag`, `note_tag`, `concept`, `note_concept`) viven en GlobalBase; archivos `.md` bajo `<vault_root>/notes/{permanent,literature,fleeting}`. CLI `workflow vault {info,validate,unify}`; FK real `note.main_topic_id → main_topic.id` (Phase B). Accepted (P0–P3 shipped)
- **STY-0000..0011** — Archivos de estilo LaTeX (macros, formatos, colores)
- **0001..0016** — Sistema Zettelkasten, ejercicios, exportacion Moodle, grafo, evaluaciones
- **PRISMA-0000..0005** — Revision sistematica, modelo de datos, CLI SQLAlchemy

## Enlaces

- [README.md](../../README.md) — Documentacion principal del proyecto
- [CLAUDE.md](../../CLAUDE.md) — Guia para agentes de codigo
- [ADR Index](../ADR/INDEX.md) — Indice de decisiones de arquitectura
