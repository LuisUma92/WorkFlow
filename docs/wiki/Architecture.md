# Architecture

Descripcion de la arquitectura del sistema WorkFlow, sus modulos, patrones y decisiones de diseno.

## Vista general

```
src/
  workflow/           # Core del sistema unificado
    db/               # Base de datos (SQLAlchemy 2.0)
                      #   models/, repos/, seed.py, seed_codes.py,
                      #   taxonomy.py, maturation.py, schema_version.py,
                      #   errors.py, migrations/{global,local}/NNNN_*.py
                      #   (runner forward-only, ver ITEP-0010)
    notes/            # Zettelkasten: workspace init, gestion de notas
    exercise/         # Banco de ejercicios (parser, moodle, generator, selector, service)
    lecture/          # Integracion de cursos (scanner, splitter, linker, eval_builder)
    graph/            # Grafo de conocimiento (dominio, collectors, DOT, TikZ, clustering)
    latex/            # Parsing compartido de LaTeX
    tikz/             # Pipeline de diagramas
    validation/       # Validacion de frontmatter (incl. candidate_project)
    project/          # CLI propose-maturation (ITEP-0009)
  itep/               # Scaffolding de proyectos LaTeX
  latexzettel/        # Motor Zettelkasten + servidor JSONL/RPC (24 rutas)
  lectkit/            # Utilidades (cleta)
  PRISMAreview/       # App web Django (PRISMA)
  appfunc/            # Utilidades compartidas
shared/
  latex/
    sty/              # 18 archivos de estilo LaTeX (incl. SetZettelkasten.sty)
    cls/              # texnote.cls y preambulos
    templates/        # Templates para notas, ejercicios, clases
    pandoc/           # Pipeline Pandoc (filter.lua, template.tex, preprocess.py)
```

## Base de datos hibrida ([ADR-0003](../ADR/0003-hybrid-database.md), [ADR ITEP-0011](../ADR/ITEP-0011-vault-unification.md))

Dos bases de datos SQLite con propositos distintos:

```
~/.local/share/workflow/workflow.db     ← GlobalBase (referencia + vault unificado)
<proyecto>/slipbox.db                   ← LocalBase (datos por proyecto, post-ITEP-0011)
```

### GlobalBase — workflow.db

Datos que trascienden proyectos individuales (incluye el **vault Zettelkasten unificado** desde ITEP-0011 P1):

```
Capa 1: Referencia         institution, main_topic, discipline_area
Capa 2: Entidades maestras bib_entry, topic, content, bib_content, concept
Capa 3: Templates          course, course_content, evaluation_template,
                           item, evaluation_item, exercise, exercise_option
Capa 4: Instancias         lecture_instance, general_project
Capa 5: Vault (ITEP-0011)  note, citation, label, link, tag, note_tag, note_concept
```

`note.main_topic_id` es FK real a `main_topic(id)` ON DELETE SET NULL (Phase B).

Ver [ADR ITEP-0002](../ADR/ITEP-0002-four-layer-schema.md) y [ADR ITEP-0011](../ADR/ITEP-0011-vault-unification.md) para detalles.

### LocalBase — slipbox.db

Post-ITEP-0011 P3 las tablas de notas viven en GlobalBase. LocalBase queda como contexto de proyecto:

```
prisma_decision   Decisiones PRISMA por articulo (P5 — pendiente)
project_note      Ideas/hipotesis/conexiones por proyecto (P5 — pendiente)
```

Las tablas legacy de notas (`note`, `label`, `link`, `citation`, `tag`, `note_tag`) siguen presentes en `slipbox.db` files antiguos hasta ITEP-0011 P4 (drop forward-only). Cada proyecto migrado lleva un `.vault_pointer` marker.

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
| [ITEP-0008](../ADR/ITEP-0008-general-project-nomenclature.md) | Nomenclatura `DDTTAA-YYPP-title` + FK catalogo→estado | Estado de `MainTopic` solo puede referenciar `DisciplineArea` reales |
| [ITEP-0010](../ADR/ITEP-0010-schema-versioning-and-migrations.md) | Migraciones forward-only + `schema_version` + `@with_schema_guard` | Errores de esquema dejan de ser tracebacks; `workflow db migrate` es el unico runner |

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
