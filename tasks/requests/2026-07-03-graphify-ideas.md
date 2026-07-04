---
id: 20260703-graph-evolution-strategy
title: Evolución del Knowledge Graph arquitectónico y pipeline incremental
type: enhancement
source_agent: user
opened_on: 2026-07-03

status: open
priority: P1
severity: recurring-friction

labels:
  - graph
  - docs
  - architecture
  - ci
  - knowledge-management

components:
  - workflow.graph
  - workflow.docs
  - workflow.db

adr_refs: []
related_requests: []
related_gaps: []
duplicates: []
blocked_by: []

assignee: unassigned
target_release:

implementation: []
closed_on:
closed_by:

acceptance_criteria:
  - Definir estrategia de mantenimiento incremental del grafo
  - Definir métricas arquitectónicas calculables sin LLM
  - Diseñar pipeline CI de bajo costo
  - Mantener sincronización entre ADRs y representación derivada
  - "Merge de scope: incorporar directorios nuevos a grafo existente preservando IDs (skill merge, no generate)"

verification: []
---

# Request: Evolución del Knowledge Graph arquitectónico y pipeline incremental

## Context

Actualmente existe un Knowledge Graph generado mediante un agente LLM especializado.

El análisis realizado hasta la fecha produjo:

- ~400 archivos analizados
- ~2969 nodos
- ~5084 relaciones
- ~287 comunidades

Sin embargo, el análisis NO cubre la totalidad del repositorio.

Directorios incluidos:

```text
src/
docs/
nvim-plugin/
```

Directorios excluidos o parcialmente excluidos:

```text
tests/
share/
```

Observaciones:

### tests/

Contiene más de mil pruebas automatizadas.

Actualmente no forma parte del grafo.

Esto implica que:

- dependencias ejercidas por los tests no aparecen
- cobertura arquitectónica real es parcialmente desconocida
- fan-in/fan-out observados pueden estar subestimados

### share/

Contiene recursos auxiliares:

- librerías LaTeX personalizadas
- imágenes reutilizables
- recursos compartidos
- plantillas

Actualmente no participa en el modelo.

## Arquitectura conceptual actual

El sistema NO utiliza el grafo como fuente canónica.

La jerarquía actual es:

```text
Código fuente
(src/, docs/, nvim-plugin/)
        │
        ▼
ADRs (fuente arquitectónica canónica)
        │
        ▼
Agente LLM + extracción
        │
        ▼
Knowledge Graph
        │
        ▼
Reportes / visualizaciones
```

Por diseño:

- El código es la fuente de verdad del comportamiento.
- Los ADR son la fuente de verdad arquitectónica.
- El grafo es un artefacto derivado.

No se desea convertir el grafo en una segunda fuente de verdad.

## Problema

Actualmente el proceso de generación del grafo consume una cantidad significativa de contexto LLM.

El objetivo es poder:

- mantener el grafo actualizado
- integrar validaciones arquitectónicas en CI
- evitar regeneraciones completas
- minimizar uso de tokens

## Proposal

Separar claramente:

### 1. Análisis estructural determinista

Realizado sin LLM.

Posibles tecnologías:

- AST Python
- Tree-sitter
- pydeps
- pyan
- networkx

Información extraíble sin IA:

- imports
- dependencias
- clases
- funciones
- llamadas
- ciclos
- fan-in
- fan-out
- componentes conectados
- centralidad
- comunidades

### 2. Enriquecimiento semántico

Realizado únicamente mediante LLM.

Reservado para relaciones imposibles de inferir sintácticamente:

Ejemplos:

- implementación de ADR
- patrones arquitectónicos
- bounded contexts
- responsabilidades semánticas
- relaciones conceptuales entre módulos

## Desired CI Strategy

Pipeline ligero en cada commit:

```text
git diff
    │
    ▼
Análisis estructural incremental
    │
    ▼
Métricas arquitectónicas
    │
    ▼
Validaciones
```

Sin uso de LLM.

Pipeline pesado únicamente:

- releases
- revisiones arquitectónicas
- regeneraciones completas
- cambios importantes de diseño

## Métricas deseadas

### Acoplamiento entre comunidades

Para cada comunidad:

```text
ratio =
aristas_externas /
aristas_internas
```

Objetivo:

- identificar módulos excesivamente dependientes
- detectar erosión arquitectónica

### Matriz de dependencias entre comunidades

Ejemplo:

```text
        A   B   C   D

A       -  12   3   1
B      12   -  29   7
C       3  29   -   0
D       1   7   0   -
```

Objetivo:

- visualizar acoplamiento global
- identificar hubs inesperados

### Fan-in por comunidad

Permite detectar:

- bibliotecas estables
- módulos reutilizados
- puntos de integración

### Fan-out por comunidad

Permite detectar:

- orquestadores
- componentes excesivamente dependientes

