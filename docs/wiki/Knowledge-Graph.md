# Knowledge Graph

El grafo de conocimiento unifica datos de ambas bases de datos (global + local) para visualizar y analizar las conexiones entre notas, ejercicios, bibliografia y cursos.

## Fuentes de datos

| Fuente | Base de datos | Tipo de nodo | Tipo de arista |
|--------|--------------|-------------|----------------|
| Notas | Local (slipbox.db) | `note` | `link` (nota → nota via Label) |
| Citas | Local (slipbox.db) | — | `citation` (nota → bib_entry) |
| Ejercicios | Global (workflow.db) | `exercise` | `exercise_content`, `exercise_book` |
| Contenidos | Global (workflow.db) | `content`, `topic` | `bib_content`, `course_content` |
| Bibliografia | Global (workflow.db) | `bib_entry` | — |
| Cursos | Global (workflow.db) | `course` | — |

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

Nodos huerfanos son aquellos sin ninguna arista (ni entrante ni saliente). Indica contenido aislado que deberia conectarse.

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

Usa un layout force-directed (Fruchterman-Reingold) implementado en Python puro. Para grafos grandes (>500 nodos) emite una advertencia.

```bash
# Compilar el TikZ standalone
pdflatex grafo.tex
```

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
