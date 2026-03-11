# WorkFlow

Toolkit CLI en Python para gestionar proyectos LaTeX orientados a escritura academica (tesis, cursos, ejercicios). Provee herramientas independientes construidas con Click.

## Instalacion

```bash
# Con uv (recomendado)
uv sync

# O con pip (editable)
pip install -e .
```

### Dependencias

`appdirs`, `bibtexparser`, `click`, `pyyaml`, `sqlalchemy`

Python >= 3.10

## Comandos disponibles

| Comando    | Modulo              | Descripcion                             |
| ---------- | ------------------- | --------------------------------------- |
| `workflow` | `main:cli`          | Menu interactivo principal              |
| `inittex`  | `itep.create:cli`   | Crear o clonar un proyecto LaTeX        |
| `relink`   | `itep.links:cli`    | Recrear symlinks desde la base de datos |
| `cleta`    | `lectkit.cleta:cli` | Limpiar archivos auxiliares de TeX      |
| `crete`    | `lectkit.crete:cli` | Crear archivos de ejercicios desde refs |
| `nofi`     | `lectkit.nofi:cli`  | Dividir notas en archivos LaTeX         |

## ITeP - Init TeX Project

Modulo principal para crear y administrar estructuras de proyecto LaTeX. Usa una base de datos SQLite relacional como fuente de verdad.

### Arquitectura

La informacion de proyectos se almacena en una base de datos SQLite ubicada en:

```
~/.local/share/itep/itep.db
```

El archivo `config.yaml` dentro de cada proyecto se reduce a un puntero minimo:

```yaml
project_type: lecture # o "general"
project_id: 42
```

Todo lo demas (institucion, curso, temas, libros, evaluaciones) se consulta desde la DB.

### Esquema de la base de datos

El esquema se organiza en cuatro capas:

**Capa 1 — Datos de referencia** (precargados, rara vez cambian):

- `institution` — Universidades (UCR, UFide, UCIMED) con semanas por ciclo, nombre del ciclo, URL de Moodle.
- `main_topic` — Temas principales de fisica con codigo y clasificacion Dewey.

**Capa 2 — Entidades maestras** (reutilizables):

- `author`, `book`, `book_author` — Libros con autores y roles.
- `topic` — Subtemas dentro de un main_topic.
- `content` — Capitulos/secciones con paginas y ejercicios.
- `book_content` — Asocia libros con contenidos.

**Capa 3 — Templates de curso** (reutilizables entre ciclos):

- `course` — Curso con institucion, codigo, nombre, frecuencia de clases.
- `course_content` — Contenidos asignados a semanas del curso.
- `evaluation_template`, `item`, `evaluation_item` — Templates de evaluacion con items de Bloom.
- `course_evaluation` — Evaluaciones programadas con porcentaje y semana.

**Capa 4 — Instancias de proyecto** (reemplazan config.yaml):

- `lecture_instance` — Instancia de un curso en un ciclo/anno concreto.
- `general_project` — Proyecto general asociado 1:1 con un main_topic.
- `general_project_book`, `general_project_topic` — Asociaciones.

### Uso

#### Crear un proyecto

```bash
# Interactivo: selecciona tipo, institucion, curso, etc.
inittex

# Especificar directorio padre y fuente de templates
inittex -p ~/Documents/Fisica -s ~/.config/mytex
```

El flujo interactivo:

1. Seleccionar tipo de proyecto: `lecture` o `general`
2. Si es **lecture**:
   - Seleccionar institucion (de la DB)
   - Seleccionar curso existente o crear uno nuevo
   - Ingresar anno, ciclo, primer lunes
   - Se crea un `lecture_instance` en la DB
3. Si es **general**:
   - Seleccionar main_topic
   - Seleccionar temas y libros
   - Se crea un `general_project` en la DB
4. Se crean los directorios del proyecto
5. Se escribe `config.yaml` con el puntero a la DB

#### Clonar un ciclo (solo lecture)

```bash
# Clona un lecture_instance existente a un nuevo ciclo
# Hereda curso, temas, libros, evaluaciones
inittex --clone 42
```

Se solicita nuevo anno, ciclo y primer lunes. El curso y todo su contenido se reutilizan.

#### Recrear symlinks

```bash
# Desde el directorio del proyecto
relink

# O especificar el directorio
relink /ruta/al/proyecto
```

Lee el `config.yaml`, consulta la DB y recrea todos los symlinks.

### Estructura de directorios generada

**Proyecto general** (`{codigo}-{nombre}`):

```
10MC-MecanicaClasica/
  config.yaml
  bib/
  config/
  img/
  projects/
  tex/
    000-0-Glossaries/
    000-1-Summaries/
    000-2-Notes/
    001-Cinematica/
    002-Dinamica/
```

**Proyecto lecture** (`{institucion}-{codigo_curso}`):

```
UCR-FS0121/
  config.yaml
  admin/
  eval/
    config/
    img/
    tex/
      001-Cinematica/
  lect/
    bib/
    config/
    img/
    svg/
    tex/
      001-Cinematica/
```

### Operaciones CRUD (modulo `manager`)

El modulo `itep.manager` provee funciones para operar directamente sobre la DB:

```python
from itep.database import get_session, init_db, seed_reference_data
from itep import manager

engine = init_db()
session = get_session(engine)
seed_reference_data(session)

# Instituciones
inst = manager.get_institution_by_short_name(session, "UCR")

# Cursos
course = manager.create_course(session, inst.id, "FS0121", "Fisica General I")

# Temas
mt = manager.get_main_topic_by_code(session, "10MC")
topic = manager.create_topic(session, mt.id, "Cinematica", 1)

# Contenidos
content = manager.create_content(session, topic.id, 1, 1, "Posicion", 1, 25)
manager.add_course_content(session, course.id, content.id, lecture_week=1)

# Instancias
from datetime import date
li = manager.create_lecture_instance(
    session, course.id, 2026, 1, date(2026, 3, 9),
    "/home/user/docs", "/home/user/.config/mytex",
)

# Clonar a nuevo ciclo
cloned = manager.clone_lecture_instance(
    session, li.id, 2026, 2, date(2026, 8, 10),
)

# Proyectos generales
gp = manager.create_general_project(
    session, mt.id, "/home/user/docs", "/home/user/.config/mytex",
    topic_ids=[topic.id], book_ids=[],
)
```

## LectKit

### CleTA - Clean TeX Auxiliary

Elimina archivos auxiliares comunes de LaTeX (`.aux`, `.log`, `.out`, etc.).

```bash
cleta
```

### NoFi - Notes to Files

Toma un archivo TeX plano y crea subarchivos usando marcadores `%>ruta/archivo.tex` y `%>END`.

```bash
nofi archivo.tex
```

Ejemplo de marcadores:

```tex
%>tex/C1/C1S1-001-file.tex
Contenido que se copiara al archivo C1S1-001-file.tex
%>END
```

### CreTE - Create TeX Exercises

Crea archivos de ejercicios a partir de metadatos JSON de libros de referencia.

```bash
crete
```

## PRISMAreview

Herramientas para revision sistematica PRISMA. **Estado: en pausa** (en desarrollo en otro repositorio).

## Tests

```bash
# Todos los tests
uv run pytest

# Un archivo especifico
uv run pytest tests/test_database.py

# Con detalle
uv run pytest -v
```

## Lint

```bash
# Errores criticos
uv run flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Completo
uv run flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

## CI

GitHub Actions en push/PR a `master`. Tests en Python 3.9, 3.10, 3.11.
