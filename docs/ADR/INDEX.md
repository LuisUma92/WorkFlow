# Architecture Decision Records — WorkFlow

WorkFlow integrates three systems into a unified academic toolkit:

1. **ITeP** (Init TeX Project) — Project scaffolding, academic DB schema, institutional profiles
2. **LaTeX Style Files** — Custom macros for exercises, physics, formatting, and evaluation
3. **Zettelkasten Workflow** — Note management, exercise parsing, Moodle export, knowledge graph

This index organizes all ADRs by concern, showing cross-system dependencies.

---

## Foundation: Project Structure & Database

These decisions establish the physical and logical organization of projects.

| ADR | Title | Domain | Status | Depends On |
|-----|-------|--------|--------|------------|
| [ITEP-0000](ITEP-0000-project-structure.md) | ITeP project structure conventions | ITeP | Accepted | — |
| [ITEP-0004](ITEP-0004-two-project-types.md) | Two project types: Lecture & General | ITeP | Accepted | ITEP-0000 |
| [ITEP-0005](ITEP-0005-symlink-based-config.md) | Symlink-based shared resource distribution | ITeP | Accepted | ITEP-0000 |
| [ITEP-0003](ITEP-0003-config-yaml-as-db-pointer.md) | config.yaml as minimal DB pointer | ITeP | Accepted | ITEP-0001 |
| [0008](0008-xdg-directory-layout.md) | XDG directory layout | Zettelkasten | Accepted | — |

## Foundation: Database & ORM

| ADR | Title | Domain | Status | Depends On |
|-----|-------|--------|--------|------------|
| [ITEP-0001](ITEP-0001-sqlalchemy-persistence.md) | SQLAlchemy as persistence layer | ITeP | Accepted | — |
| [ITEP-0002](ITEP-0002-four-layer-schema.md) | Four-layer database schema | ITeP | Accepted | ITEP-0001 |
| [ITEP-0006](ITEP-0006-taxonomy-enums.md) | Bloom taxonomy enums | ITeP | Accepted | ITEP-0002 |
| [ITEP-0007](ITEP-0007-crud-manager-layer.md) | CRUD manager abstraction | ITeP | Accepted | ITEP-0001 |
| [0003](0003-hybrid-database.md) | Hybrid database (global + local) | Zettelkasten | Accepted | ITEP-0001 |
| [0004](0004-sqlalchemy-single-orm.md) | SQLAlchemy 2.0 as single ORM | Zettelkasten | Accepted | ITEP-0001 |
| [0007](0007-shared-db-module.md) | Shared DB module with repository API | Zettelkasten | Accepted | 0003, 0004 |

## LaTeX Style System

These ADRs document the custom LaTeX packages in `shared/sty/`.

| ADR | Title | File | Status |
|-----|-------|------|--------|
| [STY-0000](STY-0000-set-format.md) | SetFormat — Package loading & document setup | SetFormat.sty | Accepted |
| [STY-0001](STY-0001-set-loyaut.md) | SetLoyaut — Page geometry & environments | SetLoyaut.sty | Accepted |
| [STY-0002](STY-0002-set-commands.md) | SetCommands — Core macros (\question, \exa, \vc) | SetCommands.sty | Accepted |
| [STY-0003](STY-0003-partial-commands.md) | PartialCommands — Exam/exercise macros (\pts, \rightoption) | PartialCommands.sty | Accepted |
| [STY-0004](STY-0004-set-units.md) | SetUnits — SI unit formatting (siunitx) | SetUnits.sty | Accepted |
| [STY-0005](STY-0005-set-symbols.md) | SetSymbols — Physics symbols & vectors | SetSymbols.sty | Accepted |
| [STY-0006](STY-0006-colors.md) | Colors — Institution-specific color schemes | Colors*.sty | Accepted |
| [STY-0007](STY-0007-vector-pgf.md) | VectorPGF — TikZ 3D vector macros | VectorPGF.sty | Accepted |
| [STY-0008](STY-0008-set-profiles.md) | SetProfiles — Institutional metadata & PPI instructions | SetProfiles.sty | Accepted |
| [STY-0009](STY-0009-set-headers.md) | SetHeaders — Institution-specific headers/footers | SetHeaders.sty | Accepted |
| [STY-0010](STY-0010-centred-page.md) | CentredPage — Full-page title layout (l3keys) | SetCommands.sty | Accepted |
| [STY-0011](STY-0011-set-constant.md) | SetConstant — Physical constants & values | SetConstant.sty | Accepted |

## Knowledge Layer: Zettelkasten & Notes

| ADR | Title | Domain | Status | Depends On |
|-----|-------|--------|--------|------------|
| [0001](0001-Zettelkasten-system.md) | Zettelkasten note semantic layer | Zettelkasten | Accepted | — |
| [0002](0002-Unified-knowledge.md) | Markdown as canonical knowledge layer | Zettelkasten | Accepted | 0001 |

## Exercise System

These decisions define how exercises are authored, parsed, indexed, and exported.

