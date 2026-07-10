---
id: 
parent: Wiki
title: Knowledge Graph
aliases: []
type: permanent
created: 
tags: []
concepts: []
references: []
exercises: []
images: []
---

# Knowledge Graph

El grafo de conocimiento consulta el GlobalBase unificado (ITEP-0011) para visualizar y analizar las conexiones entre notas, ejercicios, bibliografia y cursos.

## Fuentes de datos

Desde ITEP-0011 (vault unificado) **todas** las notas, citas, etiquetas y conceptos viven en el **GlobalBase** (`workflow.db`) — no hay una DB local por proyecto para este layer. `slipbox.db` por proyecto sigue existiendo pero solo para `ProjectNote`/`PrismaDecision`, que el grafo no consulta.

| Fuente | Base de datos | Tipo de nodo | Tipo de arista |
|--------|--------------|-------------|----------------|
| Notas | GlobalBase (workflow.db) | `note` | `link` (nota → nota via Label) |
| Citas | GlobalBase (workflow.db) | — | `citation` (nota → bib_entry) |
| Relaciones de notas | GlobalBase (workflow.db) | — | `note_edge:structural`, `note_edge:associative` |
| Ejercicios | GlobalBase (workflow.db) | `exercise` | `exercise_content`, `exercise_book` |
| Contenidos | GlobalBase (workflow.db) | `content`, `topic` | `bib_content`, `course_content` |
| Bibliografia | GlobalBase (workflow.db) | `bib_entry` | — |
| Cursos | GlobalBase (workflow.db) | `course` | — |

Las aristas `note_edge:structural` y `note_edge:associative` provienen de la tabla `note_edge` (ITEP-0013). El campo `GraphEdge.label` contiene el `relation_type` de la arista (ej. `"refines"`, `"see_also"`). Solo se incluyen aristas con `target_id` resuelto; para resolver referencias pendientes usar `workflow notes edges resolve`. Los comandos `graph stats`, `graph export-dot` y `graph export-tikz` incorporan estas aristas automaticamente sin flag adicional.

Cada nodo `note` ahora carga sus `tags` reales (M2M `NoteTag`) y su `main_topic` (FK `Note.main_topic_id`) — propagacion real batch, sin N+1 (F5, freeze-window plan). Estos atributos alimentan los filtros `--include-tags`/`--exclude-tags`/`--color-by tag|main_topic` de `export-tikz` (ver abajo).

## Filtros de taxonomia (Phase 4E)

`stats`, `orphans`, `export-dot`, `export-tikz`, `clusters` y `neighbors` aceptan los mismos tres flags para restringir el grafo antes de analizarlo:

```bash
workflow graph stats --topic SLUG_OR_ID
workflow graph stats --discipline-area SLUG_OR_ID
workflow graph stats --main-topic SLUG_OR_ID
```

- `--topic` — restringe a nodos bajo ese `Topic`.
- `--discipline-area` — restringe a nodos bajo esa `DisciplineArea`.
- `--main-topic` — restringe a nodos alcanzables desde ese `MainTopic`.

Los tres aceptan slug o id numerico. Combinables con los demas flags de cada comando (`--project`, `--type`, `--json`, etc).

## Comandos

### stats — Resumen del grafo

```bash
workflow graph stats --project /ruta/al/proyecto/
```

```
Nodes: 127
Edges: 234
Orphans: 8
Components: 3

Nodes by type:
  note: 45
  exercise: 52
  bib_entry: 18
  content: 8
  topic: 3
  course: 1

Edges by type:
  link: 89
  citation: 67
  exercise_content: 42
  exercise_book: 26
  bib_content: 8
  course_content: 2
  note_edge:structural: 14
  note_edge:associative: 31
```

### orphans — Nodos sin conexiones

```bash
# Todos los huerfanos
workflow graph orphans --project .

# Solo notas huerfanas
workflow graph orphans --type note --project .

# Solo ejercicios huerfanos
workflow graph orphans --type exercise --project .
```

Nodos huerfanos son aquellos sin ninguna arista (ni entrante ni saliente). Indica contenido aislado que deberia conectarse. `orphans` tambien reporta **lineage roots**: notas sin aristas estructurales entrantes (no tienen "padre" en el grafo de relaciones ITEP-0013), aunque si tengan otras conexiones.

### neighbors — Vecindad de un nodo

```bash
# Vecinos directos
workflow graph neighbors note:42 --project .

# Hasta 2 saltos de distancia
workflow graph neighbors exercise:phys-gauss-001 --depth 2 --project .
```

Muestra el subgrafo alrededor de un nodo especifico. Util para entender el contexto de una nota o ejercicio.

### clusters — Agrupaciones tematicas

```bash
workflow graph clusters --project .
```

Requiere `networkx` (`pip install networkx`). Usa deteccion de comunidades (Louvain/greedy modularity) para agrupar nodos por conectividad.

```
Cluster 1 (12 nodes):
  [note] cinematica-intro.tex
  [note] cinematica-vectores.tex
  [exercise] phys-cinematica-001
  [bib_entry] serway2019
  ...

Cluster 2 (8 nodes):
  [note] dinamica-newton.tex
  ...
```

### export-dot — Exportar a Graphviz

```bash
# A stdout
workflow graph export-dot --project .

# A archivo
workflow graph export-dot --project . -o grafo.dot --highlight-orphans

# Renderizar con Graphviz
dot -Tpdf grafo.dot -o grafo.pdf
dot -Tsvg grafo.dot -o grafo.svg
neato -Tpdf grafo.dot -o grafo.pdf    # layout alternativo
```

