# Architecture

Descripcion de la arquitectura del sistema WorkFlow, sus modulos, patrones y decisiones de diseno.

## Vista general

```
src/
  workflow/           # Core del sistema unificado
    db/               # Base de datos (SQLAlchemy 2.0)
    latex/            # Parsing compartido de LaTeX
    exercise/         # Banco de ejercicios
    lecture/          # Integracion de cursos
    graph/            # Grafo de conocimiento
    tikz/             # Pipeline de diagramas
    validation/       # Validacion de frontmatter
  itep/               # Scaffolding de proyectos LaTeX
  latexzettel/        # Motor Zettelkasten + servidor JSONL
  lectkit/            # Utilidades legado (cleta)
  PRISMAreview/       # App web Django (PRISMA)
  appfunc/            # Utilidades compartidas
shared/
  sty/                # 17 archivos de estilo LaTeX
  templates/          # Templates para notas, ejercicios, clases
```

## Base de datos hibrida ([ADR-0003](../ADR/0003-hybrid-database.md))

Dos bases de datos SQLite con propositos distintos:

```
~/.local/share/workflow/workflow.db     ← GlobalBase (datos de referencia)
<proyecto>/slipbox.db                   ← LocalBase (notas por proyecto)
```

### GlobalBase — workflow.db

Datos que trascienden proyectos individuales:

```
Capa 1: Referencia         institution, main_topic
Capa 2: Entidades maestras bib_entry, topic, content, bib_content
Capa 3: Templates          course, course_content, evaluation_template,
                           item, evaluation_item, exercise, exercise_option
Capa 4: Instancias         lecture_instance, general_project
```

Ver [ADR ITEP-0002](../ADR/ITEP-0002-four-layer-schema.md) para detalles del esquema.

### LocalBase — slipbox.db

Datos especificos de cada proyecto:

```
note         Archivo registrado con referencia unica
citation     Citas bibliograficas en notas (\cite{})
label        Etiquetas definidas en notas (\label{})
link         Enlaces entre notas (nota → label)
tag          Sistema de etiquetas M2M
note_tag     Tabla puente nota ↔ tag
```

### Acceso a datos

Todo el acceso pasa por interfaces Protocol ([ADR-0007](../ADR/0007-shared-db-module.md)):

```python
# Protocolos en workflow.db.repos.protocols
class ExerciseRepo(Protocol):
    def get_by_exercise_id(self, exercise_id: str) -> Exercise | None: ...
    def find_by_filters(self, *, tags=None, difficulty=None, ...) -> list[Exercise]: ...
    def upsert(self, exercise: Exercise) -> Exercise: ...

# Implementaciones en workflow.db.repos.sqlalchemy
class SqlExerciseRepo:
    def __init__(self, session: Session): ...
```

---

## Modulos

### workflow.latex — Parsing compartido ([ADR-0009](../ADR/0009-exercise-module-boundary.md))

Utilidades de parsing reutilizadas por `exercise`, `lecture`, y `tikz`:

| Archivo | Funcion | ADR |
|---------|---------|-----|
| `braces.py` | `extract_brace_arg()`, `extract_macro_args()` — extraccion por conteo de llaves | [0011](../ADR/0011-latex-exercise-parser-strategy.md) |
| `comments.py` | `extract_commented_yaml()`, `strip_comments()` — YAML en comentarios LaTeX | [0011](../ADR/0011-latex-exercise-parser-strategy.md) |
| `normalize.py` | `normalize()`, `convert_math_delimiters()` — expansion de macros personalizados | [0012](../ADR/0012-moodle-xml-export-mapping.md) |

### workflow.exercise — Banco de ejercicios ([ADR-0009](../ADR/0009-exercise-module-boundary.md), [ADR-0010](../ADR/0010-exercise-persistence-model.md))

| Archivo | Responsabilidad |
|---------|----------------|
| `domain.py` | `ParsedExercise`, `ParsedOption`, `ParseResult` (frozen dataclasses) |
| `parser.py` | Parseo de .tex → domain objects (3 pasadas: metadata, estructura, anotaciones) |
| `moodle.py` | `exercise_to_xml()`, `exercises_to_quiz_xml()` — Moodle XML con CDATA |
| `generator.py` | `generate_exercise_file()`, `generate_from_content()` — crear placeholders |
| `selector.py` | `select_exercises()` — seleccion por taxonomia sin duplicados |
| `exam_builder.py` | `build_exam()` — ensamblaje de examen desde seleccion |
| `cli.py` | 8 comandos Click |

**Principio central**: El archivo `.tex` es la fuente de verdad. La DB almacena solo metadatos (`exercise_id`, `source_path`, `file_hash`, `status`, `type`, `difficulty`, `taxonomy_*`, `tags`). El contenido (stem, solucion, opciones) se lee del archivo en tiempo de parseo/exportacion.

### workflow.lecture — Integracion de cursos