| ADR | Title | Domain | Status | Depends On |
|-----|-------|--------|--------|------------|
| [0005](0005-exercise-dsl-extends-macros.md) | Exercise DSL extends existing macros | Zettelkasten | Accepted | STY-0002, STY-0003 |
| [0009](0009-exercise-module-boundary.md) | Exercise module boundary + shared LaTeX parsing | Zettelkasten | Accepted | 0005, 0007 |
| [0010](0010-exercise-persistence-model.md) | Exercise persistence: file as truth, DB as index | Zettelkasten | Accepted | 0007, 0009 |
| [0011](0011-latex-exercise-parser-strategy.md) | LaTeX parser: brace-counting extractor | Zettelkasten | Accepted | 0009 |
| [0012](0012-moodle-xml-export-mapping.md) | Moodle XML export with LaTeX normalization | Zettelkasten | Accepted | 0011, STY-0002, STY-0003 |

## LaTeXZettel: Note Management Engine

| ADR | Title | Domain | Status | Depends On |
|-----|-------|--------|--------|------------|
| [LZK-0000](LZK-0000-zettelkasten-engine-architecture.md) | 7-layer engine architecture (CLI → Server → API → Domain → Infra) | LaTeXZettel | Accepted | 0001, 0002, 0003 |
| [LZK-0001](LZK-0001-jsonl-rpc-server.md) | JSONL/NDJSON RPC server for Neovim (24 routes) | LaTeXZettel | Accepted | LZK-0000 |
| [LZK-0002](LZK-0002-pandoc-conversion-pipeline.md) | Pandoc pipeline: Markdown ↔ LaTeX with wiki-links | LaTeXZettel | Accepted | LZK-0000, 0002 |
| [LZK-0003](LZK-0003-note-reference-system.md) | Note reference system: IDs, regex patterns, cross-refs | LaTeXZettel | Accepted | LZK-0000, 0001 |
| [LZK-0004](LZK-0004-dependency-injection-db-shim.md) | Dependency injection and Peewee → SQLAlchemy shim | LaTeXZettel | Accepted | LZK-0000, 0004 |

## PRISMAreview: Systematic Literature Review

| ADR | Title | Domain | Status | Depends On |
|-----|-------|--------|--------|------------|
| [PRISMA-0000](PRISMA-0000-systematic-review-architecture.md) | Systematic review architecture (Django, dual-DB) | PRISMA | Accepted | 0003, 0007 |
| [PRISMA-0001](PRISMA-0001-dual-database-router.md) | Dual-database router: MariaDB + shared SQLite | PRISMA | Accepted | PRISMA-0000, 0003 |
| [PRISMA-0002](PRISMA-0002-bibliography-import-pipeline.md) | Bibliography import pipeline (BibTeX → structured data) | PRISMA | Accepted | PRISMA-0000 |
| [PRISMA-0003](PRISMA-0003-screening-review-workflow.md) | Article screening and review workflow | PRISMA | Accepted | PRISMA-0002 |
| [PRISMA-0004](PRISMA-0004-data-model-schema.md) | Data model: 30+ Django models for systematic review | PRISMA | Accepted | PRISMA-0000 |

## Asset Pipeline

| ADR | Title | Domain | Status | Depends On |
|-----|-------|--------|--------|------------|
| [0006](0006-tikz-asset-pipeline.md) | TikZ standalone asset pipeline | Zettelkasten | Accepted | STY-0007 |

## Cross-System Dependency Graph

```
ITEP-0000 (project structure)
    ├── ITEP-0004 (project types)
    ├── ITEP-0005 (symlinks)
    └── ITEP-0001 (SQLAlchemy)
         ├── ITEP-0002 (4-layer schema)
         │    └── ITEP-0006 (taxonomy enums)
         ├── ITEP-0003 (config.yaml pointer)
         ├── ITEP-0007 (CRUD manager)
         ├── 0003 (hybrid DB) ──→ 0007 (shared DB module)
         └── 0004 (single ORM) ─┘

STY-0000 (format/packages)
    ├── STY-0001 (geometry)
    ├── STY-0002 (commands) ──→ 0005 (exercise DSL) ──→ 0009 (module boundary)
    ├── STY-0003 (partials) ─┘                             ├── 0010 (persistence)
    ├── STY-0004 (units)                                    ├── 0011 (parser)
    ├── STY-0005 (symbols)                                  └── 0012 (Moodle export)
    ├── STY-0006 (colors)
    ├── STY-0007 (VectorPGF) ──→ 0006 (TikZ pipeline)
    └── STY-0008..0011 (profiles, headers, centred, constants)

0001 (Zettelkasten) ──→ 0002 (Markdown layer)
```

## Zettelkasten Implementation

| ADR | Title | Domain | Status | Depends On |
|-----|-------|--------|--------|------------|
| [0014](0014-zettelkasten-implementation.md) | Zettelkasten implementation: macros, note model, workspace init, Markdown pipeline | System | Proposed | 0001, 0002, 0003, 0007, ITEP-0000 |

## Maintenance & Consolidation

| ADR | Title | Domain | Status | Depends On |
|-----|-------|--------|--------|------------|
| [0013](0013-codebase-consolidation.md) | Codebase consolidation: sessions, decoupling, CLI split | System | Accepted | 0003, 0004, 0007, 0009 |

## Planning & Review Documents

| Document | Purpose |
|----------|---------|
| [PLAN-consolidated-architecture.md](PLAN-consolidated-architecture.md) | Full 7-phase implementation plan |
| [REVIEW-architectural-state.md](REVIEW-architectural-state.md) | Pre-Phase 0 codebase review |
| [0000-TEMPLATE.md](0000-TEMPLATE.md) | ADR template |
| [git-action.md](git-action.md) | CI/CD pipeline notes |