### Centralidad

Calcular:

- betweenness
- pagerank
- closeness
- eigenvector

Objetivo:

- detectar cuellos de botella arquitectónicos
- identificar componentes críticos

## Desired Future Architecture

Se desea evolucionar hacia:

```text
Código
    │
    ▼
Extractor estructural
    │
    ▼
Grafo estructural
    │
    ├── ADR
    ├── documentación
    └── metadatos
            │
            ▼
Knowledge Graph enriquecido
            │
            ▼
Métricas
            │
            ▼
Reportes
            │
            ▼
Visualizaciones
            │
            ▼
LLM
```

El LLM no debería construir el grafo completo.

El LLM debería enriquecer un grafo previamente generado de forma determinista.

## Long-Term Goal

Implementar actualización incremental:

```text
git diff
    │
    ▼
Archivos modificados
    │
    ▼
Regenerar únicamente
los nodos afectados
    │
    ▼
Invalidar comunidades relacionadas
    │
    ▼
Reanalizar semánticamente
solo las zonas impactadas
```

De esta forma el costo pasa de:

```text
O(tamaño del proyecto)
```

a

```text
O(tamaño del cambio)
```

permitiendo mantener el grafo actualizado de manera continua.

## Findings — 2026-07-03 (verificación en vivo)

1. **Capacidades YA existentes en el skill** (`~/.claude/skills/graphify/SKILL.md`):
   - `/graphify <path> --update` — modo incremental documentado: re-extrae solo archivos nuevos/cambiados (SKILL.md línea 20).
   - `graphify merge-graphs` — merge multi-grafo ya existe para el caso multi-repo (líneas 75, 94); cada nodo lleva atributo `repo`.
   - `graphify-out/manifest.json` YA es un índice incremental por archivo: `{path: {mtime, ast_hash, semantic_hash}}` (verificado en el manifest real). La propuesta del usuario `{path, sha256, last_graph_update}` es un refinamiento, no algo nuevo: `ast_hash`/`semantic_hash` ya cumplen el rol de sha256 (y mejor: invariantes a cambios cosméticos); el delta real es añadir `last_graph_update` y quizá etiquetas de activación por directorio.
   - Cache semántico por chunks en `graphify-out/cache/` con merge cached+new (líneas 399-472).
   - IDs de nodo son slugs deterministas derivados del path (ej. `src_main_py`) — preservar IDs en un merge es viable por construcción; no hay IDs aleatorios.
2. **Por qué tests/, share/, data/ quedaron fuera**: no hay exclusión hard-coded en el skill; el corpus se estrechó en el build original (gate de tamaño / narrowing interactivo). Incorporarlos = correr `--update` ampliando el scan root, no un rediseño.
3. **Herramientas propuestas — disponibilidad verificada (2026-07-03)**: networkx NO (ni uv env ni system python — es dep opcional de workflow.graph.clustering, no instalada), pydeps NO, pyan NO, tree_sitter (binding Python) NO; solo existe el binario CLI /usr/bin/tree-sitter. Cualquier extractor determinista propio requeriría `uv add` primero; alternativa sin deps: stdlib `ast` (ya usado por el propio pipeline AST del skill).
4. **Gap real destilado** (reformular el request hacia esto): el skill ya es incremental *dentro* de un scope fijo; lo que falta es (a) **merge de scope** — añadir directorios nuevos (tests/, share/, data/) a un grafo existente preservando IDs/comunidades en vez de regenerar; (b) `last_graph_update` + etiquetas por entrada en manifest para CI; (c) métricas deterministas (fan-in/out, acoplamiento entre comunidades, centralidad) calculables offline — bloqueado por networkx ausente.

## Questions For Future Agent

1. ¿Qué partes del grafo pueden derivarse completamente mediante AST? (parcialmente respondida — ver Findings)
2. ¿Cómo detectar comunidades arquitectónicas de forma reproducible?
3. ¿Qué algoritmo de community detection es más adecuado?
4. ¿Cómo medir estabilidad arquitectónica entre commits?
5. ¿Cómo comparar dos grafos consecutivos y producir un changelog arquitectónico?
6. ¿Cómo integrar estas métricas en CI sin usar LLM? (parcialmente respondida — ver Findings)
7. ¿Qué información semántica justifica realmente el uso de un LLM?
8. ¿Cómo incorporar eventualmente `tests/` y `share/` sin degradar la utilidad del grafo?

## Success Criteria

El proyecto se considerará exitoso cuando:

- el grafo pueda mantenerse automáticamente
- la mayoría de métricas se calculen sin LLM
- el costo de actualización dependa únicamente de los cambios realizados
- el CI detecte degradaciones arquitectónicas
- los ADR continúen siendo la fuente canónica de arquitectura
- el Knowledge Graph permanezca como representación derivada y enriquecida
