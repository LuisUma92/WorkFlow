# WorkFlow Wiki

WorkFlow es un toolkit CLI en Python para gestionar proyectos LaTeX y un sistema unificado de Zettelkasten para escritura academica. Integra notas, ejercicios, diagramas TikZ, exportacion a Moodle y un grafo de conocimiento.

## Guias

| Guia | Descripcion |
|------|-------------|
| [Getting Started](Getting-Started.md) | Instalacion, primer proyecto, primeras notas |
| [Exercise Workflow](Exercise-Workflow.md) | Crear, parsear, sincronizar y exportar ejercicios |
| [Lectures Workflow](Lectures-Workflow.md) | Escaneo de cursos, enlaces cruzados, evaluaciones |
| [Knowledge Graph](Knowledge-Graph.md) | Analisis de conexiones, exportacion DOT/TikZ |
| [LaTeX Macros](LaTeX-Macros.md) | Referencia de macros personalizados y normalizacion |
| [Architecture](Architecture.md) | Modulos, base de datos, patrones de diseno |

## Referencia rapida

```bash
# Comandos principales
workflow exercise parse|list|sync|gc|export-moodle|create|create-range|build-exam
workflow lectures scan|split|link|build-eval
workflow graph    orphans|stats|export-dot|export-tikz|clusters|neighbors
workflow tikz     build|list|clean
workflow validate notes|exercises

# Utilidades independientes
inittex    # Crear proyecto LaTeX
relink     # Recrear symlinks
cleta      # Limpiar archivos auxiliares TeX
```

## Decisiones de arquitectura

Todas las decisiones estan documentadas en [docs/ADR/INDEX.md](../ADR/INDEX.md):

- **ITEP-0000..0007** — Estructura de proyectos, esquema de DB, taxonomia Bloom
- **STY-0000..0011** — Archivos de estilo LaTeX (macros, formatos, colores)
- **0001..0012** — Sistema Zettelkasten, ejercicios, exportacion Moodle, grafo

## Enlaces

- [README.md](../../README.md) — Documentacion principal del proyecto
- [CLAUDE.md](../../CLAUDE.md) — Guia para agentes de codigo
- [ADR Index](../ADR/INDEX.md) — Indice de decisiones de arquitectura