Los nodos se colorean por tipo:
- Notas: azul (#4A90D9)
- Ejercicios: rojo (#E74C3C)
- Bibliografia: verde (#2ECC71)
- Contenidos: naranja (#F39C12)
- Temas: purpura (#9B59B6)
- Cursos: turquesa (#1ABC9C)

Con `--highlight-orphans`, los nodos huerfanos reciben borde rojo.

### export-tikz — Exportar a TikZ

```bash
# Documento standalone (compilable directamente)
workflow graph export-tikz --project . -o grafo.tex --standalone

# Solo el tikzpicture (para incluir en otro documento)
workflow graph export-tikz --project . -o grafo.tex --no-standalone
```

Usa un layout force-directed (Fruchterman-Reingold) por default. Para grafos grandes (>500 nodos) emite una advertencia.

```bash
# Compilar el TikZ standalone
pdflatex grafo.tex
```

#### Filtros por tags, color y layout (F5)

```bash
# Solo nodos con al menos uno de estos tags reales (via NoteTag, case-insensitive)
workflow graph export-tikz --project . --include-tags physics,electrostatics -o grafo.tex

# Excluir nodos con cualquiera de estos tags
workflow graph export-tikz --project . --exclude-tags borrador -o grafo.tex

# Colorear por MainTopic o Tag (hash SHA-1 → paleta estable) en vez de por tipo
workflow graph export-tikz --project . --color-by main_topic -o grafo.tex
workflow graph export-tikz --project . --color-by tag -o grafo.tex

# Layout alternativo y expansion por anillos BFS
workflow graph export-tikz --project . --layout radial --main-topic FS0121-electromagnetismo --depth 1 -o grafo.tex

# Restringir a una comunidad ya calculada por `graph clusters`
workflow graph export-tikz --project . --cluster "Cluster 2" -o grafo.tex
```

- `--include-tags`/`--exclude-tags` matchean contra filas `Tag` reales via `NoteTag` — **solo nodos de tipo `note` cargan tags**; nodos no-nota (exercise, bib_entry, etc.) quedan fuera de un filtro `--include-tags` **by design** (behavior change ratificado en F5: antes de la propagacion real, un substring accidental en labels colaba algunos nodos no-nota; ya no).
- `--color-by type|main_topic|tag` — `type` (default) usa colores por tipo de nodo (ver tabla de colores mas abajo); `main_topic`/`tag` mapean el valor real de `MainTopic`/`Tag` de cada nodo a un color estable via hash; nodos sin ese atributo caen al color default de su tipo.
- `--layout force|radial|hierarchical` — algoritmo de posicionamiento de nodos.
- `--depth N` — expande el conjunto de nodos filtrado por N anillos de vecinos (BFS), 0 = coincidencia exacta del filtro.
- `--cluster NAME` — restringe a una comunidad precomputada de `graph clusters` (numero 1-based o `"Cluster N"`); mutuamente exclusivo con `--main-topic`.

### resume / trace — Lineage a lo largo de aristas estructurales (ITEP-0013)

```bash
# Descendientes: notas que continuan desde esta (BFS hacia adelante)
workflow graph resume VTr3k8pLmnQ4 --max-depth 5 --node-budget 30

# Ancestros: lineage hacia las raices (BFS hacia atras)
workflow graph trace VTr3k8pLmnQ4 --json
```

Ambos recorren solo aristas `structural` (nunca `associative`) de la tabla `NoteEdge`. `--max-depth` limita la profundidad BFS (default 10); `--node-budget` detiene el recorrido tras recolectar ese numero de nodos (default 50) — util para evitar explosion combinatoria en grafos densos. Sin `--project`/filtros de taxonomia: operan directamente sobre `zettel_id`, sobre todo el GlobalBase.

---

## Interpretacion del grafo

### Patrones saludables

- **Pocos huerfanos**: La mayoria de notas y ejercicios estan conectados
- **Componentes conectados grandes**: El conocimiento forma una red coherente
- **Clusters tematicos claros**: Los temas se agrupan naturalmente

### Senales de alerta

- **Muchos huerfanos**: Contenido escrito pero no referenciado
- **Componentes aislados**: Islas de conocimiento sin puente
- **Nodo hub con demasiadas conexiones**: Posible nota demasiado generica

### Acciones sugeridas

| Problema | Accion |
|----------|--------|
| Nota huerfana | Agregar `\ref{}` o `\cite{}` desde otra nota |
| Ejercicio huerfano | Agregar `content_id` en metadatos YAML |
| Cluster aislado | Crear nota puente que conecte temas |
| Bibliografia sin citas | Agregar `\cite{}` en notas relevantes |

---

## Arquitectura

- **domain.py** — `GraphNode`, `GraphEdge`, `KnowledgeGraph` (frozen dataclasses)
- **collectors.py** — Consultas a ambas DBs, retorna tipos de dominio
- **analysis.py** — Algoritmos puros (BFS, grado, componentes) sin dependencias externas
- **dot_export.py** — Generacion DOT (Graphviz)
- **tikz_export.py** — Generacion TikZ con layout spring (Fruchterman-Reingold)
- **clustering.py** — Deteccion de comunidades (networkx opcional)

## ADRs relacionados

- [ADR-0017](../ADR/0017-graph-neighbors-json-contract.md) — Contrato JSON de `graph neighbors`
- [ITEP-0011](../ADR/ITEP-0011-vault-unification.md) — Vault unificado: GlobalBase como unica fuente de notas
- [ITEP-0013](../ADR/ITEP-0013-note-relation-graph.md) — `NoteEdge`, `graph resume`/`trace`, lineage roots en `orphans`
- [Zettelkasten Notes](Zettelkasten-Notes.md) — `notes link --concept/--main-topic/--relation`, `notes edges` (fuente de las aristas y el `main_topic`/tags que colorea el grafo)