| Archivo | Responsabilidad |
|---------|----------------|
| `scanner.py` | Descubrir .tex en directorios de curso, registrar como Notes |
| `note_splitter.py` | Dividir archivos con marcadores `%>` |
| `linker.py` | Extraer `\cite`, `\ref`, `\label`, crear Citation/Link en DB |
| `eval_builder.py` | Puente EvaluationTemplate → ExerciseSlot |
| `cli.py` | 4 comandos Click |

### workflow.graph — Grafo de conocimiento

| Archivo | Responsabilidad |
|---------|----------------|
| `domain.py` | `GraphNode`, `GraphEdge`, `KnowledgeGraph` (frozen dataclasses) |
| `collectors.py` | Consultas a ambas DBs → tipos de dominio |
| `analysis.py` | `find_orphans`, `find_hubs`, `connected_components`, `neighbors`, `compute_stats` |
| `dot_export.py` | Graphviz DOT output con colores por tipo |
| `tikz_export.py` | TikZ output con spring layout (Fruchterman-Reingold) |
| `clustering.py` | Deteccion de comunidades (networkx opcional) |
| `cli.py` | 6 comandos Click |

---

## Patrones de diseno

### Frozen Dataclasses

Todos los tipos de dominio usan `@dataclass(frozen=True)`. Colecciones usan `tuple`, nunca `list`:

```python
@dataclass(frozen=True)
class ParseResult:
    exercise: ParsedExercise | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
```

### Separacion puro/IO

La logica de dominio es pura (sin I/O, sin DB). La interaccion con DB y archivos se aisla en funciones separadas:

```
domain.py    ← tipos puros, sin imports de sqlalchemy/pathlib
parser.py    ← lee archivos, retorna tipos puros
selector.py  ← logica pura sobre listas de Exercise
cli.py       ← maneja DB sessions, llama funciones puras
```

### Click CLI

Todos los CLIs usan Click groups con `@click.pass_context` para inyectar engines:

```python
@click.group()
def exercise() -> None:
    """Exercise bank management."""

@exercise.command(name="list")
@click.option("--status", type=click.Choice([...], case_sensitive=False))
@click.pass_context
def list_exercises(ctx, status, ...):
    engine = _get_engine(ctx)
    with Session(engine) as session:
        ...
```

### Validacion en fronteras

La validacion ocurre en las fronteras del sistema (CLI, parseo de archivos), no en las funciones internas:

- IDs de ejercicio se validan contra regex `^[a-zA-Z0-9._-]+$` en `generator.py`
- Paths se validan contra path traversal en `note_splitter.py` y `moodle.py`
- Tamanno de archivo se limita a 10MB en `cli.py`
- Conteo de archivos se limita a 10,000 en `cli.py`

---

## Decisiones de arquitectura (ADRs)

Ver [docs/ADR/INDEX.md](../ADR/INDEX.md) para el indice completo con dependencias cruzadas.

### Decisiones fundamentales

| ADR | Decision | Impacto |
|-----|----------|---------|
| [0003](../ADR/0003-hybrid-database.md) | DB hibrida (global + local) | Permite datos compartidos + notas por proyecto |
| [0004](../ADR/0004-sqlalchemy-single-orm.md) | SQLAlchemy 2.0 unico ORM | Elimina Peewee, unifica acceso a datos |
| [0010](../ADR/0010-exercise-persistence-model.md) | Archivo como verdad, DB como indice | El .tex es la fuente de verdad, no la DB |
| [0012](../ADR/0012-moodle-xml-export-mapping.md) | Normalizacion antes de Moodle | No depende de config MathJax institucional |
| [ITEP-0002](../ADR/ITEP-0002-four-layer-schema.md) | Esquema de 4 capas | Separacion clara referencia/maestro/template/instancia |

### Decisiones de ejercicios

| ADR | Decision |
|-----|----------|
| [0005](../ADR/0005-exercise-dsl-extends-macros.md) | Extender macros existentes, nunca reemplazar |
| [0009](../ADR/0009-exercise-module-boundary.md) | Modulo exercise + latex compartido |
| [0011](../ADR/0011-latex-exercise-parser-strategy.md) | Parser por conteo de llaves (sin deps) |

---

## Tests

411 tests organizados por modulo:

```
tests/workflow/
  latex/          test_braces, test_comments, test_normalize
  exercise/       test_parser, test_moodle, test_generator, test_selector,
                  test_exam_builder, test_cli
  lecture/        test_scanner, test_note_splitter, test_linker,
                  test_eval_builder, test_cli
  graph/          test_domain, test_collectors, test_analysis,
                  test_dot_export, test_tikz_export, test_clustering, test_cli
  test_exercise_models, test_exercise_repo
```

```bash
uv run pytest tests/workflow/           # todos
uv run pytest tests/workflow/exercise/  # solo ejercicios
uv run pytest -k "test_parse"           # por nombre
```
